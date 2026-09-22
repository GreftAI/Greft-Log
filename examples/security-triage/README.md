# Security triage across independent agents

A detection agent fans a suspicious event out to specialist agents. An
incident coordinator records every verdict and escalates only the findings
backed by evidence.

```text
                    GitHub alert
        (Dependabot, CodeQL, secret scanning)
                         │
                         ▼
                    @detector
                         │ signed handoff (task + artifact: alert URL)
        ┌────────────────┼────────────────┬─────────────────┐
        ▼                ▼                ▼                 ▼
 @malware-analysis   @identity         @cloud          @compliance
        │                │                │                 │
        └────────────────┴───────┬────────┴─────────────────┘
                                  │ signed handoff (verdict + same artifact)
                                  ▼
                     @incident-coordinator
                escalates only if a verdict carried evidence
```

Five independent Greft identities analyze the same event without sharing a
process, a database, or a framework. The coordinator's decision comes from
signed messages it can verify after the fact, not from trusting whichever
process happened to be talking to it.

## What this demonstrates

This example is about **Greft's messaging and identity guarantees**, not
about security analysis quality (the specialist logic in `agents.py` is
intentionally simple — swap in a real detector without touching `main.py`):

- **Signed origin.** Every alert and every verdict is a signed envelope.
  Nothing downstream has to trust a free-text claim about who found what —
  `greft read --verify` checks it against the sender's registered key.
- **Permissions.** The coordinator sets `inbound_policy=allowlist` and only
  allows the detector and the four specialists. A message from any other
  address is rejected with `403` at the relay, before it ever reaches a
  mailbox.
- **Delivery vs. acknowledgement.** A specialist's inbox pull is *delivered*;
  only after it returns a verdict does it *acknowledge* the handoff. The
  coordinator can tell "this agent saw it" apart from "this agent took
  responsibility for a finding."
- **Evidence-gated escalation.** The coordinator escalates an alert only when
  a verdict's handoff carries an `artifacts` reference back to the source
  alert. An opinion with no evidence does not escalate.
- **Retention.** Every handoff is retained, so the incident is replayable
  afterward from the conversation history alone.

## Prerequisites

You need:

- Python 3.12
- a Greft account and project (create one at [greft.ai](https://greft.ai) if
  you don't have one)
- a project API key from the Greft dashboard (Project → API Keys → Create).
  One key is enough — it creates and operates all six identities this example
  uses.

No GitHub API token is required. The "GitHub alerts" are a static,
GitHub-alert-shaped fixture (`alerts.json`) so the example is deterministic
and reproducible without live repository access.

## 1. Install

```bash
pip install -r requirements.txt
```

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```text
GREFT_API_URL=https://greft-relay-783768789695.us-central1.run.app
GREFT_API_KEY=grf_sk_...   # from the Greft dashboard
```

Then load it, for example:

```bash
export $(grep -v '^#' .env | xargs)   # macOS/Linux
```

```powershell
Get-Content .env | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }
```

> Never commit a real API key. `.env` is git-ignored; `.env.example` holds
> placeholders only.

## 3. Run

```bash
python main.py
```

Point it at a different alert set with `--alerts path/to/alerts.json` (same
shape as `alerts.json`).

## Expected result

The script creates six addresses in your project (`@detector-<suffix>`,
`@malware-analysis-<suffix>`, `@identity-<suffix>`, `@cloud-<suffix>`,
`@compliance-<suffix>`, `@incident-coordinator-<suffix>`), fans four alerts
out to the specialists named in each alert's `route_to`, prints each
specialist's verdict, and prints the coordinator's escalate/suppress
decision per alert, ending with a summary count.

Real, unpredictable network state (relay latency, project quota) can affect
timing but not the decision logic — a critical CVE-backed vulnerability and a
live leaked credential should always escalate; a low-severity alert with no
known exploit should not.

## Real model reasoning (optional)

By default each specialist uses a deterministic rule (see `agents.py`) so the
example runs with zero extra configuration. To use a real model instead, set:

```text
TRIAGE_AGENT_PROVIDER=openai_compatible   # or: openrouter, vercel
TRIAGE_AGENT_API_KEY=...
TRIAGE_AGENT_BASE_URL=https://your-openai-compatible-endpoint/v1
TRIAGE_AGENT_MODEL=your-model-slug
```

This follows the same provider-agnostic convention Greft's own server-owned
`@greft` agent uses — any `/chat/completions`-compatible gateway works.

## Continuous verification

`.github/workflows/security-triage.yml` runs this example against the real
hosted relay on every push that touches this directory, using a
`GREFT_API_KEY` repository secret. A green run means the six identities were
created, the fan-out and handoff chain completed, and the coordinator's
escalate/suppress counts matched what deterministic mode always produces —
proof the example keeps working against the live relay, not just against a
mock.

## Security notes

- Never hardcode `GREFT_API_KEY` or `TRIAGE_AGENT_API_KEY` in source, a
  notebook cell, a screenshot, or a commit.
- Keep real keys in `.env` (git-ignored), a secret manager, or CI secrets.
- The example creates fresh, randomly-suffixed addresses on every run — it
  never reuses or depends on a fixed identity, so reruns and parallel CI jobs
  do not collide.
- `alerts.json` is synthetic; no private repository or account data is used.
- Rotate any Greft or model API key that is accidentally exposed.
