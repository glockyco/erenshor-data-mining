"""Unit tests for the ExportSurface tool runner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from erenshor.application.export_surface import runner


def test_missing_assembly_raises(tmp_path: Path) -> None:
    (tmp_path / "m.json").write_text("{}")
    with pytest.raises(FileNotFoundError, match="assembly"):
        runner.run_field_coverage(Path(), tmp_path / "nope.dll", tmp_path / "m.json")


def test_missing_manifest_raises(tmp_path: Path) -> None:
    (tmp_path / "dll.dll").write_bytes(b"")
    with pytest.raises(FileNotFoundError, match="manifest"):
        runner.run_field_coverage(Path(), tmp_path / "dll.dll", tmp_path / "nope.json")


def _mock_proc(returncode: int, stdout: str = "", stderr: str = "") -> object:
    """Build a fake subprocess.CompletedProcess."""
    return type(
        "Proc",
        (),
        {"returncode": returncode, "stdout": stdout, "stderr": stderr},
    )()


def test_exit_2_raises_runtime_error(tmp_path: Path) -> None:
    (tmp_path / "dll.dll").write_bytes(b"")
    (tmp_path / "m.json").write_text('{"tracks_build": "x", "types": [], "fields": {}}')
    with (
        patch("erenshor.application.export_surface.runner.subprocess.run") as mock_run,
        patch("erenshor.application.export_surface.runner.shutil.which", return_value="dotnet"),
    ):
        mock_run.side_effect = [
            _mock_proc(0),
            _mock_proc(2, stderr="usage error"),
        ]
        with pytest.raises(RuntimeError, match="exit 2"):
            runner.run_field_coverage(Path(), tmp_path / "dll.dll", tmp_path / "m.json")


def test_exit_0_returns_empty_findings(tmp_path: Path) -> None:
    (tmp_path / "dll.dll").write_bytes(b"")
    (tmp_path / "m.json").write_text('{"tracks_build": "x", "types": [], "fields": {}}')
    envelope = {"type": "erenshor://export/field-coverage-drift", "status": 0, "detail": "clean", "findings": []}
    with (
        patch("erenshor.application.export_surface.runner.subprocess.run") as mock_run,
        patch("erenshor.application.export_surface.runner.shutil.which", return_value="dotnet"),
    ):
        mock_run.side_effect = [
            _mock_proc(0),
            _mock_proc(0, stdout=json.dumps(envelope)),
        ]
        result = runner.run_field_coverage(Path(), tmp_path / "dll.dll", tmp_path / "m.json")
    assert result == []


def test_exit_1_returns_findings(tmp_path: Path) -> None:
    (tmp_path / "dll.dll").write_bytes(b"")
    (tmp_path / "m.json").write_text('{"tracks_build": "x", "types": [], "fields": {}}')
    findings = [
        {"script_type": "Item", "field_name": "X", "kind": "unclassified", "expected": None, "actual": "System.Boolean"}
    ]
    envelope = {
        "type": "erenshor://export/field-coverage-drift",
        "status": 1,
        "detail": "1 finding",
        "findings": findings,
    }
    with (
        patch("erenshor.application.export_surface.runner.subprocess.run") as mock_run,
        patch("erenshor.application.export_surface.runner.shutil.which", return_value="dotnet"),
    ):
        mock_run.side_effect = [
            _mock_proc(0),
            _mock_proc(1, stdout=json.dumps(envelope)),
        ]
        result = runner.run_field_coverage(Path(), tmp_path / "dll.dll", tmp_path / "m.json")
    assert len(result) == 1
    assert result[0]["kind"] == "unclassified"
