from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from erenshor.application.processor.item_provenance import ProvenanceBuilder
from erenshor.application.processor.writer import Writer
from erenshor.domain.value_objects.item_provenance import PROVENANCE_SCHEMA_VERSION
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository
from erenshor.infrastructure.database.repositories.quests import QuestRepository


@pytest.fixture
def panel_db(tmp_path: Path) -> Iterator[tuple[Writer, QuestRepository]]:
    path = tmp_path / "quests.sqlite"
    writer = Writer(path)
    writer.create_schema()
    writer.conn.execute(
        "INSERT INTO item_provenance_meta VALUES (?, 'fixture-build', '{}')", (PROVENANCE_SCHEMA_VERSION,)
    )
    writer.insert_quests(
        [
            {
                "stable_key": key,
                "display_name": "Same display name (1)",
                "wiki_page_name": "Shared page",
                "image_name": "Quest",
            }
            for key in ("quest:one", "quest:two", "quest:gate")
        ]
    )
    writer.insert_characters(
        [
            {
                "stable_key": key,
                "display_name": "Giver",
                "wiki_page_name": "Giver",
                "image_name": "Giver",
                "encounter_tier": "npc",
                "level_scales_with_player": 0,
            }
            for key in ("character:a", "character:b", "character:backup")
        ]
    )
    assert writer.conn.execute("SELECT COUNT(*) FROM characters").fetchone()[0] == 3
    writer.insert_character_deduplications(
        [
            {"group_key": "character:a", "member_stable_key": key, "is_wiki_generated": generated}
            for key, generated in (("character:a", 1), ("character:b", 1), ("character:backup", 0))
        ]
    )
    connection = DatabaseConnection(path, read_only=True)
    try:
        yield writer, QuestRepository(connection)
    finally:
        connection.close()
        writer.conn.close()


def _variant(resource: str, quest: str = "quest:one", **changes: object) -> dict[str, object]:
    return {
        "resource_name": resource,
        "quest_stable_key": quest,
        "quest_name": "Same presentation name",
        "xp_on_complete": 0,
        "gold_on_complete": 0,
        "item_on_complete_stable_key": None,
        "assign_new_quest_on_complete_stable_key": None,
        "dialog_on_partial_success": None,
        "repeatable": 1,
        "once_per_spawn_instance": 0,
        "assign_this_quest_on_partial_complete": 0,
        "kill_turn_in_holder": 0,
        "drop_invuln_on_holder": 0,
    } | changes


def _turnin(writer: Writer, quest: str = "quest:one") -> None:
    writer.insert_quest_completion_sources(
        [
            {
                "quest_stable_key": quest,
                "method": "item_turnin",
                "source_type": "character",
                "source_stable_key": "character:a",
            }
        ]
    )
    writer.conn.execute(
        "INSERT INTO character_quest_manager_quests "
        "SELECT 'character:a', quest_stable_key, row_number() OVER (ORDER BY resource_name), resource_name "
        "FROM quest_variants WHERE quest_stable_key = ?",
        (quest,),
    )


def _panel_rows(writer: Writer, repo: QuestRepository) -> dict[str, list[dict[str, object]]]:
    writer.conn.execute(
        "INSERT OR IGNORE INTO items (stable_key, display_name, image_name) "
        "SELECT item, item, item FROM ("
        "SELECT item_on_complete_stable_key AS item FROM quest_variants "
        "UNION SELECT item_stable_key FROM quest_required_items "
        "UNION SELECT give_item_stable_key FROM character_dialogs) WHERE item IS NOT NULL"
    )
    builder = ProvenanceBuilder(writer.conn)
    builder.quests()
    builder.vendors_and_dialog()
    builder.persist()
    writer.conn.commit()
    return repo.get_quest_panel_rows()


