"""Tests for the wiki fetch page-title index."""

from __future__ import annotations

from unittest.mock import Mock

from tests.unit.application.wiki_lua.fakes import (
    make_character,
    make_item,
    make_skill,
    make_spell,
    make_stance,
    make_zone,
)

from erenshor.application.wiki.services.fetch_service import build_fetch_page_index


def _context_with_one_of_each() -> Mock:
    context = Mock()
    context.item_repo.get_items_for_wiki_generation.return_value = [make_item()]
    context.character_repo.get_characters_for_wiki_generation.return_value = [make_character()]
    context.spell_repo.get_spells_for_wiki_generation.return_value = [make_spell()]
    context.skill_repo.get_skills_for_wiki_generation.return_value = [make_skill()]
    context.stance_repo.get_all.return_value = [make_stance()]
    context.zone_repo.get_all_zones.return_value = [make_zone()]
    return context


def test_build_fetch_page_index_includes_zone_pages() -> None:
    """Zone pages contribute stable keys to the fetch metadata index."""
    zone = make_zone()
    context = _context_with_one_of_each()
    context.zone_repo.get_all_zones.return_value = [zone]

    index = build_fetch_page_index(context)

    assert index[zone.wiki_page_name] == [zone.stable_key]


def test_build_fetch_page_index_groups_every_entity_kind() -> None:
    """Every wiki-generated entity kind is represented in the index."""
    context = _context_with_one_of_each()

    index = build_fetch_page_index(context)

    assert {
        "Sword of Flames",
        "A Grizzly Bear",
        "Minor Lightning",
        "Double Attack",
        "Aggressive Stance",
        "Port Azure",
    } <= set(index)
