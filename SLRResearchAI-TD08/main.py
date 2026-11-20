import json
from pathlib import Path

from slrresearch.orchestrator import full_pipeline_run, full_supervisor_run
from slrresearch.quality_agent import evaluate_rules, run_quality_loop
from slrresearch.td08_runtime import artifact_writer, build_artifact_workers, build_state, load_td08_artifacts

ROOT = Path(__file__).parent
OBJECTIVE = "Contrôler la fidélité d'une note SLR avant sa livraison."


def run_demo(root: Path = ROOT) -> dict:
    """Rejoue les deux phases sur les artefacts fournis, sans service externe."""
    evidence, required_rqs, draft, repaired = load_td08_artifacts(root)
    evaluate = lambda report: evaluate_rules(report, evidence, required_rqs)
    initial = evaluate(draft)
    corrected = evaluate(repaired)
    reflection = run_quality_loop(
        draft, evidence, required_rqs, artifact_writer(repaired), max_revisions=1,
    )
    exhausted = run_quality_loop(
        draft, evidence, required_rqs, lambda report, feedback: report, max_revisions=1,
    )
    # Chaque expérience dispose de ses propres workers et de son propre état.
    pipeline = full_pipeline_run(
        build_state(draft, evidence, OBJECTIVE, budget=8),
        build_artifact_workers(root, evidence, draft, repaired), evaluate,
    )
    supervisor = full_supervisor_run(
        build_state(draft, evidence, OBJECTIVE, budget=8),
        build_artifact_workers(root, evidence, draft, repaired), evaluate,
        max_handoffs=8,
    )
    return {
        "schema_version": "TD08-EXECUTION-1.0",
        "mode": "Artefacts pédagogiques et règles déterministes",
        "actual_llm_calls": 0,
        "scope": "Les workers rejouent les artefacts fournis ; aucune recherche ou génération LLM réelle.",
        "initial_quality": initial.model_dump(mode="json"),
        "repaired_quality": corrected.model_dump(mode="json"),
        "reflection": {
            "quality": reflection["quality"].model_dump(mode="json"),
            "history": [item.model_dump(mode="json") for item in reflection["history"]],
        },
        "reflection_without_repair": {
            "quality": exhausted["quality"].model_dump(mode="json"),
            "history": [item.model_dump(mode="json") for item in exhausted["history"]],
        },
        "pipeline": pipeline.model_dump(mode="json"),
        "supervisor": supervisor.model_dump(mode="json"),
    }


def render_note(report: dict) -> str:
    claims = {item["id"]: item for item in report["claims"]}
    lines = [f"# {report['title']}", "",
             "Note pédagogique corrigée à partir des artefacts fournis. Le contrôle lexical ne constitue pas une validation scientifique.", ""]
    for section in report["sections"]:
        lines.extend([f"## {section['rq_id']} — {section['title']}", ""])
        for claim_id in section["claim_ids"]:
            claim = claims[claim_id]
            lines.append(f"- **{claim_id}** — {claim['text']} [{', '.join(claim['evidence_ids'])}]")
        lines.append("")
    return "\n".join(lines)


def main():
    result = run_demo()
    output = ROOT / "artifacts" / "td08_execution.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    note = ROOT / "artifacts" / "td08_note_corrigee.md"
    note.write_text(render_note(result["supervisor"]["state"]["report"]), encoding="utf-8")
    print("TD08 — QualityAgent et orchestration (mode déterministe)")
    for label, key in [("Note initiale", "initial_quality"), ("Note corrigée", "repaired_quality")]:
        quality = result[key]
        print(f"{label} : {quality['verdict']}, score={quality['score']:.2%}, fidélité={quality['faithfulness']:.0%}")
    for pattern in ["pipeline", "supervisor"]:
        execution = result[pattern]
        print(f"{pattern} : {execution['status']}")
        print("  " + " → ".join(execution["transitions"]))
    print(f"Réflexion sans correction : {result['reflection_without_repair']['quality']['verdict']}")
    print(f"Résultats : {output}\nNote corrigée : {note}")


if __name__ == "__main__":
    main()

