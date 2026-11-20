# Compte rendu TD08 — QualityAgent et orchestration multi-agent

**Projet :** SLRResearchAI  
**Date :** 17 novembre 2026  
**Sujet :** contrôle des affirmations, juge structuré, réflexion bornée et routage.

## 1. Objectif et entrées

Le TD08 contrôle une note de synthèse avant sa livraison. Il réutilise
`artifacts/td06_evidence.json` et `artifacts/td07_writing_artifact.json`.
Le premier contient **8 unités de preuve issues de 4 études et 3 RQ**.
Le second fournit un brouillon de cinq affirmations et une version corrigée.

Le cas volontairement problématique est A5 : « La précision dépasse celle
des experts. » Il cite E8, qui porte sur la calibration du prompt et son
contrôle local, sans établir une supériorité sur des experts.

Le travail complète les huit TODO demandés dans `quality_agent.py` et
`orchestrator.py`. Les anciennes fonctions `pipeline_run()` et
`supervisor_run()` sont conservées ; les expériences utilisent bien
`full_pipeline_run()` et `full_supervisor_run()`.

## 2. Livrables

- [QualityAgent](slrresearch/quality_agent.py) : TODO 1 à 5.
- [Orchestrateur](slrresearch/orchestrator.py) : TODO 6 à 8.
- [Démonstration exécutable](main.py) : qualité, réflexion et comparaison des architectures.
- [Tests complémentaires](tests/test_td08_regressions.py) : 31 cas, dont les deux routes de réparation.
- [Lanceur Windows](run_tests.ps1) : exécution reproductible sans cache pytest partagé.
- [Résultats JSON](artifacts/td08_execution.json) : métriques, états, artefacts et handoffs.
- [Note corrigée](artifacts/td08_note_corrigee.md) : sections et affirmations avec identifiants de preuve.

## 3. TODO 1 — Contrat des affirmations

`parse_claims()` transforme chaque dictionnaire de `report.get("claims", [])`
en `Claim` avec `Claim.model_validate()`. Un champ absent donne une liste
vide ; une affirmation invalide déclenche une erreur Pydantic. Le brouillon
produit cinq objets validés, chacun avec son identifiant, sa RQ, son texte
et ses références de preuve.

## 4. TODO 2 — Couverture des RQ

La couverture est calculée par :

```python
len(sections & required_rqs) / max(1, len(required_rqs))
```

L'intersection exclut les RQ non demandées et les ensembles empêchent de
compter plusieurs fois une même section. Le brouillon couvre 3/3 RQ, soit
100 %. Avec deux sections, il couvre 2/3 RQ, soit environ 66,67 %.
L'ensemble requis vide ne provoque pas de division par zéro ; la formule
pédagogique donne alors 0.

## 5. TODO 3 — Preuves, métriques et verdict

Les quatre expressions ont les types et rôles suivants :

| Expression | Type attendu | Résultat produit |
| --- | --- | --- |
| `selected` | `list[EvidenceItem \| None]` | Retrouve chaque preuve citée et conserve `None` pour tout identifiant inconnu. |
| `overlap` | `set[str]` | Retient les mots communs entre l'affirmation et le texte source retenu. |
| `verdict` | chaîne `ACCEPT` ou `REVISE` | Accepte seulement si le score atteint le seuil et si le feedback est vide. |
| `repair_target` | chaîne `rag` ou `writing` | Renvoie vers RAG si une affirmation manque de soutien, sinon vers Writing. |

Le texte source est `finding` s'il est renseigné, sinon `text`. La
tokenisation met le texte en minuscules et conserve les mots d'au moins
quatre caractères. Une preuve est considérée comme lexicalement soutenante
si au moins deux mots sont communs. Ce seuil évite qu'un seul mot suffise,
mais ne démontre pas une implication sémantique.

Les métriques calculées sont :

- **Couverture :** RQ requises présentes dans les sections / RQ requises.
- **Validité des citations :** affirmations citant uniquement des preuves connues / affirmations.
- **Fidélité lexicale :** affirmations classées `supported` / affirmations.
- **Score :** moyenne de ces trois valeurs.

La validité des citations est donc calculée par affirmation, pas par
référence individuelle. Une citation existante peut rester insuffisante.

