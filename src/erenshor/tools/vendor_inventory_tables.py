#!/usr/bin/env python3
"""Generate paste-ready wiki vendor inventory tables from the clean database.

By default, the report contains only vendor pages whose fetched Store inventory
is missing or differs from the current database. Use ``--all`` to include every
vendor page.

Usage:
    uv run python src/tools/generate_vendor_inventory_tables.py
    uv run python src/tools/generate_vendor_inventory_tables.py --all
    uv run python src/tools/generate_vendor_inventory_tables.py --output /tmp/vendors.wiki
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast
from urllib.parse import quote

DEFAULT_DATABASE = Path("variants/main/erenshor-main.sqlite")
DEFAULT_FETCHED_DIR = Path("variants/main/wiki/fetched")
DEFAULT_OUTPUT = Path("wiki/vendor_inventory_tables.generated.wiki")

INVENTORY_QUERY = """
WITH inventory_sources AS (
    SELECT DISTINCT
        c.wiki_page_name AS vendor_page,
        cvi.item_stable_key AS item_key,
        NULL AS unlock_quest_page
    FROM characters c
    JOIN character_vendor_items cvi
        ON cvi.character_stable_key = c.stable_key
    WHERE c.wiki_page_name IS NOT NULL

    UNION ALL

    SELECT DISTINCT
        c.wiki_page_name AS vendor_page,
        qv.unlock_item_for_vendor_stable_key AS item_key,
        q.wiki_page_name AS unlock_quest_page
    FROM characters c
    JOIN character_vendor_quest_unlocks cvqu
        ON cvqu.character_stable_key = c.stable_key
    JOIN quests q
        ON q.stable_key = cvqu.quest_stable_key
    JOIN quest_variants qv
        ON qv.quest_stable_key = q.stable_key
    WHERE c.wiki_page_name IS NOT NULL
      AND qv.unlock_item_for_vendor_stable_key IS NOT NULL
)
SELECT
    inventory_sources.vendor_page,
    inventory_sources.unlock_quest_page,
    i.stable_key,
    i.display_name,
    i.wiki_page_name,
    i.required_slot,
    i.this_weapon_type,
    i.teach_spell_stable_key,
    i.teach_skill_stable_key,
    i.template,
    i.item_effect_on_click_stable_key,
    i.disposable,
    i.shield,
    i.item_value
FROM inventory_sources
JOIN items i
    ON i.stable_key = inventory_sources.item_key
ORDER BY
    inventory_sources.vendor_page COLLATE NOCASE,
    i.display_name COLLATE NOCASE,
    i.stable_key,
    inventory_sources.unlock_quest_page COLLATE NOCASE
