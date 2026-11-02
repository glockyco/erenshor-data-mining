"""Derive, once, the item facts that products show, and store them in the clean database."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import astuple, replace
from typing import TYPE_CHECKING

from erenshor.domain.value_objects.item_provenance import (
    ItemAcquisition,
    ItemDisposition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceEvidence,
    ProvenanceLocation,
    conditions_satisfiable,
)
from erenshor.domain.value_objects.item_public_view import (
    ItemStatus,
    MechanismParameter,
    Omission,
    PublicCondition,
    PublicPlace,
    PublicSource,
    PublicUse,
    PublicView,
    condition_omission_reason,
    drop_implied_gates,
    public_conditions,
)

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Mapping, Sequence
    from pathlib import Path


def report_path(database: Path) -> Path:
    """The report of what the public view of a clean database leaves out."""
    return database.with_name(database.name + ".report.json")


_PARAMETER_REASONS = frozenset({"mechanism_parameter", "formula_operand"})


def _hidden_reason(fact: ItemAcquisition) -> str | None:
    if fact.player_access_state != "verified_player":
        return fact.player_access_state
    if fact.probability_stage == "native_pool":
        return "native_pool"
    if fact.probability_max is not None and fact.probability_max <= 0:
        return "zero_probability"
    return None


def _compatible_places(
    conditions: tuple[ProvenanceCondition, ...], locations: tuple[ProvenanceLocation, ...]
) -> tuple[ProvenanceLocation, ...]:
    return tuple(location for location in locations if conditions_satisfiable(conditions + location.conditions))


def _unreachable_reason(fact: ItemAcquisition | ItemUse, current: frozenset[str]) -> str | None:
    if fact.item_stable_key not in current:
        return "item_not_current"
    if not conditions_satisfiable(fact.conditions):
        return "unsatisfiable_conditions"
    if fact.locations and not _compatible_places(fact.conditions, fact.locations):
        return "no_compatible_place"
    return None


def _is_global_catch(fact: ItemAcquisition, bonus: ItemAcquisition) -> bool:
    """A water's catch whose final rate is the global replacement's rate, so any water gives it."""
    return (
        fact.kind == "fishing"
        and fact.probability_kind == "exact"
        and fact.probability_min == fact.probability_max
        and bonus.probability_min == fact.probability_min
        and bonus.probability_max == fact.probability_max
    )


class _Places:
    """Each place set once: a source's places, or the subset of them that one fact can use."""

    def __init__(self) -> None:
        self.sets: dict[str, tuple[ProvenanceLocation, ...]] = {}

    def key(self, fact: ItemAcquisition | ItemUse) -> str | None:
        if not fact.locations:
            return None
        if fact.location_source_key is None:
            raise ValueError(f"Located fact names no location source: {_fact_key(fact)}")
        compatible = _compatible_places(fact.conditions, fact.locations)
        key = fact.location_source_key
        if compatible != fact.locations:
            key += "|" + json.dumps(sorted(location.location_key for location in compatible), ensure_ascii=False)
        if self.sets.setdefault(key, compatible) != compatible:
            raise ValueError(f"Place set {key} names two different sets of places")
        return key

    def conditions(self, fact: ItemAcquisition | ItemUse, key: str | None) -> tuple[PublicCondition, ...]:
        """A fact's public conditions, without the gates that each of its places already requires."""
        implied_by = tuple(public_conditions(location.conditions) for location in self.sets.get(key or "", ()))
        return drop_implied_gates(public_conditions(fact.conditions), implied_by)

    def places(self) -> tuple[PublicPlace, ...]:
        return tuple(
            PublicPlace(
                key,
                location.location_key,
                location.relation,
                location.scene,
                location.zone_stable_key,
                location.coordinate_stable_key,
                location.x,
                location.y,
                location.z,
                location.player_level_min,
                location.player_level_max,
                location.source_copy_stable_key,
                location.entry_zone_line_keys,
                public_conditions(location.conditions),
            )
            for key, locations in sorted(self.sets.items())
            for location in locations
        )


def _fact_key(fact: ItemAcquisition | ItemUse) -> str:
    return fact.acquisition_key if isinstance(fact, ItemAcquisition) else fact.use_key


def _source(fact: ItemAcquisition, place_set_key: str | None, conditions: tuple[PublicCondition, ...]) -> PublicSource:
    return PublicSource(
        fact.acquisition_key,
        fact.item_stable_key,
        fact.kind,
        fact.source_stable_key,
        fact.source_group_key,
        fact.source_copy_stable_key,
        fact.variant_key,
        fact.mechanic,
        fact.probability_kind,
        fact.probability_min,
        fact.probability_max,
        fact.probability_basis,
        fact.quantity_kind,
        fact.quantity_min,
        fact.quantity_max,
        fact.expected_quantity,
        fact.guarantee_scope == "item",
        place_set_key,
        conditions,
    )


