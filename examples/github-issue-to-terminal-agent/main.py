#!/usr/bin/env python3
"""GitHub Issue -> LLM summary -> Greft handoff to a terminal agent.

Scenario: a GitHub Issue is opened on a repository. A CI job (see
.github/workflows/issue-to-terminal-agent.yml in the repo root) calls an LLM
to turn the raw issue into a short, actionable summary, then sends it as a
signed Greft handoff to a fixed terminal agent's address. Whoever is running
`greft connect` (or polling `greft inbox`) as that address receives the issue
live and can start working on it immediately — including handing it to a
local coding agent.

What this demonstrates about Greft:
  - A CI job (no long-running server, no webhook receiver you have to host)
    can reach a specific, persistent agent identity by address alone.
  - The message survives whether or not the terminal agent happens to be
    connected at the moment CI runs — it is delivered live if connected,
    or queued in the mailbox and delivered the moment it reconnects.
  - The handoff is a structured, signed, evidence-carrying object (the
    original issue URL as an artifact), not a raw webhook payload someone
    has to trust blindly.

The LLM call is intentionally small: one summarization step. Swap the prompt
or the model for anything more elaborate without touching the Greft side.

Prerequisites — see README.md in this directory. In short:
    pip install -r requirements.txt
    export GREFT_API_URL=...          # optional, defaults to the hosted relay
    export GREFT_API_KEY=grf_sk_...   # a project API key from the Greft dashboard
    export TERMINAL_AGENT_ADDRESS=@triage
    export OPENROUTER_API_KEY=sk-or-...
    export GITHUB_ISSUE_TITLE=...
    export GITHUB_ISSUE_BODY=...
    export GITHUB_ISSUE_URL=...

Usage:
    python main.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

import httpx
from sdk.python.client import GreftClient

GREFT_API_URL = os.environ.get(
    "GREFT_API_URL", "https://greft-relay-783768789695.us-central1.run.app"
)
GREFT_API_KEY = os.environ.get("GREFT_API_KEY", "")
TERMINAL_AGENT_ADDRESS = os.environ.get("TERMINAL_AGENT_ADDRESS", "")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
)
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-5")

SUMMARY_SYSTEM_PROMPT = """\
You turn a raw GitHub Issue into a short, actionable brief for an engineer \
picking up the work. Given the issue title and body, respond with strict \
JSON only, no prose outside the JSON:

{
  "summary": "one or two sentences describing the problem",
  "suspected_area": "short guess at the affected component/file/module, or empty string if unclear",
  "suggested_first_step": "one concrete first action to investigate or fix it"
}
"""


def _summarize_issue(title: str, body: str) -> dict[str, str]:
    """Call an OpenRouter model to turn the issue into a structured brief.

    Falls back to a deterministic pass-through summary if no API key is
    configured, so the script never blocks on an optional dependency.
    """
    if not OPENROUTER_API_KEY:
        return {
            "summary": title or "(no title)",
            "suspected_area": "",
            "suggested_first_step": "Read the full issue body and reproduce the problem.",
        }
    try:
        response = httpx.post(
            f"{OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps({"title": title, "body": body}),
                    },
                ],
                "temperature": 0,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed: dict[str, Any] = json.loads(content)
        return {
            "summary": str(parsed.get("summary", title or "(no title)")),
            "suspected_area": str(parsed.get("suspected_area", "")),
            "suggested_first_step": str(parsed.get("suggested_first_step", "")),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "summary": title or "(no title)",
            "suspected_area": "",
            "suggested_first_step": f"LLM summarization failed ({exc}); read the raw issue body.",
        }


def run(
    *,
    issue_title: str,
    issue_body: str,
    issue_url: str,
    issue_number: str,
    repository: str,
) -> None:
    if not GREFT_API_KEY:
        msg = (
            "GREFT_API_KEY is not set. Create a project API key in the Greft "
            "dashboard and export it. See README.md in this directory."
        )
        raise RuntimeError(msg)
    if not TERMINAL_AGENT_ADDRESS:
        msg = "TERMINAL_AGENT_ADDRESS is not set (e.g. @triage). See README.md."
        raise RuntimeError(msg)

    brief = _summarize_issue(issue_title, issue_body)

    with tempfile.TemporaryDirectory(prefix="greft-issue-bot-") as tmp:
        home = Path(tmp)
        suffix = uuid.uuid4().hex[:6]
        bot_address = f"@issue-bot-{suffix}"

        with GreftClient(
            api_url=GREFT_API_URL, home=home, api_key=GREFT_API_KEY
        ) as client:
            client.init(bot_address)
            client.connect()

            print(
                f"Sending issue #{issue_number} from {repository} to {TERMINAL_AGENT_ADDRESS}"
            )
            print(f"  summary: {brief['summary']}")

            handoff = client.send(
                to=TERMINAL_AGENT_ADDRESS,
                msg_type="handoff",
                payload={
                    "task": f"Triage GitHub issue #{issue_number}: {issue_title}",
                    "summary": brief["summary"],
                    "status": "new",
                    "current_state": f"Issue opened on {repository}.",
                    "artifacts": [{"type": "file_reference", "uri": issue_url}],
                    "requested_action": brief["suggested_first_step"],
                    "suspected_area": brief["suspected_area"],
                    "issue_number": issue_number,
                    "repository": repository,
                },
                # A handoff's structured payload is validated server-side,
                # which requires it to be readable on ingest.
                encrypt=False,
            )
            print(f"Handoff sent: {handoff['id']}  status={handoff['status']}")


if __name__ == "__main__":
    try:
        run(
            issue_title=os.environ.get("GITHUB_ISSUE_TITLE", ""),
            issue_body=os.environ.get("GITHUB_ISSUE_BODY", ""),
            issue_url=os.environ.get("GITHUB_ISSUE_URL", ""),
            issue_number=os.environ.get("GITHUB_ISSUE_NUMBER", ""),
            repository=os.environ.get("GITHUB_REPOSITORY", ""),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
