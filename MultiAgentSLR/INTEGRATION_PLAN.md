# Integration plan

1. Vendor the working TD primitives with source attribution. Add typed review artifacts, a SQLite cache and run store, and measured Ollama/Groq and bibliographic adapters. Test schema validation, rate limiting and cache behavior.
2. Connect research planning, ReAct search and title/abstract screening. Validate paper IDs at handoffs and persist the human review queue. Test automatic and human-resumed paths.
3. Connect classical and adaptive retrieval, Plan-and-Execute writing and claim quality checks. Bound feedback and revision, persist claim adjudications, and export referenced Markdown and PDF. Test the full workflow with controlled providers.
4. Add the Streamlit chat and Evaluation page. Run paired comparisons against the same inputs and budgets, retain reproducible experiment records, and calculate label-based metrics only when reference annotations are available.
5. Package one application container with persistent data and a health check. Run controlled tests locally and in Docker where available, run live smoke checks separately, and document deployment and observed results.

