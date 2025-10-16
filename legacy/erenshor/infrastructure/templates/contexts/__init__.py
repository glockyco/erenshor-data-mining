"""Template contexts for all content types.

All Pydantic models used for rendering Jinja2 templates.
Organized by content type: abilities, spells, skills, characters, fishing, items.

This module provides convenience imports for all context classes.
"""

from erenshor.infrastructure.templates.contexts.abilities import (
    AbilityInfoboxContext,
    SkillInfoboxContext,
    SpellInfoboxContext,
)
from erenshor.infrastructure.templates.contexts.characters import (
    CharacterInfoboxContext,
    EnemyInfoboxContext,
)
from erenshor.infrastructure.templates.contexts.fishing import (
    FishingRow,
    FishingTableContext,
)
from erenshor.infrastructure.templates.contexts.items import (
    AbilityBookInfoboxContext,
    AuraInfoboxContext,
    FancyArmorColumn,
    FancyArmorTableContext,
    FancyArmorTemplateContext,
    FancyCharmContext,
    FancyWeaponColumn,
    FancyWeaponTableContext,
    FancyWeaponTemplateContext,
    ItemInfoboxContext,
)

__all__ = [
    # Abilities (unified)
    "AbilityInfoboxContext",
    # Spells (separate)
    "SpellInfoboxContext",
    # Skills (separate)
    "SkillInfoboxContext",
    # Characters
    "CharacterInfoboxContext",
    "EnemyInfoboxContext",
    # Fishing
    "FishingRow",
    "FishingTableContext",
    # Items
    "ItemInfoboxContext",
    "AbilityBookInfoboxContext",
    "AuraInfoboxContext",
    "FancyWeaponColumn",
    "FancyWeaponTableContext",
    "FancyArmorColumn",
    "FancyArmorTableContext",
    "FancyWeaponTemplateContext",
    "FancyArmorTemplateContext",
    "FancyCharmContext",
]
