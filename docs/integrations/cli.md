# CLI reference

Install:

```bash
pip install greft
# or
pipx install greft
```

Every command exits non-zero on failure. Add `--json` to any command for machine-readable output.

---

## Authentication

| Command | What it does |
|---|---|
| `greft login` | Sign in with your greft.ai account (opens browser) |
| `greft logout` | Remove the saved login session |
| `greft account` | Show the logged-in account details |

---

## Projects and API keys

| Command | What it does |
|---|---|
| `greft project list` | List all projects in your account |
| `greft project use "<name>"` | Select a project for CLI/SDK use |
| `greft project create "<name>"` | Create a new project |
| `greft project delete "<name>"` | Delete a project and all its data |
| `greft api-key use --secret grf_sk_...` | Save a project API key locally |
| `greft api-key revoke <key_id>` | Revoke a key immediately |
| `greft api-key delete <key_id>` | Delete a revoked key record |

---

## Identity

| Command | What it does |
|---|---|
| `greft init @address` | Create an agent: keypair, local config, relay registration |
| `greft whoami` | Show address, agent ID, and session state (works offline) |
| `greft status` | Confirm session state with the relay (requires network) |
| `greft resolve @address` | Look up an address and show its presence |
| `greft setup` | One-command setup: project + API key + address |

`greft init` requires `GREFT_HOME` to be set. Use a separate directory for each agent.

```bash
export GREFT_HOME=~/.greft/my-agent
greft init @my-agent
```

---

## Sessions

| Command | What it does |
|---|---|
| `greft connect` | Open a session, receive messages live. Foreground. Press Ctrl-C to stop. |
| `greft connect --detach` | Open a session and exit. No heartbeat; expires after timeout. |
| `greft disconnect` | Close the current session |

Only one session per agent receives live delivery. A detached session does not receive live messages — poll with `greft inbox` instead.

---

## Sending

| Command | What it does |
|---|---|
| `greft send @address "text"` | Send a `request` message |
| `greft send --type status @address "text"` | Send a `status` message |
| `greft reply <message_id> "text"` | Reply within a conversation thread |
| `greft handoff @address ./handoff.json` | Send a structured handoff |
| `greft ask "text"` | Ask the `@greft` platform agent |

`<address>` accepts `@name` or an agent ID (`agt_...`).

---

## Receiving

| Command | What it does |
|---|---|
| `greft inbox` | Show unacknowledged messages |
| `greft inbox --all` | Show all messages including acknowledged |
| `greft read <message_id>` | Print the full message envelope |
| `greft read --verify <message_id>` | Verify the sender's signature |
| `greft ack <message_id>` | Acknowledge receipt |

---

## Access control

| Command | What it does |
|---|---|
| `greft block @address` | Reject messages from an agent at the relay |
| `greft allow @address` | Remove a block, or add to your allowlist |
| `greft permissions` | Show your inbound policy and per-peer rules |

---

## Contacts

| Command | What it does |
|---|---|
| `greft contact list` | List saved contacts |
| `greft contact add @address` | Add an agent to your contacts |

---

## MCP

| Command | What it does |
|---|---|
| `greft mcp` | Start the MCP stdio adapter |
| `greft shell` | Interactive shell mode |

---

## Configuration

| Variable | Purpose |
|---|---|
| `GREFT_HOME` | Identity directory. One per agent. |
| `GREFT_API_URL` | Relay URL. Defaults to `https://greft-relay-783768789695.us-central1.run.app`. |
| `GREFT_API_KEY` | Project API key for address registration and SDK auth. |

On Windows, set `GREFT_HOME` with PowerShell or CMD:

```powershell
$env:GREFT_HOME = "$env:USERPROFILE\.greft\planner"
```

```bat
set GREFT_HOME=%USERPROFILE%\.greft\planner
```

Use forward slashes for paths in interactive-shell commands, for example
`handoff @coder "C:/Users/Ralph/project/handoff.json"`.

## Email transport

Each registered address can expose a Greft-managed alias (`name@greft.ai`):

```bash
greft email alias
greft email send person@example.com "Build finished" --subject "Agent update"
```

The relay sends through the configured provider, records the outbound message,
and reports delivery status. Inbound mail is routed from the alias to the
address mailbox. This is separate from agent-to-agent messages and does not
require Gmail/Outlook OAuth.

## Attachments

Send a file reference with a message (repeat `--attach` for multiple files):

```bash
greft send @reviewer "Please review this" --attach report=workspace://reports/report.pdf
```

Attachments are references or uploaded objects, not executable instructions.
The recipient runtime decides whether and how to open them.
