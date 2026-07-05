"""Parse a Terraform plan JSON into a clean list of meaningful resource changes.

Input: the JSON produced by `terraform show -json plan.tfplan`.
Output: only create/update/delete resources, each reduced to the three fields
that matter for a security/cost review — type, action, and resolved settings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Actions that actually change infrastructure and are worth reviewing.
# "no-op" (nothing changes) and "read" (data source lookup) are noise: they add
# tokens/cost and dilute the signal, so we drop them.
REVIEWABLE_ACTIONS = {"create", "update", "delete"}


@dataclass
class ResourceChange:
    """A single reviewable resource change, reduced to what the LLM needs."""

    address: str          # e.g. "aws_security_group.web" — identity for logs/reports
    type: str             # e.g. "aws_security_group" — context for risk weighting
    action: str           # "create" | "update" | "delete"
    after: dict           # resolved settings after the change (the actual risk lives here)


def parse_plan(plan_path: str | Path) -> list[ResourceChange]:
    """Read a plan JSON file and return only the reviewable resource changes."""
    data = json.loads(Path(plan_path).read_text(encoding="utf-8"))

    changes: list[ResourceChange] = []
    for rc in data.get("resource_changes", []):
        actions = rc.get("change", {}).get("actions", [])

        # Keep the resource if ANY of its actions is reviewable. This also covers
        # "replace" (["delete", "create"]) — we don't want to miss those.
        reviewable = [a for a in actions if a in REVIEWABLE_ACTIONS]
        if not reviewable:
            continue

        changes.append(
            ResourceChange(
                address=rc.get("address", "<unknown>"),
                type=rc.get("type", "<unknown>"),
                action=reviewable[0],
                # `after` is null for a pure delete; normalize to {} so downstream
                # code never has to guard against None.
                after=rc.get("change", {}).get("after") or {},
            )
        )

    return changes
