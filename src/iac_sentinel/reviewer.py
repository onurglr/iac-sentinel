"""Ask an LLM to review the parsed resource changes and return structured findings.

This module owns the review *logic* (what to ask, the result shape). It does NOT
know which provider answers — that lives behind the `llm.complete_structured`
seam, so we can switch providers without touching this file.
"""

from __future__ import annotations

import json

from .llm import complete_structured
from .models import Finding, LLMReview
from .plan_parser import ResourceChange

# System prompt = the reviewer's fixed identity and rules (same on every call).
# Kept deliberately strict: report only concrete risks, no speculation — this is
# how we bias the tool toward fewer false positives.
SYSTEM_PROMPT = """You are a senior cloud security and cost reviewer for Terraform changes.
You are given a list of resource changes from a `terraform plan` (already parsed).
Report only concrete, defensible risks — do NOT speculate or invent issues.
For each risk, assign a severity and a short, actionable recommendation.
If there are no real risks, return an empty findings list. An empty list is a
valid, meaningful result ("reviewed, clean") — never invent a finding to fill it.
Focus on contextual and combinatorial risks: public exposure, missing encryption,
overly broad IAM, cost blow-ups, and irreversible/destructive changes (deletes)."""


def _build_user_prompt(
    changes: list[ResourceChange], known: list[Finding]
) -> str:
    """User prompt = the per-request data: this PR's changes, plus already-known findings."""
    payload = [
        {"resource": c.address, "type": c.type, "action": c.action, "settings": c.after}
        for c in changes
    ]
    parts = ["Here are the resource changes to review:", json.dumps(payload, indent=2)]

    if known:
        # Deterministic rules already caught these and will be reported separately.
        # Tell the LLM not to repeat them, and to focus on ADDITIONAL risks.
        known_payload = [f.model_dump() for f in known]
        parts += [
            "\nThese issues were ALREADY detected by deterministic rules and will be "
            "reported separately. Do NOT repeat them; find only ADDITIONAL risks:",
            json.dumps(known_payload, indent=2),
        ]
    return "\n".join(parts)


def review_changes(
    changes: list[ResourceChange], known: list[Finding] | None = None
) -> LLMReview:
    """Send the changes to the LLM and return its validated structured output."""
    known = known or []

    # Nothing reviewable -> don't spend a token; return a clean result directly.
    if not changes:
        return LLMReview(findings=[], summary="No reviewable resource changes.")

    return complete_structured(
        system=SYSTEM_PROMPT,
        user=_build_user_prompt(changes, known),
        output_format=LLMReview,
    )
