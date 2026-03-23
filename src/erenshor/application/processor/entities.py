"""Generic entity processor for non-character entity types.

Handles zones, factions, items, spells, skills, stances, quests, and all
their supporting tables.  Each processor function follows the same pattern:

1. Read all rows from the raw DB (PascalCase columns).
2. Apply mapping overrides (display_name, wiki_page_name, image_name).
3. Attach is_wiki_generated / is_map_visible flags (no row exclusion).
4. Rename columns to snake_case.
5. Write to the clean DB via the Writer.

Junction tables that reference entity stable keys are filtered to keep only
rows whose foreign key is in the set of non-excluded entities.

Processing order (enforced by build.py):
    zones → factions → items → spells → skills → stances → quests

Characters are handled separately in characters.py.
"""

from __future__ import annotations

import re
import sqlite3
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from .mapping import MappingOverride
    from .writer import Writer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snake(name: str) -> str:
    """Convert PascalCase or camelCase column name to snake_case.

    Handles common patterns in the raw DB:
    - Require2H  → require_2h  (digit before uppercase)
    - BaseMHAtkDelay → base_mh_atk_delay
    - BaseOHAtkDelay → base_oh_atk_delay
    """
    # Insert underscore before a digit that follows a lowercase letter
    s = re.sub(r"([a-z])([0-9])", r"\1_\2", name)
    # Insert underscore before uppercase runs followed by lowercase
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    # Insert underscore before uppercase that follows lowercase or digit
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]


def _apply_mapping(
    rows: list[dict[str, object]],
    stable_key_col: str,
    name_col: str,
    mapping: dict[str, MappingOverride],
) -> list[dict[str, object]]:
    """Apply mapping overrides.

    Adds display_name, wiki_page_name, image_name, is_wiki_generated, and
    is_map_visible to each row. wiki_page_name may be None (no wiki page).
    """
    result = []
    for row in rows:
        sk = str(row[stable_key_col])
        default_name = str(row[name_col]) if row[name_col] is not None else ""
        override = mapping.get(sk)
        if override is not None:
            row["display_name"] = override["display_name"].strip()
            row["wiki_page_name"] = (
                override["wiki_page_name"].strip() if override["wiki_page_name"] is not None else None
            )
            row["image_name"] = override["image_name"].strip()
            row["is_wiki_generated"] = int(override["is_wiki_generated"])
            row["is_map_visible"] = int(override["is_map_visible"])
        else:
            row["display_name"] = default_name.strip()
            row["wiki_page_name"] = default_name.strip()
            row["image_name"] = default_name.strip()
            row["is_wiki_generated"] = 1
            row["is_map_visible"] = 1
        result.append(row)
    return result


def _rename_cols(rows: list[dict[str, object]], renames: dict[str, str] | None = None) -> list[dict[str, object]]:
    """Rename all keys from PascalCase to snake_case.

    Optionally applies additional specific renames (e.g. 'Unique' → 'is_unique'
    to avoid SQL reserved word collision and follow boolean naming convention).
    """
    renames = renames or {}
    result = []
    for row in rows:
        new = {}
        for k, v in row.items():
            dest = renames.get(k, _snake(k))
            new[dest] = v
        result.append(new)
    return result


def _filter_junction(
    rows: list[dict[str, object]],
    fk_col: str,  # PascalCase FK column name
    valid_keys: set[str],
) -> list[dict[str, object]]:
    """Keep only junction rows whose FK is in valid_keys."""
    return [r for r in rows if r.get(fk_col) in valid_keys]


# ---------------------------------------------------------------------------
# World / placement tables (copied verbatim, no exclusion filtering)
# ---------------------------------------------------------------------------


