"""Cas limites des protocoles de planification et d'exécution du TD07."""

from pathlib import Path

import pytest

from slrresearch import plan_and_execute as runtime
from slrresearch.planning_models import PlanCandidate, PlanningAnalysis, StepResult
from slrresearch.td07_runtime import (
    controlled_planner,
    controlled_replanner,
    load_td06_handoff,
)


ROOT = Path(__file__).parents[1]
EVIDENCE, REQUIRED_RQS = load_td06_handoff(ROOT / "artifacts" / "td06_evidence.json")
ALLOWED = {item.id for item in EVIDENCE}
OBJECTIVE = "Produire une note pédagogique couvrant RQ1, RQ2 et RQ3."


def direct_plan():
    return controlled_planner("direct", OBJECTIVE, EVIDENCE)


class ScriptedModel:
    """Réponses dictionnaires pour tester l'adaptateur sans service externe."""

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def with_structured_output(self, schema):
        owner = self

        class Structured:
            def invoke(self, prompt):
                owner.calls.append((schema, prompt))
                return next(owner.responses)

        return Structured()


@pytest.mark.parametrize("strategy", ["direct", "cot", "tot"])
def test_llm_dicts_et_normalisation_du_plan(strategy):
    analysis = {
        "proposed_order": ["RQ3", "RQ1", "RQ2"],
        "rationale": ["Justification observable de test"],
        "risks": ["Risque observable de test"],
    }
    raw_plan = direct_plan().model_dump()
    responses = {
        "direct": [raw_plan],
        "cot": [analysis, raw_plan],
        "tot": [raw_plan, raw_plan, raw_plan],
    }
    model = ScriptedModel(responses[strategy])
    plan = runtime.build_llm_planner(model)(strategy, OBJECTIVE, EVIDENCE)

    assert plan.llm_calls == len(model.calls) == len(responses[strategy])
    assert [step.rq_id for step in plan.steps] == runtime.STRATEGY_RQ_ORDER[strategy]
    runtime.validate_plan(plan, ALLOWED, REQUIRED_RQS)
    if strategy == "cot":
        assert [schema for schema, _ in model.calls] == [PlanningAnalysis, PlanCandidate]
        assert analysis["rationale"][0] in model.calls[1][1]
        assert analysis["risks"][0] in model.calls[1][1]


def test_tot_ignore_candidats_mal_formes_et_non_autorises():
    unauthorized = direct_plan().model_dump()
    unauthorized["steps"][0]["evidence_ids"] = ["E999"]
    valid = direct_plan().model_dump()
    model = ScriptedModel([{"steps": []}, unauthorized, valid])

    plan = runtime.build_llm_planner(model)("tot", OBJECTIVE, EVIDENCE)

    assert len(model.calls) == plan.llm_calls == 3
    runtime.validate_plan(plan, ALLOWED, REQUIRED_RQS)
    assert len({prompt for _, prompt in model.calls}) == 3


def test_tot_selectionne_le_candidat_valide_le_plus_complet():
    incomplete = direct_plan().model_dump()
    incomplete["steps"][0]["objective"] = ""
    complete = direct_plan().model_dump()
    complete["objective"] = "Candidat complet retenu"
    model = ScriptedModel([incomplete, complete, incomplete])

    plan = runtime.build_llm_planner(model)("tot", OBJECTIVE, EVIDENCE)

    assert plan.objective == complete["objective"]
    assert runtime.evaluate_plan(plan, ALLOWED, REQUIRED_RQS).section_coverage == 1


def test_tot_echoue_explicitement_si_aucun_candidat_est_valide():
    model = ScriptedModel([{}, {}, {}])
    with pytest.raises(ValueError, match="Aucun candidat ToT valide"):
        runtime.build_llm_planner(model)("tot", OBJECTIVE, EVIDENCE)
    assert len(model.calls) == 3


def test_strategie_inconnue_refusee_avant_appel_llm():
    model = ScriptedModel([])
    with pytest.raises(ValueError, match="Stratégie inconnue"):
        runtime.build_llm_planner(model)("unknown", OBJECTIVE, EVIDENCE)
    assert not model.calls


@pytest.mark.parametrize("case", ["duplicate_id", "missing_rq", "forward_dependency"])
def test_validation_refuse_les_autres_graphes_invalides(case):
    plan = direct_plan()
    if case == "duplicate_id":
        plan.steps[1].id = plan.steps[0].id
    elif case == "missing_rq":
        plan.steps.pop()
    else:
        plan.steps[0].depends_on = [plan.steps[-1].id]
    with pytest.raises(ValueError):
        runtime.validate_plan(plan, ALLOWED, REQUIRED_RQS)


