# Security

## Reporting a vulnerability

Please do not report security vulnerabilities through public GitHub issues.

Email **security@greft.ai** with:

- A description of the vulnerability
- Steps to reproduce
- The potential impact
- Any suggested mitigations

You will receive a response within 48 hours. We will work with you to understand and fix the issue before any public disclosure.

## Scope

In scope:

- The Greft relay API (`greft-relay-*.run.app`)
- The greft.ai dashboard and authentication
- The `greft` CLI and Python SDK
- The MCP adapter

Out of scope:

- Denial of service attacks
- Social engineering
- Physical attacks
- Issues already known or already reported

## Security model

See [docs/security.md](docs/security.md) for a full description of how Greft handles keys, signatures, and access control.
