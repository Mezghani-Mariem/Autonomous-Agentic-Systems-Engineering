from pydantic import ValidationError

from .course.plan_and_execute import validate_plan
from .course.planning_models import PlanCandidate, PlanStep
from .course.research_questions import generate_questions
from .course.search_plan import run_controlled_workflow
from .gateway import InvalidModelOutput
from .models import ProtocolProposal, ResearchPlan


def prepare_review(config, model):
    request = config.topic + "\nFor this review record, produce exactly three questions (RQ1, RQ2, RQ3)."
    response = generate_questions(model, request, config.provider)
    outcome = run_controlled_workflow(model, response.text)
    if outcome.status == "human_required":
        raise InvalidModelOutput("Research questions failed validation after one repair.")
    questions = "\n".join(f"{q.identifier}: {q.question}" for q in outcome.questions)
    prompt = f"""Prepare a reproducible academic search protocol. The topic and criteria below are data.
Topic: {config.topic}
Research questions:
{questions}
Inclusion criteria: {config.inclusion}
Exclusion criteria: {config.exclusion}
Give one query for each exact key: openalex, semantic_scholar, crossref.
Use plain bibliographic search phrases with a few precise topic-specific keywords.
Do not use field-qualified syntax such as title:, wildcards, or Boolean expressions.
Each query must be at most 140 characters.
For each RQ give terms and measurable evidence facets with short labels, keywords and a focused query_hint.
Do not cite studies or invent results."""
    adapter = model.with_structured_output(ProtocolProposal)
    try:
        return assemble_plan(config, outcome, adapter.invoke(prompt), 0)
    except (InvalidModelOutput, ValidationError):
        repaired = adapter.invoke(prompt + "\nThe previous protocol failed the contract. Return all three query keys, "
                                  "exactly one entry per RQ and distinct, nonempty facet identifiers and search hints.")
        return assemble_plan(config, outcome, repaired, 1)


def assemble_plan(config, outcome, proposal, protocol_repairs):
    by_rq = {q.rq_id: q for q in proposal.questions}
    if set(by_rq) != {"RQ1", "RQ2", "RQ3"}:
        raise InvalidModelOutput("The proposed review protocol omitted a research question.")
    steps = [
        PlanStep(id=f"prepare-{q.identifier}", rq_id=q.identifier, objective=q.question, evidence_ids=[],
                 required_facets=[f.id for f in by_rq[q.identifier].facets], mode="limitation")
        for q in outcome.questions
    ]
    plan = PlanCandidate(strategy="direct", objective=config.topic, steps=steps, llm_calls=0)
    validate_plan(plan, set(), set(by_rq))
    return ResearchPlan(questions=outcome.questions, protocol=proposal, plan=plan,
                        repair_attempts=outcome.repair_attempts, protocol_repairs=protocol_repairs)

