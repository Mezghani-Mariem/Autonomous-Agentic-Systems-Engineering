import json

import pytest

from evaluation.metrics import review_metrics
from slr.gateway import GatewayError
from slr.models import ReviewRun, SourceRecord
from slr.report import markdown
from slr.settings import Settings
from slr.storage import DiskStore
from slr.supervisor import Supervisor

from conftest import ControlledModel, CourseSnapshot, Structured


class ScreeningCases:
    def __init__(self):
        include = CourseSnapshot().record
        self.records = [
            include,
            SourceRecord(source="crossref", native_id="fixture-exclude", title="Treatment efficacy",
                         abstract="This clinical trial studied treatment efficacy outside the review domain."),
            SourceRecord(source="crossref", native_id="fixture-disagreement", title="A screening protocol",
                         abstract="This screening protocol describes an out-of-scope population."),
            SourceRecord(source="crossref", native_id="fixture-missing", title="A record without an abstract"),
        ]

    def search(self, source, query, limit):
        return [record for record in self.records if record.source == source][:limit]


class MixedScreeningModel(ControlledModel):
    def with_structured_output(self, schema):
        return MixedScreeningResponses(self, schema)


class MixedScreeningResponses(Structured):
    def LLMScreeningDecision(self, messages):
        abstract = messages[-1].content.partition("Résumé : ")[2]
        if "clinical trial" in abstract or "out-of-scope population" in abstract:
            return {"paper_id": "fixture", "decision": "exclude", "confidence": 0.93,
                    "reasons": ["The record is outside the topic."], "evidence": abstract,
                    "needs_human_review": False}
        return super().LLMScreeningDecision(messages)


def test_automatic_finishes_with_mixed_screening_and_discloses_withholding(tmp_path, config, monkeypatch):
    from slr.course.screening_agent import ScreeningAgent

    def rules_called(*args, **kwargs):
        raise AssertionError("The main workflow must not use the rule baseline")

    monkeypatch.setattr(ScreeningAgent, "run", rules_called)
    store = DiskStore(tmp_path)
    supervisor = Supervisor(store, Settings(), model=MixedScreeningModel(), sources=ScreeningCases())
    run = supervisor.start(config.model_copy(update={"per_source": 5}))
    assert config.execution_mode == "automatic"
    assert run.status == "complete", run.error
    saved = store.load(run.id)
    counts = saved.screening.counts()
    assert counts == {"included": 1, "excluded": 2, "unresolved": 1,
                      "automatically_included": 1, "automatically_excluded": 2}
    assert saved.screening.policy == "llm-evidence-v1"
    decisions = {item.paper_id: item for item in saved.screening.decisions}
    assert all(item.rule is None for item in decisions.values())
    assert all(item.quote_verified is True for item in decisions.values() if item.final != "uncertain")
    assert {item.decided_by for item in decisions.values() if item.final != "uncertain"} == {"ai"}
    assert {item.paper_id for item in saved.rag.evidence} == {
        item.paper_id for item in decisions.values() if item.final == "include"
    }
    report = markdown(saved)
    assert "included 1, excluded 2, and left 1 unresolved" in report
    assert "Unresolved screening records" in report and "were withheld from retrieval" in report
    assert "Full text was unavailable" in report
    metrics = review_metrics(saved)
    assert metrics["flow"]["pending"] == metrics["flow"]["unresolved"] == 1
    assert len(metrics["screening_audit"]["decisions"]) == 4
    assert "rule" not in metrics["screening"]


@pytest.mark.parametrize("empty_search", [False, True])
def test_automatic_stops_when_eligible_set_is_empty(tmp_path, config, empty_search):
    source = CourseSnapshot(missing_abstract=True)
    if empty_search:
        source.search = lambda source, query, limit: []
    store = DiskStore(tmp_path)
    run = Supervisor(store, Settings(), model=ControlledModel(), sources=source).start(config)
    assert run.status == "insufficient_evidence"
    assert store.load(run.id).screening.counts()["included"] == 0
    assert run.handoffs[-1].source == "screening" and run.handoffs[-1].status == "blocked"
    assert run.rag is None and run.draft is None
    with pytest.raises(ValueError, match="No studies met the inclusion policy"):
        markdown(run)


def test_automatic_claim_gate_keeps_only_supported_claims(tmp_path, config):
    supervisor = Supervisor(DiskStore(tmp_path), Settings(), model=ControlledModel(invalid_citation=True),
                            sources=CourseSnapshot())
    run = supervisor.start(config.model_copy(update={"revision_budget": 0}))
    assert run.status == "complete", run.error
    assert run.withheld_claim_ids == ["C1"]
    assert run.retained_claims() and all(claim.id != "C1" for claim in run.retained_claims())
    report = markdown(run)
    assert "(C1," not in report and "Quality review withheld 1" in report


def test_automatic_stops_without_supported_claims(tmp_path, config):
    supervisor = Supervisor(DiskStore(tmp_path), Settings(), model=ControlledModel(reject_claim=True),
                            sources=CourseSnapshot())
    run = supervisor.start(config)
    assert run.status == "insufficient_evidence" and run.revision == config.revision_budget
    assert run.rag.evidence and run.withheld_claim_ids and not run.retained_claims()
    assert "No supported, cited claims" in run.outcome_reason


