# Architecture et orchestration

MultiAgentSLR est un processus Streamlit dans lequel un superviseur Python appelle six rôles synchrones. Les rôles partagent un objet `ReviewRun` persistant et des contrats Pydantic. Les handoffs enregistrent les transitions et les artefacts. Le passage de données effectif lit les attributs de `ReviewRun`. La communication entre agents ne dépend d'aucun bus, message autonome ou microservice interne. Les appels externes concernent le fournisseur LLM, les API bibliographiques et, si configuré, les embeddings Ollama.

## 1. Composants

```mermaid
flowchart LR
  U["Chercheur ou évaluateur"] --> UI["app.py<br/>review_page / evaluation_page"]
  CLI["slr.__main__.main"] --> S["slr.supervisor.Supervisor"]
  UI --> S
  S --> P["planning.prepare_review"]
  S --> F["sources.search_review"]
  S --> T["screen.screen_papers"]
  S --> R["retrieval.gather_evidence"]
  S --> W["synthesis.write_review"]
  S --> Q["synthesis.evaluate_claims"]
  S --> DB[("storage.DiskStore<br/>SQLite runs / cache")]
  P --> L["gateway.MeasuredModel"]
  T --> L
  R --> L
  W --> L
  Q --> L
  L --> O["Ollama / Groq"]
  F --> API["sources.ScientificSources<br/>OpenAlex / Semantic Scholar / Crossref"]
  L --> C["gateway.Calls / Telemetry"]
  API --> C
  C --> DB
  UI --> E["evaluation.metrics / benchmarks"]
  E --> X[("expériences / exports")]
  S --> M["report.markdown / pdf<br/>état complete requis"]
```

La flèche du superviseur vers `report` représente l'autorisation par l'état. Les entrées UI et CLI invoquent le rendu. Les éventuels embeddings empruntent `MeasuredEmbeddings` et `Calls`. [Entrée UI](../../app.py) · [Entrée CLI](../../slr/__main__.py) · [Gateway](../../slr/gateway.py)

## 2. Workflow et contrôle

```mermaid
flowchart TD
  A["Sujet / ReviewConfig"] --> B["Supervisor.start"]
  B --> P["prepare_review → ResearchPlan"]
  P --> S["search_review → consolidate → SearchBatch"]
  S --> T["screen_papers → ScreeningBatch"]
  T --> H{"Mode humain et lot non vide ?"}
  H -->|Oui| J["awaiting_screening<br/>finish_screening ou continue_automatically"]
  H -->|Non| G["handoff_screening"]
  J --> G
  G -->|Aucune inclusion| IE["insufficient_evidence"]
  G -->|PDF demandé en mode humain| D["awaiting_documents<br/>finish_documents"]
  G -->|Inclusions disponibles| R["gather_evidence<br/>corpus → RAG → preuves"]
  D --> R
  R -->|Aucun passage vérifié| IE
  R -->|RagBundle| W["write_review → Draft"]
  W --> Q["evaluate_claims → QualityResult"]
  Q --> K{"quality_route"}
  K -->|réviser la récupération| R
  K -->|réviser la rédaction| W
  K -->|arbitrage en mode humain| A2["awaiting_claims / review_claim"]
  K -->|fin ou filtrage automatique| C["Supervisor.complete"]
  A2 --> C
  C -->|aucune affirmation retenue| IE
  C -->|complete| P2["Markdown / PDF"]
```

La branche PDF n'est prise qu'après le handoff de screening si `pause_for_documents=True`. Des échecs attendus transforment le stade courant en `failed`. Le détail est enregistré même si aucune sortie finale ne peut être produite. [Supervisor](../../slr/supervisor.py)

## 3. Séquence nominale et contrats

