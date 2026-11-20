# Compte rendu TD02 - Du texte libre au workflow controle

## Informations

TD : TD02 - SLRResearchAI  
Fichier Python a soumettre : `slrresearch/search_plan.py`  
Document : reponses aux questions de synthese

## Reponses aux questions de synthese

### 1. Pourquoi une sortie lisible peut-elle etre inutilisable par un programme ?

Une sortie peut etre claire pour un humain mais inutilisable par un programme si sa forme n'est pas stable. Par exemple, un humain comprend une introduction comme "Voici mes propositions", mais le programme attend exactement trois lignes commencant par `RQ1.`, `RQ2.` et `RQ3.`. Sans format previsible, le code ne peut pas extraire les donnees de maniere fiable.

### 2. Quelle difference existe entre regex et Pydantic ?

La regex controle surtout la forme textuelle brute. Dans ce TD, elle verifie que chaque ligne respecte le format `RQn. question` et permet d'extraire l'identifiant et la question. Pydantic intervient ensuite sur les donnees structurees pour verifier le contrat : presence des champs, types, format de l'identifiant et longueur minimale de la question.

### 3. Pourquoi le prompt n'est-il pas un contrat logiciel ?

Un prompt influence la reponse du LLM, mais il ne garantit pas que le modele respectera toujours les consignes. Le LLM peut ajouter une introduction, changer le format ou produire une sortie incomplete. Un contrat logiciel doit etre verifie par du code deterministe, avec des erreurs explicites lorsque les donnees ne sont pas conformes.

### 4. Pourquoi conserver le meme validateur pour zero-shot et few-shot ?

Il faut conserver le meme validateur pour comparer les sorties de facon objective. Le few-shot peut ameliorer le respect du format, mais il ne remplace pas la validation. Utiliser un validateur different rendrait le controle moins fiable et pourrait accepter des sorties non conformes simplement parce qu'elles proviennent d'un autre prompt.

### 5. Pourquoi transmettre l'erreur exacte au repair ?

Transmettre l'erreur exacte permet au LLM de repair de corriger le probleme precis qui a ete detecte. Par exemple, si l'erreur indique une ligne non conforme, le modele sait qu'il doit corriger la forme et non inventer de nouvelles questions. Cela rend la reparation plus ciblee et limite le risque de modifier le sens des questions.

### 6. Pourquoi borner le repair a une tentative ?

Borner le repair a une tentative permet de controler le cout, le temps d'execution et le comportement du workflow. Sans limite, le systeme pourrait entrer dans une boucle de corrections successives sans garantie de succes. Apres un second echec, il est plus prudent de demander une validation humaine.

### 7. Quand faut-il s'abstenir et demander un humain ?

Il faut demander un humain lorsque la sortie initiale est invalide et que la tentative de repair reste elle aussi invalide apres revalidation. Dans ce cas, le systeme ne doit pas faire confiance a une sortie non conforme. Le statut `human_required` indique que l'automatisation s'arrete et qu'une decision humaine est necessaire.

### 8. Pourquoi LCEL convient-il a la transformation finale ?

LCEL convient car la transformation finale est une chaine ordonnee de fonctions deterministes. Le texte est d'abord valide par regex, puis transforme en objets Pydantic, puis converti en requetes booleennes. Les sorties et entrees de chaque etape correspondent bien, ce qui permet de composer clairement `validate_free_text | validate_questions | build_queries`.

### 9. Pourquoi ce workflow controle n'est-il pas encore un agent autonome ?

Ce workflow n'est pas encore un agent autonome car il suit un chemin fixe. Il ne choisit pas dynamiquement des outils, ne planifie pas plusieurs actions, ne lance pas de recherche documentaire et ne prend pas de decisions complexes sur l'environnement. Il encadre seulement une sortie LLM avec validation, repair borne et transformation deterministe.

### 10. Quel artefact sera donne au SearchAgent du TD03 ?

L'artefact donne au `SearchAgent` du TD03 sera la strategie de recherche booleenne produite par la chaine LCEL. Elle prend la forme d'un dictionnaire contenant des requetes pour plusieurs moteurs, par exemple `scholar`, `ieee` et `acm`. Ces requetes combinent les concepts de tache et de technologie avec `AND` et les synonymes avec `OR`.

## Validation

La validation attendue pour le TD02 est :

```bash
python -m pytest -v
```

Resultat attendu :

```text
13 passed
```
