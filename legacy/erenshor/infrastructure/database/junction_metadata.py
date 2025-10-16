"""Junction table metadata registry for generic data enrichment.

This module provides declarative metadata for junction tables, enabling
generic batch-loading logic without repetitive manual code. Each junction
table is described once with its structure and aggregation rules, then
the enricher can automatically populate entity fields.

Design Philosophy:
- Metadata-driven: Declare structure once, use everywhere
- Type-safe: Explicit types for all configuration
- DRY: Eliminate repetitive batch-fetch code
- Explicit: Clear aggregation rules, no magic
- Testable: Centralized logic, tested once

SECURITY WARNING:
Table names, column names, and SQL fragments in metadata are interpolated
directly into SQL queries. Only use trusted, hardcoded metadata from this
registry. NEVER construct metadata from user input or external sources.
All metadata in JUNCTION_METADATA should be defined by developers, not
dynamically generated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, Type

from erenshor.domain.value_objects.crafting import CraftingMaterial, CraftingReward
from erenshor.domain.value_objects.faction import FactionModifier


class JunctionAggregation(Enum):
    """How to aggregate junction table rows into entity field values.

    Defines the strategy for combining multiple junction rows that belong
    to the same parent entity into a single value for the entity's field.
    """

    COMMA_SEPARATED = "comma_separated"
    """Aggregate first column values into comma-separated string.

    Example: ["Arcanist", "Druid"] -> "Arcanist, Druid"
    Used for: ItemClasses.ClassName, SpellClasses.ClassName
    """

    LIST_OF_STRINGS = "list_of_strings"
    """Aggregate first column values into list of strings.

    Example: ["Bag1", "Bag2"] -> ["Bag1", "Bag2"]
    Used for: Junction tables returning simple lists
    """

    LIST_OF_OBJECTS = "list_of_objects"
    """Convert each row to dataclass instance, return list.

    Example: [{col1: v1, col2: v2}] -> [DataClass(col1=v1, col2=v2)]
    Used for: Complex junction tables with multiple columns
    Requires: dataclass_type parameter
    """

    CUSTOM = "custom"
    """Use custom aggregator function for complex logic.

    Example: Custom formatting or transformation
    Used for: Special cases that don't fit standard patterns
    Requires: custom_aggregator parameter
    """


@dataclass
class JunctionMeta:
    """Metadata describing a junction table's structure and enrichment rules.

    This metadata enables generic batch-loading: the enricher reads this
    configuration to know how to query the junction table and populate
    the target entity field.

    Attributes:
        table: Junction table name in database
        entity_id_field: Field name on entity object (e.g., "Id", "SpellDBIndex")
        entity_id_column: Column name in junction table (e.g., "ItemId", "SpellId")
        target_field: Field name on entity to populate (e.g., "Classes", "Bags")
        related_columns: Column names to fetch from junction table
        aggregation: How to combine rows into target field value
        filter_clause: Optional WHERE clause filter (without "WHERE" keyword)
        order_by: Optional ORDER BY expression (without "ORDER BY" keyword)
        separator: Separator for COMMA_SEPARATED aggregation (default ", ")
        dataclass_type: Dataclass for LIST_OF_OBJECTS aggregation
        custom_aggregator: Function for CUSTOM aggregation
        column_to_field_map: Optional explicit SQL column to dataclass field mapping.
                            If not provided, columns are lowercased to match fields.

    Example:
        ItemClasses junction table metadata:

        JunctionMeta(
            table="ItemClasses",
            entity_id_field="Id",           # DbItem.Id
            entity_id_column="ItemId",      # ItemClasses.ItemId
            target_field="Classes",         # DbItem.Classes
            related_columns=["ClassName"],  # ItemClasses.ClassName
            aggregation=JunctionAggregation.COMMA_SEPARATED,
            order_by="ClassName",           # Sort alphabetically
        )

        SQL generated:
        SELECT ItemId, ClassName
        FROM ItemClasses
        WHERE ItemId IN (...)
        ORDER BY ItemId, ClassName

        Result: DbItem.Classes = "Arcanist, Druid, Paladin"
    """

    table: str
    entity_id_field: str
    entity_id_column: str
    target_field: str
    related_columns: list[str]
    aggregation: JunctionAggregation
    filter_clause: Optional[str] = None
    order_by: Optional[str] = None
    separator: str = ", "
    dataclass_type: Optional[Type[Any]] = None
    custom_aggregator: Optional[Callable[[list[dict[str, Any]]], Any]] = None
    column_to_field_map: Optional[dict[str, str]] = (
        None  # Maps SQL column -> dataclass field
    )

    def __post_init__(self) -> None:
        """Validate metadata configuration after initialization.

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate required fields
        if not self.table:
            raise ValueError("table cannot be empty")
        if not self.entity_id_field:
            raise ValueError("entity_id_field cannot be empty")
        if not self.entity_id_column:
            raise ValueError("entity_id_column cannot be empty")
        if not self.target_field:
            raise ValueError("target_field cannot be empty")
        if not self.related_columns:
            raise ValueError("related_columns cannot be empty")

        # Validate aggregation-specific requirements
        if self.aggregation == JunctionAggregation.LIST_OF_OBJECTS:
            if not self.dataclass_type:
                raise ValueError(
                    f"LIST_OF_OBJECTS aggregation requires dataclass_type for table {self.table}"
                )
        elif self.aggregation == JunctionAggregation.CUSTOM:
            if not self.custom_aggregator:
                raise ValueError(
                    f"CUSTOM aggregation requires custom_aggregator for table {self.table}"
                )


