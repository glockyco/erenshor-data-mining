"""Export field-coverage precondition check.

Pre-export gate that enforces the three invariants (spec §5):
1. Completeness - every public instance field of each in-scope type is classified.
2. No staleness/retype - manifest entries match the actual field surface.
3. Listener-type coverage - every IAssetScanListener<T> declaration has T in the
   manifest's declared type set.

Invariants 1-2 are delegated to the C# ExportSurface checker (via the runner);
invariant 3 is a Python regex over listener declarations. Both are aggregated
into one pass/fail before Unity compiles, so a referenced removal surfaces as
a friendly envelope instead of a raw CS1061.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from erenshor.application.export_surface.runner import missing_listener_types, run_field_coverage

from ..base import PreconditionResult

LISTENER_DIR = Path("src/Assets/Editor/ExportSystem/AssetScanner/Listener")
MANIFEST_PATH = Path("src/tools/ExportSurface/field-coverage.json")


def export_field_coverage_current(context: dict[str, Any]) -> PreconditionResult:
    """Run the field-coverage gate before export.

    Aggregates the C# checker findings (invariants 1-2) and the listener-type
    coverage check (invariant 3) into a single pass/fail. Always strict
    (spec §7): a missing DLL or manifest fails the gate.
    """
    repo_root = Path(context["repo_root"])
    game_dir = Path(context["game_dir"])
    dll = game_dir / "Erenshor_Data" / "Managed" / "Assembly-CSharp.dll"
    manifest = repo_root / MANIFEST_PATH
    listener_dir = repo_root / LISTENER_DIR

    if not dll.exists():
        return PreconditionResult(
            passed=False,
            check_name="export_field_coverage_current",
            message="shipped Assembly-CSharp.dll not found",
            detail=f"Expected: {dll}\nThe field-coverage gate requires the shipped game binary.",
        )
    if not manifest.exists():
        return PreconditionResult(
            passed=False,
            check_name="export_field_coverage_current",
            message="field-coverage manifest not found",
            detail=f"Missing: {manifest}\n"
            "Run the reconciliation step to seed src/tools/ExportSurface/field-coverage.json.",
        )

    manifest_data = json.loads(manifest.read_text())
    declared_types = set(manifest_data["types"])

    # Invariants 1-2: C# checker (DLL metadata vs manifest).
    field_findings = run_field_coverage(repo_root, dll, manifest)

    # Invariant 3: listener-type coverage (regex over declarations).
    listener_findings = missing_listener_types(listener_dir, declared_types)

    if not field_findings and not listener_findings:
        return PreconditionResult(
            passed=True,
            check_name="export_field_coverage_current",
            message="export field surface matches the manifest",
        )

    lines: list[str] = []
    if field_findings:
        lines.append(f"{len(field_findings)} field-coverage finding(s):")
        for f in field_findings:
            lines.append(
                f"  {f['script_type']}.{f['field_name']} - {f['kind']}"
                + (
                    f" (expected {f['expected']}, actual {f['actual']})"
                    if f.get("expected")
                    else f" ({f.get('actual', '')})"
                )
            )
    if listener_findings:
        lines.append(f"{len(listener_findings)} listener type(s) not in manifest:")
        for t in listener_findings:
            lines.append(f"  {t}")
    lines.append(
        "Classify findings in src/tools/ExportSurface/field-coverage.json "
        "(captured/ignored) or add the missing type to the manifest's types list."
    )

    return PreconditionResult(
        passed=False,
        check_name="export_field_coverage_current",
        message="export field-coverage gate failed",
        detail="\n".join(lines),
    )
