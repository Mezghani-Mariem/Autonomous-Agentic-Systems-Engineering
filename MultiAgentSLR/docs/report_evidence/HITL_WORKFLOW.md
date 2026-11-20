# Workflow Human-in-the-Loop

## Activation, pauses et reprise

1. Dans **Review workspace**, choisir **New review** puis **Human-in-the-Loop** dans **Execution mode**. Saisir le sujet. La CLI accepte `--execution-mode human_in_the_loop`, et l'interface permet ensuite l'arbitrage de la revue sauvegardée. Vérifier l'ID et le mode de la revue affichée, indépendamment du mode choisi pour le prochain sujet.
2. Après le screening LLM, un lot non vide déclenche `awaiting_screening`, même si tous les verdicts AI sont définitifs. Les dossiers `uncertain` sont en tête, ouverts par défaut et libellés **unresolved**. Les autres restent accessibles pour un override.
3. L'écran expose titre, résumé ou son absence, lien de notice HTTP(S), `paper_id`, résultat courant et origine, motif, recommandation AI, extrait soumis et indicateur de vérification. L'audit global montre aussi la confiance, l'évaluation initiale, le motif humain et les overrides. Le code n'associe pas ces décisions à un compte de réviseur nominatif.
4. Choisir **include**, **exclude** ou **uncertain**, saisir une raison non blanche et cliquer **Save screening decision**. `review_screening` contrôle état et ID, pose `decided_by=human` et remplace le verdict et le motif finaux. Il conserve la proposition AI et ajoute `ScreeningOverride` avec verdict, origine et raison précédents, nouvel état, motif et timestamp. L'événement inclut le `paper_id`. L'enregistrement individuel laisse la revue en pause.
5. **Continue to evidence retrieval**, ou **Finish screening** sans étude incluse, appelle `finish_screening`. En présence de l'option, **Continue in Automatic mode** bascule le mode, conserve les verdicts et retire la pause PDF. Les seuls verdicts finaux `include` rejoignent RAG. Sans inclusion, état `insufficient_evidence`.
6. **Attach full text to a paper** est accessible au screening et, si **Pause to add full-text PDFs** a été choisi, à l'état `awaiting_documents`. Fichier commençant par `%PDF`, ≤ 12 Mio, ≤ 250 pages et ≤ 1 million de caractères, avec texte extractible. Il peut être associé à un dossier non exclu. Ajouter un PDF ne classe pas le dossier. `finish_documents` reprend RAG. Le fichier n'est ni authentifié bibliographiquement ni traité par reconnaissance optique.
7. Si Quality conserve des alertes après le budget ou utilise `fixed`, le mode humain atteint `awaiting_claims`. **Claims need your review** montre texte, motif et extraits. **Save claim decision** ajoute `ClaimReview(accept/remove)` avec justification de 4 à 2 000 caractères et événement. Une citation invalide impose `remove`. Quand toutes les alertes ont été traitées, `complete` exige au moins une affirmation retenue. Le rapport distingue l'arbitrage humain du contrôle automatique.

`DiskStore.save` versionne chaque mutation, `DiskStore.load` relit l'état et l'interface recharge après action. Les conflits de version évitent l'écrasement silencieux. `human_interventions` compte aussi une libération de point de pause, un changement de mode ou une relance RAG. Il ne compte pas le nombre de personnes, de dossiers revus ou d'uploads PDF. [UI](../../app.py) · [Superviseur](../../slr/supervisor.py) · [Modèles](../../slr/models.py) · [SQLite](../../slr/storage.py)

## Traces humaines réelles

Source de ces états et événements, `/app/data/slr.sqlite3` dans le volume Compose `review_data`.

| Revue | Fait observé | Portée |
| --- | --- | --- |
| `fffdbf8dd9f44dc4b8098f2829f5c405` | Historique `legacy`, `awaiting_screening`. 8 dossiers, 5 inclusions humaines, 1 exclusion humaine, 2 non résolus. Six événements entre 12:40:01 et 12:43:12 UTC | Décisions humaines sauvegardées, dont une proposition LLM `exclude` remplacée par `include`. Structure historique sans `review_history` moderne. Aucun RAG ou arbitrage qualité |
| `7311878fa531429a9f6e32f918c31c46` | `finish_screening` à 14:00:17 UTC, 6 inclusions et 4 non résolus, modèle et API servis par le cache, 0 preuve | Libération réelle suivie d'une abstention RAG. Aucun override moderne observé ici |
| `479f468f2c6f4cd1b10c073e25d479e3` | `continue_automatically` à 14:00:41 UTC, mêmes 6 inclus et 4 incertains, ancien RAG sans passage | Changement de mode conservé dans la trace, sans reclassification |
| `805dc2e915ac47eb85dba5146e46ffea` | Sujet différent sur la génération de tests unitaires. `finish_screening` à 15:56:57 UTC. Aucun override ni `ClaimReview`. 3 inclusions AI, 5 incertains, 5 extraits et 3 affirmations retenues | Parcours avec libération humaine et fin technique. Source export `C:/Users/Lenovo/Downloads/evaluation-805dc2e9.csv`. Aucune comparaison appariée au sujet SLR |
| `32cb856375074c8da4cd9b675ea722e2` | Ancienne revue complétée chargée en mode humain, zéro événement humain. Le validateur attribue ce mode aux anciens objets sans champ | Le mode historique ne suffit pas à établir une interaction |

Les replays de `278d886a…` enregistrent `retry_retrieval` dans la catégorie humaine. Ce fait indique la relance du harnais et ne constitue pas une annotation.

## Couverture des tests et démonstrations manquantes

| Comportement | Couverture contrôlée | Évidence interactive manquante |
| --- | --- | --- |
| Formulaire de screening | `test_streamlit_saves_short_screening_reason_for_the_correct_paper` teste un motif « No. » sur le second dossier | Capture d'un checkpoint récent et d'un override avec historique |
| Override, reprise et abstention | `test_human_override_keeps_original_ai_recommendation_and_history`, `test_human_can_override_a_batch_with_no_unresolved_papers` et `test_missing_abstract_pauses_then_resumes` | Vérifier sur une revue réelle l'effet de l'override sur le lot RAG et le rechargement de l'historique moderne |
| Bascule automatique | `test_convert_paused_ai_review_without_reclassifying_records` et événement sauvegardé réel | Capture avant/après sur une revue distincte |
| PDF et page réelle | `test_supplied_pdf_retains_page_provenance` et `test_mixed_evidence_and_cross_paper_selection_rejection` | Démontrer un upload d'article autorisé et le numéro de page dans le rapport. Usage réel de PDF dans les runs audités **NON VÉRIFIÉ** |
| Arbitrage qualité | `test_unsupported_and_budget_exhaustion_pause_for_claim_review` et `test_human_cannot_bypass_unknown_citation` | Observer `awaiting_claims` sur un cas documenté, puis sauvegarder un motif. Aucun arbitrage réel de ce type dans les revues examinées |
| Redémarrage | `test_resume_persists_and_checks_version`. Relecture réelle de sauvegardes Compose | Capture d'un override actuel avant et après redémarrage |

[Tests UI](../../tests/test_ui.py) · [Modes](../../tests/test_execution_modes.py) · [Intégration](../../tests/test_review.py) · [Stockage](../../tests/test_foundation.py) · [Captures](SCREENSHOT_CHECKLIST.md)
