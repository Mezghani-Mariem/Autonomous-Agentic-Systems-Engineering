# Présentation de MultiAgentSLR

## Problème et objectifs

Une revue systématique transforme une question en protocole de recherche, puis en sélection d'études et en synthèse traçable. La planification précise le périmètre et les critères. La recherche récupère les notices et consigne les résultats des sources. Le dédoublonnage évite de compter deux fois une même notice. Le screening applique les critères d'admissibilité. L'extraction relie les résultats au texte disponible. La synthèse distingue affirmations, preuves et questions ouvertes. Le contrôle final vérifie que chaque affirmation est associée aux preuves pertinentes. Ces étapes répondent à deux questions différentes pour le lecteur, à savoir comment un document est entré dans la revue et sur quoi repose chaque affirmation.

Dans un flux manuel, comparer des listes de résultats, repérer les doublons, appliquer les critères sur de nombreux résumés et retrouver la citation correspondant à chaque affirmation demandent du temps et une coordination entre évaluateurs. La divergence des appréciations et l'évolution des index compliquent la reproduction. Ce sont des motivations de conception. Le projet ne mesure ni le temps humain économisé, ni l'accord inter-évaluateurs, ni un gain de coût.

MultiAgentSLR automatise une **synthèse exploratoire fondée en priorité sur les résumés**. Les LLM assistent la formulation des questions et des requêtes, le screening, la sélection d'extraits, la rédaction et le jugement de support. Le code applique la politique de recherche, les contrats de données, la provenance et les budgets. La décomposition en six rôles permet de localiser un échec, de reprendre une revue sauvegardée et d'examiner les décisions. Par rapport à une synthèse produite en un seul appel LLM, la recherche, les décisions de tri, les extraits vérifiés et les affirmations ont chacun leur propre artefact et leurs identifiants. La différence est architecturale. Aucune comparaison au générateur mono-appel n'a été exécutée.

### Entrées et sorties

| Entrées | Effet | Sorties observables |
| --- | --- | --- |
| Sujet, critères d'inclusion et d'exclusion | Oriente les trois questions, les requêtes et le tri | `ResearchPlan`, requêtes et facettes par question |
| Mode, fournisseur LLM, limite de notices, paramètres RAG et révision | Détermine le chemin, les quotas et les pauses | `ReviewRun`, observations, décisions, traces et événements |
| Notices d'OpenAlex, Semantic Scholar et Crossref | Constitue une liste dédoublonnée et conserve les alias natifs | `SearchBatch` et `ScreeningBatch` |
| PDF à texte extractible, facultatif en mode humain | Remplace le résumé dans le corpus de l'étude lorsque des fragments sont disponibles | Provenance PDF avec page réelle. Un résumé ne reçoit aucune page |
| Décisions humaines justifiées, facultatives selon le mode et le point de pause | Modifie la décision finale de screening ou statue sur une affirmation | Historique, événements humains et décisions de qualité |
| Étiquettes CSV et rélevance JSON facultatives, dans Evaluation | Permet les calculs de référence quand elles sont valides | Export d'évaluation JSON ou CSV. Ces étiquettes ne pilotent pas la revue |
| Revue suffisamment étayée | Produit synthèse, références et limites | Rapport Markdown et PDF. Sinon, état explicite de preuve insuffisante |

Les résumés peuvent omettre la méthode, les conditions ou les résultats détaillés. Les recherches sont bornées par un nombre de résultats par source. Les critères peuvent être appliqués sur le titre et le résumé, même si un PDF est ajouté ensuite. Le rapport déclare l'absence de texte intégral. Les résultats disponibles attestent un fonctionnement logiciel et une synthèse documentée, dans ce périmètre. [Limites et menaces](LIMITATIONS_AND_THREATS_TO_VALIDITY.md)

## Contributions et réutilisation du cours

