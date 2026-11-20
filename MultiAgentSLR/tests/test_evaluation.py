import json

import pytest

from evaluation.benchmarks import rule_screening_baseline, run_benchmark
from evaluation.metrics import load_annotations, screening_metrics, to_csv
from slr.course.agentic_rag_models import EvidenceFacet
from slr.course.rag_models import Chunk
from slr.retrieval import retrieve
from slr.settings import Settings
from slr.sources import consolidate

from conftest import CourseSnapshot


def test_screening_metrics_require_and_count_labels():
    assert screening_metrics({"x": "include"}, None) is None
    labels = load_annotations(
        "paper_id,label,annotator,protocol\nx,include,test,protocol\n"
        "y,include,test,protocol\nz,exclude,test,protocol\nw,include,test,protocol\n"
    )
    result = screening_metrics({"x": "include", "y": "exclude", "z": "include", "w": "uncertain"}, labels)
    assert (result["tp"], result["fp"], result["fn"], result["tn"]) == (1, 1, 1, 0)
    assert result["precision"] == result["recall"] == result["f1"] == 0.5
    assert result["false_negative_rate"] == 0.5 and result["positive_abstentions"] == 1
    assert "precision,0.5" in to_csv(result)


def test_rule_baseline_runs_independently_of_a_model():
    papers = consolidate([CourseSnapshot().record])
    decision, = rule_screening_baseline(papers, ["screening"], ["clinical trial"])
    assert decision.rule == "include" and decision.decided_by == "rule"
    assert decision.llm is None


def test_retrieval_budget_is_enforced_when_facets_missing():
    chunks = [Chunk(paper_id="p", chunk_id="p1", page=1, text="Actual review topic text")]
    facets = [EvidenceFacet(id="missing", label="Missing", keywords=["unavailable"], query_hint="something else")]
    _, output = retrieve(chunks, "review topic", facets, "RQ1", "agentic", 1, 1)
    assert output.calls == 1 and output.status == "budget_exhausted"
    assert output.missing == ["missing"]


@pytest.mark.parametrize("key", ["a", "c", "d"])
def test_controlled_benchmarks_save_provenance_and_outputs(tmp_path, key):
    location, report = run_benchmark(key, Settings(experiment_dir=tmp_path, data_dir=tmp_path))
    assert {"inputs.json", "outputs.json", "metadata.json", "prompts.json", "events.json"} <= {p.name for p in location.iterdir()}
    metadata = json.loads((location / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["data_sha256"] and metadata["conditions"]
    output = report["outputs"]
    if key == "a":
        assert output["fixed"]["tool_order"] != output["react"]["tool_order"]
    elif key == "c":
        assert all(arm["precision_at_k"] is not None for pair in output.values() for arm in pair.values())
    else:
        assert output["fixed"]["status"] == "ESCALATE" and output["supervisor"]["status"] == "FINISH"
