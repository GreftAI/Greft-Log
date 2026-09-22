# Greft Job Companion

Give a running Python job a Greft identity so another Greft identity can start it, ask for progress, cancel it, and retrieve the latest result.

This example uses **no LLM**. Greft is the communication layer around an ordinary long-running Python process.

```text
controller identity
      |
      | RUN / STATUS / CANCEL / RESULT
      v
    Greft
      |
      v
worker identity -> Python process -> background job
                                  -> sample-inputs/ -> output/
```

## Why this example matters

Greft is not limited to communication between AI assistants. A normal
long-running program can have its own Greft identity and mailbox.

That means a separate user, agent, or application can communicate with
the job while it is running without sharing its process or execution
environment.

The Markdown-to-HTML conversion in this example is intentionally simple.
The same pattern can wrap model training, simulations, imports, exports,
builds, evaluations, notebook computations, or other long-running work.

## What the sample job does

The worker converts the bundled Markdown/text files in `sample-inputs/` into HTML files in `output/`. A short delay between files makes `STATUS` and `CANCEL` easy to test while the job is active.

Replace the conversion function with an import, export, build, simulation, evaluation loop, notebook computation, or another long-running task.

## Requirements

- Python 3.12 recommended
- Greft `0.1.15`
- two existing Greft identities in the same project:
  - one controller
  - one worker

The addresses can have any names. You do **not** need to create new addresses specifically for this example.

## 1. Create a project virtual environment

Installing Greft with `pipx` makes the CLI available, but that isolated installation is not automatically importable by your project Python. Install Greft inside this project's virtual environment too.

### PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Windows CMD

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Verify the SDK import:

```bash
python -c "from sdk.python.client import GreftClient; print('Greft SDK OK')"
```

## 2. Select the worker identity

Use the `GREFT_HOME` that belongs to the Greft identity that should act as the running job.

### PowerShell

```powershell
$env:GREFT_HOME="$HOME\.greft\your-worker-home"
greft whoami
```

### Windows CMD

```bat
set "GREFT_HOME=%USERPROFILE%\.greft\your-worker-home"
greft whoami
```

### macOS / Linux

```bash
export GREFT_HOME="$HOME/.greft/your-worker-home"
greft whoami
```

`greft whoami` should show the worker address you intend to use.

If you do not already have a suitable worker identity and your account allows another address, initialize one using the normal Greft setup flow. Do not commit Greft keys or API credentials to this repository.

## 3. Configure the controller

The worker needs the address to which it should send responses.

### PowerShell

```powershell
$env:OWNER_ADDRESS="@your-controller"
```

### Windows CMD

```bat
set OWNER_ADDRESS=@your-controller
```

### macOS / Linux

```bash
export OWNER_ADDRESS=@your-controller
```

`OWNER_ADDRESS` is required for real Greft runs. The program exits immediately if it is missing instead of attempting to send to a fake default address.

For stricter control, also set the controller's stable Greft agent ID:

```text
OWNER_AGENT_ID=agt_...
```

When `OWNER_AGENT_ID` is set, messages from other identities are ignored as control commands.

## 4. Optional local smoke test

Test the background worker without contacting Greft:

```bash
python main.py --dry-run --start --once
```

It should process all six bundled files, print progress, print the completion message that would be sent through Greft, and exit.

## 5. Start the Job Companion

With the worker identity selected through `GREFT_HOME`:

```bash
python main.py
```

Expected startup output:

```text
Job Companion is running.
Commands: RUN, STATUS, CANCEL, RESULT
```

Leave this terminal running.

## 6. Control it from another Greft identity

Open a second terminal and select your controller's `GREFT_HOME`.

Then send commands to the worker address.

```bash
greft send @your-worker "RUN"
```

While it is running:

```bash
greft send @your-worker "STATUS"
```

Request cancellation:

```bash
greft send @your-worker "CANCEL"
```

Retrieve the latest stored result:

```bash
greft send @your-worker "RESULT"
```

Check the controller inbox using the normal Greft CLI workflow.

A running job reports status similar to:

```text
Job Companion status

Job: job_a1b2c3d4
State: running
Progress: 3/6
Last file: 03-notes.txt
Elapsed: 7s
Error: None
```

## Expected behavior

A useful end-to-end test is:

```text
RUN
 -> job starts
STATUS
 -> real progress is returned
CANCEL
 -> cancellation is requested
RESULT
 -> state is canceled, never completed
RUN
 -> a new job starts
RESULT after completion
 -> state is completed and progress is 6/6
```

Starting a new run clears previous generated HTML files so the contents of `output/` correspond to the current job.

## Restart behavior

The Greft mailbox can persist independently of this Python process, but the worker thread cannot survive a process restart.

If the application restarts while local state says a job was `running`, the example changes that job to `interrupted`. It does not pretend computation resumed automatically.

## Message safety

The example handles two important cases explicitly:

- **Undecryptable messages:** if Greft reports `decryption_status: failed`, the program prints the decryption error and leaves the message unacknowledged instead of treating it as an empty command.
- **Duplicate delivery:** handled message IDs are stored in `state.json`. If an acknowledgement fails after a successful response, a redelivered message can be acknowledged without sending the response twice.

## Troubleshooting

### `ModuleNotFoundError: No module named 'sdk'`

The Greft CLI may be installed with `pipx`, while your application is using a different Python interpreter. Activate the project `.venv` and run:

```bash
python -m pip install -r requirements.txt
```

### `RuntimeError: No identity configured.`

Check `GREFT_HOME` in the same terminal that starts `python main.py`, then run:

```bash
greft whoami
```

Remember that PowerShell, CMD, and Bash use different environment-variable syntax as shown above.

### A message arrives but cannot be decrypted

The SDK may report that the local `.x25519` private key for the selected identity is missing. Do not copy encryption keys from another identity. Repair the identity using Greft's supported recovery flow, or temporarily use another existing identity whose key material is intact.

### Sending a response returns `404 Not Found`

Verify that `OWNER_ADDRESS` is a real, resolvable Greft address in the project rather than a placeholder.

## Files

```text
job-companion/
├── .gitignore
├── README.md
├── main.py
├── requirements.txt
├── sample-inputs/
│   ├── 01-welcome.md
│   ├── 02-roadmap.md
│   ├── 03-notes.txt
│   ├── 04-checklist.md
│   ├── 05-summary.txt
│   └── 06-finish.md
└── output/
    └── .gitkeep
```

`state.json`, generated outputs, virtual environments, local Greft state, and `.env` files are ignored by Git.

## Greft SDK surface used

```python
from sdk.python.client import GreftClient

client = GreftClient()
client.connect()
client.inbox()
client.send(to=..., msg_type=..., payload={...})
client.ack(message_id)
client.disconnect()
```

The example uses polling rather than `listen()` to keep the receive loop explicit and easy to adapt.
