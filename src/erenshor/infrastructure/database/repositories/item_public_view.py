"""Read the public item view: what players can act on, the conditions they meet and where."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from erenshor.domain.value_objects.item_provenance import validate_provenance_metadata
from erenshor.domain.value_objects.item_public_view import (
    ItemStatus,
    MechanismParameter,
    PublicCondition,
    PublicPlace,
    PublicSource,
    PublicUse,
)
from erenshor.infrastructure.database.connection import DatabaseConnectionError
from erenshor.infrastructure.database.repository import RepositoryError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from erenshor.infrastructure.database.connection import DatabaseConnection

_CONDITION_FIELDS = (
    "gate_index",
    "alternative_index",
    "atom_index",
    "gate_key",
    "predicate",
    "reference_stable_key",
    "reference_slot",
    "actor",
    "value",
    "minimum",
    "maximum",
    "minimum_inclusive",
    "maximum_inclusive",
    "phase",
)


def _condition(row: sqlite3.Row) -> PublicCondition:
    data: dict[str, Any] = {field: row[field] for field in _CONDITION_FIELDS}
    data["minimum_inclusive"] = bool(data["minimum_inclusive"])
    data["maximum_inclusive"] = bool(data["maximum_inclusive"])
    return PublicCondition(**data)


class ItemPublicViewRepository:
    """Load the public view once and index it the ways the products look it up."""

    def __init__(self, db: DatabaseConnection) -> None:
        try:
            with db.connect() as connection:
                meta = connection.execute("SELECT * FROM item_provenance_meta").fetchall()
                if len(meta) != 1:
                    raise ValueError("Expected exactly one metadata record")
                validate_provenance_metadata(dict(meta[0]))
                self._load(connection)
        except (sqlite3.Error, DatabaseConnectionError, ValueError) as error:
            raise RepositoryError(f"Unsupported item provenance schema: {error}") from error

    def _load(self, connection: sqlite3.Connection) -> None:
        conditions: dict[str, list[PublicCondition]] = defaultdict(list)
        for row in connection.execute(
            "SELECT * FROM item_conditions ORDER BY owner_key, gate_index, alternative_index, atom_index"
        ):
            conditions[row["owner_key"]].append(_condition(row))
        place_conditions: dict[tuple[str, str], list[PublicCondition]] = defaultdict(list)
        for row in connection.execute(
            "SELECT * FROM item_place_conditions"
            " ORDER BY place_set_key, place_key, gate_index, alternative_index, atom_index"
        ):
            place_conditions[row["place_set_key"], row["place_key"]].append(_condition(row))

        self._sources: dict[str, PublicSource] = {}
        self._sources_by_item: dict[str, list[PublicSource]] = defaultdict(list)
        for row in connection.execute("SELECT * FROM item_sources ORDER BY source_key"):
            data = dict(row)
            data["guaranteed"] = bool(data["guaranteed"])
            source = PublicSource(**data, conditions=tuple(conditions.get(row["source_key"], ())))
            self._sources[source.source_key] = source
            self._sources_by_item[source.item_stable_key].append(source)

        self._uses: dict[str, PublicUse] = {}
        self._uses_by_item: dict[str, list[PublicUse]] = defaultdict(list)
        self._uses_by_target: dict[str, list[PublicUse]] = defaultdict(list)
        for row in connection.execute("SELECT * FROM item_usages ORDER BY use_key"):
            use = PublicUse(**dict(row), conditions=tuple(conditions.get(row["use_key"], ())))
            self._uses[use.use_key] = use
            self._uses_by_item[use.item_stable_key].append(use)
            if use.target_stable_key is not None:
                self._uses_by_target[use.target_stable_key].append(use)

        places: dict[str, list[PublicPlace]] = defaultdict(list)
        for row in connection.execute("SELECT * FROM item_places ORDER BY place_set_key, place_key"):
            data = dict(row)
            entries = data.pop("entry_zone_line_keys")
            key = (row["place_set_key"], row["place_key"])
            places[row["place_set_key"]].append(
                PublicPlace(
                    **data,
                    entry_zone_line_keys=tuple(json.loads(entries)) if entries else (),
                    conditions=tuple(place_conditions.get(key, ())),
                )
            )
        self._places = {key: tuple(value) for key, value in places.items()}

        parameters: dict[str, list[MechanismParameter]] = defaultdict(list)
        for row in connection.execute("SELECT * FROM item_mechanism_parameters ORDER BY mechanic_key, parameter_index"):
            parameters[row["mechanic_key"]].append(MechanismParameter(**dict(row)))
        self._parameters = {key: tuple(value) for key, value in parameters.items()}

        contributors: dict[str, list[str]] = defaultdict(list)
        for row in connection.execute(
            "SELECT * FROM item_source_contributors ORDER BY source_key, character_stable_key"
        ):
            contributors[row["source_key"]].append(row["character_stable_key"])
        self._contributors = {key: tuple(value) for key, value in contributors.items()}

        self._statuses = {
            row["item_stable_key"]: ItemStatus(
                row["item_stable_key"],
                row["disposition"],
                row["reason"],
                tuple(json.loads(row["current_pages"])),
                tuple(json.loads(row["former_pages"])),
            )
            for row in connection.execute("SELECT * FROM item_statuses ORDER BY item_stable_key")
        }

    def sources(self) -> tuple[PublicSource, ...]:
        return tuple(self._sources.values())

    def source(self, key: str) -> PublicSource | None:
        return self._sources.get(key)

    def sources_for_item(self, item_key: str) -> tuple[PublicSource, ...]:
        return tuple(self._sources_by_item.get(item_key, ()))

    def sources_from_copies(self, copy_keys: Iterable[str]) -> tuple[PublicSource, ...]:
        """The sources a character copy offers, such as its drops and its stock."""
        keys = frozenset(copy_keys)
        return tuple(source for source in self._sources.values() if source.source_copy_stable_key in keys)

    def uses(self) -> tuple[PublicUse, ...]:
        return tuple(self._uses.values())

    def uses_for_item(self, item_key: str) -> tuple[PublicUse, ...]:
        return tuple(self._uses_by_item.get(item_key, ()))

    def uses_targeting(self, target_key: str) -> tuple[PublicUse, ...]:
        return tuple(self._uses_by_target.get(target_key, ()))

    def places(self, place_set_key: str | None) -> tuple[PublicPlace, ...]:
        return self._places.get(place_set_key, ()) if place_set_key is not None else ()

    def parameters(self, mechanic_key: str | None) -> tuple[MechanismParameter, ...]:
        return self._parameters.get(mechanic_key, ()) if mechanic_key is not None else ()

    def contributors(self, source_key: str) -> tuple[str, ...]:
        return self._contributors.get(source_key, ())

    def common_world_contributors(self) -> frozenset[str]:
        """The characters whose loot rows a common world item summarizes."""
        return frozenset(character for characters in self._contributors.values() for character in characters)

    def status(self, item_key: str) -> ItemStatus | None:
        return self._statuses.get(item_key)

    def statuses(self) -> tuple[ItemStatus, ...]:
        return tuple(self._statuses.values())
