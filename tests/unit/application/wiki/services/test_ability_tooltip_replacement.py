"""Focused tests for generated ability tooltip reconciliation."""

from __future__ import annotations

import pytest

from erenshor.application.wiki.services.generate_service import WikiGenerateService


def _service() -> WikiGenerateService:
    return WikiGenerateService.__new__(WikiGenerateService)


def _root(kind: str, name: str = "Root", stablekey: str | None = None) -> str:
    key = f"|stablekey={stablekey}" if stablekey is not None else ""
    return f"{{{{{kind}|name={name}{key}}}}}"


def _comp(kind: str, key: str, body: str = "") -> str:
    return f"{{{{{kind}|stablekey={key}{body}}}}}"


@pytest.mark.parametrize(
    ("root_kind", "companion_kind", "key"),
    [
        ("Ability", "SpellTooltip", "spell:minor_lightning"),
        ("Ability", "SkillTooltip", "skill:backstab"),
        ("Stance", "StanceTooltip", "stance:aggressive"),
    ],
)
def test_reconciles_each_root_kind_and_is_idempotent(root_kind: str, companion_kind: str, key: str) -> None:
    service = _service()
    old = f"intro\n{_root(root_kind)}\n{_comp(companion_kind, key, '|old=1')}\nend"
    new = f"{_root(root_kind)}\n{_comp(companion_kind, key, '|new=2')}"

    result = service._replace_ability_tooltip_templates(old, new)

    assert result == f"intro\n{_root(root_kind)}\n{_comp(companion_kind, key, '|new=2')}\nend"
    assert service._replace_ability_tooltip_templates(result, new) == result


def test_inserts_missing_companion_without_moving_manual_prose() -> None:
    service = _service()
    old = "before\n{{Ability|name=One}}\nmanual prose\n{{Ability|name=Two}}\nend"
    new = (
        "{{Ability|name=One}}\n{{SpellTooltip|stablekey=spell:one}}\n"
        "{{Ability|name=Two}}\n{{SpellTooltip|stablekey=spell:two}}"
    )

    result = service._replace_ability_tooltip_templates(old, new)

    assert result == (
        "before\n{{Ability|name=One}}\n{{SpellTooltip|stablekey=spell:one}}\n"
        "manual prose\n{{Ability|name=Two}}\n{{SpellTooltip|stablekey=spell:two}}\nend"
    )


def test_removes_stale_and_unkeyed_top_level_companions() -> None:
    service = _service()
    old = (
        "{{Ability|name=One}}\n{{SpellTooltip|stablekey=spell:stale}}\n"
        "{{SkillTooltip}}\n{{Ability|name=Two}}\n{{SkillTooltip|stablekey=skill:keep}}"
    )
    new = (
        "{{Ability|name=One}}\n{{SpellTooltip|stablekey=spell:new}}\n"
        "{{Ability|name=Two}}\n{{SkillTooltip|stablekey=skill:keep}}"
    )

    result = service._replace_ability_tooltip_templates(old, new)

    assert "spell:stale" not in result
    assert "{{SkillTooltip}}" not in result
    assert "spell:new" in result
    assert "skill:keep" in result


def test_no_new_companions_returns_old_bytes_unchanged() -> None:
    service = _service()
    old = "manual\n{{Ability}}\n{{SpellTooltip|stablekey=spell:stale}}\n"

    assert service._replace_ability_tooltip_templates(old, "{{Ability}}") == old


def test_root_ordinals_associate_companions_even_with_manual_prose() -> None:
    service = _service()
    old = "{{Ability|name=One}}\n{{Ability|name=Two}}\n"
    new = (
        "{{Ability|name=One}}\n{{SpellTooltip|stablekey=spell:one}}\n"
        "{{Ability|name=Two}}\n{{SpellTooltip|stablekey=spell:two}}"
    )

    result = service._replace_ability_tooltip_templates(old, new)

    assert result == (
        "{{Ability|name=One}}\n{{SpellTooltip|stablekey=spell:one}}\n"
        "{{Ability|name=Two}}\n{{SpellTooltip|stablekey=spell:two}}\n"
    )


@pytest.mark.parametrize(
    "new",
    [
        "{{Ability}}\n{{SpellTooltip}}",
        "{{Ability}}\n{{SpellTooltip|stablekey=skill:wrong}}",
        "{{SpellTooltip|stablekey=spell:orphan}}",
        "{{Ability}}\nprose\n{{SpellTooltip|stablekey=spell:nonadjacent}}",
    ],
)
def test_rejects_invalid_new_companion_shapes(new: str) -> None:
    service = _service()
    with pytest.raises(ValueError):
        service._replace_ability_tooltip_templates("{{Ability}}", new)


def test_rejects_duplicate_new_keys() -> None:
    service = _service()
    new = (
        "{{Ability}}\n{{SpellTooltip|stablekey=spell:duplicate}}\n"
        "{{Ability}}\n{{SpellTooltip|stablekey=spell:duplicate}}"
    )
    with pytest.raises(ValueError, match="Duplicate generated"):
        service._replace_ability_tooltip_templates("{{Ability}}\n{{Ability}}", new)


def test_rejects_duplicate_old_matches() -> None:
    service = _service()
    old = (
        "{{Ability}}\n{{SpellTooltip|stablekey=spell:duplicate}}\n"
        "{{Ability}}\n{{SpellTooltip|stablekey=spell:duplicate}}"
    )
    new = "{{Ability}}\n{{SpellTooltip|stablekey=spell:duplicate}}\n{{Ability}}"
    with pytest.raises(ValueError, match="Duplicate old"):
        service._replace_ability_tooltip_templates(old, new)


def test_rejects_missing_old_root_ordinal() -> None:
    service = _service()
    with pytest.raises(ValueError, match="Missing old Ability root ordinal"):
        service._replace_ability_tooltip_templates(
            "{{Ability}}", "{{Ability}}\n{{Ability}}\n{{SpellTooltip|stablekey=spell:two}}"
        )


def test_rejects_nonadjacent_old_generated_companion() -> None:
    service = _service()
    old = "{{Ability}}\nmanual prose\n{{SpellTooltip|stablekey=spell:one}}"
    new = "{{Ability}}\n{{SpellTooltip|stablekey=spell:one}}"
    with pytest.raises(ValueError, match="Nonadjacent"):
        service._replace_ability_tooltip_templates(old, new)


def test_rejects_keyed_old_stance_root() -> None:
    service = _service()
    old = "{{Stance|stablekey=stance:aggressive}}"
    new = "{{Stance}}\n{{StanceTooltip|stablekey=stance:aggressive}}"
    with pytest.raises(ValueError, match="Keyed old Stance"):
        service._replace_ability_tooltip_templates(old, new)
