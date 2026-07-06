"""Render a ReviewResult as a Markdown PR comment.

Design goals: scannable (severity first, visual badges, a one-line header) and
idempotent — every comment carries a hidden marker so the publish step can find
and UPDATE the same comment instead of spamming a new one on each run (upsert).
"""

from __future__ import annotations

from .models import ReviewResult

# Hidden HTML comment: invisible to readers, but lets the publish step locate the
# tool's own previous comment for upsert. Never remove/rename without updating publish.
COMMENT_MARKER = "<!-- iac-sentinel -->"

_SEVERITY_BADGE = {"high": "🔴 HIGH", "medium": "🟠 MEDIUM", "low": "🟡 LOW"}


def _header(result: ReviewResult) -> str:
    """One-line summary so a busy reviewer gets the verdict without reading details."""
    if not result.findings:
        if not result.llm_available:
            # No rule findings AND the LLM never ran -> NOT a clean bill of health.
            # Say so, or a partial review masquerades as "all clear" (silent failure).
            return (
                "## 🛡️ iac-sentinel\n\n⚠️ **Review incomplete — LLM unavailable.** "
                "No deterministic-rule risks found, but the AI review did not run."
            )
        return "## 🛡️ iac-sentinel\n\n✅ **No risks found.** Reviewed and clean."

    counts: dict[str, int] = {}
    for f in result.findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    parts = [f"{counts[s]} {s}" for s in ("high", "medium", "low") if s in counts]
    return f"## 🛡️ iac-sentinel\n\n**{len(result.findings)} finding(s):** " + ", ".join(parts)


def render_markdown(result: ReviewResult) -> str:
    """Turn a ReviewResult into the final PR comment body (marker included)."""
    lines = [COMMENT_MARKER, _header(result)]

    # Surface a degraded run even when rules DID find things: the review is partial.
    if not result.llm_available and result.findings:
        lines.append(
            "\n> ⚠️ **The AI review did not run** (LLM unavailable). Findings below "
            "are from deterministic rules only — treat this as a partial review."
        )

    for f in result.findings:  # already severity-sorted by analyze()
        badge = _SEVERITY_BADGE.get(f.severity, f.severity.upper())
        lines += [
            f"\n### {badge} — `{f.resource}`",
            f"**Issue:** {f.issue}",
            f"**Recommendation:** {f.recommendation}",
        ]

    lines.append("\n---\n<sub>Automated review. Deterministic rules + LLM. Verify before merging.</sub>")
    return "\n".join(lines)
