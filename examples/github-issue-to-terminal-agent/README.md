# GitHub issue to terminal agent

A GitHub Issue is opened. CI summarizes it with an LLM call and sends the
result as a signed Greft handoff to a fixed terminal agent's address.
Whoever is running `greft connect` as that address receives the issue live
and can start working on it — including handing it straight to a local
coding agent.

```text
GitHub Issue opened
        │
        ▼
  GitHub Actions job
        │  1 LLM call (OpenRouter): raw issue -> short structured brief
        ▼
    @issue-bot-xxxxxx  (fresh identity, created per run)
        │  signed handoff (task + artifact: issue URL)
        ▼
      Greft relay
        │
        ▼
    @triage  (your terminal, `greft connect`)
```

## What this demonstrates

- **No webhook receiver to host.** CI reaches a specific, persistent agent
  identity by address alone — no public endpoint, no ngrok, no server you
  have to keep running to receive the message.
- **Delivery survives disconnection.** If `@triage` is connected when CI
  runs, the handoff arrives immediately. If not, it queues in the mailbox
  and delivers the moment `@triage` reconnects.
- **A structured, signed object, not a raw payload.** The recipient gets a
  `handoff` with a `task`, a `summary`, a `requested_action`, and an
  `artifacts` reference back to the real issue URL — not a blob of JSON it
  has to parse and trust blindly.

## Prerequisites

You need:

- Python 3.12
- a Greft project and a project API key (Project → API Keys → Create in the
  [Greft dashboard](https://greft.ai))
- a terminal agent address already created in that same project (this
  example assumes `@triage` — substitute your own)
- an [OpenRouter](https://openrouter.ai) API key (optional — without one,
  the script falls back to a deterministic pass-through summary instead of
  calling an LLM)

## 1. Install

```bash
pip install -r requirements.txt
```

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env` with your real `GREFT_API_KEY`, `TERMINAL_AGENT_ADDRESS`, and
(optionally) `OPENROUTER_API_KEY`. Then load it and run the terminal agent
in another shell so it can receive the message live:

```bash
export GREFT_HOME="$HOME/.greft/triage"
greft login
greft project use "YOUR_PROJECT"
greft api-key use --secret YOUR_GREFT_API_KEY
greft connect   # keep this open
```

## 3. Run

With `.env` loaded in this directory's shell:

```bash
python main.py
```

The terminal running `greft connect` as `@triage` should print the incoming
handoff immediately. If it isn't connected, check later with:

```bash
greft inbox
greft read <handoff_id>
```

## Running from GitHub Actions

`.github/workflows/issue-to-terminal-agent.yml` (repo root) runs this
automatically whenever an issue is opened on this repository, and supports a
manual test run via **Actions → GitHub issue to terminal agent → Run
workflow**.

It needs, configured once in the repo's Settings → Secrets and variables →
Actions:

| Name | Type | Value |
|---|---|---|
| `GREFT_API_KEY` | Secret | Your Greft project API key |
| `GREFT_API_URL` | Secret (optional) | Relay URL, if not using the default hosted relay |
| `OPENROUTER_API_KEY` | Secret (optional) | Enables real LLM summarization instead of the fallback |
| `TERMINAL_AGENT_ADDRESS` | **Variable** (not secret — addresses are public) | e.g. `@triage` |

A green run means: the issue was summarized, a fresh bot identity was
created and authenticated against the live relay, and a signed handoff was
sent and accepted by the relay for `TERMINAL_AGENT_ADDRESS`. It does not by
itself confirm delivery to a human — check the terminal agent's inbox to
see the actual message.

## Security notes

- Never hardcode `GREFT_API_KEY` or `OPENROUTER_API_KEY` in source, a
  screenshot, or a commit. Keep them in `.env` (git-ignored) or CI secrets.
- `TERMINAL_AGENT_ADDRESS` is not a secret — Greft addresses are public by
  design — but it is a live routing target, so only set it to an address you
  control and expect to receive this traffic.
- Every run creates a fresh, randomly-suffixed sender identity
  (`@issue-bot-xxxxxx`); it never reuses or depends on a fixed sender
  address.
- The terminal agent's own adapter (MCP, CLI, or SDK) is responsible for
  what happens next. Greft messages are data, not instructions — a coding
  agent receiving this handoff should treat its contents as a task
  description to evaluate, not a command to execute blindly.
