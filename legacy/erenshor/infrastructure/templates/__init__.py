"""Infrastructure templates - Jinja2 rendering and contexts."""

from erenshor.infrastructure.templates.contexts import (
    AbilityBookInfoboxContext,
    AbilityInfoboxContext,
    AuraInfoboxContext,
    CharacterInfoboxContext,
    EnemyInfoboxContext,
    FancyArmorColumn,
    FancyArmorTableContext,
    FancyArmorTemplateContext,
    FancyWeaponColumn,
    FancyWeaponTableContext,
    FancyWeaponTemplateContext,
    FishingRow,
    FishingTableContext,
    ItemInfoboxContext,
)
from erenshor.infrastructure.templates.engine import (
    build_env,
    render_template,
)

__all__ = [
    # Engine
    "build_env",
    "render_template",
    # Contexts
    "AbilityInfoboxContext",
    "CharacterInfoboxContext",
    "EnemyInfoboxContext",
    "FishingRow",
    "FishingTableContext",
    "ItemInfoboxContext",
    "AbilityBookInfoboxContext",
    "AuraInfoboxContext",
    "FancyWeaponColumn",
    "FancyWeaponTableContext",
    "FancyArmorColumn",
    "FancyArmorTableContext",
    "FancyWeaponTemplateContext",
    "FancyArmorTemplateContext",
]
