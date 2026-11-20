# Dictionnaire des mesures

Sauf indication, exemples tirés de `b31a5129748e4569a8b8f2aac656e4f9`, confirmé dans `/app/data/slr.sqlite3` et `C:/Users/Lenovo/Downloads/evaluation-b31a5129.json`. L'exécution fraîche `000cca74…` sert de contraste pour les appels réels. **E** désigne une clé d'export, **T** une valeur tracée, **D** un résultat dérivé pendant l'audit. Un `null` indique une quantité indisponible ou indéfinie. Un zéro peut être une vraie valeur, ou un compteur de champ dont le stade ne s'est pas exécuté. Les tableaux ci-dessous précisent le sens des deux cas. [Code des métriques](../../evaluation/metrics.py) · [Inventaire](EXPERIMENTS_AND_RESULTS.md)

## Planification

Liens des formules. [review_metrics](../../evaluation/metrics.py) · [evaluate_plan](../../slr/course/plan_and_execute.py) · [Contrats](../../slr/models.py)

| Niveau et clé | Définition et calcul | Exemple b31a5129 | Interprétation et limite |
| --- | --- | --- | --- |
| E `planner.research_question_validity` | Nombre d'IDs distincts parmi RQ1–RQ3 / 3 | 1 | Les trois contrats sont présents. Pas de note de pertinence, de couverture du sujet ou de redondance sémantique |
| E `planner.query_validity` | Requêtes non blanches / 3 | 1 | Trois clés remplies. Les chaînes peuvent être identiques, comme dans ce run, et leur rappel est inconnu |
| E `repair_attempts` et `protocol_repairs` | Nombre de réparations de texte et de protocole. Chacun 0 ou 1 | 0 et 0 | Le protocole a validé dans cet état, sans mesure de difficulté sur des entrées rejetées |
| E `plan.valid` et `plan_validity_rate` | Booléen `validate_plan` et projection 1 si valide, 0 sinon. `errors` énumère les défauts | vrai, 1, liste vide | Un plan individuel valide. Le « taux » est un indicateur binaire pour ce plan, pas une moyenne d'échantillon |
| E `plan.rq_coverage` | Nombre de RQ attendues apparaissant dans les étapes / nombre attendu | 1 | Chaque RQ a une étape |
| E `plan.section_coverage` | Étapes avec objectif, facettes **et** IDs de preuve / étapes | 0 au plan initial | Le plan de recherche est construit avant collecte et utilise des étapes sans preuve. Ce zéro ne signifie pas protocole invalide |
| E `plan.consistency` | Nombre d'arêtes vers une dépendance connue et antérieure / nombre d'arêtes. Convention 1 si aucune | 1, aucune dépendance dans ce plan initial | Valeur triviale pour plan sans arêtes, ne teste pas une chaîne complexe |

## Acquisition et screening

Sources. [search_review et consolidate](../../slr/sources.py) · [Observations TD03](../../slr/course/runtime.py) · [ScreeningBatch.counts](../../slr/models.py) · [screen_paper](../../slr/screen.py) · [Métriques](../../evaluation/metrics.py)

