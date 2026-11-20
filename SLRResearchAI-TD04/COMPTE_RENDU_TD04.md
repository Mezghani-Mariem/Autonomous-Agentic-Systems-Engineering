# Compte rendu TD04 - Du resultat de recherche au screening controle

## Informations generales

**TD :** TD04 - Du resultat de recherche au screening controle  
**Projet :** SLRResearchAI  
**Date :** 13 octobre 2026

## Fichiers Python modifies

Les fichiers modifies pendant le TD04 sont :

- `slrresearch/screening_agent.py`
- `slrresearch/llm_screening_agent.py`

Les autres fichiers correspondent aux acquis des TD precedents ou aux fichiers
fournis pour le TD04.

## Resume du travail realise

Le TD04 consomme l'artefact `artifacts/search_results.json` produit par le TD03.
Cet artefact contient les resultats de recherche dedupliques, sous forme de
papiers avec titre, resume, DOI, source, URL et information d'acces libre.

Le but du TD04 est de faire un screening titre/resume avant l'etape suivante,
qui pourra traiter les textes integraux. Dans ce TD, une decision `include`
signifie que le papier doit passer a l'etape suivante. Une decision `exclude`
reste une recommandation controlee, et les cas incertains ou sensibles sont
envoyes a l'humain.

Deux approches ont ete implementees :

- **A : agent deterministe**, fonde sur des mots-cles et une politique fixe;
- **B : agent LLM controle**, qui produit une sortie structuree et dont la preuve
  est verifiee localement;
- **C : comparaison**, qui detecte accords, desaccords et besoins d'arbitrage
  humain.

Validation obtenue :

```text
14 passed pour les tests propres au TD04
37 passed pour les tests cumulatifs
```

## Explication des TODO

### TODO 1 - Normaliser le texte du papier

La fonction `normalize_paper_text()` construit le texte analyse a partir du
titre et du resume :

```python
text = (paper.title + " " + paper.abstract).lower()
```

Le passage en minuscules permet de comparer les mots-cles sans etre sensible a
la casse. L'espace evite de coller le dernier mot du titre au premier mot du
resume.

### TODO 2 - Observer les indicateurs

La fonction `observe_indicators()` cherche les termes d'inclusion et
d'exclusion dans le texte normalise. Elle ne decide pas encore du verdict. Elle
produit seulement des signaux :

- termes d'inclusion trouves;
- termes d'exclusion trouves;
- information suffisante ou non;
- conflit entre inclusion et exclusion.

Les listes sont triees avec `sorted()` pour obtenir un resultat reproductible.

### TODO 3 - Choisir un verdict provisoire

La fonction `choose_preliminary_verdict()` applique la politique du TD :

1. si un terme d'exclusion est detecte, le verdict est `exclude`;
2. sinon, si un terme d'inclusion est detecte, le verdict est `include`;
3. sinon, le verdict est `uncertain`.

L'exclusion est prioritaire. Les confiances sont fixees par la regle :

- `0.95` pour `exclude`;
- `0.90` pour `include`;
- `0.45` pour `uncertain`.

### TODO 4 - Decider si un humain doit revoir le cas

La fonction `requires_human_review()` demande une revue humaine si une seule
condition est vraie :

- le verdict est `uncertain`;
- la confiance est inferieure au seuil;
- il existe un conflit entre signaux;
- le titre ou le resume est insuffisant.

Cela evite d'automatiser des decisions fragiles.

### TODO 5 - Construire la decision structuree

La fonction `apply_screening_policy()` retourne un objet `ScreeningDecision`.
Cet objet conserve :

- l'identifiant du papier;
- le verdict;
- la confiance;
- les raisons;
- les indicateurs observes;
- le drapeau `needs_human_review`.

La decision reste donc explicable et tracable.

### TODO 6 - Orchestrer le ScreeningAgent

`ScreeningAgent.run()` parcourt tous les papiers de l'artefact TD03. Pour chaque
papier, il observe les indicateurs, applique la politique, puis ajoute la
decision a la liste. Ensuite, il construit la file humaine avec les decisions
dont `needs_human_review` vaut `True`.

