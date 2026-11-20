# Analyse technique des agents

Les noms métier désignent des rôles. En production, leurs points d'entrée sont les fonctions appelées par `Supervisor.run_stage`. Les classes supplémentaires des copies TD ont des usages distincts. Les prompts historiques représentent la révision du code qui les a produits. [Architecture](SYSTEM_ARCHITECTURE.md) · [Schémas](DATA_FLOW_AND_SCHEMAS.md)

## Recherche et planification

| Élément | Implémentation |
| --- | --- |
| Entrée et sortie | `ReviewConfig` → `ResearchPlan` avec trois `ResearchQuestion`, `ProtocolProposal`, `PlanCandidate` et compteurs de réparation. `Supervisor.handoff` passe le plan à `search` |
| Génération | `prepare_review` appelle `generate_questions`. Les messages TD01 fixent rôle méthodologique, sujet, français et questions ouvertes. L'instruction applicative exige exactement RQ1–RQ3, bien que le cadre TD01 mentionne 3–5 |
| Validation | `run_controlled_workflow` impose trois lignes ordonnées au format `RQn. …`, formulations textuellement distinctes et minima. Une correction ciblée du format. `human_required` du TD devient une erreur de planification, sans écran humain de correction des RQ |
| Protocole structuré | `with_structured_output(ProtocolProposal)` reçoit sujet, RQ et critères. Demande une phrase de recherche par API et pour chaque RQ des termes et facettes mesurables avec mots-clés et `query_hint`. Une nouvelle tentative si le protocole ne valide pas |
| Contrats | Exactement trois clés source normalisées, sans répétition. Phrases de 3 à 420 caractères avec caractère alphanumérique dans le code. Le prompt demande ≤ 140 caractères et proscrit les opérateurs booléens et champs spéciaux. Ces deux exigences du prompt ne sont pas strictement vérifiées par un parseur. `QuestionProtocol` borne termes et facettes et interdit les IDs de facette répétés localement |
| Plan initial | `assemble_plan` construit trois étapes `prepare-RQn` en Python, stratégie `direct`, mode `limitation`, sans preuves à ce stade. `validate_plan` contrôle dépendances, couverture et preuves autorisées |
| Mesures et limites | Validité des RQ et requêtes selon contrat, réparations, couverture et cohérence du plan. La validation ne mesure ni pertinence scientifique ni rappel documentaire. `build_queries` TD02 génère des expressions booléennes pour Scholar/IEEE/ACM dans la copie pédagogique |

[Production](../../slr/planning.py) · [Contrats](../../slr/models.py) · [Génération TD01](../../slr/course/research_questions.py) · [Validation TD02](../../slr/course/search_plan.py) · [Planification TD07](../../slr/course/plan_and_execute.py)

## Recherche bibliographique ReAct

| Élément | Implémentation |
| --- | --- |
| Entrée et sortie | Sujet, requêtes, limite et mode → `SearchBatch`, `SearchState`, liste de `Study`, actions, observations, traces, notices utilisables et doublons |
| Outils | `ScientificSources.search` utilise HTTPX. OpenAlex `/works` avec `search/per-page`, Semantic Scholar `/graph/v1/paper/search` avec `query/limit/fields`, Crossref `/works` avec `query.bibliographic/rows`. Identifiants optionnels par environnement |
| Décision ReAct | `search_review` crée le `ToolRegistry`. `run_react_agent` exécute `react_policy`, une fonction déterministe qui consulte observations et sources tentées. Après une source en échec ou vide, Crossref devient prioritaire si encore disponible. Puis `finish` après épuisement des sources. `LLMDecisionPolicy` est présent dans la copie TD sans usage dans ce chemin |
| Schéma et erreurs | `AgentAction` valide action, outil, requête et limite. `execute_authorized_action` contrôle l'autorisation. `Observation` encode succès, vide, 429, autre erreur HTTP, réseau et actions invalides/refusées. `Calls.use` peut réessayer le transport une fois. Échec de toutes les sources → `failed`. Un retour vide reste une action réussie vide |
| Bornes | Budget ReAct quatre tours, cible `3 × per_source + 1` au-dessus du maximum ordinaire. En fixe `run_tool_workflow` tente les trois sources dans l'ordre OpenAlex, Semantic Scholar, Crossref. Pas de pagination ni reformulation de la requête bibliographique par la politique de recherche |
| Normalisation et dédoublonnage | `normalize_openalex` reconstitue l'index inversé dans l'ordre des positions. `normalize_rows` nettoie les champs, écarte les notices sans identifiant ou titre. `consolidate` normalise le DOI, rapproche un titre normalisé de son DOI unique si possible, sinon titre+année. Les ID natifs sont des alias par source. SHA-256 du groupement → `P-…`. Le plus long résumé est retenu. `SearchState.papers` comporte une déduplication distincte du lot de production |
| Mesures et limites | Notices et doublons, ordre, état et latence des outils, raison d'arrêt, tentatives, retries et cache. Aucun rappel documentaire sans corpus de référence |

