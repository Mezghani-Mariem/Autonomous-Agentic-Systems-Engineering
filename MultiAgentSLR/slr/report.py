from dataclasses import dataclass
from html import escape
from io import BytesIO
import re

from .models import SOURCES
from .screen import LLM_POLICY, LLM_CONFIDENCE_FLOOR


@dataclass(frozen=True)
class Block:
    role: str
    text: str


def report_blocks(run, *, context=""):
    if run.status != "complete":
        raise ValueError(run.outcome_reason or "Complete the review before exporting a report")
    reviews = {item.claim_id: item for item in run.adjudications}
    claims = run.retained_claims()
    evidence = {item.id: item for item in run.rag.evidence}
    papers = {paper.id: paper for paper in run.search.papers}
    referenced = list(dict.fromkeys(evidence[ref].paper_id for c in claims for ref in c.evidence_ids))
    bibliographic_id = {identifier: index for index, identifier in enumerate(referenced, 1)}
    included = [item for item in run.screening.decisions if item.final == "include"]
    unresolved = [item for item in run.screening.decisions if item.final == "uncertain"]
    counts = run.screening.counts()
    abstracts_only = sum(1 for item in included if item.paper_id not in run.full_text)
    missing = "Full text was unavailable or not supplied for " + f"{abstracts_only} of {len(included)} included records."
    blocks = [Block("title", "Literature review"), Block("subtitle", run.config.topic)]
    if context:
        blocks.append(Block("note", context))
    blocks.extend([
        Block("note", "Evidence scope: abstract-first. " + missing),
        Block("p", "Abstract-based findings are limited to what those abstracts report. "
                   "Bibliographic searches and automated checks support a bounded research workflow."),
        Block("p", f"Review ID {run.id} | Started {run.created[:10]}"),
        Block("h2", "Search and selection"),
        Block("p", f"Inclusion criteria: {run.config.inclusion}"),
        Block("p", f"Exclusion criteria: {run.config.exclusion}"),
        Block("p", f"The result limit was {run.config.per_source} per source. "
                   f"Observed {run.search.discovered} records, removed {run.search.duplicates} duplicates, "
                   f"screened {len(run.screening.decisions)}, included {counts['included']}, "
                   f"excluded {counts['excluded']}, and left {counts['unresolved']} unresolved."),
        Block("p", f"Execution mode: {run.config.execution_mode.replace('_', ' ')}. "
                   f"The policy automatically included {counts['automatically_included']} and excluded "
                   f"{counts['automatically_excluded']} records."),
    ])
    if run.screening.policy == LLM_POLICY:
        blocks.append(Block("p", "AI screening used the declared eligibility criteria. Definite decisions required "
                                 "an available abstract, a justification, a grounded excerpt longer than one word, no review flag, "
                                 f"and confidence of at least {LLM_CONFIDENCE_FLOOR:.2f}. "
                                 "AI decisions are recorded separately from reviewer decisions."))
    elif run.screening.policy == "hybrid-agreement-v1":
        blocks.append(Block("p", "Automatic screening decisions required rule and LLM agreement on a definite verdict, "
                                 "an available abstract, no review flags, and a grounded LLM excerpt with confidence "
                                 f"of at least {LLM_CONFIDENCE_FLOOR:.2f}. The model's confidence is a screening signal."))
    for source in SOURCES:
        observations = [obs.status for obs in run.search.state.observations if obs.tool == source]
        status = ", ".join(observations) or "unattempted"
        blocks.append(Block("p", f"{source} ({status}): {run.plan.protocol.queries[source]}"))
    if unresolved:
        blocks.append(Block("h3", "Unresolved screening records"))
        blocks.append(Block("p", "These records were withheld from retrieval and may change the findings if reviewed."))
        for item in unresolved:
            blocks.append(Block("p", f"{item.paper_id} · {papers[item.paper_id].title}. {item.reason}"))
    blocks.extend([
        Block("h2", "Synthesis"),
        Block("p", f"Search mode: {run.config.search}. Screening policy: {run.screening.policy}. "
                   f"Retrieval: {run.config.retrieval}. Quality revisions: {run.revision}."),
    ])
    models = sorted({event.operation.rsplit("/", 1)[0] for event in run.events if event.kind == "llm"})
    if models:
        blocks.append(Block("p", "Model calls recorded for " + ", ".join(models) + "."))
    if run.withheld_claim_ids:
        count = len(run.withheld_claim_ids)
        unit = "claim" if count == 1 else "claims"
        blocks.append(Block("p", f"Quality review withheld {count} {unit} with insufficient support "
                                 "or invalid citations at final quality review."))
    for question in run.plan.questions:
        blocks.append(Block("h3", f"{question.identifier}. {question.question}"))
        selected = [claim for claim in claims if claim.rq_id == question.identifier]
        retrieval = next((item for item in run.rag.retrieval if item.rq_id == question.identifier), None)
        if not selected:
            blocks.append(Block("p", "No supported claim was retained for this research question."))
        if retrieval and retrieval.missing:
            blocks.append(Block("p", "Retrieval did not cover these configured facets: " + ", ".join(retrieval.missing) + "."))
        for claim in selected:
            indexes = sorted({bibliographic_id[evidence[ref].paper_id] for ref in claim.evidence_ids})
            tags = " ".join(f"[{i}]" for i in indexes)
            mode = "human adjudication" if claim.id in reviews else "automated evidence check"
            blocks.append(Block("p", f"{claim.text} {tags} ({claim.id}, {mode})"))
            if claim.id in reviews:
                blocks.append(Block("p", "Human reason: " + reviews[claim.id].reason))
    blocks.append(Block("h2", "Evidence and provenance"))
    for ref in dict.fromkeys(ref for c in claims for ref in c.evidence_ids):
        item = evidence[ref]
        where = f"supplied full text, page {item.page}" if item.source_type == "full_text" else "abstract only"
        source = item.source or papers[item.paper_id].abstract_source
        if item.source_type == "abstract" and source:
            where += f" via {source}"
            if item.source_record_id:
                where += f" ({item.source_record_id})"
        blocks.append(Block("quote", f"{item.id} · [{bibliographic_id[item.paper_id]}] · {where} · "
                                     f"{item.chunk_id} · “{item.quote}”"))
    if not referenced:
        blocks.append(Block("p", "There are no retained citations."))
    blocks.append(Block("h2", "References"))
    for identifier in referenced:
        paper = papers[identifier]
        author = ", ".join(paper.authors) if paper.authors else "Authors unavailable in retrieved metadata"
        year = f" ({paper.year})" if paper.year else " (year unavailable)"
        aliases = ", ".join(f"{item.source}:{item.native_id}" for item in paper.sources)
        url = f" {paper.url}" if paper.url else ""
        blocks.append(Block("p", f"[{bibliographic_id[identifier]}] {author}{year}. {paper.title}.{url}"))
        blocks.append(Block("p", f"Study ID {paper.id}. Source records: {aliases}."))
    blocks.append(Block("h2", "Limitations"))
    evidence_papers = {item.paper_id for item in run.rag.evidence}
    blocks.append(Block("p", f"Verified excerpts were available from {len(evidence_papers)} of "
                             f"{counts['included']} included records. Findings cover only the retained evidence."))
    blocks.append(Block("p", "The configured source and result limits constrain retrieval coverage. "
                             "Automated support judgments and lexical overlap are screening aids. "
                             "The supplied sources and any human adjudications should be checked for scientific interpretation."))
    return blocks