"""

_STORE_TABLE_RE = re.compile(r"(?is)\{\|[^\n]*\n\|\+\s*Store inventory\s*\n(.*?)\n\|\}")
_ROW_SEPARATOR_RE = re.compile(r"(?m)^\|-\s*$")
_ITEM_LINK_RE = re.compile(r"\{\{\s*ItemLink\s*\|([^{}]*)\}\}", re.IGNORECASE)
_STORE_TABLE_BLOCK_RE = re.compile(r"(?is)\{\|[^\n]*\n\|\+\s*Store inventory\s*\n.*?\n\|\}")
_PAGE_LINK_RE = re.compile(r"\[\[([^]|#]+)(?:#[^]|]*)?(?:\|([^]]+))?\]\]")


@dataclass(frozen=True)
class ExistingInventoryItem:
    name: str
    item_type: str
    price: int | None


@dataclass
class InventoryItem:
    stable_key: str
    display_name: str
    wiki_page_name: str | None
    required_slot: str | None
    weapon_type: str | None
    teach_spell: str | None
    teach_skill: str | None
    is_template: bool
    click_effect: str | None
    disposable: bool
    shield: bool
    price: int | None
    unlock_quests: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class VendorInventory:
    page: str
    items: tuple[InventoryItem, ...]


@dataclass(frozen=True)
class Arguments:
    database: Path
    fetched_dir: Path
    output: Path
    include_all: bool


_CANONICAL_TYPES = {
    "Axe": "[[Weapons|Weapon]]",
    "Bow": "[[Weapons|Weapon]]",
    "Sword": "[[Weapons|Weapon]]",
    "Mace": "[[Weapons|Weapon]]",
    "Club": "[[Weapons|Weapon]]",
    "Dagger": "[[Weapons|Weapon]]",
    "Knife": "[[Weapons|Weapon]]",
    "Weapon": "[[Weapons|Weapon]]",
    "2-Handed Weapon": "[[Weapons|Weapon]]",
    "Primary or Secondary": "[[Weapons|Weapon]]",
    "Shield": "[[Armor]]",
    "Chest Armor": "[[Armor]]",
    "Chest armor": "[[Armor]]",
    "Leg Armor": "[[Armor]]",
    "Foot Armor": "[[Armor]]",
    "Foot": "[[Armor]]",
    "Hand Armor": "[[Armor]]",
    "Hands": "[[Armor]]",
    "Head": "[[Armor]]",
    "Head Armor": "[[Armor]]",
    "Arm Armor": "[[Armor]]",
    "Wrist Armor": "[[Armor]]",
    "Wrist armor": "[[Armor]]",
    "Waist Armor": "[[Armor]]",
    "Ring": "[[Armor]]",
    "Necklace": "[[Armor]]",
    "Armor": "[[Armor]]",
    "Aura": "[[Auras|Aura]]",
    "Auras": "[[Auras|Aura]]",
    "Skill Book": "[[Ability Books|Skill Book]]",
    "Spell Book": "[[Ability Books|Spell Book]]",
    "Spell Scroll": "[[Ability Books|Spell Scroll]]",
    "Consumable": "[[Consumables|Consumable]]",
    "Food": "[[Consumables|Consumable]]",
    "Drink": "[[Consumables|Consumable]]",
    "Potion": "[[Consumables|Potion]]",
    "Items": "[[Consumables|Consumable]]",
    "Mold": "[[Crafting|Mold]]",
    "Crafting": "[[Crafting]]",
    "Quest Items": "[[Quest Items|Quest Item]]",
    "Lore": "[[Lore Items|Lore]]",
    "Cosmetic": "[[:Category:Cosmetic Items|Cosmetic]]",
    "Summoning": "[[:Category:Items|Summoning]]",
    "Fishing Pole": "[[Fishing|Fishing Pole]]",
    "Fishing": "[[Fishing]]",
}

_ARMOR_SLOTS = frozenset({"chest", "leg", "foot", "hand", "head", "bracer", "arm", "waist", "ring", "neck"})


def parse_inventory_table(wikitext: str) -> tuple[ExistingInventoryItem, ...] | None:
    """Parse the first manually maintained Store inventory table on a page."""
    table_match = _STORE_TABLE_RE.search(wikitext)
    if table_match is None:
        return None

    items: list[ExistingInventoryItem] = []
    for row in _ROW_SEPARATOR_RE.split(table_match.group(1))[1:]:
        cells = _table_cells(row)
        if not cells:
            continue
        name = _item_name(cells[0])
        if name is None:
            continue
        price = next(
            (
                int(cleaned)
                for cell in reversed(cells[1:])
                if (cleaned := re.sub(r"<[^>]+>", "", cell).strip().replace(",", "")).isdigit()
            ),
            None,
        )
        items.append(
            ExistingInventoryItem(
                name=name,
                item_type=cells[1] if len(cells) >= 3 else "",
                price=price,
            )
        )
    return tuple(items)


def _table_cells(row: str) -> list[str]:
    cells: list[str] = []
    for line in row.splitlines():
        if line.startswith("|") and not line.startswith(("|+", "|-")):
            cells.extend(part.strip() for part in line[1:].split("||"))
    return cells


def _item_name(cell: str) -> str | None:
    item_link = _ITEM_LINK_RE.search(cell)
    if item_link is not None:
        args = [argument.strip() for argument in item_link.group(1).split("|")]
        for argument in args[1:]:
            name, separator, value = argument.partition("=")
            if separator and name.strip().casefold() == "text":
                return value.strip()
        return args[0] if args else None
    page_link = _PAGE_LINK_RE.search(cell)
    if page_link is None:
        return None
    return (page_link.group(2) or page_link.group(1)).strip()


def load_vendor_inventories(database: Path) -> tuple[VendorInventory, ...]:
    """Load and deduplicate base plus quest-unlocked inventory rows."""
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        rows = cast("list[sqlite3.Row]", connection.execute(INVENTORY_QUERY).fetchall())
    finally:
        connection.close()

    items_by_vendor: dict[str, dict[str, InventoryItem]] = defaultdict(dict)
    for row in rows:
        page = cast("str", row["vendor_page"])
        stable_key = cast("str", row["stable_key"])
        item = items_by_vendor[page].get(stable_key)
        if item is None:
            item = InventoryItem(
                stable_key=stable_key,
                display_name=cast("str", row["display_name"]),
                wiki_page_name=cast("str | None", row["wiki_page_name"]),
                required_slot=cast("str | None", row["required_slot"]),
                weapon_type=cast("str | None", row["this_weapon_type"]),
                teach_spell=cast("str | None", row["teach_spell_stable_key"]),
                teach_skill=cast("str | None", row["teach_skill_stable_key"]),
                is_template=bool(cast("int | None", row["template"])),
                click_effect=cast("str | None", row["item_effect_on_click_stable_key"]),
                disposable=bool(cast("int | None", row["disposable"])),
                shield=bool(cast("int | None", row["shield"])),
                price=cast("int | None", row["item_value"]),
            )
            items_by_vendor[page][stable_key] = item
        unlock_quest_page = cast("str | None", row["unlock_quest_page"])
        if unlock_quest_page:
            item.unlock_quests.add(unlock_quest_page)

    inventories: list[VendorInventory] = []
    for page, keyed_items in items_by_vendor.items():
        items = _collapse_wiki_duplicates(keyed_items.values())
        inventories.append(VendorInventory(page=page, items=items))
    return tuple(sorted(inventories, key=lambda inventory: inventory.page.casefold()))


def _collapse_wiki_duplicates(items: Iterable[InventoryItem]) -> tuple[InventoryItem, ...]:
    selected: dict[tuple[str, int | None], InventoryItem] = {}
    for item in items:
        identity = (item.wiki_page_name or item.display_name, item.price)
        previous = selected.get(identity)
        if previous is None or item.stable_key < previous.stable_key:
            selected[identity] = item
        elif item.unlock_quests:
            previous.unlock_quests.update(item.unlock_quests)
    return tuple(sorted(selected.values(), key=lambda item: (item.display_name.casefold(), item.stable_key)))


def load_existing_tables(
    inventories: tuple[VendorInventory, ...], fetched_dir: Path
) -> dict[str, tuple[ExistingInventoryItem, ...] | None]:
    """Read the fetched table corresponding to each current vendor page."""
    result: dict[str, tuple[ExistingInventoryItem, ...] | None] = {}
    for inventory in inventories:
        encoded_page = quote(inventory.page, safe="")
        path = fetched_dir / f"{encoded_page}.txt"
        result[inventory.page] = parse_inventory_table(path.read_text(encoding="utf-8")) if path.is_file() else None
    return result


def existing_type_index(
    existing_tables: dict[str, tuple[ExistingInventoryItem, ...] | None],
) -> dict[str, str]:
    """Index established labels, preferring specific types over General Item."""
    candidates: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for table in existing_tables.values():
        if table is None:
            continue
        for item in table:
            candidates[item.name][item.item_type] += 1
    return {
        name: min(
            labels,
            key=lambda label: (
                _visible_label(label) == "General Item",
                -labels[label],
                label.casefold(),
            ),
        )
        for name, labels in candidates.items()
    }


def inventory_is_current(
    inventory: VendorInventory,
    existing: tuple[ExistingInventoryItem, ...] | None,
) -> bool:
    if existing is None:
        return False
    current_rows = sorted(
        ((item.display_name, item.price) for item in inventory.items),
        key=lambda row: row[0].casefold(),
    )
    existing_rows = sorted(
        ((item.name, item.price) for item in existing),
        key=lambda row: row[0].casefold(),
    )
    return current_rows == existing_rows


def item_type(item: InventoryItem, known_types: dict[str, str]) -> str:
    """Render the table's human-facing item type using game fields first."""
    semantic_type = _semantic_item_type(item)
    if semantic_type is not None:
        return semantic_type
    return _general_item_type(item, known_types)


