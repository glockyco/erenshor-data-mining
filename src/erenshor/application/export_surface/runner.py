"""Run the ExportSurface field-coverage checker and parse its findings.

The C# tool (src/tools/ExportSurface) reads the shipped Assembly-CSharp.dll
metadata via Mono.Cecil and diffs the public instance field surface of each
in-scope game type against field-coverage.json. This module wraps the dotnet
build+invoke so all workflow commands go through ``uv run`` (AGENTS.md):
``dotnet`` appears only inside this subprocess, mirroring the code-facts runner.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

TOOL_PROJECT = Path("src") / "tools" / "ExportSurface"


def run_field_coverage(repo_root: Path, assembly: Path, manifest: Path) -> list[dict[str, Any]]:
    """Build + invoke the ExportSurface checker; return parsed findings.

    Exit 0 = clean (no findings); exit 1 = drift (findings in stdout);
    exit 2 = usage/IO error (raises RuntimeError). A missing assembly or
    manifest raises FileNotFoundError. Mirrors code_facts/runner.py's
    subprocess pattern but tolerates exit 1 because the C# tool emits
    findings on stdout in that case.
    """
    if not assembly.exists():
        raise FileNotFoundError(f"shipped game assembly not found: {assembly}")
    if not manifest.exists():
        raise FileNotFoundError(f"field-coverage manifest not found: {manifest}")

    dotnet = shutil.which("dotnet")
    if dotnet is None:
        raise RuntimeError("dotnet SDK not found on PATH")

    project = repo_root / TOOL_PROJECT
    subprocess.run(
        [dotnet, "build", str(project), "-c", "Release"],
        check=True,
        capture_output=True,
        text=True,
    )
    proc = subprocess.run(
        [
            dotnet,
            "run",
            "-c",
            "Release",
            "--no-build",
            "--project",
            str(project),
            "--",
            str(assembly),
            str(manifest),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"ExportSurface failed (exit {proc.returncode}).\n"
            f"stderr: {proc.stderr.strip()}\n"
            f"output: {proc.stdout.strip()}"
        )
    payload: dict[str, Any] = json.loads(proc.stdout)
    findings: list[dict[str, Any]] = payload["findings"]
    return findings