def markdown(run, *, context=""):
    prefixes = {"title": "# ", "subtitle": "## ", "h2": "## ", "h3": "### ", "note": "> ", "quote": "> "}
    def safe(text):
        text = re.sub(r"[\r\n]+", " ", text)
        return re.sub(r"([\\\x60*_<>])", r"\\\1", text)
    return "\n\n".join(prefixes.get(block.role, "") + safe(block.text)
                       for block in report_blocks(run, context=context)) + "\n"


def pdf(run, *, context=""):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    output = BytesIO()
    style = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, leading=15,
                           textColor=colors.HexColor("#233145"), spaceAfter=8, alignment=TA_LEFT,
                           splitLongWords=True)
    def variant(name, **options):
        return ParagraphStyle(name, parent=style, **options)

    styles = {
        "title": variant("title", fontName="Helvetica-Bold", fontSize=26, leading=31,
                         textColor=colors.HexColor("#102846"), spaceAfter=13, keepWithNext=True),
        "subtitle": variant("subtitle", fontSize=15, leading=20, keepWithNext=True, spaceAfter=15),
        "h2": variant("h2", fontName="Helvetica-Bold", fontSize=15, leading=19,
                      spaceBefore=13, keepWithNext=True, textColor=colors.HexColor("#102846")),
        "h3": variant("h3", fontName="Helvetica-Bold", spaceBefore=8, keepWithNext=True),
        "note": variant("note", backColor=colors.HexColor("#eaf3f2"), borderPadding=8,
                        spaceBefore=7, spaceAfter=15, textColor=colors.HexColor("#174c49")),
        "quote": variant("quote", leftIndent=13, fontSize=9.5, leading=14,
                         textColor=colors.HexColor("#42546b")),
    }
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d7e1ea"))
        canvas.line(doc.leftMargin, 0.54 * inch, doc.pagesize[0] - doc.rightMargin, 0.54 * inch)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#526579"))
        canvas.drawString(doc.leftMargin, 0.38 * inch, "Multi-Agent SLR  |  Evidence-linked report")
        canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.38 * inch, str(doc.page))
        canvas.restoreState()

    story = [Paragraph(escape(re.sub(r"[\r\n]+", " ", b.text)).replace("—", "-").replace("–", "-"),
                       styles.get(b.role, style)) for b in report_blocks(run, context=context)]
    doc = SimpleDocTemplate(output, title=run.config.topic, leftMargin=52, rightMargin=52,
                            topMargin=48, bottomMargin=54)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
