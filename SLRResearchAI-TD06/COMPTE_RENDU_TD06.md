# Compte rendu TD06 — Du RAG classique au retrieval adaptatif

**Projet :** SLRResearchAI  
**Date :** 3 novembre 2026  
**Validation :** 65 tests réussis ; six scénarios Streamlit contrôlés vérifiés.

## 1. Objectif et réalisation

Le TD06 transforme le pipeline fixe du TD05 en une boucle de retrieval
adaptatif. Après chaque recherche, le système observe les facettes couvertes
par les passages mémorisés. Il termine si les informations attendues sont
présentes, cible les facettes manquantes avec le retriever sémantique si le
budget le permet, ou s'abstient lorsque le budget est épuisé.

```text
Question → décision → contrôle de l'action et du budget → retrieval
                ↑                                         ↓
                └──── état partagé ← mémoire ← observation

Couverture suffisante → finish → génération → vérification de la citation
Budget épuisé         → abstention → aucune génération
```

Les huit TODO ont été complétés dans `slrresearch/agentic_rag.py`. Les anciens
modules et les tests fournis ont été conservés. Le fichier ajouté
`tests/test_td06_integration.py` vérifie le protocole complet et les conditions
d'arrêt.

| TODO | Fonction | Solution réalisée |
|---|---|---|
| 1 | `evaluate_facets` | Ajouter `facet.id` dans la liste des facettes couvertes ou manquantes. |
| 2 | `controlled_decider` | Commencer par le lexical, terminer si la couverture est complète, s'abstenir si le budget est épuisé, sinon rechercher avec `semantic` et les `query_hint` manquants. |
| 3 | `execute_retrieval_action` | Vérifier l'action et le registre, puis appeler une seule fois `tools[action.tool](chunks, action.query, k)`. |
| 4 | `merge_candidates` | Dédupliquer par `chunk_id`, conserver le meilleur score, trier par score décroissant et limiter à `limit`. |
| 5 | `update_state_after_retrieval` | Reporter `covered` et `missing` dans l'état et dans la trace ; conserver la mémoire et incrémenter les compteurs. |
| 6 | `run_adaptive_retrieval` | Traiter `finish`, puis `abstain`, contrôler le budget avant tout nouvel appel, exécuter et mettre à jour le même état. |
| 7 | `compare_baseline_and_agentic` | Calculer les métriques sur les identifiants des passages des deux variantes avec les mêmes références annotées. |
| 8 | `build_llm_decider` | Retourner `structured_model.invoke(prompt)` avec le contrat `RetrievalAction`. |

## 2. Continuité des artefacts et corpus

Le corpus provient des artefacts pédagogiques fournis dans ce dépôt, sans
nouvel appel aux API scientifiques ni téléchargement de PDF.

```text
search_results.json → screening_decisions.json
                    → document_manifest.json + extracted_pages.json
                    → chunks TD05 + agentic_rag_cases.json
                    → comparaison et traces TD06
```

| Élément | Nombre observé |
|---|---:|
| Articles trouvés au TD03 | 3 |
| Articles inclus au TD04 | 2 |
| Documents disponibles et transmis au RAG | 2 |
| Chunks du corpus TD06 | 5 |
| Questions du protocole | 3 |

Les articles transmis sont `W4402635906` et `W4410000915`.
`W4410813691` reste exclu du RAG. Les cinq pages fournies produisent cinq
chunks avec `size=1000` et `overlap=0`. Les identifiants d'article, de chunk
et les numéros de page sont conservés.

## 3. Protocole expérimental

La baseline utilise un appel lexical avec `k=1`. La variante agentique commence
par le même appel lexical, conserve les passages et peut effectuer un second
appel sémantique. Le budget principal est de deux recherches et la mémoire
est limitée à quatre chunks. Chaque comparaison utilise les mêmes chunks,
la même question et les mêmes identifiants pertinents annotés.

Le mode contrôlé utilise `ProtocolEmbeddings` : la question reçoit le vecteur
`[1, 0]`, les chunks annotés pertinents reçoivent `[1, 0]` et les autres
`[0, 1]`. Ces vecteurs isolent la logique d'adaptation. Ils utilisent les
annotations et ne permettent donc pas de mesurer la qualité d'un vrai modèle
d'embeddings. Le générateur contrôlé cite le premier passage mémorisé ; aucun
LLM réel n'est nécessaire à cette expérience.