| Provenance | Brique cours utilisée | Contribution vérifiable de l'application |
| --- | --- | --- |
| TD01 et TD02 | Messages zero-shot, validation textuelle et Pydantic, réparation bornée | Protocole structuré adapté à trois API réelles. La génération booléenne du TD02 demeure une brique pédagogique |
| TD03 | Contrats `AgentAction` et `Observation`, registre, boucle ReAct et flux fixe | Adapters HTTPX, mémoire d'observations, politique déterministe à repli, métadonnées fusionnées et télémétrie |
| TD04 | Décision LLM structurée et baseline lexicale | Politique `llm-evidence-v1`, révision humaine historisée, baseline séparée de la production |
| TD05 et TD06 | Extraction PDF, TF-IDF/cosinus, facettes et récupération adaptative | Corpus résumé/PDF, sélection par deux identifiants et vérification exacte indépendante, journal des rejets |
| TD07 | `PlanCandidate`, validation, exécution, replanning | Sections avec limitation explicite, affirmations par question et références autorisées, conservation des affirmations étayées |
| TD08 | `Handoff`, contrôle de transition et métriques déterministes | Coordinateur persistant, juge structuré par affirmation, filtrage et exports. Comparaison fixe/supervisée conservée sur fixture |
| Intégration | Assemblage des briques précédentes | Interface Streamlit, cache SQLite, métriques/export, preuves reproductibles et images Docker de l'application et des tests |

Le tableau de provenance complet est dans [COURSE_CODE.md](../../COURSE_CODE.md). Les concepts sont décrits d'après leur usage dans l'application, qui peut différer des notebooks originaux. [Analyse des agents](AGENTS_TECHNICAL_DETAILS.md)

## Pile vérifiée

Versions constatées dans le conteneur local ou sur l'hôte lors de l'audit. Les plages indiquent les dépendances déclarées. L'image et la résolution des paquets peuvent évoluer.

| Technologie | Version constatée ou borne | Rôle et usage réel | Source |
| --- | --- | --- | --- |
| Python | conteneur 3.12.16, base `python:3.12-slim` | Exécution des six étapes, CLI, UI et tests | [Dockerfile](../../Dockerfile) |
| Streamlit | 1.67.0, `>=1.50,<2` | Pages Review workspace et Evaluation, formulaires, téléchargements, `AppTest` côté tests | [app.py](../../app.py), [requirements.txt](../../requirements.txt) |
| Ollama | hôte 0.13.0, bibliothèque Python transitive 0.6.3, modèle observé `qwen2.5:7b` | Modèle conversationnel par défaut, température 0 dans l'adapter. Embeddings Ollama facultatifs selon configuration | [gateway.py](../../slr/gateway.py), [settings.py](../../slr/settings.py) |
| LangChain Core et Ollama | 1.8.4 et 1.1.0, plages déclarées `>=0.3.70,<2` et `>=0.3.6,<2` | Messages et adaptation structurée Ollama en mode `json_schema` | [gateway.py](../../slr/gateway.py), [requirements.txt](../../requirements.txt) |
| Groq et LangChain Groq | SDK 1.7.0, adapter 1.2.1, plage de l'adapter `>=0.3.6,<2` | Fournisseur facultatif, modèle par défaut `openai/gpt-oss-20b`, sortie `json_mode` avec schéma ajouté au prompt. Un essai historique HTTP 401 est documenté. Succès live **NON VÉRIFIÉ** | [gateway.py](../../slr/gateway.py), [VALIDATION.md](../../VALIDATION.md) |
| HTTPX | 0.28.1, `>=0.27,<1` | Requêtes bibliographiques et conversions des erreurs transport/statut | [sources.py](../../slr/sources.py), [gateway.py](../../slr/gateway.py) |
| Pydantic | 2.14.4, `>=2.10,<3` | Validation des objets d'étape, actions, décisions et sorties LLM | [models.py](../../slr/models.py) |
| TF-IDF et cosinus | Calcul Python local, scikit-learn absent des dépendances déclarées et du chemin audité | Fréquences, IDF lissée, score cosinus, top-k. Aucun serveur vectoriel dans le chemin courant | [rag_pipeline.py](../../slr/course/rag_pipeline.py) |
| pypdf et ReportLab | 6.21.4 et 4.5.1, `>=5,<7` et `>=4.2,<5` | Extraction de texte par page et rendu PDF | [pdf_loader.py](../../slr/course/pdf_loader.py), [report.py](../../slr/report.py) |
| SQLite et bibliothèque standard | `sqlite3` et `hashlib` de Python | Tables `runs` et `cache`, WAL, contrôle de version, SHA-256 des clés | [storage.py](../../slr/storage.py) |
| python-dotenv | 1.2.4, `>=1,<2` | Chargement facultatif de la configuration locale | [settings.py](../../slr/settings.py) |
| Docker et Compose | client et serveur 28.0.4, plugin 2.34.0-desktop.1 | Service Streamlit, profil tests, volume persistant, santé locale | [compose.yaml](../../compose.yaml), [Dockerfile](../../Dockerfile) |
| pytest | 9.2.0 dans l'image de test, `>=8,<10` | Unitaire, intégration, UI contrôlée et parcours live distinct | [requirements-dev.txt](../../requirements-dev.txt), [pytest.ini](../../pytest.ini) |
| FastAPI | Sans objet | Aucun service FastAPI dans les entrées, dépendances directes ou fichiers de déploiement audités | [app.py](../../app.py), [compose.yaml](../../compose.yaml) |

