# Synthèse de l'audit MultiAgentSLR

**Périmètre.** Audit technique et expérimental des fichiers présents le 20 novembre 2026. Sources Python, contrats, interface, configuration, tests, archives, volume Docker et exports locaux ont été recoupés. Le projet est un prototype de synthèse exploratoire abstract-first. La rédaction finale et les diapositives ne font pas partie de cet audit.

## Architecture confirmée

Application Streamlit et CLI, six rôles synchrones coordonnés par `slr.supervisor.Supervisor`, état Pydantic `ReviewRun` dans SQLite, cache et télémétrie. Sujet → questions/requêtes → trois API/dédoublonnage → screening → corpus → RAG et provenance → Plan-and-Execute → contrôle et révision → rapport ou abstention. Le mode humain ajoute des checkpoints persistants. Le ReAct de recherche prend ses décisions à partir d'observations et de règles. Le RAG adaptatif reformule selon les facettes. [Architecture et six diagrammes](SYSTEM_ARCHITECTURE.md)

| Rôle | Point d'entrée confirmé | Contrat transmis |
| --- | --- | --- |
| Planification | [`prepare_review`](../../slr/planning.py) | `ReviewConfig → ResearchPlan` |
| Découverte | [`search_review` et `consolidate`](../../slr/sources.py) | Requêtes → `SearchBatch` |
| Screening | [`screen_papers`](../../slr/screen.py) | `Study → ScreeningBatch` |
| Récupération | [`gather_evidence` et `verify_excerpt`](../../slr/retrieval.py) | Inclusions/facettes → `RagBundle` |
| Rédaction | [`write_review`](../../slr/synthesis.py) | Passages → `Draft` |
| Qualité | [`evaluate_claims` et `quality_route`](../../slr/synthesis.py) | Affirmations → `QualityResult` et prochaine étape |
| Coordination | [`Supervisor`](../../slr/supervisor.py) | `Handoff`, état, pauses et reprises |
| Présentation et mesure | [`app.py`](../../app.py), [`review_metrics`](../../evaluation/metrics.py), [`report.py`](../../slr/report.py) | Rapports Markdown/PDF et métriques CSV/JSON |

## Résultats vérifiés et portée

| Preuve | Résultat établi | Où vérifier |
| --- | --- | --- |
| Revue centrale `b31a5129748e4569a8b8f2aac656e4f9` | Succès avec cache intégral. 12 notices, 10 uniques, 6 inclusions, 4 non résolues, 9 passages, 2 affirmations retenues. 18 hits LLM, 3 hits API et zéro appel réel | `/app/data/slr.sqlite3` et exports `C:/Users/Lenovo/Downloads/evaluation-b31a5129.json` et `C:/Users/Lenovo/Downloads/evaluation-b31a5129.csv` |
| Échec originel `278d886ab8a94ef6bc17229cb4b69fe6` | 6 abstracts, 9 positions RAG, aucune preuve. Deux listes vides et deux en-têtes proposés comme extraits | `/app/data/slr.sqlite3` · [Historique](../../VALIDATION.md) |
| Replay final `65af34fdf89a45d4a6b55fc31e0c82de` | Search/screening identiques. Nouvelles inférences à partir de RAG, 9 passages, 3 affirmations et 3 notices citées, 1 claim retiré. Markdown et PDF disponibles | [Trace](../../experiments/live/replay-278d886a-final/run.json) · [PDF](../../experiments/live/replay-278d886a-final/literature-review.pdf) |
| Run final frais `000cca74b20344e4b0379398a98ae591` | 8 uniques, 3 inclusions, 5 non résolues, 10 extraits, 4 claims et une notice citée, 16 appels LLM réels. Une révision. Exports contrôlés | [Trace](../../experiments/live/000cca74b20344e4b0379398a98ae591/run.json) · [Métriques](../../experiments/live/000cca74b20344e4b0379398a98ae591/metrics.json) · [PDF](../../experiments/live/000cca74b20344e4b0379398a98ae591/literature-review.pdf) |
| HITL | Six décisions humaines historiques. Libération du checkpoint sur une revue moderne qui se termine sur un autre sujet, sans arbitrage d'affirmation | [HITL et preuves](HITL_WORKFLOW.md) |
| A, B, C, D | A, 3 notices par bras, ordre différent. B historique, 6/10 attentes sans référence. C, Q2 de 0 à 1 à k=1 au prix d'un appel, autres cas stables. D, score 0,9333 → 1 avec correction fournie | [Résultats et liens directs](BASELINES_AND_ABLATIONS.md) |
| Reproductibilité locale | HTTP 200, 50 tests contrôlés réussis (4,03 s), 6 live désélectionnés. Test live archivé, 1 réussi en 168,24 s | [Inventaire](EXPERIMENTS_AND_RESULTS.md) · [Tests](../../tests/) |

