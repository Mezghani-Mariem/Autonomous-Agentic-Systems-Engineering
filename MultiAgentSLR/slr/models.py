import re
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from .course.agentic_rag_models import AgentTraceEvent, EvidenceFacet
from .course.contracts import SearchState
from .course.planning_models import ExecutionResult, PlanCandidate
from .course.quality_models import Handoff
from .course.search_plan import ResearchQuestion

Sources = Literal["openalex", "semantic_scholar", "crossref"]
SOURCES = ("openalex", "semantic_scholar", "crossref")
Verdict = Literal["include", "exclude", "uncertain"]
DecisionOrigin = Literal["ai", "rule", "automatic", "human", "pending"]
STAGES = ("planning", "search", "screening", "rag", "writing", "quality")


def now():
    return datetime.now(timezone.utc).isoformat()


class ReviewConfig(BaseModel):
    topic: str = Field(min_length=12, max_length=1000)
    provider: Literal["ollama", "groq"] = "ollama"
    execution_mode: Literal["automatic", "human_in_the_loop"] = "automatic"
    per_source: int = Field(default=4, ge=1, le=15)
    search: Literal["react", "fixed"] = "react"
    screen: Literal["rules", "llm", "hybrid"] = "llm"
    retrieval: Literal["classical", "agentic"] = "agentic"
    orchestration: Literal["supervisor", "fixed"] = "supervisor"
    top_k: int = Field(default=3, ge=1, le=8)
    retrieval_budget: int = Field(default=2, ge=1, le=3)
    revision_budget: int = Field(default=1, ge=0, le=2)
    pause_for_documents: bool = False
    inclusion: str = Field(default="Primary research relevant to the topic.", min_length=5, max_length=1500)
    exclusion: str = Field(default="Exclude out-of-scope work and records without primary research.", min_length=5, max_length=1500)

    @model_validator(mode="after")
    def validate_execution_mode(self):
        if self.execution_mode == "automatic" and self.pause_for_documents:
            raise ValueError("Use Human-in-the-Loop mode to pause for full-text PDFs")
        return self


class QuestionProtocol(BaseModel):
    rq_id: Literal["RQ1", "RQ2", "RQ3"]
    terms: list[str] = Field(min_length=1, max_length=5)
    facets: list[EvidenceFacet] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def check_facets(self):
        if len({facet.id for facet in self.facets}) != len(self.facets):
            raise ValueError("Repeated facet ID")
        if any(not term.strip() for term in self.terms):
            raise ValueError("Blank search term")
        return self


class ProtocolProposal(BaseModel):
    queries: dict[str, str]
    questions: list[QuestionProtocol] = Field(min_length=3, max_length=3)
    include_signals: list[str] = Field(default_factory=list, max_length=12)
    exclude_signals: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("queries")
    @classmethod
    def normalize_source_names(cls, queries):
        sources = {source.replace("_", ""): source for source in SOURCES}
        normalized = {}
        for key, query in queries.items():
            canonical = sources.get(re.sub(r"[^a-z]", "", key.casefold()))
            if canonical is None or canonical in normalized:
                raise ValueError("Queries must have distinct keys for the three allowed sources")
            normalized[canonical] = query.strip()
        if set(normalized) != set(SOURCES):
            raise ValueError("Queries must cover OpenAlex, Semantic Scholar and Crossref")
        return normalized


class ResearchPlan(BaseModel):
    origin: Literal["planning"] = "planning"
    questions: list[ResearchQuestion] = Field(min_length=3, max_length=3)
    protocol: ProtocolProposal
    plan: PlanCandidate
    repair_attempts: int = Field(default=0, ge=0, le=1)
    protocol_repairs: int = Field(default=0, ge=0, le=1)

    @model_validator(mode="after")
    def check_protocol(self):
        expected = {"RQ1", "RQ2", "RQ3"}
        if {q.identifier for q in self.questions} != expected:
            raise ValueError("Expected RQ1, RQ2 and RQ3")
        if {q.rq_id for q in self.protocol.questions} != expected:
            raise ValueError("Protocol must cover each question once")
        if set(self.protocol.queries) != set(SOURCES):
            raise ValueError("A query is required for each scientific source")
        if any(not 3 <= len(q.strip()) <= 420 or not any(c.isalnum() for c in q)
               for q in self.protocol.queries.values()):
            raise ValueError("Malformed bibliographic query")
        if {step.rq_id for step in self.plan.steps} != expected or len(self.plan.steps) != 3:
            raise ValueError("Planning steps must cover the three research questions")
        return self