### TODO 7 - Construire le prompt LLM

La fonction `build_screening_messages()` construit deux messages :

- un `SystemMessage`, qui fixe les regles du LLM;
- un `HumanMessage`, qui contient le sujet, les criteres et le papier.

Le prompt impose au LLM de choisir seulement `include`, `exclude` ou
`uncertain`, d'utiliser uniquement le titre et le resume, de ne rien inventer,
de produire une confiance entre `0` et `1`, et de donner une preuve copiee du
texte fourni.

### TODO 8 - Faire un appel structure

La fonction `invoke_structured_screening()` utilise :

```python
structured_model = model.with_structured_output(LLMScreeningDecision)
decision = structured_model.invoke(messages)
```

Le schema Pydantic impose la forme de sortie du LLM. L'identifiant du papier est
ensuite remplace par `paper.id`, car l'identite technique ne doit pas dependre
du LLM.

### TODO 9 - Verifier l'ancrage de la preuve

La fonction `validate_grounding()` accepte la sortie du LLM seulement si :

- la decision est `uncertain` et la preuve est vide;
- ou la preuve non vide apparait reellement dans le titre ou le resume.

Si le LLM invente une preuve, le papier devient `uncertain` et part en revue
humaine. Le lot complet n'est pas interrompu.

### TODO 10 - Comparer A et B

La fonction `compare_decisions()` compare la decision deterministe et la
decision LLM. Elle demande l'humain si :

- les deux agents ne sont pas d'accord;
- ou l'agent deterministe demande l'humain;
- ou l'agent LLM demande l'humain.

Cette etape C ne refait pas un screening. Elle route les cas vers `AUTO` ou
`HUMAN`.

## Commandes de validation

Pour eviter les problemes de permission du dossier temporaire Windows :

```powershell
cd C:\Users\Lenovo\Desktop\agent\SLRResearchAI-TD04
New-Item -ItemType Directory -Force .pytest-tmp
python -m pytest -v --basetemp .pytest-tmp
```

Pour tester seulement TD04 :

```powershell
python -m pytest -v tests\test_td04.py tests\test_td04_llm.py --basetemp .pytest-tmp
```

Pour lancer la demonstration terminal :

```powershell
python -X utf8 main.py
```

Pour lancer Streamlit :

```powershell
python -X utf8 -m streamlit run streamlit_app.py --server.headless true --server.port 8502
```

Adresse locale :

```text
http://localhost:8502
```

## Reponses aux questions d'interpretation

### 1. Pourquoi utiliser un artefact plutot qu'importer directement le code du TD03 ?

Un artefact separe clairement les etapes du pipeline. Le TD04 consomme le
resultat produit par le TD03 sans relancer la recherche ni dependre du code
interne du TD03. Cela rend la transmission plus robuste, reproductible et
verifiable.

### 2. Que garantit Pydantic lors du chargement ? Que ne garantit-il pas ?

Pydantic garantit la structure du fichier : presence des champs, types,
origine `TD03`, version du schema et liste non vide de papiers. En revanche, il
ne garantit pas la qualite scientifique des articles, la pertinence des resumes
ou l'exactitude des metadonnees.

### 3. Pourquoi certains papiers reels sans resume n'empechent-ils pas le chargement ?

L'absence de resume est une limite normale des metadonnees scientifiques. Le
contrat accepte un resume vide, car un papier peut exister meme si l'API n'a pas
fourni d'abstract. Cette insuffisance est traitee plus tard par la politique de
screening, qui envoie ces cas vers l'humain.

### 4. Quelle difference existe entre un critere et un indicateur ?

Un critere est une regle definie a l'avance, par exemple inclure les papiers sur
le screening des SLR. Un indicateur est un signal observe dans un papier, par
exemple la presence du mot `screening` dans le titre ou le resume.

### 5. Pourquoi separer `observe_indicators()` et `apply_screening_policy()` ?

Cette separation rend le systeme plus clair. `observe_indicators()` observe les
signaux sans decider. `apply_screening_policy()` transforme ces signaux en
verdict. On peut donc modifier la politique sans changer l'extraction des
signaux.

