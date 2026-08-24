"""Unit tests for maps CLI command orchestration."""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from erenshor.application.maps import build_info
from erenshor.cli.commands import maps
from erenshor.cli.context import CLIContext
from erenshor.infrastructure.config.schema import Config, MapsConfig, VariantConfig


def _write_project(tmp_path: Path) -> tuple[Path, Path]:
    maps_dir = tmp_path / "maps"
    (maps_dir / "src").mkdir(parents=True)
    (maps_dir / "static" / "db").mkdir(parents=True)
    tiles_dir = maps_dir / "static" / "tiles" / "TestZone" / "-1" / "0"
    tiles_dir.mkdir(parents=True)
    (maps_dir / "static" / "tiles" / "tiles-manifest.json").write_text(
        '{"zoom_levels": {"0": {"tiles": ["/tiles/TestZone/-1/0/0.webp"], "count": 1}}}\n'
    )
    (tiles_dir / "0.webp").write_bytes(b"tile")
    (maps_dir / "node_modules").mkdir()
    (maps_dir / "package.json").write_text("{}\n")
    (maps_dir / "src" / "app.ts").write_text("export const ok = true;\n")
    database_path = tmp_path / "erenshor.sqlite"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO items (id) VALUES (1)")
        connection.commit()
    return maps_dir, database_path


def _ctx(tmp_path: Path, maps_dir: Path, database_path: Path, *, dry_run: bool = False) -> Any:
    variant = VariantConfig(
        name="Main",
        app_id="0",
        unity_project=str(tmp_path / "unity"),
        editor_scripts=str(tmp_path / "editor"),
        game_files=str(tmp_path / "game"),
        database_raw=str(tmp_path / "raw.sqlite"),
        database=str(database_path),
        logs=str(tmp_path / "logs"),
        backups=str(tmp_path / "backups"),
        wiki=str(tmp_path / "wiki"),
        maps=MapsConfig(
            source_dir=str(maps_dir),
            database_dir=str(maps_dir / "static" / "db"),
            build_dir=str(maps_dir / "build"),
        ),
    )
    cli_context = CLIContext(
        config=Config(variants={"main": variant}),
        variant="main",
        dry_run=dry_run,
        repo_root=tmp_path,
    )
    return SimpleNamespace(obj=cli_context)


def test_build_copies_database_runs_verify_prebuild_then_build_and_writes_sidecar(
    tmp_path: Path, monkeypatch: Any
) -> None:
    maps_dir, database_path = _write_project(tmp_path)
    ctx = _ctx(tmp_path, maps_dir, database_path)
    calls: list[list[str]] = []
    environments: list[dict[str, str] | None] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args == ["node", "scripts/generate-item-icons.mjs", "main"]:
            staged_database = maps_dir / "static" / "db" / "erenshor.sqlite"
            assert staged_database.read_bytes() == database_path.read_bytes()
        calls.append(args)
        environments.append(kwargs.get("env"))
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(maps, "_check_pnpm_available", lambda: True)
    monkeypatch.setattr("erenshor.cli.commands.maps.subprocess.run", fake_run)

    maps.build(ctx)

    assert calls == [
        ["node", "scripts/generate-tiles-manifest.js"],
        ["pnpm", "run", "lint"],
        ["pnpm", "run", "check"],
        ["pnpm", "run", "test"],
        ["node", "scripts/generate-og-image.mjs"],
        ["node", "scripts/generate-item-icons.mjs", "main"],
        ["pnpm", "exec", "vite", "build"],
    ]
    assert environments[-1] is not None
    assert environments[-1]["ERENSHOR_MAPS_DATABASE_PATH"] == str(database_path)
    assert (maps_dir / "static" / "db" / "erenshor.sqlite").read_bytes() == database_path.read_bytes()
    expected = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)
    assert build_info.read_build_info(maps_dir / "build") == expected


