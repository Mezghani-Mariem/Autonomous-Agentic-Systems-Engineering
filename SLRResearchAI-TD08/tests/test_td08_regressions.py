"""Cas limites des contrats TD08 et des deux chemins de réparation."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from slrresearch.orchestrator import FULL_TRANSITIONS, full_pipeline_run, full_supervisor_run, validate_handoff
from slrresearch.quality_agent import build_llm_judge, evaluate_rules, parse_claims, run_quality_loop
from slrresearch.quality_models import Claim, Handoff, QualityJudgeDecision
from slrresearch.td08_runtime import build_artifact_workers, build_state, load_td08_artifacts

ROOT = Path(__file__).parents[1]
EVIDENCE, REQUIRED_RQS, DRAFT, REPAIRED = load_td08_artifacts(ROOT)
OBJECTIVE = "Contrôler la fidélité de la note avant livraison."


def evaluate(report):
    return evaluate_rules(report, EVIDENCE, REQUIRED_RQS)


def test_claim_contract_rejects_invalid_output_and_handles_absent_claims():
    assert parse_claims({}) == []
    assert all(isinstance(claim, Claim) for claim in parse_claims(DRAFT))
    bad = {"claims": [{**DRAFT["claims"][0], "text": "x"}]}
    with pytest.raises(ValidationError):
        parse_claims(bad)


def test_coverage_ignores_duplicates_and_unrequired_sections():
    report = {**REPAIRED, "sections": [{"rq_id": "RQ1"}, {"rq_id": "RQ1"}, {"rq_id": "OTHER"}]}
    quality = evaluate(report)
    assert quality.rq_coverage == pytest.approx(1 / 3)
    assert quality.verdict == "REVISE" and quality.repair_target == "writing"
    assert evaluate_rules(REPAIRED, EVIDENCE, set()).rq_coverage == 0


def test_empty_report_never_passes():
    quality = evaluate({})
    assert quality.score == 0 and quality.verdict == "REVISE"
    assert any("aucune affirmation" in item for item in quality.feedback)


@pytest.mark.parametrize("citations", [[], ["UNKNOWN"], ["E1", "UNKNOWN"]])
def test_missing_citations_stay_unsupported(citations):
    claim = {**DRAFT["claims"][0], "evidence_ids": citations}
    quality = evaluate({**DRAFT, "claims": [claim]})
    assert quality.findings[0].status == "unsupported"
    assert quality.citation_validity == 0
    assert quality.repair_target == "rag"


def test_a5_is_rejected_even_when_global_score_exceeds_threshold():
    quality = evaluate(DRAFT)
    assert quality.score == pytest.approx(14 / 15)
    assert quality.citation_validity == 1 and quality.faithfulness == 0.8
    assert [item.claim_id for item in quality.findings if item.status == "unsupported"] == ["A5"]
    assert quality.verdict == "REVISE" and quality.repair_target == "rag"
    corrected = evaluate(REPAIRED)
    assert corrected.score == 1 and corrected.verdict == "ACCEPT"


@pytest.mark.parametrize("as_model", [False, True])
def test_structured_judge_invoked_once_and_cannot_overrule_unknown_evidence(as_model):
    decision = QualityJudgeDecision(verdict="ACCEPT", score=1, feedback=["Avis du juge."])
    model = Mock()
    structured = model.with_structured_output.return_value
    structured.invoke.return_value = decision if as_model else decision.model_dump()
    bad = {**DRAFT, "claims": [{**DRAFT["claims"][0], "evidence_ids": ["UNKNOWN"]}]}
    rules = evaluate(bad)
    result = build_llm_judge(model)(bad, rules)
    model.with_structured_output.assert_called_once_with(QualityJudgeDecision)
    structured.invoke.assert_called_once()
    prompt = structured.invoke.call_args.args[0]
    assert "UNKNOWN" in prompt and "QualityJudgeDecision" in prompt
    assert "rq_coverage" in prompt and "findings" in prompt
    assert result.verdict == "REVISE" and result.score == rules.score
    assert result.llm_calls == 1 and result.repair_target == "rag"
    assert result.feedback == [*rules.feedback, "Avis du juge."]


@pytest.mark.parametrize("verdict", ["REVISE", "ESCALATE"])
def test_judge_can_request_stricter_verdict_and_lower_score(verdict):
    model = Mock()
    model.with_structured_output.return_value.invoke.return_value = {
        "verdict": verdict, "score": 0.5, "feedback": ["Relecture nécessaire."],
    }
    result = build_llm_judge(model)(REPAIRED, evaluate(REPAIRED))
    assert result.verdict == verdict and result.score == 0.5


def test_invalid_judge_output_is_rejected():
    model = Mock()
    model.with_structured_output.return_value.invoke.return_value = {
        "verdict": "ACCEPT", "score": 2, "feedback": [],
    }
    with pytest.raises(ValidationError):
        build_llm_judge(model)(REPAIRED, evaluate(REPAIRED))


@pytest.mark.parametrize("draft,budget,verdict", [(REPAIRED, 0, "ACCEPT"), (DRAFT, 0, "ESCALATE")])
def test_quality_loop_stops_without_calling_writer(draft, budget, verdict):
    writer = Mock(side_effect=AssertionError("Le Writer ne doit pas être appelé."))
    result = run_quality_loop(draft, EVIDENCE, REQUIRED_RQS, writer, max_revisions=budget)
    assert result["quality"].verdict == verdict and len(result["history"]) == 1
    writer.assert_not_called()


def test_quality_loop_passes_feedback_and_limits_failed_revisions():
    writer = Mock(side_effect=lambda report, feedback: report)
    result = run_quality_loop(DRAFT, EVIDENCE, REQUIRED_RQS, writer, max_revisions=2)
    assert writer.call_count == 2 and result["quality"].verdict == "ESCALATE"
    assert [quality.revision for quality in result["history"]] == [0, 1, 2]
    assert all("A5" in feedback[0] for _, feedback in [call.args for call in writer.call_args_list])


def test_judge_escalation_stops_reflection_immediately():
    writer = Mock()
    judge = lambda report, rules: rules.model_copy(update={"verdict": "ESCALATE"})
    result = run_quality_loop(DRAFT, EVIDENCE, REQUIRED_RQS, writer, max_revisions=3, judge=judge)
    assert result["quality"].verdict == "ESCALATE" and len(result["history"]) == 1
    writer.assert_not_called()


@pytest.mark.parametrize("update,error", [
    ({"target": "unknown"}, PermissionError),
    ({"source": "unknown"}, PermissionError),
    ({"evidence_ids": ["UNKNOWN"]}, ValueError),
    ({"budget_left": -1}, ValueError),
])
def test_handoff_rejects_each_contract_violation(update, error):
    handoff = Handoff(source="writing", target="quality", objective=OBJECTIVE,
                      artifact={}, evidence_ids=["E1"], status="ok", budget_left=2)
    # model_copy permet de vérifier aussi la garde du runtime après mutation.
    with pytest.raises(error):
        validate_handoff(handoff.model_copy(update=update), FULL_TRANSITIONS, {"E1"})


def test_pipeline_records_current_artifacts_and_preserves_input_state():
    state = build_state(DRAFT, EVIDENCE, OBJECTIVE, budget=8)
    before = state.model_dump()
    result = full_pipeline_run(state, build_artifact_workers(ROOT, EVIDENCE, DRAFT, REPAIRED), evaluate)
    assert state.model_dump() == before
    assert result.state.history == ["search", "screening", "rag", "writing", "quality"]
    assert [handoff.budget_left for handoff in result.handoffs] == [8, 7, 6, 5]
    for handoff in result.handoffs:
        assert handoff.artifact == result.state.artifacts[handoff.source]
    assert result.status == "ESCALATE"


@pytest.mark.parametrize("target", ["rag", "writing"])
def test_supervisor_routes_feedback_then_writing_then_quality(target):
    draft = deepcopy(DRAFT)
    if target == "writing":
        draft = {**REPAIRED, "sections": REPAIRED["sections"][:2]}
    workers = build_artifact_workers(ROOT, EVIDENCE, draft, REPAIRED)
    observed = []
    original = workers[target]

    def repair_worker(state):
        if state.quality is not None:
            observed.append((state.budget_left, state.quality.feedback))
        return original(state)

    workers[target] = repair_worker
    result = full_supervisor_run(build_state(draft, EVIDENCE, OBJECTIVE, budget=8), workers, evaluate, max_handoffs=8)
    expected_tail = ["rag", "writing", "quality"] if target == "rag" else ["writing", "quality"]
    assert result.state.history[5:] == expected_tail
    assert result.status == "FINISH" and result.state.quality.verdict == "ACCEPT"
    handoff = result.handoffs[4]
    assert (handoff.source, handoff.target, handoff.status) == ("quality", target, "partial")
    assert handoff.artifact == {"feedback": evaluate(draft).feedback, "repair_target": target}
    assert observed == [(3, evaluate(draft).feedback)]
    assert result.transitions[-1] == "quality→finish"


@pytest.mark.parametrize("runner", [full_pipeline_run, full_supervisor_run])
def test_no_worker_is_called_without_budget(runner):
    workers = {"search": Mock(side_effect=AssertionError("Budget épuisé."))}
    result = runner(build_state(DRAFT, EVIDENCE, OBJECTIVE, budget=0), workers, evaluate)
    assert result.status == "BUDGET_EXHAUSTED" and result.state.history == []
    workers["search"].assert_not_called()


@pytest.mark.parametrize("budget,limit", [(5, 8), (8, 5), (8, 7)])
def test_supervisor_reports_exhaustion_when_repair_cannot_finish(budget, limit):
    result = full_supervisor_run(
        build_state(DRAFT, EVIDENCE, OBJECTIVE, budget=budget),
        build_artifact_workers(ROOT, EVIDENCE, DRAFT, REPAIRED), evaluate,
        max_handoffs=limit,
    )
    assert result.status == "BUDGET_EXHAUSTED"
    assert result.state.budget_left >= 0 and result.actions <= limit
    assert result.state.quality.verdict == "REVISE"


@pytest.mark.parametrize("target,verdict", [("human", "REVISE"), ("rag", "ESCALATE")])
def test_supervisor_human_or_escalation_does_not_relaunch_workers(target, verdict):
    evaluator = lambda report: evaluate(report).model_copy(update={"repair_target": target, "verdict": verdict})
    result = full_supervisor_run(
        build_state(DRAFT, EVIDENCE, OBJECTIVE, budget=8),
        build_artifact_workers(ROOT, EVIDENCE, DRAFT, REPAIRED), evaluator, max_handoffs=8,
    )
    assert result.status == "ESCALATE" and len(result.state.history) == 5


def test_demo_exports_actual_transitions_and_repaired_claim():
    from main import run_demo

    result = run_demo(ROOT)
    assert result["actual_llm_calls"] == 0
    assert result["pipeline"]["status"] == "ESCALATE"
    assert result["supervisor"]["status"] == "FINISH"
    assert result["supervisor"]["state"]["report"]["claims"][-1]["id"] == "A5R"
