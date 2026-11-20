import json
import os
from dataclasses import replace
from io import BytesIO

import httpx
import pytest
from pypdf import PdfReader

from slr.gateway import Calls, build_model, Telemetry
from evaluation.metrics import review_metrics
from slr.models import ReviewConfig, SOURCES
from slr.report import markdown, pdf
from slr.retrieval import build_corpus
from slr.settings import Settings
from slr.sources import ScientificSources
from slr.storage import DiskStore
from slr.supervisor import Supervisor

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("SLR_RUN_LIVE") != "1", reason="Set SLR_RUN_LIVE=1 to make real requests"),
]


@pytest.mark.parametrize("source", SOURCES)
def test_live_bibliographic_source(tmp_path, source):
    settings = Settings.from_env()
    telemetry = Telemetry()
    with httpx.Client(timeout=settings.timeout) as client:
        records = ScientificSources(settings, Calls(DiskStore(tmp_path), telemetry, 0), client).search(
            source, "systematic review screening", 1)
        assert records and records[0].title
        assert any(event.kind == "api" and event.status == "ok" for event in telemetry.events)


@pytest.mark.parametrize("provider", ["ollama", "groq"])
def test_live_model_round_trip(tmp_path, provider):
    from pydantic import BaseModel
    class Reply(BaseModel):
        answer: str

    settings = Settings.from_env()
    if provider not in os.getenv("SLR_LIVE_PROVIDERS", settings.provider).split(","):
        pytest.skip("Provider is outside the requested live smoke checks")
    model = build_model(settings, provider, Calls(DiskStore(tmp_path), Telemetry(), 0))
    reply = model.with_structured_output(Reply).invoke("Return an answer field with the string ready.")
    assert reply.answer.strip().lower() == "ready"


@pytest.mark.skipif(os.getenv("SLR_RUN_LIVE_REVIEW") != "1",
                    reason="Set SLR_RUN_LIVE_REVIEW=1 to run the Ollama evidence workflow")
def test_live_automatic_review_exports_referenced_report(tmp_path):
    settings = replace(Settings.from_env(), cache_ttl=0)
    supervisor = Supervisor(DiskStore(tmp_path), settings, record_prompts=True)
    config = ReviewConfig(
        topic="How are large language models evaluated for title and abstract screening in systematic literature reviews?",
        provider="ollama", execution_mode="automatic", per_source=4,
    )
    run = supervisor.start(config)
    output = settings.experiment_dir / "live" / run.id
    output.mkdir(parents=True, exist_ok=True)
    (output / "run.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")
    (output / "prompts.json").write_text(json.dumps(supervisor.prompts, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics = review_metrics(run)
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Live review artifact: {output}")
    print(f"Outcome: {run.status}, screening: {metrics['flow']}")
    if run.rag:
        print(f"Usable abstracts: {run.rag.corpus.included_abstracts}, "
              f"retrieved chunks: {sum(len(item.ranks) for item in run.rag.retrieval)}, "
              f"verified evidence passages: {len(run.rag.evidence)}")
    assert run.status == "complete", run.error or run.outcome_reason
    assert run.screening.policy == "llm-evidence-v1"
    assert any(event.kind == "api" and event.status == "ok" for event in run.events)
    assert any(event.kind == "llm" and event.stage == "screening" and event.operation.startswith("ollama:")
               and event.status == "ok" for event in run.events)
    assert all(item.decided_by == "ai" for item in run.screening.decisions if item.final != "uncertain")
    included = {item.paper_id for item in run.screening.decisions if item.final == "include"}
    assert included and all(item.quote_verified is True for item in run.screening.decisions
                            if item.final != "uncertain")
    evidence = {item.id: item for item in run.rag.evidence}
    corpus = {chunk.chunk_id: chunk for chunk in build_corpus(run.search.papers, included, {})}
    assert evidence and all(item.source_type == "abstract" and item.page is None for item in evidence.values())
    assert all(item.quote in corpus[item.chunk_id].text and item.paper_id == corpus[item.chunk_id].paper_id
               and item.source_record_id for item in evidence.values())
    assert any(event.stage == "writing" and event.kind == "llm" and event.status == "ok" for event in run.events)
    assert any(event.stage == "quality" and event.kind == "llm" and event.status == "ok" for event in run.events)
    claims = run.retained_claims()
    assert claims and all(claim.evidence_ids for claim in claims)
    assert all(evidence[ref].paper_id in included for claim in claims for ref in claim.evidence_ids)
    report = markdown(run)
    assert "## References" in report and "AI decisions are recorded separately" in report
    exported = pdf(run)
    assert any("References" in page.extract_text() for page in PdfReader(BytesIO(exported)).pages)
    (output / "literature-review.md").write_text(report, encoding="utf-8")
    (output / "literature-review.pdf").write_bytes(exported)