```mermaid
sequenceDiagram
  actor U as Chercheur
  participant UI as review_page
  participant S as Supervisor
  participant DB as DiskStore
  participant P as prepare_review
  participant D as search_review
  participant T as screen_papers
  participant R as gather_evidence
  participant W as write_review
  participant Q as evaluate_claims
  U->>UI: Sujet et protocole
  UI->>S: start(ReviewConfig)
  S->>DB: save(ReviewRun)
  S->>P: config et modèle
  P-->>S: ResearchPlan
  S->>D: topic, queries, per_source, source_gateway
  D-->>S: SearchBatch avec Study et SearchState
  S->>T: studies, config, modèle
  T-->>S: ScreeningBatch
  opt Checkpoint humain
    S->>DB: save(awaiting_screening)
    U->>UI: Motiver un verdict et libérer le checkpoint
    UI->>S: review_screening / finish_screening
  end
  S->>R: run, modèle, embeddings facultatifs
  R-->>S: RagBundle, EvidenceLocation et Passage
  S->>W: run et preuves vérifiées
  W-->>S: Draft et ExecutionResult
  S->>Q: claims et passages cités
  Q-->>S: QualityResult, jugements et feedback
  S->>DB: save après stade ou décision humaine
  S-->>UI: ReviewRun terminal ou en attente
  UI-->>U: markdown(run) et pdf(run) si complete
```

## 4. Points de décision humains

```mermaid
flowchart TD
  H["human_in_the_loop + ScreeningBatch non vide"] --> A["awaiting_screening / screening_ui"]
  A --> B["review_screening<br/>include, exclude ou uncertain + motif"]
  B --> C["ScreeningOverride + Event + DiskStore.save"]
  C --> A
  A --> F["finish_screening"]
  A --> G["continue_automatically<br/>préserve les verdicts"]
  F --> Z{"Au moins un verdict include ?"}
  G --> Z
  Z -->|Non| I["insufficient_evidence"]
  Z -->|Oui| D{"pause_for_documents ?"}
  D -->|Oui| P["awaiting_documents<br/>attach_document / finish_documents"]
  D -->|Non| R["RAG puis Writing et Quality"]
  P --> R
  R -->|Alerte finale et mode humain| E["awaiting_claims / quality_ui"]
  E --> J["review_claim<br/>accept ou remove + justification"]
  E -->|Citation invalide| X["remove uniquement"]
  X --> J
  J -->|Reste un dossier à traiter| E
  J -->|Plus de dossier à traiter| K["complete ou insufficient_evidence"]
```

[Workflow humain, éléments de preuve et tests](HITL_WORKFLOW.md)

## 5. RAG et provenance

```mermaid
flowchart LR
  S["Study + ScreeningDecision.final=include"] --> B["build_corpus"]
  D["full_text par paper_id"] --> B
  B --> A["EvidenceChunk abstract<br/>source + ID API, page absente"]
  B --> P["EvidenceChunk full_text<br/>page PDF réelle"]
  A --> R["retrieve"]
  P --> R
  Q["QuestionProtocol<br/>RQ, terms, facets"] --> R
  R --> C["lexical_retrieve ou run_adaptive_retrieval"]
  C --> X["excerpt_candidates<br/>extraits du top-k numérotés"]
  X --> L["Extraction / ExcerptSelection<br/>chunk_id + candidate_id"]
  L --> V["verify_excerpt<br/>corpus + métadonnées + texte exact"]
  V -->|accepté| E["Passage<br/>E-… / RQ / paper_id / chunk_id"]
  V -->|rejeté| A2["ExtractionAudit"]
  E --> W["write_review puis evaluate_claims"]
```

## 6. Boucle de qualité

```mermaid
flowchart TD
  W["write_review / run_with_replanning"] --> Q["evaluate_claims<br/>citations + juge + score lexical"]
  Q --> T{"quality_route"}
  T -->|Aucun feedback| F["complete"]
  T -->|Révision disponible et ID invalide ou jugement incertain| W2["revision += 1<br/>write_review"]
  T -->|Révision disponible et autre défaut de support| R["revision += 1<br/>gather_evidence"]
  R --> W2
  W2 --> K["Conserver les affirmations déjà étayées<br/>si leurs preuves restent autorisées"]
  K --> Q
  T -->|Budget épuisé ou fixed avec feedback| M{"execution_mode"}
  M -->|Automatic| A["withheld_claim_ids<br/>retirer les affirmations signalées"]
  M -->|Human-in-the-Loop| H["awaiting_claims"]
  H --> F
  A --> F
  F -->|Aucune affirmation retenue| I["insufficient_evidence"]
  F -->|Affirmations retenues| P["finish / export"]
```

