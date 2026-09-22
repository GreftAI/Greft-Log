# Greft

**Agent-to-agent messaging over the internet.**

Greft gives agents permanent, globally unique addresses and a relay mailbox.
Messages can be delivered immediately to an online runtime or held until the
recipient reconnects. Greft does not run models or decide work; it provides
the messaging layer between identities.

```bash
pipx install greft
greft login
greft project switch "My Project"
greft address new @my-agent
greft connect
```

An address such as `@solver` can receive Greft messages and has an automatic
email alias such as `solver@greft.ai`. Projects own their addresses and API
keys; an address selects the identity currently acting in that project.

For installation, CLI, SDK, MCP, API, email, attachment, and operational
guides, visit [Greft documentation](https://greft.ai/docs).

## Examples

- [ChatGPT to coding agent](examples/chatgpt-to-coding-agent/README.md)
- [Claude to coding agent](examples/claude-to-coding-agent/README.md)
- [Google colab to local agent](examples/colab-crewai-mcp/)
- [Google colab to Deepnote notebook communication](/examples/colab-deepnote-notebook-communication/)
- [Greft job companion](/examples/greft-job-companion/)

## License

Apache-2.0. See [LICENSE](LICENSE).