Les métriques sont calculées ainsi :

```text
hits      = nombre d'identifiants retournés appartenant aux références
précision = hits / nombre de passages retournés
rappel    = hits / nombre de passages pertinents annotés
```

Les champs du rapport sont nommés `precision_at_k` et `recall_at_k`. Pour la
variante agentique, ils portent sur toute la mémoire finale, qui peut contenir
plus de `k` passages après plusieurs cycles. La comparaison oppose donc ici
un Top-1 fixe à une mémoire pouvant cumuler deux résultats. Le gain doit être
interprété avec ce budget supplémentaire.

## 4. Résultats avec un budget de deux cycles

| Cas | Précision baseline | Rappel baseline | Précision agentique | Rappel agentique | Appels baseline / agent | Gain de rappel |
|---|---:|---:|---:|---:|---:|---:|
| Q1 — Niveaux de rappel | 0,00 | 0,00 | 0,50 | 1,00 | 1 / 2 | +1,00 |
| Q2 — Supervision humaine | 0,00 | 0,00 | 0,50 | 1,00 | 1 / 2 | +1,00 |
| Q3 — Stratégies de prompting | 1,00 | 1,00 | 1,00 | 1,00 | 1 / 1 | 0,00 |

**Q1.** Le premier passage lexical ne couvre pas `recall_values`. L'agent
construit la requête `recall values prompting strategies`, utilise le
sémantique et récupère `W4402635906_p2_c1`. La couverture devient complète.

**Q2.** Le lexical ne couvre pas `human_oversight`. La requête devient
`human oversight quality control reproducibility` ; le sémantique retrouve
`W4410000915_p2_c1`. L'agent conserve le premier passage et le passage
pertinent : un résultat pertinent parmi deux explique la précision de 0,50.

**Q3.** Le premier passage lexical, `W4402635906_p1_c1`, couvre déjà
`input_output`, `chain_of_thought` et `majority_voting`. L'agent termine
immédiatement, sans recherche supplémentaire.

Les trois états finaux portent le statut `completed`. Le second appel n'est
donc pas systématique : il dépend de l'observation du premier.

## 5. Budget, abstention et traçabilité

| Cas | Budget | Appels exécutés | Statut final | Génération |
|---|---:|---:|---|---|
| Q1 | 1 | 1 | `budget_exhausted` | Aucune |
| Q2 | 1 | 1 | `budget_exhausted` | Aucune |
| Q3 | 1 | 1 | `completed` | Preuve vérifiée |

Avec le corpus livré, Q3 ne montre pas d'abstention à budget 1 : son premier
passage suffit déjà. Q2 est l'exemple retenu pour démontrer l'abstention.
Le programme ne fabrique pas de réponse lorsque la couverture est incomplète.

Le budget est imposé avant chaque appel d'outil. Un test supplémentaire utilise
un décideur qui réclame toujours une recherche et un outil qui ne retourne
aucun résultat : avec un budget de deux, seuls deux appels sont exécutés.
Une abstention volontaire avant le premier appel est également testée et
produit le statut `abstained`.

Chaque recherche ajoute un événement contenant le cycle, l'outil, la requête,
le nombre de résultats, les facettes couvertes et manquantes, ainsi que la
raison de la décision. Les observations précédentes restent disponibles après
la mise à jour suivante. La mémoire conserve un seul exemplaire par `chunk_id`.

Dans le contrat fourni, la trace enregistre les recherches ; les actions
terminales `finish` et `abstain` se lisent dans le statut final, sans ajouter
d'événement d'outil.

## 6. Preuves et limites

En mode contrôlé, les trois cas terminés produisent une citation ayant le
statut `verified`. Les informations présentes dans les extraits sont :

| Question | Information dans le passage | Provenance |
|---|---|---|
| Q1 | Rappel de 0,82 pour input-output, 0,97 pour zero-shot chain of thought et 1,0 pour few-shot chain of thought et majority voting. | `W4402635906`, page 2, `W4402635906_p2_c1` |
| Q2 | Supervision pour le contrôle qualité, la reproductibilité, la gestion des coûts et l'amélioration des prompts. | `W4410000915`, page 2, `W4410000915_p2_c1` |
| Q3 | Standard input-output, zero-shot chain of thought, few-shot chain of thought et majority voting. | `W4402635906`, page 1, `W4402635906_p1_c1` |

