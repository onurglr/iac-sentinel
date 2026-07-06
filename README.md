# 🛡️ iac-sentinel

**AI-assisted Terraform reviewer for pull requests.** It reads a `terraform plan`,
combines deterministic security/cost rules with an LLM, and posts a single,
always-up-to-date review comment on the PR.

> Built as a hands-on study of the DevOps × Agentic-AI intersection: IaC, CI/CD,
> structured LLM output, provider independence, and defense-in-depth.

---

## Why it exists

A `terraform plan` shows exactly what will change in your infrastructure — but on a
busy PR, risky changes (a security group open to `0.0.0.0/0`, an unencrypted
database, a 50× GPU cost blow-up) are easy to miss. iac-sentinel reviews the plan
automatically on every PR and surfaces the risks where the team already works.

## How it works

```
terraform plan (JSON)
        │
        ▼
   [ parse ]        keep create/update/delete; drop no-op/read noise
        │
        ├─────────────► [ rules ]  deterministic safety net (guaranteed floor)
        │                   │       0.0.0.0/0, unencrypted storage, cost blow-ups
        ├─────────────► [ LLM ]    contextual/novel risks (flexible ceiling)
        │                   │       via a provider-agnostic seam
        ▼                   ▼
      [ merge ] ── severity-sorted, de-duplicated ReviewResult
        │
        ▼
   [ report ]       scannable Markdown (badges, summary, hidden marker)
        │
        ▼
   [ publish ]      upsert one PR comment via the GitHub REST API
```

### Design highlights

- **Defense in depth.** Deterministic rules are the *floor*: obvious risks
  (`0.0.0.0/0`, missing encryption at rest, expensive/high-count compute) are
  caught **every time**, independent of the LLM. The LLM is the *ceiling*: it
  reasons about novel and contextual risks the rules can't enumerate. Neither
  layer alone is trusted.
- **Graceful degradation (fail-safe).** The LLM call is isolated in the
  orchestrator: if the model is down, rate-limited, or unauthenticated, the
  review **does not crash** — it falls back to the deterministic rules and posts
  a **visible** "AI review did not run — partial review" warning instead of
  silently masquerading as a clean bill of health. The failure reason is never
  echoed into the public comment (it could leak tokens/URLs).
- **Provider-agnostic.** All model access lives behind one seam (`llm.py`).
  The default provider is **GitHub Models** (OpenAI-compatible); switching
  providers touches only that file — no vendor lock-in.
- **Structured output.** The LLM is forced into a validated Pydantic schema, so
  results are machine-readable (severity as a closed set, not prose) — no fragile
  JSON string parsing.
- **Idempotent comments.** A hidden marker lets the tool update its own previous
  comment instead of spamming a new one on every push.
- **CI-native.** Ships as a GitHub Actions workflow with least-privilege
  permissions; optional `--fail-on-high` gates merges.

## Usage

```bash
pip install -e .

# Generate a plan
terraform plan -out=plan.tfplan
terraform show -json plan.tfplan > plan.json

# Review it (prints Markdown)
iac-sentinel --plan plan.json

# Review and post/update a PR comment (CI)
iac-sentinel --plan plan.json --comment
```

Set `GITHUB_TOKEN` (a token with `models: read`, plus `pull-requests: write` when
using `--comment`). Locally, put it in a `.env` file — see `.env.example`.

## In CI

`.github/workflows/iac-sentinel.yml` runs on every pull request and comments
automatically. The job token needs:

```yaml
permissions:
  contents: read
  pull-requests: write
  models: read
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

The deterministic layer (parser + rules) is fully unit-tested — fast, no API,
no network. The LLM boundary is deliberately kept out of unit tests.

## Roadmap

- Generate the plan from real `terraform plan` in CI (currently a sample plan).
- Make the LLM **agentic**: tool-use to query live cloud state / CVEs, multi-step
  investigation before judging.
- Observability (Langfuse): token cost & tracing per review.
- More rules (public S3, wildcard IAM, unencrypted volumes).

## Architecture decisions

See [`DECISIONS.md`](./DECISIONS.md) for the reasoned ADRs (input format, structured
output, the provider seam, the hybrid rules+LLM design, graceful degradation, and more).
""