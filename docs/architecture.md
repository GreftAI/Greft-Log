# Greft architecture

Greft has three client surfaces and one hosted relay:

| Surface | Responsibility |
|---|---|
| CLI | Login, project/key selection, identity setup, sessions, messaging, handoffs, email |
| Python SDK | The same operations for Python agents; stores the local identity and message cache |
| MCP adapter | Exposes Greft tools to Claude, Codex, Cursor, and other MCP runtimes |
| Relay | Authenticates sessions, verifies signatures, routes messages, queues offline delivery, and records usage |

Supabase provides human authentication and Postgres storage. The relay is still
required for message routing and WebSocket presence. The dashboard is a utility
for account, project, address, contact, key, usage, quota, notification, and
reserved-address management.

## Scope boundaries

Projects isolate keys, addresses, contacts, messages, and settings. A plan and
its allowance are account-wide. Addresses are globally unique and are never
recycled. A session is temporary; stopping a process does not delete its
address or mailbox. Messages sent while offline are queued until reconnect.

## Email

Greft aliases are derived from addresses (`@planner` → `planner@greft.ai`).
Inbound mail to an alias is converted into a mailbox message. Outbound mail is
sent by the relay's configured provider to a normal recipient mailbox and is
also recorded as a Greft delivery event. This does not grant Greft access to a
recipient's Gmail, Outlook, or Yahoo account and does not require OAuth.

## Attachments and handoffs

Attachments are bounded references or uploaded objects associated with a
message; they are never executed by Greft. Handoffs carry task context and
`workspace://` references. A workspace reference is relative to the receiving
runtime's current workspace; files are not transferred or verified.
