"""Command-line entry point: parse a plan, review it, print or post the result.

Wiring: parse_plan -> analyze (rules + LLM) -> render_markdown -> (print | upsert).
This is what CI runs. Config that varies per environment comes from env vars.
"""

from __future__ import annotations

import argparse
import os
import sys

from .analysis import analyze
from .plan_parser import parse_plan
from .publish import upsert_comment
from .report import render_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="iac-sentinel", description="AI Terraform reviewer.")
    parser.add_argument("--plan", default="plan.json", help="Path to plan JSON.")
    parser.add_argument("--comment", action="store_true", help="Post result as a PR comment.")
    parser.add_argument("--fail-on-high", action="store_true", help="Exit 1 if any high finding.")
    args = parser.parse_args(argv)

    # Local convenience: load .env if present. Does NOT override real env vars,
    # so in CI the actual environment (GITHUB_TOKEN etc.) always wins.
    from dotenv import load_dotenv

    load_dotenv()

    changes = parse_plan(args.plan)
    result = analyze(changes)
    body = render_markdown(result)

    if args.comment:
        # In GitHub Actions these are provided automatically / via the workflow.
        owner, name = os.environ["GITHUB_REPOSITORY"].split("/", 1)
        pr = int(os.environ["PR_NUMBER"])
        token = os.environ["GITHUB_TOKEN"]
        url = upsert_comment(owner, name, pr, token, body)
        print(f"Comment posted: {url}")
    else:
        # Write bytes so emoji survive on legacy (Windows cp1252) consoles too.
        sys.stdout.buffer.write((body + "\n").encode("utf-8"))

    # Gating: optionally fail the CI job when a high-severity risk is present.
    has_high = any(f.severity == "high" for f in result.findings)
    return 1 if (args.fail_on_high and has_high) else 0


if __name__ == "__main__":
    raise SystemExit(main())
