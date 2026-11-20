# Baselines, ablations et validité des comparaisons

Les comparaisons A–D sont implémentées dans `evaluation.benchmarks`. Le mode humain est une variante de `Supervisor`, sans comparaison E automatisée. La matrice qualifie ce que les artefacts permettent de conclure. Les paramètres et validations de chaque run restent dans les fichiers `inputs.json`, `outputs.json`, `events.json`, `prompts.json` et `metadata.json` quand disponibles. [Code](../../evaluation/benchmarks.py) · [Guide initial](../../EVALUATION.md)

| Comparaison | IMPLÉMENTÉ | TESTÉ SUR FIXTURES | TESTÉ LIVE | SCIENTIFIQUEMENT COMPARABLE | PAS ENCORE TESTÉ |
| --- | --- | --- | --- | --- | --- |
| A · Fixed Search / ReAct Search | Oui, même passerelle d'outils | Oui, même catalogue et 429 simulé | ReAct dans des revues réelles. Paire live **NON VÉRIFIÉE** | Ordre et résultats comparables dans le seul scénario contrôlé | Recherche externe répétée, rappel et précision documentaires |
| B · Règles / LLM | Oui, baseline indépendante actuelle et politique LLM | Données gelées, labels synthétiques utilisés seulement en tests de formules | Oui, neuf appels Ollama dans le bras LLM historique. Version courante de la paire **NON VÉRIFIÉE** | Volumes et calculs sur les mêmes 15 notices, sans comparaison de l'exactitude | Annotation indépendante avec prédictions masquées, adjudication et réplication de la version actuelle |
| C · Classical / Agentic RAG | Oui avec le même moteur lexical de base, embeddings optionnels | Oui, trois cas avec références pédagogiques | Agentic en production. Un run classique historique en cache. Paire simultanée live **NON VÉRIFIÉE** | Oui sur les trois cas et leur top-k. Portée limitée au corpus TD06 | Jugements indépendants sur abstracts réels, répétitions, budget/couts et embeddings |
| D · Fixed Pipeline / Supervisor | Oui, harness TD08 et réglage fixe de production, deux chemins distincts | Oui, même brouillon initial, même catalogue, correction fournie | Superviseur de production exécuté. Paire de production live **NON VÉRIFIÉE** | Contrôles de transition et score déterministe sur un scénario préconstruit | Correction générée en aveugle, référence humaine, plusieurs cas, comparaison appariée du code de production |
| Modes Automatic / Human-in-the-Loop | Oui | Oui, tests d'intégration, pas de benchmark apparié | Des revues automatiques et des checkpoints humains sont attestés | Comparaison interventionnelle **NON VÉRIFIÉE** | Même lot, politique, RQ, budget, références, protocoles humains et mesure du temps |

## A. Fixed Search versus ReAct Search

`fixed_vs_react` ouvre le [catalogue pédagogique TD03](../../experiments/datasets/search_catalog.json) de quatre entrées. Même phrase `systematic review screening`, limite 2 par source, trois tentatives logiques d'outil. Les deux variantes voient le même HTTP 429 **injecté** sur OpenAlex. Fixed continue via Semantic Scholar puis Crossref. ReAct intercale Crossref immédiatement après l'observation négative, puis tente Semantic Scholar. **Trois notices uniques et zéro doublon** pour chaque bras. Temps total du benchmark local de référence 0,0016055 s, temps de fixture et non réseau. Les DOI de la fixture sont des exemples. L'ordre montre la réaction programmée. Aucun gain de qualité documentaire ni de latence réseau ne peut en être déduit.

Artefacts répétés, valeurs de sortie identiques pour ces indicateurs. [Premier run local](../../experiments/runs/2026-11-20T11-50-16-a-0be73f1280/metadata.json) · [Run de référence](../../experiments/runs/2026-11-20T11-55-49-a-12e64f727f/outputs.json). Deux replays depuis l'UI existent dans `/app/data/experiments/runs/2026-11-20T13-59-48-a-c62c8851bb` (0,005539 s) et `/app/data/experiments/runs/2026-11-20T15-57-35-a-ff0cb268d7` (0,003032 s), même résultat, aucune inférence externe.

À comparer ensuite avec un snapshot de réponses uniformes et plusieurs scénarios fixés, en figeant limites, fenêtres de temps et stockage de réponses. Mesurer séparément l'ordre, la couverture des références connues et la disponibilité. Le comportement live de ReAct seul ne donne aucune différence contre Fixed.

## B. Règles versus LLM Screening

Le code courant `screening_pair` fournit les **mêmes études dédoublonnées** aux deux bras. Les règles utilisent les termes `slr, screening, systematic review` et `medicine, clinical trial` comme signaux négatifs. Le bras LLM emploie les critères rédigés et `screen_papers`. Les valeurs `raw_decision_metrics` et `automatic_policy_metrics` distinguent verdict brut et verdict après la politique. Les labels sont facultatifs et la comparaison du bruit de transport est bornée par l'adapter.

