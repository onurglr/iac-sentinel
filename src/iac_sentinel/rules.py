"""Deterministic safety-net checks — the guaranteed floor of the review.

Each rule is a pure function: (ResourceChange) -> list[Finding]. No I/O, no LLM,
fully reproducible. These catch known, non-negotiable misconfigurations that must
NEVER slip through regardless of what the LLM does (defense in depth).
"""

from __future__ import annotations

from collections.abc import Callable

from .models import Finding
from .plan_parser import ResourceChange

OPEN_CIDR = "0.0.0.0/0"

# Known-expensive instance family prefixes (GPU / large memory). This list is the
# rule's blind spot by design: new expensive types AWS releases later won't be here
# — that long tail is the LLM's job. The rule only guarantees the KNOWN cases.
EXPENSIVE_INSTANCE_PREFIXES = ("p4d", "p5", "p3dn", "x2", "u-", "trn1")
HIGH_COUNT_THRESHOLD = 10


def _open_ingress(change: ResourceChange) -> list[Finding]:
    """Flag any security group ingress rule open to the whole internet."""
    if change.type != "aws_security_group":
        return []

    findings: list[Finding] = []
    for rule in change.after.get("ingress", []):
        if OPEN_CIDR in rule.get("cidr_blocks", []):
            port = rule.get("from_port", "?")
            findings.append(
                Finding(
                    resource=change.address,
                    severity="high",
                    issue=f"Ingress on port {port} is open to the entire internet ({OPEN_CIDR}).",
                    recommendation="Restrict cidr_blocks to specific trusted IP ranges.",
                )
            )
    return findings


def _unencrypted_storage(change: ResourceChange) -> list[Finding]:
    """Flag storage resources created without encryption at rest."""
    encryptable = {"aws_db_instance", "aws_ebs_volume", "aws_rds_cluster"}
    if change.type not in encryptable:
        return []
    if change.after.get("storage_encrypted") is False:
        return [
            Finding(
                resource=change.address,
                severity="high",
                issue="Storage is created without encryption at rest (storage_encrypted = false).",
                recommendation="Set storage_encrypted = true.",
            )
        ]
    return []


def _expensive_compute(change: ResourceChange) -> list[Finding]:
    """Flag EC2 instances that are obviously expensive: costly type or high count."""
    if change.type != "aws_instance":
        return []

    instance_type = change.after.get("instance_type", "")
    count = change.after.get("count", 1)
    reasons = []
    if instance_type.startswith(EXPENSIVE_INSTANCE_PREFIXES):
        reasons.append(f"expensive instance type '{instance_type}'")
    if isinstance(count, int) and count >= HIGH_COUNT_THRESHOLD:
        reasons.append(f"high instance count ({count})")

    if not reasons:
        return []
    return [
        Finding(
            resource=change.address,
            severity="high",
            issue="Potential cost blow-up: " + " and ".join(reasons) + ".",
            recommendation="Confirm this scale is intended; consider smaller types or lower count.",
        )
    ]


# Registry of active rules. Adding a new check = add a function here.
RULES: list[Callable[[ResourceChange], list[Finding]]] = [
    _open_ingress,
    _unencrypted_storage,
    _expensive_compute,
]


def apply_rules(changes: list[ResourceChange]) -> list[Finding]:
    """Run every rule against every change; return all deterministic findings."""
    findings: list[Finding] = []
    for change in changes:
        for rule in RULES:
            findings.extend(rule(change))
    return findings
