"""Enriched character data DTO."""

from erenshor.domain.entities.character import Character
from erenshor.domain.value_objects.loot import LootDropInfo
from erenshor.domain.value_objects.spawn import CharacterSpawnInfo

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
        loot_drops: list[LootDropInfo],
        spells: list[str],
    ) -> None:
        """Initialize enriched character data.

        Args:
            character: Character entity
            spawn_infos: Spawn point data from SpawnPointRepository
            loot_drops: Loot drop data from LootTableRepository
            spells: Spell stable keys that this character can use
        """
        self.character = character
        self.spawn_infos = spawn_infos
        self.loot_drops = loot_drops
        self.spells = spells
