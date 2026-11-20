"""Validation du protocole fourni et des conditions d'arrêt du TD06."""

from pathlib import Path

import pytest

from main import load_chunks
from slrresearch.agentic_rag import (
    compare_baseline_and_agentic,
    finalize_agentic_evidence,
    run_adaptive_retrieval,
)
from slrresearch.agentic_rag_artifacts import load_agentic_cases
from slrresearch.agentic_rag_models import EvidenceFacet, RetrievalAction
from slrresearch.agentic_rag_runtime import (
    ProtocolEmbeddings,
    build_retrieval_tools,
    controlled_extractor,
)


ROOT = Path(__file__).resolve().parents[1]
CASES = {case.id: case for case in load_agentic_cases(ROOT / "artifacts/agentic_rag_cases.json")}


def run_protocol(case_id, budget=2):
    case = CASES[case_id]
    chunks = load_chunks(ROOT)
    tools = build_retrieval_tools(ProtocolEmbeddings(chunks, set(case.relevant_chunk_ids)))
    baseline = tools[case.baseline_tool](chunks, case.question, case.baseline_k)
    state = run_adaptive_retrieval(
        case.question, case.facets, chunks, tools,
        k=case.baseline_k, max_iterations=budget,
    )
    return case, baseline, state


@pytest.mark.parametrize("case_id", ["Q1", "Q2", "Q3"])
def test_protocol_retrouve_la_preuve_et_conserve_les_observations(case_id):
    case, baseline, state = run_protocol(case_id)
    report = compare_baseline_and_agentic(case, baseline, state)
    evidence = finalize_agentic_evidence(state, controlled_extractor(state))

    assert state.status == "completed"
    assert state.missing_facets == []
    assert state.covered_facets == [facet.id for facet in case.facets]
    assert len({item["chunk_id"] for item in state.selected_chunks}) == len(state.selected_chunks)
    assert evidence.status == "verified"
    assert evidence.chunk_id in case.relevant_chunk_ids
    assert report.agentic["recall_at_k"] == 1.0
    assert state.trace[-1].covered_facets == state.covered_facets

    if case_id == "Q3":
        assert [event.tool for event in state.trace] == ["lexical"]
        assert report.extra_retrieval_calls == 0
        assert report.delta_recall == 0.0
    else:
        assert [event.tool for event in state.trace] == ["lexical", "semantic"]
        assert state.retrieval_calls == 2
        assert state.trace[0].missing_facets == [facet.id for facet in case.facets]
        assert state.trace[0].covered_facets == []
        assert state.trace[1].query == " ".join(facet.query_hint for facet in case.facets)
        assert report.delta_recall == 1.0
        assert report.extra_retrieval_calls == 1


@pytest.mark.parametrize("case_id", ["Q1", "Q2"])
def test_budget_un_cycle_interdit_la_generation_si_preuve_manquante(case_id):
    case, _, state = run_protocol(case_id, budget=1)

    def forbidden_extractor(question, context):
        pytest.fail("Une recherche incomplète ne doit pas lancer la génération")

    assert state.status == "budget_exhausted"
    assert state.iteration == state.retrieval_calls == len(state.trace) == 1
    assert state.missing_facets == [facet.id for facet in case.facets]
    assert finalize_agentic_evidence(state, forbidden_extractor) is None


def test_q3_peut_terminer_a_la_derniere_iteration_autorisee():
    _, _, state = run_protocol("Q3", budget=1)
    assert state.status == "completed"
    assert state.retrieval_calls == 1
    assert finalize_agentic_evidence(state, controlled_extractor(state)).status == "verified"


def test_budget_impose_meme_si_le_decideur_demande_toujours_un_retrieval():
    calls = []

    def empty_tool(chunks, query, k):
        calls.append(query)
        return []

    def persistent_decider(state):
        return RetrievalAction(action="retrieve", tool="lexical", query="q", reason="continuer")

    state = run_adaptive_retrieval(
        "q", [EvidenceFacet(id="f", label="preuve", keywords=["evidence"], query_hint="evidence")],
        [], {"lexical": empty_tool}, decider=persistent_decider, max_iterations=2,
    )
    assert state.status == "budget_exhausted"
    assert len(calls) == state.retrieval_calls == len(state.trace) == 2
    assert all(event.found == 0 and event.missing_facets == ["f"] for event in state.trace)


def test_abstention_volontaire_n_execute_aucun_outil():
    state = run_adaptive_retrieval(
        "q", [], [], {},
        decider=lambda state: RetrievalAction(action="abstain", reason="Preuves indisponibles."),
    )
    assert state.status == "abstained"
    assert state.iteration == state.retrieval_calls == len(state.trace) == 0