def process_world_tables(raw: sqlite3.Connection, writer: Writer) -> None:
    """Copy all world/placement tables verbatim (snake_case rename only)."""

    simple_tables = [
        ("SELECT * FROM Teleports", writer.insert_teleports, {"TeleportItemStableKey": "teleport_item_stable_key"}),
        ("SELECT * FROM WishingWells", writer.insert_wishing_wells, {}),
        (
            "SELECT * FROM AchievementTriggers",
            writer.insert_achievement_triggers,
            {"AchievementName": "achievement_name"},
        ),
        ("SELECT * FROM Doors", writer.insert_doors, {"KeyItemStableKey": "key_item_stable_key"}),
        ("SELECT * FROM Forges", writer.insert_forges, {}),
        ("SELECT * FROM TreasureLocations", writer.insert_treasure_locations, {}),
        ("SELECT * FROM Waters", writer.insert_waters, {}),
        ("SELECT * FROM GameConstants", writer.insert_game_constants, {}),
        ("SELECT * FROM SecretPassages", writer.insert_secret_passages, {}),
        ("SELECT * FROM Ascensions", writer.insert_ascensions, {}),
        ("SELECT * FROM Books", writer.insert_books, {}),
        ("SELECT * FROM GuildTopics", writer.insert_guild_topics, {}),
        ("SELECT * FROM TreasureHunting", writer.insert_treasure_hunting, {}),
    ]

    for sql, insert_fn, extra_renames in simple_tables:
        table_name = sql.split("FROM ")[1].strip()
        rows = _rows(raw, sql)
        rows = _rename_cols(rows, extra_renames)
        n = insert_fn(rows)
        logger.debug(f"  {table_name}: {n} rows")

    # ItemBags: rename ItemStableKey only
    rows = _rows(raw, "SELECT * FROM ItemBags")
    rows = _rename_cols(rows, {"ItemStableKey": "item_stable_key"})
    writer.insert_item_bags(rows)

    # MiningNodes + MiningNodeItems
    rows = _rows(raw, "SELECT * FROM MiningNodes")
    rows = _rename_cols(rows)
    writer.insert_mining_nodes(rows)

    rows = _rows(raw, "SELECT * FROM MiningNodeItems")
    rows = _rename_cols(
        rows,
        {
            "MiningNodeStableKey": "mining_node_stable_key",
            "ItemStableKey": "item_stable_key",
            "DropChance": "drop_chance",
        },
    )
    writer.insert_mining_node_items(rows)

    # Waters + WaterFishables
    rows = _rows(raw, "SELECT * FROM WaterFishables")
    rows = _rename_cols(
        rows,
        {
            "WaterStableKey": "water_stable_key",
            "Type": "type",
            "ItemStableKey": "item_stable_key",
            "DropChance": "drop_chance",
        },
    )
    writer.insert_water_fishables(rows)

    # ZoneLines
    rows = _rows(raw, "SELECT * FROM ZoneLines")
    rows = _rename_cols(
        rows,
        {
            "DestinationZoneStableKey": "destination_zone_stable_key",
        },
    )
    writer.insert_zone_lines(rows)

    # ZoneLineQuestUnlocks
    rows = _rows(raw, "SELECT * FROM ZoneLineQuestUnlocks")
    rows = _rename_cols(rows)
    writer.insert_zone_line_quest_unlocks(rows)

    # CharacterQuestUnlocks
    rows = _rows(raw, "SELECT * FROM CharacterQuestUnlocks")
    rows = _rename_cols(rows)
    writer.insert_character_quest_unlocks(rows)

    # ZoneAtlasEntries + ZoneAtlasNeighbors
    rows = _rows(raw, "SELECT * FROM ZoneAtlasEntries")
    rows = _rename_cols(rows)
    writer.insert_zone_atlas_entries(rows)

    rows = _rows(raw, "SELECT * FROM ZoneAtlasNeighbors")
    rows = _rename_cols(
        rows,
        {
            "ZoneAtlasId": "zone_atlas_id",
            "NeighborZoneStableKey": "neighbor_zone_stable_key",
        },
    )
    writer.insert_zone_atlas_neighbors(rows)

    # Classes
    rows = _rows(raw, "SELECT * FROM Classes")
    rows = _rename_cols(rows)
    writer.insert_classes(rows)


# ---------------------------------------------------------------------------
# Zones
# ---------------------------------------------------------------------------


def process_zones(
    raw: sqlite3.Connection,
    writer: Writer,
    mapping: dict[str, MappingOverride],
) -> set[str]:
    """Process Zones table. Returns set of included stable keys."""
    rows = _rows(raw, "SELECT * FROM Zones")
    logger.info(f"Zones: {len(rows)} raw")

    rows = _apply_mapping(rows, "StableKey", "ZoneName", mapping)
    logger.info(f"Zones: {len(rows)} after mapping")

    rows = _rename_cols(rows)
    writer.insert_zones(rows)
    return {str(r["stable_key"]) for r in rows}