def _semantic_item_type(item: InventoryItem) -> str | None:
    name = item.display_name.casefold()
    slot = (item.required_slot or "").casefold()
    weapon_type = (item.weapon_type or "").casefold()

    special_type = None
    if item.teach_spell:
        special_type = "[[Ability Books|Spell Scroll]]"
    elif item.teach_skill:
        special_type = "[[Ability Books|Skill Book]]"
    elif slot == "aura":
        special_type = "[[Auras|Aura]]"
    elif item.is_template or name.startswith("mold:"):
        special_type = "[[Crafting|Mold]]"
    if special_type is not None:
        return special_type
    if item.shield or slot in _ARMOR_SLOTS:
        return "[[Armor]]"
    if weapon_type != "none" or slot in {"primary", "primaryorsecondary", "secondary"}:
        return "[[Weapons|Weapon]]"
    return None


def _general_item_type(item: InventoryItem, known_types: dict[str, str]) -> str:
    name = item.display_name.casefold()
    old_label = _visible_label(known_types.get(item.display_name))
    if old_label in _CANONICAL_TYPES:
        return _CANONICAL_TYPES[old_label]
    if item.disposable or item.click_effect:
        return "[[Consumables|Consumable]]"
    if "lamp" in name:
        return "[[:Category:Cosmetic Items|Cosmetic]]"
    if "arena fee" in name:
        return "[[Quest Items|Quest Item]]"
    if any(token in name for token in (" set", "smithy", "resting place", "game room")):
        return "[[Furniture]]"
    return "[[:Category:Items|General Item]]"


