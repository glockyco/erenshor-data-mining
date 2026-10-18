"""Versioned item facts shared by database readers and output adapters."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from typing import Literal, cast

PROVENANCE_SCHEMA_VERSION = 1

PlayerAccessState = Literal["verified_player", "unconfirmed_player", "internal_only", "non_acquirable"]
ProbabilityKind = Literal["exact", "bounded", "unknown", "not_applicable"]
ProbabilityStage = Literal["native_pool", "final_acquisition"]
ConditionPhase = Literal[
    "availability",
    "source_initialization",
    "operation_input",
    "operation_outcome",
    "mechanic_parameter",
]
CONDITION_PHASES: tuple[ConditionPhase, ...] = (
    "availability",
    "source_initialization",
    "operation_input",
    "operation_outcome",
    "mechanic_parameter",
)


@dataclass(frozen=True, slots=True)
class ProvenanceCondition:
    gate_key: str
    group_index: int
    atom_index: int
    predicate: str
    reference_stable_key: str | None = None
    reference_slot: str | None = None
    actor: str | None = None
    value: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    minimum_inclusive: bool = True
    maximum_inclusive: bool = True
    scope: str = "source"
    phase: ConditionPhase = "availability"


@dataclass(frozen=True, slots=True)
class ProvenanceLocation:
    location_key: str
    relation: str
    scene: str | None = None
    zone_stable_key: str | None = None
    placement_key: str | None = None
    coordinate_stable_key: str | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None
    gate_scope: str | None = None
    player_level_min: int | None = None
    player_level_max: int | None = None
    conditions: tuple[ProvenanceCondition, ...] = ()
    entry_zone_line_keys: tuple[str, ...] = ()
    source_copy_stable_key: str | None = None


@dataclass(frozen=True, slots=True)
class ProvenanceEvidence:
    input_relation: str
    input_primary_key: str


@dataclass(frozen=True, slots=True)
class ItemAcquisition:
    acquisition_key: str
    item_stable_key: str
    kind: str
    source_stable_key: str | None
    source_group_key: str | None = None
    source_copy_stable_key: str | None = None
    variant_key: str | None = None
    mechanic: str | None = None
    player_access_state: PlayerAccessState = "verified_player"
    probability_kind: ProbabilityKind = "unknown"
    probability_min: float | None = None
    probability_max: float | None = None
    probability_basis: str | None = None
    probability_stage: ProbabilityStage = "final_acquisition"
    quantity_min: float | None = None
    quantity_max: float | None = None
    quantity_kind: str = "unknown"
    expected_quantity: float | None = None
    count_distribution: str | None = None
    guarantee_scope: str | None = None
    guaranteed_roll_count: int | None = None
    conditions: tuple[ProvenanceCondition, ...] = ()
    locations: tuple[ProvenanceLocation, ...] = ()
    evidence: tuple[ProvenanceEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class ItemUse:
    use_key: str
    item_stable_key: str
    target_stable_key: str | None
    kind: str
    variant_key: str | None = None
    material_slot: int | None = None
    quantity_min: float | None = None
    quantity_max: float | None = None
    quantity_kind: str = "unknown"
    mechanic: str | None = None
    outcome_key: str | None = None
    conditions: tuple[ProvenanceCondition, ...] = ()
    locations: tuple[ProvenanceLocation, ...] = ()
    evidence: tuple[ProvenanceEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class ItemDisposition:
    item_stable_key: str
    disposition: str
    reason: str | None = None
    evidence: str | None = None
    current_pages: tuple[str, ...] = ()
    former_pages: tuple[str, ...] = ()


def _record(
    value: object,
    cls: type[ItemAcquisition]
    | type[ItemUse]
    | type[ItemDisposition]
    | type[ProvenanceCondition]
    | type[ProvenanceLocation]
    | type[ProvenanceEvidence],
) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{cls.__name__}: expected an object")
    record = cast("Mapping[str, object]", value)
    expected = {field.name for field in fields(cls)}
    if set(record) != expected:
        raise ValueError(
            f"{cls.__name__}: missing fields {sorted(expected - set(record))}, "
            f"unknown fields {sorted(set(record) - expected)}"
        )
    return record


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected a nonempty string")
    return value


def _optional_text(value: object) -> str | None:
    return None if value is None else _text(value)


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Expected a finite number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Expected a finite number")
    return value


def _optional_number(value: object) -> float | None:
    return None if value is None else _number(value)


def _integer(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Expected a nonnegative integer")
    return value


def _optional_integer(value: object) -> int | None:
    return None if value is None else _integer(value)


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("Expected a boolean")
    return value


def _enum(value: object, choices: tuple[str, ...]) -> str:
    result = _text(value)
    if result not in choices:
        raise ValueError(f"Unsupported provenance value {result!r}, expected one of {choices}")
    return result


def _sequence(value: object) -> tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("Expected an array")
    return tuple(value)


ACQUISITION_KINDS = (
    "character_drop",
    "common_world_item",
    "special_world_drop",
    "vendor",
    "dialog",
    "crafting",
    "quest_reward",
    "mining",
    "fishing",
    "fishing_bonus",
    "item_bag",
    "item_drop",
    "spell_created",
    "item_conversion",
    "starting_class",
    "auction_house",
    "ui_grant",
    "internal_equipment",
)
USE_KINDS = (
    "crafting_recipe",
    "crafting_material",
    "quest_requirement",
    "item_drop",
    "spell_created",
    "item_conversion",
    "zone_restriction",
    "quality_offering",
    "smithing",
)
CONDITION_PREDICATES = (
    "never",
    "quest_done",
    "quest_not_done",
    "room_furnished",
    "planning_slot_item",
    "key_held",
    "item_held",
    "encounter_won",
    "item_not_owned",
    "actor_level",
    "actor_class",
    "account_state",
    "world_state",
    "time_of_day",
    "zone_use",
    "quality",
    "formula_operand",
    "route",
    "source_replenishment",
)


def condition_from_dict(value: object) -> ProvenanceCondition:
    data = _record(value, ProvenanceCondition)
    condition = ProvenanceCondition(
        gate_key=_text(data["gate_key"]),
        group_index=_integer(data["group_index"]),
        atom_index=_integer(data["atom_index"]),
        predicate=_enum(data["predicate"], CONDITION_PREDICATES),
        reference_stable_key=_optional_text(data["reference_stable_key"]),
        reference_slot=_optional_text(data["reference_slot"]),
        actor=_optional_text(data["actor"]),
        value=_optional_text(data["value"]),
        minimum=_optional_number(data["minimum"]),
        maximum=_optional_number(data["maximum"]),
        minimum_inclusive=_boolean(data["minimum_inclusive"]),
        maximum_inclusive=_boolean(data["maximum_inclusive"]),
        scope=_text(data["scope"]),
        phase=cast("ConditionPhase", _enum(data["phase"], CONDITION_PHASES)),
    )
    if condition.actor is not None:
        _enum(condition.actor, ("player", "sim", "sim_player", "enemy", "account"))
    if condition.predicate == "time_of_day":
        _enum(condition.value, ("day", "night"))
    if condition.predicate == "account_state":
        _enum(condition.reference_stable_key, ("account_state:reliquary_claimed",))
        _enum(condition.actor, ("account",))
        _enum(condition.value, ("true", "false"))
        _enum(condition.phase, ("availability", "operation_outcome"))
    if (
        condition.predicate
        in (
            "quest_done",
            "quest_not_done",
            "room_furnished",
            "planning_slot_item",
            "key_held",
            "item_held",
            "item_not_owned",
            "encounter_won",
            "world_state",
            "actor_class",
            "zone_use",
        )
        and condition.reference_stable_key is None
    ):
        raise ValueError(f"{condition.predicate}: missing reference_stable_key")
    if condition.predicate == "planning_slot_item":
        _enum(
            condition.reference_slot,
            (
                "PlanarFern",
                "PlanarBrax",
                "PlanarVith",
                "PlanarSol",
                "Rune1",
                "Rune2",
                "Rune3",
                "Rune4",
                "Rune5",
                "Rune6",
            ),
        )
        _enum(condition.phase, ("availability",))
    if condition.predicate == "actor_level" and (
        condition.actor is None or (condition.minimum is None and condition.maximum is None)
    ):
        raise ValueError("actor_level needs an actor and at least one bound")
    if condition.predicate in ("route", "source_replenishment", "formula_operand") and condition.value is None:
        raise ValueError(f"{condition.predicate}: missing value")
    return condition


def _conditions(value: object) -> tuple[ProvenanceCondition, ...]:
    conditions = tuple(condition_from_dict(atom) for atom in _sequence(value))
    identities = [(atom.scope, atom.gate_key, atom.phase, atom.group_index, atom.atom_index) for atom in conditions]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate condition atom identity")
    return conditions


def location_from_dict(value: object) -> ProvenanceLocation:
    data = _record(value, ProvenanceLocation)
    location = ProvenanceLocation(
        location_key=_text(data["location_key"]),
        relation=_enum(
            data["relation"], ("fixed", "spawn", "possible_treasure", "unlocated", "mechanic_zone", "interaction")
        ),
        scene=_optional_text(data["scene"]),
        zone_stable_key=_optional_text(data["zone_stable_key"]),
        placement_key=_optional_text(data["placement_key"]),
        coordinate_stable_key=_optional_text(data["coordinate_stable_key"]),
        x=_optional_number(data["x"]),
        y=_optional_number(data["y"]),
        z=_optional_number(data["z"]),
        gate_scope=_optional_text(data["gate_scope"]),
        player_level_min=_optional_integer(data["player_level_min"]),
        player_level_max=_optional_integer(data["player_level_max"]),
        conditions=_conditions(data["conditions"]),
        entry_zone_line_keys=tuple(_text(key) for key in _sequence(data["entry_zone_line_keys"])),
        source_copy_stable_key=_optional_text(data["source_copy_stable_key"]),
    )
    if any(axis is None for axis in (location.x, location.y, location.z)) and any(
        axis is not None for axis in (location.x, location.y, location.z)
    ):
        raise ValueError("Location coordinates must have all three axes or none")
    if (
        location.player_level_min is not None
        and location.player_level_max is not None
        and location.player_level_min > location.player_level_max
    ):
        raise ValueError("Location player level interval is reversed")
    if len(set(location.entry_zone_line_keys)) != len(location.entry_zone_line_keys):
        raise ValueError("Duplicate location entry identity")
    return location


def evidence_from_dict(value: object) -> ProvenanceEvidence:
    data = _record(value, ProvenanceEvidence)
    return ProvenanceEvidence(_text(data["input_relation"]), _text(data["input_primary_key"]))


def _locations(value: object) -> tuple[ProvenanceLocation, ...]:
    locations = tuple(location_from_dict(location) for location in _sequence(value))
    if len({location.location_key for location in locations}) != len(locations):
        raise ValueError("Duplicate location identity")
    return locations


def _evidence(value: object) -> tuple[ProvenanceEvidence, ...]:
    evidence = tuple(evidence_from_dict(entry) for entry in _sequence(value))
    if len(set(evidence)) != len(evidence):
        raise ValueError("Duplicate evidence identity")
    return evidence


def _interval(kind: str, minimum: float | None, maximum: float | None, *, probability: bool = False) -> None:
    if any(bound is not None and (bound < 0 or (probability and bound > 100)) for bound in (minimum, maximum)):
        raise ValueError("Probability or quantity bound outside its domain")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("Reversed probability or quantity interval")
    if kind in ("unknown", "not_applicable"):
        if minimum is not None or maximum is not None:
            raise ValueError(f"{kind} must not carry numeric bounds")
    elif kind == "exact":
        if minimum is None or maximum is None or minimum != maximum:
            raise ValueError(f"{kind} requires equal numeric bounds")
    elif probability and (minimum is None or maximum is None):
        raise ValueError("Bounded probabilities require both numeric bounds")
    elif minimum is None and maximum is None:
        raise ValueError("Bounded quantities require at least one numeric bound")


def _quantity(data: Mapping[str, object]) -> tuple[str, float | None, float | None]:
    kind = _enum(data["quantity_kind"], ("exact", "bounded", "unknown", "not_applicable"))
    minimum, maximum = _optional_number(data["quantity_min"]), _optional_number(data["quantity_max"])
    _interval(kind, minimum, maximum)
    return kind, minimum, maximum


def _count_distribution(value: object) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    distribution: object = json.loads(text)
    if isinstance(distribution, dict):
        for count in distribution:
            if not isinstance(count, str) or not count.isascii() or not count.isdecimal():
                raise ValueError("Count distribution keys must be nonnegative integer strings")
        probabilities = tuple(distribution.values())
    elif isinstance(distribution, list):
        probabilities = tuple(distribution)
    else:
        raise ValueError("Count distribution must be an object or array")
    if not probabilities or any(not 0 <= _number(chance) <= 1 for chance in probabilities):
        raise ValueError("Count distribution contains invalid probabilities")
    if sum(_number(chance) for chance in probabilities) > 1 + 1e-9:
        raise ValueError("Count distribution probabilities exceed one")
    return text


def acquisition_from_dict(value: object) -> ItemAcquisition:
    data = _record(value, ItemAcquisition)
    quantity_kind, quantity_min, quantity_max = _quantity(data)
    probability_kind = cast(
        "ProbabilityKind", _enum(data["probability_kind"], ("exact", "bounded", "unknown", "not_applicable"))
    )
    probability_min, probability_max = (
        _optional_number(data["probability_min"]),
        _optional_number(data["probability_max"]),
    )
    _interval(probability_kind, probability_min, probability_max, probability=True)
    expected_quantity = _optional_number(data["expected_quantity"])
    if expected_quantity is not None and expected_quantity < 0:
        raise ValueError("Expected quantity must be nonnegative")
    basis = _optional_text(data["probability_basis"])
    if basis is not None:
        _enum(
            basis,
            ("per_kill", "per_use", "per_node", "per_successful_catch", "per_listing_opportunity", "not_applicable"),
        )
    guarantee = _optional_text(data["guarantee_scope"])
    if guarantee is not None:
        _enum(guarantee, ("pool", "pool_roll", "item", "successful_roll", "successful_ui_transfer"))
    return ItemAcquisition(
        acquisition_key=_text(data["acquisition_key"]),
        item_stable_key=_text(data["item_stable_key"]),
        kind=_enum(data["kind"], ACQUISITION_KINDS),
        source_stable_key=_optional_text(data["source_stable_key"]),
        source_group_key=_optional_text(data["source_group_key"]),
        source_copy_stable_key=_optional_text(data["source_copy_stable_key"]),
        variant_key=_optional_text(data["variant_key"]),
        mechanic=_optional_text(data["mechanic"]),
        player_access_state=cast(
            "PlayerAccessState",
            _enum(
                data["player_access_state"],
                (
                    "verified_player",
                    "unconfirmed_player",
                    "internal_only",
                    "non_acquirable",
                ),
            ),
        ),
        probability_kind=probability_kind,
        probability_min=probability_min,
        probability_max=probability_max,
        probability_basis=basis,
        probability_stage=cast(
            "ProbabilityStage", _enum(data["probability_stage"], ("native_pool", "final_acquisition"))
        ),
        quantity_min=quantity_min,
        quantity_max=quantity_max,
        quantity_kind=quantity_kind,
        expected_quantity=expected_quantity,
        count_distribution=_count_distribution(data["count_distribution"]),
        guarantee_scope=guarantee,
        guaranteed_roll_count=_optional_integer(data["guaranteed_roll_count"]),
        conditions=_conditions(data["conditions"]),
        locations=_locations(data["locations"]),
        evidence=_evidence(data["evidence"]),
    )


def use_from_dict(value: object) -> ItemUse:
    data = _record(value, ItemUse)
    quantity_kind, quantity_min, quantity_max = _quantity(data)
    return ItemUse(
        use_key=_text(data["use_key"]),
        item_stable_key=_text(data["item_stable_key"]),
        target_stable_key=_optional_text(data["target_stable_key"]),
        kind=_enum(data["kind"], USE_KINDS),
        variant_key=_optional_text(data["variant_key"]),
        material_slot=_optional_integer(data["material_slot"]),
        quantity_min=quantity_min,
        quantity_max=quantity_max,
        quantity_kind=quantity_kind,
        mechanic=_optional_text(data["mechanic"]),
        outcome_key=_optional_text(data["outcome_key"]),
        conditions=_conditions(data["conditions"]),
        locations=_locations(data["locations"]),
        evidence=_evidence(data["evidence"]),
    )


def disposition_from_dict(value: object) -> ItemDisposition:
    data = _record(value, ItemDisposition)
    return ItemDisposition(
        item_stable_key=_text(data["item_stable_key"]),
        disposition=_enum(data["disposition"], ("current", "removed", "unobtainable", "unused")),
        reason=_optional_text(data["reason"]),
        evidence=_optional_text(data["evidence"]),
        current_pages=tuple(_text(page) for page in _sequence(data["current_pages"])),
        former_pages=tuple(_text(page) for page in _sequence(data["former_pages"])),
    )


def fact_from_dict(value: object) -> ItemAcquisition | ItemUse | ItemDisposition:
    """Decode every schema1 field without coercing or discarding dimensions."""
    if not isinstance(value, Mapping):
        raise ValueError("Expected a provenance fact object")
    if "acquisition_key" in value:
        return acquisition_from_dict(value)
    if "use_key" in value:
        return use_from_dict(value)
    return disposition_from_dict(value)


def fact_to_dict(fact: ItemAcquisition | ItemUse | ItemDisposition) -> dict[str, object]:
    """Encode validated, lossless schema1 fields for output adapters."""
    data = asdict(fact)
    fact_from_dict(data)
    return data


def validate_provenance_schema_version(value: object) -> None:
    if type(value) is not int or value != PROVENANCE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported item provenance schema: expected {PROVENANCE_SCHEMA_VERSION}")


def validate_provenance_metadata(value: object) -> None:
    if not isinstance(value, Mapping) or set(value) != {"schema_version", "game_build_id", "input_digests"}:
        raise ValueError("Invalid item provenance schema metadata fields")
    validate_provenance_schema_version(value["schema_version"])
    _text(value["game_build_id"])
    digests: object = json.loads(_text(value["input_digests"]))
    if not isinstance(digests, dict):
        raise ValueError("Provenance input digests must be an object")
    for key, digest in digests.items():
        _text(key)
        if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("Provenance input digests must be SHA256 hex strings")


def _atoms_satisfiable(atoms: tuple[ProvenanceCondition, ...]) -> bool:
    numeric: dict[tuple[str, str, str, str | None, str | None, str | None], list[ProvenanceCondition]] = defaultdict(
        list
    )
    positive: set[tuple[str, str, str | None, str | None, str | None]] = set()
    negative: set[tuple[str, str, str | None, str | None, str | None]] = set()
    choices: dict[tuple[str, str, str | None], str] = {}
    account_states: dict[tuple[str, str | None, str | None], str] = {}
    for atom in atoms:
        context = "current" if atom.phase in ("availability", "operation_input") else atom.phase
        if atom.predicate == "never":
            return False
        if atom.predicate == "account_state" and atom.value is not None:
            account_key = (context, atom.reference_stable_key, atom.actor)
            if account_key in account_states and account_states[account_key] != atom.value:
                return False
            account_states[account_key] = atom.value
        if atom.predicate in ("quest_done", "quest_not_done", "item_held", "item_not_owned"):
            family = "quest" if atom.predicate.startswith("quest_") else "item"
            # Inventory membership and unlock-key checks cover different storage.
            ownership_scope = atom.value if family == "item" else None
            key = (context, family, atom.actor, atom.reference_stable_key, ownership_scope)
            (negative if atom.predicate in ("quest_not_done", "item_not_owned") else positive).add(key)
        if atom.predicate == "actor_level":
            numeric[context, "actor_state", atom.predicate, atom.actor, None, None].append(atom)
        elif atom.predicate == "quality" or atom.minimum is not None or atom.maximum is not None:
            numeric[context, atom.scope, atom.predicate, atom.actor, atom.reference_stable_key, atom.value].append(atom)
        if atom.predicate in ("time_of_day", "actor_class"):
            choice = atom.value if atom.predicate == "time_of_day" else atom.reference_stable_key
            if choice is not None:
                choice_key = (context, atom.predicate, atom.actor)
                if choice_key in choices and choices[choice_key] != choice:
                    return False
                choices[choice_key] = choice
    if positive & negative:
        return False
    for bounds in numeric.values():
        low = max((atom.minimum for atom in bounds if atom.minimum is not None), default=-math.inf)
        high = min((atom.maximum for atom in bounds if atom.maximum is not None), default=math.inf)
        if low > high or (
            low == high
            and any(
                (atom.minimum == low and not atom.minimum_inclusive)
                or (atom.maximum == high and not atom.maximum_inclusive)
                for atom in bounds
            )
        ):
            return False
    return True


def conditions_satisfiable(conditions: tuple[ProvenanceCondition, ...]) -> bool:
    """Require one compatible AND group from every independent OR gate."""
    gates: dict[tuple[str, str, ConditionPhase], dict[int, list[ProvenanceCondition]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for condition in conditions:
        gates[condition.scope, condition.gate_key, condition.phase][condition.group_index].append(condition)
    alternatives = [tuple(tuple(atoms) for atoms in groups.values()) for groups in gates.values()]

    def compatible(index: int, selected: tuple[ProvenanceCondition, ...]) -> bool:
        if index == len(alternatives):
            return True
        for group in alternatives[index]:
            combined = selected + group
            if _atoms_satisfiable(combined) and compatible(index + 1, combined):
                return True
        return False

    return compatible(0, ())


def is_actionable_acquisition(fact: ItemAcquisition) -> bool:
    return (
        fact.player_access_state == "verified_player"
        and fact.probability_stage == "final_acquisition"
        and not (fact.probability_max is not None and fact.probability_max <= 0)
        and conditions_satisfiable(fact.conditions)
        and (
            not fact.locations
            or any(conditions_satisfiable(fact.conditions + location.conditions) for location in fact.locations)
        )
    )
