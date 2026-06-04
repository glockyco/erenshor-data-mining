"""Generate a compact Lua data module for stance wiki pages."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.lua_writer import module_text

if TYPE_CHECKING:
    from erenshor.domain.entities.stance import Stance

LuaData = dict[str, object]

# Raw stance modifier fields emitted verbatim; the Lua module owns display
# formatting (multiplier -> percentage, "no change" hiding). Mirrors the field
# set the live Template:Stance consumes.
_STANCE_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("maxHpMod", "max_hp_mod"),
    ("damageMod", "damage_mod"),
    ("damageTakenMod", "damage_taken_mod"),
    ("procRateMod", "proc_rate_mod"),
    ("aggroGenMod", "aggro_gen_mod"),
    ("spellDamageMod", "spell_damage_mod"),
    ("selfDamagePerAttack", "self_damage_per_attack"),
    ("selfDamagePerCast", "self_damage_per_cast"),
    ("lifestealAmount", "lifesteal_amount"),
    ("resonanceAmount", "resonance_amount"),
)


class StanceDataRepository(Protocol):
    """Repository methods needed to build the stance data module."""

    def get_all(self) -> list[Stance]: ...


def generate_stances_module(stance_repo: StanceDataRepository) -> str:
    """Generate `Module:Erenshor/Data/Stances` from clean DB repositories."""
    return module_text(build_stances_data(stance_repo.get_all()))


def write_stances_module(stance_repo: StanceDataRepository, output_root: Path) -> Path:
    """Write the generated stance data module below an output root."""
    output_path = output_root / "Erenshor" / "Data" / "Stances.lua"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate_stances_module(stance_repo), encoding="utf-8")
    return output_path


def build_stances_data(stances: Iterable[Stance]) -> LuaData:
    """Build the serializable stance data table for `mw.loadData()`."""
    rows: dict[str, LuaData] = {}
    for stance in sorted(stances, key=lambda candidate: candidate.stable_key):
        record = _stance_record(stance)
        if record is not None:
            rows[stance.stable_key] = record
    return {"stances": rows}


def _stance_record(stance: Stance) -> LuaData | None:
    name = stance.display_name or stance.wiki_page_name
    page = stance.wiki_page_name or name
    if name is None or page is None:
        return None

    record: LuaData = {"name": name, "page": page}
    _put(record, "image", stance.image_name)
    _put(record, "description", stance.stance_desc)
    _put(record, "switchMessage", stance.switch_message)
    for lua_key, attr in _STANCE_FIELD_MAP:
        _put(record, lua_key, getattr(stance, attr))
    record["stopRegen"] = bool(stance.stop_regen)
    return record


def _put(row: LuaData, key: str, value: object) -> None:
    if value is not None and value != "":
        row[key] = value
