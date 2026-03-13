"""Character processor for the Layer 2 pipeline.

This is the most complex processor because characters have the most
relationships and require deduplication and is_unique computation.

Processing steps (in order):
1. Load all Characters rows from the raw DB, excluding SimPlayers, the
   Player object, and blank ObjectName rows.
2. Apply mapping overrides (display_name, wiki_page_name, image_name).
3. Attach is_wiki_generated / is_map_visible flags (no exclusion).
4. Load all junction data (spawns, spells, loot, dialogs, etc.) into memory.
5. Deduplicate all characters: group by identity key (all scalar fields +
   relationship sets). Compute stable dedup groups and write
   character_deduplications membership rows.
6. Recompute is_unique and is_rare per group using all merged spawns.
7. Write characters, spawns, and all junction tables.

Deduplication identity includes:
- display_name (post-mapping)
- wiki-displayed stats only (level, effective HP/AC/resists, mana,
  primary stats, xp multiplier)
- frozenset of (item_stable_key, drop_probability) loot pairs
- frozenset of attack skill stable keys
- boolean type flags (excluding IsVendor)

Non-displayed stats (attack damage, run speed, XP ranges, etc.),
quest assignments, dialog, spells, and vendor items are NOT part of
identity. Spawn locations and spells are merged across the dedup
group at query time.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from loguru import logger

if TYPE_CHECKING:
    from .mapping import MappingOverride, SpawnMappingOverride
    from .writer import Writer

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class _CharRow:
    """Holds a raw character row with mapping applied."""

    # Raw row dict (PascalCase keys)
    raw: dict[str, object]

    # Resolved display fields
    stable_key: str
    display_name: str
    wiki_page_name: str | None
    image_name: str
    is_wiki_generated: int
    is_map_visible: int


@dataclass
class _SpawnRow:
    """A single spawn slot for one character."""

    # spawn point or directly-placed info
    spawn_point_stable_key: str | None
    zone_stable_key: str | None
    scene: str | None
    x: float | None
    y: float | None
    z: float | None
    is_enabled: int | None
    is_directly_placed: int
    rare_npc_chance: int | None
    level_mod: int | None
    spawn_delay_1: float | None
    spawn_delay_2: float | None
    spawn_delay_3: float | None
    spawn_delay_4: float | None
    staggerable: int | None
    stagger_mod: float | None
    night_spawn: int | None
    patrol_points: str | None
    loop_patrol: int | None
    random_wander_range: float | None
    spawn_upon_quest_complete_stable_key: str | None
    protector_stable_key: str | None
    spawn_chance: float
    is_common: int | None
    is_rare: int | None
    is_wiki_generated: int | None
    is_map_visible: int | None


@dataclass
class _CharData:
    """Aggregated data for one character during processing."""

    char: _CharRow
    spawns: list[_SpawnRow] = field(default_factory=list)
    # Relationship sets (used for dedup key)
    attack_spell_keys: frozenset[str] = frozenset()
    buff_spell_keys: frozenset[str] = frozenset()
    heal_spell_keys: frozenset[str] = frozenset()
    group_heal_spell_keys: frozenset[str] = frozenset()
    cc_spell_keys: frozenset[str] = frozenset()
    taunt_spell_keys: frozenset[str] = frozenset()
    attack_skill_keys: frozenset[str] = frozenset()
    loot: frozenset[tuple[str, float]] = frozenset()  # (item_key, probability)
    vendor_item_keys: frozenset[str] = frozenset()
    quest_manager_quest_keys: frozenset[str] = frozenset()
    dialog_quest_keys: frozenset[tuple[str | None, str | None]] = frozenset()


# ---------------------------------------------------------------------------
# Dedup key
# ---------------------------------------------------------------------------

_STAT_FIELDS = [
    # Only fields that appear in wiki output. Non-displayed fields
    # (attack damage, XP ranges, run speed, etc.) are excluded so
    # prefabs that differ only in hidden stats get merged.
    "Level",
    "BossXpMultiplier",
    "EffectiveHP",
    "EffectiveAC",
    "BaseMana",
    "BaseStr",
    "BaseEnd",
    "BaseDex",
    "BaseAgi",
    "BaseInt",
    "BaseWis",
    "BaseCha",
    "EffectiveMinMR",
    "EffectiveMaxMR",
    "EffectiveMinER",
    "EffectiveMaxER",
    "EffectiveMinPR",
    "EffectiveMaxPR",
    "EffectiveMinVR",
    "EffectiveMaxVR",
]

_FLAG_FIELDS = [
    # Only IsFriendly affects wiki output (NPC vs Enemy type label).
    "IsFriendly",
]


def _dedup_key(d: _CharData) -> tuple[object, ...]:
    raw = d.char.raw
    stats = tuple(raw.get(f) for f in _STAT_FIELDS)
    flags = tuple(raw.get(f) for f in _FLAG_FIELDS)
    return (
        d.char.display_name,
        stats,
        flags,
        d.attack_skill_keys,
        d.loot,
    )


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------


def _load_rows(conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]


def _load_junction_set(
    conn: sqlite3.Connection,
    table: str,
    char_col: str,
    value_col: str,
) -> dict[str, frozenset[str]]:
    """Load a simple junction table into a {char_key → frozenset(value)} dict."""
    rows = _load_rows(conn, f"SELECT {char_col}, {value_col} FROM {table}")
    result: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        ck = str(r[char_col])
        val = r[value_col]
        if val is not None:
            result[ck].add(str(val))
    return {k: frozenset(v) for k, v in result.items()}


def _load_zone_by_scene(conn: sqlite3.Connection) -> dict[str, str]:
    """Map SceneName → StableKey for the Zones table."""
    rows = _load_rows(conn, "SELECT StableKey, SceneName FROM Zones")
    return {str(r["SceneName"]): str(r["StableKey"]) for r in rows if r["SceneName"]}


# ---------------------------------------------------------------------------
# Main processor
# ---------------------------------------------------------------------------


def process_characters(
    raw: sqlite3.Connection,
    writer: Writer,
    mapping: dict[str, MappingOverride],
    spawn_mapping: dict[str, SpawnMappingOverride] | None = None,
) -> None:
    """Full character processing pipeline. Writes to writer."""

    # ------------------------------------------------------------------
    # Step 1: Load characters, apply mapping, attach flags
    # ------------------------------------------------------------------
    char_rows = _load_rows(
        raw,
        """
        SELECT * FROM Characters
        WHERE COALESCE(ObjectName, '') != ''
          AND COALESCE(IsSimPlayer, 0) = 0
          AND ObjectName != 'Player'
    """,
    )
    logger.info(f"Characters: {len(char_rows)} after initial filter (SimPlayer/Player/blank)")

    chars: list[_CharRow] = []
    for row in char_rows:
        sk = str(row["StableKey"])
        npc_name = str(row["NPCName"]) if row["NPCName"] is not None else ""
        override = mapping.get(sk)
        if override is not None:
            display_name = override["display_name"].strip()
            wiki_page_name = override["wiki_page_name"].strip() if override["wiki_page_name"] is not None else None
            image_name = override["image_name"].strip()
            is_wiki_generated = int(override["is_wiki_generated"])
            is_map_visible = int(override["is_map_visible"])
        else:
            display_name = npc_name.strip()
            wiki_page_name = npc_name.strip()
            image_name = npc_name.strip()
            is_wiki_generated = 1
            is_map_visible = 1
        chars.append(
            _CharRow(
                raw=row,
                stable_key=sk,
                display_name=display_name,
                wiki_page_name=wiki_page_name,
                image_name=image_name,
                is_wiki_generated=is_wiki_generated,
                is_map_visible=is_map_visible,
            )
        )

    logger.info(f"Characters: {len(chars)} after mapping")
    all_keys: set[str] = {c.stable_key for c in chars}

    # ------------------------------------------------------------------
    # Step 2: Load spawn data
    # ------------------------------------------------------------------
    zone_by_scene = _load_zone_by_scene(raw)

    # Load directly-placed characters (they have coordinates in Characters table
    # but no SpawnPoint — their scene/X/Y/Z IS the spawn location)
    direct_spawn_by_char: dict[str, _SpawnRow] = {}
    for row in char_rows:
        sk = str(row["StableKey"])
        if sk not in all_keys:
            continue
        scene = row.get("Scene")
        if scene is not None:
            direct_spawn_by_char[sk] = _SpawnRow(
                spawn_point_stable_key=None,
                zone_stable_key=zone_by_scene.get(str(scene)),
                scene=str(scene) if scene else None,
                x=row.get("X"),  # type: ignore[arg-type]
                y=row.get("Y"),  # type: ignore[arg-type]
                z=row.get("Z"),  # type: ignore[arg-type]
                is_enabled=row.get("IsEnabled"),  # type: ignore[arg-type]
                is_directly_placed=1,
                rare_npc_chance=None,
                level_mod=None,
                spawn_delay_1=None,
                spawn_delay_2=None,
                spawn_delay_3=None,
                spawn_delay_4=None,
                staggerable=None,
                stagger_mod=None,
                night_spawn=None,
                patrol_points=None,
                loop_patrol=None,
                random_wander_range=None,
                spawn_upon_quest_complete_stable_key=None,
                protector_stable_key=None,
                spawn_chance=100.0,
                is_common=None,
                is_rare=None,
                is_wiki_generated=None,
                is_map_visible=None,
            )

    # Load spawn-point based spawns
    sp_rows = _load_rows(
        raw,
        """
        SELECT
            sp.StableKey        AS SpawnPointStableKey,
            sp.Scene            AS SpScene,
            sp.X, sp.Y, sp.Z,
            sp.IsEnabled,
            sp.IsDirectlyPlaced,
            sp.RareNPCChance,
            sp.LevelMod,
            sp.SpawnDelay1, sp.SpawnDelay2, sp.SpawnDelay3, sp.SpawnDelay4,
            sp.Staggerable, sp.StaggerMod,
            sp.NightSpawn,
            sp.PatrolPoints, sp.LoopPatrol, sp.RandomWanderRange,
            sp.SpawnUponQuestCompleteStableKey,
            sp.ProtectorStableKey,
            spc.CharacterStableKey,
            spc.SpawnChance,
            spc.IsCommon,
            spc.IsRare
        FROM SpawnPoints sp
        JOIN SpawnPointCharacters spc ON sp.StableKey = spc.SpawnPointStableKey
        WHERE spc.CharacterStableKey IN ({})
    """.format(",".join("?" * len(all_keys))),
        tuple(all_keys),
    )

    # Group spawn rows by character
    spawn_rows_by_char: dict[str, list[_SpawnRow]] = defaultdict(list)
    _spawn_mapping = spawn_mapping or {}
    for r in sp_rows:
        sk = str(r["CharacterStableKey"])
        scene = r.get("SpScene")
        spk = str(r["SpawnPointStableKey"])
        spawn_override = _spawn_mapping.get(spk)
        spawn_rows_by_char[sk].append(
            _SpawnRow(
                spawn_point_stable_key=spk,
                zone_stable_key=zone_by_scene.get(str(scene)) if scene else None,
                scene=str(scene) if scene else None,
                x=cast("float | None", r.get("X")),
                y=cast("float | None", r.get("Y")),
                z=cast("float | None", r.get("Z")),
                is_enabled=cast("int | None", r.get("IsEnabled")),
                is_directly_placed=int(cast("int", r.get("IsDirectlyPlaced") or 0)),
                rare_npc_chance=cast("int | None", r.get("RareNPCChance")),
                level_mod=cast("int | None", r.get("LevelMod")),
                spawn_delay_1=cast("float | None", r.get("SpawnDelay1")),
                spawn_delay_2=cast("float | None", r.get("SpawnDelay2")),
                spawn_delay_3=cast("float | None", r.get("SpawnDelay3")),
                spawn_delay_4=cast("float | None", r.get("SpawnDelay4")),
                staggerable=cast("int | None", r.get("Staggerable")),
                stagger_mod=cast("float | None", r.get("StaggerMod")),
                night_spawn=cast("int | None", r.get("NightSpawn")),
                patrol_points=cast("str | None", r.get("PatrolPoints")),
                loop_patrol=cast("int | None", r.get("LoopPatrol")),
                random_wander_range=cast("float | None", r.get("RandomWanderRange")),
                spawn_upon_quest_complete_stable_key=cast("str | None", r.get("SpawnUponQuestCompleteStableKey")),
                protector_stable_key=cast("str | None", r.get("ProtectorStableKey")),
                spawn_chance=float(cast("float", r.get("SpawnChance") or 0.0)),
                is_common=cast("int | None", r.get("IsCommon")),
                is_rare=cast("int | None", r.get("IsRare")),
                is_wiki_generated=spawn_override["is_wiki_generated"] if spawn_override else None,
                is_map_visible=spawn_override["is_map_visible"] if spawn_override else None,
            )
        )

    # ------------------------------------------------------------------
    # Step 3: Load junction data for dedup key
    # ------------------------------------------------------------------
    attack_spells = _load_junction_set(raw, "CharacterAttackSpells", "CharacterStableKey", "SpellStableKey")
    buff_spells = _load_junction_set(raw, "CharacterBuffSpells", "CharacterStableKey", "SpellStableKey")
    heal_spells = _load_junction_set(raw, "CharacterHealSpells", "CharacterStableKey", "SpellStableKey")
    gh_spells = _load_junction_set(raw, "CharacterGroupHealSpells", "CharacterStableKey", "SpellStableKey")
    cc_spells = _load_junction_set(raw, "CharacterCCSpells", "CharacterStableKey", "SpellStableKey")
    taunt_spells = _load_junction_set(raw, "CharacterTauntSpells", "CharacterStableKey", "SpellStableKey")
    attack_skills = _load_junction_set(raw, "CharacterAttackSkills", "CharacterStableKey", "SkillStableKey")
    vendor_items = _load_junction_set(raw, "CharacterVendorItems", "CharacterStableKey", "ItemStableKey")
    qm_quests = _load_junction_set(raw, "CharacterQuestManagerQuests", "CharacterStableKey", "QuestStableKey")

    # Loot: (item_key, probability) pairs
    loot_rows = _load_rows(
        raw,
        """
        SELECT CharacterStableKey, ItemStableKey, DropProbability
        FROM LootDrops
        WHERE CharacterStableKey IN ({})
    """.format(",".join("?" * len(all_keys))),
        tuple(all_keys),
    )
    loot_by_char: dict[str, frozenset[tuple[str, float]]] = defaultdict(frozenset)
    tmp_loot: dict[str, set[tuple[str, float]]] = defaultdict(set)
    for r in loot_rows:
        ck = str(r["CharacterStableKey"])
        prob = float(cast("float", r["DropProbability"])) if r["DropProbability"] is not None else 0.0
        tmp_loot[ck].add((str(r["ItemStableKey"]), prob))
    loot_by_char = {k: frozenset(v) for k, v in tmp_loot.items()}

    # Dialog quest keys: (assign_quest, complete_quest) pairs
    dialog_rows = _load_rows(
        raw,
        """
        SELECT CharacterStableKey, AssignQuestStableKey, CompleteQuestStableKey
        FROM CharacterDialogs
        WHERE CharacterStableKey IN ({})
    """.format(",".join("?" * len(all_keys))),
        tuple(all_keys),
    )
    tmp_dialog: dict[str, set[tuple[str | None, str | None]]] = defaultdict(set)
    for r in dialog_rows:
        ck = str(r["CharacterStableKey"])
        tmp_dialog[ck].add(
            (
                str(r["AssignQuestStableKey"]) if r["AssignQuestStableKey"] else None,
                str(r["CompleteQuestStableKey"]) if r["CompleteQuestStableKey"] else None,
            )
        )
    dialog_quest_by_char: dict[str, frozenset[tuple[str | None, str | None]]] = {
        k: frozenset(v) for k, v in tmp_dialog.items()
    }

    # ------------------------------------------------------------------
    # Step 4: Build _CharData objects
    # ------------------------------------------------------------------
    char_data: list[_CharData] = []
    for c in chars:
        sk = c.stable_key
        spawns: list[_SpawnRow] = []
        if sk in direct_spawn_by_char:
            spawns.append(direct_spawn_by_char[sk])
        spawns.extend(spawn_rows_by_char.get(sk, []))
        char_data.append(
            _CharData(
                char=c,
                spawns=spawns,
                attack_spell_keys=attack_spells.get(sk, frozenset()),
                buff_spell_keys=buff_spells.get(sk, frozenset()),
                heal_spell_keys=heal_spells.get(sk, frozenset()),
                group_heal_spell_keys=gh_spells.get(sk, frozenset()),
                cc_spell_keys=cc_spells.get(sk, frozenset()),
                taunt_spell_keys=taunt_spells.get(sk, frozenset()),
                attack_skill_keys=attack_skills.get(sk, frozenset()),
                loot=loot_by_char.get(sk, frozenset()),
                vendor_item_keys=vendor_items.get(sk, frozenset()),
                quest_manager_quest_keys=qm_quests.get(sk, frozenset()),
                dialog_quest_keys=dialog_quest_by_char.get(sk, frozenset()),
            )
        )

    # ------------------------------------------------------------------
    # Step 5: Deduplicate (group membership only)
    # ------------------------------------------------------------------
    groups: dict[tuple[object, ...], list[_CharData]] = defaultdict(list)
    for d in char_data:
        groups[_dedup_key(d)].append(d)

    logger.info(f"Characters: {len(groups)} dedup groups from {len(char_data)} characters")

    dedup_rows: list[dict[str, object]] = []
    unique_group_count = 0
    rare_group_count = 0
    for members in groups.values():
        group_key = min(m.char.stable_key for m in members)
        for m in members:
            dedup_rows.append(
                {
                    "group_key": group_key,
                    "member_stable_key": m.char.stable_key,
                    "is_wiki_generated": m.char.is_wiki_generated,
                    "is_map_visible": m.char.is_map_visible,
                }
            )

        # Recompute is_unique / is_rare based on all group spawns.
        # Note: this may need revisiting if map visibility excludes some spawns.
        group_spawns = [s for m in members for s in m.spawns]
        total_spawns = len(group_spawns)
        is_unique = 1 if total_spawns == 1 else 0
        any_common = any(bool(s.is_common) for s in group_spawns)
        any_rare = any(bool(s.is_rare) for s in group_spawns)
        is_rare = 1 if any_rare and not any_common else 0

        if is_unique:
            unique_group_count += 1
        if is_rare:
            rare_group_count += 1

        for m in members:
            m.char.raw["IsUnique"] = is_unique
            m.char.raw["IsRare"] = is_rare

    logger.info(f"Characters: {unique_group_count} unique groups, {rare_group_count} rare groups after recomputation")

    # ------------------------------------------------------------------
    # Step 6: Write characters
    # ------------------------------------------------------------------

    def _char_row(d: _CharData) -> dict[str, object]:
        r = d.char.raw
        return {
            "stable_key": d.char.stable_key,
            "object_name": r.get("ObjectName"),
            "npc_name": r.get("NPCName"),
            "display_name": d.char.display_name,
            "wiki_page_name": d.char.wiki_page_name,
            "image_name": d.char.image_name,
            "is_wiki_generated": d.char.is_wiki_generated,
            "is_map_visible": d.char.is_map_visible,
            "scene": r.get("Scene"),
            "x": r.get("X"),
            "y": r.get("Y"),
            "z": r.get("Z"),
            "guid": r.get("Guid"),
            "my_world_faction_stable_key": r.get("MyWorldFactionStableKey"),
            "my_faction": r.get("MyFaction"),
            "aggro_range": r.get("AggroRange"),
            "attack_range": r.get("AttackRange"),
            "aggressive_towards": r.get("AggressiveTowards"),
            "allies": r.get("Allies"),
            "is_prefab": r.get("IsPrefab"),
            "is_common": r.get("IsCommon"),
            "is_rare": r.get("IsRare"),
            "is_unique": r.get("IsUnique"),
            "is_friendly": r.get("IsFriendly"),
            "is_npc": r.get("IsNPC"),
            "is_vendor": r.get("IsVendor"),
            "is_mining_node": r.get("IsMiningNode"),
            "has_stats": r.get("HasStats"),
            "has_dialog": r.get("HasDialog"),
            "has_modify_faction": r.get("HasModifyFaction"),
            "is_enabled": r.get("IsEnabled"),
            "invulnerable": r.get("Invulnerable"),
            "shout_on_death": r.get("ShoutOnDeath"),
            "quest_complete_on_death": r.get("QuestCompleteOnDeath"),
            "shout_trigger_quest_stable_key": r.get("ShoutTriggerQuestStableKey"),
            "destroy_on_death": r.get("DestroyOnDeath"),
            "level": r.get("Level"),
            "base_xp_min": r.get("BaseXpMin"),
            "base_xp_max": r.get("BaseXpMax"),
            "boss_xp_multiplier": r.get("BossXpMultiplier"),
            "base_hp": r.get("BaseHP"),
            "base_ac": r.get("BaseAC"),
            "base_mana": r.get("BaseMana"),
            "base_str": r.get("BaseStr"),
            "base_end": r.get("BaseEnd"),
            "base_dex": r.get("BaseDex"),
            "base_agi": r.get("BaseAgi"),
            "base_int": r.get("BaseInt"),
            "base_wis": r.get("BaseWis"),
            "base_cha": r.get("BaseCha"),
            "base_res": r.get("BaseRes"),
            "base_mr": r.get("BaseMR"),
            "base_er": r.get("BaseER"),
            "base_pr": r.get("BasePR"),
            "base_vr": r.get("BaseVR"),
            "run_speed": r.get("RunSpeed"),
            "base_life_steal": r.get("BaseLifeSteal"),
            "base_mh_atk_delay": r.get("BaseMHAtkDelay"),
            "base_oh_atk_delay": r.get("BaseOHAtkDelay"),
            "effective_hp": r.get("EffectiveHP"),
            "effective_ac": r.get("EffectiveAC"),
            "effective_base_atk_dmg": r.get("EffectiveBaseAtkDmg"),
            "effective_attack_ability": r.get("EffectiveAttackAbility"),
            "effective_min_mr": r.get("EffectiveMinMR"),
            "effective_max_mr": r.get("EffectiveMaxMR"),
            "effective_min_er": r.get("EffectiveMinER"),
            "effective_max_er": r.get("EffectiveMaxER"),
            "effective_min_pr": r.get("EffectiveMinPR"),
            "effective_max_pr": r.get("EffectiveMaxPR"),
            "effective_min_vr": r.get("EffectiveMinVR"),
            "effective_max_vr": r.get("EffectiveMaxVR"),
            "pet_spell_stable_key": r.get("PetSpellStableKey"),
            "proc_on_hit_stable_key": r.get("ProcOnHitStableKey"),
            "proc_on_hit_chance": r.get("ProcOnHitChance"),
            "hand_set_resistances": r.get("HandSetResistances"),
            "hard_set_ac": r.get("HardSetAC"),
            "base_atk_dmg": r.get("BaseAtkDmg"),
            "oh_atk_dmg": r.get("OHAtkDmg"),
            "min_atk_dmg": r.get("MinAtkDmg"),
            "damage_range_min": r.get("DamageRangeMin"),
            "damage_range_max": r.get("DamageRangeMax"),
            "damage_mult": r.get("DamageMult"),
            "armor_pen_mult": r.get("ArmorPenMult"),
            "power_attack_base_dmg": r.get("PowerAttackBaseDmg"),
            "power_attack_freq": r.get("PowerAttackFreq"),
            "heal_tolerance": r.get("HealTolerance"),
            "leash_range": r.get("LeashRange"),
            "aggro_regardless_of_level": r.get("AggroRegardlessOfLevel"),
            "mobile": r.get("Mobile"),
            "group_encounter": r.get("GroupEncounter"),
            "treasure_chest": r.get("TreasureChest"),
            "do_not_leave_corpse": r.get("DoNotLeaveCorpse"),
            "set_achievement_on_defeat": r.get("SetAchievementOnDefeat"),
            "set_achievement_on_spawn": r.get("SetAchievementOnSpawn"),
            "aggro_msg": r.get("AggroMsg"),
            "aggro_emote": r.get("AggroEmote"),
            "spawn_emote": r.get("SpawnEmote"),
            "guild_name": r.get("GuildName"),
            "modify_factions": r.get("ModifyFactions"),
            "vendor_desc": r.get("VendorDesc"),
            "items_for_sale": r.get("ItemsForSale"),
            "quest_manager_sim_usable": r.get("QuestManagerSimUsable"),
        }

    writer.insert_characters([_char_row(d) for d in char_data])
    writer.insert_character_deduplications(dedup_rows)

    # character_spawns
    spawn_out: list[dict[str, object]] = []
    for d in char_data:
        for s in d.spawns:
            spawn_out.append(
                {
                    "character_stable_key": d.char.stable_key,
                    "spawn_point_stable_key": s.spawn_point_stable_key,
                    "zone_stable_key": s.zone_stable_key,
                    "scene": s.scene,
                    "x": s.x,
                    "y": s.y,
                    "z": s.z,
                    "is_enabled": s.is_enabled,
                    "is_directly_placed": s.is_directly_placed,
                    "rare_npc_chance": s.rare_npc_chance,
                    "level_mod": s.level_mod,
                    "spawn_delay_1": s.spawn_delay_1,
                    "spawn_delay_2": s.spawn_delay_2,
                    "spawn_delay_3": s.spawn_delay_3,
                    "spawn_delay_4": s.spawn_delay_4,
                    "staggerable": s.staggerable,
                    "stagger_mod": s.stagger_mod,
                    "night_spawn": s.night_spawn,
                    "patrol_points": s.patrol_points,
                    "loop_patrol": s.loop_patrol,
                    "random_wander_range": s.random_wander_range,
                    "spawn_upon_quest_complete_stable_key": s.spawn_upon_quest_complete_stable_key,
                    "protector_stable_key": s.protector_stable_key,
                    "spawn_chance": s.spawn_chance,
                    "is_common": s.is_common,
                    "is_rare": s.is_rare,
                    "is_wiki_generated": s.is_wiki_generated,
                    "is_map_visible": s.is_map_visible,
                }
            )
    writer.insert_character_spawns(spawn_out)
    logger.info(f"Characters: wrote {len(spawn_out)} spawn rows")

    # ------------------------------------------------------------------
    # Step 7: Write junction tables (filtered to all keys)
    # ------------------------------------------------------------------

    def _write_spell_junction(table: str, raw_table: str, insert_fn: Callable[[list[dict[str, object]]], int]) -> None:
        rows = _load_rows(raw, f"SELECT CharacterStableKey, SpellStableKey FROM {raw_table}")
        rows = [r for r in rows if r["CharacterStableKey"] in all_keys]
        insert_fn(
            [
                {
                    "character_stable_key": r["CharacterStableKey"],
                    "spell_stable_key": r["SpellStableKey"],
                }
                for r in rows
            ]
        )

    _write_spell_junction("character_attack_spells", "CharacterAttackSpells", writer.insert_character_attack_spells)
    _write_spell_junction("character_buff_spells", "CharacterBuffSpells", writer.insert_character_buff_spells)
    _write_spell_junction("character_heal_spells", "CharacterHealSpells", writer.insert_character_heal_spells)
    _write_spell_junction(
        "character_group_heal_spells", "CharacterGroupHealSpells", writer.insert_character_group_heal_spells
    )
    _write_spell_junction("character_cc_spells", "CharacterCCSpells", writer.insert_character_cc_spells)
    _write_spell_junction("character_taunt_spells", "CharacterTauntSpells", writer.insert_character_taunt_spells)

    # Attack skills
    skill_rows = _load_rows(raw, "SELECT CharacterStableKey, SkillStableKey FROM CharacterAttackSkills")
    skill_rows = [r for r in skill_rows if r["CharacterStableKey"] in all_keys]
    writer.insert_character_attack_skills(
        [
            {
                "character_stable_key": r["CharacterStableKey"],
                "skill_stable_key": r["SkillStableKey"],
            }
            for r in skill_rows
        ]
    )

    # Vendor items
    vi_rows = _load_rows(raw, "SELECT CharacterStableKey, ItemStableKey FROM CharacterVendorItems")
    vi_rows = [r for r in vi_rows if r["CharacterStableKey"] in all_keys]
    writer.insert_character_vendor_items(
        [
            {
                "character_stable_key": r["CharacterStableKey"],
                "item_stable_key": r["ItemStableKey"],
            }
            for r in vi_rows
        ]
    )

    # Aggressive factions
    af_rows = _load_rows(raw, "SELECT CharacterStableKey, FactionName FROM CharacterAggressiveFactions")
    af_rows = [r for r in af_rows if r["CharacterStableKey"] in all_keys]
    writer.insert_character_aggressive_factions(
        [
            {
                "character_stable_key": r["CharacterStableKey"],
                "faction_name": r["FactionName"],
            }
            for r in af_rows
        ]
    )

    # Allied factions
    all_rows = _load_rows(raw, "SELECT CharacterStableKey, FactionName FROM CharacterAlliedFactions")
    all_rows = [r for r in all_rows if r["CharacterStableKey"] in all_keys]
    writer.insert_character_allied_factions(
        [
            {
                "character_stable_key": r["CharacterStableKey"],
                "faction_name": r["FactionName"],
            }
            for r in all_rows
        ]
    )

    # Faction modifiers
    fm_rows = _load_rows(
        raw, "SELECT CharacterStableKey, FactionStableKey, ModifierValue FROM CharacterFactionModifiers"
    )
    fm_rows = [r for r in fm_rows if r["CharacterStableKey"] in all_keys]
    writer.insert_character_faction_modifiers(
        [
            {
                "character_stable_key": r["CharacterStableKey"],
                "faction_stable_key": r["FactionStableKey"],
                "modifier_value": r["ModifierValue"],
            }
            for r in fm_rows
        ]
    )

    # Death shouts
    ds_rows = _load_rows(raw, "SELECT CharacterStableKey, SequenceIndex, ShoutText FROM CharacterDeathShouts")
    ds_rows = [r for r in ds_rows if r["CharacterStableKey"] in all_keys]
    writer.insert_character_death_shouts(
        [
            {
                "character_stable_key": r["CharacterStableKey"],
                "sequence_index": r["SequenceIndex"],
                "shout_text": r["ShoutText"],
            }
            for r in ds_rows
        ]
    )

    # Vendor quest unlocks
    vqu_rows = _load_rows(raw, "SELECT CharacterStableKey, QuestStableKey FROM CharacterVendorQuestUnlocks")
    vqu_rows = [r for r in vqu_rows if r["CharacterStableKey"] in all_keys]
    writer.insert_character_vendor_quest_unlocks(
        [
            {
                "character_stable_key": r["CharacterStableKey"],
                "quest_stable_key": r["QuestStableKey"],
            }
            for r in vqu_rows
        ]
    )

    # Quest manager quests
    qm_rows = _load_rows(raw, "SELECT CharacterStableKey, QuestStableKey FROM CharacterQuestManagerQuests")
    qm_rows = [r for r in qm_rows if r["CharacterStableKey"] in all_keys]
    writer.insert_character_quest_manager_quests(
        [
            {
                "character_stable_key": r["CharacterStableKey"],
                "quest_stable_key": r["QuestStableKey"],
            }
            for r in qm_rows
        ]
    )

    # Loot drops
    ld_rows = _load_rows(raw, "SELECT * FROM LootDrops")
    ld_rows = [r for r in ld_rows if r["CharacterStableKey"] in all_keys]
    writer.insert_loot_drops(
        [
            {
                "character_stable_key": r["CharacterStableKey"],
                "item_stable_key": r["ItemStableKey"],
                "drop_probability": r["DropProbability"],
                "expected_per_kill": r["ExpectedPerKill"],
                "drop_count_distribution": r["DropCountDistribution"],
                "is_actual": r["IsActual"],
                "is_guaranteed": r["IsGuaranteed"],
                "is_common": r["IsCommon"],
                "is_uncommon": r["IsUncommon"],
                "is_rare": r["IsRare"],
                "is_legendary": r["IsLegendary"],
                "is_ultra_rare": r["IsUltraRare"],
                "is_unique": r["IsUnique"],
                "is_visible": r["IsVisible"],
                "zone": r["Zone"],
            }
            for r in ld_rows
        ]
    )

    # Dialogs (full dialog rows, not just quest keys)
    all_dialog_rows = _load_rows(raw, "SELECT * FROM CharacterDialogs")
    all_dialog_rows = [r for r in all_dialog_rows if r["CharacterStableKey"] in all_keys]
    writer.insert_character_dialogs(
        [
            {
                "character_stable_key": r["CharacterStableKey"],
                "dialog_index": r["DialogIndex"],
                "dialog_text": r["DialogText"],
                "keywords": r["Keywords"],
                "give_item_stable_key": r["GiveItemStableKey"],
                "assign_quest_stable_key": r["AssignQuestStableKey"],
                "complete_quest_stable_key": r["CompleteQuestStableKey"],
                "repeating_quest_dialog": r["RepeatingQuestDialog"],
                "kill_self_on_say": r["KillSelfOnSay"],
                "required_quest_stable_key": r["RequiredQuestStableKey"],
                "spawn_character_stable_key": r["SpawnCharacterStableKey"],
            }
            for r in all_dialog_rows
        ]
    )

    # SpawnPointPatrolPoints — filtered to spawn points used by surviving characters
    surviving_sp_keys: set[str] = set()
    for spawn_row in spawn_out:
        sp = cast("str | None", spawn_row.get("spawn_point_stable_key"))
        if sp is not None:
            surviving_sp_keys.add(sp)

    pp_rows = _load_rows(raw, "SELECT * FROM SpawnPointPatrolPoints")
    pp_rows = [r for r in pp_rows if r["SpawnPointStableKey"] in surviving_sp_keys]
    writer.insert_spawn_point_patrol_points(
        [
            {
                "spawn_point_stable_key": r["SpawnPointStableKey"],
                "sequence_index": r["SequenceIndex"],
                "x": r["X"],
                "y": r["Y"],
                "z": r["Z"],
            }
            for r in pp_rows
        ]
    )

    # SpawnPointStopQuests
    sq_rows = _load_rows(raw, "SELECT * FROM SpawnPointStopQuests")
    sq_rows = [r for r in sq_rows if r["SpawnPointStableKey"] in surviving_sp_keys]
    writer.insert_spawn_point_stop_quests(
        [
            {
                "spawn_point_stable_key": r["SpawnPointStableKey"],
                "quest_stable_key": r["QuestStableKey"],
            }
            for r in sq_rows
        ]
    )

    logger.info(f"Characters: processing complete ({len(char_data)} characters written)")