| Mesure | Brouillon | Note corrigée |
| --- | ---: | ---: |
| Couverture | 100 % | 100 % |
| Validité des citations | 100 % | 100 % |
| Fidélité lexicale | 80 % | 100 % |
| Score global | 93,33 % | 100 % |
| Verdict | `REVISE` | `ACCEPT` |

Le score du brouillon dépasse le seuil de 80 %, mais A5 produit encore un
feedback : le verdict reste donc `REVISE`, avec `repair_target="rag"`.

## 6. TODO 4 — Juge LLM structuré

`build_llm_judge()` construit une fois l'adaptateur
`with_structured_output(QualityJudgeDecision)`. À chaque évaluation, le prompt
transmet le rapport et `rule_report.model_dump()`, puis demande un verdict,
un score borné entre 0 et 1 et au moins un élément de feedback.

Un seul `structured.invoke(prompt)` est effectué. Une réponse déjà typée
`QualityJudgeDecision` est conservée ; un dictionnaire est validé avec
`QualityJudgeDecision.model_validate()`.

La fusion fournie conserve le verdict le plus contraignant, prend le minimum
des deux scores et fusionne les feedbacks sans doublon. Le juge ne peut donc
pas transformer une citation inconnue refusée par les règles en rapport
acceptable. Les tests vérifient ce cas ainsi que le rejet d'une réponse invalide.

Les appels du juge ont été **simulés dans les tests**. Aucun fournisseur LLM
réel n'a été sollicité pendant la réalisation.

## 7. TODO 5 — Réflexion bornée

La boucle effectue une évaluation initiale, puis au plus `max_revisions`
appels au Writer. `ACCEPT` arrête immédiatement la boucle. Une demande
`ESCALATE` du juge, ou la fin du budget sans acceptation, arrête également
la boucle sans nouvel appel au Writer.

Le Writer reçoit le rapport courant et `quality.feedback`. Chaque
évaluation est conservée dans `history` avec son numéro de révision.
Lors de l'épuisement, le verdict final est `ESCALATE` ; l'historique conserve
les verdicts observés avant cette décision d'arrêt, conformément au squelette.

| Expérience | Révisions autorisées | Appels Writer | Évaluations | Verdict final |
| --- | ---: | ---: | ---: | --- |
| Writer renvoyant la correction fournie | 1 | 1 | 2 | `ACCEPT` |
| Writer renvoyant le brouillon inchangé | 1 | 1 | 2 | `ESCALATE` |

Le second scénario montre qu'une répétition ne crée pas de preuve supplémentaire.

## 8. TODO 6 — Handoff et permissions

La permission est vérifiée par :

```python
handoff.target in allowed.get(handoff.source, set())
```

Une source inconnue ou une cible non autorisée déclenche `PermissionError`.
Les contrôles fournis rejettent ensuite toute preuve absente de l'état
partagé et tout budget négatif avec `ValueError`. Aucun LLM n'est appelé
par cette validation.

Pydantic bloque normalement un budget négatif dès la construction. Le test
du contrôle runtime emploie `model_copy(update=...)`, qui permet de simuler
un handoff modifié après sa validation initiale.

## 9. TODO 7 — Pipeline fixe

Le handoff de chaque étape contient la source, la cible et l'artefact de
la source courante. Il est validé avant d'être ajouté à la trace.

Trace observée :

```text
Search → Screening → RAG → Writing → Quality → ESCALATE
```

Le pipeline exécute les cinq agents une seule fois. Il ne répare pas A5 :
le QualityAgent retourne `REVISE`, puis le pipeline s'arrête avec `ESCALATE`.

## 10. TODO 8 — Supervision et routage

Le superviseur lit `state.quality.repair_target`. Le handoff
`quality → target` contient le feedback et la cible, avec le statut `partial`.
Il est validé et le budget est décrémenté avant l'appel au worker cible.

Pour A5, la trace complète obtenue est :

```text
Search → Screening → RAG → Writing → Quality
       → RAG → Writing → Quality → FINISH
```

Le suffixe est bien `quality→rag→writing→quality→finish`.
Un test distinct provoque une section manquante, sans défaut de preuve :
la cible devient `writing` et la réparation suit directement
`quality→writing→quality→finish`.

Chaque architecture utilise un état et des workers neufs. Le compteur du
Writer de la première expérience ne peut donc pas modifier la seconde.

