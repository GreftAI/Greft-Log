from __future__ import annotations

import argparse
import html
import json
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "sample-inputs"
OUTPUT_DIR = ROOT / "output"
STATE_FILE = ROOT / "state.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_inbox(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        for key in ("messages", "items", "data"):
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise TypeError("Unexpected Greft inbox response shape.")


def message_text(envelope: dict[str, Any]) -> str:
    payload = envelope.get("payload")
    if isinstance(payload, dict):
        text = payload.get("text")
        if isinstance(text, str):
            return text
    text = envelope.get("text")
    return text if isinstance(text, str) else ""


def sender_agent_id(envelope: dict[str, Any]) -> str | None:
    for key in (
        "from_agent_id",
        "sender_agent_id",
        "fromAgentId",
        "senderAgentId",
    ):
        value = envelope.get(key)
        if isinstance(value, str) and value:
            return value

    sender = envelope.get("sender")
    if isinstance(sender, dict):
        for key in ("id", "agent_id", "agentId"):
            value = sender.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def decryption_failure(envelope: dict[str, Any]) -> str | None:
    metadata = envelope.get("metadata")
    if not isinstance(metadata, dict):
        return None
    if metadata.get("decryption_status") != "failed":
        return None
    error = metadata.get("decryption_error")
    return error if isinstance(error, str) and error else "Unknown decryption error"


class GreftGateway:
    """Tiny adapter around the Greft 0.1.15 Python SDK surface used by this example."""

    def __init__(self) -> None:
        try:
            from sdk.python.client import GreftClient
        except ImportError as exc:
            raise RuntimeError(
                "Greft's Python SDK is not importable. Install requirements and "
                "make sure the Greft package exposes sdk.python.client."
            ) from exc
        self.client = GreftClient()

    def connect(self) -> None:
        self.client.connect()

    def disconnect(self) -> None:
        self.client.disconnect()

    def inbox(self) -> list[dict[str, Any]]:
        return normalize_inbox(self.client.inbox())

    def ack(self, message_id: str) -> None:
        self.client.ack(message_id)

    def send(self, to: str, text: str, *, msg_type: str = "status") -> None:
        self.client.send(
            to=to,
            msg_type=msg_type,
            payload={"text": text},
        )


class DryRunGateway:
    def connect(self) -> None:
        print("[dry-run] Greft connection skipped.")

    def disconnect(self) -> None:
        pass

    def inbox(self) -> list[dict[str, Any]]:
        return []

    def ack(self, message_id: str) -> None:
        print(f"[dry-run] Would acknowledge {message_id}")

    def send(self, to: str, text: str, *, msg_type: str = "status") -> None:
        print("\n--- DRY RUN: GREFT MESSAGE ---")
        print(f"To: {to}")
        print(f"Type: {msg_type}")
        print(text)
        print("--- END MESSAGE ---\n")


@dataclass(frozen=True)
class WorkerEvent:
    kind: str
    processed: int
    total: int
    filename: str | None = None
    error: str | None = None