def test_build_refuses_missing_tiles_before_frontend_checks(tmp_path: Path, monkeypatch: Any) -> None:
    maps_dir, database_path = _write_project(tmp_path)
    tile_dir = maps_dir / "static" / "tiles"
    shutil.rmtree(tile_dir)
    ctx = _ctx(tmp_path, maps_dir, database_path)
    calls: list[list[str]] = []

    def fake_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(maps, "_check_pnpm_available", lambda: True)
    monkeypatch.setattr("erenshor.cli.commands.maps.subprocess.run", fake_run)

    with pytest.raises(typer.Exit):
        maps.build(ctx)

    assert calls == []


def test_build_generates_missing_manifest_from_captured_tiles(tmp_path: Path, monkeypatch: Any) -> None:
    maps_dir, database_path = _write_project(tmp_path)
    manifest_path = maps_dir / "static" / "tiles" / "tiles-manifest.json"
    manifest_path.unlink()
    ctx = _ctx(tmp_path, maps_dir, database_path)
    calls: list[list[str]] = []

    def fake_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args == ["node", "scripts/generate-tiles-manifest.js"]:
            manifest_path.write_text('{"zoom_levels": {"0": {"tiles": ["/tiles/TestZone/-1/0/0.webp"], "count": 1}}}\n')
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(maps, "_check_pnpm_available", lambda: True)
    monkeypatch.setattr("erenshor.cli.commands.maps.subprocess.run", fake_run)

    maps.build(ctx, skip_checks=True)

    assert calls[0] == ["node", "scripts/generate-tiles-manifest.js"]
    assert manifest_path.is_file()


def test_check_runs_only_deterministic_frontend_checks(tmp_path: Path, monkeypatch: Any) -> None:
    maps_dir, database_path = _write_project(tmp_path)
    ctx = _ctx(tmp_path, maps_dir, database_path)
    calls: list[list[str]] = []

    def fake_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(maps, "_check_pnpm_available", lambda: True)
    monkeypatch.setattr("erenshor.cli.commands.maps.subprocess.run", fake_run)

    maps.check(ctx)

    assert calls == [list(command) for command in maps.CHECK_COMMANDS]


def test_build_can_reuse_completed_checks_without_repeating_them(tmp_path: Path, monkeypatch: Any) -> None:
    maps_dir, database_path = _write_project(tmp_path)
    ctx = _ctx(tmp_path, maps_dir, database_path)
    calls: list[list[str]] = []

    def fake_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(maps, "_check_pnpm_available", lambda: True)
    monkeypatch.setattr("erenshor.cli.commands.maps.subprocess.run", fake_run)

    maps.build(ctx, skip_checks=True)

    assert calls == [
        ["node", "scripts/generate-tiles-manifest.js"],
        ["node", "scripts/generate-og-image.mjs"],
        ["node", "scripts/generate-item-icons.mjs", "main"],
        ["pnpm", "exec", "vite", "build"],
    ]


def test_preview_uses_vite_directly_for_fresh_build(tmp_path: Path, monkeypatch: Any) -> None:
    maps_dir, database_path = _write_project(tmp_path)
    build_dir = maps_dir / "build"
    build_dir.mkdir()
    (build_dir / "index.html").write_text("<h1>ok</h1>\n")
    hashes = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)
    build_info.write_build_info(build_dir, hashes)
    ctx = _ctx(tmp_path, maps_dir, database_path)
    calls: list[list[str]] = []

    def fake_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(maps, "_check_pnpm_available", lambda: True)
    monkeypatch.setattr("erenshor.cli.commands.maps.subprocess.run", fake_run)

    maps.preview(ctx, port=4174)

    assert calls == [["pnpm", "exec", "vite", "preview", "--port", "4174"]]


def _ready_to_deploy(tmp_path: Path, monkeypatch: Any, *, dry_run: bool = False) -> tuple[Any, list[list[str]]]:
    """A fresh, stamped build plus credentials, with wrangler calls recorded."""
    maps_dir, database_path = _write_project(tmp_path)
    build_dir = maps_dir / "build"
    build_dir.mkdir()
    (build_dir / "index.html").write_text("<h1>ok</h1>\n")
    hashes = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)
    build_info.write_build_info(build_dir, hashes)
    ctx = _ctx(tmp_path, maps_dir, database_path, dry_run=dry_run)
    calls: list[list[str]] = []

    def fake_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    monkeypatch.setattr(maps, "_check_pnpm_available", lambda: True)
    monkeypatch.setattr("erenshor.cli.commands.maps.subprocess.run", fake_run)
    return ctx, calls