Dans l'[exécution historique b-1109e9b08f](../../experiments/runs/2026-11-20T11-57-38-b-1109e9b08f/metadata.json), le snapshot compte **15 notices**. Le bras règles produit **14** verdicts bruts définitifs et **6** décisions finales en attente. Le bras LLM produit **5** verdicts bruts définitifs et **10** en attente. Neuf appels Ollama `qwen2.5:7b` réussis, température 0, cache désactivé, **6 036** tokens d'entrée et **1 484** de sortie, 48,8208 s cumulées d'inférence et 49,1616 s au total. Les nombres « brut définitif » et « final en attente » ne sont pas des compléments. Aucun label indépendant, donc precision/recall/F1/matrice **null**. Le `config.screen=hybrid` historique et le hash de `slr/screen.py` diffèrent de la politique actuelle. Ce journal ne valide pas les performances du `llm-evidence-v1` actuel. [Entrées](../../experiments/runs/2026-11-20T11-57-38-b-1109e9b08f/inputs.json) · [Résultats](../../experiments/runs/2026-11-20T11-57-38-b-1109e9b08f/outputs.json) · [Événements](../../experiments/runs/2026-11-20T11-57-38-b-1109e9b08f/events.json)

À refaire après annotation indépendante. Publier nombre d'appariés/décidés, abstentions et abstentions positives avec les métriques. Ajouter une analyse où l'abstention représente une demande de revue humaine et mesurer son coût. Ne pas utiliser les arbitrages opérationnels comme vérité terrain indépendante.

## C. Classical RAG versus Agentic RAG

`retrieval_pair` utilise les passages de PDF TD06. Découpage de **1 000 caractères sans chevauchement** dans le benchmark, différent des 900/90 en production. Chaque cas est testé avec le même corpus, mêmes labels réservés à l'évaluation, même top-k et même plafond de deux appels. Le classique utilise un appel par construction. L'adaptatif lexical peut en tirer deux. Pas d'embeddings lors des deux exécutions enregistrées. Les labels existent dans la fixture et leurs auteurs/protocole indépendant n'y sont pas consignés. [Cas TD06](../../experiments/datasets/retrieval_cases.json) · [Résultats de référence](../../experiments/runs/2026-11-20T11-55-49-c-a4bd19b5e3/outputs.json) · [Premier run](../../experiments/runs/2026-11-20T11-50-16-c-daa48b4fb2/metadata.json)

| Cas | P@1/R@1 classique → adaptatif | Couverture de facettes | Appels classique → adaptatif |
| --- | --- | --- | --- |
| Q1 | 0/0 → 0/0 | 0 → 0 | 1 → 2 |
| Q2 | 0/0 → 1/1 | 0 → 1 | 1 → 2 |
| Q3 | 1/1 → 1/1 | 1 → 1 | 1 → 1 |

Pour Q1 et Q2, le classique ne retourne aucun chunk. P@1 vaut 0 avec la définition sur k. La précision parmi les chunks retournés est alors indéfinie. Dans Q2, l'adaptation trouve le passage étiqueté au prix d'un appel de plus. Ce cas unique n'établit aucune performance générale. Au total 3 contre 5 opérations. Refaire les deux variantes sur des résumés annotés, avec plusieurs domaines et plusieurs k. Maintenir les mêmes budgets ou afficher le compromis couverture/coût.

## D. Fixed Pipeline versus Quality-Driven Supervisor

`orchestration_pair` fournit un brouillon TD08, le catalogue TD07 et une **révision déjà écrite** par le cours. Même état initial, budget 8, même vérificateur déterministe avec seuil 0,80 et contrôles de feedback. Aucun Ollama ou recherche externe. Pipeline fixe `ESCALATE` après 5 actions, score 0,933333 inchangé. Superviseur `FINISH` à 8 actions après `quality→rag→writing→quality`. Le score passe de 0,933333 à 1, et la correction A5R remplace A5. La démonstration porte sur la boucle et les contrats, et ne mesure pas la capacité d'un LLM à produire la correction. Les états du harness sont distincts des états `ReviewRun`. [Sortie et handoffs](../../experiments/runs/2026-11-20T11-55-49-d-3f4df3caad/outputs.json) · [Premier run](../../experiments/runs/2026-11-20T11-50-16-d-5debed397d/metadata.json)

À évaluer en production sur les mêmes preuves et prompts, avec révisions réellement générées, un juge indépendant et un budget d'inférence déclaré. Les sorties preuves, citations structurelles et entailment doivent être évaluées séparément.

## Automatic versus Human-in-the-Loop

Les deux modes exécutent les mêmes agents avec les mêmes règles de sélection auto. Le mode humain ajoute les points de pause et la possibilité d'écraser le verdict. L'automatique omet les incertains et filtre les affirmations non résolues. Les témoins disponibles diffèrent par leur époque, leur cache et parfois leur sujet. Le replay qui journalise `retry_retrieval` n'est pas une expérience HITL. Pour isoler la valeur du mode humain, geler un lot et les prédictions, donner aux évaluateurs un protocole et mesurer le taux d'override, l'accord entre annotateurs, le temps humain, la couverture et les affirmations réellement retenues. [Traces HITL](HITL_WORKFLOW.md) · [Résultats](EXPERIMENTS_AND_RESULTS.md)