def _any_water(bonus: ItemAcquisition, members: Sequence[ItemAcquisition]) -> PublicSource:
    """One source for a catch that every water gives at the global replacement's rate."""
    minimums = [member.quantity_min for member in members]
    maximums = [member.quantity_max for member in members]
    bases = {member.probability_basis for member in members}
    if len(bases) != 1:
        raise ValueError(f"Global catch members differ in basis: {bonus.acquisition_key}")
    return PublicSource(
        bonus.acquisition_key,
        bonus.item_stable_key,
        "fishing",
        bonus.source_stable_key,
        None,
        None,
        None,
        bonus.mechanic,
        bonus.probability_kind,
        bonus.probability_min,
        bonus.probability_max,
        bases.pop(),
        members[0].quantity_kind,
        None if None in minimums else min(value for value in minimums if value is not None),
        None if None in maximums else max(value for value in maximums if value is not None),
        None,
        False,
        None,
    )


def derive_public_view(
    acquisitions: Sequence[ItemAcquisition],
    uses: Sequence[ItemUse],
    dispositions: Sequence[ItemDisposition],
    evidence: Mapping[str, tuple[ProvenanceEvidence, ...]],
    mechanism_conditions: Mapping[str, tuple[ProvenanceCondition, ...]],
) -> PublicView:
    """Select what a player can act on and the conditions they meet, and name why the rest is left out."""
    current = frozenset(d.item_stable_key for d in dispositions if d.disposition == "current")
    omissions: list[Omission] = []
    hidden_conditions: Counter[tuple[str, str]] = Counter()
    bonuses = {
        fact.item_stable_key: fact
        for fact in acquisitions
        if fact.kind == "fishing_bonus"
        and fact.probability_stage == "native_pool"
        and fact.mechanic == "fishing_global_replacement"
        and fact.probability_kind == "exact"
    }
    # An operation whose every alternative for one of its inputs is a retired or unused item, such
    # as a mold no player can get, gives nothing a player can act on.
    alternatives: dict[str, dict[tuple[str, int | None], bool]] = {}
    for use in uses:
        if use.outcome_key is not None:
            roles = alternatives.setdefault(use.outcome_key, {})
            role = (use.kind, use.material_slot)
            roles[role] = roles.get(role, False) or use.item_stable_key in current
    blocked = {outcome for outcome, roles in alternatives.items() if not all(roles.values())}
    places = _Places()
    sources: list[PublicSource] = []
    public_keys: set[str] = set()
    members: dict[str, list[ItemAcquisition]] = {}
    for fact in acquisitions:
        reason = _hidden_reason(fact) or _unreachable_reason(fact, current)
        if reason is None and fact.acquisition_key in blocked:
            reason = "input_not_current"
        bonus = bonuses.get(fact.item_stable_key)
        if reason is None and bonus is not None and _is_global_catch(fact, bonus):
            members.setdefault(bonus.acquisition_key, []).append(fact)
            omissions.append(Omission(fact.acquisition_key, "any_water_member", bonus.acquisition_key))
            continue
        if reason is not None:
            omissions.append(Omission(fact.acquisition_key, reason))
            continue
        place_set = places.key(fact)
        sources.append(_source(fact, place_set, places.conditions(fact, place_set)))
        public_keys.add(fact.acquisition_key)
        _count_hidden(fact.conditions, sources[-1].conditions, hidden_conditions)
    for bonus in bonuses.values():
        if bonus.acquisition_key in members:
            sources.append(_any_water(bonus, members[bonus.acquisition_key]))
            public_keys.add(bonus.acquisition_key)
    omissions = [o for o in omissions if o.owner_key not in public_keys]

    acquisition_keys = {fact.acquisition_key for fact in acquisitions}
    # A material or fuel names the mold it is used with. When no craft with that mold is public,
    # neither is the material.
    molds = {fact.source_stable_key for fact in acquisitions if fact.kind == "crafting"}
    public_molds = {source.source_stable_key for source in sources if source.kind == "crafting"}
    public_uses: list[PublicUse] = []
    for use in uses:
        reason = _unreachable_reason(use, current)
        if reason is None and use.outcome_key in acquisition_keys and use.outcome_key not in public_keys:
            reason = "outcome_not_public"
        if reason is None and use.target_stable_key in molds and use.target_stable_key not in public_molds:
            reason = "recipe_not_public"
        if reason is not None:
            omissions.append(Omission(use.use_key, reason))
            continue
        place_set = places.key(use)
        public_uses.append(
            PublicUse(
                use.use_key,
                use.item_stable_key,
                use.target_stable_key,
                use.kind,
                use.variant_key,
                use.material_slot,
                use.quantity_kind,
                use.quantity_min,
                use.quantity_max,
                use.mechanic,
                use.outcome_key,
                place_set,
                places.conditions(use, place_set),
            )
        )
        _count_hidden(use.conditions, public_uses[-1].conditions, hidden_conditions)

    public_mechanics = {source.mechanic for source in sources} | {use.mechanic for use in public_uses}
    parameters = tuple(
        MechanismParameter(
            mechanic, index, atom.gate_key, atom.predicate, atom.value, atom.minimum, atom.maximum, atom.phase
        )
        for mechanic, conditions in sorted(mechanism_conditions.items())
        if mechanic in public_mechanics
        for index, atom in enumerate(
            atom for atom in conditions if condition_omission_reason(atom) in _PARAMETER_REASONS
        )
    )
    contributors = tuple(
        sorted(
            {
                (source.source_key, str(json.loads(entry.input_primary_key)[0]))
                for source in sources
                if source.kind == "common_world_item"
                for entry in evidence.get(source.source_key, ())
                if entry.input_relation == "loot_drops"
            }
        )
    )
    statuses = tuple(
        ItemStatus(d.item_stable_key, d.disposition, d.reason, d.current_pages, d.former_pages)
        for d in sorted(dispositions, key=lambda d: d.item_stable_key)
    )
    return PublicView(
        tuple(sorted(sources, key=lambda source: source.source_key)),
        tuple(sorted(public_uses, key=lambda use: use.use_key)),
        places.places(),
        parameters,
        contributors,
        statuses,
        tuple(sorted(omissions, key=lambda o: o.owner_key)),
        tuple((reason, predicate, count) for (reason, predicate), count in sorted(hidden_conditions.items())),
    )


