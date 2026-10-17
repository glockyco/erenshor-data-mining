"""Quest panels obtain item grants and native required slots from persisted facts."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from erenshor.application.processor.item_provenance import ProvenanceBuilder
from erenshor.application.processor.writer import Writer
from erenshor.domain.value_objects.item_provenance import (
    PROVENANCE_SCHEMA_VERSION,
    ItemAcquisition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceLocation,
)
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.quests import QuestRepository
from erenshor.infrastructure.database.repository import RepositoryError


@pytest.fixture
def database(tmp_path: Path) -> Iterator[tuple[Writer, DatabaseConnection]]:
    path = tmp_path / "quests.sqlite"
    writer = Writer(path)
    writer.create_schema()
    writer.conn.execute(
        "INSERT INTO item_provenance_meta VALUES (?, 'fixture-build', '{}')", (PROVENANCE_SCHEMA_VERSION,)
    )
    writer.conn.executemany(
        "INSERT INTO quests (stable_key, display_name, wiki_page_name, image_name) VALUES (?, ?, ?, '')",
        [("quest:shared", "Shared quest", "Shared quest"), ("quest:assigned", "Assigned quest", "Assigned quest")],
    )
    writer.conn.execute(
        "INSERT INTO characters (stable_key, display_name, image_name, encounter_tier, level_scales_with_player) "
        "VALUES ('character:copy', 'Holder', '', 'enemy', 0)"
    )
    writer.conn.execute(
        "INSERT INTO character_deduplications (group_key, member_stable_key) VALUES ('group', 'character:copy')"
    )
    writer.conn.executemany(
        "INSERT INTO items (stable_key, display_name, image_name) VALUES (?, ?, '')",
        [("item:raw", "Raw reward"), ("item:canonical", "Canonical reward"), ("item:furniture", "Furniture")],
    )
    writer.conn.executemany(
        "INSERT INTO quest_variants (resource_name, quest_stable_key, xp_on_complete, gold_on_complete, "
        "item_on_complete_stable_key, repeatable, once_per_spawn_instance, assign_this_quest_on_partial_complete, "
        "dialog_on_partial_success, kill_turn_in_holder, drop_invuln_on_holder) "
        "VALUES (?, ?, 300, 25, 'item:raw', 0, 1, 1, 'Keep going', 1, 1)",
        [("native-a", "quest:shared"), ("unrelated-b", "quest:shared"), ("assignment", "quest:assigned")],
    )
    writer.conn.commit()
    db = DatabaseConnection(path, read_only=True)
    try:
        yield writer, db
    finally:
        db.close()
        writer.conn.close()


def _persist(writer: Writer, *facts: ItemAcquisition | ItemUse) -> None:
    builder = ProvenanceBuilder(writer.conn)
    for fact in facts:
        if isinstance(fact, ItemAcquisition):
            builder.acquisitions.append(fact)
        else:
            builder.uses.append(fact)
    builder.persist()
    writer.conn.commit()


def _turnin(writer: Writer) -> None:
    writer.conn.execute(
        "INSERT INTO quest_completion_sources "
        "VALUES ('quest:shared', 'item_turnin', 'character', 'character:copy', NULL)"
    )
    writer.conn.commit()


def _reward(key: str, mechanic: str) -> ItemAcquisition:
    return ItemAcquisition(
        key,
        "item:canonical",
        "quest_reward",
        "quest:shared",
        source_group_key="group",
        source_copy_stable_key="character:copy",
        variant_key="native-a",
        mechanic=mechanic,
        quantity_min=2,
        quantity_max=2,
        quantity_kind="exact",
    )


def test_raw_item_configuration_does_not_create_item_facts(database: tuple[Writer, DatabaseConnection]) -> None:
    writer, db = database
    _turnin(writer)
    writer.conn.execute("INSERT INTO quest_required_items VALUES ('native-a', 4, 'item:raw', 99)")
    writer.conn.commit()

    rows = QuestRepository(db).get_quest_panel_rows()["quest:shared"]

    variants = [row for row in rows if row["type"] == "variant"]
    assert len(variants) == 2
    assert all("item" not in row and "quantity" not in row for row in variants)
    assert all(row["experience"] == 300 and row["gold"] == 25 for row in variants)
    assert all(row["rewardMethod"] == "item_turnin" for row in variants)
    assert not any(row["type"] == "required" for row in rows)


def test_trade_items_keep_exact_variant_and_each_native_manager_route(
    database: tuple[Writer, DatabaseConnection],
) -> None:
    writer, db = database
    _turnin(writer)
    _persist(writer, _reward("reward:slot2", "trade:slot2"), _reward("reward:slot7", "trade:slot7"))

    rows = QuestRepository(db).get_quest_panel_rows()["quest:shared"]

    variants = {row["variant"]: row for row in rows if row["type"] == "variant"}
    assert variants["native-a"]["item"] == "item:canonical"
    assert variants["native-a"]["quantity"] == 2
    assert "item" not in variants["unrelated-b"]
    assert variants["unrelated-b"]["experience"] == 300
    assert variants["unrelated-b"]["gold"] == 25
    completions = [row for row in rows if row["type"] == "completion"]
    assert len(completions) == 2
    assert {(row["acquisitionKey"], row["mechanic"]) for row in completions} == {
        ("reward:slot2", "trade:slot2"),
        ("reward:slot7", "trade:slot7"),
    }
    assert all(row["variant"] == "native-a" for row in completions)
    assert all(row["sourceCopy"] == "character:copy" for row in completions)
    assert all(row["source"] == "character:copy" for row in completions)
    assert all(row["item"] == "item:canonical" and row["quantity"] == 2 for row in completions)


def test_canonical_trade_route_does_not_require_raw_completion_source(
    database: tuple[Writer, DatabaseConnection],
) -> None:
    writer, db = database
    _persist(writer, _reward("reward:slot2", "trade:slot2"))

    rows = QuestRepository(db).get_quest_panel_rows()["quest:shared"]

    assert any(row["type"] == "completion" and row["acquisitionKey"] == "reward:slot2" for row in rows)
    assert all(row["experience"] == 300 for row in rows if row["type"] == "variant")


def test_required_items_keep_variant_native_slot_and_independent_quantity(
    database: tuple[Writer, DatabaseConnection],
) -> None:
    writer, db = database
    _turnin(writer)
    writer.conn.execute("INSERT INTO quest_required_items VALUES ('native-a', 1, 'item:raw', 999)")
    _persist(
        writer,
        *(
            ItemUse(
                f"use:{variant}:{slot}",
                "item:canonical",
                "quest:shared",
                "quest_requirement",
                variant_key=variant,
                material_slot=slot,
                quantity_min=quantity,
                quantity_max=quantity,
                quantity_kind="exact",
            )
            for variant, slot, quantity in [("native-a", 2, 3), ("native-a", 9, 8), ("unrelated-b", 5, 2)]
        ),
    )

    rows = QuestRepository(db).get_quest_panel_rows()["quest:shared"]
    requirements = [row for row in rows if row["type"] == "required"]

    assert {(row["variant"], row["requiredSlot"], row["quantity"]) for row in requirements} == {
        ("native-a", 2, 3),
        ("native-a", 9, 8),
        ("unrelated-b", 5, 2),
    }
    assert all(row["item"] == "item:canonical" for row in requirements)


def test_dialog_gift_keeps_payload_gates_and_canonical_furniture(
    database: tuple[Writer, DatabaseConnection],
) -> None:
    writer, db = database
    writer.conn.execute(
        "INSERT INTO quest_completion_sources VALUES ('quest:shared', 'talk', 'character', 'character:copy', NULL)"
    )
    writer.conn.executemany(
        "INSERT INTO character_dialogs (character_stable_key, dialog_index, keywords, give_item_stable_key, "
        "assign_quest_stable_key, complete_quest_stable_key, required_quest_stable_key) "
        "VALUES ('character:copy', ?, 'thanks', 'item:canonical', 'quest:assigned', 'quest:shared', 'quest:assigned')",
        [(4,), (8,)],
    )
    furnished = ProvenanceCondition("furniture", 0, 0, "room_furnished", "item:furniture", "west")
    _persist(
        writer,
        ItemAcquisition(
            "dialog:4",
            "item:canonical",
            "dialog",
            "group",
            source_group_key="group",
            source_copy_stable_key="character:copy",
            variant_key="4",
            quantity_min=1,
            quantity_max=1,
            quantity_kind="exact",
            locations=(ProvenanceLocation("room", "spawn", conditions=(furnished,)),),
        ),
    )

    rows = QuestRepository(db).get_quest_panel_rows()["quest:shared"]
    dialogs = {row["dialogIndex"]: row for row in rows if row["type"] == "completion"}
    gift = dialogs[4]

    assert gift["item"] == "item:canonical"
    assert gift["quantity"] == 1
    assert gift["acquisitionKey"] == "dialog:4"
    assert gift["notOwnedItem"] == "item:canonical"
    assert gift["blockedByQuest"] == "quest:assigned"
    assert gift["prerequisite"] == "quest:assigned"
    assert gift["keywords"] == "thanks"
    assert gift["furniture"] == "item:furniture"
    assert gift["room"] == "west"
    assert "item" not in dialogs[8]
    assert dialogs[8]["notOwnedItem"] == "item:canonical"
    variants = [row for row in rows if row["type"] == "variant"]
    assert all(row["experience"] == 0 and row["gold"] == 0 and "item" not in row for row in variants)
    assert all(not row["oncePerSpawn"] and not row["killsHolder"] for row in variants)


def test_trade_route_preserves_canonical_furniture_alternatives(database: tuple[Writer, DatabaseConnection]) -> None:
    writer, db = database
    furnished = ProvenanceCondition("furniture", 0, 0, "room_furnished", "item:furniture", "east")
    reward = _reward("reward:slot2", "trade:slot2")
    _persist(
        writer,
        replace(reward, locations=(ProvenanceLocation("room", "spawn", conditions=(furnished,)),)),
    )

    completions = [
        row for row in QuestRepository(db).get_quest_panel_rows()["quest:shared"] if row["type"] == "completion"
    ]

    assert len(completions) == 1
    assert completions[0]["furniture"] == "item:furniture"
    assert completions[0]["room"] == "east"


def test_quest_panel_rejects_missing_canonical_contract(database: tuple[Writer, DatabaseConnection]) -> None:
    writer, db = database
    writer.conn.execute("DELETE FROM item_provenance_meta")
    writer.conn.commit()

    with pytest.raises(RepositoryError, match="Unsupported item provenance schema"):
        QuestRepository(db).get_quest_panel_rows()
