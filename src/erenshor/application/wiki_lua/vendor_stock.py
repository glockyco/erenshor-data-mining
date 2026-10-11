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

VENDOR_STOCK = DataView(
    module="VendorStock",
    description="What each vendor sells, sorted by type, price, and item name.",
    entity="vendor character",
    fields=(
        ViewField("item", "key", "The item."),
        ViewField("price", "integer", "The gold that the vendor asks for one item."),
        ViewField("type", "text", "The item's kind, as Module:Erenshor/Data/Items names it."),
        ViewField("typePage", "text", "The page that lists the items of that kind.", optional=True),
        ViewField(
            "quests",
            "keys",
            "The quests whose completion adds the item to the stock. Absent when the item is always in stock.",
            optional=True,
        ),
    ),
)

# The pages that list the items of each kind. General items have none.
_KIND_PAGES: Mapping[str, str] = {
    "Weapon": "Weapons",
    "Armor": "Armor",
    "Charm": "Charms",
    "Aura": "Auras",
    "Spell Scroll": "Ability Books",
    "Skill Book": "Ability Books",
    "Consumable": "Consumables",
    "Mold": "Crafting",
}


class VendorStockRepository(Protocol):
    """Repository method needed for the vendor stock view."""

    def get_vendor_stock(self) -> list[tuple[str, str, str | None]]: ...


def build_vendor_stock_rows(
    stock: Iterable[tuple[str, str, str | None]], items_by_key: Mapping[str, Item]
) -> dict[str, list[dict[str, object]]]:
    """Return each vendor's rows. An item that is always in stock carries no quests."""
    always: set[tuple[str, str]] = set()
    quests: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for vendor_key, item_key, quest_key in stock:
        if quest_key is None:
            always.add((vendor_key, item_key))
        else:
            quests[vendor_key, item_key].add(quest_key)

    rows_by_vendor: defaultdict[str, list[tuple[tuple[str, int, str], dict[str, object]]]] = defaultdict(list)
    for vendor_key, item_key in always | quests.keys():
        item = items_by_key.get(item_key)
        if item is None:
            raise ValueError(f"{vendor_key} sells {item_key}, which has no wiki page")
        kind = item_kind_label(item)
        row: dict[str, object] = {"item": item_key, "price": item.item_value, "type": kind}
        if kind in _KIND_PAGES:
            row["typePage"] = _KIND_PAGES[kind]
        if (vendor_key, item_key) not in always:
            row["quests"] = sorted(quests[vendor_key, item_key])
        name = (item.display_name or item.item_name or item_key).casefold()
        rows_by_vendor[vendor_key].append(((kind.casefold(), item.item_value or 0, name), row))
    return {
        vendor: [row for _, row in sorted(rows, key=lambda entry: entry[0])] for vendor, rows in rows_by_vendor.items()
    }


def write_vendor_stock_module(
    repo: VendorStockRepository, items: Iterable[Item], known_keys: Collection[str], output_root: Path
) -> Path:
    """Write ``Data/VendorStock.lua`` below an output root."""
    rows = build_vendor_stock_rows(repo.get_vendor_stock(), {item.stable_key: item for item in items})
    output_path = output_root / "Erenshor" / "Data" / "VendorStock.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(view_module_text(VENDOR_STOCK, rows, known_keys), encoding="utf-8")
    return output_path