def test_requirements_rewards_and_flags_stay_with_each_resource(panel_db: tuple[Writer, QuestRepository]) -> None:
    writer, repo = panel_db
    writer.insert_quest_variants(
        [
            _variant("Resource A", xp_on_complete=155, item_on_complete_stable_key="item:belt"),
            _variant("Resource B", gold_on_complete=8, repeatable=0, once_per_spawn_instance=1, kill_turn_in_holder=1),
            _variant("Other identity", "quest:two", xp_on_complete=90),
        ]
    )
    writer.insert_quest_required_items(
        [
            {"quest_variant_resource_name": resource, "required_slot": 0, "item_stable_key": item, "quantity": quantity}
            for resource, item, quantity in (("Resource A", "item:eye", 3), ("Resource B", "item:bone", 2))
        ]
    )
    writer.insert_quest_faction_affects(
        [{"quest_variant_resource_name": "Resource A", "faction_stable_key": "faction:one", "modifier_value": -4}]
    )
    _turnin(writer)
    rows = _panel_rows(writer, repo)
    variants = {row["variant"]: row for row in rows["quest:one"] if row["type"] == "variant"}
    assert variants["Resource A"]["experience"] == 155
    assert variants["Resource A"]["item"] == "item:belt"
    assert variants["Resource A"]["quantity"] == 1
    assert variants["Resource B"]["gold"] == 8
    assert variants["Resource B"]["repeatable"] is False
    assert variants["Resource B"]["oncePerSpawn"] is True
    assert variants["Resource B"]["killsHolder"] is True
    assert [row for row in rows["quest:one"] if row["type"] == "required"] == [
        {"type": "required", "variant": "Resource A", "requiredSlot": 0, "item": "item:eye", "quantity": 3},
        {"type": "required", "variant": "Resource B", "requiredSlot": 0, "item": "item:bone", "quantity": 2},
    ]
    assert {row["variant"] for row in rows["quest:two"]} == {"Other identity"}
    assert {"type": "faction", "variant": "Resource A", "faction": "faction:one", "amount": -4} in rows["quest:one"]


def test_dialog_gates_remain_on_their_routes_not_on_named_variants(panel_db: tuple[Writer, QuestRepository]) -> None:
    writer, repo = panel_db
    writer.insert_quest_variants([_variant("Resource A"), _variant("Resource B")])
    writer.insert_quest_acquisition_sources(
        [
            {"quest_stable_key": "quest:one", "method": "dialog", "source_type": "character", "source_stable_key": key}
            for key in ("character:b", "character:backup")
        ]
    )
    writer.insert_character_dialogs(
        [
            {
                "character_stable_key": "character:b",
                "dialog_index": index,
                "keywords": keyword,
                "assign_quest_stable_key": "quest:one",
                "required_quest_stable_key": gate,
            }
            for index, keyword, gate in ((1, "favor", "quest:gate"), (2, "help", None))
        ]
    )
    routes = [row for row in _panel_rows(writer, repo)["quest:one"] if row["type"] == "acquisition"]
    assert len(routes) == 2
    assert all(row["source"] == "character:a" and row["sourceCopy"] == "character:b" for row in routes)
    assert all("variant" not in row for row in routes)
    assert routes[0]["prerequisite"] == "quest:gate"
    assert routes[0]["keywords"] == "favor"
    assert "prerequisite" not in routes[1]


def test_chain_predecessor_resources_and_completion_consequences_are_distinct(
    panel_db: tuple[Writer, QuestRepository],
) -> None:
    writer, repo = panel_db
    writer.insert_quest_variants(
        [
            _variant("Target"),
            _variant("Predecessor", "quest:two", assign_new_quest_on_complete_stable_key="quest:one"),
            _variant("Not a predecessor", "quest:two"),
        ]
    )
    writer.insert_quest_acquisition_sources(
        [
            {
                "quest_stable_key": "quest:one",
                "method": "quest_chain",
                "source_type": "quest",
                "source_stable_key": "quest:two",
            }
        ]
    )
    writer.insert_quest_complete_other_quests(
        [{"quest_variant_resource_name": "Target", "completed_quest_stable_key": "quest:gate"}]
    )
    _turnin(writer)
    rows = _panel_rows(writer, repo)["quest:one"]
    assert {
        "type": "acquisition",
        "method": "quest_chain",
        "source": "quest:two",
        "sourceKind": "quest",
        "sourceVariant": "Predecessor",
    } in rows
    assert {"type": "completes", "variant": "Target", "quest": "quest:gate"} in rows
    assert not any("prerequisite" in row for row in rows)


def test_partial_turnin_route_only_belongs_to_flagged_resources(panel_db: tuple[Writer, QuestRepository]) -> None:
    writer, repo = panel_db
    writer.insert_quest_variants(
        [
            _variant("Partial", assign_this_quest_on_partial_complete=1, dialog_on_partial_success="Bring more"),
            _variant("Other", assign_this_quest_on_partial_complete=1, dialog_on_partial_success=""),
            _variant("Single", assign_this_quest_on_partial_complete=1, dialog_on_partial_success="Bring more"),
            _variant("Empty", assign_this_quest_on_partial_complete=1, dialog_on_partial_success="Bring more"),
        ]
    )
    writer.insert_quest_required_items(
        [
            {
                "quest_variant_resource_name": resource,
                "required_slot": 0,
                "item_stable_key": "item:required",
                "quantity": quantity,
            }
            for resource, quantity in (("Partial", 2), ("Other", 2), ("Single", 1))
        ]
    )
    writer.insert_quest_acquisition_sources(
        [
            {
                "quest_stable_key": "quest:one",
                "method": "partial_turnin",
                "source_type": "character",
                "source_stable_key": "character:a",
            }
        ]
    )
    _turnin(writer)
    rows = _panel_rows(writer, repo)["quest:one"]
    assert [row["variant"] for row in rows if row["type"] == "acquisition"] == ["Partial"]
    assert (
        next(row for row in rows if row["type"] == "variant" and row["variant"] == "Partial")["partialAssigns"] is True
    )
    assert (
        next(row for row in rows if row["type"] == "variant" and row["variant"] == "Other")["partialAssigns"] is False
    )
    assert all(
        row["partialAssigns"] is False
        for row in rows
        if row["type"] == "variant" and row["variant"] in {"Single", "Empty"}
    )


