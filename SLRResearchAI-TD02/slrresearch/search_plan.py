import re
from typing import Literal

from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field


class ResearchQuestion(BaseModel):
    """Contrat des données utilisables après le contrôle textuel."""

    identifier: str = Field(pattern=r"^RQ[0-9]+$")
    question: str = Field(min_length=15)


class WorkflowOutcome(BaseModel):
    """État observable du workflow après validation et repair éventuel."""

    status: Literal["accepted", "repaired", "human_required"]
    text: str
    questions: list[ResearchQuestion] = Field(default_factory=list)
    error: str | None = None
    repair_attempts: int = 0


RQ_PATTERN = re.compile(r"^(RQ[0-9]+)\.\s*(.{15,})$")
SEARCH_CONCEPTS = {
    "task": [
        "systematic review screening",
        "study selection",
        "title and abstract screening",
    ],
    "technology": ["large language models", "LLM", "generative AI"],
}


def extract_non_empty_lines(text: str) -> list[str]:
    """TODO 1.1 - Nettoyer le texte et retourner les lignes non vides."""
    lines = [
        line.strip()
        for line in text.strip().splitlines()
        if line.strip()
    ]
    if not lines:
        raise ValueError("Texte vide")
    return lines


def parse_rq_line(line: str) -> dict:
    """TODO 1.2 - Contrôler toute la ligne avec RQ_PATTERN.fullmatch."""
    match = RQ_PATTERN.fullmatch(line)
    if match is None:
        raise ValueError(f"Ligne non conforme : {line}")
    return {
        "identifier": match.group(1),
        "question": match.group(2).strip(),
    }


def validate_identifiers(records: list[dict]) -> None:
    """TODO 1.3 - Exiger exactement RQ1, RQ2, RQ3 dans cet ordre."""
    identifiers = [record["identifier"] for record in records]
    if identifiers != ["RQ1", "RQ2", "RQ3"]:
        raise ValueError("Les identifiants attendus sont RQ1, RQ2, RQ3")


def validate_no_duplicates(records: list[dict]) -> None:
    """TODO 1.4 - Refuser deux formulations identiques."""
    questions = [record["question"] for record in records]
    unique_questions = set(questions)

    if len(questions) != len(unique_questions):
        raise ValueError("Les trois questions doivent etre differentes")


def validate_free_text(text: str) -> list[dict]:
    """TODO 1.5 - Composer les quatre contrôles textuels précédents."""
    lines = extract_non_empty_lines(text)
    records = [parse_rq_line(line) for line in lines]
    validate_identifiers(records)
    validate_no_duplicates(records)
    return records


def build_few_shot_prompt(topic: str) -> str:
    """TODO 2 - Ajouter deux exemples sans modifier le validateur."""
    clean = topic.strip()
    if not clean:
        raise ValueError("Sujet vide")

    return f"""Propose exactement trois questions de recherche.
N'ajoute ni introduction, ni conclusion, ni JSON.

Exemple 1 - Sujet : Utilisation de l'IA pour personnaliser l'apprentissage
RQ1. Comment l'IA influence-t-elle la personnalisation pedagogique ?
RQ2. Quels risques l'IA introduit-elle dans l'evaluation ?
RQ3. Quel controle humain doit-il etre conserve ?

Exemple 2 - Sujet : Tests automatises en genie logiciel
RQ1. Comment les tests automatises ameliorent-ils la detection des defauts ?
RQ2. Quelles limites les equipes rencontrent-elles lors de leur adoption ?
RQ3. Quelles metriques permettent-elles d'evaluer leur efficacite ?

Sujet courant : {clean}
Retourne exactement trois lignes RQ1., RQ2. et RQ3."""


