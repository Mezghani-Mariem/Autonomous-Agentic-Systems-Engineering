# Observed validation

Validated on 20 November 2026. The original TD01–TD08 folders were retained as course evidence.

## Application and container

- The controlled suite passed locally and in the Compose test container. Docker selected 19 controlled tests and deselected the five live tests. The suite covered schemas, persistence, model/cache accounting, HTTP 429, malformed questions, missing abstracts, both human review checkpoints, unsupported citations, exhausted budgets, page provenance and Streamlit topic-to-export behavior.
- Docker Compose built and started the service with a named persistent volume. The container reached Healthy, the host health endpoint returned HTTP 200, and the Streamlit and SQLite checks passed. After a container restart, the completed live review reloaded from the volume and exported to PDF. The container also reached the configured Ollama endpoint and found qwen2.5:7b.
- The Render Blueprint is configured for a single Web Service with a persistent disk. Cloud startup and cloud endpoint checks remain unverified. See [Deployment](DEPLOYMENT.md) and the [Render Blueprint reference](https://render.com/docs/blueprint-spec).

## Live checks

| Service | Observed result |
| --- | --- |
| OpenAlex | Successful works retrieval. |
| Crossref | Successful works retrieval. |
| Semantic Scholar | HTTP 429 during the smoke check and live review. Search retained the failures and continued with the other sources. |
| Ollama with qwen2.5:7b | Structured-output smoke test passed after starting the installed service. Real review and Experiment B completed. |
| Groq with the configured credential | HTTP 401 during the smoke check. Successful live Groq inference remains unverified. |

The first Ollama integration attempt exposed variant source labels. The planner now normalizes the known source names and can repair a malformed structured protocol within one additional attempt. The subsequent live run completed with two retrieved and included papers, no duplicates, eight measured model calls, one cached model response, and one retained claim cited to an abstract. The abstract-first report leaves two research questions without retained claims and identifies the missing full texts. It reports automated evidence checks, with zero human interventions in this run.

- [Live run and trace](experiments/live/32cb856375074c8da4cd9b675ea722e2/run.json) · [Exact model prompts](experiments/live/32cb856375074c8da4cd9b675ea722e2/prompts.json)
- [Literature review in Markdown](output/literature-review.md) · [Literature review in PDF](output/pdf/literature-review.pdf)

## Benchmarks

| Experiment | Observed result |
| --- | --- |
| A · Fixed vs ReAct search | Each arm returned three unique items with the TD03 simulated OpenAlex HTTP 429. The ReAct policy attempted Crossref immediately after observing the failure. [Outputs and trace](experiments/runs/2026-11-20T11-55-49-a-12e64f727f/outputs.json) |
| B · Rule vs LLM screening | Nine live Ollama calls succeeded against the frozen snapshot. The rule policy routed six cases to review and the LLM policy routed ten. Independent ground-truth labels were unavailable. Precision, recall, F1 and confusion matrix remained unset. [Outputs](experiments/runs/2026-11-20T11-57-38-b-1109e9b08f/outputs.json) · [Events](experiments/runs/2026-11-20T11-57-38-b-1109e9b08f/events.json) |
| C · Classical vs Agentic RAG | Precision@1 and recall stayed at zero for Q1 and rose from zero to one for Q2 in the adaptive lexical run. Q3 scored one in both. The adaptive arm used one additional retrieval for Q1 and Q2. These are three fixed classroom cases. [Outputs](experiments/runs/2026-11-20T11-55-49-c-a4bd19b5e3/outputs.json) |
| D · Fixed pipeline vs supervisor | The fixed replay escalated. The supervisor finished after replaying the supplied revision. The deterministic quality score changed from 93.3% to 100% for that artifact. [Outputs and handoffs](experiments/runs/2026-11-20T11-55-49-d-3f4df3caad/outputs.json) |

The benchmark directories preserve resolved settings, inputs, outputs, checksums and event logs. [Protocol and limitations](EVALUATION.md)

## Screening execution modes

The expanded Docker suite passed **32 controlled tests**. It covers mixed screening decisions, missing abstracts, screening disagreement, low confidence, ungrounded excerpts, empty eligibility, retry from the saved screening checkpoint, and withholding unsupported claims. Streamlit's test submitted a three-character reason in the second of two review forms and verified that the reason and decision persisted for the correct paper. The rebuilt app returned HTTP 200 and reopened an existing paused review on its persistent volume.

Two Automatic reviews used live Ollama with qwen2.5:7b and disabled the response cache. OpenAlex and Crossref returned records on both runs. Semantic Scholar returned HTTP 429 on both runs.

| Live run | Screening outcome | Report outcome |
| --- | --- | --- |
| Two results per source | Four included, zero excluded, zero unresolved | One cited claim and 11 measured LLM calls. Markdown and PDF exports verified. [Trace](experiments/live/771da1b5a72840bbb78fc09548aad222/run.json) · [Report](experiments/live/771da1b5a72840bbb78fc09548aad222/literature-review.md) |
| Four results per source | Seven included, zero excluded, one unresolved | Completed with zero human interventions. The unresolved record stayed outside retrieval. After one quality revision, one claim was retained and one was withheld. The evidence and remaining gaps are disclosed in the report. [Trace](experiments/live/86eed70ed90f4aff82f0d3f60aa570d6/run.json) · [Metrics](experiments/live/86eed70ed90f4aff82f0d3f60aa570d6/metrics.json) · [Report](experiments/live/86eed70ed90f4aff82f0d3f60aa570d6/literature-review.md) |

## LLM screening policy

The updated Compose suite passed **39 controlled tests**. These cover structured-output validation, the evidence gate, mixed screening outcomes, the independent rule baseline, human overrides and their history, no eligible studies, saved-run recovery, and both export formats. The Streamlit container returned HTTP 200 and loaded earlier reviews from the persistent volume.

An uncached end-to-end test in the Docker test container passed with Ollama `qwen2.5:7b`, ReAct search, agentic RAG and the `llm-evidence-v1` policy. OpenAlex and Crossref responded. Semantic Scholar returned HTTP 429 on both attempts. Of eight unique records, the AI included four and excluded one. Three remained uncertain due to one missing abstract and two excerpts that failed grounding. All three stayed outside retrieval. The run completed without human intervention and exported a review with one cited abstract-backed claim. No full texts were available and two research questions had no retained claims. The claim received automated checks only. [Markdown](experiments/live/556c086dfb074f8d9d95eb9c4a0ea3bf/literature-review.md) · [PDF](experiments/live/556c086dfb074f8d9d95eb9c4a0ea3bf/literature-review.pdf) · [Run](experiments/live/556c086dfb074f8d9d95eb9c4a0ea3bf/run.json) · [Metrics](experiments/live/556c086dfb074f8d9d95eb9c4a0ea3bf/metrics.json) · [Prompts](experiments/live/556c086dfb074f8d9d95eb9c4a0ea3bf/prompts.json)

An earlier live attempt during implementation had five AI inclusions, one AI exclusion and two uncertain records. Retrieval found no verified passages, so the workflow returned insufficient evidence without exporting a report. [Run](experiments/live/dc7656060f514d60b875d78bb37e4cd5/run.json)

## Abstract-first evidence selection

The saved failing review `278d886ab8a94ef6bc17229cb4b69fe6` passed six included studies with usable API abstracts to RAG. No PDF was supplied. The corpus had 16 chunks, and the retriever selected three chunks for each of the three questions. A read-only replay of the original cached responses showed that Ollama returned an empty list for RQ1 and RQ3. For RQ2 it returned two proposals with the right paper and chunk identifiers but used the `[PAPER …] [CHUNK …] [PAGE 1]` headers as the supporting quotations. Neither header appeared in the source text, so exact verification rejected both. The saved workflow stopped before Writing and Quality.

The new selector returns source chunk IDs paired with offered excerpt IDs. The application checks the pairing and verifies the exact excerpt against the canonical chunk. It keeps the source record ID for an abstract and an actual PDF page for full text. Empty selections, invalid responses and rejected IDs are visible by research question. Saved reviews can retry the evidence stage with the same screened studies.

**Controlled tests.** Docker Compose ran 49 controlled tests. All 49 passed and six live tests were deselected (4.73 seconds). A separate Windows run of the evidence, execution-mode, evaluation and foundation tests passed all 38 selected tests (5.59 seconds). The rebuilt Streamlit app returned HTTP 200 from its health endpoint.

**Uncached live test.** The Docker test used Ollama `qwen2.5:7b` and the topic “How are large language models evaluated for title and abstract screening in systematic literature reviews?” The test passed in 145.88 seconds, with 54 other tests deselected. OpenAlex and Crossref succeeded. Semantic Scholar was rate limited on two attempts. Screening yielded four included papers and four unresolved records. All four included papers had usable abstracts and none had supplied full text. The corpus held 11 abstract chunks, of which six unique chunks were retrieved across seven selections. The selector verified nine excerpts across the three questions. Writing and Quality executed twice with one bounded revision. The report retained five claims citing three bibliographic records and withheld one unsupported claim. Markdown and PDF exports passed the reference and provenance checks. [Markdown](experiments/live/ed7ecbba7aee4a5288940f6315920e9c/literature-review.md) · [PDF](experiments/live/ed7ecbba7aee4a5288940f6315920e9c/literature-review.pdf) · [Run](experiments/live/ed7ecbba7aee4a5288940f6315920e9c/run.json) · [Metrics](experiments/live/ed7ecbba7aee4a5288940f6315920e9c/metrics.json)

The first replay of the original saved review verified nine excerpts while preserving its search and screening. Quality judged three claims supported in the first draft. The revision dropped all three, and Quality correctly withheld the two replacements. Writing now retains previously supported claims when their cited evidence is still available, and Quality judges those claims again. The final controlled suite added a regression test for an empty correction and passed all 50 controlled tests, with six live tests deselected (3.77 seconds). [First replay](experiments/live/replay-278d886a/run.json)

**Final replay of the original review.** The stored search and screening artifacts were identical to those in the original run. RAG selected nine chunks, verified nine passages and rejected one selection whose candidate was paired with the wrong chunk. Writing and Quality completed one revision. The final report kept the three claims that passed both Quality checks, cited three bibliographic records and withheld one unsupported replacement. Both formats contain a bibliography and the abstract-first disclosure. The PDF has three pages. [Markdown](experiments/live/replay-278d886a-final/literature-review.md) · [PDF](experiments/live/replay-278d886a-final/literature-review.pdf) · [Run](experiments/live/replay-278d886a-final/run.json) · [Replay metadata](experiments/live/replay-278d886a-final/metadata.json)

**Final uncached test.** The final image passed the same live Ollama test in 168.24 seconds, with 55 other tests deselected. It screened eight unique records. Three included studies had usable abstracts and five records remained unresolved. RAG retrieved nine chunks across the three questions (five unique chunks) and verified ten excerpts. Writing and Quality each executed twice. After one revision, the report retained four automatically supported claims citing one bibliographic record. Markdown and the three-page PDF both contain the bibliography and abstract-only disclosure. OpenAlex and Crossref responded and Semantic Scholar returned HTTP 429 on both attempts. No full text or human scientific judgments were supplied. [Markdown](experiments/live/000cca74b20344e4b0379398a98ae591/literature-review.md) · [PDF](experiments/live/000cca74b20344e4b0379398a98ae591/literature-review.pdf) · [Run](experiments/live/000cca74b20344e4b0379398a98ae591/run.json) · [Metrics](experiments/live/000cca74b20344e4b0379398a98ae591/metrics.json)

Files changed in this fix are `slr/models.py`, `slr/retrieval.py`, `slr/course/planning_models.py`, `slr/synthesis.py`, `slr/supervisor.py`, `slr/report.py`, `app.py`, `evaluation/metrics.py`, `tests/conftest.py`, `tests/test_evidence.py`, `tests/test_execution_modes.py`, `tests/test_live.py`, `tests/test_review.py`, `README.md`, `COURSE_CODE.md` and `VALIDATION.md`. All 431 catalogued TD source records, including archived source files, matched their earlier checksums.
