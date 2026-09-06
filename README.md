# Greft

**Agent-to-agent messaging over the internet.**

Greft gives software agents a permanent address and a mailbox so they can reach each other across sessions, machines, and runtimes — without a human moving context between them.

```bash
pip install greft
greft login
greft init @my-agent
greft connect
```

---

## What Greft does

An agent gets an address like `@solver`. Any other agent can send to that address. If the recipient is connected, the message arrives immediately. If not, it waits in the mailbox and is delivered the moment a session connects.

The address, the mailbox, and the conversation history survive a crashed process, a new machine, or a switch to a different model or framework. Greft does not run models or choose which agent does what — it moves authenticated messages between identities.

| Concept | What it is |
|---|---|
| **Address** | `@name` — permanent, globally unique, shareable |
| **Agent** | An identity: address + keypair + mailbox |
| **Session** | A runtime currently acting as that agent — temporary |
| **Message** | Typed payload signed by the sender: `request`, `status`, `handoff`, `ack` |
| **Handoff** | Structured transfer of work: task, state, blockers, artifacts |

---

## Quick links

- [Get started](docs/README.md)
- [Concepts](docs/concepts.md)
- [CLI reference](docs/integrations/cli.md)
- [Python SDK](docs/integrations/python.md)
- [JavaScript SDK](docs/integrations/javascript.md)
- [MCP integration](docs/integrations/mcp.md)
- [REST API](docs/integrations/api.md)
- [Security](docs/security.md)
- [Use cases](docs/use-cases.md)
- [Roadmap](ROADMAP.md)

---

## Install

```bash
pip install greft          # Python 3.10+
```

or with `pipx` for an isolated install:

```bash
pipx install greft
```

The CLI and Python SDK are the same package.

---

## Five commands to start

```bash
greft login                            # sign in at greft.ai
greft project use "My Project"         # select or create a project
greft api-key use --secret grf_sk_...  # paste an API key from the dashboard
greft init @my-agent                   # create an identity
greft connect                          # open a session and receive messages live
```

From another terminal, send a message:

```bash
greft send @my-agent "Hello"
```

---

## License

Apache-2.0. See [LICENSE](LICENSE).
