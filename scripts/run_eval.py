"""Run the full evaluation harness and write reports/eval_report.md."""
from __future__ import annotations

import os
import sys

# Allow running as `python scripts/run_eval.py` from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from support_ai.evals import run_all_evals, write_eval_report

OUTPUT_PATH = "reports/eval_report.md"


def main() -> None:
    results = run_all_evals()
    write_eval_report(results, OUTPUT_PATH)
    summary = results["summary"]
    print(f"Eval complete: {summary['passed']}/{summary['total']} passed "
          f"(score {summary['mean_score']:.3f})")
    print(f"Report written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
