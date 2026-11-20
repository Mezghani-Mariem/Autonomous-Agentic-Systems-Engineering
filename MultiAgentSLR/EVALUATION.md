# Evaluation and reproducibility

## Reference data

| Dataset in experiments/datasets | Origin | Purpose |
| --- | --- | --- |
| search_catalog.json | TD03 data/papers.json | Pedagogical catalog. Experiment A injects the OpenAlex HTTP 429 described in TD03. Identifiers in this catalog are examples only. |
| screening_snapshot.json | TD04 artifacts/search_results.json | Frozen historical search snapshot of actual metadata with documented source failures. Supplies identical records to both arms in B and the search side of D. |
| document_manifest.json, extracted_pages.json, retrieval_cases.json | TD06 artifacts | The fixed TD06 corpus and labeled passage IDs. The source material supplies annotations but does not identify annotators or report their agreement. |
| synthesis_evidence.json | TD07 artifacts/td06_evidence.json | Classroom evidence catalog used by D. |
| writing_artifact.json | TD08 artifacts/td07_writing_artifact.json | Draft with the unsupported A5 example and supplied correction used by D. |

The workspace contains no independently annotated screening dataset. A team can create one by fixing the criteria, blinding reviewers to model predictions, having them label records independently, and adjudicating disagreement before evaluation. Import adjudicated CSV rows keyed by canonical paper_id with label (include or exclude), annotator and protocol. Use the exact paper IDs emitted by the app or Experiment B. Application decisions, including operational human arbitration, are never loaded automatically as benchmark labels. Record annotation protocol and agreement separately. Precision, recall, F1 and confusion-matrix counts stay unavailable in the absence of reference labels.

## Paired comparisons

- **A · Fixed versus ReAct search.** Both arms use the same four-record catalog, query, per-source cap and simulated OpenAlex throttling. Both can attempt all three sources. Compare the trace, order, API outcome categories and duplicate counts. This is a flow test on a small classroom catalog.
- **B · Rule versus LLM screening.** Both arms see the same frozen records and topic. The independent rule baseline uses lexical signals. The LLM uses eligibility criteria with one structured decision per usable abstract and bounded transport retry. The artifact records labels if supplied, per-paper predictions, resolved decisions, prompts and actual provider events. Missing or uncertain outputs remain abstentions.
- **C · Classical versus Agentic RAG.** Build the TD06 corpus with its original 1,000-character chunks, no overlap, and the original per-case k. Both arms share a maximum allowance of two retrieval calls, and the classical arm uses one by design. The active memory and final top-k are capped equally. Labels are used after ranking. The test does not use TD06's annotation-derived embedding vectors. Lexical adaptation runs without a provider. An optional configured Ollama embedding model can be used for adaptive retrieval. Any lexical fallback appears in the logged method.
- **D · Fixed pipeline versus Quality-Driven Supervisor.** Both replay the supplied TD08 draft, evidence, deterministic rules and same transition budget. The supervised writer can use the correction already provided by the course. Report score changes and routing, not model-generated repair efficacy. The application suite separately tests the integrated supervisor using injected responses.

Each successful benchmark writes inputs.json, outputs.json, metadata.json, events.json and prompts.json in experiments/runs. Metadata includes input and implementation checksums, effective configuration, runtime versions, time, model and cache policy. A and D have deterministic decisions and therefore no LLM prompts. C records cases, exact query traces, and the optional embedding identity. B stores exact model prompt messages and schemas. Review examples and benchmarking logs may contain excerpts and reviewer text. Use the team storage policy for sharing them.

## Metrics

| Component | Measures |
| --- | --- |
| Research Planner | Count of valid RQs, nonempty per-source query contracts, plan and RQ coverage, repairs. These are software checks, separately from topic completeness. |
| Search | Discovered usable rows, unique papers, duplicates, per-tool attempts and outcome, latency, stop reason. API attempts, retry and cache counts appear in measured events. |
| Screening | Precision TP/(TP+FP), recall TP/(TP+FN), F1, confusion matrix and false-negative rate FN/(FN+TP). These are conditional on decided, independently labeled records. Matched labels, abstentions and positive abstentions are reported alongside them. |
| Retrieval | Precision@k uses hits divided by requested k. Precision among returned items also preserves the TD05 denominator. Recall uses hits divided by relevant IDs. Facet coverage uses keyword checks and the logged number of tool calls measures retrieval cost. Missing labels produce null precision and recall. |
| Writing plan | Validity, dependency order, RQ and section coverage, executed steps, retries/replans and action counts. |
| Quality | Citation-contract validity, lexical overlap score, individual automated support judgments, unsupported and uncertain counts and revision results. Human claim decisions are recorded separately. |
| Overall | Task state, elapsed and active time, model/API/embedding calls, cache hits, available token counts, failures, retries and human interventions. |

A passing controlled run establishes its tested behavior. It cannot estimate scientific accuracy on unseen papers or reliability of a live service. Search uses bounded result lists, abstracts may omit decisive information, and automated support scores and human scientific judgments have different purposes.
