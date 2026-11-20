# Plan du rapport universitaire

Titre de travail **MultiAgentSLR, orchestration et provenance d'une synthèse bibliographique assistée par LLM**. Présenter un prototype abstract-first et ses conditions expérimentales. Les chapitres relient les affirmations aux artefacts et signalent les éléments à collecter. Le rapport final et les diapositives restent à produire.

## 1. Introduction générale

Présenter le passage d'une question à des affirmations sourcées. Résumer le prototype, les sources, les deux modes et les résultats d'exécution. Annoncer les axes d'évaluation, fonctionnement, traçabilité et comparaisons limitées. [Présentation](PROJECT_OVERVIEW.md)

## 2. Contexte et problématique

Expliquer le coût de collecte, sélection et traçabilité manuelles, les divergences de jugement et les changements de bibliographie. Poser la question d'ingénierie. Comment obtenir une synthèse traçable avec abstention et vérification sur le texte disponible ? Délimiter la différence avec une revue exhaustive ou un prompt unique. [Présentation et limites](PROJECT_OVERVIEW.md)

## 3. Objectifs et contributions

Lister la production de trois RQ, l'acquisition bornée, le tri explicable, le corpus à provenance, le contrôle des affirmations et les exports. Séparer apports d'intégration, copies du cours et correction d'incidents. La paire chunk/candidat répond à un défaut reproduit. Le gain scientifique reste à évaluer. [Provenance TD](../../COURSE_CODE.md) · [Exécutions](EXPERIMENTS_AND_RESULTS.md)

## 4. État de l'art et approches utilisées

Organiser la future revue des méthodes autour de recherche bibliographique, validation de schémas, ReAct, TF-IDF/RAG adaptatif, Plan-and-Execute et contrôle humain. Citer les TD pour chaque brique pertinente et compléter ensuite par les références scientifiques nécessaires. Distinguer politique d'outil déterministe et appels LLM. [Détails des agents](AGENTS_TECHNICAL_DETAILS.md)

## 5. Analyse des besoins

Décrire chercheur, évaluateur et mainteneur comme rôles d'usage, sans attribuer des comptes ou permissions non implémentés. Spécifier sujet, critères, mode, fournisseur, sources et pièces facultatives. Définir les cas attendus de succès et d'abstention, les conditions de vérification et de reproductibilité. [Entrées, sorties et portée](PROJECT_OVERVIEW.md)

## 6. Architecture multi-agents

Insérer diagrammes de composants, workflow, séquence et routage Quality. Expliquer le rôle de `ReviewRun`, des handoffs et du coordinateur. Montrer les dépendances RQ/requêtes, décisions/corpus et preuves/affirmations. Présenter le diagramme de provenance. [Six diagrammes](SYSTEM_ARCHITECTURE.md)

## 7. Description détaillée des agents

Une sous-section par rôle, du planificateur au contrôle qualité, puis le superviseur. Inclure entrée/sortie, prompt ou règle, schéma, outil, erreurs, traces et métriques. Illustrer l'échec original et le contrat chunk/candidat. Décrire les modes classique et adaptatif. [Agents](AGENTS_TECHNICAL_DETAILS.md) · [Exemple d'artefacts](DATA_FLOW_AND_SCHEMAS.md)

## 8. Implémentation technique

Présenter dossiers, pile et versions, Streamlit, LangChain, HTTPX, Pydantic, SQLite et Docker. Annoter dépendances et commandes. Distinguer Compose sain et Blueprint Render. Prévoir capture de la configuration courante et des résultats pytest. [Pile](PROJECT_OVERVIEW.md) · [Déploiement](../../DEPLOYMENT.md) · [Captures](SCREENSHOT_CHECKLIST.md)

## 9. Workflow Human-in-the-Loop

Illustrer tri, justification, override et reprise. Expliquer pause PDF et arbitrage des affirmations. Séparer les traces historiques, la libération actuelle d'un checkpoint et les résultats avec `AppTest`. Citer les captures disponibles et celles qui manquent. [HITL](HITL_WORKFLOW.md)

## 10. Protocole expérimental

Définir test contrôlé, benchmark sur fixture, exécution en cache/replay et appels externes réels. Identifier corpus, modèles, température, budgets, version, temps et critères de succès. Séparer latence réseau, temps actif, temps sauvegardé et temps pytest. Prescrire un protocole d'annotation indépendante pour les métriques indisponibles. [Baselines](BASELINES_AND_ABLATIONS.md) · [Dictionnaire](METRICS_DICTIONARY.md)

## 11. Résultats et visualisations

Présenter le flux 12 → 10 → 6/0/4 pour `b31a5129…`, étiqueté cache intégral. Montrer RQ1/RQ2/RQ3 avec 2/6/1 preuves et deux affirmations retenues. Ajouter replay à neuf passages et run frais à dix dans des tableaux aux conditions distinctes. Présenter A–D et les captures vérifiées. [Exécutions](EXPERIMENTS_AND_RESULTS.md) · [Visuels](SCREENSHOT_CHECKLIST.md)

## 12. Discussion et interprétation

Expliquer que le nouveau contrat permet de vérifier les citations sans recopies libres. La révision conserve des affirmations soutenues dont les preuves restent disponibles. Discuter score composite et cache. La hausse du score de la revue centrale ne prouve pas l'amélioration de l'entailment. [Métriques](METRICS_DICTIONARY.md) · [Comparaisons](BASELINES_AND_ABLATIONS.md)

## 13. Limites et menaces à la validité

Décrire biais de données et de sélection, faible taille des essais, accès aux bases, doublons inter-versions, résumés, jugements automatiques, annotations et charge/cloud. Expliquer les limites de généralisation des fixtures. [Menaces](LIMITATIONS_AND_THREATS_TO_VALIDITY.md)

## 14. Perspectives

Proposer jeux annotés, essais multi-domaines, comparaisons appariées, chronométrage humain et jugements indépendants des affirmations. Séparer évaluation des embeddings, démonstration PDF et validation d'un éventuel déploiement. [Matrice](BASELINES_AND_ABLATIONS.md)

## 15. Conclusion générale

Rappeler la valeur d'une synthèse traçable et la capacité observée à s'arrêter ou produire un rapport partiel. Citer les chiffres du run frais, le diagnostic d'origine, puis l'évaluation indépendante encore absente. [Audit](AUDIT_SUMMARY.md)

## 16. Annexes : exemples JSON, tableaux de métriques, traces et captures

Inclure le cas Homiar et al., les IDs, les définitions et formules, les artefacts et les captures avec légende, version, cache et dossier. Ajouter les commandes reproductibles. Filtrer données privées, secrets et images d'autres projets. [Schémas](DATA_FLOW_AND_SCHEMAS.md) · [Métriques](METRICS_DICTIONARY.md) · [Inventaire](SCREENSHOT_CHECKLIST.md)
