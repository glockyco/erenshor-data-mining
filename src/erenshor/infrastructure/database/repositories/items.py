"""Item repository - database queries for items."""

from __future__ import annotations

from typing import List

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError as SQLAlchemyDatabaseError

from erenshor.domain.entities import DbItem, DbItemStats
from erenshor.domain.entities.recipe import CraftingRecipe
from erenshor.domain.exceptions import JunctionEnrichmentError
from erenshor.domain.value_objects.crafting import CraftingMaterial, CraftingReward
from erenshor.infrastructure.database.junction_enricher import JunctionEnricher

__all__ = [
    "get_auras",
    "get_consumables_and_ability_books",
    "get_crafting_recipe",
    "get_fishable_item_names",
    "get_item_stats",
    "get_items",
    "get_items_by_ids",
    "get_items_producing_item",
    "get_items_requiring_item",
    "get_mining_item_names",
]


def get_items(engine: Engine, *, obtainable_only: bool = True) -> List[DbItem]:
    """Fetch all items from the database with classes pre-populated from junction table.

    The Classes field is populated from the ItemClasses junction table using the
    generic JunctionEnricher.
    """
    sql = text(
        """
        SELECT Id,
               ItemName,
               ResourceName,
               COALESCE(ItemIconName, '') AS ItemIconName,
               COALESCE(ItemLevel, 0) AS ItemLevel,
               COALESCE(ItemValue, 0) AS ItemValue,
               COALESCE(SellValue, 0) AS SellValue,
               COALESCE(Template, 0) AS Template,
               COALESCE(ThisWeaponType, '') AS ThisWeaponType,
               COALESCE(WeaponDly, 0.0) AS WeaponDly,
               COALESCE(WeaponProcChance, 0) AS WeaponProcChance,
               COALESCE(WeaponProcOnHit, '') AS WeaponProcOnHit,
               COALESCE(IsWand, 0) AS IsWand,
               COALESCE(WandRange, 0.0) AS WandRange,
               COALESCE(WandProcChance, 0) AS WandProcChance,
               COALESCE(WandEffect, '') AS WandEffect,
               COALESCE(IsBow, 0) AS IsBow,
               COALESCE(BowEffect, '') AS BowEffect,
               COALESCE(BowProcChance, 0) AS BowProcChance,
               COALESCE(TeachSpell, '') AS TeachSpell,
               COALESCE(TeachSkill, '') AS TeachSkill,
               COALESCE(ItemEffectOnClick, '') AS ItemEffectOnClick,
               COALESCE(Lore, '') AS Lore,
               COALESCE(RequiredSlot, '') AS RequiredSlot,
               COALESCE(Relic, 0) AS Relic,
               COALESCE(Shield, 0) AS Shield,
               COALESCE(WornEffect, '') AS WornEffect,
               COALESCE(Disposable, 0) AS Disposable,
               COALESCE(CompleteOnRead, '') AS CompleteOnRead,
               COALESCE(Aura, '') AS Aura
        FROM Items
        WHERE COALESCE(ItemName, '') <> '' AND COALESCE(ResourceName, '') <> ''
        ORDER BY ItemName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
        items = [DbItem.model_validate(dict(r)) for r in rows]

    # Enrich with junction table data using generic enricher
    # Populates DbItem.Classes field from ItemClasses junction table
    # Populates DbItem.CraftingMaterials from CraftingRecipes junction table
    # Populates DbItem.CraftingRewards from CraftingRewards junction table
    enricher = JunctionEnricher(engine)
    enricher.enrich(
        items,
        [
            "ItemClasses",
            "CraftingRecipes",
            "CraftingRewards",
        ],
    )

    return items


def get_item_stats(engine: Engine, item_id: str) -> List[DbItemStats]:
    """Fetch item stats for a given item ID."""
    sql = text(
        """
        SELECT ItemId, Quality,
               COALESCE(WeaponDmg, 0) AS WeaponDmg,
               COALESCE(HP, 0) AS HP,
               COALESCE(AC, 0) AS AC,
               COALESCE(Mana, 0) AS Mana,
               COALESCE(Str, 0) AS Str,
               COALESCE(End, 0) AS End,
               COALESCE(Dex, 0) AS Dex,
               COALESCE(Agi, 0) AS Agi,
               COALESCE(Int, 0) AS Int,
               COALESCE(Wis, 0) AS Wis,
               COALESCE(Cha, 0) AS Cha,
               COALESCE(Res, 0) AS Res,
               COALESCE(MR, 0) AS MR,
               COALESCE(ER, 0) AS ER,
               COALESCE(PR, 0) AS PR,
               COALESCE(VR, 0) AS VR
        FROM ItemStats
        WHERE ItemId = :item_id
        ORDER BY CASE Quality
            WHEN 'Normal' THEN 0
            WHEN 'Blessed' THEN 1
            WHEN 'Godly' THEN 2
            WHEN '0' THEN 0
            WHEN '1' THEN 1
            WHEN '2' THEN 2
            ELSE 99 END,
            ItemId
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"item_id": item_id}).mappings().all()
    return [DbItemStats.model_validate(dict(r)) for r in rows]


