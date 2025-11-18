"""Character enrichment service for wiki generation.

This service aggregates and formats all character-related data for wiki template generation:
- Faction modifiers with display name translation
- Spawn point locations (zones, coordinates, respawn times)
- Loot drops with percentages and wiki links
- Spells/abilities the character can use
- Enemy type classification (Boss/Rare/Enemy/NPC)
"""

from loguru import logger

from erenshor.domain.enriched_data.character import EnrichedCharacterData
from erenshor.domain.entities.character import Character
from erenshor.infrastructure.database.repositories.loot_tables import LootTableRepository
from erenshor.infrastructure.database.repositories.spawn_points import SpawnPointRepository
from erenshor.infrastructure.database.repositories.spells import SpellRepository

__all__ = ["CharacterEnricher", "EnrichedCharacterData"]


class CharacterEnricher:
    """Service for enriching characters with related data.

    Aggregates data from multiple repositories. Formatting is done by template generators.
    """

    def __init__(
        self,
        spawn_repo: SpawnPointRepository,
        loot_repo: LootTableRepository,
        spell_repo: SpellRepository,
    ) -> None:
        """Initialize character enricher.

        Args:
            spawn_repo: Repository for spawn point data
            loot_repo: Repository for loot table data
            spell_repo: Repository for spell data (abilities character can use)
        """
        self._spawn_repo = spawn_repo
        self._loot_repo = loot_repo
        self._spell_repo = spell_repo

    def enrich(self, character: Character) -> EnrichedCharacterData:
        """Enrich character with related data from other tables.

        Args:
            character: Character entity

        Returns:
            EnrichedCharacterData with spawn points, loot, spells, and faction data
        """
        logger.debug(f"Enriching character: {character.npc_name}")

        # Get spawn points
        spawn_infos = self._spawn_repo.get_spawn_info_for_character(
            character_stable_key=character.stable_key,
            is_prefab=bool(character.is_prefab),
        )

        # Get loot drops
        loot_drops = self._loot_repo.get_loot_for_character(character.stable_key)

        # Get spells/abilities this character can use
        spells = self._spell_repo.get_spells_used_by_character(character.stable_key)
        logger.debug(f"Character '{character.npc_name}' uses {len(spells)} spells")

        return EnrichedCharacterData(
            character=character,
            spawn_infos=spawn_infos,
            loot_drops=loot_drops,
            spells=spells,
        )