[Sources](../../slr/sources.py) · [Contrats](../../slr/course/contracts.py) · [ReAct](../../slr/course/react_agent.py) · [Runtime](../../slr/course/runtime.py) · [Flux fixe](../../slr/course/workflow.py)

## Screening titre et résumé

| Élément | Implémentation |
| --- | --- |
| Entrée et sortie | `Study`, sujet, critères déclarés et modèle → `ScreeningDecision`. `screen_papers` fournit un `ScreeningBatch`, une décision par ID |
| Prompt et schéma | `build_screening_messages` fournit titre, résumé, critères et ID. Choix `include/exclude/uncertain` sur les textes fournis, citation copiée et justification du critère. `LLMScreeningDecision` contient `paper_id`, décision, confiance, raisons, evidence et `needs_human_review`. `invoke_structured_screening` rétablit l'ID autoritatif. La confiance numérique est contrôlée par Pydantic et les pourcentages permis sont ramenés à 0–1 |
| Politique `llm-evidence-v1` | Résumé requis, confiance ≥ 0,80, justification non blanche, aucun signal de revue humaine ni abstention. Extrait contigu à bornes de mots dans un seul champ titre ou résumé après normalisation NFKC, casse, espaces et ponctuation, au moins deux mots. `quote_verified` seul ne suffit pas à décider |
| Abstention | Résumé absent → aucun appel. Réponse invalide, transport, confiance faible, citation non ancrée ou demande de revue → `uncertain`. Verdict brut, extrait, confiance, raison et statut d'ancrage sont conservés lorsque disponibles |
| Override et baseline | `review_screening` peut remplacer tout verdict au checkpoint humain et consigne un `ScreeningOverride` daté. `ScreeningAgent.run` lexical sert la baseline B, indépendamment du LLM. `rule` et `hybrid` restent lisibles dans des traces historiques. `Supervisor.start` impose `llm` en production |
| Mesures et limites | Incl./excl./non résolus, origine AI ou humaine, confiance et ancrage par dossier, métriques conditionnelles si annotations indépendantes. Confiance non calibrée et pertinence non établie par l'ancrage lexical |

[Screening](../../slr/screen.py) · [Prompt TD04](../../slr/course/llm_screening_agent.py) · [Baseline](../../evaluation/benchmarks.py) · [HITL](HITL_WORKFLOW.md)

## Récupération de preuves

| Élément | Implémentation |
| --- | --- |
| Entrée et corpus | `gather_evidence` consomme les inclusions effectives, `Study`, pages et questions/facettes. `build_corpus` produit des `EvidenceChunk` de 900 caractères, 90 de recouvrement. Priorité au PDF avec texte, résumé de secours. `abstract:P-…_cN` sans page. `full_text:P-…_pN_cN` avec page réelle |
| Classique | `retrieve` exécute une recherche TF-IDF Python sur question et termes. Cosinus, scores positifs et top-k. Un appel de récupération par question et par passe |
| Adaptatif | `run_adaptive_retrieval` commence au lexical. `controlled_decider` observe les facettes et cible les `query_hint` manquants. Recherche sémantique si embeddings Ollama configurés, sinon lexicale, avec repli lexical si le service d'embeddings échoue. Fusion par ID, meilleur score, top-k et budget par RQ. `build_llm_decider` du TD06 n'est pas la politique utilisée |
| Prompt et schéma | `excerpt_candidates` prépare des extraits existants bornés à 600 caractères et filtrés à trois tokens au moins. Le prompt demande une preuve directe même partielle et tolère des langues différentes. `Extraction` autorise jusqu'à huit `ExcerptSelection(chunk_id, candidate_id)` ou une liste vide |
| Provenance | Valider le chunk offert et la paire. `verify_excerpt` compare localisation complète et sous-chaîne exacte du chunk canonique. `E-…` dérivé de RQ, chunk, texte. Déduplication par étude et texte dans la RQ. Le PDF garde sa page et l'abstract l'ID API de provenance lorsqu'il est disponible |
| Sortie et limites | `RagBundle` regroupe corpus, rangs, appels, facettes, `Passage` et `ExtractionAudit`. Réponse invalide, aucun chunk, aucun extrait exploitable, sélection vide et rejet sont des cas distincts. Sans extrait vérifié, abstention possible. La présence littérale d'un passage ne valide ni sa pertinence ni les affirmations. L'efficacité des embeddings **NON VÉRIFIÉE** dans les runs live examinés |

