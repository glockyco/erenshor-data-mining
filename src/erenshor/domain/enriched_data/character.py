"""Enriched character data DTO."""

from erenshor.domain.entities.character import Character
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo
from erenshor.domain.value_objects.wiki_link import AbilityLink

__all__ = ["EnrichedCharacterData"]


class EnrichedCharacterData:
    """Enriched character data with related entities.

    Contains raw character data plus related data from other tables.
    Formatting is done by template generators, not here.
    """

    def __init__(
        self,
        character: Character,
        spawn_infos: list[CharacterSpawnInfo],
        spells: list[AbilityLink],
    ) -> None:
        """Initialize enriched character data.

        Args:
            character: Character entity
            spawn_infos: Spawn point data from SpawnPointRepository
            spells: Pre-built AbilityLink objects for spells this character uses
        """
        self.character = character
        self.spawn_infos = spawn_infos
        self.spells = spells
