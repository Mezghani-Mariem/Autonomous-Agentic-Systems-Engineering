# Flux et schémas de preuve

## Contrats et clés de liaison

| Étape | Modèle et champs utiles | Invariant ou liaison |
| --- | --- | --- |
| Paramétrage | `ReviewConfig(topic, provider, execution_mode, search, screen, retrieval, orchestration, per_source, top_k, retrieval_budget, revision_budget, pause_for_documents, inclusion, exclusion)` | Sujet 12 à 1 000 caractères, `per_source` 1–15, top-k 1–8, budget RAG 1–3 par RQ, révision Quality 0–2. Pause PDF réservée au mode humain |
| Planification | `ResearchPlan(questions, protocol, plan, repair_attempts, protocol_repairs)`, `ResearchQuestion(identifier, question)`, `ProtocolProposal(queries, questions)`, `QuestionProtocol(rq_id, terms, facets)`, `EvidenceFacet(id, label, keywords, query_hint)` | Exactement RQ1–RQ3 et requêtes sur les trois sources. `include_signals/exclude_signals` restent compatibles avec les valeurs historiques |
| Acquisition | `AgentAction(action, tool, query, limit)`, `Observation(tool, status, count, latency_seconds, error, papers)`, `SearchState` avec objectif, requêtes, état, actions, observations, trace, raison d'arrêt | La notice de l'observation est différente du lot canonique |
| Notice et étude | `SourceRecord(source, native_id, title, abstract, doi, url, authors, year, open_access)`, `Study(id, title, abstract, doi, url, authors, year, abstract_source, sources)`, `SearchBatch(papers, discovered, duplicates, state)` | Aliases natifs préservés. `Study.id` est dérivé par SHA-256 de la clé DOI, ou titre normalisé et année. `discovered = len(papers) + duplicates` |
| Tri | `LLMScreeningDecision` avec ID, décision, confiance, raisons, preuve, signal humain. `ScreeningBatch(policy, decisions)`, `ScreeningDecision(paper_id, rule, llm, final, decided_by, reason, quote, quote_verified, llm_confidence, screening_reason, review_history)` | Un verdict par `Study.id`. Origine humaine distincte, historique daté. `rule/rule_reason` peuvent subsister dans des états historiques |
| Corpus et provenance | `EvidenceLocation(paper_id, chunk_id, source_type, page, source, source_record_id, source_url)`, `EvidenceChunk(text)`, `CorpusSummary(included_abstracts, abstract_chunks, full_text_chunks, missing_text_paper_ids)` | Uniquement `include`. Page présente uniquement pour `full_text`. Source et ID natif du résumé lorsque connus. `source_type` accepte l'ancien alias `kind` en lecture |
| Classement et preuve | `RetrievalRun` (RQ, rangs, facettes, budget consommé, méthode, query, trace et extraction), `Extraction(selections)`, `ExcerptSelection(chunk_id, candidate_id)`, `ExtractionAudit`, `Passage(id, rq_id, quote, facets, …provenance)`, `RagBundle(evidence, retrieval, corpus)` | Une paire doit coïncider, la citation provient du chunk canonique, `E-…` est dérivé de RQ/chunk/texte. Un même chunk peut être sélectionné pour plusieurs RQ |
| Exécution et rédaction | `PlanCandidate` avec étapes, stratégie et objectif, `PlanStep` avec RQ, dépendances, mode, facettes et IDs autorisés, `ExecutionResult`, `Draft(claims, execution)`, `Claim(id, rq_id, text, evidence_ids)` | Le superviseur tient un brouillon courant. La référence textuelle `C…` est attribuée en Python, l'ID survit aux révisions lorsqu'une affirmation étayée est conservée |
| Qualité et fin | `ClaimCheck(claim_id, judgment, reason)`, `QualityResult(revision, citation_validity, lexical_support, automated_score, question_coverage, findings, invalid_claims, feedback)`, `ClaimReview(claim_id, decision, reason)` | Une affirmation cite des passages du même RQ. En automatique les alertes résiduelles deviennent `withheld_claim_ids`. Les citations imprimées reçoivent des numéros basés sur l'ordre d'apparition des études retenues |
| État commun | `ReviewRun` avec ID, version, dates UTC, config, stage, statut, erreur, motifs, artefacts, révision, documents, décisions, `Event` et `Handoff` | SQLite persiste le JSON. Les handoffs décrivent source, cible, artefact, état, budget et IDs de preuve disponibles. Dans `Event`, `stage/kind/operation/status`, latence, tokens optionnels, retry, détail et timestamp |

Sources du schéma. [models.py](../../slr/models.py) · [Contrats TD03](../../slr/course/contracts.py) · [Recherche de facettes](../../slr/course/agentic_rag_models.py) · [Contrats TD07](../../slr/course/planning_models.py) · [Handoff](../../slr/course/quality_models.py) · [Rendu](../../slr/report.py)

## Cas réel `b31a5129748e4569a8b8f2aac656e4f9`

Instance du 20 novembre 2026, stockée dans `/app/data/slr.sqlite3` (volume `review_data`). Le JSON d'évaluation se trouve à `C:/Users/Lenovo/Downloads/evaluation-b31a5129.json`. Les fragments ci-dessous sont des projections de l'artefact, avec de longs champs omis. Les réponses HTTP originales ne sont pas archivées en brut pour cette revue. Le point de départ vérifiable est la notice source normalisée issue du cache. La page source et la citation sont reliées par les identifiants conservés par le programme.

Pour relire le JSON de la revue à partir du volume local, sans lancer d'inférence.

