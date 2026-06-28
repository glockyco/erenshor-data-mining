"""Unit tests for maps CLI command orchestration."""

from __future__ import annotations

import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from erenshor.application.maps import build_info
from erenshor.cli.commands import maps
from erenshor.cli.context import CLIContext
from erenshor.infrastructure.config.schema import Config, MapsConfig, VariantConfig


def _write_project(tmp_path: Path) -> tuple[Path, Path]:
    maps_dir = tmp_path / "maps"
    (maps_dir / "src").mkdir(parents=True)
    (maps_dir / "static" / "db").mkdir(parents=True)
    (maps_dir / "node_modules").mkdir()
    (maps_dir / "package.json").write_text("{}\n")
    (maps_dir / "src" / "app.ts").write_text("export const ok = true;\n")
    database_path = tmp_path / "erenshor.sqlite"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO items (id) VALUES (1)")
        connection.commit()
    return maps_dir, database_path


def _ctx(tmp_path: Path, maps_dir: Path, database_path: Path, *, dry_run: bool = False) -> SimpleNamespace:
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

    def fake_run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(maps, "_check_pnpm_available", lambda: True)
    monkeypatch.setattr(maps.subprocess, "run", fake_run)

    maps.build(ctx)

    assert calls == [
        ["pnpm", "run", "lint"],
        ["pnpm", "run", "check"],
        ["pnpm", "run", "test"],
        ["uv", "run", "erenshor", "-V", "main", "mod", "publish"],
        ["node", "scripts/generate-tiles-manifest.js"],
        ["node", "scripts/generate-og-image.mjs"],
        ["node", "scripts/generate-item-icons.mjs", "main"],
        ["pnpm", "exec", "vite", "build"],
    ]
    assert (maps_dir / "static" / "db" / "erenshor.sqlite").read_bytes() == database_path.read_bytes()
    expected = build_info.compute_input_hashes(maps_source_dir=maps_dir, database_path=database_path)
    assert build_info.read_build_info(maps_dir / "build") == expected


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
    monkeypatch.setattr(maps.subprocess, "run", fake_run)

    maps.preview(ctx, port=4174)

    assert calls == [["pnpm", "exec", "vite", "preview", "--port", "4174"]]


def test_deploy_uses_wrangler_directly_for_fresh_build(tmp_path: Path, monkeypatch: Any) -> None:
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

    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    monkeypatch.setattr(maps, "_check_pnpm_available", lambda: True)
    monkeypatch.setattr(maps.subprocess, "run", fake_run)

    maps.deploy(ctx)

    assert calls == [["pnpm", "exec", "wrangler", "deploy"]]
