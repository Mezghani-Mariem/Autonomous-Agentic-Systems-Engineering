# SLRResearchAI — TD08 réalisé

Le TD08 ajoute au projet du TD07, dans cet ordre pédagogique :

1. un QualityAgent qui contrôle la fidélité des affirmations ;
2. ensuite, une orchestration par pipeline et par superviseur.

Artefacts utilisés :

- `artifacts/td06_evidence.json` ;
- `artifacts/td07_writing_artifact.json`.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
pytest -v
```

Les huit TODO de [ENONCE_TD08.md](ENONCE_TD08.md) sont complétés dans
`slrresearch/quality_agent.py` et `slrresearch/orchestrator.py`.
Le [compte rendu](COMPTE_RENDU_TD08.md) explique les expressions, les mesures,
les traces et les limites du contrôle lexical.

Après réalisation :

```bash
python3 main.py
python3 -m streamlit run streamlit_app.py
```

Sous Windows, depuis ce dossier et avec un Python disposant des dépendances :

```powershell
.\run_tests.ps1
python -X utf8 main.py
python -X utf8 -m streamlit run streamlit_app.py
```

Le lanceur cherche un Python disposant de `pytest` parmi les interpréteurs
du PATH, puis essaie `C:\Python312\python.exe`. Il peut ainsi fonctionner même
si un ancien environnement virtuel sans pytest est actif. Il affiche
l'interpréteur retenu. Pour en sélectionner un explicitement :

```powershell
.\run_tests.ps1 -PythonExecutable "C:\Python312\python.exe"
```

Le lanceur désactive le cache pytest et utilise un dossier temporaire unique.
Sur la machine de réalisation, **99 tests passent** : 68 tests fournis et
31 cas complémentaires. Les deux phases Streamlit ont aussi été vérifiées
avec `AppTest`, y compris des budgets insuffisants.

`main.py` rejoue une démonstration déterministe et enregistre :

- [Les résultats et traces JSON](artifacts/td08_execution.json).
- [La note corrigée](artifacts/td08_note_corrigee.md).

Résultats : note initiale `REVISE` (score 93,33 %, fidélité 80 %), note corrigée
`ACCEPT` (100 %), pipeline `ESCALATE`, superviseur `FINISH` avec retour vers RAG.
Le score élevé du brouillon ne suffit pas à accepter A5, car son feedback
signale une affirmation non soutenue.

Cette démonstration réutilise les artefacts pédagogiques fournis. Le RAG ne
récupère pas de nouvelles preuves et le Writer renvoie la correction fournie.
Aucun LLM réel n'a été appelé ; l'adaptateur du juge a été testé avec des
réponses simulées. Le mode LLM réel reste configurable dans Streamlit selon
`.env.example`.