```powershell
docker compose exec -T app python -m slr inspect b31a5129748e4569a8b8f2aac656e4f9
```

### 1. Protocole

Projection de `plan.protocol`. Les trois sources ont reçu la même phrase bien que le schéma permette de les distinguer.

```json
{
  "queries": {
    "openalex": "large language models evaluation title abstract systematic review",
    "semantic_scholar": "large language models evaluation title abstract systematic review",
    "crossref": "large language models evaluation title abstract systematic review"
  }
}
```

### 2. Notice API normalisée et étude dédoublonnée

Projections de `search.papers[].sources` et `search.papers[]`. L'ID natif OpenAlex est également utilisé dans le rapport. Des occurrences parallèles partagent le DOI et sont fusionnées.

```json
{
  "source": "openalex",
  "native_id": "W4412582725",
  "title": "Development and evaluation of prompts for a large language model to screen titles and abstracts in a living systematic review",
  "doi": "10.1136/bmjment-2025-301762",
  "year": 2025,
  "open_access": true
}
```

```json
{
  "id": "P-955f95396b410f69",
  "doi": "10.1136/bmjment-2025-301762",
  "abstract_source": "openalex",
  "sources": [
    {"source": "openalex", "native_id": "W4412582725"},
    {"source": "semantic_scholar", "native_id": "0f1a909bd7ef0d01ba94510bbc12da326065b4ce"}
  ]
}
```

### 3. Décision de tri et entrée du corpus

La recommandation est AI et la preuve de screening correspond cette fois au **titre**. La preuve citée par Writing sera un passage différent, tiré du résumé.

```json
{
  "paper_id": "P-955f95396b410f69",
  "llm": "include",
  "final": "include",
  "decided_by": "ai",
  "llm_confidence": 1.0,
  "quote_verified": true,
  "quote": "Development and evaluation of prompts for a large language model to screen titles and abstracts in a living systematic review",
  "review_history": []
}
```

### 4. Classement et paire choisie

Dans `rag.retrieval` pour RQ1, le chunk est deuxième dans la mémoire finale. Le numéro du candidat est local à cette demande d'extraction. Le texte complet des chunks intermédiaires n'est pas exporté dans la métrique, mais `build_corpus` peut le reconstruire depuis le résumé conservé, la règle de découpe et l'ID. L'extrait final conservé suit dans l'étape suivante.

```json
{
  "rq_id": "RQ1",
  "ranks": [
    "abstract:P-467c8a257916fffe_c3",
    "abstract:P-955f95396b410f69_c1",
    "abstract:P-2ba098aa70c61452_c1"
  ],
  "extraction": {
    "status": "verified",
    "candidate_count": 20,
    "selections": [
      {"chunk_id": "abstract:P-955f95396b410f69_c1", "candidate_id": 12},
      {"chunk_id": "abstract:P-2ba098aa70c61452_c1", "candidate_id": 18}
    ],
    "verified_count": 2
  }
}
```

### 5. Preuve vérifiée et rédaction

Projections de `rag.evidence` et `draft.claims`. Le résolveur `verify_excerpt` vérifie que l'extrait et les métadonnées sont ceux du chunk canonique.

```json
{
  "id": "E-f4b1c28ea2196a85",
  "rq_id": "RQ1",
  "paper_id": "P-955f95396b410f69",
  "chunk_id": "abstract:P-955f95396b410f69_c1",
  "source_type": "abstract",
  "page": null,
  "source": "openalex",
  "source_record_id": "W4412582725",
  "source_url": "https://doi.org/10.1136/bmjment-2025-301762",
  "quote": "METHODS: Human decisions from an LSR on prodopaminergic interventions for anhedonia served as the reference standard.",
  "facets": ["evaluation_criteria"]
}
```

```json
{
  "id": "C1",
  "rq_id": "RQ1",
  "text": "Studies use human decisions from systematic reviews (LSRs) as reference standards for evaluating language models in title and abstract screening.",
  "evidence_ids": ["E-f4b1c28ea2196a85"]
}
```

### 6. Contrôle, handoff et citation

Le verdict ci-dessous est celui du juge automatique final, sans arbitrage humain. L'analyste doit garder la portée de la citation, qui décrit une étude précise. La formulation plurielle du modèle dépasse possiblement la généralisation directe justifiée par cet extrait seul.

```json
{
  "claim_id": "C1",
  "judgment": "supported",
  "reason": "The cited passage mentions that human decisions from an LSR served as the reference standard, which aligns with the claim about using human decisions for evaluating language models in title and abstract screening."
}
```

```json
{
  "source": "quality",
  "target": "finish",
  "budget_left": 0,
  "artifact": {
    "claim_ids": ["C1", "C4"],
    "human_decisions": [],
    "withheld_claim_ids": ["C5", "C6"]
  }
}
```

Le rendu relu en mémoire associe `C1` à **[1]**, Ava Homiar et al. (2025), DOI `10.1136/bmjment-2025-301762`. La ligne de provenance associe aussi l'extrait à `openalex:W4412582725`. Les PDF et Markdown nommés simplement `literature-review` dans Téléchargements portent **5c1aa9ed…**, autre exécution qui donne les mêmes champs clés. Ne pas les attribuer à `b31a5129…`. [Inventaire et exports](EXPERIMENTS_AND_RESULTS.md)

La chaîne utile au rapport est `W4412582725 → P-955f95396b410f69 → abstract:P-955f95396b410f69_c1 → E-f4b1c28ea2196a85 → C1 → [1] → 10.1136/bmjment-2025-301762`.
