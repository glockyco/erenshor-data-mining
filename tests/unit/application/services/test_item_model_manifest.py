"""The item capture manifest picks each item's model and the bodies that draw it differently."""

from __future__ import annotations

from typing import cast

import pytest

from erenshor.application.services.item_model_manifest import (
    ItemSource,
    ModelParts,
    build_item_manifest,
)


def _item(key: str, subject: str, slot: str, part: str, **fields: object) -> ItemSource:
    return ItemSource(
        stable_key=key,
        item_id=key.upper(),
        subject=subject,
        wiki_page=str(fields.get("page", subject)),
        required_slot=slot,
        part=part,
        is_bow=bool(fields.get("is_bow", False)),
        is_furniture_set=bool(fields.get("is_furniture_set", False)),
        cosmetic_effect=cast("str | None", fields.get("cosmetic_effect")),
    )


_PARTS = ModelParts(
    body_meshes={
        ("male", "BootsL", "LeatherBoots"): frozenset({"male_boots_l"}),
        ("male", "BootsR", "LeatherBoots"): frozenset({"male_boots_r"}),
        ("female", "BootsL", "LeatherBoots"): frozenset({"female_boots_l"}),
        ("female", "BootsR", "LeatherBoots"): frozenset({"female_boots_r"}),
        ("male", "Cloak", "AngledCape"): frozenset({"cape"}),
        ("female", "Cloak", "AngledCape"): frozenset({"cape"}),
        ("male", "GloveL", "LeatherHalfGlove"): frozenset({"male_glove"}),
        ("male", "WeaponL", "MoloraiBow"): frozenset({"bow"}),
        ("female", "WeaponL", "MoloraiBow"): frozenset({"bow"}),
        ("male", "WeaponR", "Letterswords"): frozenset({"letters"}),
        ("female", "WeaponR", "Letterswords"): frozenset({"letters"}),
    },
    furnishings={"Wood Training": ("Reliquary", (270.0, 1.4, 325.0))},
)


def _manifest(*items: ItemSource) -> dict[str, tuple[str, str, str | None]]:
    manifest = build_item_manifest(items, _PARTS, "24405256")
    return {entry.subject: (entry.title, entry.kind, entry.body) for entry in manifest.entries}


def test_a_part_with_a_mesh_for_each_body_gets_a_render_of_each() -> None:
    entries = _manifest(_item("item:boots", "Wolfhide Boots", "Foot", "LeatherBoots"))

    assert entries == {
        "Wolfhide Boots (male)": ("Wolfhide Boots render (male).png", "worn", "male"),
        "Wolfhide Boots (female)": ("Wolfhide Boots render (female).png", "worn", "female"),
    }


def test_a_part_that_both_bodies_share_and_a_part_of_one_body_get_one_render() -> None:
    entries = _manifest(
        _item("item:cape", "Feathered Cape", "Back", "AngledCape"),
        _item("item:glove", "Rough Gloves", "Hand", "LeatherHalfGlove"),
    )

    assert entries == {
        "Feathered Cape": ("Feathered Cape render.png", "worn", "male"),
        "Rough Gloves": ("Rough Gloves render.png", "worn", "male"),
    }


def test_weapons_masks_furnishings_and_cosmetic_objects_get_one_render() -> None:
    manifest = build_item_manifest(
        [
            _item("item:bow", "Molorai Bow", "Primary", "MoloraiBow", is_bow=True),
            _item("item:mask", "Mask Fox", "General", "Fox", cosmetic_effect="mask"),
            _item("item:set", "Wood Training Set", "General", "Wood Training", is_furniture_set=True),
            # A lamp names no part; the capture finds the player's belt lamp by the effect.
            _item("item:lantern", "Keeper's Lantern", "General", "", cosmetic_effect="belt lamp"),
            # A part that no mask object holds is no mask without the effect.
            _item("item:fake", "Mask Fake", "General", "Fox"),
        ],
        _PARTS,
        "24405256",
    )

    assert {entry.subject: (entry.title, entry.kind, entry.body, entry.part) for entry in manifest.entries} == {
        "Molorai Bow": ("Molorai Bow render.png", "weapon", "male", "MoloraiBow"),
        "Mask Fox": ("Mask Fox render.png", "mask", None, "Fox"),
        "Wood Training Set": ("Wood Training Set render.png", "furnishing", None, "Wood Training"),
        "Keeper's Lantern": ("Keeper's Lantern render.png", "cosmetic", None, "belt lamp"),
    }


def test_items_that_share_a_subject_share_one_capture_with_all_their_pages() -> None:
    manifest = build_item_manifest(
        [
            _item("item:letters rare", "Letters and Words", "PrimaryOrSecondary", "Letterswords", page="Letters"),
            _item("item:letters common", "Letters and Words", "PrimaryOrSecondary", "Letterswords", page="Words"),
        ],
        _PARTS,
        "24405256",
    )

    assert [(entry.subject, entry.stable_key, entry.pages) for entry in manifest.entries] == [
        ("Letters and Words", "item:letters common", ("Letters", "Words"))
    ]


def test_a_blueprint_gets_no_capture_and_a_missing_part_is_listed_apart() -> None:
    manifest = build_item_manifest(
        [
            _item("item:blueprint", "Blueprint Wood Training", "General", "Wood Training"),
            _item("item:quiver", "Vithean Quiver", "Back", "WindQuiver"),
        ],
        _PARTS,
        "24405256",
    )

    assert manifest.entries == ()
    assert [(item.subject, item.part) for item in manifest.unsourced] == [("Vithean Quiver", "WindQuiver")]


def test_items_that_share_a_subject_but_not_a_model_fail_naming_them() -> None:
    with pytest.raises(ValueError, match="item:a, item:b share a subject but not a model"):
        build_item_manifest(
            [
                _item("item:a", "Twin", "Back", "AngledCape"),
                _item("item:b", "Twin", "Foot", "LeatherBoots"),
            ],
            _PARTS,
            "24405256",
        )
