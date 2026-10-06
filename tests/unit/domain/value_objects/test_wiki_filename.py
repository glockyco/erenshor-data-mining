from __future__ import annotations

import pytest

from erenshor.domain.value_objects.wiki_filename import sanitize_wiki_filename, upload_file_title


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("Aura: Ancient Presence", "Aura Ancient Presence"),
        ("Blueprint: Stone | Bank", "Blueprint Stone Bank"),
        ("  Multiple  :  Spaces  ", "Multiple Spaces"),
        ("Normal Item", "Normal Item"),
        (":|#<>[]{}", ""),
    ],
)
def test_sanitize_wiki_filename_removes_mediawiki_syntax(original: str, expected: str) -> None:
    assert sanitize_wiki_filename(original) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Aura: Ancient Presence.png", "Aura Ancient Presence.png"),
        ("Summoned: Brute.png", "Summoned Brute.png"),
        ("Thorned Branch.png", "Thorned Branch.png"),
    ],
)
def test_an_upload_title_drops_what_file_names_forbid_and_keeps_the_extension(title: str, expected: str) -> None:
    assert upload_file_title(title) == expected