La garde de routage donne priorité à l'absence de feedback. `fixed` désactive les retours de correction de production et conserve la décision terminale selon le mode. La boucle TD08 expérimentale a ses propres états et budgets. [synthesis.py](../../slr/synthesis.py) · [orchestrator.py](../../slr/course/orchestrator.py) · [Ablations](BASELINES_AND_ABLATIONS.md)

## Coordination, reprise et déploiement

| Fonction | Comportement en production | Fichiers |
| --- | --- | --- |
| Ordonnancement | `advance` itère sur `next_stage` tant que `status=running`. `on_stage` alimente l'indicateur de progression Streamlit. Le modèle est instancié à la demande par séquence d'exécution | [supervisor.py](../../slr/supervisor.py), [app.py](../../app.py) |
| Contrats de passage | `Handoff` contient source, cible, objectif, artifact, identifiants de preuve, statut `ok/partial/blocked` et budget restant. `validate_handoff` exige une transition autorisée, preuves dans l'état et budget non négatif. L'ensemble de candidats au screening doit correspondre aux études découvertes. RAG ne peut transmettre que les études incluses | [quality_models.py](../../slr/course/quality_models.py), [orchestrator.py](../../slr/course/orchestrator.py), [supervisor.py](../../slr/supervisor.py) |
| Reprise et abstention | `retry` reprend l'étape échouée. `retry_retrieval` redémarre à `rag` après une preuve insuffisante à cet endroit, conserve search et screening et journalise une intervention. Le bouton Continue review peut reprendre un état `running` sauvegardé. Pas de reprise automatique des appels en cours après interruption du processus | [supervisor.py](../../slr/supervisor.py), [app.py](../../app.py) |
| Persistance | SQLite en WAL, version optimiste lors de `save` et horodatage UTC. `StaleRunError` signale une modification concurrente. Sauvegarde des textes de pages et des décisions, sans fichier PDF original dans l'état | [storage.py](../../slr/storage.py), [models.py](../../slr/models.py) |
| Cache | `Calls.use` consulte une clé SHA-256 incluant opération et identité. Le modèle y inclut fournisseur, modèle, endpoint le cas échéant, température, messages et schéma structuré. Le cache d'API repose sur URL, requête et limite. Seules les réponses réussies et validées alimentent le cache. Cache désactivable par TTL 0 | [gateway.py](../../slr/gateway.py), [sources.py](../../slr/sources.py) |
| Erreurs externes | Retry de transport borné à une tentative additionnelle pour l'API et les appels LLM, selon erreur temporaire et délai accepté. `Retry-After` numérique ou délai par défaut 0,25 s et plafond de 3 s pour le retry. Les observations donnent le statut final et les événements décrivent les tentatives | [gateway.py](../../slr/gateway.py), [runtime.py](../../slr/course/runtime.py) |
| Expériences | `run_benchmark` écrit inputs, outputs, prompts, événements et métadonnées avec hashes. Le CLI `--record-prompts` et les tests live documentent certaines exécutions. La session UI ordinaire conserve les artefacts d'étape et la télémétrie en base, sans capture intégrale des prompts | [benchmarks.py](../../evaluation/benchmarks.py), [__main__.py](../../slr/__main__.py), [test_live.py](../../tests/test_live.py) |
| Déploiement | Conteneur d'application unique, volume `review_data` et conteneur tests séparé. `slr.health` vérifie la santé HTTP Streamlit et l'accès SQLite en écriture. Render décrit un service, sans validation effective de déploiement cloud | [Dockerfile](../../Dockerfile), [compose.yaml](../../compose.yaml), [health.py](../../slr/health.py), [render.yaml](../../render.yaml) |
