# Compte rendu TD05 — Construire, comparer et vérifier un RAG classique

**Projet :** SLRResearchAI  
**Date :** 20 octobre 2026  
**Validation :** 49 tests réussis ; interface Streamlit vérifiée en mode contrôlé.

## 1. Objectif et travail réalisé

Le TD05 ajoute un pipeline RAG classique au projet cumulatif des TD01 à TD04.
Le programme conserve un ordre fixe : préparation du corpus, découpage,
retrieval, construction du contexte, génération structurée et vérification
de la preuve. Le générateur reçoit uniquement les passages du Top-k.

Les dix TODO ont été complétés dans `slrresearch/rag_pipeline.py`, sans
modifier les modules des TD précédents ni les tests fournis.

| TODO | Fonction | Solution réalisée |
|---|---|---|
| 1 | `validate_chunking` | Refuser `size <= 0`, `overlap < 0` et `overlap >= size` ; retourner `size - overlap`. |
| 2 | `chunk_pages` | Construire un `Chunk` conservant `paper_id`, `chunk_id`, `page` et `text`. |
| 3 | `lexical_retrieve` | Trier les scores TF-IDF/cosinus par ordre décroissant et conserver `[:k]`. |
| 4 | `cosine_similarity` | Diviser le produit scalaire par le produit des normes ; retourner `0.0` si une norme est nulle. |
| 5 | `semantic_retrieve` | Trier les similarités des embeddings par ordre décroissant et conserver `[:k]`. |
| 6 | `retrieval_metrics` | Calculer précision et rappel à partir des identifiants pertinents annotés. |
| 7 | `build_context` | Joindre les blocs de provenance et de texte avec `"\n\n"`. |
| 8 | `build_llm_extractor` | Appeler `structured_model.invoke(prompt)` avec le contrat `ProposedEvidence`. |
| 9 | `verify_evidence` | Rechercher le `chunk_id` annoncé parmi les seuls chunks récupérés. |
| 10 | `run_rag` | Contrôler la proposition avec `verify_evidence(proposal, selected)`. |

## 2. Continuité et préparation du corpus

`load_rag_handoff()` joint les artefacts fournis par `paper_id` et conserve
uniquement les articles trouvés, définitivement inclus et disponibles.

| Étape | Nombre observé |
|---|---:|
| Articles trouvés au TD03 | 3 |
| Articles inclus au TD04 | 2 |
| Documents disponibles | 2 |
| Documents transmis au RAG | 2 |
| Chunks obtenus | 4 |

Les deux articles transmis sont `W4402635906` et `W4410000915`.
`W4410813691` est exclu du corpus RAG. Les quatre pages pédagogiques sont
courtes : avec `size=1000` caractères et `overlap=0`, chacune produit un chunk.
Le découpage reste indépendant pour chaque page et la numérotation commence à 1.

## 3. Protocole de comparaison

Les deux retrievers utilisent les mêmes quatre chunks, les trois questions
de `artifacts/rag_evaluation.json` et `k=2`.

- Le retriever lexical utilise la tokenisation, TF-IDF et le cosinus fournis.
- Le retriever sémantique utilise ici les vecteurs pédagogiques contrôlés de
  l'interface : le chunk annoté pertinent reçoit `[1, 0]`, les autres `[0, 1]`,
  et la question `[1, 0]`.
- La génération est contrôlée, sans appel à un LLM réel.

Les vecteurs contrôlés utilisent directement les annotations. Ils vérifient
le fonctionnement du classement mais ne mesurent pas la qualité d'un véritable
modèle d'embeddings. Aucun résultat Ollama ou Groq n'est revendiqué.

Pour `hits`, le nombre de chunks retournés appartenant aux références :

```text
Precision@k = hits / nombre de chunks retournés
Recall@k    = hits / nombre de chunks pertinents annotés
```

Les métriques valent zéro si aucun passage n'est retourné ; le rappel vaut
également zéro si l'ensemble des références est vide.

## 4. Résultats observés

Les passages, leurs scores et les métriques sont conservés dans
`artifacts/rag_comparison.json`.

| Question | Retriever | Premier chunk | Precision@2 | Recall@2 |
|---|---|---|---:|---:|
| Q1 — Niveaux de rappel | Lexical | `W4402635906_p1_c1` | 0,50 | 1,00 |
| Q1 — Niveaux de rappel | Sémantique contrôlé | `W4402635906_p2_c1` | 0,50 | 1,00 |
| Q2 — Supervision humaine | Lexical | `W4402635906_p1_c1` | 0,00 | 0,00 |
| Q2 — Supervision humaine | Sémantique contrôlé | `W4410000915_p2_c1` | 0,50 | 1,00 |
| Q3 — Stratégies comparées | Lexical | `W4402635906_p1_c1` | 0,50 | 1,00 |
| Q3 — Stratégies comparées | Sémantique contrôlé | `W4402635906_p1_c1` | 0,50 | 1,00 |

