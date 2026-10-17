"""Reviewed lifecycle inputs resolve stable item identities without inferred removals."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from erenshor.infrastructure.content_lifecycle import (
    ContentLifecycle,
    LifecyclePage,
    LifecycleRename,
    LifecycleSplit,
    LifecycleState,
    derive_item_dispositions,
    load_content_lifecycle,
)


def _fact(title: str, key: str | None, state: LifecycleState) -> LifecyclePage:
    return LifecyclePage(title, key, state, "item", None, None, None, f"Reviewed {title}")


def test_current_items_without_reviewed_facts_remain_current_including_unpublished_variants() -> None:
    lifecycle = ContentLifecycle(pages={}, renames={}, splits={})

    facts = derive_item_dispositions(
        lifecycle,
        {"item:visible": "Shared Ring", "item:variant": "Shared Ring", "item:hidden": None, "item:blank": ""},
    )

    by_key = {fact.item_stable_key: fact for fact in facts}
    assert [fact.item_stable_key for fact in facts] == sorted(by_key)
    assert all(fact.disposition == "current" for fact in facts)
    assert all(fact.reason is None and fact.evidence is None for fact in facts)
    assert by_key["item:visible"].current_pages == ("Shared Ring",)
    assert by_key["item:variant"].current_pages == ("Shared Ring",)
    assert by_key["item:hidden"].current_pages == ()
    assert by_key["item:blank"].current_pages == ()


def test_reviewed_states_match_stable_keys_not_reused_page_titles() -> None:
    lifecycle = ContentLifecycle(
        pages={"Old Ring": _fact("Old Ring", "item:old", "unobtainable")}, renames={}, splits={}
    )

    facts = derive_item_dispositions(lifecycle, {"item:old": "Renamed Ring", "item:new": "Old Ring"})

    by_key = {fact.item_stable_key: fact for fact in facts}
    assert by_key["item:old"].disposition == "unobtainable"
    assert by_key["item:old"].current_pages == ("Renamed Ring",)
    assert by_key["item:old"].former_pages == ("Old Ring",)
    assert by_key["item:old"].evidence == "Reviewed Old Ring"
    assert by_key["item:new"].disposition == "current"
    assert by_key["item:new"].former_pages == ()


def test_absent_reviewed_identity_is_retained_but_page_only_notices_are_not_guessed() -> None:
    lifecycle = ContentLifecycle(
        pages={
            "Removed Ring": _fact("Removed Ring", "item:removed", "removed"),
            "Missing Ring": _fact("Missing Ring", "item:missing", "unused"),
            "Old Scroll": _fact("Old Scroll", None, "removed"),
            "Removed Skill": LifecyclePage(
                "Removed Skill", "skill:removed", "removed", "skill", None, None, None, "Reviewed skill"
            ),
        },
        renames={},
        splits={},
    )

    facts = derive_item_dispositions(lifecycle, {})

    by_key = {fact.item_stable_key: fact for fact in facts}
    assert set(by_key) == {"item:removed", "item:missing"}
    assert by_key["item:removed"].disposition == "removed"
    assert by_key["item:removed"].current_pages == ()
    assert by_key["item:removed"].former_pages == ("Removed Ring",)
    assert by_key["item:missing"].disposition == "unused"


def test_rename_and_split_relations_keep_each_current_item_identity() -> None:
    lifecycle = ContentLifecycle(
        pages={},
        renames={"Old Book": LifecycleRename("Old Book", "item:book", "New Book", "Same book identity")},
        splits={
            "Old Guard": LifecycleSplit(
                "Old Guard", ("Fire Guard", "Ice Guard"), ("item:fire", "item:ice"), "Separate guard variants"
            )
        },
    )

    facts = derive_item_dispositions(lifecycle, {"item:book": "New Book", "item:fire": "Fire Guard", "item:ice": None})

    by_key = {fact.item_stable_key: fact for fact in facts}
    assert by_key["item:book"].current_pages == ("New Book",)
    assert by_key["item:book"].former_pages == ("Old Book",)
    assert by_key["item:book"].evidence == "Same book identity"
    assert by_key["item:fire"].current_pages == ("Fire Guard",)
    assert by_key["item:ice"].current_pages == ("Ice Guard",)
    assert by_key["item:fire"].former_pages == by_key["item:ice"].former_pages == ("Old Guard",)
    assert all(fact.disposition == "current" for fact in facts)


def test_page_relations_alone_do_not_invent_absent_item_entities_or_removals() -> None:
    lifecycle = ContentLifecycle(
        pages={},
        renames={"Old Book": LifecycleRename("Old Book", "item:book", "New Book", "Same book identity")},
        splits={},
    )

    assert derive_item_dispositions(lifecycle, {}) == ()


def test_conflicting_reviewed_states_reject_ambiguous_item_identity() -> None:
    lifecycle = ContentLifecycle(
        pages={
            "Old Ring": _fact("Old Ring", "item:ring", "removed"),
            "New Ring": _fact("New Ring", "item:ring", "unused"),
        },
        renames={},
        splits={},
    )

    with pytest.raises(ValueError, match="item:ring: conflicting reviewed item lifecycle states"):
        derive_item_dispositions(lifecycle, {"item:ring": "New Ring"})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("state", "retired", "unknown state"),
        ("date", "2026-02-30", "malformed date"),
        ("patch_notes_url", "http://example.org/notes", "https link"),
        ("date", None, "update requires a date"),
        ("chat", True, "expected fields"),
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