[Récupération](../../slr/retrieval.py) · [RAG TD05](../../slr/course/rag_pipeline.py) · [RAG TD06](../../slr/course/agentic_rag.py) · [PDF](../../slr/course/pdf_loader.py)

## Rédaction Plan-and-Execute

| Élément | Implémentation |
| --- | --- |
| Entrées et plan | `make_plan` construit un `PlanStep` par question avec IDs admissibles, mode `synthesis` ou `limitation`. `evidence_items` conserve les pages éventuelles. `run_with_replanning` du TD07 contrôle dépendances, citations et facettes. `limitation_replan` peut réduire les prétentions d'une étape déficitaire |
| Budgets | Jusqu'à trois révisions et six actions du plan de rédaction pour trois RQ dans `write_review`. Compteurs distincts de la révision Quality. Sans passage autorisé par une étape exécutée, brouillon vide |
| Prompt et schéma | `ClaimProposal`, ≤ 18 `Claim`. Texte atomique au plus près des extraits, RQ et ID(s) de preuve de la même RQ. Proscription des DOI, URL et références numériques inline et résultats inventés. Extraits et brouillon sont traités comme données. Questions, preuves, brouillon et feedback entrent dans le prompt |
| Sortie | `Draft` avec claims et `ExecutionResult`. ID `C…` attribué en Python. En révision, garder les affirmations appuyées dont les preuves restent permises et de même RQ, puis repasser l'ensemble à Quality. Les sorties LLM peuvent contenir une mauvaise référence et seront contrôlées en aval |
| Mesures et limites | Validité, cohérence, couverture, étapes complétées et actions. Taille du brouillon et affirmations retenues dérivées. Un plan à trois RQ n'implique pas trois sections scientifiquement étayées |

[Production](../../slr/synthesis.py) · [Contrats TD07](../../slr/course/planning_models.py) · [Exécution](../../slr/course/plan_and_execute.py)

## Contrôle qualité

| Élément | Implémentation |
| --- | --- |
| Entrée et vérification | `evaluate_claims` contrôle RQ valide, preuve de même RQ, au moins un ID et absence de référence inline repérée par regex. Violation → `unsupported` et `invalid_claims`. `evaluate_rules` TD08 calcule l'appui lexical avec au moins deux tokens communs, et la couverture des RQ sur les affirmations à citations valides |
| Prompt et schéma | `JudgeResponse`, liste de `ClaimCheck` par ID, verdict `supported/unsupported/uncertain` et motif. Le juge reçoit l'affirmation et ses extraits. Il examine valeurs, direction, conditions, groupes et portée. Omission, double réponse pour le même ID ou erreur du juge → incertitude |
| Routage | `quality_route` renvoie fin sans feedback. Avec feedback et budget disponible, citation invalide ou incertitude → Writing, sinon → RAG. Budget épuisé ou `fixed` → décision terminale humaine ou filtrage selon le mode. `Supervisor.complete` exige au moins une affirmation retenue |
| Filtrage | En automatique, mémoriser les IDs des affirmations encore signalées et les omettre du rapport. En mode humain, accepter ou retirer avec motif. Une citation invalide force le retrait. `report_blocks` construit références et provenance depuis les objets d'origine et déclare le périmètre abstrait |
| Mesures et limites | Taux de citations valides, appui lexical, couverture, score composite, jugements séparés, révisions et retraits. Le score composite ne commande pas à lui seul l'export. Le même modèle joue généralement rédaction et jugement |

[Qualité](../../slr/synthesis.py) · [Scores TD08](../../slr/course/quality_agent.py) · [Export](../../slr/report.py)

## Superviseur Python

`Supervisor.start/advance/run_stage/handoff` ordonnance les stades, enregistre `ReviewRun` et applique `TRANSITIONS`. `Telemetry` enregistre actions, erreurs, retries, cache et tokens disponibles. `retry` et `retry_retrieval` reprennent le bon stade. Le superviseur n'a aucun prompt. `orchestration=fixed` conserve les stades et interfaces, désactive les retours Quality et applique la décision terminale selon le mode. La comparaison TD08 emploie d'autres replays et un budget de transitions. [Code](../../slr/supervisor.py) · [Architecture](SYSTEM_ARCHITECTURE.md) · [Comparaisons](BASELINES_AND_ABLATIONS.md)
