"""Unit tests for golden baseline file writers."""

from __future__ import annotations

import csv
from pathlib import Path

from erenshor.cli.commands.golden import _write_golden_csv


def test_write_golden_csv_preserves_trailing_cell_space_without_trailing_line_whitespace(tmp_path: Path) -> None:
    """CSV goldens keep data spaces but never end physical lines with spaces or CRLF."""
    path = tmp_path / "sample.csv"

    _write_golden_csv(path, [["name", "description"], ["Item", "ends with space "]])

    data = path.read_bytes()
    assert b"\r\n" not in data
    assert all(not line.endswith((b" ", b"\t")) for line in data.splitlines())
    with path.open(newline="", encoding="utf-8") as f:
        assert list(csv.reader(f)) == [["name", "description"], ["Item", "ends with space "]]
