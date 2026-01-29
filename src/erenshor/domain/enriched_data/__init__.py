"""Enriched data DTOs for passing data between enrichers and generators.

These data transfer objects carry entity data along with related enrichments
(like spawn points, loot drops, teaching items, etc.) from enricher services
to template generators.
"""

from erenshor.domain.enriched_data.character import EnrichedCharacterData
from erenshor.domain.enriched_data.item import EnrichedItemData
from erenshor.domain.enriched_data.skill import EnrichedSkillData
from erenshor.domain.enriched_data.spell import EnrichedSpellData
from erenshor.domain.enriched_data.stance import EnrichedStanceData

__all__ = [
    "EnrichedCharacterData",
    "EnrichedItemData",
    "EnrichedSkillData",
    "EnrichedSpellData",
    "EnrichedStanceData",
]