| Niveau et clé | Définition et calcul | Exemple b31a5129 | Interprétation et limite |
| --- | --- | --- | --- |
| E `flow.discovered / deduplicated / duplicates` | Nombre de notices utilisables ramenées par les adaptateurs / études canoniques / différence | 12 / 10 / 2 | `deduplicated` représente les notices uniques conservées. Ce n'est pas le compteur de doublons supprimés |
| D Taux de dédoublonnage | `duplicates / discovered` si dénominateur positif | 2/12 = 16,67 % | Ratio dérivé, absent de l'export. Décrit les groupements opérés, pas leur exactitude bibliographique |
| E `search.tool_counts` | Comptage des observations par outil | 1 OpenAlex, 1 Semantic Scholar, 1 Crossref | Trois actions d'outil. La trace ReAct inclut aussi une action terminale `finish`, absente de ce compteur |
| E `successful_tool_actions / failed_tool_actions` et T statuts par outil | `success` et `empty` sont des succès d'action. Autres statuts sont classés en échecs | 3 / 0, les trois `success` issus du cache | Cas frais `000cca74…`, deux succès d'action, une source 429 avec deux tentatives échouées. Un appel HTTP et une action outil ne sont pas interchangeables |
| E `observed_latency_seconds`, `stop_reason` | Somme des durées des observations / motif d'arrêt `SearchState` | 0,0026 s, `agent_finish` | Latence de recherche locale avec cache, sans temps réseau. L'arrêt est logique |
| E `screened / included / excluded / unresolved / pending` | Nombre de décisions et partition par verdict final. `pending` et `unresolved` affichent le même compteur | 10 / 6 / 0 / 4 / 4 | Le screening compte aussi un dossier sans résumé et sans appel LLM. Éviter de sommer pending et unresolved |
| E `automatically_included / automatically_excluded` | Verdict final `include/exclude` dont l'origine est `ai`, `automatic` ou `rule` | 6 / 0 tous avec `ai` dans cette revue | Peut inclure les origines historiques. Les décisions humaines ne comptent pas ici |
| T `quote_verified` et `llm_confidence` | Flag lexical par dossier et score auto-déclaré, domaine [0,1]. Le seuil automatique est 0,80. Dénombrement d'audit | 6 vrais, 3 faux, 1 null. Confiance 0,95–1,00 chez les six inclus, 0,95–0,98 chez trois abstentions avec score, une sans score | Les abstentions à confiance élevée illustrent le filtre d'ancrage. Aucune moyenne, calibration ou exactitude validée par l'application |
| T et D Arbitrages humains de screening | Décisions `human`, `review_history` courant et événements de screening par opération | 0 dans b31a5129. Dans `fffdbf8…`, 6 décisions historiques, dont 5 inclusions et 1 exclusion | Différent du total des interventions système. Ces décisions ne sont pas des labels indépendants |

### Classification avec étiquettes indépendantes

`load_annotations` exige CSV `paper_id,label,annotator,protocol`, un verdict de référence `include/exclude` par ID. `screening_metrics` compare uniquement les IDs appariés. Le code ne peut pas vérifier la véritable indépendance de l'annotateur. `rule` s'affiche quand une décision de règle existe, sinon la production compare seulement `llm` brut et `final`. L'expérience B sépare les deux politiques dans des bras distincts. [Métriques](../../evaluation/metrics.py) · [Évaluation](../../EVALUATION.md)

| E | Définition et formule | Valeur réelle dans b31a5129 et B historique | Limite |
| --- | --- | --- | --- |
| `annotated / matched / decided` | Nombre de labels, présents dans prédictions, et rendus définitivement | null pour l'objet de classification | Aucun fichier annoté indépendant trouvé |
| `abstentions / positive_abstentions` | Prédictions appariées autres qu'inclusion/exclusion, puis sous-ensemble de références positives | null | Rapporter avec les mesures pour éviter de masquer des positifs abstentionnés |
| `tp / fp / tn / fn` | Matrice des décisions définitives face aux deux classes de référence | null | Les abstentions ne sont pas rangées automatiquement en FN |
| `precision / recall / f1 / false_negative_rate` | TP/(TP+FP), TP/(TP+FN), 2TP/(2TP+FP+FN), FN/(FN+TP) | null | Diviseur nul → null. Le rappel conditionnel sur les décidés peut cacher la perte de couverture. Un test synthétique de formule ne fournit aucune performance empirique |

## Récupération de preuves

Sources. [retrieval.py](../../slr/retrieval.py) · [agentic_rag.py](../../slr/course/agentic_rag.py) · [retrieval_quality](../../evaluation/metrics.py) · [Comparaison C](BASELINES_AND_ABLATIONS.md)

