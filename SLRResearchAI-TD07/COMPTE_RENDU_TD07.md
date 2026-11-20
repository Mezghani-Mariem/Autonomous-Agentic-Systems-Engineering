# Compte rendu TD07 — Plan-and-Execute

**Projet :** SLRResearchAI  
**Date :** 10 novembre 2026  
**Sujet :** planification, exécution contrôlée et replanning sur un mini-corpus pédagogique.

## 1. Objectif et périmètre

Le TD07 exploite le contrat de transmission `artifacts/td06_evidence.json`.
Le fichier contient **4 études primaires, 8 unités de preuve et 3 questions de
recherche**. E7 et E8 réutilisent des études déjà présentes : huit extractions
ne représentent donc pas huit études indépendantes.

L'objectif est de produire une **note de synthèse pédagogique** en séparant
la proposition d'un plan, sa validation, l'exécution des étapes et la révision
du plan restant. Le corpus n'est pas exhaustif et la note ne constitue pas une
revue systématique publiable.

## 2. Livrables

- [Code complété](slrresearch/plan_and_execute.py) : les six TODO et leurs sous-parties.
- [Tests complémentaires](tests/test_td07_regressions.py) : 24 cas de régression.
- [Lanceur Windows](run_tests.ps1) : tests avec un dossier temporaire propre à chaque exécution.
- [Note de synthèse finale](artifacts/td07_note_synthese.md) : trois sections après replanning.
- [Résultats et traces JSON](artifacts/td07_execution.json) : plans, métriques et deux expériences.

Les contrats, le runtime contrôlé, le corpus, l'interface et les tests fournis
ont été conservés.

## 3. Réalisation des six TODO

### TODO 1 — Direct, CoT structurée et ToT

`build_planning_prompt()` conserve la même spécification et le même catalogue
de preuves, avec des consignes propres à chaque stratégie.

| Stratégie | Protocole de l'adaptateur LLM | Appels |
| --- | --- | ---: |
| Direct | Produire directement un `PlanCandidate`. | 1 |
| CoT structurée | Produire un `PlanningAnalysis`, le valider, puis transmettre cette analyse à l'appel qui construit le plan. | 2 |
| ToT | Produire trois candidats indépendants, éliminer les candidats invalides et sélectionner le meilleur. | 3 |

Les réponses dictionnaires sont converties avec `model_validate()`. Pour ToT,
chaque candidat est validé avant son évaluation. Le score est comparé dans
l'ordre : `rq_coverage`, `consistency`, puis `section_coverage`. Si aucun
candidat n'est valide, une erreur explicite est levée.

L'adaptateur fourni harmonise ensuite l'ordre et les dépendances du plan pour
la comparaison expérimentale.

### TODO 2 — Validation du plan

`validate_plan()` refuse :

1. les identifiants d'étapes dupliqués ;
2. plusieurs étapes principales pour la même RQ ;
3. une preuve absente de la liste autorisée ;
4. une dépendance vers soi-même ;
5. une dépendance inconnue ou placée après l'étape ;
6. l'absence d'une RQ obligatoire.

La validation précède l'exécution et est répétée après chaque révision.
La structure peut être valide même si une facette scientifique demandée
n'est pas disponible : cette insuffisance est détectée pendant l'exécution.

### TODO 3 — Comparaison des stratégies

`compare_planning_strategies()` appelle successivement `direct`, `cot` et
`tot` avec le même objectif et la même liste de preuves. Chaque résultat
conserve la stratégie, le plan et ses métriques.

### TODO 4 — Exécution autorisée

`execute_step()` vérifie d'abord les dépendances terminées, puis les preuves
autorisées. Une étape bloquée reste observable et ne consomme aucun appel
d'outil selon son `StepResult`.

Les facettes disponibles proviennent uniquement des preuves sélectionnées.
Une synthèse qui exige une facette absente retourne `insufficient_evidence`.
Le mode `limitation` permet de rédiger les résultats disponibles en signalant
la limite ; les éventuelles facettes manquantes restent présentes dans le résultat.

### TODO 5 — Plan fixe et retry

`run_classic()` accepte une section seulement si l'étape réussit **et** si
ses citations appartiennent aux études autorisées. Les réessais sont bornés
par `max_retries` et le budget d'actions. Ils conservent le plan et les preuves.

Répéter une étape ne crée pas la validation prospective absente du corpus :
le plan Direct finit donc par s'abstenir.

### TODO 6 — Replanning contrôlé

`run_with_replanning()` travaille sur une copie du plan initial. Il autorise
une révision lorsque `revisions < max_revisions` et qu'une action reste possible.
Le replanner reçoit le plan courant, l'étape en échec et les facettes couvertes.

