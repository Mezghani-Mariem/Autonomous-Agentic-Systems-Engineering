import hmac
import json
from pathlib import Path

import streamlit as st

from evaluation.benchmarks import BENCHMARKS, run_benchmark
from evaluation.metrics import load_annotations, review_metrics, to_csv
from slr.gateway import GatewayError
from slr.models import ReviewConfig, STAGES
from slr.report import markdown, pdf
from slr.screen import LLM_POLICY
from slr.settings import Settings
from slr.storage import DiskStore, StaleRunError
from slr.supervisor import Supervisor, pending_claims

st.set_page_config(page_title="Multi-Agent SLR", page_icon=":material/menu_book:", layout="wide")
settings = Settings.from_env()
if settings.access_token and not st.session_state.get("slr_authenticated"):
    st.title("Multi-Agent SLR")
    with st.form("access"):
        token = st.text_input("Team access token", type="password")
        submitted = st.form_submit_button("Open workspace", type="primary")
    if submitted:
        if hmac.compare_digest(token, settings.access_token):
            st.session_state.slr_authenticated = True
            st.rerun()
        st.error("The access token did not match.")
    st.stop()

store = DiskStore(settings.data_dir)
supervisor = Supervisor(store, settings)
MODE_LABELS = {"automatic": "Automatic", "human_in_the_loop": "Human-in-the-Loop"}
STAGE_LABELS = {
    "planning": "Research planning", "search": "Scientific search", "screening": "Title and abstract screening",
    "rag": "Evidence retrieval", "writing": "Synthesis", "quality": "Quality review",
}


def select_review():
    runs = store.recent()
    titles = {run.id: f"{run.config.topic[:68]} · {run.id[:8]}" for run in runs}
    options = [""] + list(titles)
    current = st.session_state.get("review_id", "")
    index = options.index(current) if current in options else 0
    selected = st.sidebar.selectbox("Saved review", options, index=index,
                                    format_func=lambda item: titles.get(item, "New review"))
    st.session_state.review_id = selected
    return store.load(selected) if selected else None


def run_action(action):
    try:
        with st.status("Updating review…") as progress:
            def show_stage(stage):
                label = STAGE_LABELS[stage]
                progress.update(label=f"Stage {STAGES.index(stage) + 1} of {len(STAGES)} · {label}")
                st.write(label)

            supervisor.on_stage = show_stage
            try:
                action()
            finally:
                supervisor.on_stage = None
        st.rerun()
    except (ValueError, StaleRunError, GatewayError) as exc:
        st.error(str(exc))


def upload_full_text(run):
    decisions = {d.paper_id: d for d in run.screening.decisions if d.final != "exclude"}
    papers = {p.id: p for p in run.search.papers if p.id in decisions}
    if not papers:
        return
    with st.expander("Attach full text to a paper"):
        st.caption("Choose the matching paper. The report records supplied full text and its page numbers.")
        with st.form("document"):
            selected = st.selectbox("Paper", list(papers), format_func=lambda identifier: papers[identifier].title)
            document = st.file_uploader("PDF", type=["pdf"])
            uploaded = st.form_submit_button("Attach PDF")
        if uploaded and document is not None:
            run_action(lambda: supervisor.attach_document(run, selected, document.getvalue()))
        if run.full_text:
            st.write("PDFs attached", len(run.full_text))


def screening_ui(run):
    st.subheader("Review screening decisions")
    st.caption("Review unresolved papers or override a decision with a reason. Only included studies go to retrieval.")
    papers = {paper.id: paper for paper in run.search.papers}
    for item in sorted(run.screening.decisions, key=lambda decision: decision.final != "uncertain"):
        paper = papers[item.paper_id]
        label = "unresolved" if item.final == "uncertain" else item.final
        with st.expander(f"{paper.title} · {label}", expanded=item.final == "uncertain"):
            st.write(paper.abstract or "Abstract unavailable.")
            if paper.url.startswith(("https://", "http://")):
                st.link_button("Open source record", paper.url)
            st.caption(f"{paper.id} · {item.final} by {item.decided_by} · {item.reason}")
            st.write({"AI recommendation": item.llm, "Submitted excerpt": item.quote,
                      "Excerpt verified": item.quote_verified})
            key = f"screen-{run.id}-{paper.id}"
            with st.form(key):
                decision = st.radio("Decision", ["include", "exclude", "uncertain"], horizontal=True, index=None,
                                    key=f"{key}-decision")
                reason = st.text_area("Reason", key=f"{key}-reason")
                if st.form_submit_button("Save screening decision"):
                    run_action(lambda: supervisor.review_screening(run, paper.id, decision, reason))
    upload_full_text(run)
    eligible = run.screening.counts()["included"]
    label = "Continue to evidence retrieval" if eligible else "Finish screening"
    if st.button(label, type="primary"):
        run_action(lambda: supervisor.finish_screening(run))
    if run.config.screen in {"llm", "hybrid"}:
        if st.button("Continue in Automatic mode"):
            run_action(lambda: supervisor.continue_automatically(run))


