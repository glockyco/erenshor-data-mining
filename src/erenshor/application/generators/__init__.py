"""Wiki template generators.

This module contains template generators for creating MediaWiki template wikitext
from game entities. Template generators handle SINGLE entities only - multi-entity
page assembly is handled by WikiService.

Includes category tag generation, field preservation, legacy template migration,
and content formatting.
"""

from erenshor.application.generators.categories import CategoryGenerator
from erenshor.application.generators.character_template_generator import CharacterTemplateGenerator
from erenshor.application.generators.field_preservation import (
    FieldPreservationConfig,
    FieldPreservationHandler,
    override_handler,
    prefer_manual_handler,
    preserve_handler,
)
from erenshor.application.generators.item_template_generator import ItemTemplateGenerator
from erenshor.application.generators.legacy_template_remover import LegacyTemplateRemover
from erenshor.application.generators.skill_template_generator import SkillTemplateGenerator
from erenshor.application.generators.spell_template_generator import SpellTemplateGenerator
from erenshor.application.generators.template_generator_base import TemplateGeneratorBase

__all__ = [
    "CategoryGenerator",
    "CharacterTemplateGenerator",
    "FieldPreservationConfig",
    "FieldPreservationHandler",
    "ItemTemplateGenerator",
    "LegacyTemplateRemover",
    "SkillTemplateGenerator",
    "SpellTemplateGenerator",
    "TemplateGeneratorBase",
    "override_handler",
    "prefer_manual_handler",
    "preserve_handler",
]
