"""Tests for MediaWiki save-content normalization."""

from __future__ import annotations

import pytest

from erenshor.infrastructure.wiki.content import normalize_saved_text


@pytest.mark.parametrize(
    ("sent", "stored"),
    [
        # Trailing whitespace and newlines are right-trimmed.
        ("x  \n\n\n", "x"),
        ("one trailing newline\n", "one trailing newline"),
        ("trailing spaces   ", "trailing spaces"),
        # CR and CRLF line endings collapse to LF.
        ("a\r\nb\r\n", "a\nb"),
        ("a\rb\r", "a\nb"),
        # Leading and internal whitespace is preserved.
        ("  lead\ntrail   ", "  lead\ntrail"),
        ("line \nend", "line \nend"),
        # Empty and whitespace-only inputs normalize to empty.
        ("", ""),
        ("   \n\t\n", ""),
    ],
)
def test_normalize_saved_text_matches_mediawiki_save_normalization(sent: str, stored: str) -> None:
    """Test the helper reproduces MediaWiki's CR-to-LF and trailing-trim behavior."""
    assert normalize_saved_text(sent) == stored


def test_normalize_saved_text_is_idempotent() -> None:
    """Test re-normalizing already-normalized text is a no-op."""
    once = normalize_saved_text("return { v = 1 }\r\n\n")
    assert normalize_saved_text(once) == once