### Répertoires et commandes

| Chemin | Responsabilité |
| --- | --- |
| `app.py`, `slr/__main__.py` | UI et CLI `run`, `inspect`, `export` |
| `slr/` et `slr/course/` | Intégration de production et copies locales des briques pédagogiques |
| `evaluation/` et `experiments/datasets/` | Métriques, exports et expériences A–D sur artefacts gelés |
| `experiments/runs/` et `experiments/live/` | Artefacts expérimentaux sur disque local. Les résultats UI Compose se trouvent sous `/app/data/experiments` |
| `tests/` | Fakes contrôlés, contrats, intégration, UI et smoke tests live |
| `data/slr.sqlite3` | Stockage local natif, distinct de `/app/data/slr.sqlite3` dans le volume Compose |
| `output/` | Exemples d'exports historiques. Vérifier l'identifiant imprimé avant citation |
| `render.yaml` | Blueprint mono-instance, disque 2 Go, health HTTP, Groq configuré. Déploiement cloud **NON VÉRIFIÉ** |

Exécuter depuis le répertoire `MultiAgentSLR`.

```powershell
python -m pip install -r requirements-dev.txt
python -m streamlit run app.py
docker compose up --build -d --wait app
docker compose --profile tests run --rm tests
python -m slr run "Sujet de recherche documenté" --provider ollama --record-prompts
python -m slr inspect RUN_ID
python -m slr export RUN_ID --output output/exemple
python -m evaluation controlled
```

Les commandes locales et Compose utilisent des espaces de données différents par défaut. Pour inspecter une revue Compose depuis le conteneur, employer `docker compose exec -T app python -m slr inspect RUN_ID`. Pour les tests live, activer `SLR_RUN_LIVE=1` et, pour le parcours complet, `SLR_RUN_LIVE_REVIEW=1`. `SLR_LIVE_PROVIDERS` sélectionne les modèles des smoke tests. [README](../../README.md) · [Déploiement](../../DEPLOYMENT.md)

| Variables | Effet |
| --- | --- |
| `LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_EMBEDDING_MODEL` | Ollama par défaut, hôte local hors conteneur ou passerelle hôte via Compose |
| `GROQ_MODEL`, `GROQ_API_KEY` | Modèle et authentification Groq |
| `OPENALEX_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `CROSSREF_EMAIL` | Accès optionnel ou identification auprès des sources |
| `SLR_DATA_DIR`, `SLR_EXPERIMENT_DIR` | Répertoires distincts de persistance et d'expériences |
| `SLR_CACHE_TTL_SECONDS`, `SLR_REQUEST_TIMEOUT_SECONDS` | TTL applicatif par défaut 86 400 s, 0 désactive le cache. Délai par défaut 25 s |
| `SLR_ACCESS_TOKEN`, `SLR_HOST_PORT`, `PORT` | Protection d'équipe facultative et ports de service. Aucun secret n'est reproduit dans l'audit |

Sources de configuration. [Exemple d'environnement](../../.env.example) · [Settings](../../slr/settings.py) · [Compose](../../compose.yaml) · [Render](../../render.yaml)