def test_deploy_refuses_blank_tile_provenance(tmp_path: Path, monkeypatch: Any) -> None:
    ctx, calls = _ready_to_deploy(tmp_path, monkeypatch)
    build_dir = Path(ctx.obj.config.variants["main"].maps.build_dir)
    (build_dir / build_info.BUILD_INFO_NAME).write_text('{"code": "abc", "data": "def", "tiles": ""}\n')

    with pytest.raises(typer.Exit):
        maps.deploy(ctx)

    assert calls == []


def test_deploy_publishes_canonical_before_legacy(tmp_path: Path, monkeypatch: Any) -> None:
    # The canonical deploy is the one that repoints the Custom Domain, so it
    # must run first for the cutover to stay reversible.
    ctx, calls = _ready_to_deploy(tmp_path, monkeypatch)

    maps.deploy(ctx)

    assert calls == [
        ["pnpm", "exec", "wrangler", "deploy", "--config", "wrangler.jsonc"],
        ["pnpm", "exec", "wrangler", "deploy", "--config", "wrangler.legacy.jsonc"],
    ]


def test_deploy_site_target_leaves_the_legacy_service_untouched(tmp_path: Path, monkeypatch: Any) -> None:
    ctx, calls = _ready_to_deploy(tmp_path, monkeypatch)

    maps.deploy(ctx, target=maps.DeployTarget.SITE)

    assert calls == [["pnpm", "exec", "wrangler", "deploy", "--config", "wrangler.jsonc"]]


def test_deploy_legacy_target_leaves_the_canonical_service_untouched(tmp_path: Path, monkeypatch: Any) -> None:
    ctx, calls = _ready_to_deploy(tmp_path, monkeypatch)

    maps.deploy(ctx, target=maps.DeployTarget.LEGACY)

    assert calls == [["pnpm", "exec", "wrangler", "deploy", "--config", "wrangler.legacy.jsonc"]]


def test_deploy_stops_before_the_legacy_service_when_the_canonical_one_fails(tmp_path: Path, monkeypatch: Any) -> None:
    ctx, calls = _ready_to_deploy(tmp_path, monkeypatch)

    def failing_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=1)

    monkeypatch.setattr("erenshor.cli.commands.maps.subprocess.run", failing_run)

    with pytest.raises(typer.Exit):
        maps.deploy(ctx)

    assert calls == [["pnpm", "exec", "wrangler", "deploy", "--config", "wrangler.jsonc"]]


