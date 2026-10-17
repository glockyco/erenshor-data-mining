"""Exact title selection happens before entity assembly and table rendering."""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from erenshor.application.wiki.generators.pages.armor_overview import ArmorOverviewPageGenerator
from erenshor.application.wiki.generators.pages.entities import EntityPageGenerator
from erenshor.application.wiki.generators.pages.weapons_overview import WeaponsOverviewPageGenerator
from erenshor.domain.entities.stance import Stance


def test_selected_entity_page_assembles_every_root_but_no_other_page() -> None:
    context = MagicMock()
    context.item_repo.get_items_for_wiki_generation.return_value = []
    context.character_repo.get_characters_for_wiki_generation.return_value = []
    context.spell_repo.get_spells_for_wiki_generation.return_value = []
    context.skill_repo.get_skills_for_wiki_generation.return_value = []
    context.stance_repo.get_all.return_value = [
        Stance(stable_key="stance:second", wiki_page_name="Shared"),
        Stance(stable_key="stance:excluded", wiki_page_name="Other"),
        Stance(stable_key="stance:first", wiki_page_name="Shared"),
    ]
    context.skill_repo.get_skills_using_stance.return_value = []
    generator = EntityPageGenerator(context)
    generator.stance_generator.generate_template = MagicMock(
        side_effect=lambda enriched, _: "{{Stance|stablekey=" + enriched.stance.stable_key + "}}",
    )
    generator.category_generator.generate_categories = MagicMock(return_value=[])
    generator.category_generator.format_category_tags = MagicMock(return_value="")

    [page] = generator.generate_pages(page_titles=frozenset({"Shared"}))

    assert page.title == "Shared"
    assert page.stable_keys == ["stance:first", "stance:second"]
    assert "stance:first" in page.content
    assert "stance:second" in page.content
    assert "stance:excluded" not in page.content
    assert context.skill_repo.get_skills_using_stance.call_args_list == [
        call("stance:first"),
        call("stance:second"),
    ]
    assert generator.stance_generator.generate_template.call_count == 2


@pytest.mark.parametrize("generator_type", [ArmorOverviewPageGenerator, WeaponsOverviewPageGenerator])
def test_excluded_overview_does_not_query_or_render_items(generator_type: type) -> None:
    context = MagicMock()
    context.item_repo.get_items_for_wiki_generation.side_effect = AssertionError("Excluded overview queried items")

    assert list(generator_type(context).generate_pages(page_titles=frozenset({"Shared"}))) == []
    context.item_repo.get_items_for_wiki_generation.assert_not_called()


@pytest.mark.parametrize("generator_type", [ArmorOverviewPageGenerator, WeaponsOverviewPageGenerator])
def test_selected_overview_still_generates_its_complete_table(generator_type: type) -> None:
    context = MagicMock()
    context.item_repo.get_items_for_wiki_generation.return_value = []

    [page] = generator_type(context).generate_pages(page_titles=frozenset({generator_type.PAGE_TITLE}))

    assert page.title == generator_type.PAGE_TITLE
    assert '{| class="wikitable' in page.content
    context.item_repo.get_items_for_wiki_generation.assert_called_once_with()