| Résultat, budget initial de 8 | Pipeline | Superviseur |
| --- | ---: | ---: |
| Agents exécutés | 5 | 8 |
| Handoffs enregistrés | 4 | 7 |
| Budget restant | 4 | 1 |
| Score final évalué | 93,33 % | 100 % |
| Verdict QualityAgent | `REVISE` | `ACCEPT` |
| Statut de l'orchestration | `ESCALATE` | `FINISH` |

Le squelette compte le premier contrôle qualité dans `actions`, tandis que
`budget_left` est décrémenté par handoff. Le plafond `max_handoffs` est
appliqué à ce compteur `actions` dans le code fourni : ces compteurs ne sont
donc pas interchangeables. L'expérience principale utilise 8 pour les deux
limites afin de permettre la réévaluation finale. Dans cette implémentation,
la limite 7 interrompt la réparation avant cette réévaluation.

Une correction ponctuelle du statut terminal fait désormais retourner
`BUDGET_EXHAUSTED` si le plafond `max_handoffs` est atteint, même si
`budget_left` reste positif. Un routage humain ou un verdict `ESCALATE`
s'arrête sans relancer les workers.

## 11. Évolution de A5

| Version | Texte | Preuve | Statut lexical |
| --- | --- | --- | --- |
| A5 | La précision dépasse celle des experts. | E8 | `unsupported` |
| A5R | Le prompt doit être calibré et contrôlé dans le domaine avant déploiement. | E8 | `supported` |

A5 n'a aucun mot commun avec le champ `finding` de E8. A5R en partage quatre :
`avant`, `doit`, `prompt` et `être`. La correction remplace la comparaison
non étayée par une recommandation conforme au sujet de la preuve fournie.
La section RQ3 référence désormais A5R.

Dans le runtime fourni, le worker RAG rejoue le même artefact et le Writer
renvoie une correction déjà préparée au second appel. Cette expérience
valide le chemin de contrôle et la réévaluation ; elle ne mesure pas une
capacité autonome de recherche ou de rédaction d'un modèle.

## 12. Vérification

Résultat de la suite complète :

```text
99 passed
```

Cela comprend les **68 tests fournis** et **31 cas complémentaires**. Ils
contrôlent notamment les citations inconnues, les violations de handoff,
les réponses du juge sous deux formes, l'arrêt de la réflexion, les deux
routes de réparation et les budgets insuffisants.

Le contrôle avec `streamlit.testing.v1.AppTest` a exécuté le chargement
initial, le formulaire de Phase 1 puis celui de Phase 2. Les budgets 5 et 7
produisent `BUDGET_EXHAUSTED` ; 8 et 10 permettent `FINISH`. Aucune exception
applicative ni erreur affichée n'a été observée. Streamlit émet des messages
de dépréciation pour `use_container_width` dans l'interface fournie ; ils
n'empêchent pas ces scénarios.

`python -X utf8 main.py` génère les résultats et la note corrigée. Le mode
de démonstration et le nombre réel d'appels LLM, zéro, sont explicités dans
le JSON. Le mode LLM réel n'a pas été validé auprès d'un service externe.

## 13. Reproduire sous Windows

Depuis le dossier `SLRResearchAI-TD08`, avec les dépendances installées :

```powershell
.\run_tests.ps1
python -X utf8 main.py
python -X utf8 -m streamlit run streamlit_app.py
```

La validation sur cette machine a utilisé `C:\Python312\python.exe`
(Python 3.12.6, Pydantic 2.12.4, pytest 9.1.1 et Streamlit 1.64.0).
Le lanceur détecte un Python équipé de pytest dans le PATH, puis essaie
`C:\Python312\python.exe` si nécessaire. Il accepte aussi `-PythonExecutable`
pour sélectionner cet interpréteur ou celui d'un environnement virtuel.
Le mode déterministe ne nécessite
ni clé API ni serveur Ollama.

## 14. Limites

La couverture vérifie la présence des sections, pas leur exhaustivité
scientifique. Le recouvrement lexical peut produire des faux positifs,
notamment avec des mots courants, et manquer des paraphrases correctes.
Il ne contrôle ni les contradictions ni la justesse des valeurs numériques.
Le score n'est donc pas une probabilité que le rapport soit exact.

Un statut `ACCEPT` signifie que les règles de ce TD ont été satisfaites.
Les références scientifiques n'ont pas été revérifiées dans les publications
originales. Le corpus reste pédagogique et la note ne constitue pas une
revue systématique publiable.