def _visible_label(wikitext: str | None) -> str | None:
    if not wikitext:
        return None
    links: list[str] = re.findall(r"\[\[(?:[^]|]+\|)?([^]]+)\]\]", wikitext)
    if links:
        return links[-1].strip()
    return wikitext.replace("[[", "").replace("]]", "").strip() or None


def render_report(
    inventories: tuple[VendorInventory, ...],
    existing_tables: dict[str, tuple[ExistingInventoryItem, ...] | None],
    *,
    include_all: bool,
) -> tuple[str, int, int]:
    known_types = existing_type_index(existing_tables)
    selected = tuple(
        inventory
        for inventory in inventories
        if include_all or not inventory_is_current(inventory, existing_tables[inventory.page])
    )
    rows = sum(len(inventory.items) for inventory in selected)
    omitted = len(inventories) - len(selected)
    scope = "all current vendor pages" if include_all else "stale or missing fetched tables"
    lines = [
        "<!-- Generated by src/tools/generate_vendor_inventory_tables.py. Do not edit directly. -->",
        "Vendor inventory tables — current main database",
        "",
        f"{len(selected)} pages included ({scope}); {omitted} current fetched tables omitted.",
        "",
    ]
    for inventory in selected:
        lines.extend(_render_inventory(inventory, known_types))
    return "\n".join(lines).rstrip() + "\n", len(selected), rows


