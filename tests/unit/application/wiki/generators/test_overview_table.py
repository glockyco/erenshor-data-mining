"""Unit tests for the replacement of the generated overview table."""

from __future__ import annotations

import pytest

from erenshor.application.wiki.generators.overview_table import GeneratedTableError, replace_generated_table

GENERATED = '{| class="wikitable"\n!Armor\n!class="numeric"|Level\n|-\n|[[New Helm]]\n|5\n|}\n'

ARMOR_SETS = '{| class="wikitable"\n!Armor set\n!Bonus\n|-\n|[[Iron Set]]\n|+5 AC\n|}'


def _live_table(row: str, level_header: str = '!class="numeric"|Level') -> str:
    return f'{{| class="wikitable"\n!Armor\n{level_header}\n|-\n{row}\n|}}'


def test_replaces_only_the_generated_table() -> None:
    live = (
        "Armor protects you.\n\n"
        + _live_table("|[[Old Helm]]\n|3", level_header='!class="numeric" style="width: 4em"|Level')
        + "\n\n== Notes ==\nSets give bonuses.\n\n"
        + ARMOR_SETS
        + "\n"
    )

    page = replace_generated_table(live, GENERATED)

    assert page.startswith('Armor protects you.\n\n{| class="wikitable"\n!Armor\n')
    assert "[[New Helm]]" in page
    assert "[[Old Helm]]" not in page
    assert page.endswith("|}\n\n== Notes ==\nSets give bonuses.\n\n" + ARMOR_SETS + "\n")


def test_page_without_the_generated_table_fails() -> None:
    with pytest.raises(GeneratedTableError, match="no table with the generated header"):
        replace_generated_table("Armor protects you.\n\n" + ARMOR_SETS + "\n", GENERATED)


def test_page_with_two_generated_tables_fails() -> None:
    live = _live_table("|[[Old Helm]]\n|3") + "\n\n" + _live_table("|[[Old Boots]]\n|4") + "\n"

    with pytest.raises(GeneratedTableError, match="2 tables with the generated header"):
        replace_generated_table(live, GENERATED)