Ces informations décrivent les extraits pédagogiques fournis. Le générateur
contrôlé produit une réponse générique et recopie un passage ; le tableau
ci-dessus explique le contenu des preuves plutôt qu'une synthèse générée par
un LLM.

La couverture est une heuristique : une facette est couverte dès qu'un de ses
mots-clés apparaît, sans raisonnement sur la pertinence ou la complétude de
la réponse. De même, `verified` contrôle la citation et sa provenance, sans
garantir que toute la réponse est scientifiquement justifiée. La fusion
compare aussi directement les scores lexical et sémantique conformément au
TD ; une application réelle devrait examiner leur calibration.

Le décideur LLM utilise une sortie structurée `RetrievalAction`. Le programme
garde l'autorisation des outils et le budget. L'interface fournie contient un
fallback contrôlé pour certaines décisions LLM invalides. Le test du TODO 8
vérifie l'appel structuré avec un modèle simulé ; les services Ollama/Groq,
les embeddings réels et ce fallback en situation réelle n'ont pas été exécutés.

## 7. Validation et artefacts produits

La suite complète a été exécutée avec Python 3.12.6 sous Windows :

```text
65 passed in 0.82s
```

Elle comprend les 57 tests fournis, dont les huit TODO TD06 et les 49 tests
des acquis TD01 à TD05, ainsi que huit cas d'intégration ajoutés.
`main.py` s'exécute avec succès pour les trois questions.

L'interface a été exercée avec `streamlit.testing.v1.AppTest` pour Q1, Q2 et
Q3, chacune avec les budgets 1 et 2, en conservant `Top-k=1` et les trois
modes contrôlés. Les six parcours ne présentent aucune erreur et vérifient
le statut final, les compteurs, la présence ou l'absence de génération et
l'écriture de l'artefact. Cette validation porte sur l'exécution de
l'interface ; elle ne constitue pas une inspection visuelle dans un navigateur.

| Fichier | Contenu |
|---|---|
| `artifacts/agentic_result_q1.json` | Comparaison Q1 à budget 2 et trace des deux recherches. |
| `artifacts/agentic_result_q2.json` | Comparaison Q2 à budget 2 et trace des deux recherches. |
| `artifacts/agentic_result_q3.json` | Comparaison Q3 et arrêt après le premier cycle. |
| `artifacts/agentic_result_q2_budget1.json` | Exemple d'abstention par épuisement du budget. |
| `artifacts/agentic_rag_result.json` | Dernière comparaison Streamlit : Q2, budget 2. |
| `artifacts/td06_ui_validation.json` | Paramètres, filiation du corpus et résumé des six parcours AppTest. |
| `A_RENDRE_TD06.zip` | Projet complété, compte rendu, tests et artefacts ; sans environnement virtuel, cache, `.git` ni `.env`. |

Les comparaisons exportées contiennent les métriques et les traces, conformément
au format fourni ; elles ne sérialisent pas la preuve finale. La preuve est
vérifiée dans les tests et affichée dans Streamlit. Chaque nouvelle comparaison
dans l'interface remplace `artifacts/agentic_rag_result.json`.

## 8. Reproduction sous Windows

Depuis `SLRResearchAI-TD06`, avec l'environnement existant du dossier parent :

```powershell
New-Item -ItemType Directory -Force .pytest_cache | Out-Null
..\venv\Scripts\python.exe -X utf8 -m pytest -v --basetemp .pytest_cache/td06-temp
..\venv\Scripts\python.exe -X utf8 main.py
..\venv\Scripts\python.exe -X utf8 -m streamlit run streamlit_app.py
```

Pour une installation indépendante après extraction du ZIP :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory -Force .pytest_cache | Out-Null
.\.venv\Scripts\python.exe -X utf8 -m pytest -v --basetemp .pytest_cache/td06-temp
.\.venv\Scripts\python.exe -X utf8 main.py
.\.venv\Scripts\python.exe -X utf8 -m streamlit run streamlit_app.py
```

Dans l'interface, conserver les modes contrôlés, `Top-k=1` et un budget de 2
pour reproduire la comparaison principale. Choisir ensuite Q2 avec un budget
de 1 pour observer l'abstention. Aucun fichier `.env` n'est nécessaire pour
ces parcours.
