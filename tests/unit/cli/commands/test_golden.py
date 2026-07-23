"""Unit tests for golden baseline file writers."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from erenshor.cli.commands.golden import _replace_golden_baseline, _write_golden_csv


def _tree_snapshot(root: Path) -> dict[str, bytes | None]:
    """Return relative paths and file bytes for a deterministic tree comparison."""
    return {
        str(path.relative_to(root)): path.read_bytes() if path.is_file() else None for path in sorted(root.rglob("*"))
    }


def _sibling_names(root: Path) -> set[str]:
    return {path.name for path in root.iterdir()}


def test_replace_golden_baseline_replaces_stale_files_with_populated_content(tmp_path: Path) -> None:
    golden_dir = tmp_path / "golden"
    (golden_dir / "wiki").mkdir(parents=True)
    (golden_dir / "sheets").mkdir()
    (golden_dir / "wiki" / "stale.txt").write_bytes(b"stale wiki")
    (golden_dir / "sheets" / "stale.csv").write_bytes(b"stale sheets")
    before_siblings = _sibling_names(tmp_path)

    def populate(staging_dir: Path) -> None:
        (staging_dir / "wiki").mkdir()
        (staging_dir / "sheets").mkdir()
        (staging_dir / "wiki" / "fresh.txt").write_bytes(b"fresh wiki")
        (staging_dir / "sheets" / "fresh.csv").write_bytes(b"fresh sheets")

    _replace_golden_baseline(golden_dir, populate)

    assert _tree_snapshot(golden_dir) == {
        "sheets": None,
        "sheets/fresh.csv": b"fresh sheets",
        "wiki": None,
        "wiki/fresh.txt": b"fresh wiki",
    }
    assert _sibling_names(tmp_path) == before_siblings


def test_replace_golden_baseline_preserves_original_tree_after_populate_failure(tmp_path: Path) -> None:
    golden_dir = tmp_path / "golden"
    for family in ("wiki", "sheets", "map", "code_facts"):
        (golden_dir / family).mkdir(parents=True)
        (golden_dir / family / "original.dat").write_bytes(f"original {family}".encode())
    original_tree = _tree_snapshot(golden_dir)
    before_siblings = _sibling_names(tmp_path)

    def populate(staging_dir: Path) -> None:
        for family in ("wiki", "sheets", "map", "code_facts"):
            (staging_dir / family).mkdir(parents=True)
            (staging_dir / family / "replacement.dat").write_bytes(f"replacement {family}".encode())
        raise RuntimeError("late populate failure")

    with pytest.raises(RuntimeError, match="late populate failure"):
        _replace_golden_baseline(golden_dir, populate)

    assert _tree_snapshot(golden_dir) == original_tree
    assert _sibling_names(tmp_path) == before_siblings


def test_replace_golden_baseline_restores_original_tree_after_final_rename_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    golden_dir = tmp_path / "golden"
    (golden_dir / "wiki").mkdir(parents=True)
    (golden_dir / "wiki" / "original.txt").write_bytes(b"original")
    original_tree = _tree_snapshot(golden_dir)
    before_siblings = _sibling_names(tmp_path)
    original_rename = Path.rename
    rename_calls = 0

    def fail_final_rename(self: Path, target: Path) -> Path:
        nonlocal rename_calls
        rename_calls += 1
        if rename_calls == 2 and Path(target) == golden_dir:
            raise OSError("injected final rename failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_final_rename)

    def populate(staging_dir: Path) -> None:
        (staging_dir / "wiki").mkdir()
        (staging_dir / "wiki" / "replacement.txt").write_bytes(b"replacement")

    with pytest.raises(OSError, match="injected final rename failure"):
        _replace_golden_baseline(golden_dir, populate)

    assert _tree_snapshot(golden_dir) == original_tree
    assert _sibling_names(tmp_path) == before_siblings


def test_write_golden_csv_preserves_trailing_cell_space_without_trailing_line_whitespace(tmp_path: Path) -> None:
    """CSV goldens keep data spaces but never end physical lines with spaces or CRLF."""
    path = tmp_path / "sample.csv"

    _write_golden_csv(path, [["name", "description"], ["Item", "ends with space "]])

    data = path.read_bytes()
    assert b"\r\n" not in data
    assert all(not line.endswith((b" ", b"\t")) for line in data.splitlines())
    with path.open(newline="", encoding="utf-8") as f:
        assert list(csv.reader(f)) == [["name", "description"], ["Item", "ends with space "]]
