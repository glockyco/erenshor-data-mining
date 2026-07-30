"""Run the CodeFacts analyzer and persist results into the raw database."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from loguru import logger

TOOL_PROJECT = Path("src") / "tools" / "CodeFacts"


def run_tool(repo_root: Path, assembly: Path, variant: str | None = None) -> dict[str, Any]:
    """Invoke the analyzer; raise on any failure (fail fast, no fallbacks)."""
    if not assembly.exists():
        raise FileNotFoundError(f"shipped game assembly not found: {assembly}")
    project = repo_root / TOOL_PROJECT
    specs = project / "specs" / "erenshor-facts.json"
    if not specs.exists():
        raise FileNotFoundError(f"fact specs not found: {specs}")
    subprocess.run(
        ["dotnet", "build", str(project), "-c", "Release"],
        check=True,
        capture_output=True,
        text=True,
    )
    command = [
        "dotnet",
        "run",
        "-c",
        "Release",
        "--no-build",
        "--project",
        str(project),
        "--",
        str(assembly),
        str(specs),
    ]
    if variant is not None:
        command.extend(["--variant", variant])
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"CodeFacts analyzer failed (exit {proc.returncode}).\n"
            f"stderr: {proc.stderr.strip()}\n"
            f"output: {proc.stdout.strip()}\n"
            "A binding failure means the game code changed shape: re-derive the "
            "affected fact spec in src/tools/CodeFacts/specs/erenshor-facts.json."
        )
    return cast("dict[str, Any]", json.loads(proc.stdout))


def write_code_facts(
    raw_db_path: Path,
    payload: dict[str, Any],
    assembly_sha256: str,
    game_build_id: str | None,
    game_build_updated_at: str | None,
) -> int:
    """Replace the writer-owned `code_facts` tables with the analyzer payload.

    Drops and recreates only ``code_facts`` and ``code_facts_meta``; all other
    raw tables (owned by the Unity export) are left untouched.

    ``game_build_id`` is the installed Steam build the shipped assembly came
    from. It is the only precise, publicly verifiable identifier for a game
    version (Erenshor ships coarse version strings), so it rides along with the
    extraction metadata and becomes the provenance shown by downstream
    consumers. ``game_build_updated_at`` dates that build rather than this run,
    so re-extracting without a game update never advances it.
    """
    rows: list[tuple[str, str, str, str]] = []
    for fact in payload["facts"]:
        if fact["mode"] == "extract":
            for key, value in fact["values"].items():
                rows.append((fact["id"], key, value, "text"))
        else:
            rows.append((fact["id"], "ok", "true" if fact["ok"] else "false", "bool"))

    with sqlite3.connect(raw_db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS code_facts")
        conn.execute("DROP TABLE IF EXISTS code_facts_meta")
        conn.execute(
            "CREATE TABLE code_facts ("
            "fact_id TEXT NOT NULL, key TEXT NOT NULL, "
            "value TEXT NOT NULL, value_type TEXT NOT NULL, "
            "PRIMARY KEY (fact_id, key))"
        )
        conn.execute(
            "CREATE TABLE code_facts_meta ("
            "assembly_sha256 TEXT NOT NULL, extracted_at TEXT NOT NULL, "
            "game_build_id TEXT, game_build_updated_at TEXT)"
        )
        conn.executemany("INSERT INTO code_facts VALUES (?, ?, ?, ?)", rows)
        conn.execute(
            "INSERT INTO code_facts_meta VALUES (?, ?, ?, ?)",
            (assembly_sha256, datetime.now(UTC).isoformat(), game_build_id, game_build_updated_at),
        )
    logger.info(f"code_facts written: {len(rows)} rows (game build {game_build_id or 'unknown'})")
    return len(rows)


def extract_code_facts(
    repo_root: Path,
    assembly: Path,
    raw_db_path: Path,
    variant: str | None = None,
    game_build_id: str | None = None,
    game_build_updated_at: str | None = None,
) -> int:
    """Run the analyzer against ``assembly`` and persist the facts into the raw DB."""
    payload = run_tool(repo_root, assembly, variant)
    sha = hashlib.sha256(assembly.read_bytes()).hexdigest()
    return write_code_facts(
        raw_db_path,
        payload,
        assembly_sha256=sha,
        game_build_id=game_build_id,
        game_build_updated_at=game_build_updated_at,
    )