| Niveau et mesure | Définition et calcul | Exemple réel | Limite |
| --- | --- | --- | --- |
| E `evidence_corpus` | Inclus avec résumé, chunks résumé/PDF, IDs sans texte | 6 / 16 / 0 et liste vide | Des inclusions avec PDF peuvent aussi compter dans les 6 avec résumé. L'absence de chunks PDF ne discrédite pas le résumé |
| E `retrieval[].selected / requested_k / ranks` | Taille et IDs de la liste finale par question, top-k demandé | 3/3 pour chaque RQ. D somme 9, union 8 | Un chunk partagé entre RQ compte plusieurs fois dans la somme. Les candidats intermédiaires exclus de la mémoire ne sont pas dans `ranks` |
| E `retrieval_calls` et D budget utilisé | Appels d'outil par RQ. Part dérivée `calls / config.retrieval_budget` dans le mode Agentic | 1, 1, 2 sur plafond 2. 4/6 sur cette passe. RQ3 `budget_exhausted` | Budget d'opérations RAG, indépendamment du coût et des appels LLM. Le mode classique fait un appel quand le corpus existe. Un autre passage de RAG peut être demandé par Quality |
| E `facet_coverage / covered / missing` | Facettes avec mot-clé repéré / facettes définies, mesuré sur la mémoire des chunks | 1, 1, 0. RQ3 manque `evaluation_challenges` et `solution_strategies` | Une facette reconnue lexicalement n'établit pas une preuve. Un extrait peut exister même si une facette est manquante |
| E `extraction.candidate_count / selections / rejections / verified_count` | Nombre de candidats proposés, paires retournées, motifs de rejet et passages exacts acceptés. D agrégation ou `len(rag.evidence)` | 20 candidats par RQ, choix 2/6/2, passages 2/6/1 = 9. Une paire mal liée rejetée sur RQ3 | Le nombre de passages ne mesure pas la diversité des articles ni l'entailment. Les archives anciennes peuvent ne pas porter cet audit |
| E `precision_at_k` | Nombre de chunks pertinents uniques retournés / k demandé. Repli sur la taille de la liste si le k manque dans un artefact historique | null dans b31a5129. C/Q2 `0 → 1` à k=1 | Requiert labels explicites. Un classement vide avec k connu et labels donne 0 |
| E `recall_at_k` | Chunks pertinents retournés / taille de l'ensemble pertinent | null dans b31a5129. C/Q2 `0 → 1` | Référence vide → null. Les Q1–Q3 pédagogiques ne sont pas les RQ de la revue live |
| E `precision_among_returned` | Chunks pertinents / taille retournée, pour comparaison TD05 | absent sans labels dans b31a5129. C/Q2 classique null, Agentic 1 | Dénominateur différent de `precision_at_k`. Une absence de résultat n'est pas un 0 pour cette définition |

L'UI accepte un objet JSON RQ → liste d'IDs. Elle valide la forme, sans vérifier qualité, exhaustivité ou travail indépendant de l'annotation. Pour une comparaison future, conserver l'ID de version du découpage et choisir les labels sur le même corpus.

## Rédaction, qualité et synthèse exportée

Sources. [synthesis.py](../../slr/synthesis.py) · [evaluate_rules](../../slr/course/quality_agent.py) · [execute_step et evaluate_plan](../../slr/course/plan_and_execute.py) · [Retenue et rapports](../../slr/report.py)

| Niveau et mesure | Définition et calcul | Exemple b31a5129 | Limite |
| --- | --- | --- | --- |
| E `planning_execution.valid / plan_validity_rate / rq_coverage / section_coverage / consistency / dependency_validity / errors` | Mêmes contrats TD07 que le plan initial, mais corpus d'IDs autorisés de RAG. `dependency_validity` recopie `consistency` | vrai, 1, 1, 1, 1, 1, aucune erreur | Une structure complète ne garantit pas des affirmations retenues sur chaque RQ |
| E `completed_steps / execution_actions / status` | Nombre de sections exécutées, `ExecutionResult.tool_calls` et état de fin du plan | 3 / 5 / completed | Une section de limitation compte. Une action de plan est différente d'un appel Ollama |
| T/D Affirmations proposées, soutenues, incertaines, non soutenues | `len(draft.claims)` pour brouillon final, taille et catégories de `quality[i].findings` pour les passes. Export contient `detected_unsupported` et `uncertain` explicites | 4 au brouillon final. Rév. 0 → 2/0/2, rév. 1 → 2/1/1 (soutenu/incertain/non soutenu) | Dernier brouillon sauvegardé en propre. Les handoffs et findings documentent les états de révision. Pas de consensus scientifique |
| D Affirmations retenues et études citées | `ReviewRun.retained_claims()` en état terminal complet, puis nombre de `paper_id` distincts dans les preuves citées | 2 affirmations et 2 études citées sur 6 incluses. RQ1/RQ3 seulement | La couverture à l'export est 2/3, distincte de la couverture `quality.question_coverage` sur les citations valides avant filtrage |
| E `citation_validity` | Proportion d'affirmations dont les citations satisfont le contrat applicatif (RQ, IDs existants, aucune réf. inline illicite) / affirmations | 0,50 → 0,75. Faux IDs ou mauvais RQ pour C2/C3 puis C5 | Contrôle structurel. Valide ne signifie pas soutenue |
| E `lexical_support` | Sur les affirmations à citations valides, fraction avec au moins deux tokens distincts de longueur ≥4 en commun avec les extraits sélectionnés par `evaluate_rules` | 1,00 → 1,00 | Ce score n'est ni le verdict du LLM ni une mesure d'entailment. Dénominateur interne `max(1,n)` |
| E `question_coverage` | RQ représentées parmi les affirmations structurellement valides / 3 | 2/3 → 3/3 | Avant filtrage. RQ2 est couverte au score final sans qu'une affirmation de cette RQ n'apparaisse au rapport |
| E `automated_score` | Moyenne de citation_validity, lexical_support et question_coverage | 0,722222 → 0,916667 | Le nombre d'affirmations soutenues reste 2. La hausse est descriptive, pas la preuve d'un gain scientifique |
| T et E Révisions, `withheld_claims` et `revision_success` | `run.revision` et valeurs dans `quality`, taille de `withheld_claim_ids`, absence de feedback ultime après au moins une révision | 1, 2 retirées (C5/C6), `false` | Le run peut être complet en gardant un sous-ensemble. Une révision sans feedback n'est pas une validation humaine. Un retrait humain relève d'`adjudications` et n'incrémente pas forcément `withheld_claims` |
| E `human_claim_judgments` | Liste des acceptations/retraits motivés | vide | Une absence de décision ne remplace pas une revue scientifique |

