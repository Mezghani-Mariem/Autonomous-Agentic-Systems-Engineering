import argparse
from pathlib import Path

from slr.settings import Settings

from .benchmarks import BENCHMARKS, run_benchmark
from .metrics import load_annotations


def main():
    parser = argparse.ArgumentParser(description="Run the paired Multi-Agent SLR benchmarks")
    parser.add_argument("experiment", choices=[*BENCHMARKS, "controlled", "all"])
    parser.add_argument("--annotations", type=Path, help="Independent screening reference CSV")
    args = parser.parse_args()
    settings = Settings.from_env()
    annotations = load_annotations(args.annotations.read_text(encoding="utf-8-sig")) if args.annotations else None
    keys = {"controlled": ["a", "c", "d"], "all": BENCHMARKS}.get(args.experiment, [args.experiment])
    for key in keys:
        path, _ = run_benchmark(key, settings, annotations)
        print(f"{BENCHMARKS[key]} -> {path}")


if __name__ == "__main__":
    main()
