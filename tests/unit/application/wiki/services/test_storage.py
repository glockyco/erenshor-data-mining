"""Unit tests for wiki generated-page storage."""

from __future__ import annotations

from pathlib import Path

import pytest

from erenshor.application.wiki.services.storage import WikiStorage


def test_save_generated_by_title_strips_trailing_line_whitespace(tmp_path: Path) -> None:
    """Standard generated pages are written without line-end spaces."""
    storage = WikiStorage(tmp_path)

    storage.save_generated_by_title("A Page", ["stable:key"], "Alpha  \nBeta\t\n")

    assert (tmp_path / "generated" / "A%20Page.txt").read_text(encoding="utf-8") == "Alpha\nBeta\n"
    assert storage.list_generated_titles() == ("A Page",)


def test_read_generated_pages_returns_filtered_deterministic_snapshot(tmp_path: Path) -> None:
    storage = WikiStorage(tmp_path)
    storage.save_generated_by_title("Zulu", ["item:zulu"], "zulu\n")
    storage.save_generated_by_title("alpha", ["item:alpha"], "alpha\n")

    assert storage.read_generated_pages() == {"alpha": "alpha\n", "Zulu": "zulu\n"}
    assert storage.read_generated_pages(["Zulu"]) == {"Zulu": "zulu\n"}


def test_read_generated_pages_rejects_missing_content_file(tmp_path: Path) -> None:
    storage = WikiStorage(tmp_path)
    storage.save_generated_by_title("Missing", ["item:missing"], "content\n")
    (tmp_path / "generated" / "Missing.txt").unlink()

    with pytest.raises(FileNotFoundError, match="Generated wiki content missing"):
        storage.read_generated_pages()
