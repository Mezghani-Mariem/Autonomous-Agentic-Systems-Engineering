import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx

from slr.course.agentic_rag_models import AgenticCase
from slr.course.orchestrator import full_pipeline_run, full_supervisor_run
from slr.course.planning_models import EvidenceItem
from slr.course.quality_agent import evaluate_rules
from slr.course.quality_models import SharedState
from slr.course.rag_pipeline import chunk_pages
from slr.gateway import Calls, MeasuredEmbeddings, Telemetry, build_model
from slr.course.screening_agent import ScreeningAgent
from slr.models import ReviewConfig, ScreeningDecision, SourceRecord, now
from slr.retrieval import retrieve
from slr.screen import screen_papers
from slr.sources import consolidate, normalize_doi, search_review
from slr.storage import DiskStore

from .metrics import event_stats, retrieval_quality, screening_metrics

DATA = Path(__file__).resolve().parents[1] / "experiments" / "datasets"
TOPIC = "Large language models for title and abstract screening in systematic literature reviews"
BENCHMARKS = {
    "a": "Fixed Search vs ReAct Search",
    "b": "Rule-Based vs LLM Screening",
    "c": "Classical RAG vs Agentic RAG",
    "d": "Fixed Pipeline vs Quality-Driven Supervisor",
}


