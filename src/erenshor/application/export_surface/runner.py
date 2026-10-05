"""Run the ExportSurface field-coverage checker and parse its findings.

The C# tool (src/tools/ExportSurface) reads the shipped Assembly-CSharp.dll
metadata via Mono.Cecil and diffs the public instance field surface of each
in-scope game type against field-coverage.json. This module wraps the dotnet
build+invoke so all workflow commands go through ``uv run``:
``dotnet`` appears only inside this subprocess, mirroring the code-facts runner.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from erenshor.application.dotnet_tool import run_dotnet_tool

TOOL_PROJECT = Path("src") / "tools" / "ExportSurface"

# Generic Unity wrapper types have no fixed data surface — listeners that
# declare these as <T> are not in the field-coverage manifest (spec §5).
GENERIC_UNITY_TYPES = {"GameObject", "Object", "NullScriptableObject", "MonoBehaviour"}

# Matches the <T> generic argument of IAssetScanListener<T> in listener
# declarations. Regex over declarations only — never parses method bodies
# (spec §5). Catches "added a listener, forgot the manifest."
_LISTENER_RE = re.compile(r"IAssetScanListener<(\w+)>")


def missing_listener_types(listener_dir: Path, declared_types: set[str]) -> list[str]:
    """Return game-data listener <T> types not present in declared_types.

    Scans every *.cs in listener_dir for IAssetScanListener<T> declarations
    (invariant 3, spec §5), excluding generic Unity wrappers that have no
    fixed data surface. Returns a sorted list of missing type names.
    """
    found: set[str] = set()
    for cs in listener_dir.glob("*.cs"):
        for m in _LISTENER_RE.finditer(cs.read_text(encoding="utf-8")):
            if m.group(1) not in GENERIC_UNITY_TYPES:
                found.add(m.group(1))
    return sorted(found - declared_types)


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

    proc = run_dotnet_tool(repo_root / TOOL_PROJECT, [str(assembly), str(manifest)])
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"ExportSurface failed (exit {proc.returncode}).\n"
            f"stderr: {proc.stderr.strip()}\n"
            f"output: {proc.stdout.strip()}"
        )
    payload: dict[str, Any] = json.loads(proc.stdout)
    findings: list[dict[str, Any]] = payload["findings"]
    return findings
