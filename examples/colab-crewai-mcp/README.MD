# CrewAI in Google Colab → Local Agent via Greft

This example shows a **CrewAI agent running in Google Colab** completing a small software-release analysis and sending the result to a **separate Greft agent running on a local machine**.

The point of the example is not CrewAI-to-CrewAI collaboration. CrewAI already supports multi-agent workflows inside one CrewAI application. This example demonstrates **communication between independently running agents in different environments** through Greft.

```text
Google Colab
┌──────────────────────────────┐
│ CrewAI                       │
│ @colab-agent                 │
│ Software Release Analyst     │
└──────────────┬───────────────┘
               │ Greft MCP
               ▼
          Greft relay
               │
               ▼
┌──────────────────────────────┐
│ Local machine                │
│ @terminal-agent              │
│ Greft CLI                    │
└──────────────────────────────┘
```

## What the agent does

The Colab agent receives five **synthetic** software issues:

1. Login form accepts an invalid email address.
2. Dashboard crashes when the API returns an empty response.
3. Button spacing is slightly inconsistent on mobile devices.
4. Password reset links sometimes expire immediately after being generated.
5. The browser console contains a non-sensitive warning.

It must classify the issues by priority, explain the priorities, identify release blockers, produce a concise recommendation, and then use Greft's `send_message` MCP tool to send the complete analysis to `@terminal-agent`.

## Prerequisites

You need:

- a Greft project;
- `@colab-agent` and `@terminal-agent` in the same project;
- access to a publicly reachable Greft MCP relay;
- the Greft CLI installed locally;
- an OpenRouter API key;
- a Google account for Colab.

The notebook defaults to OpenRouter's free-model router, so the LLM portion can be run without paid model usage while free capacity is available.

## 1. Configure the local Greft agent

Use a dedicated Greft home directory if you want to keep this demo identity isolated from other Greft identities.

### Windows CMD

```bat
set "GREFT_HOME=%USERPROFILE%\.greft\terminal-agent"
greft login
greft project use "YOUR_PROJECT"
greft api-key use --secret YOUR_GREFT_API_KEY
greft init @terminal-agent
```

### macOS / Linux

```bash
export GREFT_HOME="$HOME/.greft/terminal-agent"
greft login
greft project use "YOUR_PROJECT"
greft api-key use --secret YOUR_GREFT_API_KEY
greft init @terminal-agent
```

Confirm the Colab identity is reachable:

```bash
greft contacts add @colab-agent
greft resolve @colab-agent
```

> Do not paste real API keys into source files, screenshots, recordings, issues, or commits.

## 2. Add Colab secrets

Open `notebook.ipynb` in Google Colab.

In the **Secrets** panel, add:

| Secret               | Value                                       |
| -------------------- | ------------------------------------------- |
| `OPENROUTER_API_KEY` | Your OpenRouter API key                     |
| `GREFT_API_KEY`      | Your Greft project API key                  |
| `GREFT_API_URL`      | Base URL of the Greft relay, without `/mcp` |

Example shape only:

```text
OPENROUTER_API_KEY = sk-or-...
GREFT_API_KEY      = grf_sk_...
GREFT_API_URL      = https://your-greft-relay.example
```

The notebook reads these values with `google.colab.userdata`; it does not print them.

## 3. Make the terminal receiver listen to incoming messages or manually check the inbox yourself

Run:

```bash
greft connect
```

OR

```bash
greft inbox
greft read <YOUR_MESSAGE_ID>
```

Keep this terminal open.

## 4. Run the notebook

Run `notebook.ipynb` from top to bottom.

The notebook:

1. installs pinned CrewAI and MCP dependencies;
2. loads credentials from Colab Secrets;
3. configures OpenRouter;
4. connects CrewAI to Greft's Streamable HTTP MCP endpoint;
5. exposes only the `send_message` MCP tool to the agent;
6. runs the software-release analysis;
7. sends the final analysis to `@terminal-agent`.

## Expected result

The local terminal should receive a message from `@colab-agent` containing a prioritized release assessment.

The exact wording varies by model, but the result should include:

- high-, medium-, and low-priority issues;
- issues that should block release;
- a short release recommendation.

## Why Greft?

CrewAI can coordinate agents that belong to the same CrewAI workflow.

This example demonstrates a different boundary:

```text
CrewAI agent in Google Colab
            │
            ▼
          Greft
            │
            ▼
independently running local agent
```

The two sides do not need to share the same Python process or filesystem. Greft provides the communication layer between their identities.

## Security notes

Before publishing changes to this example:

- never hardcode `OPENROUTER_API_KEY` or `GREFT_API_KEY`;
- keep real keys only in Colab Secrets or another secret manager;
- keep the MCP tool allowlist restricted to what the demo needs;
- clear notebook outputs before committing if they contain account-specific data;
- rotate any credential that is accidentally exposed.

The sample issue reports are deliberately synthetic so no private project data is required.

## Dependencies

Pinned in `requirements-colab.txt`:

```text
crewai[litellm]==1.15.22
mcp
```

The notebook repeats the same pins in its install cell so it remains runnable directly from Colab without requiring the repository to be cloned first.
