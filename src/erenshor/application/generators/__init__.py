"""Wiki page generators.

This module contains generators for creating MediaWiki pages from game data,
including category tag generation, field preservation, legacy template migration,
and content formatting.
"""

from erenshor.application.generators.categories import CategoryGenerator
from erenshor.application.generators.character_page_generator import CharacterPageGenerator
from erenshor.application.generators.field_preservation import (
    FieldPreservationConfig,
    FieldPreservationHandler,
    override_handler,
    prefer_manual_handler,
    preserve_handler,
)
from erenshor.application.generators.item_page_generator import ItemPageGenerator
from erenshor.application.generators.legacy_template_remover import LegacyTemplateRemover
from erenshor.application.generators.page_generator_base import PageGeneratorBase
from erenshor.application.generators.spell_page_generator import SpellPageGenerator

__all__ = [
    "CategoryGenerator",
    "CharacterPageGenerator",
    "FieldPreservationConfig",
    "FieldPreservationHandler",
    "ItemPageGenerator",
    "LegacyTemplateRemover",
    "PageGeneratorBase",
    "SpellPageGenerator",
    "override_handler",
    "prefer_manual_handler",
    "preserve_handler",
]
