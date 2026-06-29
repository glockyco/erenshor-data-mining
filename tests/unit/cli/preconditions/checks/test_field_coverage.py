"""Unit tests for the export field-coverage precondition check."""

from __future__ import annotations

import json
from pathlib import Path

from erenshor.cli.preconditions.checks import field_coverage as fc


def _manifest(repo_root: Path, *, types: list[str] | None = None) -> None:
    m = repo_root / "src" / "tools" / "ExportSurface" / "field-coverage.json"
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(
        json.dumps(
            {
                "tracks_build": "test",
                "types": types or [],
                "fields": {},
            }
        )
    )


def test_fails_on_field_findings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        fc,
        "run_field_coverage",
        lambda *a: [{"script_type": "Item", "field_name": "X", "kind": "unclassified", "actual": "System.Boolean"}],
    )
    monkeypatch.setattr(fc, "missing_listener_types", lambda *a: [])
    _manifest(tmp_path)
    managed = tmp_path / "Erenshor_Data" / "Managed"
    managed.mkdir(parents=True)
    (managed / "Assembly-CSharp.dll").write_bytes(b"")

    res = fc.export_field_coverage_current(
        {
            "repo_root": tmp_path,
            "game_dir": tmp_path,
        }
    )

    assert res.passed is False
    assert res.check_name == "export_field_coverage_current"
    assert "unclassified" in res.detail


def test_fails_on_missing_listener_types(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(fc, "run_field_coverage", lambda *a: [])
    monkeypatch.setattr(fc, "missing_listener_types", lambda *a: ["NewThing"])
    _manifest(tmp_path)
    managed = tmp_path / "Erenshor_Data" / "Managed"
    managed.mkdir(parents=True)
    (managed / "Assembly-CSharp.dll").write_bytes(b"")

    res = fc.export_field_coverage_current(
        {
            "repo_root": tmp_path,
            "game_dir": tmp_path,
        }
    )

    assert res.passed is False
    assert "NewThing" in res.detail


def test_passes_when_clean(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(fc, "run_field_coverage", lambda *a: [])
    monkeypatch.setattr(fc, "missing_listener_types", lambda *a: [])
    _manifest(tmp_path, types=["Item"])
    managed = tmp_path / "Erenshor_Data" / "Managed"
    managed.mkdir(parents=True)
    (managed / "Assembly-CSharp.dll").write_bytes(b"")

    res = fc.export_field_coverage_current(
        {
            "repo_root": tmp_path,
            "game_dir": tmp_path,
        }
    )

    assert res.passed is True


def test_fails_when_dll_absent(tmp_path: Path) -> None:
    """A missing shipped DLL fails the gate — always strict, no fallback (spec §7)."""
    _manifest(tmp_path)

    res = fc.export_field_coverage_current(
        {
            "repo_root": tmp_path,
            "game_dir": tmp_path,
        }
    )

    assert res.passed is False
    assert "dll" in res.message.lower() or "assembly" in res.detail.lower()
