# Multi-Agent SLR

A Streamlit research workspace with six roles coordinated by a Python supervisor. Enter a topic in chat, review uncertain records or claims, and export the evidence-linked review as Markdown and PDF. SQLite persists runs and successful API and model responses. The Evaluation page exposes execution metrics and reproducible paired comparisons.

## Local setup

Run from this folder using Python 3.12. Install project dependencies in your own virtual environment.

    python -m pip install -r requirements-dev.txt
    python -m streamlit run app.py

Copy .env.example to .env. Set LLM_PROVIDER to ollama or groq.

- **Ollama** requires a reachable Ollama process with OLLAMA_MODEL loaded. Set OLLAMA_EMBEDDING_MODEL to an installed model such as nomic-embed-text if you want dense semantic retrieval. With no embedding model, adaptive retrieval uses missing-facet queries over the same TF-IDF corpus.
- **Groq** requires GROQ_API_KEY and a GROQ_MODEL supporting JSON mode. Groq supports chat and structured output here. Embeddings still use optional Ollama.
- **Search** uses OpenAlex, Semantic Scholar and Crossref. Set OPENALEX_API_KEY and SEMANTIC_SCHOLAR_API_KEY where available. Set CROSSREF_EMAIL to use Crossref's identified pool. Source failures remain visible and the review stops if every source fails. See [OpenAlex authentication](https://help.openalex.org/api/authentication/), [Semantic Scholar Academic Graph API](https://api.semanticscholar.org/api-docs), and [Crossref access](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication).
- **Storage** defaults to data/slr.sqlite3 locally. Set SLR_DATA_DIR and SLR_EXPERIMENT_DIR to choose the locations. Set SLR_CACHE_TTL_SECONDS=0 to bypass cache during a measurement. Token totals include calls with reported usage and exclude cache hits.
- **Access** can be restricted with SLR_ACCESS_TOKEN. A running instance and its stored reviews are shared by team members with that token.

## Review flow

Select **Execution mode** in the sidebar before starting a review. Saved reviews retain their mode.

- **Automatic** is the demonstration default. The TD04 LLM screener, using Ollama by default, decides against the declared eligibility criteria. A final include or exclude requires an abstract, a valid structured response, a justification, a grounded excerpt longer than one word, confidence of at least 0.80, and no review flag. The confidence is model-reported. Definite decisions are recorded as AI decisions. Missing abstracts, invalid responses, abstentions and weak evidence stay unresolved and outside retrieval.
- **Human-in-the-Loop** adds a screening checkpoint. Review unresolved records or override any recommendation, choose a decision, and save a reason. The audit keeps the original AI recommendation and all overrides. Select **Continue to evidence retrieval** to release the included set. Unresolved records stay outside retrieval. This mode also supports PDF collection and claim adjudication.

The rule-based TD04 baseline runs independently in **Evaluation → Experiment B**. New review runs do not use rule agreement or lexical screening signals. Saved runs retain the policy and decisions originally used. A review paused at screening can switch to Automatic while preserving its recorded decisions.

At least one included study is required to begin retrieval. A report requires a verified excerpt and at least one retained, supported claim with valid evidence references. Automatic mode withholds claims that still fail quality checks after the revision budget. Either mode returns **Insufficient evidence** when the relevant gate fails. Reports list unresolved records and their reasons separately from exclusions, disclose full-text gaps, and show which questions lack support. Automatic title and abstract screening is preliminary and may miss studies that need manual or full-text review.