## Preuves absentes ou partielles

- **NON VÉRIFIÉ** comme preuve scientifique indépendante. Aucune annotation indépendante du screening ou de pertinence des passages en production. Les labels de C sont pédagogiques. Aucun juge scientifique humain des claims observé.
- **NON VÉRIFIÉ** comme gain comparatif général. Pas de paire live équivalente Fixed/ReAct, Classical/Agentic, Fixed/Supervisor ou Automatic/HITL. B historique ne mesure pas la politique courante. Pas de comparaison au générateur mono-appel.
- **Partiel** en HITL. Tri humain et checkpoints attestés. Le PDF réel traité et l'arbitrage humain d'affirmations nécessitent une démonstration.
- **Partiel** pour les services. Semantic Scholar retourne 429 dans les essais frais examinés. Groq intégré, succès live **NON VÉRIFIÉ**. Blueprint Render disponible, déploiement abouti **NON VÉRIFIÉ**.
- **Partiel** pour la preuve visuelle. Captures historiques identifiées et dossier actuel à faire. Les exports génériques de Téléchargements portent `5c1aa9ed…`. [Checklist](SCREENSHOT_CHECKLIST.md)

## Index des 12 documents

| Fichier | Contenu |
| --- | --- |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | Problème, objectifs, contributions, dépendances, commandes |
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Six diagrammes Mermaid et architecture |
| [AGENTS_TECHNICAL_DETAILS.md](AGENTS_TECHNICAL_DETAILS.md) | Rôles, contrats, décisions, prompts, erreurs |
| [DATA_FLOW_AND_SCHEMAS.md](DATA_FLOW_AND_SCHEMAS.md) | Artefacts réels et chaîne DOI/IDs |
| [HITL_WORKFLOW.md](HITL_WORKFLOW.md) | Checkpoints, tests, traces et limites |
| [EXPERIMENTS_AND_RESULTS.md](EXPERIMENTS_AND_RESULTS.md) | Inventaire de revues, exports et preuves |
| [METRICS_DICTIONARY.md](METRICS_DICTIONARY.md) | Définitions, formules, valeurs et interprétation |
| [BASELINES_AND_ABLATIONS.md](BASELINES_AND_ABLATIONS.md) | Matrice et comparaison des variantes |
| [SCREENSHOT_CHECKLIST.md](SCREENSHOT_CHECKLIST.md) | Captures historiques, étapes de collecte actuelle |
| [LIMITATIONS_AND_THREATS_TO_VALIDITY.md](LIMITATIONS_AND_THREATS_TO_VALIDITY.md) | Limites, ambiguïtés des mesures et menaces |
| [REPORT_OUTLINE.md](REPORT_OUTLINE.md) | Plan pédagogique en 16 chapitres |
| [AUDIT_SUMMARY.md](AUDIT_SUMMARY.md) | Synthèse, preuves et index |

Sources d'exploitation. [README](../../README.md) · [DEPLOYMENT](../../DEPLOYMENT.md) · [COURSE_CODE](../../COURSE_CODE.md) · [EVALUATION](../../EVALUATION.md) · [VALIDATION](../../VALIDATION.md)

Aucune fonctionnalité applicative ou ressource TD n'a été modifiée dans cet audit. Les projections JSON ont été limitées aux champs nécessaires à la démonstration.
