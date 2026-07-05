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

    # LLM runs independently but is told what the rules already caught.
    llm_result = review_changes(changes, known=rule_findings)

    all_findings: list[Finding] = rule_findings + llm_result.findings
    all_findings.sort(key=lambda f: _SEVERITY_ORDER.get(f.severity, 99))

    summary = (
        f"{len(all_findings)} finding(s): "
        f"{len(rule_findings)} from rules, {len(llm_result.findings)} from LLM."
        if all_findings
        else "Reviewed, no risks found."
    )
    return ReviewResult(findings=all_findings, summary=summary)
