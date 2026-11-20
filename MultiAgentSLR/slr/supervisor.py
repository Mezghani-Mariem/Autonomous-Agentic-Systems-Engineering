from contextlib import contextmanager
from io import BytesIO
from time import perf_counter

import httpx
from pydantic import ValidationError

from .course.orchestrator import validate_handoff
from .course.pdf_loader import extract_pdf_pages
from .course.quality_models import Handoff
from .gateway import Calls, GatewayError, MeasuredEmbeddings, Telemetry, build_model
from .models import ClaimReview, Event, ReviewRun, ScreeningOverride, STAGES
from .planning import prepare_review
from .retrieval import gather_evidence
from .screen import screen_papers
from .sources import ScientificSources, search_review
from .synthesis import evaluate_claims, quality_route, write_review

TRANSITIONS = {
    **{source: {target} for source, target in zip(STAGES, STAGES[1:])},
    "screening": {"rag", "insufficient_evidence"},
    "rag": {"writing", "insufficient_evidence"},
    "quality": {"rag", "writing", "finish", "human", "insufficient_evidence"},
}


class Supervisor:
    def __init__(self, store, settings, *, model=None, sources=None, embeddings=None, record_prompts=False):
        self.store, self.settings = store, settings
        self.model, self.sources, self.embeddings = model, sources, embeddings
        self.record_prompts = record_prompts
        self.prompts = []
        self.on_stage = None

    def start(self, config):
        run = ReviewRun(config=config.model_copy(update={"screen": "llm"}))
        self.store.save(run)
        return self.advance(run)

    def retry(self, run):
        if run.status != "failed" or run.next_stage not in STAGES:
            raise ValueError("This review has no failed stage to retry")
        run.status, run.error = "running", ""
        self.store.save(run)
        return self.advance(run)

    def retry_retrieval(self, run):
        if not run.can_retry_retrieval():
            raise ValueError("This review has no insufficient-evidence retrieval stage to retry")
        run.status, run.next_stage, run.outcome_reason = "running", "rag", ""
        run.events.append(Event(stage="rag", kind="human", operation="retry_retrieval", status="ok", seconds=0))
        self.store.save(run)
        return self.advance(run)

    def handoff(self, run, source, target, payload):
        evidence = {passage.id for passage in run.rag.evidence} if run.rag else set()
        if target == "insufficient_evidence":
            status = "blocked"
        elif source == "quality" and target in {"rag", "writing", "human"}:
            status = "partial"
        else:
            status = "ok"
        handoff = Handoff(source=source, target=target, objective=run.config.topic, artifact=payload,
                          evidence_ids=sorted(evidence), budget_left=run.config.revision_budget - run.revision,
                          status=status)
        validate_handoff(handoff, TRANSITIONS, evidence)
        run.handoffs.append(handoff)
        run.next_stage = target

    @contextmanager
    def services(self, run):
        telemetry = Telemetry(run.events, record_prompts=self.record_prompts)
        calls = Calls(self.store, telemetry, self.settings.cache_ttl)
        with httpx.Client(timeout=self.settings.timeout) as client:
            def model():
                return self.model or build_model(self.settings, run.config.provider, calls)
            sources = self.sources or ScientificSources(self.settings, calls, client)
            embeddings = self.embeddings
            if embeddings is None and self.settings.embedding_model:
                embeddings = MeasuredEmbeddings(self.settings, calls)
            try:
                yield telemetry, model, sources, embeddings
            finally:
                self.prompts.extend(telemetry.prompts or [])

    def advance(self, run):
        if run.status != "running":
            return run
        with self.services(run) as (telemetry, model, sources, embeddings):
            instance = None
            def get_model():
                nonlocal instance
                if instance is None:
                    instance = model()
                return instance

            while run.status == "running":
                stage = run.next_stage
                telemetry.stage = stage
                if self.on_stage is not None:
                    self.on_stage(stage)
                started = perf_counter()
                try:
                    self.run_stage(run, stage, get_model, sources, embeddings)
                except (GatewayError, ValidationError, ValueError, PermissionError) as exc:
                    run.status = "failed"
                    detail = str(exc) if isinstance(exc, GatewayError) else type(exc).__name__
                    run.error = f"{stage}: {detail}"
                    telemetry.event("agent", stage, "error", started, detail=detail)
                else:
                    telemetry.event("agent", stage, "ok", started)
                self.store.save(run)
        return run

    def run_stage(self, run, stage, model, sources, embeddings):
        config = run.config
        if stage == "planning":
            run.plan = prepare_review(config, model())
            self.handoff(run, stage, "search", run.plan.model_dump(mode="json"))
        elif stage == "search":
            run.search = search_review(config.topic, run.plan.protocol.queries, config.per_source,
                                       config.search, sources)
            if all(obs.status not in {"success", "empty"} for obs in run.search.state.observations):
                raise GatewayError("All bibliographic sources failed. See the search trace and API settings.")
            self.handoff(run, stage, "screening", {
                "origin": run.search.origin, "paper_ids": [paper.id for paper in run.search.papers],
                "queries": run.search.state.queries, "discovered": run.search.discovered,
            })
        elif stage == "screening":
            run.config = config.model_copy(update={"screen": "llm"})
            run.screening = screen_papers(run.search.papers, run.config,
                                          model() if any(p.abstract.strip() for p in run.search.papers) else None)
            if config.execution_mode == "human_in_the_loop" and run.screening.decisions:
                run.status = "awaiting_screening"
            else:
                self.handoff_screening(run)
        elif stage == "rag":
            run.rag = gather_evidence(run, model(), embeddings)
            included = {d.paper_id for d in run.screening.decisions if d.final == "include"}
            if any(item.paper_id not in included for item in run.rag.evidence):
                raise ValueError("RAG can only hand off evidence from included studies")
            payload = run.rag.model_dump(mode="json")
            if run.rag.evidence:
                self.handoff(run, stage, "writing", payload)
            else:
                if run.rag.corpus.abstract_chunks + run.rag.corpus.full_text_chunks == 0:
                    reason = "The included studies had no usable abstract or supplied full text."
                else:
                    details = " ".join(f"{item.rq_id}: {item.extraction.reason}" for item in run.rag.retrieval)
                    reason = f"Retrieval found no verified passages in the included studies. {details}"
                self.insufficient(run, stage, reason, payload)
        elif stage == "writing":
            run.draft = write_review(run, model())
            self.handoff(run, stage, "quality", run.draft.model_dump(mode="json"))
        elif stage == "quality":
            result = evaluate_claims(run, model())
            run.quality.append(result)
            run.feedback = result.feedback
            target = quality_route(config.orchestration, run.revision, config.revision_budget, result)
            if target == "complete":
                self.complete(run)
            elif target == "human":
                if config.execution_mode == "automatic":
                    run.withheld_claim_ids = sorted(pending_claims(run))
                    self.complete(run)
                else:
                    self.handoff(run, stage, target, result.model_dump(mode="json"))
                    run.status = "awaiting_claims"
            else:
                run.revision += 1
                self.handoff(run, stage, target, result.model_dump(mode="json"))
        else:
            raise ValueError("Unknown review stage")

    def handoff_screening(self, run):
        paper_ids = {paper.id for paper in run.search.papers}
        decisions = run.screening.decisions
        if {d.paper_id for d in decisions} != paper_ids:
            raise ValueError("Every discovered paper needs one screening decision")
        counts = run.screening.counts()
        artifact = run.screening.model_dump(mode="json")
        if not counts["included"]:
            self.insufficient(run, "screening", "No studies met the inclusion policy. Unresolved records were withheld.",
                              artifact)
            return
        self.handoff(run, "screening", "rag", artifact)
        run.status = "awaiting_documents" if run.config.pause_for_documents else "running"

    def finish_screening(self, run):
        if run.status != "awaiting_screening" or run.config.execution_mode != "human_in_the_loop":
            raise ValueError("This review has no open screening checkpoint")
        self.handoff_screening(run)
        run.events.append(Event(stage="screening", kind="human", operation="finish_screening",
                                status="ok", seconds=0,
                                detail="Released the checkpoint. Any unresolved papers were withheld."))
        self.store.save(run)
        return self.advance(run)

    def continue_automatically(self, run):
        if run.status != "awaiting_screening" or run.config.screen not in {"llm", "hybrid"}:
            raise ValueError("Only an LLM-screened review paused at screening can continue automatically")
        run.config = run.config.model_copy(update={"execution_mode": "automatic", "pause_for_documents": False})
        self.handoff_screening(run)
        run.events.append(Event(stage="screening", kind="human", operation="continue_automatically",
                                status="ok", seconds=0, detail="Preserved all decisions and withheld unresolved records."))
        self.store.save(run)
        return self.advance(run)

    def review_screening(self, run, paper_id, decision, reason):
        if (run.status != "awaiting_screening" or run.config.execution_mode != "human_in_the_loop"
                or decision not in {"include", "exclude", "uncertain"}):
            raise ValueError("This review has no open checkpoint for that screening decision")
        reason = (reason or "").strip()
        if not reason:
            raise ValueError("Provide a reason for the decision")
        item = next((d for d in run.screening.decisions if d.paper_id == paper_id), None)
        if item is None:
            raise ValueError("Unknown paper in this screening batch")
        if not item.screening_reason:
            item.screening_reason = item.reason
        item.review_history.append(ScreeningOverride(
            previous_verdict=item.final, previous_origin=item.decided_by, previous_reason=item.reason,
            verdict=decision, reason=reason,
        ))
        item.final, item.decided_by, item.reason = decision, "human", reason
        run.events.append(Event(stage="screening", kind="human", operation=f"screening_{decision}",
                                status="ok", seconds=0, detail=paper_id))
        self.store.save(run)
        return run

    def attach_document(self, run, paper_id, pdf):
        if run.status not in {"awaiting_documents", "awaiting_screening"}:
            raise ValueError("Document collection is closed for this review")
        allowed = {d.paper_id for d in run.screening.decisions if d.final != "exclude"}
        if paper_id not in allowed or not pdf.startswith(b"%PDF") or len(pdf) > 12 * 1024 * 1024:
            raise ValueError("Choose a retained paper and a PDF under 12 MiB")
        try:
            pages = extract_pdf_pages(BytesIO(pdf))
        except Exception as exc:
            raise ValueError("The PDF could not be read or contains no extractable text") from exc
        if not any(pages) or len(pages) > 250 or sum(map(len, pages)) > 1_000_000:
            raise ValueError("Use a PDF with extractable text and up to 250 pages / 1 million characters")
        run.full_text[paper_id] = pages
        self.store.save(run)
        return run

    def finish_documents(self, run):
        if run.status != "awaiting_documents":
            raise ValueError("No document checkpoint is pending")
        run.status = "running"
        self.store.save(run)
        return self.advance(run)

    def review_claim(self, run, claim_id, decision, reason):
        if run.status != "awaiting_claims":
            raise ValueError("No claims are awaiting review")
        latest = run.quality[-1]
        pending = pending_claims(run)
        if claim_id not in pending:
            raise ValueError("Unknown or resolved pending claim")
        response = ClaimReview(claim_id=claim_id, decision=decision, reason=reason.strip())
        if response.decision == "accept" and claim_id in latest.invalid_claims:
            raise ValueError("Remove claims with unresolved evidence identifiers or inline references")
        run.adjudications.append(response)
        run.events.append(Event(stage="quality", kind="human", operation=decision,
                                status="ok", seconds=0, detail=claim_id))
        if not pending_claims(run):
            self.complete(run, source="quality")
        self.store.save(run)
        return run

    def complete(self, run, source="quality"):
        artifact = {
            "claim_ids": [claim.id for claim in run.retained_claims()],
            "human_decisions": [item.model_dump(mode="json") for item in run.adjudications],
            "withheld_claim_ids": run.withheld_claim_ids,
        }
        if not artifact["claim_ids"]:
            self.insufficient(run, source, "No supported, cited claims remained after quality review.", artifact)
            return
        self.handoff(run, source, "finish", artifact)
        run.status = "complete"

    def insufficient(self, run, stage, reason, artifact):
        self.handoff(run, stage, "insufficient_evidence", {**artifact, "outcome_reason": reason})
        run.outcome_reason = reason
        run.status = "insufficient_evidence"


def pending_claims(run):
    if not run.quality:
        return set()
    reviewed = {item.claim_id for item in run.adjudications}
    return {item.claim_id for item in run.quality[-1].findings if item.judgment != "supported"} - reviewed
