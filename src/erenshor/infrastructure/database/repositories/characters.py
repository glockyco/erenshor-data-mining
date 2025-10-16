"""Character repository - database queries for characters."""

from __future__ import annotations

from typing import Any, List

from sqlalchemy import text
from sqlalchemy.engine import Engine

from erenshor.domain.entities import DbCharacter
from erenshor.infrastructure.database.junction_enricher import JunctionEnricher

__all__ = [
    "get_character_by_object_name",
    "get_characters",
    "get_characters_dropping_item",
    "get_loot_for_character",
    "get_spawnpoints_for_character",
    "get_vendors_selling_item_by_name",
]


def get_character_by_object_name(
    engine: Engine, object_name: str
) -> DbCharacter | None:
    """Fetch a character by ObjectName (for summon spell lookups).

    Args:
        engine: Database engine
        object_name: The ObjectName value (e.g., "Summoned Dire Wolf")

    Returns:
        DbCharacter if found, None otherwise
    """
    sql = text(
        """
        SELECT c.Id AS Id,
               c.Guid AS Guid,
               c.ObjectName AS ObjectName,
               c.NPCName AS NPCName,
               COALESCE(c.MyWorldFaction, '') AS MyWorldFaction,
               COALESCE(c.MyFaction, '') AS MyFaction,
               COALESCE(c.AggroRange, 0.0) AS AggroRange,
               COALESCE(c.AttackRange, 0.0) AS AttackRange,
               COALESCE(c.IsPrefab, 0) AS IsPrefab,
               COALESCE(c.IsNPC, 0) AS IsNPC,
               COALESCE(c.IsSimPlayer, 0) AS IsSimPlayer,
               COALESCE(c.IsFriendly, 0) AS IsFriendly,
               COALESCE(c.IsUnique, 0) AS IsUnique,
               COALESCE(c.IsRare, 0) AS IsRare,
               COALESCE(c.IsVendor, 0) AS IsVendor,
               COALESCE(c.IsMiningNode, 0) AS IsMiningNode,
               COALESCE(c.HasStats, 0) AS HasStats,
               COALESCE(c.HasModifyFaction, 0) AS HasModifyFaction,
               COALESCE(c.Invulnerable, 0) AS Invulnerable,
               COALESCE(c.ShoutOnDeath, '') AS ShoutOnDeath,
               COALESCE(c.QuestCompleteOnDeath, '') AS QuestCompleteOnDeath,
               COALESCE(c.DestroyOnDeath, 0) AS DestroyOnDeath,
               co.Scene AS Scene,
               za.ZoneName AS ZoneName,
               co.X AS X,
               co.Y AS Y,
               co.Z AS Z,
               COALESCE(c.Level, 0) AS Level,
               COALESCE(c.BaseXpMin, 0) AS BaseXpMin,
               COALESCE(c.BaseXpMax, 0) AS BaseXpMax,
               COALESCE(c.BossXpMultiplier, 1.0) AS BossXpMultiplier,
               COALESCE(c.BaseHP, 0) AS BaseHP,
               COALESCE(c.BaseAC, 0) AS BaseAC,
               COALESCE(c.BaseMana, 0) AS BaseMana,
               COALESCE(c.BaseStr, 0) AS BaseStr,
               COALESCE(c.BaseEnd, 0) AS BaseEnd,
               COALESCE(c.BaseDex, 0) AS BaseDex,
               COALESCE(c.BaseAgi, 0) AS BaseAgi,
               COALESCE(c.BaseInt, 0) AS BaseInt,
               COALESCE(c.BaseWis, 0) AS BaseWis,
               COALESCE(c.BaseCha, 0) AS BaseCha,
               COALESCE(c.BaseRes, 0) AS BaseRes,
               COALESCE(c.EffectiveMinMR, 0) AS EffectiveMinMR,
               COALESCE(c.EffectiveMaxMR, 0) AS EffectiveMaxMR,
               COALESCE(c.EffectiveMinER, 0) AS EffectiveMinER,
               COALESCE(c.EffectiveMaxER, 0) AS EffectiveMaxER,
               COALESCE(c.EffectiveMinPR, 0) AS EffectiveMinPR,
               COALESCE(c.EffectiveMaxPR, 0) AS EffectiveMaxPR,
               COALESCE(c.EffectiveMinVR, 0) AS EffectiveMinVR,
               COALESCE(c.EffectiveMaxVR, 0) AS EffectiveMaxVR,
               COALESCE(c.RunSpeed, 0.0) AS RunSpeed,
               COALESCE(c.BaseLifeSteal, 0.0) AS BaseLifeSteal,
               COALESCE(c.BaseMHAtkDelay, 0.0) AS BaseMHAtkDelay,
               COALESCE(c.BaseOHAtkDelay, 0.0) AS BaseOHAtkDelay,
               COALESCE(c.PetSpell, '') AS PetSpell,
               COALESCE(c.ProcOnHit, '') AS ProcOnHit,
               COALESCE(c.ProcOnHitChance, 0.0) AS ProcOnHitChance,
               COALESCE(c.VendorDesc, '') AS VendorDesc
        FROM Characters c
        LEFT JOIN Coordinates co ON c.CoordinateId = co.Id
        LEFT JOIN ZoneAnnounces za ON za.SceneName = co.Scene
        WHERE c.ObjectName = :object_name
        AND c.NPCName IS NOT NULL AND c.NPCName <> ''
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"object_name": object_name}).mappings().first()
    return DbCharacter.model_validate(dict(row)) if row else None


def get_characters(engine: Engine) -> List[DbCharacter]:
    """Fetch all characters from the database with junction table data.

    Junction fields populated:
        - AggressiveFactions: From CharacterAggressiveFactions
        - AlliedFactions: From CharacterAlliedFactions
        - AttackSkills: From CharacterAttackSkills
        - AttackSpells: From CharacterAttackSpells
        - BuffSpells: From CharacterBuffSpells
        - CCSpells: From CharacterCCSpells
        - FactionModifiers: From CharacterFactionModifiers
        - GroupHealSpells: From CharacterGroupHealSpells
        - HealSpells: From CharacterHealSpells
        - TauntSpells: From CharacterTauntSpells
        - VendorItems: From CharacterVendorItems
    """
    sql = text(
        """
        SELECT c.Id AS Id,
               c.Guid AS Guid,
               c.ObjectName AS ObjectName,
               c.NPCName AS NPCName,
               COALESCE(c.MyWorldFaction, '') AS MyWorldFaction,
               COALESCE(c.MyFaction, '') AS MyFaction,
               COALESCE(c.AggroRange, 0.0) AS AggroRange,
               COALESCE(c.AttackRange, 0.0) AS AttackRange,
               COALESCE(c.IsPrefab, 0) AS IsPrefab,
               COALESCE(c.IsNPC, 0) AS IsNPC,
               COALESCE(c.IsSimPlayer, 0) AS IsSimPlayer,
               COALESCE(c.IsFriendly, 0) AS IsFriendly,
               COALESCE(c.IsUnique, 0) AS IsUnique,
               COALESCE(c.IsRare, 0) AS IsRare,
               COALESCE(c.IsVendor, 0) AS IsVendor,
               COALESCE(c.IsMiningNode, 0) AS IsMiningNode,
               COALESCE(c.HasStats, 0) AS HasStats,
               COALESCE(c.HasModifyFaction, 0) AS HasModifyFaction,
               COALESCE(c.Invulnerable, 0) AS Invulnerable,
               COALESCE(c.ShoutOnDeath, '') AS ShoutOnDeath,
               COALESCE(c.QuestCompleteOnDeath, '') AS QuestCompleteOnDeath,
               COALESCE(c.DestroyOnDeath, 0) AS DestroyOnDeath,
               co.Scene AS Scene,
               za.ZoneName AS ZoneName,
               co.X AS X,
               co.Y AS Y,
               co.Z AS Z,
               COALESCE(c.Level, 0) AS Level,
               COALESCE(c.BaseXpMin, 0) AS BaseXpMin,
               COALESCE(c.BaseXpMax, 0) AS BaseXpMax,
               COALESCE(c.BossXpMultiplier, 1.0) AS BossXpMultiplier,
               COALESCE(c.BaseHP, 0) AS BaseHP,
               COALESCE(c.BaseAC, 0) AS BaseAC,
               COALESCE(c.BaseMana, 0) AS BaseMana,
               COALESCE(c.BaseStr, 0) AS BaseStr,
               COALESCE(c.BaseEnd, 0) AS BaseEnd,
               COALESCE(c.BaseDex, 0) AS BaseDex,
               COALESCE(c.BaseAgi, 0) AS BaseAgi,
               COALESCE(c.BaseInt, 0) AS BaseInt,
               COALESCE(c.BaseWis, 0) AS BaseWis,
               COALESCE(c.BaseCha, 0) AS BaseCha,
               COALESCE(c.BaseRes, 0) AS BaseRes,
               COALESCE(c.EffectiveMinMR, 0) AS EffectiveMinMR,
               COALESCE(c.EffectiveMaxMR, 0) AS EffectiveMaxMR,
               COALESCE(c.EffectiveMinER, 0) AS EffectiveMinER,
               COALESCE(c.EffectiveMaxER, 0) AS EffectiveMaxER,
               COALESCE(c.EffectiveMinPR, 0) AS EffectiveMinPR,
               COALESCE(c.EffectiveMaxPR, 0) AS EffectiveMaxPR,
               COALESCE(c.EffectiveMinVR, 0) AS EffectiveMinVR,
               COALESCE(c.EffectiveMaxVR, 0) AS EffectiveMaxVR,
               COALESCE(c.RunSpeed, 0.0) AS RunSpeed,
               COALESCE(c.BaseLifeSteal, 0.0) AS BaseLifeSteal,
               COALESCE(c.BaseMHAtkDelay, 0.0) AS BaseMHAtkDelay,
               COALESCE(c.BaseOHAtkDelay, 0.0) AS BaseOHAtkDelay,
               COALESCE(c.PetSpell, '') AS PetSpell,
               COALESCE(c.ProcOnHit, '') AS ProcOnHit,
               COALESCE(c.ProcOnHitChance, 0.0) AS ProcOnHitChance,
               COALESCE(c.VendorDesc, '') AS VendorDesc
        FROM Characters c
        LEFT JOIN Coordinates co ON c.CoordinateId = co.Id
        LEFT JOIN ZoneAnnounces za ON za.SceneName = co.Scene
        WHERE c.NPCName IS NOT NULL AND c.NPCName <> ''
        ORDER BY c.NPCName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    characters = [DbCharacter.model_validate(dict(r)) for r in rows]

    # Enrich with junction table data
    enricher = JunctionEnricher(engine)
    enricher.enrich(
        characters,
        [
            "CharacterAggressiveFactions",
            "CharacterAlliedFactions",
            "CharacterAttackSkills",
            "CharacterAttackSpells",
            "CharacterBuffSpells",
            "CharacterCCSpells",
            "CharacterFactionModifiers",
            "CharacterGroupHealSpells",
            "CharacterHealSpells",
            "CharacterTauntSpells",
            "CharacterVendorItems",
        ],
    )

    return characters


def get_loot_for_character(engine: Engine, character_guid: str) -> list[dict[str, Any]]:
    """Return loot entries with item names and flags for a character prefab guid."""
    sql = text(
        """
        SELECT ld.ItemId,
               ld.DropProbability,
               ld.IsGuaranteed,
               COALESCE(ld.IsActual, 0) AS IsActual,
               ld.IsCommon,
               ld.IsUncommon,
               ld.IsRare,
               ld.IsLegendary,
               ld.IsVisible,
               COALESCE(ld.IsUnique, 0) AS IsUnique,
               i.ItemName,
               i.ResourceName,
               COALESCE(i.ItemIconName, '') AS ItemIconName,
               COALESCE(i."Unique", 0) AS ItemUnique
        FROM LootDrops ld
        LEFT JOIN Items i ON i.Id = ld.ItemId
        WHERE ld.CharacterPrefabGuid = :guid
        ORDER BY ld.DropProbability DESC, i.ItemName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"guid": character_guid}).mappings().all()
    data: list[dict[str, Any]] = []
    for row in rows:
        loot_entry = dict(row)
        # Skip placeholder/common world drop aggregations that don't resolve to a concrete item
        if (
            loot_entry.get("ItemName") is None
            and isinstance(loot_entry.get("ItemId"), str)
            and not loot_entry["ItemId"].isdigit()
        ):
            continue
        data.append(loot_entry)
    return data


def get_spawnpoints_for_character(
    engine: Engine, character_guid: str
) -> list[dict[str, Any]]:
    """Detailed spawnpoints with scene, zone display, base respawn and coordinates/chance."""
    sql = text(
        """
        SELECT co.Scene AS Scene,
               COALESCE(za.ZoneName, co.Scene) AS ZoneDisplay,
               sp.SpawnDelay1 AS BaseRespawn,
               co.X AS X,
               co.Y AS Y,
               co.Z AS Z,
               spc.SpawnChance AS SpawnChance,
               COALESCE(spc.IsRare, 0) AS IsRare,
               COALESCE(c.IsUnique, 0) AS IsUnique
        FROM SpawnPoints sp
        JOIN SpawnPointCharacters spc ON spc.SpawnPointId = sp.Id
        JOIN Coordinates co ON co.SpawnPointId = sp.Id
        JOIN Characters c ON c.Guid = spc.CharacterGuid
        LEFT JOIN ZoneAnnounces za ON za.SceneName = co.Scene
        WHERE spc.CharacterGuid = :guid AND COALESCE(spc.SpawnChance,0) > 0
        ORDER BY co.Scene COLLATE NOCASE, co.X, co.Y, co.Z
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"guid": character_guid}).mappings().all()
    return [dict(r) for r in rows]


