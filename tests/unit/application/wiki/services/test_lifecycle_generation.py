"""Reviewed lifecycle facts stay on the matching generated article roots."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import mwparserfromhell
import pytest
from rich.console import Console

from erenshor.application.wiki.generators.base import GeneratedPage, PageMetadata
from erenshor.application.wiki.lifecycle import (
    ContentLifecycle,
    LifecyclePage,
    apply_lifecycle_fields,
    load_content_lifecycle,
    render_split_disambiguation,
    validate_generated_lifecycle,
)
from erenshor.application.wiki.services.generate_service import GeneratedCorpus, WikiGenerateService

ROOT = Path(__file__).resolve().parents[5]


def _page(title: str, key: str, root: str) -> GeneratedPage:
    return GeneratedPage(
        title=title,
        content=f"{{{{{root}\n|title={title}\n|stablekey={key}\n}}}}\n",
        metadata=PageMetadata(summary="test"),
        stable_keys=[key],
    )


def _fields(text: str, name: str) -> dict[str, str]:
    code = mwparserfromhell.parse(text)
    template = next(t for t in code.filter_templates() if str(t.name).strip() == name)
    return {str(param.name).strip(): str(param.value).strip() for param in template.params}


def test_generated_pages_receive_reviewed_fields_and_keep_editor_prose() -> None:
    lifecycle = load_content_lifecycle(ROOT / "content-lifecycle.json")
    storage = MagicMock()
    storage.read_fetched_by_title.side_effect = lambda title: (
        "{{Ability\n|title=Mana Burst\n|stablekey=spell:arc - manaburst\n}}\n\nEditor notes."
        if title == "Mana Burst"
        else None
    )
    context = MagicMock(storage=storage)
    service = WikiGenerateService(context, link_catalog=(), console=Console(file=StringIO()), lifecycle=lifecycle)
    seen: list[GeneratedCorpus] = []
    pages = [
        _page("Mana Burst", "spell:arc - manaburst", "Ability"),
        _page("Pristine Ceremonial Ring", "item:ring - 14 - ancient ceremonial ring 1", "Item"),
        _page("Skill Book: Reckless Strike", "item:skillbook - stance - reckless", "Item"),
        _page("Ordinary Ring", "item:ordinary ring", "Item"),
    ]

    result = service._process_generated_pages(pages, dry_run=True, validate=seen.append)

    assert result.succeeded == 4
    generated = seen[0].pages
    assert _fields(generated["Mana Burst"], "Ability")["historical_state"] == "removed"
    assert _fields(generated["Mana Burst"], "Ability")["historical_thing"] == "spell"
    assert "Editor notes." in generated["Mana Burst"]
    assert _fields(generated["Pristine Ceremonial Ring"], "Item")["historical_state"] == "unobtainable"
    assert _fields(generated["Skill Book: Reckless Strike"], "Item")["aka"] == "Skill Book: Reckless Stance"
    assert _fields(generated["Ordinary Ring"], "Item") == {
        "title": "Ordinary Ring",
        "stablekey": "item:ordinary ring",
    }
    assert (
        not {
            "Reckless",
            "Stance: Reckless",
            "Spell Scroll: Mana Burst",
            "Spell Scroll: Mana Call",
            "Spell Scroll: Mana Flood",
        }
        & generated.keys()
    )
    storage.save_generated_by_title.assert_not_called()


def test_generated_skill_notice_uses_its_recorded_noun() -> None:
    lifecycle = ContentLifecycle(
        pages={
            "Old Skill": LifecyclePage(
                "Old Skill", "skill:old", "removed", "skill", None, None, None, "Reviewed removal"
            )
        },
        renames={},
        splits={},
    )

    text = apply_lifecycle_fields("Old Skill", ["skill:old"], "{{Ability|stablekey=skill:old}}", lifecycle)

    assert _fields(text, "Ability")["historical_thing"] == "skill"


def test_generated_page_cannot_carry_the_chat_flag() -> None:
    lifecycle = ContentLifecycle(
        pages={
            "Quiet Golem": LifecyclePage(
                "Quiet Golem", "item:golem", "unused", "item", None, None, None, "Chat names it", chat=True
            )
        },
        renames={},
        splits={},
    )

    with pytest.raises(ValueError, match="chat flag applies only to pages that generation does not write"):
        apply_lifecycle_fields("Quiet Golem", ["item:golem"], "{{Item|stablekey=item:golem}}", lifecycle)


def test_lifecycle_does_not_mark_an_unrelated_root_on_the_same_article() -> None:
    lifecycle = load_content_lifecycle(ROOT / "content-lifecycle.json")
    original = (
        "{{Ability|stablekey=spell:other|title=Mana Burst}}\n"
        "{{Ability|stablekey=spell:arc - manaburst|title=Mana Burst}}\n"
    )

    result = apply_lifecycle_fields("Mana Burst", ["spell:other", "spell:arc - manaburst"], original, lifecycle)

    roots = [
        {str(param.name).strip(): str(param.value).strip() for param in template.params}
        for template in mwparserfromhell.parse(result).filter_templates(recursive=False)
    ]
    assert "historical_state" not in roots[0]
    assert roots[1]["historical_state"] == "removed"


def test_renamed_spell_does_not_gain_an_item_former_name_field() -> None:
    lifecycle = load_content_lifecycle(ROOT / "content-lifecycle.json")
    content = "{{Ability|title=Aura: Rising Shadows I|stablekey=spell:aura - reaver 1}}"

    result = apply_lifecycle_fields("Aura: Rising Shadows I", ["spell:aura - reaver 1"], content, lifecycle)

    assert result == content


def test_full_generation_rejects_a_revived_old_title() -> None:
    lifecycle = load_content_lifecycle(ROOT / "content-lifecycle.json")
    with pytest.raises(ValueError, match="Skill Book: Reckless Stance: renamed title is still generated"):
        validate_generated_lifecycle(
            {
                "Skill Book: Reckless Stance": ["item:skillbook - stance - reckless"],
                "Skill Book: Reckless Strike": ["item:skillbook - stance - reckless"],
            },
            lifecycle,
        )


def test_planar_march_date_is_readable_on_matching_root() -> None:
    lifecycle = load_content_lifecycle(ROOT / "content-lifecycle.json")
    # A reviewed removed identity is only rendered if generation produces the same root.
    text = apply_lifecycle_fields("Reckless", "stance:reckless", "{{Ability|stablekey=stance:reckless}}", lifecycle)
    assert _fields(text, "Ability")["historical_date"] == "July 13, 2026"
    assert _fields(text, "Ability")["historical_url"].startswith("https://")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("state", "retired", "unknown state"),
        ("date", "2026-02-30", "malformed date"),
        ("patch_notes_url", "http://example.org/notes", "https link"),
        ("date", None, "update requires a date"),
        ("chat", True, "chat applies only to unused content"),
        ("chat", False, "chat must be true when present"),
    ],
)
def test_invalid_lifecycle_fact_names_its_entry(
    tmp_path: Path, field: str, value: str | bool | None, message: str
) -> None:
    path = tmp_path / "content-lifecycle.json"
    fact = {
        "stable_key": "item:ring",
        "state": "removed",
        "thing": "item",
        "update": "Planar March",
        "date": "2026-07-13",
        "patch_notes_url": "https://example.org/notes",
        "source": "Reviewed notes",
    }
    fact[field] = value
    path.write_text(json.dumps({"pages": {"Old Ring": fact}, "renames": {}, "splits": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match=f"pages\\['Old Ring'\\].*{message}"):
        load_content_lifecycle(path)


def test_a_title_cannot_be_both_removed_and_renamed(tmp_path: Path) -> None:
    path = tmp_path / "content-lifecycle.json"
    path.write_text(
        json.dumps(
            {
                "pages": {
                    "Old Ring": {
                        "stable_key": "item:ring",
                        "state": "removed",
                        "thing": "item",
                        "update": None,
                        "date": None,
                        "patch_notes_url": None,
                        "source": "Reviewed notes",
                    }
                },
                "renames": {
                    "Old Ring": {
                        "stable_key": "item:ring",
                        "current_title": "New Ring",
                        "source": "Current game data",
                    }
                },
                "splits": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"Old Ring.*both a page and a rename"):
        load_content_lifecycle(path)


def test_reviewed_split_links_both_current_variants() -> None:
    lifecycle = load_content_lifecycle(ROOT / "content-lifecycle.json")
    split = lifecycle.splits["Braxonian Planar Guard"]
    assert split.stable_keys == (
        "character:braxonian planar guardian fire",
        "character:braxonian planar guardian ice",
    )
    assert render_split_disambiguation(split) == (
        "Braxonian Planar Guard may refer to:\n\n"
        "* [[Braxonian Planar Guard (Fire)]]\n"
        "* [[Braxonian Planar Guard (Ice)]]\n\n__DISAMBIG__\n"
    )
    validate_generated_lifecycle(
        {
            "Braxonian Planar Guard (Fire)": [split.stable_keys[0]],
            "Braxonian Planar Guard (Ice)": [split.stable_keys[1]],
            "Skill Book: Reckless Strike": ["item:skillbook - stance - reckless"],
            "Aura: Rising Shadows I": ["spell:aura - reaver 1"],
            "Aura: Rising Shadows II": ["spell:aura - reaver 2"],
            "Aura: Rising Shadows III": ["spell:aura - reaver 3"],
            "Aura: Rising Shadows IV": ["spell:aura - reaver 4"],
            "Rune of Elements": ["item:gen - raid rune of brax"],
            "Enterprising Spirit": ["character:ghostly figure:shiveringstep:701.36:24.78:439.97"],
            "Invader of Dreams": ["character:dream invader:fernallaportal:343.45:0.52:405.94"],
            "Bridgekeeper": ["character:watchman:shiveringstep:508.96:68.49:659.72"],
            "Gatekeeper": ["character:gatekeeper:shiveringstep:672.15:29.53:421.14"],
        },
        lifecycle,
    )


@pytest.mark.parametrize(
    ("titles", "keys", "message"),
    [
        ([], [], "nonempty list"),
        (["Fire", "Fire"], ["character:fire", "character:ice"], "contains duplicates"),
        (["Fire", "Ice"], ["character:fire"], "match current_titles count"),
    ],
)
def test_split_requires_distinct_targets_and_matching_keys(
    tmp_path: Path, titles: list[str], keys: list[str], message: str
) -> None:
    path = tmp_path / "content-lifecycle.json"
    path.write_text(
        json.dumps(
            {
                "pages": {},
                "renames": {},
                "splits": {
                    "Old Guard": {
                        "current_titles": titles,
                        "stable_keys": keys,
                        "source": "Current game data",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=message):
        load_content_lifecycle(path)


@pytest.mark.parametrize("other_mapping", ["pages", "renames"])
def test_split_title_cannot_also_be_a_page_or_rename(tmp_path: Path, other_mapping: str) -> None:
    path = tmp_path / "content-lifecycle.json"
    data: dict[str, dict[str, object]] = {
        "pages": {},
        "renames": {},
        "splits": {
            "Old Guard": {
                "current_titles": ["Fire", "Ice"],
                "stable_keys": ["character:fire", "character:ice"],
                "source": "Current game data",
            }
        },
    }
    if other_mapping == "pages":
        data["pages"]["Old Guard"] = {
            "stable_key": None,
            "state": "unused",
            "thing": "character",
            "update": None,
            "date": None,
            "patch_notes_url": None,
            "source": "Current game data",
        }
    else:
        data["renames"]["Old Guard"] = {
            "stable_key": "character:fire",
            "current_title": "Fire",
            "source": "Current game data",
        }
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=r"Old Guard.*also a page or rename"):
        load_content_lifecycle(path)
