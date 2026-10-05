"""Generate the wiki data module for the treasure guardians."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.lua_writer import module_text

if TYPE_CHECKING:
    from erenshor.domain.value_objects.treasure import ChestWave, GuardianScaling, TreasureGuardian


class TreasureDataRepository(Protocol):
    """Repository methods needed for the treasure guardian module."""

    def get_treasure_guardians(self) -> list[TreasureGuardian]: ...

    def get_guardian_scaling(self) -> list[GuardianScaling]: ...

    def get_chest_waves(self) -> list[ChestWave]: ...


def _scaling_row(row: GuardianScaling) -> dict[str, int]:
    return {
        "playerLevel": row.player_level,
        "levelMin": row.level_min,
        "levelMax": row.level_max,
        "healthMin": row.health_min,
        "healthMax": row.health_max,
        "attackMin": row.attack_min,
        "attackMax": row.attack_max,
        "attackDelayMin": row.attack_delay_min,
        "attackDelayMax": row.attack_delay_max,
        "acMin": row.ac_min,
        "acMax": row.ac_max,
        "resistMin": row.resist_min,
        "resistMax": row.resist_max,
    }


def _wave_row(wave: ChestWave) -> dict[str, int | float | None]:
    return {
        "wavesSpawned": wave.waves_spawned,
        "strikeBreakChance": wave.strike_break_chance,
        "nextWaveGuardiansMin": wave.next_wave_guardians_min,
        "nextWaveGuardiansMax": wave.next_wave_guardians_max,
        "nextWaveDelaySeconds": wave.next_wave_delay_seconds,
    }


def build_treasure_guardians_data(repo: TreasureDataRepository) -> dict[str, object]:
    """Return the guardians in name order, their scaling by player level, and the chest waves."""
    guardians = repo.get_treasure_guardians()
    known = {guardian.stable_key for guardian in guardians}
    scaling: dict[str, list[dict[str, int]]] = {}
    for row in repo.get_guardian_scaling():
        if row.guardian_stable_key in known:
            scaling.setdefault(row.guardian_stable_key, []).append(_scaling_row(row))
    missing = sorted(known - scaling.keys())
    if missing:
        raise ValueError(f"treasure_guardian_scaling has no rows for {', '.join(missing)}")
    return {
        "guardians": [
            {"key": guardian.stable_key, "name": guardian.name, "page": guardian.page} for guardian in guardians
        ],
        "scaling": {key: sorted(rows, key=lambda row: row["playerLevel"]) for key, rows in scaling.items()},
        "waves": [_wave_row(wave) for wave in repo.get_chest_waves()],
    }


def write_treasure_guardians_module(repo: TreasureDataRepository, output_root: Path) -> Path:
    """Write the treasure guardian data as a Scribunto data module."""
    output_path = output_root / "Erenshor" / "Data" / "TreasureGuardians.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(module_text(build_treasure_guardians_data(repo)), encoding="utf-8")
    return output_path
