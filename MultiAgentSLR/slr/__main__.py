import argparse
import json
from pathlib import Path

from evaluation.metrics import review_metrics

from .models import ReviewConfig
from .report import markdown, pdf
from .settings import Settings
from .storage import DiskStore
from .supervisor import Supervisor


def main():
    parser = argparse.ArgumentParser(description="Run, inspect or export a saved literature review")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("topic")
    run.add_argument("--provider", choices=["ollama", "groq"])
    run.add_argument("--per-source", type=int, default=4)
    run.add_argument("--screen", choices=["llm"], help=argparse.SUPPRESS)
    run.add_argument("--execution-mode", choices=["automatic", "human_in_the_loop"],
                     default="automatic")
    run.add_argument("--retrieval", choices=["classical", "agentic"], default="agentic")
    run.add_argument("--search", choices=["fixed", "react"], default="react")
    run.add_argument("--orchestration", choices=["fixed", "supervisor"], default="supervisor")
    run.add_argument("--revisions", type=int, default=1)
    run.add_argument("--inclusion", default=ReviewConfig.model_fields["inclusion"].default)
    run.add_argument("--exclusion", default=ReviewConfig.model_fields["exclusion"].default)
    run.add_argument("--record-prompts", action="store_true")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("run_id")
    export = commands.add_parser("export")
    export.add_argument("run_id")
    export.add_argument("--output", type=Path, default=Path("output"))
    args = parser.parse_args()

    settings = Settings.from_env()
    store = DiskStore(settings.data_dir)
    if args.command == "run":
        supervisor = Supervisor(store, settings, record_prompts=args.record_prompts)
        review = supervisor.start(ReviewConfig(
            topic=args.topic, provider=args.provider or settings.provider, per_source=args.per_source,
            execution_mode=args.execution_mode, retrieval=args.retrieval, search=args.search,
            orchestration=args.orchestration, revision_budget=args.revisions,
            inclusion=args.inclusion, exclusion=args.exclusion,
        ))
        if args.record_prompts:
            path = settings.experiment_dir / "live" / review.id
            path.mkdir(parents=True, exist_ok=True)
            (path / "run.json").write_text(review.model_dump_json(indent=2), encoding="utf-8")
            (path / "prompts.json").write_text(json.dumps(supervisor.prompts, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
        print(json.dumps({"id": review.id, "status": review.status, "next_stage": review.next_stage,
                          "error": review.error, "outcome_reason": review.outcome_reason,
                          "metrics": review_metrics(review)["overall"]}))
        return 1 if review.status == "failed" else 0

    review = store.load(args.run_id)
    if not review:
        parser.error("Unknown review ID for the configured data directory")
    if args.command == "inspect":
        print(review.model_dump_json(indent=2))
        return 0
    if review.status != "complete":
        parser.error(review.outcome_reason or "Finish the pending review stages in Streamlit before exporting")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "literature-review.md").write_text(markdown(review), encoding="utf-8")
    (args.output / "literature-review.pdf").write_bytes(pdf(review))
    print(f"Exported review {review.id} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
