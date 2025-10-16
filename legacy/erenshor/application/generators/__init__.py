"""Application generators.

Generators stream content from database through templates to create wiki pages.
"""

from erenshor.application.generators.abilities import AbilityGenerator
from erenshor.application.generators.base import ContentGenerator, GeneratedContent
from erenshor.application.generators.characters import CharacterGenerator
from erenshor.application.generators.fishing import FishingGenerator
from erenshor.application.generators.items import ItemGenerator
from erenshor.application.generators.overviews import OverviewGenerator

__all__ = [
    "ContentGenerator",
    "GeneratedContent",
    "ItemGenerator",
    "CharacterGenerator",
    "AbilityGenerator",
    "FishingGenerator",
    "OverviewGenerator",
]
