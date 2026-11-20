# Note de synthèse pédagogique

## Périmètre

Cette note illustre Plan-and-Execute sur un mini-corpus non exhaustif. Elle ne constitue pas une SLR publiable. Chaque affirmation provient des preuves autorisées issues du TD06.

## RQ1 — Que montrent les études sélectionnées sur la sensibilité des LLM pendant le screening ?

### Réponse synthétique

Après calibration, la sensibilité atteint 100 % pour les études finalement incluses, mais varie entre 58 % et 100 % au stade titre-résumé. La règle équilibrée obtient 81,1 % à 96,5 % de sensibilité ; la règle orientée rappel atteint 94,6 % à 99,8 % mais réduit la spécificité.

### Traçabilité des preuves

- **Development and evaluation of prompts for a large language model to screen titles and abstracts in a living systematic review** — `PMID40701625`, page 1, preuve `E1`
  - Donnée extraite : Sensibilité élevée après calibration, avec variation entre mises à jour.
  - Limite : Une seule revue en santé mentale et un prompt adapté à ce corpus.
- **Sensitivity and Specificity of Using GPT-3.5 Turbo Models for Title and Abstract Screening in Systematic Reviews and Meta-analyses** — `PMID38768452`, page 1, preuve `E2`
  - Donnée extraite : Le seuil modifie le compromis sensibilité-spécificité.
  - Limite : Petit nombre de revues et performance dépendante du prompt.

## RQ2 — Quel compromis les études observent-elles entre charge économisée et risque d'erreur ?

### Réponse synthétique

La réduction simulée de charge varie entre 65 % et 85 %, avec très peu de fausses exclusions finales. La sensibilité parfaite réduit moins la charge ; une réduction proche de 94 % s'accompagne d'une sensibilité voisine de 0,94.

### Traçabilité des preuves

- **Development and evaluation of prompts for a large language model to screen titles and abstracts in a living systematic review** — `PMID40701625`, page 1, preuve `E3`
  - Donnée extraite : Réduction de charge simulée de 65 % à 85 %.
  - Limite : Gain simulé dans un seul contexte après calibration.
- **High-performance automated abstract screening with large language model ensembles** — `PMID40119675`, page 1, preuve `E4`
  - Donnée extraite : La réduction de charge et le rappel maximal ne sont pas obtenus simultanément.
  - Limite : Précision positive faible sur un corpus réel très déséquilibré.

## RQ3 — Quels mécanismes de contrôle et de validation les études recommandent-elles avant un déploiement réel ?

### Réponse synthétique

La variation entre revues impose une validation locale et favorise un fonctionnement parallèle avec un reviewer humain. Le LLM est proposé comme second screener ; un prompt séparé par critère rend les décisions plus contrôlables. Limite scientifique explicitée par le plan révisé : Synthétiser les mécanismes de contrôle étayés et signaler explicitement l'absence de validation prospective.

### Traçabilité des preuves

- **High-performance automated abstract screening with large language model ensembles** — `PMID40119675`, page 1, preuve `E5`
  - Donnée extraite : La performance varie selon la revue et le domaine.
  - Limite : Principalement des revues Cochrane et exclusion des notices sans résumé.
- **Generative pretrained transformer models can function as highly reliable second screeners** — `PMID40638273`, page 1, preuve `E6`
  - Donnée extraite : Le rôle de second screener et le multiprompt renforcent le contrôle.
  - Limite : Validation limitée au domaine de la psychologie.

## Conclusion

Les trois questions ont été traitées dans le périmètre du mini-corpus. Lorsque les preuves étaient insuffisantes, la note a explicité la limite au lieu d'inventer une réponse.