Les questions sont en français et les passages en anglais. Pour Q1 et Q2,
tous les scores lexicaux valent zéro : le tri stable conserve l'ordre du
corpus. Q1 récupère tout de même son passage pertinent en deuxième position,
alors que Q2 ne le récupère pas. Un rappel de 1,00 pour Q1 ne signifie donc
pas que le retriever a reconnu la pertinence du passage.

Pour Q3, le terme commun « prompting » permet un classement lexical utile :
les deux premiers scores valent environ 0,0436 et 0,0426. Le passage décrivant
l'expérience est classé avant celui décrivant l'usage général des LLM.

Chaque question possède un seul chunk annoté pertinent. Lorsque ce chunk
figure dans un Top-2, la précision vaut 1/2 et le rappel 1/1. Les métriques
ne distinguent pas sa première et sa deuxième position dans ce Top-2.

## 5. Réponses aux questions du corpus pédagogique

**Q1 — Quels niveaux de rappel sont rapportés selon les stratégies ?**

Le passage fourni rapporte un rappel de 0,82 pour input-output, de 0,97 pour
zero-shot chain of thought et de 1,0 pour few-shot chain of thought et majority
voting. Source : `W4402635906`, page 2, chunk `W4402635906_p2_c1`.

**Q2 — Pourquoi une supervision humaine reste-t-elle nécessaire ?**

Le passage mentionne le contrôle qualité rigoureux, la reproductibilité,
la gestion des coûts et l'amélioration des prompts. Source : `W4410000915`,
page 2, chunk `W4410000915_p2_c1`.

**Q3 — Quelles stratégies de prompting ont été comparées ?**

L'expérience compare standard input-output prompting, zero-shot chain of
thought, few-shot chain of thought et majority voting. Source : `W4402635906`,
page 1, chunk `W4402635906_p1_c1`.

Ces réponses décrivent les extraits pédagogiques livrés avec le TD ; elles
ne constituent pas une vérification indépendante des articles originaux.

## 6. Preuve exportée et limites du contrôle

`artifacts/verified_evidence.json` contient une preuve pour Q1, obtenue en
exécutant `run_rag()` avec le Top-2 sémantique contrôlé et un extracteur
déterministe. La citation conserve le passage complet, notamment ses nombres
décimaux. Son article est `W4402635906`, son chunk `W4402635906_p2_c1`,
sa page `2` et son statut `verified`.

La politique fournie distingue trois statuts :

- `verified` : citation présente après normalisation des espaces et de la casse,
  avec article et page cohérents ;
- `human_review` : citation proche selon le seuil fourni, ou citation présente
  avec une provenance incohérente ;
- `rejected` : chunk inconnu ou citation non reconnue par les règles précédentes.

Ce contrôle vérifie la citation et sa provenance. Il ne démontre pas que la
réponse répond à la question ni que la citation justifie toute l'affirmation.
Dans l'interface, une génération contrôlée sur un premier passage non pertinent
peut ainsi recevoir le statut `verified` : une citation authentique peut être
hors sujet. Le score de retrieval ne constitue pas non plus une validation
scientifique.

## 7. Validation et reproduction

La suite fournie a été exécutée sous Windows avec Python 3.12.6 :

```text
49 passed in 1.72s
```

Cela comprend 10 tests des TODO du TD05, 2 tests de transmission des artefacts
et 37 tests de non-régression des TD01 à TD04. Aucun test fourni n'a été modifié.
`main.py` s'exécute également avec succès.

L'interface a été exercée avec `streamlit.testing.v1.AppTest` : chargement du
corpus, comparaison des trois questions et génération contrôlée avec chacun
des deux retrievers, soit six parcours de génération sans erreur. Le mode
LLM réel, les embeddings Ollama réels et l'extraction de PDF n'ont pas été
exécutés pendant cette validation.

Depuis le dossier `SLRResearchAI-TD05` :

```powershell
python -X utf8 -m pytest -v --basetemp .pytest_cache/td05-temp
python -X utf8 main.py
python -X utf8 -m streamlit run streamlit_app.py
```

Pour reproduire la comparaison dans Streamlit, conserver `Top-k = 2`,
sélectionner les embeddings `Contrôlés`, puis lancer la comparaison pour
chaque question. Choisir ensuite un contexte et le générateur `Contrôlé`
avant d'exécuter le pipeline. Chaque exécution de l'interface remplace
`artifacts/verified_evidence.json` par la preuve courante.
