"""Provider-agnostic LLM seam.

This module is the ONLY place that knows which LLM provider we talk to. The rest
of the app calls `complete_structured(...)` and gets back a validated Pydantic
object — it never imports a provider SDK. Swapping providers = editing this file
only (that is the whole point of the seam / avoiding vendor lock-in).

Default provider: GitHub Models (OpenAI-compatible endpoint). It speaks the
OpenAI dialect, so we use the openai SDK pointed at GitHub's base_url. Switching
to native Anthropic, Azure, etc. later means adding another branch here.
"""

from __future__ import annotations

import os
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# GitHub Models: OpenAI-compatible inference endpoint.
GITHUB_MODELS_BASE_URL = "https://models.github.ai/inference"
DEFAULT_MODEL = "openai/gpt-4o-mini"  # cheap, supports structured outputs; configurable


def _github_models_client() -> OpenAI:
    """OpenAI client pointed at GitHub Models. Auth: a GitHub token with models:read."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN is not set. Need a GitHub token with 'models: read' permission."
        )
    return OpenAI(base_url=GITHUB_MODELS_BASE_URL, api_key=token)


def complete_structured(
    system: str,
    user: str,
    output_format: type[T],
    *,
    model: str = DEFAULT_MODEL,
    provider: str = "github",
) -> T:
    """Run one structured LLM call and return a validated instance of output_format.

    The provider decides HOW structured output is enforced; the caller only cares
    that it gets back a valid `output_format` object.
    """
    if provider == "github":
        client = _github_models_client()
        # OpenAI SDK's structured-output helper: validates against the Pydantic
        # schema and returns the parsed object (mirrors Anthropic's messages.parse).
        completion = client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=output_format,
        )
        return completion.choices[0].message.parsed

    raise ValueError(f"Unknown provider: {provider!r}")