Les identifiants déjà terminés doivent rester présents dans le nouveau plan,
puis celui-ci est revalidé. Dans le scénario fourni, seule la dernière étape
est révisée : elle passe en mode `limitation` et signale explicitement l'absence
de validation prospective, sans ajouter de preuve.

## 4. Expérience 1 — Trois plans, même exécuteur

Configuration : mode contrôlé, `max_retries=0`, `max_actions=6`.

| Plan | Ordre des RQ | Plan valide | Sections produites | Actions | Statut |
| --- | --- | --- | ---: | ---: | --- |
| Direct | RQ1 → RQ2 → RQ3 | Oui | 2 | 3 | `abstained` |
| CoT | RQ3 → RQ1 → RQ2 | Oui | 3 | 3 | `completed` |
| ToT | RQ2 → RQ1 → RQ3 | Oui | 3 | 3 | `completed` |

Pour les trois plans, les métriques fournies donnent 100 % de couverture des
RQ, de complétude des étapes et de cohérence des dépendances. Pourtant,
Direct exige `prospective_validation` dans S3, alors qu'aucune preuve du
mini-corpus ne couvre cette facette.

La différence de résultat dépend donc de l'ordre **et des exigences des plans
contrôlés fournis**. Cette expérience ne démontre pas une supériorité générale
de CoT ou ToT.

## 5. Expérience 2 — Même plan Direct, deux politiques

Configuration : même plan initial, `max_actions=6`, un réessai pour la variante
classique et une révision autorisée pour la variante adaptative.

| Variante | Sections | Actions | Révisions | Statut |
| --- | ---: | ---: | ---: | --- |
| Plan fixe avec retry | 2 | 4 | 0 | `abstained` |
| Avec replanning | 3 | 4 | 1 | `completed` |

Trace du plan fixe :

```text
S1 continue → S2 continue → S3 retry → S3 abstain
```

Trace avec replanning :

```text
S1 continue → S2 continue → S3 replan → S3 continue → S3 finish
```

Le replanning conserve les deux premières sections. La troisième expose les
mécanismes étayés et la lacune de validation prospective. Le statut `completed`
signifie que le plan révisé a été exécuté ; il ne signifie pas que cette lacune
scientifique a été résolue.

## 6. Vérification

La validation finale donne :

```text
91 passed
```

Cela comprend les 67 tests fournis, y compris ceux des TD précédents, et 24
cas complémentaires. Ces derniers contrôlent notamment les réponses LLM sous
forme de dictionnaires, l'utilisation de l'analyse CoT, la sélection ToT,
le rejet de candidats invalides, les budgets, les citations non autorisées
et la revalidation des plans révisés.

`python -X utf8 main.py` produit la comparaison attendue et la note finale.
Un contrôle avec `streamlit.testing.v1.AppTest` a également exécuté le
chargement initial et les deux formulaires de l'interface en mode contrôlé,
sans exception applicative.

Les protocoles LLM ont été testés avec des réponses simulées : **aucun service
LLM réel n'a été appelé**. En mode contrôlé, les champs `llm_calls` sont des
métadonnées fournies par le runtime ; ils ne représentent pas des appels
effectués. Le fichier JSON distingue donc ces métadonnées des appels réels,
au nombre de zéro lors de cette démonstration.

## 7. Reproduire sous Windows

Depuis le dossier `SLRResearchAI-TD07` :

```powershell
.\run_tests.ps1
& "C:\Python312\python.exe" -X utf8 main.py
& "C:\Python312\python.exe" -X utf8 -m streamlit run streamlit_app.py
```

Le lanceur utilise le Python système déjà équipé des dépendances sur cette
machine. Il désactive le cache pytest et génère un chemin temporaire unique
dans le dossier temporaire du compte qui lance la commande. Cela évite les
erreurs `PermissionError: [WinError 5]` lorsque `.pytest_cache` appartient à
un autre compte Windows. Pour choisir un autre Python disposant des dépendances :

```powershell
.\run_tests.ps1 -PythonExecutable "C:\chemin\vers\python.exe"
```

Pour le mode LLM réel, configurer le fournisseur selon `.env.example` et
disposer du service correspondant. Cette connexion n'a pas été validée ici.

## 8. Limites d'interprétation

La validation des citations contrôle leur appartenance à la liste autorisée ;
elle ne prouve pas à elle seule que chaque affirmation est soutenue par le
texte scientifique. La note reprend les extractions du corpus fourni, sans
nouvelle vérification des publications originales.

Une revue systématique complète demanderait notamment un protocole, une
recherche exhaustive, une déduplication, un double screening, un diagramme
PRISMA et une évaluation du risque de biais.
