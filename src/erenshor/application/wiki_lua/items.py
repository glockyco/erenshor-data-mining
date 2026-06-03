"""Generate compact Lua data modules for item wiki pages."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from erenshor.application.wiki_lua.lua_writer import module_text
from erenshor.domain.entities.item_kind import classify_item_kind

if TYPE_CHECKING:
    from erenshor.domain.entities.item import Item
    from erenshor.domain.entities.item_stats import ItemStats


class ItemDataRepository(Protocol):
    """Repository methods needed to build the item data module."""

    def get_items_for_wiki_generation(self) -> list[Item]: ...

    def get_item_stats(self, stable_key: str) -> list[ItemStats]: ...

    def get_item_classes(self, stable_key: str) -> list[str]: ...


LuaData = dict[str, object]

ITEMS_PER_SHARD = 200

_ITEM_FIELD_MAP = (
    ("name", "display_name"),
    ("page", "wiki_page_name"),
    ("image", "image_name"),
    ("slot", "required_slot"),
    ("weaponType", "this_weapon_type"),
    ("itemLevel", "item_level"),
    ("weaponDelay", "weapon_dly"),
    ("buyValue", "item_value"),
    ("sellValue", "sell_value"),
)

_ITEM_BOOL_FIELD_MAP = (
    ("stackable", "stackable"),
    ("unique", "is_unique"),
    ("shield", "shield"),
    ("wand", "is_wand"),
    ("bow", "is_bow"),
    ("template", "template"),
    ("disposable", "disposable"),
    ("relic", "relic"),
    ("noTradeNoDestroy", "no_trade_no_destroy"),
    ("fuelSource", "fuel_source"),
    ("unavailableToSimPlayers", "sim_players_cant_get"),
)

_ITEM_EFFECT_FIELD_MAP = (
    ("weaponProc", "weapon_proc_on_hit_stable_key"),
    ("wandEffect", "wand_effect_stable_key"),
    ("bowEffect", "bow_effect_stable_key"),
    ("clickEffect", "item_effect_on_click_stable_key"),
    ("skillUse", "item_skill_use_stable_key"),
    ("teachesSpell", "teach_spell_stable_key"),
    ("teachesSkill", "teach_skill_stable_key"),
    ("aura", "aura_stable_key"),
    ("wornEffect", "worn_effect_stable_key"),
    ("assignQuestOnRead", "assign_quest_on_read_stable_key"),
    ("completeQuestOnRead", "complete_on_read_stable_key"),
)

_STAT_FIELD_MAP = (
    ("weaponDamage", "weapon_dmg"),
    ("ac", "ac"),
    ("hp", "hp"),
    ("mana", "mana"),
    ("str", "str_"),
    ("end", "end_"),
    ("dex", "dex"),
    ("agi", "agi"),
    ("int", "int_"),
    ("wis", "wis"),
    ("cha", "cha"),
    ("res", "res"),
    ("mr", "mr"),
    ("er", "er"),
    ("pr", "pr"),
    ("vr", "vr"),
    ("strScaling", "str_scaling"),
    ("endScaling", "end_scaling"),
    ("dexScaling", "dex_scaling"),
    ("agiScaling", "agi_scaling"),
    ("intScaling", "int_scaling"),
    ("wisScaling", "wis_scaling"),
    ("chaScaling", "cha_scaling"),
    ("resistScaling", "resist_scaling"),
    ("mitigationScaling", "mitigation_scaling"),
)


def generate_items_modules(item_repo: ItemDataRepository) -> dict[str, str]:
    """Generate `Module:Erenshor/Data/Items` index and shard module content."""
    items = item_repo.get_items_for_wiki_generation()
    stats_by_item = {item.stable_key: item_repo.get_item_stats(item.stable_key) for item in items}
    classes_by_item = {item.stable_key: item_repo.get_item_classes(item.stable_key) for item in items}
    data = build_items_data(items, stats_by_item, classes_by_item)
    modules = {"Items.lua": module_text(data["index"])}
    shards = data["shards"]
    if not isinstance(shards, Mapping):
        raise TypeError("item shard data must be a mapping")
    for shard_name, shard_data in shards.items():
        modules[f"Items/{shard_name}.lua"] = module_text(shard_data)
    return modules


def write_items_modules(item_repo: ItemDataRepository, output_root: Path) -> list[Path]:
    """Write the generated item data index and shard modules below an output root."""
    output_dir = output_root / "Erenshor" / "Data"
    written_paths: list[Path] = []
    for relative_path, module in generate_items_modules(item_repo).items():
        output_path = output_dir / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(module, encoding="utf-8")
        written_paths.append(output_path)
    return written_paths


def build_items_data(
    items: Iterable[Item],
    stats_by_item: Mapping[str, list[ItemStats]],
    classes_by_item: Mapping[str, list[str]],
    *,
    items_per_shard: int = ITEMS_PER_SHARD,
) -> LuaData:
    """Build the serializable item index and shard tables for `mw.loadData()`."""
    if items_per_shard < 1:
        raise ValueError("items_per_shard must be at least 1")

    item_rows: dict[str, object] = {}
    by_name: dict[str, str] = {}
    by_page: defaultdict[str, list[str]] = defaultdict(list)

    for item in sorted(items, key=lambda candidate: candidate.stable_key):
        page = item.wiki_page_name
        if page is None:
            continue
        item_rows[item.stable_key] = _item_record(
            item=item,
            stats=stats_by_item.get(item.stable_key, []),
            classes=classes_by_item.get(item.stable_key, []),
        )
        by_page[page].append(item.stable_key)
        if item.display_name is not None:
            by_name.setdefault(item.display_name, item.stable_key)
        by_name.setdefault(page, item.stable_key)

    shards: dict[str, dict[str, object]] = {}
    item_shards: dict[str, str] = {}
    sorted_rows = sorted(item_rows.items())
    for start in range(0, len(sorted_rows), items_per_shard):
        shard_name = f"{(start // items_per_shard) + 1:03d}"
        shard_rows = dict(sorted_rows[start : start + items_per_shard])
        shards[shard_name] = shard_rows
        for stable_key in shard_rows:
            item_shards[stable_key] = shard_name

    return {
        "index": {
            "byName": dict(sorted(by_name.items())),
            "byPage": {page: sorted(stable_keys) for page, stable_keys in sorted(by_page.items())},
            "itemShards": item_shards,
            "shards": {shard_name: f"Module:Erenshor/Data/Items/{shard_name}" for shard_name in sorted(shards)},
        },
        "shards": shards,
    }


def _item_record(item: Item, stats: list[ItemStats], classes: list[str]) -> LuaData:
    row: LuaData = {}
    for lua_name, attr_name in _ITEM_FIELD_MAP:
        _put(row, lua_name, getattr(item, attr_name))
    for lua_name, attr_name in _ITEM_BOOL_FIELD_MAP:
        _put_bool(row, lua_name, getattr(item, attr_name))
    for lua_name, attr_name in _ITEM_EFFECT_FIELD_MAP:
        _put(row, lua_name, getattr(item, attr_name))

    item_kind = classify_item_kind(
        required_slot=item.required_slot,
        teach_spell=item.teach_spell_stable_key,
        teach_skill=item.teach_skill_stable_key,
        template_flag=item.template,
        click_effect=item.item_effect_on_click_stable_key,
        disposable=bool(item.disposable) if item.disposable is not None else None,
    )
    row["type"] = _item_kind_display(str(item_kind))

    summary_stat = _summary_stat(stats)
    if summary_stat is not None:
        _put(row, "damage", summary_stat.weapon_dmg)
        _put(row, "armor", summary_stat.ac)

    if classes:
        row["classes"] = sorted(classes)

    stat_rows = [_stat_record(stat) for stat in sorted(stats, key=lambda candidate: candidate.quality)]
    stat_rows = [stat for stat in stat_rows if len(stat) > 1]
    if stat_rows:
        row["stats"] = stat_rows

    return row


def _summary_stat(stats: list[ItemStats]) -> ItemStats | None:
    if not stats:
        return None
    for stat in stats:
        if stat.quality in {"Normal", "0"}:
            return stat
    return stats[0]


def _item_kind_display(item_kind: str) -> str:
    return {
        "skillbook": "Skill Book",
        "spellscroll": "Spell Scroll",
    }.get(item_kind, item_kind.capitalize())


def _stat_record(stat: ItemStats) -> LuaData:
    row: LuaData = {"quality": stat.quality}
    for lua_name, attr_name in _STAT_FIELD_MAP:
        _put(row, lua_name, getattr(stat, attr_name))
    return row


def _put(row: LuaData, key: str, value: object) -> None:
    if value is not None and value != "":
        row[key] = value


def _put_bool(row: LuaData, key: str, value: Any) -> None:
    if value is not None:
        row[key] = bool(value)
