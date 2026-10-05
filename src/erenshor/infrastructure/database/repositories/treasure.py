"""Read the treasure hunting tables of the clean database for wiki data generation."""

from pydantic import BaseModel

from erenshor.domain.value_objects.treasure import ChestWave, GuardianScaling, TreasureGuardian
from erenshor.infrastructure.database.repository import BaseRepository


class TreasureRepository(BaseRepository[BaseModel]):
    """Read the treasure guardians, their scaling, and the chest waves."""

    def get_treasure_guardians(self) -> list[TreasureGuardian]:
        """Return the wiki-visible guardians that a treasure chest spawns, by name."""
        rows = self._execute_raw(
            """
            SELECT DISTINCT c.stable_key, c.display_name, c.wiki_page_name
            FROM character_chained_spawns ccs
            JOIN characters c ON c.stable_key = ccs.child_stable_key
            JOIN treasure_guardian_scaling tgs ON tgs.guardian_character_stable_key = c.stable_key
            WHERE ccs.source_script = 'TreasureChestEvent' AND c.is_wiki_generated = 1
            ORDER BY c.display_name COLLATE NOCASE
            """
        )
        return [
            TreasureGuardian(
                stable_key=str(row["stable_key"]), name=str(row["display_name"]), page=str(row["wiki_page_name"])
            )
            for row in rows
        ]

    def get_guardian_scaling(self) -> list[GuardianScaling]:
        """Return the scaling rows of every guardian, by guardian and player level."""
        rows = self._execute_raw(
            """
            SELECT * FROM treasure_guardian_scaling
            ORDER BY guardian_character_stable_key, player_level
            """
        )
        return [
            GuardianScaling(
                guardian_stable_key=str(row["guardian_character_stable_key"]),
                player_level=int(row["player_level"]),
                level_min=int(row["level_min"]),
                level_max=int(row["level_max"]),
                health_min=int(row["health_min"]),
                health_max=int(row["health_max"]),
                attack_min=int(row["attack_min"]),
                attack_max=int(row["attack_max"]),
                attack_delay_min=int(row["attack_delay_min"]),
                attack_delay_max=int(row["attack_delay_max"]),
                ac_min=int(row["ac_min"]),
                ac_max=int(row["ac_max"]),
                resist_min=int(row["resist_min"]),
                resist_max=int(row["resist_max"]),
            )
            for row in rows
        ]

    def get_chest_waves(self) -> list[ChestWave]:
        """Return the chest wave rows, by the number of waves spawned."""
        rows = self._execute_raw("SELECT * FROM treasure_chest_waves ORDER BY waves_spawned")
        return [
            ChestWave(
                waves_spawned=int(row["waves_spawned"]),
                strike_break_chance=float(row["strike_break_chance"]),
                next_wave_guardians_min=(
                    int(row["next_wave_guardians_min"]) if row["next_wave_guardians_min"] is not None else None
                ),
                next_wave_guardians_max=(
                    int(row["next_wave_guardians_max"]) if row["next_wave_guardians_max"] is not None else None
                ),
                next_wave_delay_seconds=(
                    float(row["next_wave_delay_seconds"]) if row["next_wave_delay_seconds"] is not None else None
                ),
            )
            for row in rows
        ]
