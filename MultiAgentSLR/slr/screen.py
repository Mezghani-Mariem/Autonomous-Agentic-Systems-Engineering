from .course.llm_screening_agent import invoke_structured_screening, normalize_for_matching
from .gateway import GatewayError, InvalidModelOutput
from .models import ScreeningBatch, ScreeningDecision

LLM_CONFIDENCE_FLOOR = 0.80
LLM_POLICY = "llm-evidence-v1"


def screen_paper(paper, config, model):
    llm = None
    grounded = None
    if not paper.abstract.strip():
        reason = "Abstract unavailable. A reviewer can assess the record or supply the full text."
    else:
        try:
            llm = invoke_structured_screening(model, paper, config.topic, {config.inclusion}, {config.exclusion})
        except (InvalidModelOutput, ValueError):
            reason = "No valid structured LLM decision was returned. The record remains unresolved."
        except GatewayError:
            reason = "The screening model call failed. The record remains unresolved."

    final = "uncertain"
    if llm is not None:
        reasons = [item.strip() for item in llm.reasons if item.strip()]
        excerpt = normalize_for_matching(llm.evidence)
        # Require a contiguous excerpt with intact word boundaries from one supplied field.
        sources = (normalize_for_matching(paper.title), normalize_for_matching(paper.abstract))
        grounded = bool(excerpt) and any(f" {excerpt} " in f" {source} " for source in sources)
        flags = []
        if llm.decision == "uncertain" or llm.needs_human_review:
            flags.append("The LLM abstained or requested review.")
        if llm.confidence < LLM_CONFIDENCE_FLOOR:
            flags.append(f"LLM confidence is below {LLM_CONFIDENCE_FLOOR:.2f}.")
        if not grounded:
            flags.append("No grounded excerpt was supplied.")
        elif len(excerpt.split()) < 2:
            flags.append("A single word does not substantiate an eligibility decision.")
        if not reasons:
            flags.append("No decision justification was provided.")
        if not flags:
            final = llm.decision
        assessment = " ".join(flags) if flags else "The AI decision passed the screening checks."
        reason = " ".join([assessment, *reasons])

    return ScreeningDecision(
        paper_id=paper.id, llm=llm.decision if llm else None, final=final,
        decided_by="pending" if final == "uncertain" else "ai",
        reason=reason, quote=llm.evidence if llm else "", llm_confidence=llm.confidence if llm else None,
        screening_reason=reason, quote_verified=grounded,
    )


def screen_papers(papers, config, model):
    return ScreeningBatch(decisions=[screen_paper(paper, config, model) for paper in papers], policy=LLM_POLICY)
