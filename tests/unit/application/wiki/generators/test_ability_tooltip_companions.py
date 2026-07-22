"""Focused contracts for generated legacy ability companion templates."""

from __future__ import annotations

from erenshor.application.wiki.generators.sections.item import ItemSectionGenerator


def _render(template_name: str, **context: str) -> str:
    # ItemSectionGenerator owns the shared Jinja environment. The ability
    # templates themselves do not depend on item-specific generator behavior.
    return ItemSectionGenerator().render_template(template_name, context)


def test_ability_template_keeps_unkeyed_root_and_appends_keyed_spell_companion() -> None:
    text = _render(
        "ability.jinja2",
        title="Minor Lightning",
        stable_key="spell:minor_lightning",
        tooltip_template="SpellTooltip",
    )

    root_end = text.index("}}") + 2
    root = text[:root_end]
    companion = text[root_end:].strip()
    assert root.startswith("{{Ability")
    assert "stablekey" not in root
    assert companion == "{{SpellTooltip|stablekey=spell:minor_lightning}}"


def test_ability_template_emits_skill_companion_for_skill_context() -> None:
    text = _render(
        "ability.jinja2",
        title="Backstab",
        stable_key="skill:backstab",
        tooltip_template="SkillTooltip",
    )

    assert text.rstrip().endswith("{{SkillTooltip|stablekey=skill:backstab}}")
    assert text.count("{{SkillTooltip") == 1
    assert text.count("{{SpellTooltip") == 0


def test_stance_template_keeps_unkeyed_root_and_appends_one_keyed_companion() -> None:
    text = _render(
        "stance.jinja2",
        title="Aggressive",
        stable_key="stance:aggressive",
    )

    root_end = text.index("}}") + 2
    root = text[:root_end]
    companion = text[root_end:].strip()
    assert root.startswith("{{Stance")
    assert "stablekey" not in root
    assert companion == "{{StanceTooltip|stablekey=stance:aggressive}}"


def test_multiple_legacy_stanzas_keep_companion_order_and_adjacency() -> None:
    first = _render(
        "ability.jinja2",
        title="First",
        stable_key="spell:first",
        tooltip_template="SpellTooltip",
    ).strip()
    second = _render(
        "ability.jinja2",
        title="Second",
        stable_key="skill:second",
        tooltip_template="SkillTooltip",
    ).strip()
    page = f"{first}\n\n----\n\n{second}"

    assert page.index("{{SpellTooltip|stablekey=spell:first}}") < page.index("{{SkillTooltip|stablekey=skill:second}}")
    assert page.index("}}\n{{SpellTooltip|stablekey=spell:first}}") > page.index("{{Ability")
    assert page.index("}}\n{{SkillTooltip|stablekey=skill:second}}") > page.index("----")
    assert page.count("{{SpellTooltip") == 1
    assert page.count("{{SkillTooltip") == 1
