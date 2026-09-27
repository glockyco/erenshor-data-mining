from __future__ import annotations

import json
import signal
import subprocess
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

import pytest

from erenshor.application import process_session
from erenshor.application.process_session import ProcessIdentity

WRAPPER = ProcessIdentity(41, 41, "Sun Sep 27 19:04:19 2026", "/Applications/CrossOver.app/winewrapper.exe")
GAME = ProcessIdentity(49, 41, "Sun Sep 27 19:04:19 2026", r"C:\Games\Erenshor\Erenshor.exe")


class World:
    """Fake operating system: live processes, group membership, and signals."""

    def __init__(self, *live: ProcessIdentity, stubborn: frozenset[int] = frozenset()) -> None:
        self.live = {identity.pid: identity for identity in live}
        self.stubborn = stubborn
        self.signals: list[tuple[int, signal.Signals]] = []

    def identity(self, pid: int) -> ProcessIdentity | None:
        return self.live.get(pid)

    def group(self, process_group: int) -> list[ProcessIdentity]:
        return [identity for identity in self.live.values() if identity.process_group == process_group]

    def signal(self, pid: int, sig: signal.Signals) -> None:
        self.signals.append((pid, sig))
        if sig == signal.SIGKILL or pid not in self.stubborn:
            self.live.pop(pid, None)


class FakeProcess:
    """A group leader that exits when the world no longer lists it."""

    def __init__(self, world: World, *, interrupt_after: int | None = None) -> None:
        self.pid = WRAPPER.pid
        self.world = world
        self.interrupt_after = interrupt_after
        self.waits = 0

    def wait(self, timeout: float | None = None) -> int:
        self.waits += 1
        if self.interrupt_after is not None and self.waits > self.interrupt_after:
            raise KeyboardInterrupt
        if self.pid in self.world.live:
            raise subprocess.TimeoutExpired("fake", timeout or 0)
        return 0

    def poll(self) -> int | None:
        return None if self.pid in self.world.live else 0

    def terminate(self) -> None:
        self.world.live.pop(self.pid, None)


def _session(
    tmp_path: Path, world: World, process: FakeProcess, *, sleep: Callable[[float], None] = lambda _s: None
) -> process_session.ProcessSession:
    return process_session.ProcessSession(
        tmp_path / "session.json",
        identity_settle_seconds=0,
        poll_seconds=0,
        grace_seconds=0,
        sleep=sleep,
        starter=lambda *_args, **_kwargs: process,
        identity_reader=world.identity,
        group_reader=world.group,
        signal_process=world.signal,
    )


def test_reads_macos_process_identity_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        process_session.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, " 82125 82125 Mon Aug 24 20:50:58 2026 /usr/bin/perl\n", ""
        ),
    )
    assert process_session.read_process_identity(82125) == ProcessIdentity(
        82125, 82125, "Mon Aug 24 20:50:58 2026", "/usr/bin/perl"
    )


def test_normalizes_crossover_exec_wrapper_command(monkeypatch: pytest.MonkeyPatch) -> None:
    stable = "/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/lib/wine/winewrapper.exe --wait-children"
    monkeypatch.setattr(
        process_session.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, f" 41 41 Mon Aug 24 20:50:58 2026 /tmp/wineloader {stable}\n", ""
        ),
    )
    assert process_session.read_process_identity(41) == ProcessIdentity(41, 41, "Mon Aug 24 20:50:58 2026", stable)


def test_group_members_are_read_from_one_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    listing = (
        " 41 41 Sun Sep 27 19:04:19 2026 /Applications/CrossOver.app/winewrapper.exe\n"
        " 49 41 Sun Sep 27 19:04:19 2026 C:\\Games\\Erenshor\\Erenshor.exe\n"
        " 52 52 Sun Sep 27 19:04:19 2026 C:\\Games\\Erenshor\\UnityCrashHandler64.exe\n"
    )
    monkeypatch.setattr(
        process_session.subprocess, "run", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, listing, "")
    )
    assert process_session.read_group_members(41) == [WRAPPER, GAME]


def test_game_that_outlives_its_wrapper_is_stopped_on_interruption(tmp_path: Path) -> None:
    """Stopping the launch used to kill only the wrapper and leave the game running."""
    world = World(WRAPPER, GAME)
    process = FakeProcess(world)
    original_wait = process.wait

    def wait(timeout: float | None = None) -> int:
        if process.waits == 1:
            world.live.pop(WRAPPER.pid)  # the wrapper exits after the game was adopted
        return original_wait(timeout)

    def interrupted_sleep(_seconds: float) -> None:
        raise KeyboardInterrupt

    process.wait = wait  # type: ignore[method-assign]
    session = _session(tmp_path, world, process, sleep=interrupted_sleep)

    with pytest.raises(KeyboardInterrupt):
        session.run(["cxstart"])

    assert world.signals == [(GAME.pid, signal.SIGTERM)]
    assert not (tmp_path / "session.json").exists()