class SourceRecord(BaseModel):
    source: Sources
    native_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    abstract: str = ""
    doi: str = ""
    url: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    open_access: bool | None = None


class Study(BaseModel):
    id: str
    title: str
    abstract: str = ""
    doi: str = ""
    url: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract_source: Sources | None = None
    sources: list[SourceRecord] = Field(min_length=1)


class SearchBatch(BaseModel):
    origin: Literal["search"] = "search"
    papers: list[Study]
    discovered: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    state: SearchState

    @model_validator(mode="after")
    def check_counts(self):
        if len({paper.id for paper in self.papers}) != len(self.papers):
            raise ValueError("Duplicate canonical paper ID")
        if len(self.papers) + self.duplicates != self.discovered:
            raise ValueError("Inconsistent discovery counts")
        return self


class ScreeningOverride(BaseModel):
    previous_verdict: Verdict
    previous_origin: DecisionOrigin
    previous_reason: str
    verdict: Verdict
    reason: str = Field(min_length=1)
    timestamp: str = Field(default_factory=now)


class ScreeningDecision(BaseModel):
    paper_id: str
    rule: Verdict | None = None
    llm: Verdict | None = None
    final: Verdict
    decided_by: DecisionOrigin
    reason: str = Field(min_length=1)
    quote: str = ""
    quote_verified: bool | None = None
    rule_reason: str = ""
    llm_confidence: float | None = Field(default=None, ge=0, le=1)
    screening_reason: str = ""
    review_history: list[ScreeningOverride] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_pending(self):
        if self.final == "uncertain" and self.decided_by not in {"pending", "human"}:
            raise ValueError("Uncertain records must be pending or explicitly deferred by a reviewer")
        if self.final != "uncertain" and self.decided_by == "pending":
            raise ValueError("A definite screening decision needs a decision-maker")
        return self


class ScreeningBatch(BaseModel):
    origin: Literal["screening"] = "screening"
    decisions: list[ScreeningDecision]
    policy: str = "legacy"

    @model_validator(mode="after")
    def unique_papers(self):
        if len({d.paper_id for d in self.decisions}) != len(self.decisions):
            raise ValueError("Multiple screening decisions for a paper")
        return self

    def counts(self):
        return {
            "included": sum(d.final == "include" for d in self.decisions),
            "excluded": sum(d.final == "exclude" for d in self.decisions),
            "unresolved": sum(d.final == "uncertain" for d in self.decisions),
            "automatically_included": sum(d.final == "include" and d.decided_by in {"ai", "automatic", "rule"}
                                          for d in self.decisions),
            "automatically_excluded": sum(d.final == "exclude" and d.decided_by in {"ai", "automatic", "rule"}
                                          for d in self.decisions),
        }


class EvidenceLocation(BaseModel):
    paper_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    source_type: Literal["abstract", "full_text"] = Field(validation_alias=AliasChoices("source_type", "kind"))
    page: int | None = Field(default=None, ge=1)
    source: Sources | None = None
    source_record_id: str = ""
    source_url: str = ""

    @model_validator(mode="after")
    def check_page(self):
        if (self.source_type == "full_text") != (self.page is not None):
            raise ValueError("Only full-text citations reference a page")
        return self


class EvidenceChunk(EvidenceLocation):
    text: str = Field(min_length=1)


class Passage(EvidenceLocation):
    id: str
    rq_id: str
    quote: str = Field(min_length=1)
    facets: list[str] = Field(default_factory=list)

    @property
    def kind(self):
        return self.source_type


class ExcerptSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)
    candidate_id: StrictInt


class ExtractionAudit(BaseModel):
    status: Literal["verified", "no_chunks", "no_candidates", "empty_selection", "invalid_response", "rejected"]
    candidate_count: int = 0
    selections: list[ExcerptSelection] = Field(default_factory=list)
    rejections: list[str] = Field(default_factory=list)
    verified_count: int = 0
    reason: str = ""


