from __future__ import annotations

import pytest

from erenshor.domain.entities.image import ImageMetadata
from erenshor.domain.value_objects.wiki_filename import needs_redirect, sanitize_wiki_filename


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
def test_sanitize_wiki_filename_removes_mediawiki_syntax(
    original: str,
    expected: str,
) -> None:
    assert sanitize_wiki_filename(original) == expected
    assert needs_redirect(original, expected) is (original != expected)


def test_image_metadata_derives_the_upload_filename_from_domain_policy() -> None:
    metadata = ImageMetadata(
        stable_key="spell:ancient-presence",
        entity_type="spell",
        entity_name="Ancient Presence",
        image_name="Aura: Ancient Presence",
        source_icon_name="ancient-presence",
    )

    assert metadata.expected_wiki_filename == "Aura Ancient Presence.png"
