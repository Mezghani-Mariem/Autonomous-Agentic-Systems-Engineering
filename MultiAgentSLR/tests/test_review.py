from io import BytesIO

import pytest
from pypdf import PdfReader

from evaluation.metrics import review_metrics
from slr.report import markdown, pdf
from slr.settings import Settings
from slr.storage import DiskStore
from slr.supervisor import Supervisor, pending_claims

from conftest import ControlledModel, CourseSnapshot, Structured


def workflow(tmp_path, model=None, source=None):
    return Supervisor(DiskStore(tmp_path), Settings(), model=model or ControlledModel(),
                      sources=source or CourseSnapshot())


def test_topic_to_markdown_and_pdf(tmp_path, config):
    supervisor = workflow(tmp_path)
    run = supervisor.start(config)
    assert run.status == "complete", run.error
    assert [h.source for h in run.handoffs] == ["planning", "search", "screening", "rag", "writing", "quality"]
    assert run.rag.evidence and run.screening.decisions[0].final == "include"
    study = run.search.papers[0]
    assert {item.paper_id for item in run.rag.evidence} == {study.id}
    assert all(item.kind == "abstract" and item.page is None for item in run.rag.evidence)
    assert {ref for c in run.draft.claims for ref in c.evidence_ids} <= {e.id for e in run.rag.evidence}
    restored = DiskStore(tmp_path).load(run.id)
    report = markdown(restored)
    assert "Evidence scope: abstract-first" in report and study.doi in report and "## References" in report
    parsed = PdfReader(BytesIO(pdf(restored)))
    text = "\n".join(page.extract_text() for page in parsed.pages)
    assert "Evidence and provenance" in text and "Full text was unavailable" in text
    assert review_metrics(run)["overall"]["task_completed"]


def test_invalid_output_repairs_once_and_plan_is_valid(tmp_path, config):
    model = ControlledModel(first_invalid=True)
    run = workflow(tmp_path, model).start(config)
    assert run.status == "complete", run.error
    assert run.plan.repair_attempts == 1 and model.raw_calls == 2


def test_malformed_questions_after_repair_fail_before_search(tmp_path, config):
    from langchain_core.messages import AIMessage
    model = ControlledModel()
    model.invoke = lambda prompt: AIMessage(content="unreadable")
    run = workflow(tmp_path, model).start(config)
    assert run.status == "failed" and run.next_stage == "planning" and not run.handoffs
    supervisor = workflow(tmp_path)
    supervisor.retry(supervisor.store.load(run.id))
    assert supervisor.store.load(run.id).status == "complete"


def test_missing_abstract_pauses_then_resumes(tmp_path, config):
    config = config.model_copy(update={"execution_mode": "human_in_the_loop"})
    run = workflow(tmp_path, source=CourseSnapshot(missing_abstract=True)).start(config)
    assert run.status == "awaiting_screening", run.error
    second = workflow(tmp_path)
    restored = second.store.load(run.id)
    second.review_screening(restored, restored.screening.decisions[0].paper_id,
                            "exclude", "No.")
    second.finish_screening(restored)
    assert restored.status == "insufficient_evidence", restored.error
    assert restored.rag is None and restored.draft is None
    saved = second.store.load(run.id).screening.decisions[0]
    assert (saved.decided_by, saved.final, saved.reason) == ("human", "exclude", "No.")
    assert "Abstract unavailable" in saved.screening_reason
    assert review_metrics(restored)["overall"]["human_interventions"] == 2


def test_invalid_citation_routes_to_revision(tmp_path, config):
    run = workflow(tmp_path, ControlledModel(invalid_citation=True)).start(config)
    assert run.status == "complete", run.error
    assert run.revision == 1 and run.quality[0].invalid_claims == ["C1"]
    assert any(h.source == "quality" and h.target == "writing" for h in run.handoffs)
    assert review_metrics(run)["overall"]["revision_success"]


def test_revision_keeps_and_rechecks_supported_claims_when_writer_returns_no_correction(tmp_path, config):
    class NoCorrection(Structured):
        def ClaimProposal(self, prompt):
            return super().ClaimProposal(prompt) if self.model.writer_calls == 0 else {"claims": []}

    class RevisionModel(ControlledModel):
        def with_structured_output(self, schema):
            return NoCorrection(self, schema)

    run = workflow(tmp_path, RevisionModel(invalid_citation=True)).start(config)
    assert run.status == "complete", run.error or run.outcome_reason
    assert run.revision == 1 and run.quality[0].invalid_claims == ["C1"]
    previously_supported = {item.claim_id for item in run.quality[0].findings if item.judgment == "supported"}
    assert {c.id for c in run.retained_claims()} == previously_supported == {"C2", "C3"}
    assert all(item.judgment == "supported" for item in run.quality[-1].findings)


def test_unsupported_and_budget_exhaustion_pause_for_claim_review(tmp_path, config):
    config = config.model_copy(update={"execution_mode": "human_in_the_loop"})
    supervisor = workflow(tmp_path, ControlledModel(reject_claim=True))
    run = supervisor.start(config)
    assert run.status == "awaiting_screening", run.error
    supervisor.finish_screening(run)
    assert run.status == "awaiting_claims", run.error
    assert run.revision == config.revision_budget
    assert len(run.quality) == config.revision_budget + 1
    assert any(h.source == "quality" and h.target == "rag" for h in run.handoffs)
    with pytest.raises(ValueError):
        markdown(run)
    for claim_id in sorted(pending_claims(run)):
        supervisor.review_claim(run, claim_id, "remove", "The evidence does not support this statement.")
    assert run.status == "insufficient_evidence"
    with pytest.raises(ValueError, match="No supported, cited claims"):
        markdown(run)


def test_human_cannot_bypass_unknown_citation(tmp_path, config):
    supervisor = workflow(tmp_path, ControlledModel(invalid_citation=True))
    run = supervisor.start(config.model_copy(update={"revision_budget": 0, "execution_mode": "human_in_the_loop"}))
    assert run.status == "awaiting_screening"
    supervisor.finish_screening(run)
    assert run.status == "awaiting_claims"
    with pytest.raises(ValueError, match="Remove claims"):
        supervisor.review_claim(run, "C1", "accept", "Unknown references are invalid.")
    supervisor.review_claim(run, "C1", "remove", "Citation could not be resolved.")
    assert run.status == "complete"


def test_supplied_pdf_retains_page_provenance(tmp_path, config):
    from reportlab.pdfgen import canvas
    supervisor = workflow(tmp_path)
    run = supervisor.start(config.model_copy(update={
        "execution_mode": "human_in_the_loop", "pause_for_documents": True,
    }))
    assert run.status == "awaiting_screening"
    supervisor.finish_screening(run)
    assert run.status == "awaiting_documents"
    data = BytesIO()
    doc = canvas.Canvas(data)
    doc.drawString(55, 700, "Screening overview")
    doc.showPage()
    doc.drawString(55, 700, "Screening studies were examined in the supplied full text.")
    doc.save()
    supervisor.attach_document(run, run.search.papers[0].id, data.getvalue())
    supervisor.finish_documents(run)
    assert run.status == "complete", run.error
    assert run.rag.evidence and all(item.kind == "full_text" and item.page > 0 for item in run.rag.evidence)
    assert "supplied full text, page" in markdown(run)
