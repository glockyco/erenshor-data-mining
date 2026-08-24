from __future__ import annotations

import json
import signal
import subprocess
from pathlib import Path

import pytest

from erenshor.application import process_session


class FakeProcess:
    def __init__(self, pid: int = 41, *, interrupt: bool = False, stubborn: bool = False) -> None:
        self.pid = pid
        self.returncode: int | None = None
        self.interrupt = interrupt
        self.stubborn = stubborn
        self.wait_calls = 0
        self.terminated = False

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.interrupt and timeout is None and self.wait_calls == 1:
            raise KeyboardInterrupt
        if self.stubborn and timeout is not None and not self.terminated:
            raise subprocess.TimeoutExpired("fake", timeout)
        self.returncode = 0
        return 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -signal.SIGTERM


def identity(pid: int = 41) -> process_session.ProcessIdentity:
    return process_session.ProcessIdentity(pid, pid, "start-token", "/usr/bin/fake")


def test_reads_macos_process_identity_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        process_session.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, " 82125  Mon Aug 24 20:50:58 2026 /usr/bin/perl\n", ""
        ),
    )
    assert process_session.read_process_identity(82125) == process_session.ProcessIdentity(
        82125, 82125, "Mon Aug 24 20:50:58 2026", "/usr/bin/perl"
    )


def test_normal_completion_records_atomically_then_removes_record(tmp_path: Path) -> None:
    process = FakeProcess()
    observed: list[Path] = []

    def start(*_args: object, **_kwargs: object) -> FakeProcess:
        observed.append(tmp_path / "session.json")
        return process

    session = process_session.ProcessSession(
        tmp_path / "session.json", starter=start, identity_reader=lambda _pid: identity()
    )
    assert session.run(["fake"]) == 0
    assert not (tmp_path / "session.json").exists()
    assert not list(tmp_path.glob("*.tmp"))
    assert observed


def test_interruption_terminates_owned_group(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess(interrupt=True)
    signals: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(process_session.os, "killpg", lambda pgid, sig: signals.append((pgid, sig)))
    session = process_session.ProcessSession(
        tmp_path / "session.json",
        starter=lambda *_args, **_kwargs: process,
        identity_reader=lambda _pid: identity(),
    )
    assert session.run(["fake"]) == 130
    assert signals == [(41, signal.SIGTERM)]
    assert not (tmp_path / "session.json").exists()


def test_stubborn_owned_process_is_forced_after_grace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess(interrupt=True, stubborn=True)
    signals: list[tuple[int, signal.Signals]] = []

    def killpg(pgid: int, sig: signal.Signals) -> None:
        signals.append((pgid, sig))
        if sig == signal.SIGKILL:
            process.terminated = True

    monkeypatch.setattr(process_session.os, "killpg", killpg)
    session = process_session.ProcessSession(
        tmp_path / "session.json",
        grace_seconds=0,
        starter=lambda *_args, **_kwargs: process,
        identity_reader=lambda _pid: identity(),
    )
    assert session.run(["fake"]) == 130
    assert signals == [(41, signal.SIGTERM), (41, signal.SIGKILL)]


def test_recovery_refuses_pid_identity_mismatch(tmp_path: Path) -> None:
    record = tmp_path / "session.json"
    record.write_text(
        json.dumps({"identity": {"pid": 41, "process_group": 41, "started_at": "old", "executable": "old"}}),
        encoding="utf-8",
    )
    signaled: list[object] = []
    with pytest.raises(RuntimeError, match=r"identity mismatch.*not signaled"):
        process_session.recover_recorded_session(
            record,
            identity_reader=lambda _pid: identity(),
            signal_process_group=lambda *args: signaled.append(args),
        )
    assert signaled == []


def test_recovery_signals_exact_recorded_identity(tmp_path: Path) -> None:
    expected = identity()
    record = tmp_path / "session.json"
    record.write_text(
        json.dumps(
            {
                "identity": {
                    "pid": expected.pid,
                    "process_group": expected.process_group,
                    "started_at": expected.started_at,
                    "executable": expected.executable,
                }
            }
        ),
        encoding="utf-8",
    )
    signals: list[tuple[int, signal.Signals]] = []
    assert process_session.recover_recorded_session(
        record,
        identity_reader=lambda _pid: expected,
        signal_process_group=lambda pgid, sig: signals.append((pgid, sig)),
    )
    assert signals == [(41, signal.SIGTERM)]
