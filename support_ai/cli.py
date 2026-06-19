from __future__ import annotations

import argparse
import json
import sys

from support_ai.account_brief import (
    AccountDataUnavailable,
    AccountNotFound,
    generate_account_brief,
)
from support_ai.config import load_settings
from support_ai.data_loader import dataset_health
from support_ai.deterministic import stable_json
from support_ai.triage import triage_ticket


def cmd_data_check(args: argparse.Namespace) -> int:
    settings = load_settings()
    health = dataset_health(settings.data_dir)
    print(stable_json(health.model_dump()))
    return 0


def cmd_triage(args: argparse.Namespace) -> int:
    settings = load_settings()
    if args.text:
        ticket: object = {"text": args.text, "subject": args.text[:200], "body": args.text}
    else:
        ticket = {"subject": args.subject or "", "body": args.body or ""}
    result = triage_ticket(ticket, kb_dir=settings.kb_dir, settings=settings)
    print(stable_json(result.model_dump()))
    return 0


def cmd_account_brief(args: argparse.Namespace) -> int:
    settings = load_settings()
    try:
        brief = generate_account_brief(args.account_id, data_dir=settings.data_dir, settings=settings)
        print(stable_json(brief.model_dump()))
        return 0
    except AccountDataUnavailable as exc:
        print(json.dumps({"error": "data_unavailable", "detail": str(exc)}), file=sys.stderr)
        return 2
    except AccountNotFound as exc:
        print(json.dumps({"error": "account_not_found", "detail": str(exc)}), file=sys.stderr)
        return 1


def cmd_eval(args: argparse.Namespace) -> int:
    import os

    from support_ai.evals import run_all_evals, write_eval_report

    settings = load_settings()
    results = run_all_evals(data_dir=settings.data_dir, kb_dir=settings.kb_dir)

    output_path: str = args.output
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    if output_path.endswith(".json"):
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, ensure_ascii=False)
    else:
        write_eval_report(results, output_path)

    print(f"Eval report written to {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m support_ai.cli",
        description="Zycus Support AI CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("data-check", help="Check data health")

    triage_p = sub.add_parser("triage", help="Triage a support ticket")
    triage_p.add_argument("--subject", default="")
    triage_p.add_argument("--body", default="")
    triage_p.add_argument("--text", default="")

    brief_p = sub.add_parser("account-brief", help="Generate TAM account brief")
    brief_p.add_argument("--account-id", required=True, dest="account_id")

    eval_p = sub.add_parser("eval", help="Run evaluation harness")
    eval_p.add_argument("--output", default="reports/eval_report.md")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {
        "data-check": cmd_data_check,
        "triage": cmd_triage,
        "account-brief": cmd_account_brief,
        "eval": cmd_eval,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)
    sys.exit(handler(args))


if __name__ == "__main__":
    main()
