# Course code provenance

The application is self-contained inside this folder. The course trees remain the original teaching snapshots.

| Source TD | Local copies under slr/course | Runtime use |
| --- | --- | --- |
| TD01 | research_questions | Zero-shot message assembly and one-call RQ generation |
| TD02 | search_plan | RQ validation, one repair, and explicit escalation |
| TD03 | contracts, tools, runtime, react_agent, policies, workflow | Search contracts, allowlisting, observations and both policies' execution paths |
| TD04 | artifacts, screening_agent, llm_screening_agent | Structured LLM screening in reviews and an independent rule baseline in Evaluation |
| TD06, carrying TD05 | rag_models, rag_pipeline, pdf_loader, agentic_rag_models, agentic_rag | Chunking, TF-IDF, cosine retrieval, facets, local PDF text, adaptive state and exact quote verification |
| TD07 | planning_models, plan_and_execute | Plan validation, execution and bounded replanning |
| TD08 | quality_models, quality_agent, orchestrator | Handoff contract, deterministic scores and classroom orchestration benchmark |

The TD04 copies use local package imports. The application copy of the LLM screener also validates confidence input and asks the model to connect its excerpt and justification to an eligibility criterion. Production retrieval reuses TD05 chunking for PDFs, TF-IDF and semantic retrieval and TD06's bounded adaptive state. Its source-aware excerpt selector and exact verifier are in `slr/retrieval.py`. TD07's application copy supports an evidence-free limitation step and page-free abstract citations, with evidence still required for synthesis. The TD03 backend selection and normalization are wrapped with measured clients and merged-source provenance. The integrated planner uses TD02's validation and repair rather than its topic-specific template queries. The complete TD07 code is the source of the planner copy.

Files under experiments/datasets are exact copies of the course inputs listed in [Evaluation](EVALUATION.md). The production supervisor never reads them.