class JobCompanion:
    def __init__(
        self,
        gateway: Any,
        *,
        owner_address: str,
        owner_agent_id: str | None,
        poll_seconds: float,
        work_delay_seconds: float,
    ) -> None:
        self.gateway = gateway
        self.owner_address = owner_address
        self.owner_agent_id = owner_agent_id
        self.poll_seconds = poll_seconds
        self.work_delay_seconds = work_delay_seconds

        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.events: queue.Queue[WorkerEvent] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.state = self._load_state()
        self.processed_message_ids: set[str] = set(
            self.state.get("processed_message_ids", [])
        )
        self.warned_decryption_ids: set[str] = set()

        if self.state.get("status") == "running":
            # A Python thread cannot survive a process restart.
            self.state["status"] = "interrupted"
            self.state["finished_at"] = utc_now()
            self.state["last_error"] = "Application restarted before the job completed."
            self._save_state()

    def _default_state(self) -> dict[str, Any]:
        return {
            "job_id": None,
            "status": "idle",
            "processed": 0,
            "total": 0,
            "started_at": None,
            "finished_at": None,
            "last_file": None,
            "last_error": None,
            "result": None,
            "processed_message_ids": [],
        }

    def _load_state(self) -> dict[str, Any]:
        if not STATE_FILE.exists():
            return self._default_state()
        try:
            loaded = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._default_state()
        base = self._default_state()
        if isinstance(loaded, dict):
            base.update(loaded)
        return base

    def _save_state(self) -> None:
        STATE_FILE.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def _remember_message(self, message_id: str) -> None:
        recent = [
            item
            for item in self.state.get("processed_message_ids", [])
            if isinstance(item, str) and item != message_id
        ]
        recent.append(message_id)
        self.state["processed_message_ids"] = recent[-100:]
        self.processed_message_ids = set(self.state["processed_message_ids"])
        self._save_state()

    def _input_files(self) -> list[Path]:
        return sorted(
            path
            for path in INPUT_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in {".md", ".txt"}
        )

    def start_job(self) -> str:
        with self.lock:
            if self.worker and self.worker.is_alive():
                return self.status_text(prefix="A job is already active.")

            files = self._input_files()
            if not files:
                return "Cannot start: sample-inputs contains no .md or .txt files."

            self.cancel_event.clear()
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            for old_output in OUTPUT_DIR.glob("*.html"):
                old_output.unlink()

            self.state.update(
                {
                    "job_id": f"job_{uuid.uuid4().hex[:8]}",
                    "status": "running",
                    "processed": 0,
                    "total": len(files),
                    "started_at": utc_now(),
                    "finished_at": None,
                    "last_file": None,
                    "last_error": None,
                    "result": None,
                }
            )
            self._save_state()

            self.worker = threading.Thread(
                target=self._run_job,
                args=(files,),
                name="job-companion-worker",
                daemon=True,
            )
            self.worker.start()
            return self.status_text(prefix="Job started.")

    def _run_job(self, files: list[Path]) -> None:
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            processed = 0

            for path in files:
                if self.cancel_event.is_set():
                    self.events.put(
                        WorkerEvent("canceled", processed, len(files), filename=path.name)
                    )
                    return

                self._convert_file(path)
                processed += 1
                self.events.put(
                    WorkerEvent("progress", processed, len(files), filename=path.name)
                )

                # Deliberate pause to make STATUS/CANCEL observable in the demo.
                if self.work_delay_seconds > 0:
                    time.sleep(self.work_delay_seconds)

            self.events.put(WorkerEvent("completed", processed, len(files)))
        except Exception as exc:  # demo boundary: turn worker crashes into job state
            self.events.put(
                WorkerEvent(
                    "failed",
                    int(self.state.get("processed") or 0),
                    int(self.state.get("total") or len(files)),
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    def _convert_file(self, source: Path) -> None:
        text = source.read_text(encoding="utf-8")
        escaped = html.escape(text)
        document = (
            "<!doctype html>\n"
            '<html lang="en">\n'
            "<head><meta charset=\"utf-8\"><title>Converted note</title></head>\n"
            f"<body><pre>{escaped}</pre></body>\n"
            "</html>\n"
        )
        destination = OUTPUT_DIR / f"{source.stem}.html"
        destination.write_text(document, encoding="utf-8")

    def drain_worker_events(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                return

            notification: str | None = None
            with self.lock:
                self.state["processed"] = event.processed
                self.state["total"] = event.total
                if event.filename:
                    self.state["last_file"] = event.filename

                if event.kind == "progress":
                    print(
                        f"Progress: {event.processed}/{event.total}"
                        + (f" - {event.filename}" if event.filename else "")
                    )

                if event.kind == "completed":
                    self.state["status"] = "completed"
                    self.state["finished_at"] = utc_now()
                    self.state["result"] = (
                        f"Converted {event.processed}/{event.total} files. "
                        f"Outputs are in {OUTPUT_DIR.name}/."
                    )
                    notification = self.result_text()

                elif event.kind == "canceled":
                    self.state["status"] = "canceled"
                    self.state["finished_at"] = utc_now()
                    self.state["result"] = (
                        f"Canceled after {event.processed}/{event.total} files."
                    )
                    notification = self.result_text()

                elif event.kind == "failed":
                    self.state["status"] = "failed"
                    self.state["finished_at"] = utc_now()
                    self.state["last_error"] = event.error
                    self.state["result"] = "Job failed before completion."
                    notification = self.result_text()

                self._save_state()

            if notification:
                print(
                    f"Job {self.state.get('status')}: "
                    f"{self.state.get('processed', 0)}/{self.state.get('total', 0)}"
                )
                try:
                    self.gateway.send(self.owner_address, notification, msg_type="status")
                except Exception as exc:
                    print(f"Could not send terminal job notification: {exc}")

    def cancel_job(self) -> str:
        with self.lock:
            if not (self.worker and self.worker.is_alive()):
                return "No running job to cancel.\n\n" + self.status_text()
            self.cancel_event.set()
            return (
                "Cancellation requested. The worker will stop at the next file boundary.\n\n"
                + self.status_text()
            )

    def _elapsed_seconds(self) -> int | None:
        started = self.state.get("started_at")
        if not isinstance(started, str):
            return None
        try:
            start_dt = datetime.fromisoformat(started)
        except ValueError:
            return None
        end_raw = self.state.get("finished_at")
        try:
            end_dt = datetime.fromisoformat(end_raw) if isinstance(end_raw, str) else datetime.now(timezone.utc)
        except ValueError:
            end_dt = datetime.now(timezone.utc)
        return max(0, int((end_dt - start_dt).total_seconds()))

    def status_text(self, prefix: str | None = None) -> str:
        with self.lock:
            lines = []
            if prefix:
                lines.extend([prefix, ""])
            lines.extend(
                [
                    "Job Companion status",
                    "",
                    f"Job: {self.state.get('job_id') or 'None'}",
                    f"State: {self.state.get('status', 'idle')}",
                    f"Progress: {self.state.get('processed', 0)}/{self.state.get('total', 0)}",
                    f"Last file: {self.state.get('last_file') or 'None'}",
                    f"Elapsed: {self._elapsed_seconds() if self._elapsed_seconds() is not None else 0}s",
                    f"Error: {self.state.get('last_error') or 'None'}",
                ]
            )
            return "\n".join(lines)

    def result_text(self) -> str:
        with self.lock:
            return (
                "Job Companion result\n\n"
                f"Job: {self.state.get('job_id') or 'None'}\n"
                f"State: {self.state.get('status', 'idle')}\n"
                f"Progress: {self.state.get('processed', 0)}/{self.state.get('total', 0)}\n"
                f"Result: {self.state.get('result') or 'No completed result yet.'}\n"
                f"Error: {self.state.get('last_error') or 'None'}"
            )

    def handle_command(self, text: str) -> str:
        command = text.strip().upper()
        if command == "RUN":
            return self.start_job()
        if command == "STATUS":
            return self.status_text()
        if command == "CANCEL":
            return self.cancel_job()
        if command == "RESULT":
            return self.result_text()
        return (
            "Unknown command.\n\n"
            "Available commands:\n"
            "RUN - start the sample batch job\n"
            "STATUS - report current progress\n"
            "CANCEL - request cancellation at the next file boundary\n"
            "RESULT - return the latest stored result"
        )

    def handle_inbox(self) -> None:
        for envelope in self.gateway.inbox():
            message_id = envelope.get("id")
            if not isinstance(message_id, str) or not message_id:
                continue

            if message_id in self.processed_message_ids:
                self.gateway.ack(message_id)
                continue

            decrypt_error = decryption_failure(envelope)
            if decrypt_error:
                if message_id not in self.warned_decryption_ids:
                    print(
                        "Received a Greft message that could not be decrypted. "
                        "It will remain unacknowledged so it can be retried after "
                        "the identity key issue is fixed."
                    )
                    print(f"Decryption error: {decrypt_error}")
                    self.warned_decryption_ids.add(message_id)
                continue

            if self.owner_agent_id:
                actual_sender = sender_agent_id(envelope)
                if actual_sender != self.owner_agent_id:
                    self._remember_message(message_id)
                    self.gateway.ack(message_id)
                    print(
                        f"Ignored control message {message_id} from "
                        f"{actual_sender or 'unknown sender'}."
                    )
                    continue

            command = message_text(envelope).strip()
            if not command:
                self._remember_message(message_id)
                self.gateway.ack(message_id)
                print(f"Ignored non-text Greft message: {message_id}")
                continue

            response = self.handle_command(command)

            # Send first, then persist the handled ID, then acknowledge. If ACK
            # fails after a successful send, redelivery will be acknowledged
            # without sending the response twice.
            self.gateway.send(self.owner_address, response, msg_type="status")
            self._remember_message(message_id)
            self.gateway.ack(message_id)
            print(f"Handled Greft command: {command}")

    def run(self, *, start_immediately: bool = False, once: bool = False) -> None:
        self.gateway.connect()
        try:
            if start_immediately:
                print(self.start_job())

            print("Job Companion is running.")
            print("Commands: RUN, STATUS, CANCEL, RESULT")

            while True:
                try:
                    self.drain_worker_events()
                    self.handle_inbox()
                except Exception as exc:
                    print(f"Greft loop error: {type(exc).__name__}: {exc}")

                if once:
                    # Useful for local smoke tests without a permanent loop.
                    if self.worker:
                        self.worker.join()
                        self.drain_worker_events()
                    return

                time.sleep(self.poll_seconds)
        finally:
            self.gateway.disconnect()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Control a running batch job through Greft.")
    parser.add_argument("--start", action="store_true", help="Start the sample job immediately.")
    parser.add_argument("--dry-run", action="store_true", help="Do not connect to Greft.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one local cycle and exit (mainly for smoke testing).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    owner_address = os.getenv("OWNER_ADDRESS")
    if not owner_address:
        if args.dry_run:
            owner_address = "@owner"
        else:
            raise SystemExit(
                "Missing OWNER_ADDRESS. Set it to the Greft address that should "
                "receive job responses, for example @my-controller."
            )

    owner_agent_id = os.getenv("OWNER_AGENT_ID") or None
    poll_seconds = float(os.getenv("POLL_SECONDS", "2"))
    work_delay_seconds = float(os.getenv("WORK_DELAY_SECONDS", "2"))
    if poll_seconds <= 0:
        raise SystemExit("POLL_SECONDS must be greater than 0.")
    if work_delay_seconds < 0:
        raise SystemExit("WORK_DELAY_SECONDS cannot be negative.")

    gateway: Any = DryRunGateway() if args.dry_run else GreftGateway()
    companion = JobCompanion(
        gateway,
        owner_address=owner_address,
        owner_agent_id=owner_agent_id,
        poll_seconds=poll_seconds,
        work_delay_seconds=work_delay_seconds,
    )
    try:
        companion.run(start_immediately=args.start, once=args.once)
    except KeyboardInterrupt:
        print("\nJob Companion stopped.")


if __name__ == "__main__":
    main()