# ---------------------------------------------------------------------------
# Factions
# ---------------------------------------------------------------------------


def process_factions(
    raw: sqlite3.Connection,
    writer: Writer,
    mapping: dict[str, MappingOverride],
) -> set[str]:
    """Process Factions table. Returns set of included stable keys.

    Default display name is FactionDesc (matching registry/operations.py
    behaviour), not FactionName.
    """
    rows = _rows(raw, "SELECT * FROM Factions")
    logger.info(f"Factions: {len(rows)} raw")

    rows = _apply_mapping(rows, "StableKey", "FactionDesc", mapping)
    logger.info(f"Factions: {len(rows)} after mapping")

    rows = _rename_cols(rows)
    writer.insert_factions(rows)
    return {str(r["stable_key"]) for r in rows}


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


def process_items(
    raw: sqlite3.Connection,
    writer: Writer,
    mapping: dict[str, MappingOverride],
) -> set[str]:
    """Process Items and related tables. Returns set of included stable keys."""
    rows = _rows(raw, "SELECT * FROM Items WHERE COALESCE(ResourceName, '') != ''")
    logger.info(f"Items: {len(rows)} raw")

    rows = _apply_mapping(rows, "StableKey", "ItemName", mapping)
    logger.info(f"Items: {len(rows)} after mapping")

    # 'Unique' is a SQL reserved word — rename to is_unique (boolean 0/1)
    rows = _rename_cols(rows, {"Unique": "is_unique"})
    writer.insert_items(rows)
    valid = {str(r["stable_key"]) for r in rows}

    # ItemStats — no exclusion (stats aren't entities)
    stat_rows = _rows(raw, "SELECT * FROM ItemStats")
    stat_rows = _filter_junction(stat_rows, "ItemStableKey", valid)
    stat_rows = _rename_cols(stat_rows, {"ItemStableKey": "item_stable_key"})
    writer.insert_item_stats(stat_rows)

    # ItemClasses
    cls_rows = _rows(raw, "SELECT * FROM ItemClasses")
    cls_rows = _filter_junction(cls_rows, "ItemStableKey", valid)
    cls_rows = _rename_cols(
        cls_rows,
        {
            "ItemStableKey": "item_stable_key",
            "ClassName": "class_name",
        },
    )
    writer.insert_item_classes(cls_rows)

    # CraftingRecipes
    recipe_rows = _rows(raw, "SELECT * FROM CraftingRecipes")
    recipe_rows = _filter_junction(recipe_rows, "RecipeItemStableKey", valid)
    recipe_rows = _rename_cols(
        recipe_rows,
        {
            "RecipeItemStableKey": "recipe_item_stable_key",
            "MaterialSlot": "material_slot",
            "MaterialItemStableKey": "material_item_stable_key",
            "MaterialQuantity": "material_quantity",
        },
    )
    writer.insert_crafting_recipes(recipe_rows)

    # CraftingRewards
    reward_rows = _rows(raw, "SELECT * FROM CraftingRewards")
    reward_rows = _filter_junction(reward_rows, "RecipeItemStableKey", valid)
    reward_rows = _rename_cols(
        reward_rows,
        {
            "RecipeItemStableKey": "recipe_item_stable_key",
            "RewardSlot": "reward_slot",
            "RewardItemStableKey": "reward_item_stable_key",
            "RewardQuantity": "reward_quantity",
        },
    )
    writer.insert_crafting_rewards(reward_rows)

    # ItemDrops (item → item drops, e.g. container → loot)
    drop_rows = _rows(raw, "SELECT * FROM ItemDrops")
    drop_rows = _filter_junction(drop_rows, "SourceItemStableKey", valid)
    drop_rows = _rename_cols(
        drop_rows,
        {
            "SourceItemStableKey": "source_item_stable_key",
            "DroppedItemStableKey": "dropped_item_stable_key",
            "DropProbability": "drop_probability",
            "IsGuaranteed": "is_guaranteed",
        },
    )
    writer.insert_item_drops(drop_rows)

    logger.info(f"Items: wrote {len(valid)} items + junction tables")
    return valid


# ---------------------------------------------------------------------------
# Spells
# ---------------------------------------------------------------------------


