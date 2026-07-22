from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest
from tests.unit.application.wiki_lua.fakes import (
    make_character,
    make_item,
    make_quest,
    make_skill,
    make_spell,
    make_stance,
    make_zone,
)

from erenshor.application.wiki_lua.link_catalog import (
    LinkCatalogEntry,
    build_link_catalog_entries,
    build_links_data,
)


class FakeClassDisplay:
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def get_all_internal_names(self) -> list[str]:
        return list(self.mapping)

    def get_display_name(self, class_name: str) -> str:
        return self.mapping[class_name]


def _catalog_entries(**overrides: object) -> tuple[LinkCatalogEntry, ...]:
    values: dict[str, object] = {
        "items": [make_item()],
        "characters": [make_character()],
        "quests": [make_quest()],
        "zones": [make_zone()],
        "spells": [make_spell()],
        "skills": [make_skill()],
        "stances": [make_stance()],
        "factions": [
            SimpleNamespace(
                stable_key="faction:followers",
                display_name="The Followers",
                wiki_page_name="Shared Page",
                image_name="Followers",
            )
        ],
        "class_display": FakeClassDisplay({"Windblade": "Windblade"}),
    }
    values.update(overrides)
    return build_link_catalog_entries(**values)  # type: ignore[arg-type]


def test_catalog_entries_are_immutable() -> None:
    entry = LinkCatalogEntry("item:x", "item", "general", "X", "X", None)
    with pytest.raises(FrozenInstanceError):
        entry.name = "Changed"  # type: ignore[misc]


def test_catalog_covers_all_semantic_kinds_and_uses_canonical_subtypes() -> None:
    entries = _catalog_entries()
    assert {entry.kind for entry in entries} == {
        "item",
        "ability",
        "character",
        "quest",
        "zone",
        "faction",
        "class",
    }
    by_key = {entry.key: entry for entry in entries}
    assert by_key["item:sword_of_flames"].subtype == "weapon"
    assert by_key["spell:minor_lightning"].subtype == "spell"
    assert by_key["skill:double_attack"].subtype == "skill"
    assert by_key["stance:aggressive"].subtype == "stance"
    assert by_key["character:a_grizzly_bear"].subtype == "Enemy"
    assert by_key["zone:PortAzure"].subtype == "Zone"
    assert by_key["class:windblade"].name == "Windblade"


def test_catalog_skips_only_null_pages() -> None:
    excluded = make_item(wiki_page_name=None)
    entries = _catalog_entries(items=[excluded])
    assert all(entry.kind != "item" for entry in entries)

    with pytest.raises(ValueError, match="Blank link catalog page"):
        _catalog_entries(items=[make_item(wiki_page_name="")])
    with pytest.raises(ValueError, match="Blank link catalog name"):
        _catalog_entries(items=[make_item(display_name="")])


def test_duplicate_names_and_pages_are_preserved_but_keys_must_be_unique() -> None:
    first = make_spell(stable_key="spell:first", display_name="Same", wiki_page_name="Shared Spell Page")
    second = make_spell(stable_key="spell:second", display_name="Same", wiki_page_name="Shared Spell Page")
    entries = _catalog_entries(spells=[first, second])
    assert [entry.key for entry in entries if entry.page == "Shared Spell Page"] == ["spell:first", "spell:second"]
    data = build_links_data(entries)
    assert data["byPage"]["Shared Spell Page"] == ["spell:first", "spell:second"]

    duplicate = make_spell(stable_key="spell:first", display_name="Other", wiki_page_name="Other")
    with pytest.raises(ValueError, match="Duplicate link catalog key"):
        _catalog_entries(spells=[first, duplicate])


def test_catalog_rejects_unsupported_kinds_and_wrong_prefixes() -> None:
    with pytest.raises(ValueError, match="Unsupported link catalog kind"):
        build_links_data([LinkCatalogEntry("thing:x", "thing", None, "X", "X", None)])
    with pytest.raises(ValueError, match="wrong prefix"):
        build_links_data([LinkCatalogEntry("skill:x", "item", "weapon", "X", "X", None)])
    with pytest.raises(ValueError, match="Blank link catalog key"):
        build_links_data([LinkCatalogEntry(" ", "item", "weapon", "X", "X", None)])


def test_catalog_hash_and_indexes_are_deterministic() -> None:
    entries = _catalog_entries()
    data = build_links_data(reversed(entries))
    primitives = [entry.primitive() for entry in entries]
    expected_payload = json.dumps(primitives, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert data["catalogSha256"] == hashlib.sha256(expected_payload.encode()).hexdigest()
    assert list(data["byKey"]) == sorted(data["byKey"])
    assert data["entries"] == [entry.primitive() for entry in entries]
    assert data["byPage"]["Shared Page"] == ["faction:followers"]