def quality_ui(run):
    st.subheader("Claims need your review")
    findings = {f.claim_id: f for f in run.quality[-1].findings}
    evidence = {item.id: item for item in run.rag.evidence}
    for claim in run.draft.claims:
        if claim.id not in pending_claims(run):
            continue
        with st.expander(f"{claim.id} · {claim.rq_id}", expanded=True):
            st.write(claim.text)
            st.warning(findings[claim.id].reason)
            for ref in claim.evidence_ids:
                if ref in evidence:
                    item = evidence[ref]
                    provenance = f"Page {item.page}" if item.page else "Abstract"
                    st.caption(f"{ref} · {item.paper_id} · {provenance}")
                    st.write(item.quote)
            choices = ["remove"] if claim.id in run.quality[-1].invalid_claims else ["accept", "remove"]
            with st.form(f"claim-{claim.id}"):
                decision = st.radio("Resolution", choices, horizontal=True)
                reason = st.text_area("Scientific justification")
                if st.form_submit_button("Save claim decision"):
                    run_action(lambda: supervisor.review_claim(run, claim.id, decision, reason))


def show_review_progress(run):
    finished = {event.stage for event in run.events if event.kind == "agent" and event.status == "ok"}
    stage = run.next_stage
    if run.status == "awaiting_claims":
        stage = "quality"
    elif run.status == "insufficient_evidence":
        stage = run.handoffs[-1].source
    label = STAGE_LABELS.get(stage, "Review finished")
    st.progress(len(finished & STAGE_LABELS.keys()) / len(STAGES),
                text=f"{MODE_LABELS[run.config.execution_mode]} · {label}")
    if run.screening is None:
        st.caption("Report eligibility is assessed after screening and evidence review.")
        return

    counts = run.screening.counts()
    policy = run.screening.policy
    included_label = "AI included" if policy == LLM_POLICY else "Automatically included"
    excluded_label = "AI excluded" if policy == LLM_POLICY else "Automatically excluded"
    for column, key, title in zip(st.columns(3),
                                  ("automatically_included", "automatically_excluded", "unresolved"),
                                  (included_label, excluded_label, "Unresolved")):
        column.metric(title, counts[key])
    if run.status == "insufficient_evidence":
        st.warning(f"Report unavailable. {run.outcome_reason}")
    elif run.status == "complete" and run.retained_claims():
        st.success("Report ready. The review retained supported claims with verified citations.")
    elif run.status == "awaiting_screening":
        st.info(f"{counts['included']} studies are eligible for retrieval. Continue when you are ready. "
                "Unresolved papers will be withheld.")
    elif run.status == "awaiting_claims":
        st.info("Report on hold until claim review is complete.")
    elif counts["included"]:
        st.info(f"{counts['included']} studies are eligible for retrieval. A report requires a verified excerpt "
                "and at least one supported, cited claim.")

    titles = {paper.id: paper.title for paper in run.search.papers}
    with st.expander("Screening decision audit"):
        if policy == LLM_POLICY:
            st.caption("The LLM makes screening decisions against the eligibility criteria. "
                       "The rule-based baseline is available in Evaluation.")
        st.caption(f"Policy · {policy}")
        has_legacy_rules = any(item.rule is not None for item in run.screening.decisions)
        st.dataframe([
            {"Paper ID": d.paper_id, "Title": titles[d.paper_id],
             **({"Historical Rule": d.rule} if has_legacy_rules else {}), "AI recommendation": d.llm,
             "LLM confidence": d.llm_confidence, "Screening assessment": d.screening_reason or d.reason,
             "Final decision": "unresolved" if d.final == "uncertain" else d.final,
             "Decided by": d.decided_by, "Human reason": d.reason if d.decided_by == "human" else "",
             "Submitted excerpt": d.quote, "Excerpt verified": d.quote_verified}
            for d in run.screening.decisions
        ], hide_index=True, width="stretch")
        history = [
            {"Paper ID": item.paper_id, **change.model_dump(mode="json")}
            for item in run.screening.decisions for change in item.review_history
        ]
        if history:
            st.caption("Human decision history")
            st.dataframe(history, hide_index=True, width="stretch")


