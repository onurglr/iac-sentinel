"""Shared data contracts, produced by BOTH the deterministic rules and the LLM.

Kept in their own module so neither `rules` nor `reviewer` has to depend on the
other — they only share these models.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["high", "medium", "low"]


class Finding(BaseModel):
    """A single concrete risk. Emitted by a rule OR by the LLM — same shape."""

    resource: str = Field(description="Resource address, e.g. aws_security_group.web")
    severity: Severity
    issue: str = Field(description="What is wrong and why it is risky")
    recommendation: str = Field(description="Concrete fix")


class ReviewResult(BaseModel):
    """The full review outcome. Empty findings == reviewed and clean."""

    findings: list[Finding]
    summary: str = Field(description="One-sentence overall summary")
