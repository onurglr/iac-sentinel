"""Orchestrate the hybrid review: deterministic rules + LLM, then combine.

Order matters: rules run FIRST and independently (the guaranteed floor). Their
findings are passed to the LLM only as context ("already found, don't repeat"),
so the LLM adds contextual risks on top without duplicating the obvious ones.
"""

from __future__ import annotations

from .models import Finding, ReviewResult
from .plan_parser import ResourceChange
from .reviewer import review_changes
from .rules import apply_rules

# Rule findings first (deterministic, high-confidence), then LLM findings.
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def analyze(changes: list[ResourceChange]) -> ReviewResult:
    """Run rules + LLM and merge into a single, severity-sorted ReviewResult."""
    rule_findings = apply_rules(changes)

    # Defense in depth: the deterministic floor (rules) must survive any failure of
    # the LLM ceiling. Isolate the LLM boundary so a network/auth/rate-limit/schema
    # error degrades to rules-only instead of sinking the whole review.
    llm_available = True
    llm_findings: list[Finding] = []
    try:
        llm_findings = review_changes(changes, known=rule_findings).findings
    except Exception:
        # Deliberately broad: the LLM can fail many ways and none should crash CI.
        # We record only THAT it failed (a boolean), never the exception text, which
        # could leak secrets (tokens/URLs) into a public PR comment.
        llm_available = False

    all_findings = rule_findings + llm_findings
    all_findings.sort(key=lambda f: _SEVERITY_ORDER.get(f.severity, 99))

    if not llm_available:
        summary = (
            f"LLM review unavailable; showing deterministic rule findings only "
            f"({len(rule_findings)})."
        )
    elif all_findings:
        summary = (
            f"{len(all_findings)} finding(s): "
            f"{len(rule_findings)} from rules, {len(llm_findings)} from LLM."
        )
    else:
        summary = "Reviewed, no risks found."

    return ReviewResult(
        findings=all_findings, summary=summary, llm_available=llm_available
    )
