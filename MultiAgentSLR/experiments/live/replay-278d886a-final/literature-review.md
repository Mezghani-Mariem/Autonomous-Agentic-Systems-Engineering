# Literature review

## How are large language models evaluated for title and abstract screening in systematic literature reviews?

> Evidence scope: abstract-first. Full text was unavailable or not supplied for 6 of 6 included records.

Abstract-based findings are limited to what those abstracts report. Bibliographic searches and automated checks support a bounded research workflow.

Review ID 65af34fdf89a45d4a6b55fc31e0c82de | Started 2026-11-20

## Search and selection

Inclusion criteria: Primary research relevant to the topic.

Exclusion criteria: Exclude out-of-scope work and records without primary research.

The result limit was 4 per source. Observed 12 records, removed 2 duplicates, screened 10, included 6, excluded 0, and left 4 unresolved.

Execution mode: automatic. The policy automatically included 6 and excluded 0 records.

AI screening used the declared eligibility criteria. Definite decisions required an available abstract, a justification, a grounded excerpt longer than one word, no review flag, and confidence of at least 0.80. AI decisions are recorded separately from reviewer decisions.

openalex (success): large language models evaluation title abstract systematic review

semantic\_scholar (success): large language models evaluation title abstract systematic review

crossref (success): large language models evaluation title abstract systematic review

### Unresolved screening records

These records were withheld from retrieval and may change the findings if reviewed.

P-ec09b3e73f8489ef · Evaluating Large Language Models for Radiology Systematic Review Title and Abstract Screening. Abstract unavailable. A reviewer can assess the record or supply the full text.

P-39e515cd23467ff5 · Cost-Efficient Large Language Model-Assisted Title and Abstract Screening for Systematic Reviews: Method Evaluation and Validation. No grounded excerpt was supplied. The title and abstract discuss the use of large language models (LLMs) for automating the title and abstract screening phase in systematic reviews, which is directly relevant to the topic. The study evaluates multiple LLM-based workflows on eight independent SR datasets, focusing on EMF and non-EMF research domains, providing a structured approach that aligns with primary research.

P-5222785d1a599b1d · Explainable Artificial Intelligence for Large Language Models: A Systematic Review and Evaluation Framework. No grounded excerpt was supplied. The title and abstract focus on explainable artificial intelligence techniques for large language models, which is not directly related to evaluating LLMs in the context of systematic literature reviews as specified in the inclusion criteria.

P-5e8fa8d1ab83a6eb · Using full agreement across multiple large language models for title-and-abstract screening in systematic reviews: a proof-of-concept. No grounded excerpt was supplied. The title and abstract clearly indicate that this paper is a primary research study relevant to the topic of evaluating large language models for title-and-abstract screening in systematic literature reviews. The content discusses methods, results, and conclusions related to the use of multiple LLMs for this specific task.

## Synthesis

Search mode: react. Screening policy: llm-evidence-v1. Retrieval: agentic. Quality revisions: 1.

Model calls recorded for ollama:qwen2.5:7b.

Quality review withheld 1 claim with insufficient support or invalid citations at final quality review.

### RQ1. Quels critères et méthodes sont utilisés pour l'évaluation des modèles de langage lors du tri par titre et résumé dans les revues systématiques ?

Human decisions from an LSR on prodopaminergic interventions for anhedonia served as the reference standard. [1] (C1, automated evidence check)

### RQ2. Comment la qualité et l'efficacité des processus d'évaluation des titres et des résumés varient-elles selon différents types de modèles de langage (par exemple, GPT, BERT) et de revues systématiques ?

Jev Choice achieved sensitivity and specificity similar to or higher than those of GPT-5 mini and GPT-6 Astra, while API charges per 1000 records were US$0.043 for Jev, US$0.57 for GPT-5 mini, and US$7.39 for GPT-6 Astra. [2] (C4, automated evidence check)

### RQ3. Quels sont les défis principaux rencontrés lors de l'évaluation des modèles de langage pour le tri par titre et résumé dans le contexte des revues systématiques, et comment ces défis peuvent-ils être surmontés ?

Retrieval did not cover these configured facets: evaluation\_challenges, solution\_strategies.

Performance varies across models and is sensitive to evaluation metrics, particularly in low-prevalence screening contexts. [3] (C5, automated evidence check)

## Evidence and provenance

> E-f4b1c28ea2196a85 · [1] · abstract only via openalex (W4412582725) · abstract:P-955f95396b410f69\_c1 · “METHODS: Human decisions from an LSR on prodopaminergic interventions for anhedonia served as the reference standard.”

> E-4e7df2a513d99fb3 · [2] · abstract only via crossref (10.3390/info17111160) · abstract:P-29185e5a55fb2217\_c1 · “Jev Choice achieved sensitivity and specificity similar to or higher than those of GPT-5 mini and GPT-6 Astra, while API charges per 1000 records were US$0.043 for Jev, US$0.57 for GPT-5 mini, and US$7.39 for GPT-6 Astra.”

> E-6920acd3840dc68a · [3] · abstract only via semantic\_scholar (8ceea07569d6cf671811983fb737b08a3531e96b) · abstract:P-2f24266ea340655e\_c1 · “However, performance varies across models and is sensitive to evaluation metrics, particularly in low-prevalence screening contexts.”

## References

[1] Ava Homiar, James Thomas, Edoardo Giuseppe Ostinelli, Jaycee Kennett, Claire Friedrich, Pim J. Cuijpers, Mathias Harrer, Stefan Leucht, Clara Miguel, Alessandro Rodolico, Yuki Kataoka, Tomohiro Takayama, Keisuke Yoshimura, Ryuhei So, Yasushi Tsujimoto, Yosuke Yamagishi, Shiro Takagi, Masatsugu Sakata, Djordje Basic, Eirini Karyotaki, Jennifer Potts, Georgia Salanti, Toshi A. Furukawa, Andrea Cipriani (2025). Development and evaluation of prompts for a large language model to screen titles and abstracts in a living systematic review. https://doi.org/10.1136/bmjment-2025-301762

Study ID P-955f95396b410f69. Source records: openalex:W4412582725, semantic\_scholar:0f1a909bd7ef0d01ba94510bbc12da326065b4ce.

[2] Kentaro Matsui, Yoshikazu Takaesu (2026). Title and Abstract Screening for Systematic Reviews with Jev, a Decision Model: Comparison with Generative Large Language Models. https://doi.org/10.3390/info17111160

Study ID P-29185e5a55fb2217. Source records: crossref:10.3390/info17111160.

[3] M. Nawrath, Andrea Merlina, Jemmima Knight, S. Welch, Mahla Rashidian, I. Seifert-Dähnn (2026). Validating Large Language Models for Title-Abstract Screening in Low-Prevalence Systematic Reviews: An Environmental Science Case Study. https://doi.org/10.3390/info17050501

Study ID P-2f24266ea340655e. Source records: semantic\_scholar:8ceea07569d6cf671811983fb737b08a3531e96b.

## Limitations

Verified excerpts were available from 4 of 6 included records. Findings cover only the retained evidence.

The configured source and result limits constrain retrieval coverage. Automated support judgments and lexical overlap are screening aids. The supplied sources and any human adjudications should be checked for scientific interpretation.
