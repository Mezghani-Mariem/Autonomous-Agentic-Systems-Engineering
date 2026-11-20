import csv
import io
from collections import Counter, defaultdict
from datetime import datetime

from pydantic import BaseModel, Field

from slr.course.plan_and_execute import evaluate_plan
from slr.course.rag_pipeline import retrieval_metrics


class Annotation(BaseModel):
    paper_id: str = Field(min_length=1)
    label: str
    annotator: str = Field(min_length=1)
    protocol: str = Field(min_length=1)


def load_annotations(text):
    required = {"paper_id", "label", "annotator", "protocol"}
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not required <= set(reader.fieldnames or []):
        raise ValueError("CSV requires paper_id, label, annotator and protocol columns")
    annotations = {}
    for data in reader:
        row = Annotation.model_validate({key: (data.get(key) or "").strip() for key in required})
        if row.label not in {"include", "exclude"}:
            raise ValueError(f"Invalid label for {row.paper_id}")
        if row.paper_id in annotations:
            raise ValueError(f"Provide a single adjudicated label per paper: {row.paper_id}")
        annotations[row.paper_id] = row
    return annotations


def divide(value, total):
    return value / total if total else None


def screening_metrics(predictions, annotations):
    if not annotations:
        return None
    matrix = dict(tp=0, fp=0, tn=0, fn=0)
    abstentions = positive_abstentions = matched = 0
    for identifier, row in annotations.items():
        if identifier not in predictions:
            continue
        matched += 1
        prediction = predictions[identifier]
        if prediction in {"include", "exclude"}:
            expected = row.label
            key = {("include", "include"): "tp", ("include", "exclude"): "fp",
                   ("exclude", "exclude"): "tn", ("exclude", "include"): "fn"}[prediction, expected]
            matrix[key] += 1
        else:
            abstentions += 1
            positive_abstentions += row.label == "include"
    tp, fp, tn, fn = (matrix[key] for key in ("tp", "fp", "tn", "fn"))
    return {
        **matrix,
        "precision": divide(tp, tp + fp), "recall": divide(tp, tp + fn),
        "f1": divide(2 * tp, 2 * tp + fp + fn), "false_negative_rate": divide(fn, fn + tp),
        "annotated": len(annotations), "matched": matched, "decided": sum(matrix.values()),
        "abstentions": abstentions, "positive_abstentions": positive_abstentions,
    }


def retrieval_quality(result, labels=None):
    values = {
        "rq_id": result.rq_id, "method": result.method, "status": result.status,
        "retrieval_calls": result.calls, "selected": len(result.ranks),
        "requested_k": result.requested_k,
        "facet_coverage": divide(len(result.covered), len(result.covered) + len(result.missing)),
        "covered": result.covered, "missing": result.missing, "ranks": result.ranks,
        "query": result.query, "extraction": result.extraction.model_dump(mode="json") if result.extraction else None,
        "precision_at_k": None, "recall_at_k": None,
    }
    if labels is not None:
        reference = set(labels)
        course = retrieval_metrics(result.ranks, reference)
        hits = len(set(result.ranks) & reference)
        values["precision_at_k"] = divide(hits, result.requested_k or len(result.ranks))
        values["recall_at_k"] = course["recall_at_k"] if reference else None
        values["precision_among_returned"] = course["precision_at_k"] if result.ranks else None
    return values


def event_stats(events):
    labels = defaultdict(list)
    for event in events:
        labels[(event.stage, event.kind, event.operation)].append(event)
    rows = []
    for (stage, kind, operation), group in labels.items():
        actual = [item for item in group if item.status != "cache_hit"]
        rows.append({
            "stage": stage, "kind": kind, "operation": operation,
            "calls": len(actual), "cache_hits": len(group) - len(actual),
            "successes": sum(e.status == "ok" for e in actual),
            "failures": sum(e.status == "error" for e in actual),
            "retries": sum(e.retry for e in actual),
            "latency_seconds": round(sum(e.seconds for e in group), 4),
            "input_tokens": sum(e.input_tokens or 0 for e in actual),
            "output_tokens": sum(e.output_tokens or 0 for e in actual),
            "calls_with_token_usage": sum(e.input_tokens is not None or e.output_tokens is not None for e in actual),
        })
    return rows


