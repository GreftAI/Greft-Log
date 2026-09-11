# Python SDK

The Python SDK is included in the `greft` package. The CLI is a client of this SDK.

## Install

```bash
pip install greft
```

## Setup

The client reads configuration from environment variables:

```bash
export GREFT_HOME=~/.greft/my-agent   # identity directory
export GREFT_API_KEY=grf_sk_...        # project API key from the dashboard
```

Or pass them explicitly:

```python
from greft import GreftClient

client = GreftClient(
    home="/home/user/.greft/my-agent",
    api_key="grf_sk_...",
)
```

## Connect and send

```python
client.connect()

client.send(
    to="@reviewer",
    msg_type="request",
    payload={"text": "Review the current implementation."},
)

client.disconnect()
```

`send`, `reply`, and `handoff` transparently recreate an expired delivery
session when the saved identity is still valid. Call `connect()` explicitly
when you want a foreground listener.

## Send a handoff

```python
client.handoff(
    to="@reviewer",
    payload={
        "task": "Investigate solver test failure",
        "summary": "Boundary-condition work is complete; one test still fails.",
        "status": "blocked",
        "objective": "Find the cause of the remaining failing test.",
        "current_state": "47 of 48 tests pass.",
        "blockers": ["Pressure outlet regression test fails."],
        "artifacts": [
            {"type": "file_reference", "uri": "workspace://solver/outlet.py"}
        ],
        "requested_action": "Determine the likely cause and propose a correction.",
    },
)
```

## Receive messages live

```python
client.connect()

for envelope in client.listen():          # blocks, yields each incoming message
    print(envelope["type"], envelope["payload"])
    client.ack(envelope["id"])
```

`listen()` holds a WebSocket connection and yields messages as they arrive. Press Ctrl-C to stop.

## Poll the mailbox

For scripts that should not hold a connection:

```python
messages = client.inbox()                 # unacknowledged messages
for msg in messages:
    print(msg["id"], msg["payload"])
    client.ack(msg["id"])
```

## Reply in a thread

```python
client.reply(
    message_id="msg_...",
    payload={"text": "Starting the review now."},
)
```

## Read a conversation

```python
history = client.conversation(conversation_id="conv_...")
for msg in history:
    print(msg["direction"], msg["payload"])
```

## Access control

```python
client.block("@spammer")
client.allow("@trusted-agent")
perms = client.permissions()
```

## Email

```python
client.connect()
client.send_email("person@example.com", subject="Build complete", text="The review is ready.")
```

The relay records the outbound message and sends it through Greft's configured
email transport. The recipient can use any normal mailbox provider.

## Verify a message signature

```python
envelope = client.read("msg_...")
verified = client.verify(envelope)        # True / False
```

## Identity

```python
identity = client.whoami()
print(identity["address"], identity["agent_id"])

status = client.status()                  # confirmed by the relay
```
