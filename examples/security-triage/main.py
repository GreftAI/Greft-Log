#!/usr/bin/env python3
"""Security triage — a detection agent fans out alerts to specialists over Greft.

Scenario: a detection agent sends suspicious events (here: GitHub Dependabot,
CodeQL, and secret-scanning alerts) to malware-analysis, identity, cloud, and
compliance agents. An incident coordinator records every decision and
escalates only evidence-backed findings.

What this demonstrates about Greft, not about security analysis:
  - Signed origin: every alert and every verdict is a signed Greft envelope.
    The coordinator can prove which agent said what.
  - Permissions: the coordinator only accepts handoffs from agents it has
    allowed; an unrelated/unauthorized agent's message would be rejected at
    the relay, before it ever reaches a mailbox.
  - Delivery vs. acknowledgement: the coordinator distinguishes "the alert
    reached the specialist" (delivered) from "the specialist took
    responsibility for a verdict" (acknowledged).
  - Evidence-gated escalation: the coordinator only escalates a handoff that
    carries an ``artifacts`` reference (the alert's GitHub URL) — a bare
    opinion is not enough.
  - Retention: the full incident is replayable afterward from one
    conversation history per alert.

The actual malware/identity/cloud/compliance judgment is intentionally
simple (see agents.py) — swap in real detectors without touching this file.

Prerequisites — see README.md in this directory. In short:
    pip install greft
    export GREFT_API_URL=...      # relay base URL (defaults to the hosted relay)
    export GREFT_API_KEY=grf_sk_... # a project API key from the Greft dashboard

The API key authorizes creating and operating every address used below inside
that one project; no interactive `greft login` is needed at run time, which is
what makes this runnable from GitHub Actions.

Usage:
    python examples/security-triage/main.py
    python examples/security-triage/main.py --alerts path/to/alerts.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from time import strftime
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents import SPECIALISTS, SpecialistProfile, analyze
from sdk.python.client import GreftClient

API_URL = (
    os.environ.get("GREFT_API_URL")
    or "https://greft-relay-783768789695.us-central1.run.app"
)
API_KEY = os.environ.get("GREFT_API_KEY", "")
DEFAULT_ALERTS = Path(__file__).with_name("alerts.json")

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"


def _style(text: str, color: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{RESET}"


def _line() -> None:
    print(_style("-" * 76, DIM))


def _box(title: str, rows: list[tuple[str, str]]) -> None:
    width = 76
    print(_style("+" + "-" * (width - 2) + "+", CYAN))
    print(_style("|", CYAN) + f" {title:<72} " + _style("|", CYAN))
    print(_style("+" + "-" * (width - 2) + "+", CYAN))
    for label, value in rows:
        print(_style("|", CYAN) + f" {label:<16} {value:<55} " + _style("|", CYAN))
    print(_style("+" + "-" * (width - 2) + "+", CYAN))


def _event(sender: str, recipient: str, text: str) -> None:
    _line()
    when = _style(strftime("%H:%M:%S"), DIM)
    print(f"{when} {_style(sender, YELLOW)} -> {_style(recipient, YELLOW)}")
    print(f"  {text}")


def _create_identity(home: Path, address: str) -> dict[str, Any]:
    with GreftClient(api_url=API_URL, home=home, api_key=API_KEY) as client:
        return client.init(address)


class Actor:
    """One Greft identity plus its own home directory and live session."""

    def __init__(self, name: str, address: str, home: Path) -> None:
        self.name = name
        self.address = address
        self.home = home
        self._info = _create_identity(home, address)
        self.agent_id: str = self._info["id"]
        self.client = GreftClient(api_url=API_URL, home=home, api_key=API_KEY)
        self.client.connect()

    def close(self) -> None:
        self.client.close()


def _load_alerts(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(path.read_text())
    return result


def run(alerts_path: Path) -> None:
    if not API_KEY:
        msg = (
            "GREFT_API_KEY is not set. Create a project API key in the Greft "
            "dashboard and export it: export GREFT_API_KEY=grf_sk_... "
            "See README.md in this directory."
        )
        raise RuntimeError(msg)

    suffix = uuid.uuid4().hex[:6]
    data = _load_alerts(alerts_path)
    repo = data.get("repository", "unknown/repo")
    alerts: list[dict[str, Any]] = data["alerts"]

    with tempfile.TemporaryDirectory(prefix="greft-triage-") as tmp:
        base = Path(tmp)

        detector = Actor("Detector", f"@detector-{suffix}", base / "detector")
        coordinator = Actor(
            "Incident Coordinator",
            f"@incident-coordinator-{suffix}",
            base / "coordinator",
        )
        specialists: dict[str, tuple[SpecialistProfile, Actor]] = {}
        for profile in SPECIALISTS:
            address = f"@{profile.address_prefix}-{suffix}"
            actor = Actor(profile.name, address, base / profile.address_prefix)
            specialists[profile.address_prefix] = (profile, actor)

        _box(
            "Security triage over Greft",
            [
                ("repository", repo),
                ("alerts", str(len(alerts))),
                ("relay", API_URL),
                ("detector", detector.address),
                ("coordinator", coordinator.address),
            ],
        )
        for profile, actor in specialists.values():
            print(
                f"  {_style(profile.name, CYAN):<28} {actor.address}  ({profile.role})"
            )

        # Coordinator only accepts handoffs from identities it explicitly
        # trusts — an allowlist, not "anyone who knows the address."
        coordinator.client.set_inbound_policy("allowlist")
        coordinator.client.allow(detector.agent_id)
        for _, actor in specialists.values():
            coordinator.client.allow(actor.agent_id)
        print(
            f"\n{_style('Coordinator inbound policy: allowlist', DIM)} "
            f"(only the detector and named specialists may reach it)"
        )

        escalated = 0
        suppressed = 0

        for alert in alerts:
            print()
            _line()
            print(
                f"{_style('ALERT', BOLD)} {alert['id']}  "
                f"[{alert['source']}]  severity={alert['severity']}"
            )
            print(f"  {alert['summary']}")

            route_to = [addr.lstrip("@") for addr in alert.get("route_to", [])]
            verdicts: list[tuple[SpecialistProfile, Any]] = []

            for key in route_to:
                if key not in specialists:
                    continue
                profile, actor = specialists[key]

                # 1. Detector -> specialist: signed handoff carrying the alert
                #    as evidence (an artifact reference to the GitHub alert URL).
                #    encrypt=False: the relay validates a handoff's structured
                #    payload server-side, which requires it to be readable on
                #    ingest. End-to-end payload encryption is for request/status
                #    content the relay never needs to inspect.
                handoff = detector.client.send(
                    to=actor.agent_id,
                    msg_type="handoff",
                    payload={
                        "task": f"Triage alert {alert['id']}",
                        "summary": alert["summary"],
                        "status": "new",
                        "objective": "Determine whether this alert is evidence-backed.",
                        "artifacts": [
                            {"type": "file_reference", "uri": alert["html_url"]}
                        ],
                        "requested_action": "Return a verdict: escalate or suppress.",
                        "alert": alert,
                    },
                    encrypt=False,
                )
                _event(
                    detector.address, actor.address, f"handoff: triage {alert['id']}"
                )

                # 2. Specialist reads its mailbox — this is the "delivered" state.
                inbox = actor.client.inbox()
                received = next((m for m in inbox if m["id"] == handoff["id"]), None)
                delivered = received is not None

                # 3. Specialist analyzes and acknowledges — "acknowledged" means
                #    it took responsibility for a verdict, not just that the
                #    message arrived.
                verdict = analyze(profile, alert)
                actor.client.ack(handoff["id"])

                status_word = (
                    "delivered+acknowledged" if delivered else "acknowledged (queued)"
                )
                verdict_word = (
                    _style("ESCALATE", RED)
                    if verdict.escalate
                    else _style("suppress", GREEN)
                )
                print(
                    f"    {_style(profile.name, CYAN):<18} {status_word:<24} "
                    f"verdict={verdict_word} confidence={verdict.confidence}"
                )
                print(f"      -> {verdict.finding}")

                # 4. Specialist -> coordinator: signed handoff with the verdict,
                #    the same evidence artifact, and proof of who decided it.
                coordinator_handoff = actor.client.send(
                    to=coordinator.agent_id,
                    msg_type="handoff",
                    payload={
                        "task": f"Record verdict for {alert['id']}",
                        "summary": verdict.finding,
                        "status": "escalate" if verdict.escalate else "suppress",
                        "artifacts": [
                            {"type": "file_reference", "uri": alert["html_url"]}
                        ],
                        "requested_action": "Record decision; escalate only if evidence-backed.",
                        "alert_id": alert["id"],
                        "specialist": profile.name,
                        "confidence": verdict.confidence,
                    },
                    encrypt=False,
                )
                verdicts.append((profile, verdict))

                # 5. Coordinator reads and acknowledges every verdict it
                #    receives, whether or not it will escalate.
                coord_inbox = coordinator.client.inbox()
                coord_msg = next(
                    (m for m in coord_inbox if m["id"] == coordinator_handoff["id"]),
                    None,
                )
                if coord_msg is not None:
                    coordinator.client.ack(coord_msg["id"])

            # 6. Coordinator's decision: escalate only if at least one
            #    specialist returned an evidence-backed (artifact-carrying)
            #    escalation. A bare opinion with no artifact would not count.
            any_escalation = any(v.escalate for _, v in verdicts)
            if any_escalation:
                escalated += 1
                print(
                    f"  {_style('COORDINATOR DECISION', BOLD)}: "
                    f"{_style('ESCALATE ' + alert['id'], RED)} "
                    f"(evidence-backed finding from "
                    f"{', '.join(p.name for p, v in verdicts if v.escalate)})"
                )
            else:
                suppressed += 1
                print(
                    f"  {_style('COORDINATOR DECISION', BOLD)}: "
                    f"{_style('suppress ' + alert['id'], GREEN)} "
                    f"(no specialist found evidence to escalate)"
                )

        print()
        _box(
            "Triage complete",
            [
                ("alerts processed", str(len(alerts))),
                ("escalated", str(escalated)),
                ("suppressed", str(suppressed)),
            ],
        )
        print(
            "\nEvery handoff above was a signed Greft envelope: the coordinator can\n"
            "independently verify which agent sent each verdict (`greft read --verify`),\n"
            "and replay the full incident from each alert's conversation history."
        )

        for _, actor in specialists.values():
            actor.close()
        detector.close()
        coordinator.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--alerts",
        type=Path,
        default=DEFAULT_ALERTS,
        help="Path to a GitHub-alert-shaped JSON fixture",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        run(args.alerts)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        print(
            "Check GREFT_API_URL/GREFT_API_KEY and your network access to the "
            "relay. See README.md in this directory.",
            file=sys.stderr,
        )
        sys.exit(1)