class RetrievalRun(BaseModel):
    rq_id: str
    ranks: list[str] = Field(default_factory=list)
    covered: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    calls: int = Field(ge=0)
    requested_k: int | None = Field(default=None, ge=1)
    status: str
    method: str
    trace: list[AgentTraceEvent] = Field(default_factory=list)
    query: str = ""
    extraction: ExtractionAudit | None = None


class CorpusSummary(BaseModel):
    included_abstracts: int
    abstract_chunks: int
    full_text_chunks: int
    missing_text_paper_ids: list[str]


class RagBundle(BaseModel):
    origin: Literal["rag"] = "rag"
    evidence: list[Passage]
    retrieval: list[RetrievalRun]
    corpus: CorpusSummary | None = None

    @model_validator(mode="after")
    def unique_evidence(self):
        if len({item.id for item in self.evidence}) != len(self.evidence):
            raise ValueError("Duplicate evidence ID")
        return self


class Claim(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    rq_id: str
    text: str = Field(min_length=5, max_length=2000)
    evidence_ids: list[str] = Field(max_length=8)


class ClaimProposal(BaseModel):
    claims: list[Claim] = Field(max_length=18)


class Draft(BaseModel):
    origin: Literal["writing"] = "writing"
    claims: list[Claim]
    execution: ExecutionResult

    @model_validator(mode="after")
    def unique_claims(self):
        if len({claim.id for claim in self.claims}) != len(self.claims):
            raise ValueError("Duplicate claim IDs")
        return self


class ClaimCheck(BaseModel):
    claim_id: str
    judgment: Literal["supported", "unsupported", "uncertain"]
    reason: str = Field(min_length=1)


class JudgeResponse(BaseModel):
    findings: list[ClaimCheck]


class ClaimReview(BaseModel):
    claim_id: str
    decision: Literal["accept", "remove"]
    reason: str = Field(min_length=4, max_length=2000)


class QualityResult(BaseModel):
    revision: int = Field(ge=0)
    citation_validity: float = Field(ge=0, le=1)
    lexical_support: float = Field(ge=0, le=1)
    automated_score: float = Field(ge=0, le=1)
    question_coverage: float = Field(ge=0, le=1)
    findings: list[ClaimCheck]
    invalid_claims: list[str]
    feedback: list[str]


class Event(BaseModel):
    stage: str
    kind: Literal["agent", "api", "llm", "embedding", "human"]
    operation: str
    status: Literal["ok", "error", "cache_hit"]
    seconds: float = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    retry: bool = False
    detail: str = ""
    timestamp: str = Field(default_factory=now)


class ReviewRun(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    config: ReviewConfig
    status: Literal[
        "running", "awaiting_screening", "awaiting_documents", "awaiting_claims",
        "failed", "insufficient_evidence", "complete",
    ] = "running"
    next_stage: str = "planning"
    created: str = Field(default_factory=now)
    updated: str = Field(default_factory=now)
    version: int = 0
    revision: int = 0
    error: str = ""
    outcome_reason: str = ""
    plan: ResearchPlan | None = None
    search: SearchBatch | None = None
    screening: ScreeningBatch | None = None
    full_text: dict[str, list[str]] = Field(default_factory=dict)
    rag: RagBundle | None = None
    draft: Draft | None = None
    quality: list[QualityResult] = Field(default_factory=list)
    adjudications: list[ClaimReview] = Field(default_factory=list)
    withheld_claim_ids: list[str] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    handoffs: list[Handoff] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def preserve_saved_review_mode(cls, values):
        config = values.get("config") if isinstance(values, dict) else None
        if isinstance(config, dict) and "execution_mode" not in config:
            return {**values, "config": {**config, "execution_mode": "human_in_the_loop"}}
        return values

    def retained_claims(self):
        removed = {item.claim_id for item in self.adjudications if item.decision == "remove"}
        removed.update(self.withheld_claim_ids)
        return [claim for claim in self.draft.claims if claim.id not in removed] if self.draft else []

    def can_retry_retrieval(self):
        return self.status == "insufficient_evidence" and bool(self.handoffs) and self.handoffs[-1].source == "rag"
