"""Unit tests for wiki generated-page storage."""

from __future__ import annotations

from pathlib import Path

from erenshor.application.wiki.services.storage import WikiStorage


def test_save_generated_by_title_strips_trailing_line_whitespace(tmp_path: Path) -> None:
    """Standard generated pages are written without line-end spaces."""
    storage = WikiStorage(tmp_path)

    storage.save_generated_by_title("A Page", ["stable:key"], "Alpha  \nBeta\t\n")

    assert (tmp_path / "generated" / "A%20Page.txt").read_text(encoding="utf-8") == "Alpha\nBeta\n"
