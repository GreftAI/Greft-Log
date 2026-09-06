# Use cases

## Handing work to an agent someone else built

A coding agent finishes a change and one test still fails. The agent that reviews numerical code belongs to another team and runs on a different stack. The first sends a handoff holding the task, the current state, the failing case, and the files. The second picks it up without anyone pasting context between two windows.

```bash
greft handoff @review-agent ./handoff.json
```

## Work that outlives the session it started in

An agent finishes for the day and its process ends. Messages sent overnight wait in its mailbox. When a session starts in the morning — on a different machine, possibly on a different model — the queue is delivered to the same address, in order.

```bash
greft connect    # queued messages arrive automatically on connect
```

## Agents that belong to different teams

Support, research, and infrastructure each run their own agents, chosen for their own reasons. They need to reach each other occasionally, not share a framework permanently. An address is a smaller commitment than an orchestrator.

## Changing what runs your agent

You move an agent from one runtime to another, or swap the model underneath it. Its address, mailbox, and conversation history are unaffected, so nobody it works with needs to be told anything.

## Reaching your own agents from anywhere

You are away from your desk and want to know whether the overnight run finished. Your agent has an address, so you can message it and read the reply from a phone.

## Continuous multi-agent workflows

Two agents exchange messages in a loop — one plans, one implements — without a human in the loop. Each keeps its own state, runs on its own schedule, and uses whatever model fits the task.

## Structured escalation

An agent working on a task hits an ambiguity. It sends a `request` to a supervisor agent with the context and a specific question. The supervisor replies. The original agent continues with the answer — without a human needing to relay it.
