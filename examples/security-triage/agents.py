"""Agent identities and triage logic for the security-triage example.

Five specialist identities plus one coordinator. Each specialist inspects one
GitHub-alert-shaped event and returns a verdict: is this evidence-backed
enough to escalate, or is it noise?

Model calls use the same OpenAI-compatible provider convention as the
server-owned ``@greft`` agent (``server/greft_agent.py``): set
``TRIAGE_AGENT_PROVIDER=openai_compatible`` (or ``openrouter`` / ``vercel``)
plus ``TRIAGE_AGENT_API_KEY``/``TRIAGE_AGENT_BASE_URL``/``TRIAGE_AGENT_MODEL``
to get real reasoning. With no key configured, each agent falls back to a
deterministic, rule-based verdict so the whole example runs with zero setup.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

TRIAGE_AGENT_PROVIDER = os.environ.get("TRIAGE_AGENT_PROVIDER", "scripted")
TRIAGE_AGENT_API_KEY = os.environ.get("TRIAGE_AGENT_API_KEY", "")
TRIAGE_AGENT_BASE_URL = os.environ.get(
    "TRIAGE_AGENT_BASE_URL", "https://ai-gateway.vercel.sh/v1"
)
TRIAGE_AGENT_MODEL = os.environ.get("TRIAGE_AGENT_MODEL", "anthropic/claude-sonnet-5")
TRIAGE_AGENT_TIMEOUT = float(os.environ.get("TRIAGE_AGENT_TIMEOUT", "20"))


@dataclass(frozen=True)
class Verdict:
    """One specialist's evidence-backed (or not) finding for one alert."""

    agent_name: str
    escalate: bool
    finding: str
    confidence: str  # "low" | "medium" | "high"


@dataclass(frozen=True)
class SpecialistProfile:
    """Identity and analysis focus for one triage specialist."""

    name: str
    address_prefix: str
    role: str
    system_prompt: str


SPECIALISTS: tuple[SpecialistProfile, ...] = (
    SpecialistProfile(
        name="Malware Analysis",
        address_prefix="malware-analysis",
        role="Assess whether an alert indicates exploitable, malicious-capable code.",
        system_prompt=(
            "You are a malware-analysis triage agent. Given one security alert as JSON, "
            "decide whether it describes a real exploit path (not just an outdated "
            "version) and whether it should be escalated. Respond with strict JSON: "
            '{"escalate": bool, "finding": "one sentence", "confidence": "low|medium|high"}.'
        ),
    ),
    SpecialistProfile(
        name="Identity",
        address_prefix="identity",
        role="Assess whether an alert exposes credentials or identity material.",
        system_prompt=(
            "You are an identity-security triage agent. Given one security alert as JSON, "
            "decide whether it exposes credentials, keys, or tokens that could grant "
            "someone another identity's access, and whether it should be escalated. "
            "Respond with strict JSON: "
            '{"escalate": bool, "finding": "one sentence", "confidence": "low|medium|high"}.'
        ),
    ),
    SpecialistProfile(
        name="Cloud",
        address_prefix="cloud",
        role="Assess whether an alert affects cloud infrastructure or its configuration.",
        system_prompt=(
            "You are a cloud-security triage agent. Given one security alert as JSON, "
            "decide whether it affects cloud infrastructure, IAM, or deployment "
            "configuration, and whether it should be escalated. Respond with strict JSON: "
            '{"escalate": bool, "finding": "one sentence", "confidence": "low|medium|high"}.'
        ),
    ),
    SpecialistProfile(
        name="Compliance",
        address_prefix="compliance",
        role="Assess whether an alert creates a regulatory or policy reporting obligation.",
        system_prompt=(
            "You are a compliance triage agent. Given one security alert as JSON, decide "
            "whether it creates a disclosure, audit, or policy obligation, and whether it "
            "should be escalated. Respond with strict JSON: "
            '{"escalate": bool, "finding": "one sentence", "confidence": "low|medium|high"}.'
        ),
    ),
)


def _scripted_verdict(profile: SpecialistProfile, alert: dict[str, Any]) -> Verdict:
    """Deterministic fallback verdict used when no model provider is configured."""
    severity = str(alert.get("severity", "")).lower()
    source = str(alert.get("source", ""))
    summary = str(alert.get("summary", ""))
    high_severity = severity in ("critical", "high")

    if profile.address_prefix == "malware-analysis":
        escalate = high_severity and source == "dependabot" and bool(alert.get("cve"))
        finding = (
            f"CVE-backed vulnerability at {severity} severity: {summary}"
            if escalate
            else f"No confirmed exploit path in this {source} alert."
        )
    elif profile.address_prefix == "identity":
        escalate = source == "secret_scanning" or "credential" in summary.lower()
        finding = (
            f"Live credential exposure detected: {summary}"
            if escalate
            else "No credential or identity material exposed."
        )
    elif profile.address_prefix == "cloud":
        escalate = "terraform" in summary.lower() or "aws" in summary.lower()
        finding = (
            f"Cloud infrastructure or IAM material affected: {summary}"
            if escalate
            else "No cloud infrastructure impact identified."
        )
    else:  # compliance
        escalate = high_severity
        finding = (
            f"Disclosure-relevant finding at {severity} severity: {summary}"
            if escalate
            else "Below the threshold for a compliance obligation."
        )

    confidence = (
        "high" if escalate and alert.get("cve") else "medium" if escalate else "low"
    )
    return Verdict(
        agent_name=profile.name,
        escalate=escalate,
        finding=finding,
        confidence=confidence,
    )


def _model_verdict(profile: SpecialistProfile, alert: dict[str, Any]) -> Verdict | None:
    """Call the configured OpenAI-compatible provider; return None on any failure."""
    if not TRIAGE_AGENT_API_KEY:
        return None
    try:
        response = httpx.post(
            f"{TRIAGE_AGENT_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {TRIAGE_AGENT_API_KEY}"},
            json={
                "model": TRIAGE_AGENT_MODEL,
                "messages": [
                    {"role": "system", "content": profile.system_prompt},
                    {"role": "user", "content": json.dumps(alert)},
                ],
                "temperature": 0,
            },
            timeout=TRIAGE_AGENT_TIMEOUT,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return Verdict(
            agent_name=profile.name,
            escalate=bool(parsed["escalate"]),
            finding=str(parsed["finding"]),
            confidence=str(parsed.get("confidence", "medium")),
        )
    except Exception:
        return None


def analyze(profile: SpecialistProfile, alert: dict[str, Any]) -> Verdict:
    """Return a specialist's verdict, using a real model when configured."""
    if TRIAGE_AGENT_PROVIDER != "scripted":
        verdict = _model_verdict(profile, alert)
        if verdict is not None:
            return verdict
    return _scripted_verdict(profile, alert)