def get_characters_dropping_item(engine: Engine, item_id: str) -> list[dict[str, Any]]:
    """Return characters (prefab) that drop a given item id with drop probability flags.

    Includes character names and prefab metadata to construct stable identifiers for mapping.
    """
    sql = text(
        """
        SELECT ld.CharacterPrefabGuid AS Guid,
               COALESCE(ld.DropProbability, 0.0) AS DropProbability,
               COALESCE(ld.IsGuaranteed, 0) AS IsGuaranteed,
               c.NPCName AS NPCName,
               COALESCE(c.IsPrefab, 0) AS IsPrefab,
               c.ObjectName AS ObjectName,
               co.Scene AS Scene,
               co.X AS X,
               co.Y AS Y,
               co.Z AS Z
        FROM LootDrops ld
        LEFT JOIN Characters c ON c.Guid = ld.CharacterPrefabGuid
        LEFT JOIN Coordinates co ON co.CharacterId = c.Id
        WHERE ld.ItemId = :item_id
        AND COALESCE(ld.DropProbability, 0.0) > 0.0
        ORDER BY COALESCE(ld.DropProbability, 0.0) DESC, c.NPCName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"item_id": item_id}).mappings().all()
    return [dict(r) for r in rows]


def get_vendors_selling_item_by_name(
    engine: Engine, item_name: str
) -> list[dict[str, Any]]:
    """Return characters (vendors) that sell the given item.

    Uses CharacterVendorItems junction table for direct item name lookup.
    Matching is case-insensitive.
    """
    sql = text(
        """
        SELECT DISTINCT c.Guid AS Guid,
               c.NPCName AS NPCName,
               COALESCE(c.IsPrefab, 0) AS IsPrefab,
               c.ObjectName AS ObjectName,
               co.Scene AS Scene,
               co.X AS X,
               co.Y AS Y,
               co.Z AS Z
        FROM Characters c
        JOIN CharacterVendorItems cvi ON c.Id = cvi.CharacterId
        LEFT JOIN Coordinates co ON co.CharacterId = c.Id
        WHERE lower(cvi.ItemName) = lower(:item_name)
        ORDER BY c.NPCName COLLATE NOCASE, c.Guid
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"item_name": item_name}).mappings().all()
    return [dict(row) for row in rows]
