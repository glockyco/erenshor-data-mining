"""Hermetic CLI smoke test for the ExportSurface checker."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet SDK not installed")


def test_cli_reports_unclassified_fixture_fields(
    tmp_path: Path,
    fixture_dll: Path,
    export_surface_tool: Path,
) -> None:
    manifest = tmp_path / "export-surface.json"
    manifest.write_text(
        json.dumps(
            {
                "tracks_build": "fixture",
                "types": ["FixtureLib.FixtureLoot"],
                "fields": {"FixtureLib.FixtureLoot": {}},
            }
        )
    )

    proc = subprocess.run(
        [
            "dotnet",
            str(export_surface_tool),
            str(fixture_dll),
            str(manifest),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 1, proc.stderr
    envelope = json.loads(proc.stdout)
    assert envelope["type"] == "erenshor://export/field-coverage-drift"
    assert envelope["status"] == 1

    findings = envelope["findings"]
    assert findings
    actual_fields = {
        "Drops": "System.Collections.Generic.List`1<System.String>",
        "Level": "System.Int32",
        "PoolA": "System.Collections.Generic.List`1<System.String>",
        "SingletonB": "System.String",
    }
    assert {finding["field_name"]: finding["actual"] for finding in findings} == actual_fields
    assert all(finding["script_type"] == "FixtureLib.FixtureLoot" for finding in findings)
    assert all(finding["kind"] == "unclassified" for finding in findings)
    assert all(finding["expected"] is None for finding in findings)

    detail = envelope["detail"]
    assert "4 field-coverage finding(s)" in detail
    assert manifest.name in detail