def test_completion_dialog_gate_and_scripted_notes_are_preserved(panel_db: tuple[Writer, QuestRepository]) -> None:
    writer, repo = panel_db
    writer.insert_quest_variants([_variant("Target")])
    writer.insert_quest_completion_sources(
        [
            {
                "quest_stable_key": "quest:one",
                "method": "talk",
                "source_type": "character",
                "source_stable_key": "character:b",
                "note": None,
            },
            {
                "quest_stable_key": "quest:one",
                "method": "scripted",
                "source_type": "scripted",
                "source_stable_key": None,
                "note": "Event puzzle",
            },
        ]
    )
    writer.insert_character_dialogs(
        [
            {
                "character_stable_key": "character:b",
                "dialog_index": 2,
                "keywords": "light",
                "complete_quest_stable_key": "quest:one",
                "required_quest_stable_key": "quest:gate",
            }
        ]
    )
    rows = _panel_rows(writer, repo)["quest:one"]
    completion = [row for row in rows if row["type"] == "completion" and row["method"] == "talk"]
    assert completion[0]["prerequisite"] == "quest:gate"
    assert completion[0]["keywords"] == "light"
    assert {"type": "completion", "method": "scripted", "note": "Event puzzle"} in rows


def test_requirement_provenance_resolves_to_a_real_quest_identity(panel_db: tuple[Writer, QuestRepository]) -> None:
    writer, repo = panel_db
    writer.insert_quest_variants([_variant("Resource A")])
    writer.insert_quest_required_items(
        [
            {
                "quest_variant_resource_name": "Resource A",
                "required_slot": 0,
                "item_stable_key": "item:eye",
                "quantity": 3,
            }
        ]
    )

    _panel_rows(writer, repo)
    sources = ItemProvenanceRepository(repo.db).get_uses("item:eye")
    known_quests = {quest.stable_key for quest in repo.get_quests_for_wiki_generation()}

    assert [source.target_stable_key for source in sources] == ["quest:one"]
    assert all(source.target_stable_key in known_quests for source in sources)


def test_excluded_inactive_groups_do_not_become_completion_sources(panel_db: tuple[Writer, QuestRepository]) -> None:
    writer, repo = panel_db
    writer.insert_quest_variants([_variant("Target")])
    writer.conn.execute(
        "UPDATE character_deduplications SET group_key = 'character:backup' "
        "WHERE member_stable_key = 'character:backup'"
    )
    writer.conn.commit()
    writer.insert_character_spawns(
        [
            {
                "character_stable_key": "character:backup",
                "spawn_point_stable_key": "placed-backup",
                "is_directly_placed": 1,
            }
        ]
    )
    writer.insert_quest_completion_sources(
        [
            {
                "quest_stable_key": "quest:one",
                "method": "item_turnin",
                "source_type": "character",
                "source_stable_key": key,
            }
            for key in ("character:a", "character:backup")
        ]
    )

    routes = [row for row in _panel_rows(writer, repo)["quest:one"] if row["type"] == "completion"]

    assert [row["source"] for row in routes] == ["character:a"]


@pytest.mark.parametrize("unconditional", [False, True])
def test_furniture_completion_requires_the_furnished_room_unless_also_unconditional(
    panel_db: tuple[Writer, QuestRepository], unconditional: bool
) -> None:
    writer, repo = panel_db
    writer.insert_quest_variants([_variant("Target")])
    writer.insert_items([{"stable_key": "item:set", "display_name": "Test set", "image_name": "Test set"}])
    placements = [
        {
            "character_stable_key": "character:b",
            "spawn_point_stable_key": room,
            "is_directly_placed": 1,
            "furniture_item_stable_key": "item:set",
            "furniture_slot": room,
        }
        for room in ("L1", "R4")
    ]
    if unconditional:
        placements.append(
            {
                "character_stable_key": "character:b",
                "spawn_point_stable_key": "unconditional",
                "is_directly_placed": 1,
                "furniture_item_stable_key": None,
                "furniture_slot": None,
            }
        )
    writer.insert_character_spawns(placements)
    writer.insert_quest_completion_sources(
        [
            {
                "quest_stable_key": "quest:one",
                "method": "item_turnin",
                "source_type": "character",
                "source_stable_key": "character:b",
            }
        ]
    )

    routes = [row for row in _panel_rows(writer, repo)["quest:one"] if row["type"] == "completion"]

    assert routes
    assert all(row["source"] == "character:a" and row["sourceCopy"] == "character:b" for row in routes)
    if unconditional:
        assert len(routes) == 1
        assert "furniture" not in routes[0] and "room" not in routes[0]
    else:
        assert len(routes) == 2
        assert {row["furniture"] for row in routes} == {"item:set"}
        assert {row["room"] for row in routes} == {"L1", "R4"}


