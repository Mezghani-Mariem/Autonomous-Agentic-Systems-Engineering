# Compte rendu TD03 - SearchAgent ReAct controle

## Informations generales

**TD :** TD03 - Du workflow outille a l'agent ReAct controle  
**Projet :** SLRResearchAI  
**Date de rendu :** 12 octobre 2026

## Fichiers Python modifies

Les fichiers Python modifies pendant le TD03 sont :

- `slrresearch/contracts.py`
- `slrresearch/tools.py`
- `slrresearch/real_tools.py`
- `slrresearch/runtime.py`
- `slrresearch/workflow.py`
- `slrresearch/policies.py`
- `slrresearch/react_agent.py`

## Resume du travail realise

Dans ce TD, l'objectif etait de passer d'un workflow outille controle a un agent
ReAct controle. Le workflow execute les outils dans un ordre fixe defini par le
programme, tandis que l'agent ReAct demande a une politique de decision de
proposer l'action suivante a partir de l'etat courant.

Le travail realise a consiste a :

- definir et valider le contrat `AgentAction`;
- appliquer une liste blanche d'outils avec `ToolRegistry`;
- connecter les outils scientifiques reels OpenAlex, Crossref et Semantic Scholar;
- transformer les resultats, erreurs HTTP, erreurs reseau et refus en `Observation`;
- mettre a jour l'etat persistant `SearchState`;
- implementer le workflow deterministe;
- implementer la politique de decision LLM;
- assembler la boucle ReAct controlee avec validation, execution, observation et conditions d'arret.

La validation finale donne le resultat suivant :

```text
23 passed
```

## Reponses aux questions de reflexion

### 1. Ou la decision de l'outil est-elle prise dans la Version A ?

Dans la Version A, la decision est prise directement par le programme Python.
La fonction `run_tool_workflow()` parcourt les requetes dans l'ordre de
`queries.items()` et construit une action `search` pour chaque outil. L'ordre
des outils est donc fixe a l'avance par le workflow.

### 2. Ou est-elle prise dans la Version B ?

Dans la Version B, la decision est prise par une politique de decision appelee a
chaque tour de la boucle ReAct. Cette politique peut etre une politique
reproductible ou un LLM. Elle recoit l'etat courant et la liste des outils
autorises, puis propose une action. Le programme garde ensuite le controle de la
validation et de l'execution.

### 3. Pourquoi `AgentAction` ne doit-elle pas executer elle-meme l'outil ?

`AgentAction` represente seulement une decision structuree. Elle ne doit pas
executer l'outil, car cela melangerait le contrat de donnees avec l'execution.
L'execution doit rester dans le runtime, ou l'action peut etre validee,
autorisee, journalisee et transformee en observation.

### 4. Pourquoi Pydantic ne remplace-t-il pas `ToolRegistry` ?

Pydantic verifie la structure et les types des donnees, par exemple que
`tool` est une chaine et que `limit` respecte les bornes. En revanche, Pydantic
ne sait pas si le nom d'outil propose appartient a la liste blanche du systeme.
Cette verification d'autorisation est le role de `ToolRegistry`.

### 5. Quelle difference existe entre une erreur et une observation d'erreur ?

Une erreur brute interrompt normalement l'execution du programme. Une
observation d'erreur est une information structuree ajoutee a l'etat, avec un
statut comme `rate_limited`, `http_error`, `network_error` ou `unauthorized`.
Ainsi, l'agent peut continuer a raisonner et adapter sa prochaine action.

### 6. Pourquoi un resultat vide doit-il etre conserve dans l'etat ?

Un resultat vide est une information utile. Il indique qu'un outil a bien ete
appele, mais qu'il n'a pas trouve d'article pour la requete donnee. Si cette
observation est conservee, l'agent peut eviter de repeter inutilement la meme
recherche et choisir une autre source.

### 7. Pourquoi l'etat complet n'est-il pas automatiquement envoye au LLM ?

L'etat complet peut contenir trop d'informations, ou des informations qui ne
sont pas necessaires a la decision. Le projet utilise une projection controlee
avec `state_for_decision()`, qui expose seulement l'objectif, les requetes, les
outils deja appeles, la derniere observation, le nombre d'articles trouves et
l'etape courante.

### 8. Comment un HTTP 429 peut-il modifier la prochaine decision ?

Un HTTP 429 signifie que l'outil est limite temporairement. Comme cette erreur
est transformee en observation `rate_limited`, la politique de decision peut
constater que la source precedente n'est pas disponible et proposer une autre
source, par exemple Crossref apres un echec d'OpenAlex.

