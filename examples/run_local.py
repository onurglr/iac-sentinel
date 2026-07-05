"""Local smoke run: parse the sample plan and review it live via the LLM seam.

Usage (from repo root, venv active):
    python examples/run_local.py

Requires a .env file with GITHUB_TOKEN (Models: read-only). See .env.example.
"""

from dotenv import load_dotenv

from iac_sentinel.analysis import analyze
from iac_sentinel.plan_parser import parse_plan
from iac_sentinel.rules import apply_rules

# Load GITHUB_TOKEN from .env into the environment before the seam reads it.
load_dotenv()

changes = parse_plan("tests/fixtures/sample_plan.json")
print(f"Reviewable changes: {len(changes)}")
for c in changes:
    print(f"  - {c.address} ({c.action})")

print(f"\nDeterministic rule findings: {len(apply_rules(changes))}")

result = analyze(changes)
print("\n=== Combined review result (rules + LLM) ===")
print(result.model_dump_json(indent=2))