@pytest.mark.parametrize("method", ["talk", "read", "zone", "death", "shout", "chain", "scripted"])
def test_finishquest_without_turnin_does_not_grant_configured_rewards(
    panel_db: tuple[Writer, QuestRepository], method: str
) -> None:
    writer, repo = panel_db
    writer.insert_quest_variants(
        [
            _variant(
                "Configured",
                xp_on_complete=25,
                gold_on_complete=7,
                item_on_complete_stable_key="item:unused",
                kill_turn_in_holder=1,
                drop_invuln_on_holder=1,
            )
        ]
    )
    writer.insert_quest_completion_sources(
        [
            {
                "quest_stable_key": "quest:one",
                "method": method,
                "source_type": "character",
                "source_stable_key": "character:a",
            }
        ]
    )

    variant = next(row for row in _panel_rows(writer, repo)["quest:one"] if row["type"] == "variant")

    assert variant["experience"] == 0 and variant["gold"] == 0
    assert "item" not in variant and "quantity" not in variant
    assert variant["killsHolder"] is False and variant["dropsInvulnerability"] is False
    assert writer.conn.execute("SELECT xp_on_complete FROM quest_variants").fetchone()[0] == 25


@pytest.mark.parametrize("with_talk", [False, True])
def test_zero_required_items_and_mixed_modes_keep_reachable_turnin_rewards(
    panel_db: tuple[Writer, QuestRepository], with_talk: bool
) -> None:
    writer, repo = panel_db
    writer.insert_quest_variants(
        [
            _variant(
                "Empty requirements", xp_on_complete=25, gold_on_complete=7, item_on_complete_stable_key="item:reward"
            )
        ]
    )
    _turnin(writer)
    if with_talk:
        writer.insert_quest_completion_sources(
            [
                {
                    "quest_stable_key": "quest:one",
                    "method": "talk",
                    "source_type": "character",
                    "source_stable_key": "character:b",
                }
            ]
        )

    rows = _panel_rows(writer, repo)["quest:one"]
    variant = next(row for row in rows if row["type"] == "variant")

    assert not any(row["type"] == "required" for row in rows)
    assert variant["experience"] == 25 and variant["gold"] == 7
    assert variant["item"] == "item:reward" and variant["quantity"] == 1
    assert variant["rewardMethod"] == "item_turnin"
    assert {row["method"] for row in rows if row["type"] == "completion"} == (
        {"item_turnin", "talk"} if with_talk else {"item_turnin"}
    )


def test_dialog_giveitem_is_a_distinct_reward_with_executed_gates(panel_db: tuple[Writer, QuestRepository]) -> None:
    writer, repo = panel_db
    writer.insert_quest_variants(
        [
            _variant("Dialog quest", xp_on_complete=25, item_on_complete_stable_key="item:configured"),
            _variant("Dialog assignment", "quest:two", repeatable=0),
        ]
    )
    writer.insert_quest_completion_sources(
        [
            {
                "quest_stable_key": "quest:one",
                "method": "talk",
                "source_type": "character",
                "source_stable_key": "character:a",
            }
        ]
    )
    writer.insert_character_dialogs(
        [
            {
                "character_stable_key": "character:a",
                "dialog_index": 1,
                "complete_quest_stable_key": "quest:one",
                "assign_quest_stable_key": "quest:two",
                "give_item_stable_key": "item:actual",
                "required_quest_stable_key": "quest:gate",
                "keywords": "help",
            }
        ]
    )

    rows = _panel_rows(writer, repo)["quest:one"]
    variant = next(row for row in rows if row["type"] == "variant")
    reward = next(row for row in rows if row["type"] == "completion")

    assert variant["experience"] == 0 and "item" not in variant
    assert reward["item"] == "item:actual" and reward["quantity"] == 1
    assert reward["notOwnedItem"] == "item:actual"
    assert reward["blockedByQuest"] == "quest:two"
    assert reward["prerequisite"] == "quest:gate"