def test_deploy_names_a_resumable_command_when_only_the_legacy_service_fails(
    tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    ctx, calls = _ready_to_deploy(tmp_path, monkeypatch)

    def fail_second(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        returncode = 1 if "wrangler.legacy.jsonc" in args else 0
        return subprocess.CompletedProcess(args=args, returncode=returncode)

    monkeypatch.setattr("erenshor.cli.commands.maps.subprocess.run", fail_second)

    with pytest.raises(typer.Exit):
        maps.deploy(ctx)

    assert len(calls) == 2
    # The canonical service is already serving the custom domain at this point,
    # so the operator needs the resume command rather than a rerun of both.
    assert "maps deploy --target legacy" in capsys.readouterr().out


def test_deploy_dry_run_reports_both_services_without_invoking_wrangler(
    tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    ctx, calls = _ready_to_deploy(tmp_path, monkeypatch, dry_run=True)

    maps.deploy(ctx)

    assert calls == []
    output = capsys.readouterr().out
    assert "--config wrangler.jsonc" in output
    assert "--config wrangler.legacy.jsonc" in output


def test_database_link_transaction_restores_prior_target(tmp_path: Path) -> None:
    prior = tmp_path / "prior.sqlite"
    selected = tmp_path / "selected.sqlite"
    prior.touch()
    selected.touch()
    target = tmp_path / "erenshor.sqlite"
    target.symlink_to(prior)
    transaction = maps.DatabaseLinkTransaction(selected, target)
    transaction.install()
    assert target.readlink() == selected
    transaction.restore()
    assert target.readlink() == prior


def test_database_link_transaction_removes_initially_absent_link(tmp_path: Path) -> None:
    selected = tmp_path / "selected.sqlite"
    selected.touch()
    target = tmp_path / "erenshor.sqlite"
    transaction = maps.DatabaseLinkTransaction(selected, target)
    transaction.install()
    transaction.restore()
    assert not target.exists() and not target.is_symlink()


@pytest.mark.parametrize("kind", ["file", "directory"])
def test_database_link_transaction_refuses_unmanaged_path(tmp_path: Path, kind: str) -> None:
    selected = tmp_path / "selected.sqlite"
    selected.touch()
    target = tmp_path / "erenshor.sqlite"
    target.touch() if kind == "file" else target.mkdir()
    with pytest.raises(RuntimeError, match=str(target)):
        maps.DatabaseLinkTransaction(selected, target).install()
    assert not target.is_symlink()


def test_database_link_transaction_refuses_concurrent_replacement(tmp_path: Path) -> None:
    selected = tmp_path / "selected.sqlite"
    replacement = tmp_path / "replacement.sqlite"
    selected.touch()
    replacement.touch()
    target = tmp_path / "erenshor.sqlite"
    transaction = maps.DatabaseLinkTransaction(selected, target)
    transaction.install()
    target.unlink()
    target.symlink_to(replacement)
    with pytest.raises(RuntimeError, match="changed concurrently"):
        transaction.restore()
    assert target.readlink() == replacement


class _FakeDevProcess:
    def __init__(self, outcome: int | BaseException) -> None:
        self.pid = 73
        self.outcome = outcome
        self.returncode: int | None = None

    def wait(self, timeout: float | None = None) -> int:
        if isinstance(self.outcome, BaseException) and timeout is None:
            outcome, self.outcome = self.outcome, 0
            raise outcome
        self.returncode = int(self.outcome)
        return self.returncode

    def poll(self) -> int | None:
        return self.returncode


def _run_dev_lifecycle(
    tmp_path: Path, monkeypatch: Any, outcome: int | BaseException
) -> tuple[Path, Path, list[tuple[int, int]]]:
    maps_dir, database_path = _write_project(tmp_path)
    ctx = _ctx(tmp_path, maps_dir, database_path)
    target = maps_dir / "static/db/erenshor.sqlite"
    prior = tmp_path / "prior.sqlite"
    prior.touch()
    target.symlink_to(prior)
    process = _FakeDevProcess(outcome)
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(maps, "_check_pnpm_available", lambda: True)
    monkeypatch.setattr(maps, "_check_node_modules", lambda _path: True)
    monkeypatch.setattr(maps.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(maps.signal, "signal", lambda *_args: maps.signal.SIG_DFL)

    def killpg(pid: int, sig: int) -> None:
        signals.append((pid, sig))
        process.returncode = -sig

    monkeypatch.setattr(maps.os, "killpg", killpg)
    try:
        maps.dev(ctx)
    except typer.Exit:
        if not isinstance(outcome, int) or outcome == 0:
            raise
    return target, prior, signals


def test_maps_dev_restores_link_after_normal_exit(tmp_path: Path, monkeypatch: Any) -> None:
    target, prior, signals = _run_dev_lifecycle(tmp_path, monkeypatch, 0)
    assert target.readlink() == prior
    assert signals == []


def test_maps_dev_restores_link_after_runtime_failure(tmp_path: Path, monkeypatch: Any) -> None:
    target, prior, _signals = _run_dev_lifecycle(tmp_path, monkeypatch, 7)
    assert target.readlink() == prior


def test_maps_dev_terminates_child_and_restores_link_on_interruption(tmp_path: Path, monkeypatch: Any) -> None:
    target, prior, signals = _run_dev_lifecycle(tmp_path, monkeypatch, KeyboardInterrupt())
    assert target.readlink() == prior
    assert signals == [(73, maps.signal.SIGTERM)]