### 6. Pourquoi l'exclusion est-elle prioritaire dans cette politique ?

L'exclusion est prioritaire pour eviter d'inclure automatiquement un papier qui
contient un signal sensible d'exclusion, comme `medicine` ou `clinical trial`.
Cela rend la politique plus prudente.

### 7. Pourquoi un papier sur le recrutement contenant le mot `screening` peut-il tromper l'agent deterministe ?

L'agent deterministe cherche des sous-chaines. Il ne comprend pas le sens du mot
dans son contexte. Le mot `screening` peut designer un filtrage dans un autre
domaine, par exemple le recrutement, et non le screening des articles dans une
SLR.

### 8. Pourquoi `uncertain` est-il preferable a une decision forcee ?

`uncertain` evite de produire une fausse certitude lorsque les informations sont
insuffisantes ou ambiguës. Dans un processus scientifique, il vaut mieux
transmettre un cas douteux a l'humain que l'inclure ou l'exclure sans preuve
suffisante.

### 9. Pourquoi la confiance du TD n'est-elle pas une probabilite calibree ?

La confiance est une valeur fixee par la politique du TD. Elle n'est pas apprise
statistiquement et ne provient pas d'un modele calibre. Elle sert seulement a
controler l'automatisation.

### 10. Quelles limites de deduplication subsistent entre les resultats OpenAlex et Crossref de l'artefact reel ?

La deduplication peut manquer certains doublons si les DOI sont absents,
mal formates ou differents entre sources. Deux notices du meme article peuvent
aussi avoir des titres legerement differents. Il peut donc rester des doublons
ou, inversement, des notices proches mais distinctes peuvent etre fusionnees a
tort si la cle choisie est trop simple.

### 11. Comment ameliorer le TD03 pour conserver le meilleur resume de plusieurs sources ?

On pourrait fusionner les notices equivalentes au lieu de garder seulement la
premiere. Pour chaque groupe deduplique, le systeme pourrait conserver le resume
le plus long, le plus complet, ou celui provenant d'une source prioritaire.

### 12. Quels verdicts le TD suivant doit-il utiliser pour decider quels PDF telecharger ?

Le TD suivant devrait telecharger les PDF des papiers `include` et probablement
des papiers `uncertain` qui necessitent une verification approfondie. Les
`exclude` peuvent etre ignores, sauf s'ils ont ete marques pour revue humaine.

### 13. Pourquoi le LLM peut-il mieux interpreter le contexte qu'une recherche par sous-chaine ?

Le LLM peut prendre en compte la phrase complete, la negation et le sens global
du titre/resume. Une recherche par sous-chaine detecte seulement la presence de
mots, meme s'ils sont utilises dans un contexte qui contredit le critere.

### 14. Pourquoi `with_structured_output()` ne garantit-il ni l'ancrage ni la pertinence scientifique de la preuve ?

`with_structured_output()` impose la forme de la sortie, pas sa verite. Le LLM
peut produire un champ `evidence` bien forme mais invente ou peu pertinent.
C'est pourquoi le programme verifie localement que la preuve apparait dans le
titre ou le resume.

### 15. Pourquoi un desaccord entre les deux agents doit-il etre visible plutot que resolu silencieusement ?

Un desaccord signale un cas ambigu ou fragile. Le cacher donnerait une fausse
impression d'automatisation fiable. Le rendre visible permet a un humain
d'arbitrer et de comprendre pourquoi les deux approches divergent.

### 16. Un accord entre les deux agents suffit-il toujours pour automatiser ?

Non. Meme si les deux agents sont d'accord, l'un des deux peut demander une
revue humaine a cause d'une information insuffisante, d'une preuve fragile ou
d'un conflit. L'accord n'est exploitable automatiquement que si aucun agent ne
demande l'humain.

### 17. Pourquoi C est-il un mecanisme de cooperation et non un troisieme classifieur ?

C ne produit pas un nouveau verdict scientifique. Il compare les sorties de A et
B, verifie les drapeaux `needs_human_review`, puis decide si le cas peut rester
automatique ou doit etre transmis a l'humain. C organise donc la cooperation
entre agents et evaluateur humain.

