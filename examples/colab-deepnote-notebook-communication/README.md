# Colab ↔ Deepnote communication through

Run a small machine-learning experiment in **Google Colab**, send its metrics to **Deepnote** for review, and send the verdict back to Colab through **Greft**.

```text
Google Colab
@colab-agent
     │
     │ experiment result
     ▼
   Greft
     │
     ▼
Deepnote
@deepnote-agent
     │
     │ PASS / REVIEW
     ▼
   Greft
     │
     ▼
Google Colab
```

## What this demonstrates

The two notebooks run in independent hosted environments. Neither notebook integrates directly with the other platform.

- **Colab** runs a small Iris classification experiment.
- **Greft remote MCP** carries messages between two Greft identities.
- **Deepnote** applies a deterministic review rule.
- **Colab** receives the final review.

No LLM, CrewAI, database, public server, or direct Colab↔Deepnote API integration is required.

## Files

```text
colab-deepnote-experiment-review/
├── README.md
├── colab.ipynb
├── deepnote.ipynb
├── requirements-colab.txt
├── requirements-deepnote.txt
└── .env.example
```

## Prerequisites

You need:

- a Greft project;
- two addresses in that same project:
  - `@colab-agent`
  - `@deepnote-agent`
- access to the Greft remote MCP endpoint;
- a Greft API key for the project;
- a Google account for Colab;
- a Deepnote project.

If you use different Greft addresses, update the address constants in both notebooks.

## 1. Configure Google Colab

Open `colab.ipynb` in Colab.

In the **Secrets** panel, add:

```text
GREFT_API_URL
GREFT_API_KEY
```

`GREFT_API_URL` is the relay base URL without `/mcp`.

Do not hardcode the real values in notebook cells.

## 2. Configure Deepnote

Open `deepnote.ipynb` in Deepnote.

Create an **Environment variables** integration and add:

```text
GREFT_API_URL
GREFT_API_KEY
```

Connect that integration to the project.

Do not print or commit the real values.

## 3. Run the example

Use this order:

1. Run the setup cells in both notebooks.
2. In Colab, run the Iris experiment.
3. In Colab, send the experiment result to `@deepnote-agent`.
4. In Deepnote, read the inbox and select the newest `experiment_result`.
5. In Deepnote, apply the review rule and send the review to `@colab-agent`.
6. Back in Colab, read the inbox and select the matching `experiment_review`.

The Deepnote review rule is deliberately simple:

```python
PASS if accuracy >= 0.90 else REVIEW
```

This keeps the example deterministic and focused on Greft communication rather than model behavior.

## Why `read_messages` instead of `wait_for_message`?

A Greft address can already have unacknowledged messages in its mailbox. In that case, `wait_for_message` may return an older queued message rather than the experiment you just sent.

This example therefore uses:

```text
read_messages
    ↓
sort by message sequence
    ↓
parse JSON messages
    ↓
select the newest message with the expected `kind`
```

Colab additionally matches the `experiment_id` when reading Deepnote's review.

This makes the example tolerant of unrelated email or test messages already present in the mailbox.

## Example message: Colab → Deepnote

```json
{
  "kind": "experiment_result",
  "experiment_id": "iris-logreg-a1b2c3d4",
  "dataset": "Iris",
  "model": "LogisticRegression",
  "accuracy": 0.9667,
  "training_rows": 120,
  "test_rows": 30
}
```

## Example message: Deepnote → Colab

```json
{
  "kind": "experiment_review",
  "experiment_id": "iris-logreg-a1b2c3d4",
  "verdict": "PASS",
  "accuracy": 0.9667,
  "required_accuracy": 0.9
}
```

## Security

Before publishing notebook changes:

- never commit a real `GREFT_API_KEY`;
- keep credentials in Colab Secrets and Deepnote environment variables;
- clear outputs that contain account-specific IDs or messages;
- do not print authorization headers;
- rotate any key that is accidentally exposed.

## Adapting the example

The Iris experiment is intentionally small. The same communication pattern can be reused for:

- model evaluation;
- data-quality checks;
- simulation results;
- benchmark reports;
- notebook-to-notebook review workflows.

Replace the experiment in `colab.ipynb` and the review rule in `deepnote.ipynb`; the Greft messaging layer can remain the same.
