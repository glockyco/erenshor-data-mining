"""Character enrichment service for wiki generation.

This service aggregates and formats all character-related data for wiki template generation:
- Faction modifiers with display name translation
- Spawn point locations (zones, coordinates, respawn times)
- Loot drops with percentages and wiki links
- Enemy type classification (Boss/Rare/Enemy/NPC)
"""

from loguru import logger

from erenshor.domain.entities.character import Character
from erenshor.domain.value_objects.loot import LootDropInfo
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
from erenshor.infrastructure.database.repositories.factions import FactionRepository
from erenshor.infrastructure.database.repositories.loot_tables import LootTableRepository
from erenshor.infrastructure.database.repositories.spawn_points import SpawnPointRepository

__all__ = ["CharacterEnricher", "EnrichedCharacterData"]

# MediaWiki line separator for multi-line template fields
WIKITEXT_LINE_SEPARATOR = "<br>"


class EnrichedCharacterData:
    """Enriched character data with related entities.

    Contains raw character data plus related data from other tables.
    Formatting is done by template generators, not here.
    """

    def __init__(
        self,
        character: Character,
        spawn_infos: list[CharacterSpawnInfo],
        loot_drops: list[LootDropInfo],
        faction_display_names: dict[str, str],
    ) -> None:
        """Initialize enriched character data.

        Args:
            character: Character entity
            spawn_infos: Spawn point data from SpawnPointRepository
            loot_drops: Loot drop data from LootTableRepository
            faction_display_names: Faction REFNAME → display name mapping
        """
        self.character = character
        self.spawn_infos = spawn_infos
        self.loot_drops = loot_drops
        self.faction_display_names = faction_display_names


class CharacterEnricher:
    """Service for enriching characters with related data.

    Aggregates data from multiple repositories. Formatting is done by template generators.
    """

    def __init__(
        self,
        faction_repo: FactionRepository,
        spawn_repo: SpawnPointRepository,
        loot_repo: LootTableRepository,
    ) -> None:
        """Initialize character enricher.

        Args:
            faction_repo: Repository for faction data
            spawn_repo: Repository for spawn point data
            loot_repo: Repository for loot table data
        """
        self._faction_repo = faction_repo
        self._spawn_repo = spawn_repo
        self._loot_repo = loot_repo

    def enrich(self, character: Character) -> EnrichedCharacterData:
        """Enrich character with related data from other tables.

        Args:
            character: Character entity

        Returns:
            EnrichedCharacterData with spawn points, loot, and faction data
        """
        logger.debug(f"Enriching character: {character.npc_name}")

        # Get spawn points
        spawn_infos = self._spawn_repo.get_spawn_info_for_character(
            character_guid=character.guid,
            character_id=character.id,
            is_prefab=bool(character.is_prefab),
        )

        # Get loot drops
        loot_drops = self._loot_repo.get_loot_for_character(character.guid) if character.guid else []

        # Get faction display names
        refnames = set()
        if character.my_world_faction:
            refnames.add(character.my_world_faction)
        if character.faction_modifiers:
            refnames.update(m.faction_refname for m in character.faction_modifiers)
        refnames.update(["GOOD", "EVIL"])  # Always include generic factions
        faction_display_names = self._faction_repo.get_faction_display_names(list(refnames))

        return EnrichedCharacterData(
            character=character,
            spawn_infos=spawn_infos,
            loot_drops=loot_drops,
            faction_display_names=faction_display_names,
        )