# Registry of all junction table metadata
# Add new junction tables here as they're migrated from CSV to junction tables
JUNCTION_METADATA: dict[str, JunctionMeta] = {
    "ItemClasses": JunctionMeta(
        table="ItemClasses",
        entity_id_field="Id",
        entity_id_column="ItemId",
        target_field="Classes",
        related_columns=["ClassName"],
        aggregation=JunctionAggregation.LIST_OF_STRINGS,
        order_by="ClassName",  # Alphabetical sorting matches current behavior
    ),
    "SpellClasses": JunctionMeta(
        table="SpellClasses",
        entity_id_field="SpellDBIndex",  # Note: Uses integer PK, not Id varchar
        entity_id_column="SpellId",
        target_field="Classes",
        related_columns=["ClassName"],
        aggregation=JunctionAggregation.LIST_OF_STRINGS,
        order_by="ClassName",  # Alphabetical sorting matches current behavior
    ),
    # Character junction tables
    "CharacterAggressiveFactions": JunctionMeta(
        table="CharacterAggressiveFactions",
        entity_id_field="Id",
        entity_id_column="CharacterId",
        target_field="AggressiveFactions",
        related_columns=["FactionName"],
        aggregation=JunctionAggregation.LIST_OF_STRINGS,
    ),
    "CharacterAlliedFactions": JunctionMeta(
        table="CharacterAlliedFactions",
        entity_id_field="Id",
        entity_id_column="CharacterId",
        target_field="AlliedFactions",
        related_columns=["FactionName"],
        aggregation=JunctionAggregation.LIST_OF_STRINGS,
    ),
    "CharacterAttackSkills": JunctionMeta(
        table="CharacterAttackSkills",
        entity_id_field="Id",
        entity_id_column="CharacterId",
        target_field="AttackSkills",
        related_columns=["SkillId"],
        aggregation=JunctionAggregation.LIST_OF_STRINGS,
    ),
    "CharacterAttackSpells": JunctionMeta(
        table="CharacterAttackSpells",
        entity_id_field="Id",
        entity_id_column="CharacterId",
        target_field="AttackSpells",
        related_columns=["SpellId"],
        aggregation=JunctionAggregation.LIST_OF_STRINGS,
    ),
    "CharacterBuffSpells": JunctionMeta(
        table="CharacterBuffSpells",
        entity_id_field="Id",
        entity_id_column="CharacterId",
        target_field="BuffSpells",
        related_columns=["SpellId"],
        aggregation=JunctionAggregation.LIST_OF_STRINGS,
    ),
    "CharacterCCSpells": JunctionMeta(
        table="CharacterCCSpells",
        entity_id_field="Id",
        entity_id_column="CharacterId",
        target_field="CCSpells",
        related_columns=["SpellId"],
        aggregation=JunctionAggregation.LIST_OF_STRINGS,
    ),
    "CharacterFactionModifiers": JunctionMeta(
        table="CharacterFactionModifiers",
        entity_id_field="Id",
        entity_id_column="CharacterId",
        target_field="FactionModifiers",
        related_columns=["FactionREFNAME", "ModifierValue"],
        aggregation=JunctionAggregation.LIST_OF_OBJECTS,
        dataclass_type=FactionModifier,
        order_by="FactionREFNAME",
        column_to_field_map={
            "FactionREFNAME": "faction_name",
            "ModifierValue": "modifier_value",
        },
    ),
    "CharacterGroupHealSpells": JunctionMeta(
        table="CharacterGroupHealSpells",
        entity_id_field="Id",
        entity_id_column="CharacterId",
        target_field="GroupHealSpells",
        related_columns=["SpellId"],
        aggregation=JunctionAggregation.LIST_OF_STRINGS,
    ),
    "CharacterHealSpells": JunctionMeta(
        table="CharacterHealSpells",
        entity_id_field="Id",
        entity_id_column="CharacterId",
        target_field="HealSpells",
        related_columns=["SpellId"],
        aggregation=JunctionAggregation.LIST_OF_STRINGS,
    ),
    "CharacterTauntSpells": JunctionMeta(
        table="CharacterTauntSpells",
        entity_id_field="Id",
        entity_id_column="CharacterId",
        target_field="TauntSpells",
        related_columns=["SpellId"],
        aggregation=JunctionAggregation.LIST_OF_STRINGS,
    ),
    "CharacterVendorItems": JunctionMeta(
        table="CharacterVendorItems",
        entity_id_field="Id",
        entity_id_column="CharacterId",
        target_field="VendorItems",
        related_columns=["ItemName"],
        aggregation=JunctionAggregation.LIST_OF_STRINGS,
    ),
    # Crafting junction tables
    "CraftingRecipes": JunctionMeta(
        table="CraftingRecipes",
        entity_id_field="Id",  # DbItem.Id
        entity_id_column="RecipeItemId",
        target_field="CraftingMaterials",
        related_columns=["MaterialItemId", "MaterialSlot", "MaterialQuantity"],
        aggregation=JunctionAggregation.LIST_OF_OBJECTS,
        dataclass_type=CraftingMaterial,
        order_by="MaterialSlot",  # Preserve slot ordering
        column_to_field_map={
            "MaterialItemId": "material_item_id",
            "MaterialSlot": "material_slot",
            "MaterialQuantity": "material_quantity",
        },
    ),
    "CraftingRewards": JunctionMeta(
        table="CraftingRewards",
        entity_id_field="Id",  # DbItem.Id
        entity_id_column="RecipeItemId",
        target_field="CraftingRewards",
        related_columns=["RewardItemId", "RewardSlot", "RewardQuantity"],
        aggregation=JunctionAggregation.LIST_OF_OBJECTS,
        dataclass_type=CraftingReward,
        order_by="RewardSlot",  # Preserve slot ordering
        column_to_field_map={
            "RewardItemId": "reward_item_id",
            "RewardSlot": "reward_slot",
            "RewardQuantity": "reward_quantity",
        },
    ),
}


def get_junction_meta(junction_name: str) -> JunctionMeta:
    """Get metadata for a junction table by name.

    Args:
        junction_name: Name of the junction table

    Returns:
        Junction table metadata

    Raises:
        KeyError: If junction table not registered
    """
    if junction_name not in JUNCTION_METADATA:
        available = ", ".join(sorted(JUNCTION_METADATA.keys()))
        raise KeyError(
            f"Junction table '{junction_name}' not found in metadata registry. "
            f"Available: {available}"
        )
    return JUNCTION_METADATA[junction_name]