def process_spells(
    raw: sqlite3.Connection,
    writer: Writer,
    mapping: dict[str, MappingOverride],
) -> set[str]:
    """Process Spells and SpellClasses. Returns set of included stable keys."""
    rows = _rows(raw, "SELECT * FROM Spells")
    logger.info(f"Spells: {len(rows)} raw")

    rows = _apply_mapping(rows, "StableKey", "SpellName", mapping)
    logger.info(f"Spells: {len(rows)} after mapping")

    rows = _rename_cols(rows)
    writer.insert_spells(rows)
    valid = {str(r["stable_key"]) for r in rows}

    cls_rows = _rows(raw, "SELECT * FROM SpellClasses")
    cls_rows = _filter_junction(cls_rows, "SpellStableKey", valid)
    cls_rows = _rename_cols(
        cls_rows,
        {
            "SpellStableKey": "spell_stable_key",
            "ClassName": "class_name",
        },
    )
    writer.insert_spell_classes(cls_rows)

    return valid


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


def process_skills(
    raw: sqlite3.Connection,
    writer: Writer,
    mapping: dict[str, MappingOverride],
) -> set[str]:
    """Process Skills table. Returns set of included stable keys."""
    rows = _rows(raw, "SELECT * FROM Skills")
    logger.info(f"Skills: {len(rows)} raw")

    rows = _apply_mapping(rows, "StableKey", "SkillName", mapping)
    logger.info(f"Skills: {len(rows)} after mapping")

    # Require2H has a digit that breaks generic snake_case conversion.
    rows = _rename_cols(rows, {"Require2H": "require_2h"})
    writer.insert_skills(rows)
    return {str(r["stable_key"]) for r in rows}


# ---------------------------------------------------------------------------
# Stances
# ---------------------------------------------------------------------------


def process_stances(
    raw: sqlite3.Connection,
    writer: Writer,
    mapping: dict[str, MappingOverride],
) -> set[str]:
    """Process Stances table. Returns set of included stable keys."""
    rows = _rows(raw, "SELECT * FROM Stances")
    logger.info(f"Stances: {len(rows)} raw")

    # DisplayName is the natural name for stances
    rows = _apply_mapping(rows, "StableKey", "DisplayName", mapping)
    logger.info(f"Stances: {len(rows)} after mapping")

    rows = _rename_cols(rows)
    writer.insert_stances(rows)
    return {str(r["stable_key"]) for r in rows}


# ---------------------------------------------------------------------------
# Quests
# ---------------------------------------------------------------------------


