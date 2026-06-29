"""Integration tests for the ExportSurface field-coverage checker.

Verifies the C# tool (built + invoked through the Python runner) reports each
finding kind correctly against the real playtest assembly. Mirrors the
test_code_facts_real.py pattern: skip when the shipped DLL or dotnet SDK is
absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DLL = REPO_ROOT / "variants" / "playtest" / "game" / "Erenshor_Data" / "Managed" / "Assembly-CSharp.dll"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DLL.exists(), reason="playtest shipped DLL not present"),
]


def test_reports_each_finding_kind(tmp_path: Path) -> None:
    """A manifest with a bogus stale entry yields unclassified + stale."""
    from erenshor.application.export_surface.runner import run_field_coverage

    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps(
            {
                "tracks_build": "test",
                "types": ["LootTable"],
                "fields": {
                    "LootTable": {
                        # A field that does not exist on LootTable -> stale.
                        "DefinitelyGoneField": {
                            "type": "System.Int32",
                            "status": "ignored",
                            "reason": "test stale",
                        },
                    }
                },
            }
        )
    )

    findings = run_field_coverage(REPO_ROOT, DLL, manifest)
    kinds = {f["kind"] for f in findings}
    # Real LootTable fields are absent from the manifest -> unclassified.
    assert "unclassified" in kinds
    # The bogus field is not on the type -> stale.
    assert "stale" in kinds


def test_retype_detected(tmp_path: Path) -> None:
    """A manifest entry with the wrong type yields a retype finding."""
    from erenshor.application.export_surface.runner import run_field_coverage

    # First discover a real LootTable field's type.
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps(
            {
                "tracks_build": "test",
                "types": ["LootTable"],
                "fields": {"LootTable": {}},
            }
        )
    )
    findings = run_field_coverage(REPO_ROOT, DLL, manifest)
    # Pick the first real field and feed it a deliberately wrong type.
    real_field = findings[0]
    assert real_field["kind"] == "unclassified"
    assert real_field["actual"] is not None

    manifest.write_text(
        json.dumps(
            {
                "tracks_build": "test",
                "types": ["LootTable"],
                "fields": {
                    "LootTable": {
                        real_field["field_name"]: {
                            "type": "Definitely.Wrong.Type",
                            "status": "captured",
                            "by": "test",
                        },
                    }
                },
            }
        )
    )
    findings = run_field_coverage(REPO_ROOT, DLL, manifest)
    retypes = [f for f in findings if f["kind"] == "retype"]
    assert len(retypes) >= 1
    assert retypes[0]["field_name"] == real_field["field_name"]
    assert retypes[0]["expected"] == "Definitely.Wrong.Type"
    assert retypes[0]["actual"] == real_field["actual"]


def test_clean_manifest_passes(tmp_path: Path) -> None:
    """A manifest seeded from the real DLL (all fields, valid status) passes."""
    from erenshor.application.export_surface.runner import run_field_coverage

    manifest = tmp_path / "m.json"

    # Add LootTable to types with an empty fields dict: every real field is
    # absent from the manifest -> unclassified.
    manifest.write_text(
        json.dumps(
            {
                "tracks_build": "test",
                "types": ["LootTable"],
                "fields": {"LootTable": {}},
            }
        )
    )
    findings = run_field_coverage(REPO_ROOT, DLL, manifest)
    assert len(findings) > 0
    assert all(f["kind"] == "unclassified" for f in findings)

    # Now classify every field as ignored -> should pass.
    fields: dict[str, dict[str, dict[str, str | None]]] = {}
    for f in findings:
        fields.setdefault(f["script_type"], {})[f["field_name"]] = {
            "type": f["actual"],
            "status": "ignored",
            "reason": "test",
            "by": None,
        }
    manifest.write_text(
        json.dumps(
            {
                "tracks_build": "test",
                "types": ["LootTable"],
                "fields": fields,
            }
        )
    )
    findings = run_field_coverage(REPO_ROOT, DLL, manifest)
    assert findings == []
