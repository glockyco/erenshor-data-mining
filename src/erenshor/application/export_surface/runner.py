"""Run the ExportSurface field-coverage checker and parse its findings.

The C# tool (src/tools/ExportSurface) reads the shipped Assembly-CSharp.dll
metadata via Mono.Cecil and diffs the public instance field surface of each
in-scope game type against field-coverage.json. This module wraps the dotnet
build+invoke so all workflow commands go through ``uv run`` (AGENTS.md):
``dotnet`` appears only inside this subprocess, mirroring the code-facts runner.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

TOOL_PROJECT = Path("src") / "tools" / "ExportSurface"

# Generic Unity wrapper types have no fixed data surface — listeners that
# declare these as <T> are not in the field-coverage manifest (spec §5).
GENERIC_UNITY_TYPES = {"GameObject", "Object", "NullScriptableObject"}

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


def seed_entries(
    findings: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, str | None]]]:
    """Turn unclassified findings into placeholder manifest entries.

    Only unclassified findings (fields present in code but absent from the
    manifest) produce seed entries — stale and retype findings are about
    existing entries, not new fields. Each entry gets an empty status so the
    gate fails until a human classifies it (captured/ignored).
    """
    fields: dict[str, dict[str, dict[str, str | None]]] = {}
    for f in findings:
        if f["kind"] != "unclassified":
            continue
        type_name = f["script_type"]
        field_name = f["field_name"]
        fields.setdefault(type_name, {})[field_name] = {
            "type": f["actual"],
            "status": "",
            "by": None,
            "reason": None,
        }
    return fields


def write_manifest(
    path: Path,
    tracks_build: str,
    types: list[str],
    fields: dict[str, dict[str, dict[str, str | None]]],
) -> None:
    """Write the manifest in sorted, compact form (one field entry per line).

    Types and fields are sorted alphabetically at both levels. Each field
    entry is serialized compact on a single line so diffs stay granular and
    reviewable (spec §4). This is the one place the manifest is written —
    the C# tool stays read-only.
    """
    sorted_types = sorted(types)
    sorted_fields = {t: {fn: fields[t][fn] for fn in sorted(fields.get(t, {}))} for t in sorted(fields)}
    manifest = {"tracks_build": tracks_build, "types": sorted_types, "fields": sorted_fields}
    text = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(text + "\n")