def process_quests(
    raw: sqlite3.Connection,
    writer: Writer,
    mapping: dict[str, MappingOverride],
) -> set[str]:
    """Process Quests, QuestVariants and related tables.

    The display name for a quest is taken from its first QuestVariant's
    QuestName (matching registry/operations.py behaviour).
    """
    # Get quests with their first variant's name
    quest_rows = _rows(
        raw,
        """
        SELECT q.StableKey, q.DBName, qv.QuestName
        FROM Quests q
        JOIN QuestVariants qv ON q.StableKey = qv.QuestStableKey
        GROUP BY q.StableKey
        HAVING MIN(qv.QuestDBIndex)
    """,
    )
    logger.info(f"Quests: {len(quest_rows)} raw")

    quest_rows = _apply_mapping(quest_rows, "StableKey", "QuestName", mapping)
    logger.info(f"Quests: {len(quest_rows)} after mapping")

    valid = {str(r["StableKey"]) for r in quest_rows}

    # Write quests (drop QuestName — it came from the join, not the Quests table)
    quest_out = []
    for r in quest_rows:
        quest_out.append(
            {
                "stable_key": r["StableKey"],
                "db_name": r["DBName"],
                "display_name": r["display_name"],
                "wiki_page_name": r["wiki_page_name"],
                "image_name": r["image_name"],
            }
        )
    writer.insert_quests(quest_out)

    # QuestVariants — filter to valid quests only
    variant_rows = _rows(raw, "SELECT * FROM QuestVariants")
    variant_rows = _filter_junction(variant_rows, "QuestStableKey", valid)
    variant_rows = _rename_cols(
        variant_rows,
        {
            "QuestStableKey": "quest_stable_key",
            "QuestDBIndex": "quest_db_index",
            "QuestName": "quest_name",
            "QuestDesc": "quest_desc",
            "XPonComplete": "xp_on_complete",
            "ItemOnCompleteStableKey": "item_on_complete_stable_key",
            "GoldOnComplete": "gold_on_complete",
            "AssignNewQuestOnCompleteStableKey": "assign_new_quest_on_complete_stable_key",
            "DialogOnSuccess": "dialog_on_success",
            "DialogOnPartialSuccess": "dialog_on_partial_success",
            "DisableText": "disable_text",
            "AssignThisQuestOnPartialComplete": "assign_this_quest_on_partial_complete",
            "Repeatable": "repeatable",
            "DisableQuest": "disable_quest",
            "KillTurnInHolder": "kill_turn_in_holder",
            "DestroyTurnInHolder": "destroy_turn_in_holder",
            "DropInvulnOnHolder": "drop_invuln_on_holder",
            "OncePerSpawnInstance": "once_per_spawn_instance",
            "SetAchievementOnGet": "set_achievement_on_get",
            "SetAchievementOnFinish": "set_achievement_on_finish",
            "UnlockItemForVendorStableKey": "unlock_item_for_vendor_stable_key",
            "ResourceName": "resource_name",
        },
    )
    writer.insert_quest_variants(variant_rows)
    valid_variant_names = {str(r["resource_name"]) for r in variant_rows}

    # QuestRequiredItems
    req_rows = _rows(raw, "SELECT * FROM QuestRequiredItems")
    req_rows = _filter_junction(req_rows, "QuestVariantResourceName", valid_variant_names)
    req_rows = _rename_cols(
        req_rows,
        {
            "QuestVariantResourceName": "quest_variant_resource_name",
            "ItemStableKey": "item_stable_key",
            "Quantity": "quantity",
        },
    )
    writer.insert_quest_required_items(req_rows)

    # QuestFactionAffects
    fa_rows = _rows(raw, "SELECT * FROM QuestFactionAffects")
    fa_rows = _filter_junction(fa_rows, "QuestVariantResourceName", valid_variant_names)
    fa_rows = _rename_cols(
        fa_rows,
        {
            "QuestVariantResourceName": "quest_variant_resource_name",
            "FactionStableKey": "faction_stable_key",
            "ModifierValue": "modifier_value",
        },
    )
    writer.insert_quest_faction_affects(fa_rows)

    # QuestCompleteOtherQuests
    co_rows = _rows(raw, "SELECT * FROM QuestCompleteOtherQuests")
    co_rows = _filter_junction(co_rows, "QuestVariantResourceName", valid_variant_names)
    co_rows = _rename_cols(
        co_rows,
        {
            "QuestVariantResourceName": "quest_variant_resource_name",
            "CompletedQuestStableKey": "completed_quest_stable_key",
        },
    )
    writer.insert_quest_complete_other_quests(co_rows)

    # QuestCharacterRoles — filtered by quest stable key
    role_rows = _rows(raw, "SELECT * FROM QuestCharacterRoles")
    role_rows = _filter_junction(role_rows, "QuestStableKey", valid)
    role_rows = _rename_cols(
        role_rows,
        {
            "QuestStableKey": "quest_stable_key",
            "CharacterStableKey": "character_stable_key",
            "Role": "role",
        },
    )
    writer.insert_quest_character_roles(role_rows)

    # QuestCompletionSources — filtered by quest stable key
    src_rows = _rows(raw, "SELECT * FROM QuestCompletionSources")
    src_rows = _filter_junction(src_rows, "QuestStableKey", valid)
    src_rows = _rename_cols(
        src_rows,
        {
            "QuestStableKey": "quest_stable_key",
            "Method": "method",
            "SourceType": "source_type",
            "SourceStableKey": "source_stable_key",
            "Note": "note",
        },
    )
    writer.insert_quest_completion_sources(src_rows)

    # QuestAcquisitionSources -- filtered by quest stable key
    acq_rows = _rows(raw, "SELECT * FROM QuestAcquisitionSources")
    acq_rows = _filter_junction(acq_rows, "QuestStableKey", valid)
    acq_rows = _rename_cols(
        acq_rows,
        {
            "QuestStableKey": "quest_stable_key",
            "Method": "method",
            "SourceType": "source_type",
            "SourceStableKey": "source_stable_key",
            "Note": "note",
        },
    )
    writer.insert_quest_acquisition_sources(acq_rows)

    logger.info(f"Quests: wrote {len(valid)} quests + variant/junction tables")
    return valid