def _render_inventory(inventory: VendorInventory, known_types: dict[str, str]) -> list[str]:
    url = "https://erenshor.wiki.gg/wiki/" + quote(inventory.page.replace(" ", "_"), safe="_():")
    return [
        f"== {inventory.page} ==",
        url,
        "",
        *render_inventory_table(inventory, known_types).splitlines(),
        "",
        "",
    ]


def render_inventory_table(inventory: VendorInventory, known_types: dict[str, str]) -> str:
    """Render one paste-ready Store inventory wikitable."""
    lines = [
        '{| class="wikitable"',
        "|+Store inventory",
        "!Item name",
        "!Item type",
        "!Price",
    ]
    has_unlock_conditions = any(item.unlock_quests for item in inventory.items)
    if has_unlock_conditions:
        lines.append("!Unlock condition")
    sorted_items = sorted(
        inventory.items,
        key=lambda item: (
            (_visible_label(item_type(item, known_types)) or "").casefold(),
            item.price is None,
            item.price or 0,
            item.display_name.casefold(),
        ),
    )
    for item in sorted_items:
        price = "" if item.price is None else str(item.price)
        row = [
            "|-",
            f"|{_item_link(item)}",
            f"|{item_type(item, known_types)}",
            f"|{price}",
        ]
        if has_unlock_conditions:
            unlock_condition = "<br>".join(f"Complete [[{quest}]]" for quest in sorted(item.unlock_quests))
            row.append(f"|{unlock_condition}")
        lines.extend(row)
    lines.append("|}")
    return "\n".join(lines)


def replace_inventory_table(wikitext: str, table: str) -> str:
    """Replace one Store inventory table or insert it before trailing categories."""
    existing = _STORE_TABLE_BLOCK_RE.search(wikitext)
    if existing is not None:
        return f"{wikitext[: existing.start()]}{table}{wikitext[existing.end() :]}"

    category_start = _trailing_category_start(wikitext)
    before = wikitext[:category_start].rstrip()
    after = wikitext[category_start:].lstrip()
    if after:
        return f"{before}\n\n{table}\n\n{after.rstrip()}\n"
    return f"{before}\n\n{table}\n"


def _trailing_category_start(wikitext: str) -> int:
    lines = wikitext.splitlines(keepends=True)
    index = len(lines)
    found_category = False
    while index:
        line = lines[index - 1].strip()
        if re.fullmatch(r"\[\[Category:[^\]]+\]\]", line):
            found_category = True
            index -= 1
        elif not line and found_category:
            index -= 1
        else:
            break
    return sum(len(line) for line in lines[:index]) if found_category else len(wikitext)


def _item_link(item: InventoryItem) -> str:
    page = item.wiki_page_name or item.display_name
    args = [page]
    if page != item.display_name:
        args.append(f"text={item.display_name}")
    args.append(f"stablekey={item.stable_key}")
    return "{{ItemLink|" + "|".join(args) + "}}"


def parse_args() -> Arguments:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    _ = parser.add_argument("--fetched-dir", type=Path, default=DEFAULT_FETCHED_DIR)
    _ = parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    _ = parser.add_argument("--all", action="store_true", help="include vendors whose fetched tables already match")
    namespace = parser.parse_args()
    return Arguments(
        database=cast("Path", namespace.database),
        fetched_dir=cast("Path", namespace.fetched_dir),
        output=cast("Path", namespace.output),
        include_all=cast("bool", namespace.all),
    )


def main() -> int:
    args = parse_args()
    inventories = load_vendor_inventories(args.database)
    existing_tables = load_existing_tables(inventories, args.fetched_dir)
    report, page_count, row_count = render_report(
        inventories,
        existing_tables,
        include_all=args.include_all,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _ = args.output.write_text(report, encoding="utf-8")
    print(f"{args.output}: {page_count} vendor tables, {row_count} inventory rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
