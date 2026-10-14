"""Evaluate confirmed annotations and ruler observations, retaining failed cases."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from photomeasure.evaluation import run_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hardware", default="unspecified — record laptop and camera before publishing")
    parser.add_argument("--data-kind", choices=["real", "synthetic"], default="real")
    args = parser.parse_args()
    try:
        result = run_evaluation(args.manifest, args.output, args.hardware, args.data_kind)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({key: result[key] for key in ("data_kind", "attempted", "successful", "failed")}, indent=2))
    print(f"Saved reports to {args.output}. Read failures.md and summary.json before making claims.")


if __name__ == "__main__":
    main()