def get_consumables_and_ability_books(
    engine: Engine,
) -> tuple[list[DbItem], list[DbItem]]:
    """Return consumables and ability books as separate lists."""
    items = get_items(engine, obtainable_only=False)
    ability_books: list[DbItem] = []
    consumables: list[DbItem] = []
    for item in items:
        is_ability_book = (
            (item.TeachSpell and item.TeachSpell.strip())
            or (item.TeachSkill and item.TeachSkill.strip())
            or item.ItemName.lower().startswith("spell scroll:")
        )
        if is_ability_book:
            ability_books.append(item)
        elif item.ItemEffectOnClick and item.ItemEffectOnClick.strip():
            slot = (item.RequiredSlot or "").strip().lower()
            if not slot or slot == "general":
                consumables.append(item)
    return consumables, ability_books


def get_auras(engine: Engine) -> list[DbItem]:
    """Return all aura items."""
    items = get_items(engine, obtainable_only=False)
    auras: list[DbItem] = []
    for item in items:
        slot = (item.RequiredSlot or "").strip().lower()
        if slot == "aura":
            auras.append(item)
    return auras


def get_items_by_ids(engine: Engine, item_ids: list[str]) -> list[DbItem]:
    """Fetch items by a list of IDs.

    Returns:
        List of DbItem entities with Id, ItemName, and ResourceName populated.
        Other fields are set to defaults since this is a lightweight query.
    """
    if not item_ids:
        return []
    placeholders = ",".join([":" + f"id{i}" for i in range(len(item_ids))])
    params = {f"id{i}": item_ids[i] for i in range(len(item_ids))}
    sql = text(
        f"""
        SELECT Id, ItemName, ResourceName
        FROM Items
        WHERE Id IN ({placeholders})
        ORDER BY ItemName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()
    return [DbItem.model_validate(dict(r)) for r in rows]


def get_fishable_item_names(engine: Engine) -> list[str]:
    """Return distinct item names that appear in WaterFishables.ItemName."""
    sql = text(
        """
        SELECT DISTINCT ItemName
        FROM WaterFishables
        WHERE COALESCE(ItemName,'') <> ''
        ORDER BY ItemName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).all()
    return [str(name) for (name,) in rows]


def get_mining_item_names(engine: Engine) -> list[str]:
    """Return distinct item names that appear in MiningNodeItems.ItemName."""
    sql = text(
        """
        SELECT DISTINCT ItemName
        FROM MiningNodeItems
        WHERE COALESCE(ItemName,'') <> ''
        ORDER BY ItemName COLLATE NOCASE
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).all()
    return [str(name) for (name,) in rows]


def get_items_producing_item(engine: Engine, item_id: str) -> list[DbItem]:
    """Items whose crafting recipe produces the given item.

    Uses CraftingRewards junction table to find items where this item appears
    as a reward. Returns enriched DbItem entities with all fields populated.

    Args:
        engine: Database engine
        item_id: ID of the item to search for as a reward

    Returns:
        List of DbItem entities representing molds/templates that produce this item
    """
    # Query for distinct recipe item IDs first, then fetch full items
    sql = text(
        """
        SELECT DISTINCT cr.RecipeItemId
        FROM CraftingRewards cr
        WHERE cr.RewardItemId = :item_id
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"item_id": item_id}).fetchall()
        recipe_ids = [str(row[0]) for row in rows]

    if not recipe_ids:
        return []

    # Use existing get_items_by_ids to fetch full items, then enrich
    items = get_items_by_ids(engine, recipe_ids)

    # Enrich with junction table data to populate all fields
    enricher = JunctionEnricher(engine)
    enricher.enrich(
        items,
        [
            "ItemClasses",
            "CraftingRecipes",
            "CraftingRewards",
        ],
    )

    return items


