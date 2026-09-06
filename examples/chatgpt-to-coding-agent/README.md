# Example: ChatGPT to coding agent

This example shows a ChatGPT-based agent sending a handoff to a coding agent running on a different machine.

## What it demonstrates

- Registering two agents with separate identities
- Sending a structured handoff between them
- The coding agent receiving the handoff after its session reconnects (offline delivery)

## Setup

**Agent 1 — the planner** (runs on your machine):

```bash
export GREFT_HOME=~/.greft/planner
greft login
greft project use "My Project"
greft api-key use --secret grf_sk_...
greft init @planner
greft connect
```

**Agent 2 — the coder** (runs on any machine with the identity):

```bash
export GREFT_HOME=~/.greft/coder
greft init @coder
greft connect
```

## Send a handoff

From the planner's terminal:

```bash
cat > handoff.json <<'EOF'
{
  "task": "Implement the retry logic for the HTTP client",
  "summary": "The base client is complete. Retry on 429 and 503 with exponential backoff.",
  "status": "blocked",
  "objective": "Add retry logic and confirm all existing tests still pass.",
  "current_state": "Base client passes 12 of 12 tests. Retry logic not yet implemented.",
  "blockers": ["Retry logic not implemented"],
  "artifacts": [
    {"type": "file_reference", "uri": "workspace://src/http_client.py"},
    {"type": "file_reference", "uri": "workspace://tests/test_http_client.py"}
  ],
  "requested_action": "Implement retries and return a status update."
}
EOF

greft handoff @coder ./handoff.json
```

## What happens next

- If `@coder` is connected: the handoff arrives immediately.
- If `@coder` is offline: the handoff waits in the mailbox. When the coder reconnects with `greft connect`, it is delivered automatically.

The coder reads and acknowledges:

```bash
greft inbox
greft read <message_id>
greft ack <message_id>
greft reply <message_id> "Starting implementation now."
```

## Try it offline

Stop the coder's session (Ctrl-C), send the handoff, then restart the coder. The handoff arrives on connect — no polling, no re-send.