def _count_hidden(
    conditions: tuple[ProvenanceCondition, ...], shown: tuple[PublicCondition, ...], counter: Counter[tuple[str, str]]
) -> None:
    kept = {(atom.gate_key, atom.predicate, atom.phase, atom.value) for atom in shown}
    for atom in conditions:
        reason = condition_omission_reason(atom)
        if reason is None and (atom.gate_key, atom.predicate, atom.phase, atom.value) not in kept:
            # The gate had an alternative that needs nothing a player meets, or another gate or
            # every place of the fact already requires it.
            reason = "gate_hidden_or_implied"
        if reason is not None:
            counter[reason, atom.predicate] += 1


def _condition_rows(owner: tuple[str, ...], conditions: tuple[PublicCondition, ...]) -> list[tuple[object, ...]]:
    return [(*owner, *astuple(condition)) for condition in conditions]


def write_public_view(connection: sqlite3.Connection, view: PublicView) -> None:
    def insert(table: str, rows: Sequence[tuple[object, ...]]) -> None:
        if rows:
            marks = ",".join("?" for _ in rows[0])
            connection.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)

    insert("item_sources", [astuple(replace(source, conditions=()))[:-1] for source in view.sources])
    insert("item_usages", [astuple(replace(use, conditions=()))[:-1] for use in view.uses])
    insert(
        "item_conditions",
        [
            *(row for source in view.sources for row in _condition_rows((source.source_key,), source.conditions)),
            *(row for use in view.uses for row in _condition_rows((use.use_key,), use.conditions)),
        ],
    )
    place_rows = []
    place_conditions = []
    for place in view.places:
        entries = json.dumps(list(place.entry_zone_line_keys)) if place.entry_zone_line_keys else None
        place_rows.append((*astuple(replace(place, entry_zone_line_keys=(), conditions=()))[:-2], entries))
        place_conditions += _condition_rows((place.place_set_key, place.place_key), place.conditions)
    insert("item_places", place_rows)
    insert("item_place_conditions", place_conditions)
    insert("item_mechanism_parameters", [astuple(parameter) for parameter in view.parameters])
    insert("item_source_contributors", list(view.contributors))
    insert(
        "item_statuses",
        [
            (
                status.item_stable_key,
                status.disposition,
                status.reason,
                json.dumps(list(status.current_pages), ensure_ascii=False),
                json.dumps(list(status.former_pages), ensure_ascii=False),
            )
            for status in view.statuses
        ],
    )


def write_report(path: Path, view: PublicView) -> None:
    """List what the public view leaves out, beside the clean database and not in it."""
    reasons = Counter(omission.reason for omission in view.omissions)
    report = {
        "sources": len(view.sources),
        "uses": len(view.uses),
        "places": len(view.places),
        "omitted_fact_counts": dict(sorted(reasons.items())),
        "omitted_conditions": [
            {"reason": reason, "predicate": predicate, "count": count}
            for reason, predicate, count in view.condition_omissions
        ],
        "omitted_facts": [
            {"key": omission.owner_key, "reason": omission.reason}
            | ({"detail": omission.detail} if omission.detail else {})
            for omission in view.omissions
        ],
    }
    staged = path.with_name(f".{path.name}.tmp")
    staged.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    staged.replace(path)