def get_items_requiring_item(engine: Engine, item_id: str) -> list[DbItem]:
    """Items whose crafting recipe requires the given item as a material.

    Uses CraftingRecipes junction table to find items where this item appears
    as a required material. Returns enriched DbItem entities with all fields populated.

    Args:
        engine: Database engine
        item_id: ID of the item to search for as a material

    Returns:
        List of DbItem entities representing molds/templates that require this item
    """
    # Query for distinct recipe item IDs first, then fetch full items
    sql = text(
        """
        SELECT DISTINCT cr.RecipeItemId
        FROM CraftingRecipes cr
        WHERE cr.MaterialItemId = :item_id
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"item_id": item_id}).fetchall()
        recipe_ids = [str(row[0]) for row in rows]

    if not recipe_ids:
        return []

    # Use existing get_items_by_ids to fetch full items, then enrich
    items = get_items_by_ids(engine, recipe_ids)

    # Enrich with junction table data to populate all fields
    enricher = JunctionEnricher(engine)
    enricher.enrich(
        items,
        [
            "ItemClasses",
            "CraftingRecipes",
            "CraftingRewards",
        ],
    )

    return items


def get_crafting_recipe(engine: Engine, item_id: str) -> CraftingRecipe | None:
    """Get crafting recipe from junction tables.

    Queries CraftingRecipes (materials) and CraftingRewards junction tables
    to build complete recipe. Returns None if item has no recipe data.

    Args:
        engine: Database engine
        item_id: Database ID of the mold/template item

    Returns:
        CraftingRecipe with materials and rewards, or None if no recipe exists

    Raises:
        JunctionEnrichmentError: If database query fails or data is malformed
    """
    try:
        # Query CraftingRecipes table for materials
        materials_sql = text(
            """
            SELECT MaterialItemId, MaterialSlot, MaterialQuantity
            FROM CraftingRecipes
            WHERE RecipeItemId = :item_id
            ORDER BY MaterialSlot
            """
        )

        # Query CraftingRewards table for rewards
        rewards_sql = text(
            """
            SELECT RewardItemId, RewardSlot, RewardQuantity
            FROM CraftingRewards
            WHERE RecipeItemId = :item_id
            ORDER BY RewardSlot
            """
        )

        with engine.connect() as conn:
            # Fetch materials
            material_rows = (
                conn.execute(materials_sql, {"item_id": item_id}).mappings().all()
            )
            materials = [
                CraftingMaterial(
                    material_item_id=str(row["MaterialItemId"]),
                    material_slot=int(row["MaterialSlot"]),
                    material_quantity=int(row["MaterialQuantity"]),
                )
                for row in material_rows
            ]

            # Fetch rewards
            reward_rows = (
                conn.execute(rewards_sql, {"item_id": item_id}).mappings().all()
            )
            rewards = [
                CraftingReward(
                    reward_item_id=str(row["RewardItemId"]),
                    reward_slot=int(row["RewardSlot"]),
                    reward_quantity=int(row["RewardQuantity"]),
                )
                for row in reward_rows
            ]

        # If no rewards, no recipe exists (materials alone don't make a recipe)
        if not rewards:
            return None

        # Build and return recipe (validates business rules via __post_init__)
        return CraftingRecipe(
            recipe_item_id=item_id,
            materials=materials,
            rewards=rewards,
        )

    except SQLAlchemyDatabaseError as e:
        raise JunctionEnrichmentError(
            f"Failed to query crafting recipe for item_id={item_id}: {e}"
        ) from e
    except (KeyError, ValueError, TypeError) as e:
        raise JunctionEnrichmentError(
            f"Malformed crafting recipe data for item_id={item_id}: {e}"
        ) from e
