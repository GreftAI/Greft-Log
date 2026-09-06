# Contributing to Greft documentation

Thank you for helping improve the Greft docs.

## What belongs here

This repository is the public-facing documentation for users of [greft.ai](https://greft.ai). It covers:

- Getting started with the hosted service
- CLI commands and configuration
- SDK usage (Python, JavaScript)
- MCP integration
- Concepts, use cases, and security
- Examples

If you are reporting a bug in the Greft relay or SDK, open an issue in the main repository instead.

## How to contribute

1. Fork this repository.
2. Create a branch: `git checkout -b docs/your-topic`.
3. Make your changes.
4. Open a pull request with a clear description of what you changed and why.

## Style guide

- Write for developers integrating Greft into their agents — not for relay operators.
- Use concrete commands and code examples. Prefer showing over explaining.
- Keep sentences short. One idea per sentence.
- Do not include internal relay configuration (`GREFT_JWT_PRIVATE_KEY`, `GREFT_DATABASE_URL`, etc.) — those belong in the private repository.

## Reporting a security issue

See [SECURITY.md](SECURITY.md).
