"""Unit tests for wiki page output normalization."""

from __future__ import annotations

from erenshor.application.wiki.services.helpers import normalise_generated_page_content


def test_normalise_generated_page_content_strips_trailing_line_whitespace() -> None:
    """Generated wiki files are commit-clean without changing internal spaces."""
    assert normalise_generated_page_content("Alpha  \nBeta\t\nInside  spaces\n") == "Alpha\nBeta\nInside  spaces\n"