1. **Research Planner** drafts and validates three research questions, repairs invalid text once, then generates database-specific search queries and evidence facets.
2. **Search Agent** applies the TD03 action contract and registry to an observation-driven ReAct policy. A failed or empty source prioritizes the remaining Crossref fallback. One bounded source action per index, plus transport retry for transient failures. DOI and title matching merge duplicate records with the native source IDs preserved. A fixed search baseline uses the same budget.
3. **Title/Abstract Screening** applies the LLM decision and deterministic validation. Its audit records the recommendation, confidence, excerpt, justification, final decision, and override history. Human-in-the-Loop can pause to associate lawfully obtained PDFs with retained records.
4. **RAG** uses the supplied PDF for a study when it contains extractable text and its API abstract otherwise. Classical RAG uses one retrieval. Agentic RAG uses TD06's facet and memory logic with a bounded follow-up search. Ollama selects chunk and excerpt IDs from a list of quoted source passages. Python copies the exact text and validates the IDs, source and location before the Writing Agent receives it. Abstracts carry their API record ID, with page numbers reserved for PDFs. The Evidence retrieval audit lists selected chunks, rejected or empty selections and verified excerpts. A saved review that stopped at retrieval can use **Retry evidence retrieval** to rerun that stage with its existing screening decisions.
5. **Writing Agent** validates and executes a plan against the evidence catalog. A step with insufficient evidence can be revised into a limitation. Claims cite only evidence IDs from the same question and pass through QualityAgent before export.
6. **Quality Agent** records citation validity, lexical scores and separate automated support judgments against cited excerpts. The supervisor routes bounded revision to retrieval or writing. Writing carries forward previously supported claims when their evidence remains available, and Quality checks them again. Human-in-the-Loop sends remaining flagged claims for adjudication. Unknown, missing or wrong-question citations require removal. Reports list only retained citations and disclose unavailable full text.

A review can be resumed from the saved review selector after an app restart. Version checks detect simultaneous updates from different sessions. The reference list is drawn from source metadata, and the evidence table carries the excerpt and its location. Coverage is bounded by the supplied queries, result limits and available text. The source-level arms and fixture benchmarks are documented in [Evaluation](EVALUATION.md).

## Commands

| Action | Command |
| --- | --- |
| Controlled suite | python -m pytest -m "not live" |
| Live smoke suite | Set SLR_RUN_LIVE=1, then run python -m pytest -m live |
| Test both providers | Set SLR_LIVE_PROVIDERS=ollama,groq for the live suite |
| Controlled benchmark set | python -m evaluation controlled |
| Single experiment | python -m evaluation a, b, c, or d (choose one letter) |
| Screening benchmark with independent labels | python -m evaluation b --annotations labels.csv |
| All four benchmarks | python -m evaluation all |
| Start a review from the terminal | python -m slr run "LLM-assisted screening in systematic literature reviews" --provider groq |
| Select human review in the terminal | python -m slr run "LLM-assisted screening in systematic literature reviews" --provider ollama --execution-mode human_in_the_loop |
| Inspect a saved state | python -m slr inspect RUN_ID |
| Export a completed state | python -m slr export RUN_ID --output output/example |

On PowerShell, set an environment variable for the current terminal with $env:SLR_RUN_LIVE = '1'. On a POSIX shell, use export SLR_RUN_LIVE=1. Live tests make real, bounded requests and may require valid keys, model availability and quotas. Real runs and reproducible model prompts can be saved under experiments/live with the opt-in --record-prompts flag.

To run the full, uncached Ollama validation with scholarly APIs, set SLR_RUN_LIVE=1 and SLR_RUN_LIVE_REVIEW=1, then run:

    python -m pytest -m live -k test_live_automatic_review_exports_referenced_report -s

This test writes a trace and metrics under experiments/live. It expects a referenced report on the chosen topic, so source availability and the evidence retrieved affect its outcome.

If an existing Windows pytest temporary directory has a different owner, use a fresh path:

    $testTemp = Join-Path ([System.IO.Path]::GetTempPath()) ('slr-' + [guid]::NewGuid().ToString('N'))
    python -m pytest -m "not live" -p no:cacheprovider --basetemp $testTemp

See [integration plan](INTEGRATION_PLAN.md), [course code provenance](COURSE_CODE.md), [evaluation protocol](EVALUATION.md), [deployment instructions](DEPLOYMENT.md) and [observed validation](VALIDATION.md).