def test_execution_refuse_preuve_non_autorisee():
    step = direct_plan().steps[0]
    step.evidence_ids = ["E999"]
    with pytest.raises(ValueError, match="Preuve non autorisée"):
        runtime.execute_step(step, {item.id: item for item in EVIDENCE}, set())


def test_limitation_garde_la_facette_manquante_observable():
    step = direct_plan().steps[-1].model_copy(update={"mode": "limitation"})
    result = runtime.execute_step(step, {item.id: item for item in EVIDENCE}, {"S1", "S2"})
    assert result.status == "success"
    assert result.missing_facets == ["prospective_validation"]
    assert "Limite scientifique" in result.content
    assert "prospective_validation" not in result.covered_facets


@pytest.mark.parametrize("variant", ["classic", "replanning"])
def test_citation_invalide_interdit_acceptation_dune_section(monkeypatch, variant):
    def invalid_citation(step, evidence, completed):
        return StepResult(
            step_id=step.id, status="success", content="Contenu non accepté",
            citations=["PAPER_UNKNOWN"], covered_facets=step.required_facets,
            missing_facets=[],
        )

    monkeypatch.setattr(runtime, "execute_step", invalid_citation)
    if variant == "classic":
        result = runtime.run_classic(direct_plan(), EVIDENCE, REQUIRED_RQS, max_retries=0)
    else:
        result = runtime.run_with_replanning(
            direct_plan(), EVIDENCE, REQUIRED_RQS, controlled_replanner, max_revisions=0,
        )
    assert result.status == "abstained"
    assert not result.sections


@pytest.mark.parametrize("max_actions", [0, 2])
@pytest.mark.parametrize("variant", ["classic", "replanning"])
def test_budget_borne_les_actions(variant, max_actions):
    if variant == "classic":
        result = runtime.run_classic(direct_plan(), EVIDENCE, REQUIRED_RQS, max_actions=max_actions)
    else:
        result = runtime.run_with_replanning(
            direct_plan(), EVIDENCE, REQUIRED_RQS, controlled_replanner, max_actions=max_actions,
        )
    assert result.status == "budget_exhausted"
    assert result.tool_calls == max_actions
    assert len(result.sections) == max_actions


@pytest.mark.parametrize("limits", [{"max_actions": 3}, {"max_revisions": 0}])
def test_replanner_non_appele_sans_budget_ou_revision(limits):
    def forbidden_replanner(*args):
        pytest.fail("Le replanner ne doit pas être appelé après épuisement de la limite")

    result = runtime.run_with_replanning(
        direct_plan(), EVIDENCE, REQUIRED_RQS, forbidden_replanner, **limits,
    )
    assert result.status == "abstained"
    assert result.revisions == 0
    assert result.tool_calls == 3


def test_revisions_bornees_meme_si_replanner_ne_corrige_rien():
    result = runtime.run_with_replanning(
        direct_plan(), EVIDENCE, REQUIRED_RQS,
        lambda plan, step, facets: plan, max_revisions=2,
    )
    assert result.status == "abstained"
    assert result.revisions == 2
    assert result.tool_calls == 5


@pytest.mark.parametrize("case", ["deleted_completed_step", "unauthorized_evidence"])
def test_replanning_refuse_revision_inadmissible(case):
    def invalid_replanner(plan, failed_step, available_facets):
        revised = controlled_replanner(plan, failed_step, available_facets)
        if case == "deleted_completed_step":
            revised.steps = revised.steps[1:]
        else:
            revised.steps[-1].evidence_ids = ["E999"]
        return revised

    expected = "supprimé une étape déjà terminée" if case == "deleted_completed_step" else "Preuve"
    with pytest.raises(ValueError, match=expected):
        runtime.run_with_replanning(direct_plan(), EVIDENCE, REQUIRED_RQS, invalid_replanner)


def test_replanning_conserve_entree_et_sections_terminees():
    plan = direct_plan()
    before = plan.model_dump()
    classic = runtime.run_classic(plan, EVIDENCE, REQUIRED_RQS)
    adaptive = runtime.run_with_replanning(plan, EVIDENCE, REQUIRED_RQS, controlled_replanner)
    assert plan.model_dump() == before
    assert adaptive.sections[:2] == classic.sections
    assert len(adaptive.sections) == 3
    assert adaptive.plan.steps[-1].mode == "limitation"