def review_page():
    st.title("Multi-Agent SLR")
    st.caption("Research planning, source screening and evidence-linked synthesis")
    run = select_review()
    st.sidebar.markdown("### Review configuration")
    mode = st.sidebar.radio("Execution mode", list(MODE_LABELS), format_func=MODE_LABELS.get,
                            help="Automatic withholds uncertain records and continues with eligible studies. "
                                 "Human-in-the-Loop adds a checkpoint to review or override decisions.")
    provider = st.sidebar.selectbox("LLM provider", ["ollama", "groq"], index=1 if settings.provider == "groq" else 0)
    per_source = st.sidebar.slider("Records per source", 1, 15, 4)
    with st.sidebar.expander("Review protocol"):
        inclusion = st.text_area("Inclusion criteria", "Primary research relevant to the topic.")
        exclusion = st.text_area("Exclusion criteria", "Exclude out-of-scope work and records without primary research.")
        retrieval = st.segmented_control("Retrieval", ["classical", "agentic"], default="agentic")
        documents = mode == "human_in_the_loop" and st.checkbox("Pause to add full-text PDFs")
        revisions = st.slider("Maximum quality revisions", 0, 2, 1)

    if run:
        with st.chat_message("user"):
            st.write(run.config.topic)
        with st.chat_message("assistant"):
            st.write(f"Review status · **{run.status.replace('_', ' ')}**")
            if run.error:
                st.error(run.error)
            show_review_progress(run)
            if run.rag and run.rag.corpus:
                with st.expander("Evidence retrieval audit"):
                    corpus = run.rag.corpus
                    st.write(f"Included studies with abstracts: {corpus.included_abstracts}. "
                             f"Corpus: {corpus.abstract_chunks} abstract and {corpus.full_text_chunks} PDF chunks. "
                             f"Verified excerpts: {len(run.rag.evidence)}.")
                    if corpus.missing_text_paper_ids:
                        st.caption("No usable text for " + ", ".join(corpus.missing_text_paper_ids))
                    for item in run.rag.retrieval:
                        st.caption(f"{item.rq_id} · {item.query}")
                        st.write({"Retrieved chunks": item.ranks, **item.extraction.model_dump(mode="json")})
            if run.handoffs:
                st.dataframe([{"From": h.source, "To": h.target, "Status": h.status,
                               "Revision budget left": h.budget_left} for h in run.handoffs],
                             hide_index=True, width="stretch")
            if run.status == "awaiting_screening":
                screening_ui(run)
            elif run.status == "awaiting_documents":
                upload_full_text(run)
                if st.button("Continue to evidence retrieval", type="primary"):
                    run_action(lambda: supervisor.finish_documents(run))
            elif run.status == "awaiting_claims":
                quality_ui(run)
            elif run.status == "running":
                if st.button("Continue review", type="primary"):
                    run_action(lambda: supervisor.advance(run))
            elif run.status == "failed":
                if st.button("Retry failed stage", type="primary"):
                    run_action(lambda: supervisor.retry(run))
            elif run.can_retry_retrieval():
                if st.button("Retry evidence retrieval", type="primary"):
                    run_action(lambda: supervisor.retry_retrieval(run))
            elif run.status == "complete":
                md = markdown(run)
                st.download_button("Markdown report", md, "literature-review.md", "text/markdown")
                st.download_button("PDF report", pdf(run), "literature-review.pdf", "application/pdf")
                st.markdown(md)

    if topic := st.chat_input("Enter a research topic to start a review"):
        def start():
            config = ReviewConfig(topic=topic.strip(), provider=provider, per_source=per_source, inclusion=inclusion,
                                  exclusion=exclusion, retrieval=retrieval or "agentic", pause_for_documents=documents,
                                  revision_budget=revisions, execution_mode=mode)
            result = supervisor.start(config)
            st.session_state.review_id = result.id
            st.session_state.pop("selected_review", None)
        run_action(start)


def downloads(payload, name):
    left, right = st.columns(2)
    left.download_button("Download JSON", json.dumps(payload, ensure_ascii=False, indent=2),
                         f"{name}.json", "application/json", key=f"{name}-json")
    right.download_button("Download CSV", to_csv(payload), f"{name}.csv", "text/csv", key=f"{name}-csv")


