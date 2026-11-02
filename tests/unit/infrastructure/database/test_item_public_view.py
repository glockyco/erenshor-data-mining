"""The stored public view reads back as the view the build derived."""

from __future__ import annotations

from typing import TYPE_CHECKING

from erenshor.application.processor.item_public_view import derive_public_view, write_public_view
from erenshor.application.processor.writer import Writer
from erenshor.domain.value_objects.item_provenance import (
    PROVENANCE_SCHEMA_VERSION,
    ItemAcquisition,
    ItemDisposition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceEvidence,
    ProvenanceLocation,
)
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.item_public_view import ItemPublicViewRepository

if TYPE_CHECKING:
    from pathlib import Path


def test_the_stored_view_reads_back_unchanged(tmp_path: Path) -> None:
    quest = ProvenanceCondition("unlock", 0, 0, "quest_done", "quest:a", actor="player")
    level = ProvenanceCondition("level", 0, 0, "actor_level", actor="player", minimum=5, maximum_inclusive=False)
    chance = ProvenanceCondition(
        "chance", 0, 0, "formula_operand", value="per_pair", minimum=40, phase="mechanic_parameter"
    )
    place = ProvenanceLocation(
        "spawn:a", "spawn", "Town", "zone:town", "spawn:a", 1.5, 2, 3, 1, 9, (level,), ("line:a",), "character:a"
    )
    view = derive_public_view(
        (
            ItemAcquisition(
                "vendor",
                "item:a",
                "vendor",
                "group:a",
                "group:a",
                "character:a",
                "stock",
                "wells",
                probability_kind="not_applicable",
                quantity_kind="exact",
                quantity_min=1,
                quantity_max=1,
                guarantee_scope="item",
                location_source_key="character:a",
                conditions=(quest, chance),
                locations=(place,),
            ),
            ItemAcquisition("common", "item:a", "common_world_item", None, mechanic="wells", conditions=(chance,)),
        ),
        (ItemUse("use", "item:a", "item:b", "crafting_material", "recipe", 2, 2, 3, "bounded", conditions=(quest,)),),
        (ItemDisposition("item:a", "current", current_pages=("A",)), ItemDisposition("item:b", "removed", "gone")),
        {"common": (ProvenanceEvidence("loot_drops", '["character:b","item:a"]'),)},
        {"wells": (chance,)},
    )
    writer = Writer(tmp_path / "view.sqlite")
    writer.create_schema()
    writer.conn.executemany(
        "INSERT INTO items (stable_key, display_name, image_name) VALUES (?, ?, ?)",
        [("item:a", "A", "A"), ("item:b", "B", "B")],
    )
    writer.conn.execute(
        "INSERT INTO item_provenance_meta VALUES (?, 'build', ?)",
        (PROVENANCE_SCHEMA_VERSION, '{"items":"' + "0" * 64 + '"}'),
    )
    write_public_view(writer.conn, view)
    writer.conn.commit()

    repository = ItemPublicViewRepository(DatabaseConnection(tmp_path / "view.sqlite"))

    assert repository.sources() == view.sources
    assert repository.uses() == view.uses
    assert repository.places("character:a") == view.places
    assert repository.parameters("wells") == view.parameters
    assert repository.contributors("common") == ("character:b",)
    assert repository.statuses() == view.statuses
