# SLRResearchAI — TD06 RAG agentique

Ce dépôt cumulatif transforme la baseline RAG fixe du TD05 en retrieval
adaptatif sous contraintes.

```text
décider → récupérer → observer → adapter ou terminer
```

Le package `slrresearch/` conserve les composants acquis pendant les TD01 à
TD05. Les huit TODO du TD06 sont complétés dans :

```text
slrresearch/agentic_rag.py
```

## Démarrage

Sous Windows, avec l'environnement déjà présent dans le dossier parent :

```powershell
New-Item -ItemType Directory -Force .pytest_cache | Out-Null
..\venv\Scripts\python.exe -X utf8 -m pytest -v --basetemp .pytest_cache/td06-temp
..\venv\Scripts\python.exe -X utf8 main.py
..\venv\Scripts\python.exe -X utf8 -m streamlit run streamlit_app.py
```

Pour une installation indépendante sous Linux ou macOS :

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
pytest -v
```

Exécution :

```bash
python3 main.py
python3 -m streamlit run streamlit_app.py
```

## Documents

- `COMPTE_RENDU_TD06.md` : solutions, résultats, abstention, limites et reproduction sous Windows ;
- `A_RENDRE_TD06.zip` : projet complété et artefacts de validation ;
- `ENONCE_TD06.md` : déroulement détaillé des huit TODO ;
- `CONSTRUIRE_PROJET_BOUT_EN_BOUT.md` : chaîne complète TD01 → TD06 ;
- `ACQUIS_TD05.md` : rappel de l'énoncé précédent.

## Validation

Les 65 tests passent : 57 tests fournis et 8 cas d'intégration ajoutés.
Les six parcours Streamlit contrôlés (Q1–Q3, budgets 1 et 2) ont été vérifiés
avec `AppTest`. À budget 2, Q1 et Q2 gagnent un rappel de 1,00 avec un appel
supplémentaire ; Q3 termine dès le premier appel. À budget 1, Q1 et Q2
s'abstiennent sans génération.

Les embeddings contrôlés utilisent les annotations : ces résultats valident
la logique de la boucle, pas la qualité d'un modèle sémantique réel.

Le mode contrôlé est reproductible et ne nécessite aucun service externe. Les
modes Ollama ou Groq utilisent `.env`, créé localement à partir de
`.env.example` et ignoré par Git.