### 9. Pourquoi `finish` ne produit-il pas une observation d'outil ?

`finish` n'appelle aucun outil externe. C'est une decision d'arret de l'agent,
pas une action de recherche. Elle met fin a la boucle avec le statut
`agent_finish`, mais elle ne produit pas d'observation d'outil.

### 10. Que protege `max_steps` ?

`max_steps` protege contre les boucles infinies ou les agents qui ne proposent
jamais `finish`. Meme si la politique continue a demander des recherches,
la boucle ReAct s'arrete automatiquement lorsque le nombre maximal d'etapes est
atteint.

### 11. Quelle difference existe entre `target_reached` et `agent_finish` ?

`target_reached` signifie que le programme a arrete l'agent car le nombre cible
d'articles uniques a ete atteint. `agent_finish` signifie que la politique de
decision elle-meme a propose l'action `finish`. Dans le premier cas, l'arret est
impose par une regle du runtime; dans le second, il vient de la decision de
l'agent.

### 12. Pourquoi les tests utilisent-ils `ScriptedPolicy` plutot qu'un vrai LLM ?

Les tests doivent etre deterministes et reproductibles. Un vrai LLM peut changer
sa reponse selon le modele, le prompt, le reseau ou la configuration. Avec
`ScriptedPolicy`, les actions sont fixees a l'avance, ce qui permet de verifier
precisement la logique de la boucle ReAct.

### 13. La politique reproductible est-elle reellement intelligente ?

Non, elle n'est pas reellement intelligente. Elle suit des regles ou une liste
d'actions prevues. Elle sert surtout a montrer le fonctionnement de la boucle
ReAct sans dependre d'un LLM reel. Elle est utile pour les tests et pour
comparer le comportement du workflow et de l'agent.

### 14. A partir de quel moment peut-on raisonnablement parler d'agent dans ce TD ?

On peut parler d'agent lorsque le systeme choisit l'action suivante a partir de
l'etat courant et des observations precedentes, au lieu d'executer simplement
un ordre fixe. Dans ce TD, cela correspond a la Version B, ou la boucle ReAct
repete les etapes decider, valider, agir, observer et mettre a jour l'etat.

### 15. Pourquoi ReAct controle ne signifie-t-il pas autonomie illimitee ?

Dans ce TD, le decideur propose seulement une action. Il ne peut pas executer
directement un outil. Chaque action passe par `AgentAction`, par
`ToolRegistry`, puis par le runtime. De plus, la boucle est limitee par
`max_steps`, par `target_papers` et par l'action `finish`. L'autonomie est donc
encadree par le programme.

### 16. Le LLM appelle Semantic Scholar alors que la politique reproductible peut s'arreter apres Crossref. Cette difference prouve-t-elle que le LLM possede une meilleure strategie ? Proposez une condition d'arret hybride, mesurable et reproductible.

Cette difference ne prouve pas que le LLM possede une meilleure strategie. Elle
montre seulement que le LLM interprete le contexte differemment de la politique
reproductible. Une strategie meilleure doit etre definie avec des criteres
mesurables.

Une condition d'arret hybride possible serait :

- s'arreter si au moins deux sources differentes ont retourne un statut
  `success`;
- ou s'arreter si le nombre d'articles uniques atteint `target_papers`;
- ou s'arreter si toutes les sources autorisees ont ete essayees;
- dans tous les cas, conserver `max_steps` comme garde-fou.

Cette condition combine la decision de l'agent avec une couverture minimale
verifiable.

### 17. Pourquoi les tests des outils reels remplacent-ils `httpx.get`, alors que la validation finale dans Streamlit doit appeler les veritables API ?

Les tests remplacent `httpx.get` pour eviter de dependre d'Internet, des quotas
API, des lenteurs reseau ou des erreurs temporaires. Cela permet de tester la
configuration des appels et la normalisation des resultats de maniere
reproductible. En revanche, la validation finale dans Streamlit doit utiliser
les vraies API pour verifier que l'agent peut fonctionner avec des sources
scientifiques reelles.

## Commandes utilisees pour la validation

Comme le dossier temporaire par defaut de pytest peut etre bloque sous Windows,
la commande suivante peut etre utilisee :

```powershell
cd C:\Users\Lenovo\Desktop\agent\SLRResearchAI-TD03
New-Item -ItemType Directory -Force .pytest-tmp
python -m pytest -v --basetemp .pytest-tmp
```

Pour afficher la demonstration en terminal :

```powershell
python -X utf8 main.py
```

Pour lancer l'interface :

```powershell
python -X utf8 -m streamlit run streamlit_app.py --server.headless true --server.port 8501
```