## Système, télémétrie et exports

Sources. [Calls et Telemetry](../../slr/gateway.py) · [Event](../../slr/models.py) · [event_stats et review_metrics](../../evaluation/metrics.py)

| Niveau et mesure | Définition et calcul | Exemples b31a5129 et frais `000cca74…` | Limite |
| --- | --- | --- | --- |
| E `status / task_completed / outcome_reason` | Statut sauvegardé, vrai si `complete`, cause d'abstention disponible | Tous deux `complete / true`, motif vide | Succès technique du parcours, pas une SLR exhaustive |
| E `events_by_agent[].calls/cache_hits/successes/failures/retries` | Par stage, kind, opération. Tentatives réelles excluent `cache_hit`. Succès/échecs sur ces tentatives, retries par drapeau | b31a5129, 8 exécutions agent (1 plan, 1 search, 1 tri, 1 RAG, 2 writing, 2 quality). 0 appel LLM réel, 18 hits. 0 HTTP réel, 3 hits. Frais, 16 LLM réels réussis, 4 tentatives HTTP dont 2 succès, 0 hit | Ne pas additionner temps agent et temps enfant. Embeddings ont un `kind` distinct. Absence de groupe indique absence d'événement enregistré |
| E `latency_seconds` | Somme de toutes les durées par groupe, y compris lecture cache, arrondie à 4 décimales | b31a5129, 0,0370 s agent RAG et 0,0053 s pour groupe de trois extractions en cache | Mesure locale et dépendante du cache. Les groupes sont imbriqués |
| E `active_seconds` | Somme du temps des événements de type agent | 0,0933 s / 167,4053 s | Cumul de travail enregistré. Une reprise peut conserver du travail historique |
| E `elapsed_seconds` | Horodatage dernier état sauvegardé − création du run | 0,344655 s / 161,030736 s | Inclut éventuelles pauses et intervalle de replay quand la date est héritée. Peut être inférieur au temps actif mesuré par l'horloge monotone. À distinguer des 168,24 s de pytest |
| E `input_tokens / output_tokens / calls_with_token_usage` | Sommes d'usage remonté par API/LLM/embeddings hors cache, et nombre de tentatives où au moins un usage est présent | 0 / 0 / 0 puis 16 590 / 3 693 / 16 | Zéros cache = aucun usage nouveau mesuré. Pas de mesure de coût financier ni d'usage manquant. Les métadonnées sont dépendantes du fournisseur |
| E `api_errors / retries / human_interventions` | Échecs HTTP/transport enregistrés sous kind API, retries du service, événements `human` | 0 / 0 / 0 puis 2 / 1 / 0 | Un échec d'une source peut générer deux événements. Le compteur humain ne représente ni le temps humain ni seulement les arbitrages |

`downloads` sérialise l'objet structuré en JSON. `to_csv` aplatit les champs et indices de listes en lignes à deux colonnes `metric,value`. Une valeur Python `None` devient une cellule vide en CSV, tandis qu'une liste vide peut produire zéro ligne. Aucun export ne contient de précision supervisée pour le run b31a5129. Consulter le JSON pour les types et le rapport pour les citations effectivement rendues. [App](../../app.py) · [Exports](EXPERIMENTS_AND_RESULTS.md)