def dataset(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def records_from_course(data):
    return [
        SourceRecord.model_validate({
            **row, "native_id": row["id"], "doi": normalize_doi(row.get("doi")),
        })
        for row in data
    ]


def fixed_vs_react():
    rows = records_from_course(dataset("search_catalog.json"))
    queries = {key: "systematic review screening" for key in ("openalex", "semantic_scholar", "crossref")}
    limit = 2

    class Replay:
        def search(self, source, query, cap):
            if source == "openalex":
                request = httpx.Request("GET", "https://api.openalex.org/works")
                raise httpx.HTTPStatusError("Course simulation", request=request,
                                            response=httpx.Response(429, request=request))
            return [row for row in rows if row.source == source][:cap]

    outputs = {}
    for mode in ("fixed", "react"):
        result = search_review(TOPIC, queries, limit, mode, Replay())
        outputs[mode] = {
            "discovered": result.discovered, "unique": len(result.papers), "duplicates": result.duplicates,
            "tool_order": [obs.tool for obs in result.state.observations],
            "tool_statuses": [obs.status for obs in result.state.observations], "state": result.model_dump(mode="json"),
        }
    return {"queries": queries, "per_source": limit, "rate_limit_simulation": "OpenAlex HTTP 429 in both arms",
            "records": [row.model_dump(mode="json") for row in rows], "tools_budget": 3}, outputs


def rule_screening_baseline(papers, inclusion_terms, exclusion_terms):
    result = ScreeningAgent().run(papers, set(inclusion_terms), set(exclusion_terms))
    return [
        ScreeningDecision(
            paper_id=row.paper_id, rule=row.decision,
            final="uncertain" if row.needs_human_review else row.decision,
            decided_by="pending" if row.needs_human_review else "rule",
            reason=" ".join(row.reasons), rule_reason=" ".join(row.reasons),
        )
        for row in result["decisions"]
    ]


def screening_pair(settings, telemetry, annotations):
    papers = consolidate(records_from_course(dataset("screening_snapshot.json")["papers"]))
    include_signals = ["slr", "screening", "systematic review"]
    exclude_signals = ["medicine", "clinical trial"]
    config = ReviewConfig(topic=TOPIC, provider=settings.provider, execution_mode="human_in_the_loop")
    telemetry.stage = "screening"
    model = build_model(settings, settings.provider, Calls(DiskStore(settings.data_dir), telemetry, 0))
    outputs = {}
    arms = {
        "rules": rule_screening_baseline(papers, include_signals, exclude_signals),
        "llm": screen_papers(papers, config, model).decisions,
    }
    for mode, decisions in arms.items():
        raw_predictions = {item.paper_id: item.rule if mode == "rules" else item.llm for item in decisions}
        predictions = {item.paper_id: item.final for item in decisions}
        outputs[mode] = {
            "decisions": [item.model_dump(mode="json") for item in decisions],
            "raw_decision_metrics": screening_metrics(raw_predictions, annotations),
            "automatic_policy_metrics": screening_metrics(predictions, annotations),
            "assessed_predictions": sum(p in {"include", "exclude"} for p in raw_predictions.values()),
            "pending": sum(item.final == "uncertain" for item in decisions),
        }
    return {"config": config.model_dump(mode="json"), "paper_count": len(papers),
            "papers": [paper.model_dump(mode="json") for paper in papers],
            "include_signals": include_signals, "exclude_signals": exclude_signals,
            "annotations": {key: val.model_dump(mode="json") for key, val in (annotations or {}).items()},
            "call_cap": "one structured screening decision per paper with an abstract; one transport retry"}, outputs


def retrieval_pair(settings, telemetry):
    manifest = dataset("document_manifest.json")
    pages = dataset("extracted_pages.json")
    chunks = [
        chunk for entry in manifest["documents"] if entry["status"] == "downloaded"
        for chunk in chunk_pages(entry["paper_id"], pages[entry["extracted_pages_key"]], size=1000, overlap=0)
    ]
    cases = [AgenticCase.model_validate(item) for item in dataset("retrieval_cases.json")["cases"]]
    embeddings = None
    if settings.embedding_model:
        telemetry.stage = "rag"
        embeddings = MeasuredEmbeddings(settings, Calls(DiskStore(settings.data_dir), telemetry, 0))
    outputs = {}
    for case in cases:
        if not set(case.relevant_chunk_ids) <= {chunk.chunk_id for chunk in chunks}:
            raise ValueError("The supplied labels do not match the chunking configuration")
        outputs[case.id] = {}
        for mode in ("classical", "agentic"):
            started = perf_counter()
            _, result = retrieve(chunks, case.question, case.facets, case.id, mode, case.baseline_k, 2, embeddings)
            outputs[case.id][mode] = {
                **retrieval_quality(result, case.relevant_chunk_ids),
                "elapsed_seconds": perf_counter() - started,
                "trace": [event.model_dump(mode="json") for event in result.trace],
            }
    return {"chunks": [c.model_dump(mode="json") for c in chunks], "chunk_size": 1000, "overlap": 0,
            "cases": [c.model_dump(mode="json") for c in cases], "max_retrieval_calls_per_question": 2,
            "embeddings": settings.embedding_model or None}, outputs


def orchestration_pair():
    evidence_payload = dataset("synthesis_evidence.json")
    writing = dataset("writing_artifact.json")
    search = dataset("screening_snapshot.json")
    evidence = [EvidenceItem.model_validate(row) for row in evidence_payload["evidence"]]
    draft, repaired = writing["draft_report"], writing["repaired_report"]
    required = set(evidence_payload["required_rqs"])

    def evaluate(report):
        return evaluate_rules(report, evidence, required)

    def workers():
        calls = []
        def writer(state):
            calls.append(state.quality)
            return repaired if len(calls) > 1 else draft
        return {
            "search": lambda _: search, "screening": lambda _: {"fixture": "course screening boundary"},
            "rag": lambda _: evidence_payload, "writing": writer, "quality": lambda s: s.report,
        }

    initial = SharedState(objective=TOPIC, report=draft, evidence_ids=[item.id for item in evidence], budget_left=8)
    outputs = {}
    for mode in ("fixed", "supervisor"):
        started = perf_counter()
        result = (full_pipeline_run(initial, workers(), evaluate) if mode == "fixed"
                  else full_supervisor_run(initial, workers(), evaluate, max_handoffs=8))
        outputs[mode] = {"status": result.status, "actions": result.actions, "transitions": result.transitions,
                         "before": evaluate(draft).model_dump(mode="json"),
                         "after": result.state.quality.model_dump(mode="json"),
                         "wall_seconds": perf_counter() - started,
                         "handoffs": [item.model_dump(mode="json") for item in result.handoffs],
                         "used_supplied_revision": result.state.report == repaired}
    return {"source_snapshot": search, "evidence": evidence_payload, "writing": writing,
            "transition_budget": 8, "settings": "TD08 deterministic lexical quality rules, threshold 0.80"}, outputs


def run_benchmark(key, settings, annotations=None):
    telemetry = Telemetry(record_prompts=True)
    started = now()
    clock = perf_counter()
    if key == "a":
        inputs, outputs = fixed_vs_react()
    elif key == "b":
        inputs, outputs = screening_pair(settings, telemetry, annotations)
    elif key == "c":
        inputs, outputs = retrieval_pair(settings, telemetry)
    elif key == "d":
        inputs, outputs = orchestration_pair()
    else:
        raise ValueError("Unknown benchmark")
    files = {
        "a": ["search_catalog.json"], "b": ["screening_snapshot.json"],
        "c": ["document_manifest.json", "extracted_pages.json", "retrieval_cases.json"],
        "d": ["synthesis_evidence.json", "writing_artifact.json", "screening_snapshot.json"],
    }[key]
    key_name = f'{started[:19].replace(":", "-")}-{key}-{uuid4().hex[:10]}'
    output = settings.experiment_dir / "runs" / key_name
    output.mkdir(parents=True)
    meta = {
        "id": key_name, "benchmark": key, "title": BENCHMARKS[key], "started_utc": started,
        "elapsed_seconds": perf_counter() - clock, "cache": "disabled for provider calls",
        "conditions": {"a": "course catalog replay with the TD03 simulated HTTP 429",
                       "b": "same saved historical source records, real configured LLM for the LLM arm",
                       "c": "fixed course annotations withheld from retrieval, local embeddings only if configured",
                       "d": "TD08 artifact replay and supplied revision, no live writing or retrieval"}[key],
        "data_sha256": {name: hashlib.sha256((DATA / name).read_bytes()).hexdigest() for name in files},
        "implementation_sha256": {
            file.relative_to(DATA.parents[1]).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
            for folder in ("slr", "evaluation") for file in sorted((DATA.parents[1] / folder).rglob("*.py"))
        },
        "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                    **{name: version(name) for name in ("pydantic", "langchain-core", "httpx")}},
        "model_config": {"provider": settings.provider if key == "b" else None,
                         "model": (settings.ollama_model if settings.provider == "ollama" else settings.groq_model)
                         if key == "b" else None,
                         "embedding": (settings.embedding_model or None) if key == "c" else None,
                         "temperature": 0 if key == "b" else None},
        "events": event_stats(telemetry.events),
    }
    for name, value in {
        "inputs": inputs, "outputs": outputs, "prompts": telemetry.prompts,
        "events": [event.model_dump(mode="json") for event in telemetry.events], "metadata": meta,
    }.items():
        (output / f"{name}.json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return output, {"metadata": meta, "outputs": outputs}
