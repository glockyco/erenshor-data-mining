"""Generate the board's actual summoned copies and their dedicated canonical loot."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from erenshor.application.wiki_lua.views import DataView, ViewField, native_reference, view_module_text
from erenshor.domain.value_objects.item_provenance import is_actionable_acquisition
from erenshor.domain.value_objects.npc_level import npc_level_bounds

if TYPE_CHECKING:
    from erenshor.domain.value_objects.item_provenance import ItemAcquisition, ItemDisposition

GAME_BOARD = DataView(
    module="GameBoard",
    description="Bosses summoned by the board, with dedicated drops at the default loot rate. "
    "Each row is one drop from one exact summoned copy and piece, or a spawn without obtainable dedicated drops. "
    "Global rolls and common-world substitutions are not boss-specific loot.",
    entity="boss character",
    fields=(
        ViewField("copy", "text", "The exact spawned character stable key, not a deduplication group loot source."),
        ViewField("piece", "reference", "The native item that summons this copy."),
        ViewField("levelMin", "integer", "Lowest initialized level, after spawn modifiers and NPC variance."),
        ViewField("levelMax", "integer", "Highest initialized level, after spawn modifiers and NPC variance."),
        ViewField("scales", "boolean", "Whether this copy scales with the player's level."),
        ViewField("drop", "reference", "An obtainable dedicated drop from this exact copy.", optional=True),
        ViewField(
            "chance", "number", "Percentage chance per kill at the default loot rate, from 0 to 100.", optional=True
        ),
    ),
)


class GameBoardRepository(Protocol):
    def get_game_board_spawns(self) -> list[dict[str, object]]: ...


class GameBoardProvenanceRepository(Protocol):
    def get_character_drop_acquisitions(self, character_copy_keys: Iterable[str]) -> list[ItemAcquisition]: ...

    def get_disposition(self, item_key: str) -> ItemDisposition | None: ...


def build_game_board_rows(
    spawns: Iterable[Mapping[str, object]],
    acquisitions: Iterable[ItemAcquisition],
    dispositions: Mapping[str, ItemDisposition | None],
    reference_catalog: Mapping[str, Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    """Keep alternative copy/piece/level bindings separate, never borrowing a group's loot."""
    bindings: dict[tuple[str, str, str, int, int, bool], dict[str, object]] = {}
    for spawn in spawns:
        copy, character, piece = (spawn.get(field) for field in ("copy", "character", "piece"))
        if not isinstance(copy, str) or not copy.startswith("character:"):
            raise ValueError(f"GameBoard: invalid spawned copy {copy!r}")
        if not isinstance(character, str) or not character.startswith("character:"):
            raise ValueError(f"GameBoard: {copy} has no public character identity")
        if not isinstance(piece, str):
            raise ValueError(f"GameBoard: {copy} has no summoning piece")
        level = int(str(spawn["level"])) + int(str(spawn.get("levelMod", 0)))
        low, high = npc_level_bounds(level, bool(spawn["group"]))
        scales = bool(spawn["scales"])
        bindings[copy, character, piece, low, high, scales] = {
            "copy": copy,
            "piece": native_reference(piece, reference_catalog, kind="item"),
            "levelMin": low,
            "levelMax": high,
            "scales": scales,
        }

    copies = {identity[0] for identity in bindings}
    drops: defaultdict[str, dict[str, tuple[dict[str, object], float]]] = defaultdict(dict)
    for fact in acquisitions:
        source_copy = fact.source_copy_stable_key
        if fact.kind != "character_drop" or source_copy is None or source_copy not in copies:
            continue
        if not is_actionable_acquisition(fact):
            continue
        disposition = dispositions.get(fact.item_stable_key)
        if disposition is None or disposition.item_stable_key != fact.item_stable_key:
            raise ValueError(f"GameBoard: missing canonical disposition for {fact.item_stable_key}")
        if disposition.disposition != "current":
            continue
        if (
            fact.probability_kind != "exact"
            or fact.probability_basis != "per_kill"
            or fact.probability_min is None
            or fact.probability_min != fact.probability_max
            or not 0 < fact.probability_min <= 100
        ):
            raise ValueError(f"GameBoard: {fact.acquisition_key} has no exact per-kill chance")
        drop = native_reference(fact.item_stable_key, reference_catalog, kind="item")
        value = (drop, fact.probability_min)
        previous = drops[source_copy].get(fact.item_stable_key)
        if previous is not None and previous != value:
            raise ValueError(f"GameBoard: conflicting drop chances for {source_copy} and {fact.item_stable_key}")
        drops[source_copy][fact.item_stable_key] = value

    rows: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for (copy, character, *_), binding in sorted(bindings.items()):
        loot = drops[copy]
        if not loot:
            rows[character].append(dict(binding))
            continue
        for item in sorted(loot, key=lambda key: (-loot[key][1], str(loot[key][0]["name"]), key)):
            drop, chance = loot[item]
            rows[character].append(dict(binding, drop=drop, chance=chance))
    return dict(rows)


def write_game_board_module(
    repo: GameBoardRepository,
    provenance_repo: GameBoardProvenanceRepository,
    known_keys: Collection[str],
    output_root: Path,
    *,
    reference_catalog: Mapping[str, Mapping[str, object]],
) -> Path:
    """Write the checked board view using only acquisitions owned by summoned copies."""
    spawns = repo.get_game_board_spawns()
    copies = {str(spawn["copy"]) for spawn in spawns}
    acquisitions = provenance_repo.get_character_drop_acquisitions(copies)
    dispositions = {
        key: provenance_repo.get_disposition(key) for key in {fact.item_stable_key for fact in acquisitions}
    }
    rows = build_game_board_rows(spawns, acquisitions, dispositions, reference_catalog)
    text = view_module_text(GAME_BOARD, rows, known_keys, reference_catalog=reference_catalog)
    path = output_root / "Erenshor" / "Data" / "GameBoard.lua"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