def test_normal_completion_removes_the_record(tmp_path: Path) -> None:
    world = World(WRAPPER)
    process = FakeProcess(world)
    session = _session(tmp_path, world, process)
    original_wait = process.wait

    def wait(timeout: float | None = None) -> int:
        record = json.loads((tmp_path / "session.json").read_text())
        assert record["members"] == [asdict(WRAPPER)]
        world.live.clear()
        return original_wait(timeout)

    process.wait = wait  # type: ignore[method-assign]
    assert session.run(["cxstart"]) == 0
    assert not (tmp_path / "session.json").exists()
    assert not list(tmp_path.glob("*.tmp"))
    assert world.signals == []


def test_adopted_members_are_recorded(tmp_path: Path) -> None:
    world = World(WRAPPER, GAME)
    process = FakeProcess(world)
    session = _session(tmp_path, world, process)
    recorded: list[list[dict[str, object]]] = []
    original_wait = process.wait

    def wait(timeout: float | None = None) -> int:
        if process.waits == 1:
            recorded.append(json.loads((tmp_path / "session.json").read_text())["members"])
            world.live.clear()
        return original_wait(timeout)

    process.wait = wait  # type: ignore[method-assign]
    session.run(["cxstart"])
    assert recorded == [[asdict(WRAPPER), asdict(GAME)]]


def test_stubborn_member_is_forced_after_grace(tmp_path: Path) -> None:
    world = World(WRAPPER, GAME, stubborn=frozenset({GAME.pid}))
    process = FakeProcess(world, interrupt_after=1)

    with pytest.raises(KeyboardInterrupt):
        _session(tmp_path, world, process).run(["cxstart"])

    assert (GAME.pid, signal.SIGTERM) in world.signals
    assert (GAME.pid, signal.SIGKILL) in world.signals
    assert (WRAPPER.pid, signal.SIGKILL) not in world.signals


def test_launch_refuses_to_overwrite_existing_session_record(tmp_path: Path) -> None:
    record = tmp_path / "session.json"
    record.write_text("{}", encoding="utf-8")
    session = process_session.ProcessSession(
        record,
        starter=lambda *_args, **_kwargs: pytest.fail("must not start another process"),
    )
    with pytest.raises(RuntimeError, match=r"record already exists.*--recover"):
        session.run(["fake"])


def _record(tmp_path: Path, *members: ProcessIdentity) -> Path:
    record = tmp_path / "session.json"
    payload = {"schemaVersion": 2, "command": ["cxstart"], "members": [asdict(member) for member in members]}
    record.write_text(json.dumps(payload), encoding="utf-8")
    return record


def test_recovery_stops_a_game_whose_wrapper_is_gone(tmp_path: Path) -> None:
    world = World(GAME)
    record = _record(tmp_path, WRAPPER, GAME)

    assert process_session.recover_recorded_session(
        record, grace_seconds=0, identity_reader=world.identity, signal_process=world.signal
    )
    assert world.signals == [(GAME.pid, signal.SIGTERM)]
    assert not record.exists()


def test_recovery_never_signals_a_reused_pid(tmp_path: Path) -> None:
    stranger = ProcessIdentity(GAME.pid, 700, "Mon Sep 28 08:00:00 2026", "/usr/bin/stranger")
    world = World(stranger)
    record = _record(tmp_path, WRAPPER, GAME)

    assert not process_session.recover_recorded_session(
        record, identity_reader=world.identity, signal_process=world.signal
    )
    assert world.signals == []
    assert not record.exists()


def test_recovery_forces_a_member_that_ignores_sigterm(tmp_path: Path) -> None:
    world = World(GAME, stubborn=frozenset({GAME.pid}))
    record = _record(tmp_path, GAME)

    assert process_session.recover_recorded_session(
        record, grace_seconds=0, identity_reader=world.identity, signal_process=world.signal
    )
    assert world.signals == [(GAME.pid, signal.SIGTERM), (GAME.pid, signal.SIGKILL)]


def test_recovery_refuses_a_record_of_another_schema(tmp_path: Path) -> None:
    record = tmp_path / "session.json"
    record.write_text(json.dumps({"identity": asdict(GAME)}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="--inspect-pid"):
        process_session.recover_recorded_session(record, identity_reader=lambda _pid: pytest.fail("read"))
    assert record.exists()