def review_metrics(run, annotations=None, relevance=None):
    required = {"RQ1", "RQ2", "RQ3"}
    plan = {}
    if run.plan:
        protocol = run.plan.protocol
        plan = {"research_question_validity": len({q.identifier for q in run.plan.questions} & required) / 3,
                "query_validity": sum(bool(q.strip()) for q in protocol.queries.values()) / 3,
                "repair_attempts": run.plan.repair_attempts,
                "protocol_repairs": run.plan.protocol_repairs,
                "plan": evaluate_plan(run.plan.plan, set(), required).model_dump()}
    flow = {"discovered": 0, "deduplicated": 0, "duplicates": 0, "screened": 0,
            "included": 0, "excluded": 0, "pending": 0, "unresolved": 0,
            "automatically_included": 0, "automatically_excluded": 0}
    search = {}
    if run.search:
        flow.update(discovered=run.search.discovered, deduplicated=len(run.search.papers),
                    duplicates=run.search.duplicates)
        observations = run.search.state.observations
        search = {"tool_counts": dict(Counter(e.tool for e in observations if e.tool)),
                  "successful_tool_actions": sum(e.status in {"success", "empty"} for e in observations),
                  "failed_tool_actions": sum(e.status not in {"success", "empty"} for e in observations),
                  "observed_latency_seconds": round(sum(e.latency_seconds for e in observations), 4),
                  "stop_reason": run.search.state.stop_reason}
    screening = {}
    if run.screening:
        decisions = run.screening.decisions
        counts = run.screening.counts()
        flow.update(screened=len(decisions), pending=counts["unresolved"], **counts)
        fields = ("rule", "llm", "final") if any(item.rule is not None for item in decisions) else ("llm", "final")
        screening = {field: screening_metrics({d.paper_id: getattr(d, field) for d in decisions}, annotations)
                     for field in fields}
    retrieval = [retrieval_quality(r, (relevance or {}).get(r.rq_id)) for r in run.rag.retrieval] if run.rag else []
    writing = {}
    if run.draft:
        execution = run.draft.execution
        plan_metrics = evaluate_plan(execution.plan, {e.id for e in run.rag.evidence}, required)
        writing = {**plan_metrics.model_dump(), "completed_steps": len(execution.sections),
                   "dependency_validity": plan_metrics.consistency, "execution_actions": execution.tool_calls,
                   "status": execution.status}
    quality = [{
        **item.model_dump(mode="json"),
        "detected_unsupported": sum(f.judgment == "unsupported" for f in item.findings),
        "uncertain": sum(f.judgment == "uncertain" for f in item.findings),
    } for item in run.quality]
    events = event_stats(run.events)
    services = [r for r in events if r["kind"] in {"api", "llm", "embedding"}]
    return {
        "configuration": run.config.model_dump(mode="json"),
        "flow": flow, "planner": plan, "search": search, "screening": screening, "retrieval": retrieval,
        "screening_audit": run.screening.model_dump(mode="json") if run.screening else None,
        "evidence_corpus": run.rag.corpus.model_dump(mode="json") if run.rag and run.rag.corpus else None,
        "planning_execution": writing, "quality": quality,
        "human_claim_judgments": [d.model_dump(mode="json") for d in run.adjudications],
        "overall": {
            "status": run.status, "task_completed": run.status == "complete", "outcome_reason": run.outcome_reason,
            "withheld_claims": len(run.withheld_claim_ids),
            "active_seconds": round(sum(e.seconds for e in run.events if e.kind == "agent"), 4),
            "elapsed_seconds": (datetime.fromisoformat(run.updated) - datetime.fromisoformat(run.created)).total_seconds(),
            "input_tokens": sum(e["input_tokens"] for e in services),
            "output_tokens": sum(e["output_tokens"] for e in services),
            "calls_with_token_usage": sum(e["calls_with_token_usage"] for e in services),
            "api_errors": sum(e["failures"] for e in services if e["kind"] == "api"),
            "retries": sum(e["retries"] for e in services),
            "human_interventions": sum(e.kind == "human" for e in run.events),
            "revision_success": (
                not bool(run.quality[-1].feedback) if run.revision and run.quality else None
            ),
        },
        "events_by_agent": events,
    }


def to_csv(value):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "value"])
    def flatten(node, path):
        if isinstance(node, dict):
            for key, item in node.items():
                flatten(item, (*path, key))
        elif isinstance(node, list):
            for index, item in enumerate(node):
                flatten(item, (*path, str(index)))
        else:
            writer.writerow([".".join(path), node])
    flatten(value, ())
    return output.getvalue()
