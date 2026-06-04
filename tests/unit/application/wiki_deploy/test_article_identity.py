"""Tests for authoritative article identity maps."""

from __future__ import annotations

from dataclasses import dataclass

from erenshor.application.wiki_deploy.article_identity import build_article_identity_map


@dataclass(frozen=True)
class FakeEntity:
    stable_key: str
    wiki_page_name: str | None


def test_build_article_identity_map_groups_stable_keys_by_page() -> None:
    """The identity map mirrors generator grouping by wiki_page_name."""
    identities = build_article_identity_map(
        (
            FakeEntity("item:ember", "Ember Longsword"),
            FakeEntity("item:poem_1", "A Lost Poem"),
            FakeEntity("item:poem_2", "A Lost Poem"),
            FakeEntity("item:hidden", None),
        )
    )

    assert identities == {
        "Ember Longsword": ("item:ember",),
        "A Lost Poem": ("item:poem_1", "item:poem_2"),
    }
