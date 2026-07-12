"""Generate compact Lua data modules for item wiki pages."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from erenshor.application.wiki_lua.links import link_ref
from erenshor.application.wiki_lua.lua_writer import module_text
from erenshor.domain.entities.item_kind import ItemKind, classify_item_kind
from erenshor.domain.value_objects.source_info import ObtainedFromInfo, SourceInfo, UsedInInfo
from erenshor.shared.game_constants import TIER_ORDER_MAP, TIER_SORT_DEFAULT

if TYPE_CHECKING:
    from erenshor.domain.entities.item import Item
    from erenshor.domain.entities.item_stats import ItemStats
    from erenshor.domain.value_objects.crafting_recipe import CraftingRecipe
    from erenshor.domain.value_objects.wiki_link import ItemLink


class ItemDataRepository(Protocol):
    """Repository methods needed to build the item data module."""

    def get_items_for_wiki_generation(self) -> list[Item]: ...

    def get_item_stats(self, stable_key: str) -> list[ItemStats]: ...

    def get_item_classes(self, stable_key: str) -> list[str]: ...

    def get_crafting_recipe(self, stable_key: str) -> CraftingRecipe | None: ...


class ItemProvenanceItemRepository(Protocol):
    """Item repository methods needed for item source fields."""

    def get_recipes_rewarding_item(self, item_stable_key: str) -> list[ObtainedFromInfo]: ...

    def get_item_use_sources(self, item_stable_key: str) -> list[ObtainedFromInfo]: ...

    def get_classes_starting_with_item(self, item_stable_key: str) -> list[ObtainedFromInfo]: ...

    def get_crafting_material_sources(self, item_stable_key: str) -> list[UsedInInfo]: ...

    def get_item_smithing_special_uses(self, item_stable_key: str) -> list[UsedInInfo]: ...


class ItemProvenanceCharacterRepository(Protocol):
    """Character repository methods needed for item source fields."""

    def get_character_drop_sources(self, item_stable_key: str) -> list[ObtainedFromInfo]: ...

    def get_vendor_sources_for_item(self, item_stable_key: str) -> list[ObtainedFromInfo]: ...

    def get_characters_giving_item(self, item_stable_key: str) -> list[ObtainedFromInfo]: ...


class ItemProvenanceQuestRepository(Protocol):
    """Quest repository methods needed for item source fields."""

    def get_quest_reward_sources(self, item_stable_key: str) -> list[ObtainedFromInfo]: ...

    def get_quest_requirement_sources(self, item_stable_key: str) -> list[UsedInInfo]: ...


class ItemProvenanceZoneRepository(Protocol):
    """Zone methods needed for item obtainability source fields."""

    def get_mining_nodes_for_item(self, item_stable_key: str) -> list[ObtainedFromInfo]: ...

    def get_fishing_waters_for_item(self, item_stable_key: str) -> list[ObtainedFromInfo]: ...

    def get_item_bag_sources_for_item(self, item_stable_key: str) -> list[ObtainedFromInfo]: ...


LuaData = dict[str, object]

_ITEM_KIND_SHARDS = {
    ItemKind.WEAPON: "Weapons",
    ItemKind.ARMOR: "Armor",
    ItemKind.CHARM: "Charms",
    ItemKind.AURA: "Auras",
    ItemKind.SPELL_SCROLL: "SpellScrolls",
    ItemKind.SKILL_BOOK: "SkillBooks",
    ItemKind.CONSUMABLE: "Consumables",
    ItemKind.MOLD: "Molds",
    ItemKind.GENERAL: "General",
}

_ITEM_FIELD_MAP = (
    ("name", "display_name"),
    ("page", "wiki_page_name"),
    ("image", "image_name"),
    ("description", "lore"),
    ("bookTitle", "book_title"),
    ("slot", "required_slot"),
    ("weaponType", "this_weapon_type"),
    ("itemLevel", "item_level"),
    ("weaponDelay", "weapon_dly"),
    ("wandRange", "wand_range"),
    ("bowRange", "bow_range"),
    ("buyValue", "item_value"),
    ("castTime", "spell_cast_time"),
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
    ("mustBeEquippedToClick", "must_be_equipped_to_click"),
    ("playerCannotSell", "player_cannot_sell"),
    ("rareItem", "rare_item"),
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

_ITEM_EFFECT_CHANCE_FIELD_MAP = (
    ("weaponProcChance", "weapon_proc_chance"),
    ("wandProcChance", "wand_proc_chance"),
    ("bowProcChance", "bow_proc_chance"),
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

_RESIST_STAT_FIELDS = frozenset({"mr", "er", "pr", "vr"})


def generate_items_modules(
    item_repo: ItemDataRepository,
    sources_by_item: Mapping[str, SourceInfo] | None = None,
) -> dict[str, str]:
    """Generate `Module:Erenshor/Data/Items` index and shard module content."""

    items = item_repo.get_items_for_wiki_generation()
    stats_by_item = {item.stable_key: item_repo.get_item_stats(item.stable_key) for item in items}
    classes_by_item = {item.stable_key: item_repo.get_item_classes(item.stable_key) for item in items}
    recipes_by_item = {item.stable_key: item_repo.get_crafting_recipe(item.stable_key) for item in items}
    data = build_items_data(
        items,
        stats_by_item,
        classes_by_item,
        recipes_by_item=recipes_by_item,
        sources_by_item=sources_by_item,
    )

    modules = {"Items.lua": module_text(data["index"])}
    shards = cast("Mapping[str, LuaData]", data["shards"])
    for shard_name, shard_data in shards.items():
        modules[f"Items/{shard_name}.lua"] = module_text(shard_data)
    return modules


def write_items_modules(
    item_repo: ItemDataRepository,
    output_root: Path,
    sources_by_item: Mapping[str, SourceInfo] | None = None,
) -> list[Path]:
    """Write the generated item data index and shard modules below an output root."""
    output_dir = output_root / "Erenshor" / "Data"
    written_paths: list[Path] = []
    for relative_path, module in generate_items_modules(item_repo, sources_by_item=sources_by_item).items():
        output_path = output_dir / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(module, encoding="utf-8")
        written_paths.append(output_path)
    return written_paths


def build_item_sources_by_item(
    items: Iterable[Item],
    item_repo: ItemProvenanceItemRepository,
    character_repo: ItemProvenanceCharacterRepository,
    quest_repo: ItemProvenanceQuestRepository,
    zone_repo: ItemProvenanceZoneRepository,
) -> dict[str, SourceInfo]:
    """Build item-owned stable-keyed source metadata for each item."""
    sources_by_item: dict[str, SourceInfo] = {}
    for item in items:
        item_key = item.stable_key
        used_in = [
            *item_repo.get_crafting_material_sources(item_key),
            *quest_repo.get_quest_requirement_sources(item_key),
            *item_repo.get_item_smithing_special_uses(item_key),
        ]
        obtained_from = [
            *character_repo.get_character_drop_sources(item_key),
            *character_repo.get_vendor_sources_for_item(item_key),
            *character_repo.get_characters_giving_item(item_key),
            *quest_repo.get_quest_reward_sources(item_key),
            *item_repo.get_recipes_rewarding_item(item_key),
            *item_repo.get_item_use_sources(item_key),
            *zone_repo.get_mining_nodes_for_item(item_key),
            *zone_repo.get_fishing_waters_for_item(item_key),
            *zone_repo.get_item_bag_sources_for_item(item_key),
            *item_repo.get_classes_starting_with_item(item_key),
        ]
        sources_by_item[item_key] = SourceInfo(obtained_from=obtained_from, used_in=used_in)
    return sources_by_item


def build_items_data(
    items: Iterable[Item],
    stats_by_item: Mapping[str, list[ItemStats]],
    classes_by_item: Mapping[str, list[str]],
    recipes_by_item: Mapping[str, CraftingRecipe | None] | None = None,
    sources_by_item: Mapping[str, SourceInfo] | None = None,
) -> LuaData:
    """Build the serializable item index and semantic shard tables for `mw.loadData()`."""

    shards: defaultdict[str, dict[str, object]] = defaultdict(dict)
    by_key: dict[str, str] = {}

    for item in sorted(items, key=lambda candidate: candidate.stable_key):
        if item.wiki_page_name is None:
            continue
        shard_name = _item_shard_name(item)
        shards[shard_name][item.stable_key] = _item_record(
            item=item,
            stats=stats_by_item.get(item.stable_key, []),
            classes=classes_by_item.get(item.stable_key, []),
            recipe=recipes_by_item.get(item.stable_key) if recipes_by_item is not None else None,
            sources=sources_by_item.get(item.stable_key) if sources_by_item is not None else None,
        )
        by_key[item.stable_key] = shard_name

    return {
        "index": {"byKey": dict(sorted(by_key.items()))},
        "shards": {shard_name: dict(sorted(shard_rows.items())) for shard_name, shard_rows in sorted(shards.items())},
    }


def _item_shard_name(item: Item) -> str:
    return _ITEM_KIND_SHARDS[_item_kind(item)]


def _item_kind(item: Item) -> ItemKind:
    return classify_item_kind(
        required_slot=item.required_slot,
        teach_spell=item.teach_spell_stable_key,
        teach_skill=item.teach_skill_stable_key,
        template_flag=item.template,
        click_effect=item.item_effect_on_click_stable_key,
        disposable=bool(item.disposable) if item.disposable is not None else None,
    )


def _item_record(
    item: Item,
    stats: list[ItemStats],
    classes: list[str],
    recipe: CraftingRecipe | None,
    sources: SourceInfo | None,
) -> LuaData:
    row: LuaData = {}
    for lua_name, attr_name in _ITEM_FIELD_MAP:
        _put(row, lua_name, getattr(item, attr_name))
    for lua_name, attr_name in _ITEM_BOOL_FIELD_MAP:
        _put_bool(row, lua_name, getattr(item, attr_name))
    for lua_name, attr_name in _ITEM_EFFECT_FIELD_MAP:
        _put(row, lua_name, getattr(item, attr_name))
    for lua_name, attr_name in _ITEM_EFFECT_CHANCE_FIELD_MAP:
        _put(row, lua_name, getattr(item, attr_name))

    row["type"] = _item_kind_display(str(_item_kind(item)))

    summary_stat = _summary_stat(stats)
    if summary_stat is not None:
        _put(row, "damage", summary_stat.weapon_dmg)
        _put(row, "armor", summary_stat.ac)
    if classes:
        row["classes"] = sorted(classes)

    if sources is not None:
        _put(row, "usedIn", _format_used_in(sources))
        _put(row, "obtainedFrom", _format_obtained_from(sources))

    if recipe is not None:
        ingredients = _recipe_links(recipe.materials)
        rewards = _recipe_links(recipe.results)
        if ingredients:
            row["ingredients"] = ingredients
        if rewards:
            row["rewards"] = rewards
    normal_stat = next((stat for stat in stats if stat.quality in {"Normal", "0"}), None)
    stat_rows = [
        _stat_record(stat, normal_stat)
        for stat in sorted(stats, key=lambda candidate: _quality_order(candidate.quality))
    ]
    stat_rows = [stat for stat in stat_rows if len(stat) > 1]
    if stat_rows:
        row["stats"] = stat_rows

    return row


def _quality_order(quality: str) -> int:
    return TIER_ORDER_MAP.get(quality, TIER_SORT_DEFAULT)


def _format_obtained_from(sources: SourceInfo) -> list[LuaData]:
    """Format stable-keyed item provenance with deterministic ordering."""
    ordered = sorted(
        sources.obtained_from,
        key=lambda source: (
            source.source_type,
            source.source_key or "",
            source.condition or "",
            source.probability is None,
            source.probability if source.probability is not None else 0.0,
            source.quantity is None,
            source.quantity if source.quantity is not None else 0,
            source.is_guaranteed,
        ),
    )
    result: list[LuaData] = []
    for source in ordered:
        row: LuaData = {}
        _put(row, "type", source.source_type)
        _put(row, "sourceKey", source.source_key)
        _put(row, "probability", source.probability)
        if source.is_guaranteed:
            row["guaranteed"] = True
        _put(row, "quantity", source.quantity)
        _put(row, "condition", source.condition)
        result.append(row)
    return result


def _format_used_in(sources: SourceInfo) -> list[LuaData]:
    """Format stable-keyed item usage with deterministic ordering."""
    ordered = sorted(
        sources.used_in,
        key=lambda source: (
            source.use_type,
            source.target_key,
            source.quantity is None,
            source.quantity if source.quantity is not None else 0,
            source.slot is None,
            source.slot if source.slot is not None else 0,
        ),
    )
    result: list[LuaData] = []
    for source in ordered:
        row: LuaData = {}
        _put(row, "type", source.use_type)
        _put(row, "targetKey", source.target_key)
        _put(row, "quantity", source.quantity)
        _put(row, "slot", source.slot)
        result.append(row)
    return result


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


def _recipe_links(links: list[tuple[ItemLink, int]]) -> list[LuaData]:
    return [
        {"quantity": quantity, "link": ref} for link, quantity in links if (ref := link_ref(link, "item")) is not None
    ]


def _stat_record(stat: ItemStats, normal_stat: ItemStats | None = None) -> LuaData:
    row: LuaData = {"quality": stat.quality}
    for lua_name, attr_name in _STAT_FIELD_MAP:
        value = getattr(stat, attr_name)
        if stat.quality == "Improved +5" and normal_stat is not None and attr_name in _RESIST_STAT_FIELDS:
            # The shipped CalcResists predicate omits quality 15. Keep wiki
            # quality progression non-decreasing by applying the intended +1
            # Improved resist bonus to the final upgrade row.
            value = (getattr(normal_stat, attr_name) or 0) + 1
        _put(row, lua_name, value)
    return row


def _put(row: LuaData, key: str, value: object) -> None:
    if value is not None and value not in ("", []):
        row[key] = value


def _put_bool(row: LuaData, key: str, value: Any) -> None:
    if value is not None:
        row[key] = bool(value)
