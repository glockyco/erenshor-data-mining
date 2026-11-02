"""The item facts that every product shows: what a player can act on and what they must meet."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erenshor.domain.value_objects.item_provenance import ProvenanceCondition

# Conditions that describe how a mechanism works rather than what a player must meet.
_OWNERSHIP_HISTORY = frozenset({"item_not_owned", "item_held", "key_held"})


def condition_omission_reason(condition: ProvenanceCondition) -> str | None:
    """Name why players don't see a condition, or return None when they do."""
    if condition.phase == "mechanic_parameter":
        return "mechanism_parameter"
    if condition.predicate == "formula_operand":
        return "formula_operand"
    if condition.predicate == "source_replenishment":
        return "source_replenishment"
    if condition.predicate == "account_state" and condition.phase == "operation_outcome":
        return "account_state_outcome"
    if condition.phase == "source_initialization" and condition.predicate in _OWNERSHIP_HISTORY:
        return "ownership_history"
    return None


@dataclass(frozen=True, slots=True)
class PublicCondition:
    """One atom of a condition a player meets: all gates hold, and one alternative of each gate holds."""

    gate_index: int
    alternative_index: int
    atom_index: int
    gate_key: str
    predicate: str
    reference_stable_key: str | None = None
    reference_slot: str | None = None
    actor: str | None = None
    value: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    minimum_inclusive: bool = True
    maximum_inclusive: bool = True
    phase: str = "availability"


def public_conditions(conditions: tuple[ProvenanceCondition, ...]) -> tuple[PublicCondition, ...]:
    """Keep the gates a player meets.

    A gate with an alternative that holds only hidden atoms is left out, because one of its
    alternatives needs nothing a player meets.
    """
    gates: dict[tuple[str, str, str], dict[int, list[ProvenanceCondition]]] = {}
    for condition in conditions:
        groups = gates.setdefault((condition.scope, condition.gate_key, condition.phase), {})
        groups.setdefault(condition.group_index, []).append(condition)
    result: list[PublicCondition] = []
    gate_index = 0
    for groups in gates.values():
        alternatives: list[list[ProvenanceCondition]] = []
        for _, atoms in sorted(groups.items()):
            visible = sorted(
                (atom for atom in atoms if condition_omission_reason(atom) is None), key=lambda atom: atom.atom_index
            )
            if not visible:
                alternatives = []
                break
            alternatives.append(visible)
        if not alternatives:
            continue
        for alternative_index, atoms in enumerate(alternatives):
            for atom_index, atom in enumerate(atoms):
                result.append(
                    PublicCondition(
                        gate_index,
                        alternative_index,
                        atom_index,
                        atom.gate_key,
                        atom.predicate,
                        atom.reference_stable_key,
                        atom.reference_slot,
                        atom.actor,
                        atom.value,
                        atom.minimum,
                        atom.maximum,
                        atom.minimum_inclusive,
                        atom.maximum_inclusive,
                        atom.phase,
                    )
                )
        gate_index += 1
    return tuple(result)


@dataclass(frozen=True, slots=True)
class PublicSource:
    """One way a player can get an item."""

    source_key: str
    item_stable_key: str
    kind: str
    source_stable_key: str | None
    source_group_key: str | None
    source_copy_stable_key: str | None
    variant_key: str | None
    mechanic: str | None
    probability_kind: str
    probability_min: float | None
    probability_max: float | None
    probability_basis: str | None
    quantity_kind: str
    quantity_min: float | None
    quantity_max: float | None
    expected_quantity: float | None
    guaranteed: bool
    place_set_key: str | None
    conditions: tuple[PublicCondition, ...] = ()


@dataclass(frozen=True, slots=True)
class PublicUse:
    """One use of an item that a player can perform."""

    use_key: str
    item_stable_key: str
    target_stable_key: str | None
    kind: str
    variant_key: str | None
    material_slot: int | None
    quantity_kind: str
    quantity_min: float | None
    quantity_max: float | None
    mechanic: str | None
    outcome_key: str | None
    place_set_key: str | None
    conditions: tuple[PublicCondition, ...] = ()


@dataclass(frozen=True, slots=True)
class PublicPlace:
    """A place of a source. The marker key is the key of the map's marker and of the guide's spawn point."""

    place_set_key: str
    place_key: str
    relation: str
    scene: str | None
    zone_stable_key: str | None
    marker_stable_key: str | None
    x: float | None
    y: float | None
    z: float | None
    player_level_min: int | None
    player_level_max: int | None
    source_copy_stable_key: str | None
    entry_zone_line_keys: tuple[str, ...] = ()
    conditions: tuple[PublicCondition, ...] = ()


@dataclass(frozen=True, slots=True)
class MechanismParameter:
    """A parameter or formula of a mechanism that every fact of the mechanism shares."""

    mechanic_key: str
    parameter_index: int
    gate_key: str
    predicate: str
    value: str | None
    minimum: float | None
    maximum: float | None
    phase: str


@dataclass(frozen=True, slots=True)
class ItemStatus:
    item_stable_key: str
    disposition: str
    reason: str | None
    current_pages: tuple[str, ...] = ()
    former_pages: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Omission:
    """A fact the public view leaves out, and why."""

    owner_key: str
    reason: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class PublicView:
    sources: tuple[PublicSource, ...]
    uses: tuple[PublicUse, ...]
    places: tuple[PublicPlace, ...]
    parameters: tuple[MechanismParameter, ...]
    contributors: tuple[tuple[str, str], ...]
    statuses: tuple[ItemStatus, ...]
    omissions: tuple[Omission, ...]
    # How many hidden conditions of public facts each reason and predicate account for.
    condition_omissions: tuple[tuple[str, str, int], ...]
