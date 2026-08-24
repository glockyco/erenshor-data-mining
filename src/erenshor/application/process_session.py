"""Own and safely terminate one foreground process session."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ProcessIdentity:
    pid: int
    process_group: int
    started_at: str
    command: str


IdentityReader = Callable[[int], ProcessIdentity | None]
ProcessStarter = Callable[..., Any]


def read_process_identity(pid: int) -> ProcessIdentity | None:
    """Read identity fields from the operating system for one PID."""
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "pgid=", "-o", "lstart=", "-o", "args="],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    fields = result.stdout.strip().split(maxsplit=6)
    if len(fields) != 7:
        return None
    command = fields[6]
    crossover_command = command.find("/Applications/CrossOver.app/")
    if crossover_command >= 0:
        command = command[crossover_command:]
    return ProcessIdentity(pid, int(fields[0]), " ".join(fields[1:6]), command)


def identity_matches(expected: ProcessIdentity, actual: ProcessIdentity | None) -> bool:
    return actual == expected


class ProcessSession:
    """Start, record, wait for, and terminate one dedicated process group."""

    def __init__(
        self,
        record_path: Path,
        *,
        grace_seconds: float = 8.0,
        identity_settle_seconds: float = 0.5,
        starter: ProcessStarter = subprocess.Popen,
        identity_reader: IdentityReader = read_process_identity,
    ) -> None:
        self.record_path = record_path
        self.grace_seconds = grace_seconds
        self.identity_settle_seconds = identity_settle_seconds
        self._starter = starter
        self._identity_reader = identity_reader
        self._process: Any | None = None
        self._identity: ProcessIdentity | None = None

    def run(self, command: list[str], *, cwd: Path | None = None) -> int:
        self.record_path.parent.mkdir(parents=True, exist_ok=True)
        if self.record_path.exists():
            raise RuntimeError(
                f"game session record already exists: {self.record_path}; "
                "inspect it with `erenshor mod launch --recover` before another launch"
            )
        process = self._starter(command, cwd=cwd, start_new_session=True)
        self._process = process
        if self.identity_settle_seconds > 0:
            time.sleep(self.identity_settle_seconds)
        identity = self._identity_reader(process.pid)
        if identity is None:
            process.terminate()
            process.wait()
            raise RuntimeError(f"cannot record process identity for PID {process.pid}")
        self._identity = identity
        self._write_record(identity, command)
        previous_handlers: dict[signal.Signals, Any] = {}

        def request_shutdown(_signum: int, _frame: object) -> None:
            raise KeyboardInterrupt

        for handled_signal in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[handled_signal] = signal.signal(handled_signal, request_shutdown)
        try:
            return int(process.wait())
        except KeyboardInterrupt:
            self.shutdown()
            raise
        finally:
            for handled_signal, previous_handler in previous_handlers.items():
                signal.signal(handled_signal, previous_handler)
            if process.poll() is None:
                self.shutdown()
            if process.poll() is not None:
                self.record_path.unlink(missing_ok=True)

    def shutdown(self) -> None:
        process = self._process
        expected = self._identity
        if process is None or expected is None or process.poll() is not None:
            return
        actual = self._identity_reader(expected.pid)
        if not identity_matches(expected, actual):
            raise RuntimeError(f"process identity mismatch for PID {expected.pid}; refusing to signal candidate")
        os.killpg(expected.process_group, signal.SIGTERM)
        try:
            process.wait(timeout=self.grace_seconds)
            return
        except subprocess.TimeoutExpired:
            pass
        actual = self._identity_reader(expected.pid)
        if not identity_matches(expected, actual):
            raise RuntimeError(f"process identity mismatch for PID {expected.pid}; refusing forced termination")
        os.killpg(expected.process_group, signal.SIGKILL)
        process.wait()

    def _write_record(self, identity: ProcessIdentity, command: list[str]) -> None:
        payload = {"schemaVersion": 1, "identity": asdict(identity), "command": command}
        temporary = self.record_path.with_name(f".{self.record_path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.record_path)


def recover_recorded_session(
    record_path: Path,
    *,
    grace_seconds: float = 8.0,
    poll_seconds: float = 0.1,
    identity_reader: IdentityReader = read_process_identity,
    signal_process_group: Callable[[int, signal.Signals], None] = os.killpg,
) -> bool:
    """Terminate only a process whose complete recorded identity still matches."""
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    expected = ProcessIdentity(**payload["identity"])
    actual = identity_reader(expected.pid)
    if actual is None:
        record_path.unlink()
        return False
    if not identity_matches(expected, actual):
        raise RuntimeError(f"process identity mismatch for PID {expected.pid}; candidate was not signaled")

    def process_identity_changed() -> bool:
        deadline = time.monotonic() + grace_seconds
        while identity_matches(expected, identity_reader(expected.pid)):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(poll_seconds, remaining))
        return True

    signal_process_group(expected.process_group, signal.SIGTERM)
    if not process_identity_changed():
        signal_process_group(expected.process_group, signal.SIGKILL)
        if not process_identity_changed():
            raise RuntimeError(f"recorded process PID {expected.pid} did not exit; ownership record retained")
    record_path.unlink()
    return True