def evaluation_page():
    st.title("Evaluation")
    st.caption("Observed execution, independent labels and reproducible paired experiments")
    run = select_review()
    summary_tab, experiment_tab = st.tabs(["Review metrics", "Paired experiments"])
    with summary_tab:
        if run is None:
            st.info("Select a saved review to see execution metrics.")
        else:
            with st.expander("Independent reference labels"):
                st.caption("Upload adjudicated screening labels from an independent reviewer. "
                           "Use paper_id, label, annotator and protocol columns. "
                           "Retrieval labels map each RQ to its relevant chunk IDs.")
                labels = st.file_uploader("Screening CSV", type=["csv"])
                relevance_file = st.file_uploader("Retrieval relevance JSON", type=["json"])
                annotations = relevance = None
                try:
                    if labels:
                        annotations = load_annotations(labels.getvalue().decode("utf-8-sig"))
                    if relevance_file:
                        relevance = json.loads(relevance_file.getvalue())
                        if not isinstance(relevance, dict) or any(not isinstance(v, list) or
                                any(not isinstance(x, str) for x in v) for v in relevance.values()):
                            raise ValueError("Relevance JSON must map RQ IDs to lists of chunk IDs.")
                except (ValueError, UnicodeError) as exc:
                    annotations = relevance = None
                    st.error(str(exc))
            metric = review_metrics(run, annotations, relevance)
            for column, key in zip(st.columns(6), ("discovered", "deduplicated", "screened", "included", "excluded", "unresolved")):
                column.metric(key.title(), metric["flow"][key])
            st.subheader("Execution and usage")
            st.json(metric["overall"], expanded=False)
            st.dataframe(metric["events_by_agent"], hide_index=True, width="stretch")
            with st.expander("Planner, search and writing checks"):
                st.json({key: metric[key] for key in ("planner", "search", "planning_execution")})
            st.subheader("Screening evaluation")
            if annotations and metric["screening"]:
                rows = [{"decision": key, **value} for key, value in metric["screening"].items() if value]
                st.dataframe(rows, hide_index=True)
                for row in rows:
                    st.caption(f"{row['decision'].title()} confusion matrix · independent labels")
                    st.table([{"Reference": "Include", "Predicted include": row["tp"], "Predicted exclude": row["fn"]},
                              {"Reference": "Exclude", "Predicted include": row["fp"], "Predicted exclude": row["tn"]}])
            else:
                st.info("Precision, recall, F1 and confusion matrices require independent reference labels.")
            st.subheader("Retrieval quality")
            st.dataframe(metric["retrieval"], hide_index=True, width="stretch")
            st.subheader("Quality before and after revision")
            rows = [{k: r[k] for k in ("revision", "citation_validity", "lexical_support", "automated_score",
                                       "question_coverage", "detected_unsupported", "uncertain")} for r in metric["quality"]]
            st.dataframe(rows, hide_index=True, width="stretch")
            if metric["human_claim_judgments"]:
                st.caption("Human scientific judgments")
                st.dataframe(metric["human_claim_judgments"], hide_index=True, width="stretch")
            downloads(metric, f"evaluation-{run.id[:8]}")

    with experiment_tab:
        key = st.selectbox("Experiment", list(BENCHMARKS), format_func=lambda k: BENCHMARKS[k])
        st.caption("A, C and D use supplied course artifacts. B uses the configured live LLM on a frozen snapshot. "
                   "A–D record the same inputs for both arms and retain configuration and logs.")
        independent = st.file_uploader("Independent labels for Experiment B", type=["csv"]) if key == "b" else None
        if st.button("Run paired benchmark", type="primary"):
            try:
                with st.spinner("Running both arms…"):
                    labels = load_annotations(independent.getvalue().decode("utf-8-sig")) if independent else None
                    path, _ = run_benchmark(key, settings, labels)
                st.success(f"Saved {path.name}")
            except (GatewayError, ValueError) as exc:
                st.error(str(exc))
        root = settings.experiment_dir / "runs"
        saved = sorted(root.glob("*/metadata.json"), reverse=True)
        selected = st.selectbox("Saved comparison", [None, *saved], format_func=lambda p: p.parent.name if p else "Select run")
        if selected:
            metadata = json.loads(selected.read_text(encoding="utf-8"))
            outputs = json.loads((selected.parent / "outputs.json").read_text(encoding="utf-8"))
            st.subheader(metadata["title"])
            st.caption(metadata["conditions"])
            if metadata["benchmark"] == "c":
                st.dataframe([{"case": case, "arm": arm, **{k: v for k, v in value.items() if k != "trace"}}
                              for case, arms in outputs.items() for arm, value in arms.items()], hide_index=True)
            else:
                st.json(outputs, expanded=2)
            with st.expander("Configuration and execution conditions"):
                st.json(metadata)
            downloads({"metadata": metadata, "outputs": outputs}, f"benchmark-{selected.parent.name}")


st.navigation([
    st.Page(review_page, title="Review workspace", icon=":material/menu_book:", default=True),
    st.Page(evaluation_page, title="Evaluation", icon=":material/monitoring:", url_path="evaluation"),
]).run()
