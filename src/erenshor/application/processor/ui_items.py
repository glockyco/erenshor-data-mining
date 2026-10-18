"""Carry native UI slot references and their access routes into the clean database."""

from __future__ import annotations

import sqlite3

# Keep each native field explicit so a missing export cannot silently remove a source.
_TABLES = (
    (
        "UiItemSources",
        "ui_item_sources",
        (
            ("StableKey", "stable_key"),
            ("ComponentType", "component_type"),
            ("Scene", "scene"),
            ("HierarchyPath", "hierarchy_path"),
            ("Slot", "slot"),
            ("IconHierarchyPath", "icon_hierarchy_path"),
            ("SerializedItemStableKey", "serialized_item_stable_key"),
            ("SerializedQuantity", "serialized_quantity"),
            ("ReplenishItemStableKey", "replenish_item_stable_key"),
            ("ReplenishSourceKey", "replenish_source_key"),
            ("DisplayOnly", "display_only"),
            ("VendorSlot", "vendor_slot"),
            ("LootSlot", "loot_slot"),
            ("BankSlot", "bank_slot"),
            ("MouseSlot", "mouse_slot"),
            ("PlayerOwned", "player_owned"),
            ("NotInInventory", "not_in_inventory"),
            ("SlotType", "slot_type"),
        ),
    ),
    (
        "UiItemAccessTargets",
        "ui_item_access_targets",
        (
            ("StableKey", "stable_key"),
            ("Scene", "scene"),
            ("HierarchyPath", "hierarchy_path"),
            ("Tag", "tag"),
            ("ActiveSelf", "active_self"),
            ("ActiveInHierarchy", "active_in_hierarchy"),
            ("X", "x"),
            ("Y", "y"),
            ("Z", "z"),
        ),
    ),
)

_REQUIRED_FACTS = frozenset(
    {
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
    }
)


def process_ui_items(raw: sqlite3.Connection, clean: sqlite3.Connection) -> None:
    """Copy native references losslessly after validating export and code-fact prerequisites."""
    for raw_table, _, columns in _TABLES:
        actual = {str(row[1]) for row in raw.execute(f'PRAGMA table_info("{raw_table}")')}
        required = {source for source, _ in columns}
        if missing := sorted(required - actual):
            raise ValueError(
                f"Native UI export {raw_table} is missing required columns {missing}. "
                "Run 'erenshor extract export' with uiitemsources before building."
            )

    try:
        facts = {str(row[0]) for row in raw.execute("SELECT DISTINCT fact_id FROM code_facts")}
    except sqlite3.OperationalError as exc:
        raise ValueError("Native UI code facts are missing. Run 'erenshor extract code-facts' after export.") from exc
    if missing_facts := sorted(_REQUIRED_FACTS - facts):
        raise ValueError(
            f"Native UI code facts are missing: {missing_facts}. Run 'erenshor extract code-facts' after export."
        )

    for raw_table, clean_table, columns in _TABLES:
        source_columns = ", ".join(f'"{source}"' for source, _ in columns)
        target_columns = ", ".join(f'"{target}"' for _, target in columns)
        placeholders = ", ".join("?" for _ in columns)
        clean.executemany(
            f'INSERT INTO "{clean_table}" ({target_columns}) VALUES ({placeholders})',
            raw.execute(f'SELECT {source_columns} FROM "{raw_table}" ORDER BY StableKey'),
        )
