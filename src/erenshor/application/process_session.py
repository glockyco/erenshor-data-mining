"""Own and safely terminate one foreground process session.

A session starts its command in a new process group and owns every process
that joins that group while the group leader is alive. Under CrossOver the
leader is a Wine wrapper and the game is another member of the group, so
ownership cannot stop at the leader: the leader can exit while the game runs.

Each member is recorded with its full identity (PID, process group, start
time, command). A process is signalled only while its current identity
matches the recorded one exactly, so a reused PID is never signalled.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

RECORD_SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class ProcessIdentity:
    pid: int
    process_group: int
    started_at: str
    command: str


IdentityReader = Callable[[int], ProcessIdentity | None]
GroupReader = Callable[[int], list[ProcessIdentity]]
ProcessSignaller = Callable[[int, signal.Signals], None]
ProcessStarter = Callable[..., Any]


def _parse_identity(line: str) -> ProcessIdentity | None:
    """Parse ``pid pgid lstart(5 fields) args`` from one ``ps`` line."""
    fields = line.strip().split(maxsplit=7)
    if len(fields) != 8:
        return None
    command = fields[7]
    crossover_command = command.find("/Applications/CrossOver.app/")
    if crossover_command >= 0:
        command = command[crossover_command:]
    return ProcessIdentity(int(fields[0]), int(fields[1]), " ".join(fields[2:7]), command)


def _ps(*selection: str) -> list[str]:
    result = subprocess.run(
        ["ps", *selection, "-o", "pid=", "-o", "pgid=", "-o", "lstart=", "-o", "args="],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def read_process_identity(pid: int) -> ProcessIdentity | None:
    """Read identity fields from the operating system for one PID."""
    lines = _ps("-p", str(pid))
    return _parse_identity(lines[0]) if lines else None


def read_group_members(process_group: int) -> list[ProcessIdentity]:
    """Read the identities of every live process in one process group."""
    identities = (_parse_identity(line) for line in _ps("-ax"))
    return [identity for identity in identities if identity is not None and identity.process_group == process_group]


def identity_matches(expected: ProcessIdentity, actual: ProcessIdentity | None) -> bool:
    return actual == expected


def _live(members: Iterable[ProcessIdentity], identity_reader: IdentityReader) -> list[ProcessIdentity]:
    return [member for member in members if identity_matches(member, identity_reader(member.pid))]


def _terminate(
    members: Iterable[ProcessIdentity],
    *,
    identity_reader: IdentityReader,
    signal_process: ProcessSignaller,
    grace_seconds: float,
    poll_seconds: float,
) -> None:
    """Stop every still-matching member: SIGTERM, then SIGKILL after the grace period.

    Raises:
        RuntimeError: If a matching member survives SIGKILL.
    """

    def signal_live(sig: signal.Signals) -> list[ProcessIdentity]:
        live = _live(members, identity_reader)
        for member in live:
            with contextlib.suppress(ProcessLookupError):
                signal_process(member.pid, sig)
        return live

    def wait_until_gone(live: list[ProcessIdentity]) -> list[ProcessIdentity]:
        deadline = time.monotonic() + grace_seconds
        while (live := _live(live, identity_reader)) and time.monotonic() < deadline:
            time.sleep(min(poll_seconds, max(deadline - time.monotonic(), 0)))
        return live

    remaining = wait_until_gone(signal_live(signal.SIGTERM))
    if remaining:
        remaining = wait_until_gone(signal_live(signal.SIGKILL))
    if remaining:
        pids = ", ".join(str(member.pid) for member in remaining)
        raise RuntimeError(f"recorded processes did not exit: {pids}; ownership record retained")


class ProcessSession:
    """Start, record, wait for, and terminate one dedicated process group."""

    def __init__(
        self,
        record_path: Path,
        *,
        grace_seconds: float = 8.0,
        identity_settle_seconds: float = 0.5,
        poll_seconds: float = 1.0,
        starter: ProcessStarter = subprocess.Popen,
        identity_reader: IdentityReader = read_process_identity,
        group_reader: GroupReader = read_group_members,
        signal_process: ProcessSignaller = os.kill,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.record_path = record_path
        self._sleep = sleep
        self.grace_seconds = grace_seconds
        self.identity_settle_seconds = identity_settle_seconds
        self.poll_seconds = poll_seconds
        self._starter = starter
        self._identity_reader = identity_reader
        self._group_reader = group_reader
        self._signal_process = signal_process
        self._process: Any | None = None
        self._leader: ProcessIdentity | None = None
        self._members: dict[int, ProcessIdentity] = {}
        self._command: list[str] = []

    def run(self, command: list[str], *, cwd: Path | None = None) -> int:
        """Run ``command`` until its leader and every owned member have exited."""
        self.record_path.parent.mkdir(parents=True, exist_ok=True)
        if self.record_path.exists():
            raise RuntimeError(
                f"game session record already exists: {self.record_path}; "
                "inspect it with `erenshor mod launch --recover` before another launch"
            )
        process = self._starter(command, cwd=cwd, start_new_session=True)
        self._process = process
        self._command = list(command)
        if self.identity_settle_seconds > 0:
            self._sleep(self.identity_settle_seconds)
        leader = self._identity_reader(process.pid)
        if leader is None:
            process.terminate()
            process.wait()
            raise RuntimeError(f"cannot record process identity for PID {process.pid}")
        self._leader = leader
        self._members = {leader.pid: leader}
        self._write_record()
        previous_handlers: dict[signal.Signals, Any] = {}

        def request_shutdown(_signum: int, _frame: object) -> None:
            raise KeyboardInterrupt

        for handled_signal in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[handled_signal] = signal.signal(handled_signal, request_shutdown)
        try:
            return self._wait()
        except KeyboardInterrupt:
            self.shutdown()
            raise
        finally:
            for handled_signal, previous_handler in previous_handlers.items():
                signal.signal(handled_signal, previous_handler)
            if self._live_members():
                self.shutdown()
            if not self._live_members():
                self.record_path.unlink(missing_ok=True)

    def _wait(self) -> int:
        process = self._process
        assert process is not None
        while True:
            try:
                return_code = int(process.wait(timeout=self.poll_seconds))
                break
            except subprocess.TimeoutExpired:
                self._adopt_members()
        # The leader can exit before the processes it started, for example a
        # Wine wrapper that is signalled while the game keeps running.
        while self._live_members():
            self._sleep(self.poll_seconds)
        return return_code

    def _adopt_members(self) -> None:
        """Record new members of the group while its leader proves the group is ours."""
        leader = self._leader
        if leader is None or not identity_matches(leader, self._identity_reader(leader.pid)):
            return
        changed = False
        for member in self._group_reader(leader.process_group):
            if member.pid not in self._members:
                self._members[member.pid] = member
                changed = True
        if changed:
            self._write_record()

    def _live_members(self) -> list[ProcessIdentity]:
        if self._process is not None:
            self._process.poll()
        return _live(self._members.values(), self._identity_reader)

    def shutdown(self) -> None:
        """Stop every owned process that is still running."""
        self._adopt_members()
        _terminate(
            list(self._members.values()),
            identity_reader=self._identity_reader,
            signal_process=self._signal_process,
            grace_seconds=self.grace_seconds,
            poll_seconds=min(self.poll_seconds, 0.1),
        )
        if self._process is not None:
            self._process.poll()

    def _write_record(self) -> None:
        payload = {
            "schemaVersion": RECORD_SCHEMA_VERSION,
            "command": self._command,
            "members": [asdict(member) for member in self._members.values()],
        }
        temporary = self.record_path.with_name(f".{self.record_path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.record_path)


def recover_recorded_session(
    record_path: Path,
    *,
    grace_seconds: float = 8.0,
    poll_seconds: float = 0.1,
    identity_reader: IdentityReader = read_process_identity,
    signal_process: ProcessSignaller = os.kill,
) -> bool:
    """Stop the recorded members whose complete identity still matches.

    Returns:
        True if a live member was stopped, False if none was still running.

    Raises:
        RuntimeError: If the record has an unknown schema, or a matching
            member survives SIGKILL. The record is kept in both cases.
    """
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != RECORD_SCHEMA_VERSION:
        raise RuntimeError(
            f"{record_path} has session record schema {payload.get('schemaVersion')!r}, "
            f"expected {RECORD_SCHEMA_VERSION}. Inspect its PIDs with `erenshor mod launch --inspect-pid`, "
            "stop any that are still running, and delete the record."
        )
    members = [ProcessIdentity(**member) for member in payload["members"]]
    live = _live(members, identity_reader)
    if not live:
        record_path.unlink()
        return False
    _terminate(
        live,
        identity_reader=identity_reader,
        signal_process=signal_process,
        grace_seconds=grace_seconds,
        poll_seconds=poll_seconds,
    )
    record_path.unlink()
    return True
