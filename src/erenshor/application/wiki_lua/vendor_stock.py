"""Generate the vendor stock view: what each vendor sells."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.items import item_kind_label
from erenshor.application.wiki_lua.views import DataView, ViewField, view_module_text

if TYPE_CHECKING:
    from erenshor.domain.entities.item import Item
    from erenshor.domain.value_objects.source_info import SourceInfo
    from erenshor.domain.value_objects.vendor_stock import VendorStockEntry

VENDOR_STOCK = DataView(
    module="VendorStock",
    description="What each vendor sells, sorted by type, price, and item name.",
    entity="vendor character",
    fields=(
        ViewField("item", "key", "The item."),
        ViewField("price", "integer", "The gold that the vendor asks for one item."),
        ViewField(
            "type",
            "text",
            "The item's kind, as Module:Erenshor/Data/Items names it. A general item that smithing uses as a mold, "
            "that recipes or quests use, or that players read, is Mold, Crafting, Quest Item, or Lore instead.",
        ),
        ViewField("typePage", "text", "The page that lists the items of that type.", optional=True),
        ViewField(
            "quests",
            "keys",
            "The quests whose completion adds the item to the stock. Absent when the item is always in stock.",
            optional=True,
        ),
        ViewField(
            "furniture",
            "keys",
            "The Reliquary furniture sets whose placed vendor sells the item. Absent when every copy of the vendor "
            "in the game sells it.",
            optional=True,
        ),
    ),
)

# The pages that list the items of each type. General items have none.
_TYPE_PAGES: Mapping[str, str] = {
    "Weapon": "Weapons",
    "Armor": "Armor",
    "Charm": "Charms",
    "Aura": "Auras",
    "Spell Scroll": "Ability Books",
    "Skill Book": "Ability Books",
    "Consumable": "Consumables",
    "Mold": "Crafting",
    "Crafting": "Crafting",
    "Quest Item": "Quest Items",
    "Lore": "Lore Items",
    "Cosmetic": "Cosmetic Items",
}


class VendorStockRepository(Protocol):
    """Repository method needed for the vendor stock view."""

    def get_vendor_stock(self) -> list[VendorStockEntry]: ...


def item_type(item: Item, uses: Collection[str], molds: Collection[str]) -> str:
    """The item's kind, or for a general item what it is for: Mold, Crafting, Quest Item, or Lore.

    ``uses`` holds the use types of the item's ``usedIn`` rows in Data/Items,
    and ``molds`` the items that smithing upgrades with, such as Mold: An
    Otherwordly Box, which the game does not flag as a template.
    """
    kind = item_kind_label(item)
    if kind != "General":
        return kind
    if item.stable_key in molds:
        return "Mold"
    if "craft_material" in uses or item.fuel_source:
        return "Crafting"
    if "quest_requirement" in uses or item.complete_on_read_stable_key or item.assign_quest_on_read_stable_key:
        return "Quest Item"
    if item.book_title:
        return "Lore"
    return kind


def build_vendor_stock_rows(
    stock: Iterable[VendorStockEntry],
    items_by_key: Mapping[str, Item],
    uses_by_item: Mapping[str, Collection[str]],
    molds: Collection[str],
) -> dict[str, list[dict[str, object]]]:
    """Return each vendor's rows.

    An item that a copy of the vendor always has carries no quests. An item that
    only some copies sell carries the Reliquary furniture sets that place those
    copies. Generation fails when such an item has a seller without furniture,
    because a row cannot say which copy sells it.
    """
    copies: defaultdict[str, set[str]] = defaultdict(set)
    furniture_of: dict[str, str | None] = {}
    sellers: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    always: set[tuple[str, str]] = set()
    quests: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for entry in stock:
        key = (entry.vendor_key, entry.item_key)
        copies[entry.vendor_key].add(entry.copy_key)
        furniture_of[entry.copy_key] = entry.furniture_key
        sellers[key].add(entry.copy_key)
        if entry.quest_key is None:
            always.add(key)
        else:
            quests[key].add(entry.quest_key)

    rows_by_vendor: defaultdict[str, list[tuple[tuple[str, int, str], dict[str, object]]]] = defaultdict(list)
    for (vendor_key, item_key), selling in sellers.items():
        item = items_by_key.get(item_key)
        if item is None:
            raise ValueError(f"{vendor_key} sells {item_key}, which has no wiki page")
        kind = item_type(item, uses_by_item.get(item_key, ()), molds)
        row: dict[str, object] = {"item": item_key, "price": item.item_value, "type": kind}
        if kind in _TYPE_PAGES:
            row["typePage"] = _TYPE_PAGES[kind]
        if (vendor_key, item_key) not in always:
            row["quests"] = sorted(quests[vendor_key, item_key])
        if selling != copies[vendor_key]:
            furniture = {furniture_of[copy] for copy in selling}
            if None in furniture:
                raise ValueError(
                    f"Only some copies of {vendor_key} sell {item_key}, and not every seller is placed by furniture"
                )
            row["furniture"] = sorted(key for key in furniture if key is not None)
        name = (item.display_name or item.item_name or item_key).casefold()
        rows_by_vendor[vendor_key].append(((kind.casefold(), item.item_value or 0, name), row))
    return {
        vendor: [row for _, row in sorted(rows, key=lambda entry: entry[0])] for vendor, rows in rows_by_vendor.items()
    }


def write_vendor_stock_module(
    repo: VendorStockRepository,
    items: Iterable[Item],
    sources_by_item: Mapping[str, SourceInfo],
    known_keys: Collection[str],
    output_root: Path,
) -> Path:
    """Write ``Data/VendorStock.lua`` below an output root."""
    uses_by_item = {key: {use.use_type for use in sources.used_in} for key, sources in sources_by_item.items()}
    molds = {
        use.target_key
        for sources in sources_by_item.values()
        for use in sources.used_in
        if use.use_type == "upgrade_material"
    }
    items_by_key = {item.stable_key: item for item in items}
    rows = build_vendor_stock_rows(repo.get_vendor_stock(), items_by_key, uses_by_item, molds)
    output_path = output_root / "Erenshor" / "Data" / "VendorStock.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(view_module_text(VENDOR_STOCK, rows, known_keys), encoding="utf-8")
    return output_path
