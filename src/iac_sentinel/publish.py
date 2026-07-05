"""Post the review as a PR comment via the GitHub REST API (upsert).

Uses only the stdlib (urllib) — no extra HTTP dependency, smaller attack surface.
Upsert: if a previous comment carrying COMMENT_MARKER exists, PATCH it; otherwise
POST a new one. This keeps exactly one, always-current comment per PR.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .report import COMMENT_MARKER

API_ROOT = "https://api.github.com"


def _request(method: str, url: str, token: str, body: dict | None = None) -> object:
    """One authenticated GitHub API call. Returns the parsed JSON response."""
    data = None
    if body is not None:
        # Explicit UTF-8: never rely on the platform default (the Windows lesson).
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "iac-sentinel")  # GitHub rejects requests without one
    if data is not None:
        req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _find_existing_comment(owner: str, repo: str, pr: int, token: str) -> int | None:
    """Return the id of our previous comment (by marker), or None if none exists."""
    # per_page=100 covers most PRs; very long threads would need pagination (known limit).
    url = f"{API_ROOT}/repos/{owner}/{repo}/issues/{pr}/comments?per_page=100"
    comments = _request("GET", url, token)
    for comment in comments:
        if COMMENT_MARKER in comment.get("body", ""):
            return comment["id"]
    return None


def upsert_comment(owner: str, repo: str, pr: int, token: str, body: str) -> str:
    """Create or update the tool's PR comment. Returns the comment's html_url."""
    existing_id = _find_existing_comment(owner, repo, pr, token)

    if existing_id is not None:
        url = f"{API_ROOT}/repos/{owner}/{repo}/issues/comments/{existing_id}"
        result = _request("PATCH", url, token, {"body": body})
    else:
        url = f"{API_ROOT}/repos/{owner}/{repo}/issues/{pr}/comments"
        result = _request("POST", url, token, {"body": body})

    return result["html_url"]
