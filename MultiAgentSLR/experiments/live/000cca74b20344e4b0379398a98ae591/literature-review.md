# Literature review

## How are large language models evaluated for title and abstract screening in systematic literature reviews?

> Evidence scope: abstract-first. Full text was unavailable or not supplied for 3 of 3 included records.

Abstract-based findings are limited to what those abstracts report. Bibliographic searches and automated checks support a bounded research workflow.

Review ID 000cca74b20344e4b0379398a98ae591 | Started 2026-11-20

## Search and selection

Inclusion criteria: Primary research relevant to the topic.

Exclusion criteria: Exclude out-of-scope work and records without primary research.

The result limit was 4 per source. Observed 8 records, removed 0 duplicates, screened 8, included 3, excluded 0, and left 5 unresolved.

Execution mode: automatic. The policy automatically included 3 and excluded 0 records.

AI screening used the declared eligibility criteria. Definite decisions required an available abstract, a justification, a grounded excerpt longer than one word, no review flag, and confidence of at least 0.80. AI decisions are recorded separately from reviewer decisions.

openalex (success): large language models evaluation title abstract systematic review

semantic\_scholar (rate\_limited): large language models evaluation title abstract systematic review

crossref (success): large language models evaluation title abstract systematic review

### Unresolved screening records

These records were withheld from retrieval and may change the findings if reviewed.

P-ec09b3e73f8489ef · Evaluating Large Language Models for Radiology Systematic Review Title and Abstract Screening. Abstract unavailable. A reviewer can assess the record or supply the full text.

P-39e515cd23467ff5 · Cost-Efficient Large Language Model-Assisted Title and Abstract Screening for Systematic Reviews: Method Evaluation and Validation. No grounded excerpt was supplied. The title and abstract discuss the use of large language models (LLMs) for automating the title and abstract screening phase in systematic reviews, which is directly relevant to the topic of evaluating LLMs for this task. The study presents a methodological evaluation and validation of multiple LLM-based workflows, providing empirical evidence on their performance.

P-467c8a257916fffe · Title and abstract screening for systematic reviews with Jev, a System One model: comparison with generative large language models. No grounded excerpt was supplied. The study evaluates a non-generative model (Jev) for title and abstract screening in systematic reviews, which is relevant to the topic of evaluating large language models. It compares Jev with generative LLMs on specific datasets related to bipolar disorder treatments, providing empirical evidence.

P-5222785d1a599b1d · Explainable Artificial Intelligence for Large Language Models: A Systematic Review and Evaluation Framework. No grounded excerpt was supplied. The title and abstract focus on explainable artificial intelligence techniques for large language models, which is not directly related to evaluating LLMs in the context of systematic literature reviews as specified in the inclusion criteria.

P-5e8fa8d1ab83a6eb · Using full agreement across multiple large language models for title-and-abstract screening in systematic reviews: a proof-of-concept. No grounded excerpt was supplied. The title and abstract clearly indicate that this paper is a primary research study relevant to the topic of evaluating large language models for title-and-abstract screening in systematic literature reviews. The content discusses methods, results, and conclusions related to the use of multiple LLMs for this specific task.

## Synthesis

Search mode: react. Screening policy: llm-evidence-v1. Retrieval: agentic. Quality revisions: 1.

Model calls recorded for ollama:qwen2.5:7b.

### RQ1. Quels critères et méthodes sont utilisés pour l'évaluation des modèles de langage lors du tri par titre et résumé dans les revues systématiques ?

Retrieval did not cover these configured facets: model\_type.

Human decisions served as the reference standard for evaluating language models in systematic reviews. [1] (C1, automated evidence check)

Prompt decisions showed high consistency and minimal false exclusions, meeting screening performance benchmarks. [1] (C2, automated evidence check)

### RQ2. Comment la qualité et l'efficacité des processus d'évaluation des titres et des résumés varient-elles selon différents types de modèles de langage (par exemple, Génération de texte, Compréhension du langage naturel) ?

Retrieval did not cover these configured facets: model\_type.

A study compared the performance of an LLM (GPT-4o) with human reviewers in title and abstract screening. [1] (C3, automated evidence check)

Simulated workload reductions of 65-85% were observed when using language models for title and abstract screening. [1] (C5, automated evidence check)

### RQ3. Quels sont les défis principaux rencontrés lors de l'évaluation des modèles de langage pour le tri par titre et résumé dans le contexte des revues systématiques ?

No supported claim was retained for this research question.

Retrieval did not cover these configured facets: common\_issues, solution\_proposals.

## Evidence and provenance

> E-f4b1c28ea2196a85 · [1] · abstract only via openalex (W4412582725) · abstract:P-955f95396b410f69\_c1 · “METHODS: Human decisions from an LSR on prodopaminergic interventions for anhedonia served as the reference standard.”

> E-2bf055616d6de7b8 · [1] · abstract only via openalex (W4412582725) · abstract:P-955f95396b410f69\_c2 · “Prompt decisions showed high consistency, with minimal false exclusions, satisfying established screening performance benchmarks for systematic reviews.”

> E-6ce76595659ce6f8 · [1] · abstract only via openalex (W4412582725) · abstract:P-955f95396b410f69\_c1 · “OBJECTIVE: The study evaluated the effectiveness of an LLM (GPT-4o) in title and abstract screening compared with human reviewers.”

> E-29b82e0e35a49faf · [1] · abstract only via openalex (W4412582725) · abstract:P-955f95396b410f69\_c2 · “Simulated workload reductions of 65-85% were observed.”

## References

[1] Ava Homiar, James Thomas, Edoardo Giuseppe Ostinelli, Jaycee Kennett, Claire Friedrich, Pim J. Cuijpers, Mathias Harrer, Stefan Leucht, Clara Miguel, Alessandro Rodolico, Yuki Kataoka, Tomohiro Takayama, Keisuke Yoshimura, Ryuhei So, Yasushi Tsujimoto, Yosuke Yamagishi, Shiro Takagi, Masatsugu Sakata, Djordje Basic, Eirini Karyotaki, Jennifer Potts, Georgia Salanti, Toshi A. Furukawa, Andrea Cipriani (2025). Development and evaluation of prompts for a large language model to screen titles and abstracts in a living systematic review. https://doi.org/10.1136/bmjment-2025-301762

Study ID P-955f95396b410f69. Source records: openalex:W4412582725.

## Limitations

Verified excerpts were available from 3 of 3 included records. Findings cover only the retained evidence.

The configured source and result limits constrain retrieval coverage. Automated support judgments and lexical overlap are screening aids. The supplied sources and any human adjudications should be checked for scientific interpretation.