def build_repair_prompt(text: str, error: str) -> str:
    """TODO 3 - Demander une correction de forme ciblée."""
    return f"""Tu corriges la forme d'une sortie destinee a un programme.

[TACHE]
Corrige uniquement la forme du texte fourni.
Preserve le sens des questions.

[ERREUR DETECTEE]
{error}

[CONTRAT ATTENDU]
- Exactement trois lignes.
- Chaque ligne commence par RQ1., RQ2. puis RQ3.
- N'ajoute ni introduction, explication, Markdown ou JSON.

[EXEMPLE CONFORME]
RQ1. Comment l'IA influence-t-elle la personnalisation pedagogique ?
RQ2. Quels risques l'IA introduit-elle dans l'evaluation ?
RQ3. Quel controle humain doit-il etre conserve ?

[TEXTE A CORRIGER]
{text}

[SORTIE]
Retourne uniquement les trois lignes conformes."""


def repair_with_llm(model, text: str, error: str) -> str:
    """Code fourni : un seul appel conditionnel de réparation."""
    response = model.invoke(build_repair_prompt(text, error))
    return str(response.content).strip()


def validate_questions(records: list[dict]) -> list[ResearchQuestion]:
    """TODO 4 - Appliquer le contrat Pydantic à chaque dictionnaire."""
    questions = []
    for record in records:
        # TODO 4 - Remplacer None par l'appel Pydantic indiqué dans l'énoncé.
        question = ResearchQuestion.model_validate(record)
        questions.append(question)
    return questions



def build_queries(questions: list[ResearchQuestion]) -> dict[str, str]:
    """TODO 5 - Produire synonymes OR, concepts AND."""
    if not questions:
        raise ValueError("Au moins une RQ validée est nécessaire")
    combinations = []
    for task in SEARCH_CONCEPTS["task"]:
        for technology in SEARCH_CONCEPTS["technology"]:
            # TODO 5 - Construire ici ("task" AND "technology").
            expression = f'("{task}" AND "{technology}")'
            combinations.append(expression)
    base_query = " OR ".join(combinations)
    return {
        "scholar": base_query,
        "ieee": base_query,
        "acm": base_query,
    }


def build_question_pipeline():
    """TODO 6 - Composer regex | Pydantic | requêtes avec LCEL."""
    # TODO 6 - Remplacer chaque fonction identité par la fonction du bon stade.
    text_control = RunnableLambda(validate_free_text)
    data_contract = RunnableLambda(validate_questions)
    query_builder = RunnableLambda(build_queries)
    return text_control | data_contract | query_builder


def run_controlled_workflow(model, text: str) -> WorkflowOutcome:
    """TODO 7 - Valider, réparer une fois, revalider ou escalader."""
    try:
        # Code fourni - chemin nominal : aucune réparation si le texte est valide.
        records = validate_free_text(text)
        questions = validate_questions(records)
        return WorkflowOutcome(
            status="accepted",
            text=text,
            questions=questions,
            repair_attempts=0,
            error=None,
        )

    except ValueError as first_error:
        # Code fourni - une seule tentative de réparation après l'échec.
        repaired_text = repair_with_llm(
            model,
            text,
            str(first_error),
        )
        try:
            # TODO 7.1 — Revalider la réponse produite par le repair.
            #
            # Ligne 1 : appeler validate_free_text(repaired_text) et ranger
            #           son résultat dans repaired_records.
            # Ligne 2 : appeler validate_questions(repaired_records) et ranger
            #           son résultat dans repaired_questions.
            #
            # Vous devez donc remplacer uniquement les deux valeurs None.
            repaired_records = validate_free_text(repaired_text)
            repaired_questions = validate_questions(repaired_records)

            return WorkflowOutcome(
                status="repaired",
                text=repaired_text,
                questions=repaired_questions,
                repair_attempts=1,
                error=None,
            )

        except ValueError as second_error:
            # TODO 7.2 — Le texte réparé vient d'échouer à son tour.
            # Remplacer uniquement "accepted" par "human_required".
            # Ne modifiez aucune autre ligne et ne rappelez pas le LLM.
            return WorkflowOutcome(
                status="human_required",
                text=repaired_text,
                questions=[],
                repair_attempts=1,
                error=str(second_error),
            )