@pytest.mark.parametrize("overrides", [
    {"confidence": 0.79},
    {"confidence": None},
    {"evidence": "An invented excerpt absent from the record."},
    {"evidence": "screening"},
    {"reasons": ["  "]},
    {"decision": "maybe"},
    {"needs_human_review": True},
])
def test_screening_flags_withhold_invalid_or_weak_llm_verdicts(tmp_path, config, overrides):
    class FlaggedResponses(Structured):
        def LLMScreeningDecision(self, messages):
            return {**super().LLMScreeningDecision(messages), **overrides}

    class FlaggedModel(ControlledModel):
        def with_structured_output(self, schema):
            return FlaggedResponses(self, schema)

    supervisor = Supervisor(DiskStore(tmp_path), Settings(), model=FlaggedModel(), sources=CourseSnapshot())
    run = supervisor.start(config)
    assert run.status == "insufficient_evidence"
    assert run.screening.decisions[0].final == "uncertain"
    if overrides.get("evidence", "").startswith("An invented excerpt"):
        item = run.screening.decisions[0]
        assert item.llm == "include" and item.quote == overrides["evidence"]
        assert item.quote_verified is False
    assert run.rag is None


def test_eligible_study_without_verified_passages_does_not_generate_report(tmp_path, config):
    class EmptyExtraction(Structured):
        def Extraction(self, prompt):
            return {"selections": []}

    class NoEvidence(ControlledModel):
        def with_structured_output(self, schema):
            return EmptyExtraction(self, schema)

    supervisor = Supervisor(DiskStore(tmp_path), Settings(), model=NoEvidence(), sources=CourseSnapshot())
    run = supervisor.start(config)
    assert run.screening.counts()["included"] == 1
    assert run.status == "insufficient_evidence" and run.handoffs[-1].source == "rag"
    assert not run.rag.evidence and run.draft is None
    assert {item.extraction.status for item in run.rag.retrieval} == {"empty_selection"}
    with pytest.raises(ValueError, match="no verified passages"):
        markdown(run)
    retry = Supervisor(supervisor.store, Settings(), model=ControlledModel())
    recovered = retry.retry_retrieval(supervisor.store.load(run.id))
    assert recovered.status == "complete", recovered.error or recovered.outcome_reason
    assert recovered.screening == run.screening and recovered.search == run.search
    assert any(event.operation == "retry_retrieval" for event in recovered.events)


def test_failed_retrieval_retries_from_the_saved_screening_checkpoint(tmp_path, config):
    class FailingModel(ControlledModel):
        def with_structured_output(self, schema):
            if schema.__name__ == "Extraction":
                raise GatewayError("Controlled transient extraction failure")
            return super().with_structured_output(schema)

    store = DiskStore(tmp_path)
    failed = Supervisor(store, Settings(), model=FailingModel(), sources=CourseSnapshot()).start(config)
    assert failed.status == "failed" and failed.next_stage == "rag"
    saved = store.load(failed.id)
    result = Supervisor(store, Settings(), model=ControlledModel()).retry(saved)
    assert result.status == "complete", result.error
    assert result.screening == failed.screening
    assert [event.status for event in result.events if event.stage == "rag" and event.kind == "agent"] == ["error", "ok"]


def test_convert_paused_ai_review_without_reclassifying_records(tmp_path, config):
    store = DiskStore(tmp_path)
    supervisor = Supervisor(store, Settings(), model=MixedScreeningModel(), sources=ScreeningCases())
    human = config.model_copy(update={"per_source": 5, "execution_mode": "human_in_the_loop"})
    paused = supervisor.start(human)
    assert paused.status == "awaiting_screening" and paused.rag is None
    completed = supervisor.continue_automatically(store.load(paused.id))
    assert completed.status == "complete" and completed.config.execution_mode == "automatic"
    assert completed.screening == paused.screening
    assert any(event.operation == "continue_automatically" for event in completed.events)


def test_human_override_keeps_original_ai_recommendation_and_history(tmp_path, config):
    store = DiskStore(tmp_path)
    supervisor = Supervisor(store, Settings(), model=MixedScreeningModel(), sources=ScreeningCases())
    run = supervisor.start(config.model_copy(update={"per_source": 5, "execution_mode": "human_in_the_loop"}))
    decision = next(item for item in run.screening.decisions if item.final == "exclude")
    first = supervisor.review_screening(run, decision.paper_id, "include", "Relevant population.")
    restored = store.load(first.id)
    supervisor.review_screening(restored, decision.paper_id, "uncertain", "Study design needs verification.")
    saved = store.load(run.id)
    item = next(item for item in saved.screening.decisions if item.paper_id == decision.paper_id)
    assert item.llm == "exclude" and item.final == "uncertain" and item.decided_by == "human"
    assert [(v.previous_origin, v.previous_verdict, v.verdict, v.reason) for v in item.review_history] == [
        ("ai", "exclude", "include", "Relevant population."),
        ("human", "include", "uncertain", "Study design needs verification."),
    ]
    finished = supervisor.finish_screening(saved)
    assert finished.status == "complete", finished.error
    assert all(p.paper_id != item.paper_id for p in finished.rag.evidence)


def test_human_can_override_a_batch_with_no_unresolved_papers(tmp_path, config):
    supervisor = Supervisor(DiskStore(tmp_path), Settings(), model=ControlledModel(), sources=CourseSnapshot())
    run = supervisor.start(config.model_copy(update={"execution_mode": "human_in_the_loop"}))
    assert run.status == "awaiting_screening" and run.screening.counts()["unresolved"] == 0
    assert run.screening.decisions[0].decided_by == "ai"
    supervisor.review_screening(run, run.screening.decisions[0].paper_id, "exclude", "Outside the review scope.")
    assert supervisor.finish_screening(run).status == "insufficient_evidence"
    assert run.rag is None


def test_legacy_saved_runs_keep_human_review(config):
    old = ReviewRun(config=config).model_dump()
    old["config"].pop("execution_mode")
    assert ReviewRun.model_validate_json(json.dumps(old)).config.execution_mode == "human_in_the_loop"
