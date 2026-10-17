"""Native UI references survive the clean projection without inferred grants or stock."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from erenshor.application.processor.ui_items import process_ui_items
from erenshor.application.processor.writer import Writer

if TYPE_CHECKING:
    from pathlib import Path

_RAW_COLUMNS = {
    "UiItemSources": (
        "StableKey",
        "ComponentType",
        "Scene",
        "HierarchyPath",
        "Slot",
        "IconHierarchyPath",
        "SerializedItemStableKey",
        "SerializedQuantity",
        "ReplenishItemStableKey",
        "ReplenishSourceKey",
        "DisplayOnly",
        "VendorSlot",
        "LootSlot",
        "BankSlot",
        "MouseSlot",
        "PlayerOwned",
        "NotInInventory",
        "SlotType",
    ),
    "UiItemAccessTargets": (
        "StableKey",
        "Scene",
        "HierarchyPath",
        "Tag",
        "ActiveSelf",
        "ActiveInHierarchy",
        "X",
        "Y",
        "Z",
    ),
    "UiItemAccessActivations": (
        "StableKey",
        "TargetStableKey",
        "ActivatorStableKey",
        "Scene",
        "HierarchyPath",
        "QuestStableKey",
        "AlternativeQuestStableKey",
        "ItemStableKey",
    ),
}
_FACTS = (
    "ui.misc_reference",
    "ui.planning_reference",
    "ui.hide_slot_replenishment",
    "ui.planning_portal_not_reset",
    "ui.item_icon_pointer_access",
    "ui.item_icon_pickup",
    "ui.item_icon_pickup_quantity",
    "ui.item_icon_inventory_transfer",
    "ui.planning_desk_open",
    "ui.planning_access_quest",
    "ui.planning_access_alternative_quest",
    "ui.planning_access_item",
)


def _raw(missing_table: str | None = None, missing_column: tuple[str, str] | None = None) -> sqlite3.Connection:
    raw = sqlite3.connect(":memory:")
    raw.row_factory = sqlite3.Row
    for table, columns in _RAW_COLUMNS.items():
        if table == missing_table:
            continue
        declaration = ", ".join(f'"{column}"' for column in columns if (table, column) != missing_column)
        raw.execute(f'CREATE TABLE "{table}" ({declaration})')
    raw.execute("CREATE TABLE code_facts (fact_id TEXT, key TEXT, value TEXT)")
    raw.executemany("INSERT INTO code_facts VALUES (?, 'ok', 'true')", [(fact,) for fact in _FACTS])
    return raw


def test_ui_references_and_access_copy_losslessly(tmp_path: Path) -> None:
    raw = _raw()
    sources = [
        (
            "ui:hide",
            "ReplenishTMOGHide",
            "LoadScene",
            "UI/Hide",
            "MyIcon",
            "UI/Hide/Icon",
            "item:serialized seed",
            7,
            "item:replenished",
            "ui:misc",
            0,
            0,
            0,
            0,
            0,
            0,
            1,
            "General",
        ),
        (
            "ui:portal",
            "PlanningTableUI",
            "LoadScene",
            "UI/Planning",
            "Portal",
            "UI/Planning/Portal",
            "item:portal gift",
            3,
            None,
            None,
            1,
            0,
            0,
            0,
            0,
            1,
            1,
            "General",
        ),
        (
            "ui:empty",
            "PlanningTableUI",
            "OtherScene",
            "UI/Empty",
            "Portal",
            "UI/Empty/Portal",
            None,
            1,
            None,
            None,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            "General",
        ),
    ]
    raw.executemany("INSERT INTO UiItemSources VALUES (" + ",".join("?" * 18) + ")", sources)
    target = ("ui:desk", "Reliquary", "Rooms/Desk", "PlanningDesk", 0, 0, 1.25, 2.5, 3.75)
    raw.execute("INSERT INTO UiItemAccessTargets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", target)
    activation = (
        "ui:activation",
        "ui:desk",
        "ui:trigger",
        "Reliquary",
        "Trigger",
        "quest:claim",
        "quest:other",
        "item:key",
    )
    raw.execute("INSERT INTO UiItemAccessActivations VALUES (?, ?, ?, ?, ?, ?, ?, ?)", activation)
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    writer.conn.executemany(
        "INSERT INTO items (stable_key, display_name, image_name) VALUES (?, ?, '')",
        [(key, key) for key in ("item:serialized seed", "item:replenished", "item:portal gift", "item:key")],
    )
    writer.conn.executemany(
        "INSERT INTO quests (stable_key, display_name, image_name) VALUES (?, ?, '')",
        [(key, key) for key in ("quest:claim", "quest:other")],
    )

    process_ui_items(raw, writer.conn)

    assert [tuple(row) for row in writer.conn.execute("SELECT * FROM ui_item_sources ORDER BY stable_key")] == sorted(
        sources, key=lambda row: row[0]
    )
    assert tuple(writer.conn.execute("SELECT * FROM ui_item_access_targets").fetchone()) == target
    assert tuple(writer.conn.execute("SELECT * FROM ui_item_access_activations").fetchone()) == activation
    assert writer.conn.execute("SELECT COUNT(*) FROM item_acquisitions").fetchone()[0] == 0


@pytest.mark.parametrize("table", _RAW_COLUMNS)
def test_missing_raw_ui_table_stops_before_clean_writes(table: str) -> None:
    with pytest.raises(ValueError, match=f"Native UI export {table} is missing required columns"):
        process_ui_items(_raw(missing_table=table), sqlite3.connect(":memory:"))


@pytest.mark.parametrize(
    "table,column", [(table, column) for table, columns in _RAW_COLUMNS.items() for column in columns]
)
def test_missing_raw_ui_column_stops_before_clean_writes(table: str, column: str) -> None:
    with pytest.raises(ValueError, match=f"Native UI export {table} is missing required columns.*{column}"):
        process_ui_items(_raw(missing_column=(table, column)), sqlite3.connect(":memory:"))


@pytest.mark.parametrize("fact", _FACTS)
def test_missing_ui_fact_stops_before_clean_writes(fact: str) -> None:
    raw = _raw()
    raw.execute("DELETE FROM code_facts WHERE fact_id = ?", (fact,))
    with pytest.raises(ValueError, match="Native UI code facts are missing"):
        process_ui_items(raw, sqlite3.connect(":memory:"))


def test_missing_code_facts_table_stops_before_clean_writes() -> None:
    raw = _raw()
    raw.execute("DROP TABLE code_facts")
    with pytest.raises(ValueError, match="Native UI code facts are missing"):
        process_ui_items(raw, sqlite3.connect(":memory:"))
