"""Read the versioned canonical item contract without selecting producer facts."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable, Iterator
from typing import Literal, TypedDict, TypeVar

from erenshor.domain.value_objects.item_provenance import (
    ItemAcquisition,
    ItemDisposition,
    ItemUse,
    acquisition_from_dict,
    conditions_satisfiable,
    disposition_from_dict,
    use_from_dict,
    validate_provenance_metadata,
)
from erenshor.infrastructure.database.connection import DatabaseConnection, DatabaseConnectionError
from erenshor.infrastructure.database.repository import RepositoryError

_Fact = TypeVar("_Fact", ItemAcquisition, ItemUse)


class _Children(TypedDict):
    conditions: tuple[dict[str, object], ...]
    locations: tuple[dict[str, object], ...]
    evidence: tuple[dict[str, object], ...]


def _database_condition(row: sqlite3.Row) -> dict[str, object]:
    data: dict[str, object] = dict(row)
    del data["owner_key"]
    for field in ("minimum_inclusive", "maximum_inclusive"):
        value = data[field]
        if type(value) is not int or value not in (0, 1):
            raise ValueError(f"Invalid SQLite boolean in {field}")
        data[field] = value == 1
    return data


class ItemProvenanceRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db
        try:
            with db.connect() as connection:
                rows = connection.execute("SELECT * FROM item_provenance_meta").fetchall()
            if len(rows) != 1:
                raise ValueError("Expected exactly one metadata record")
            validate_provenance_metadata(dict(rows[0]))
        except (sqlite3.Error, DatabaseConnectionError, ValueError) as error:
            raise RepositoryError(f"Unsupported item provenance schema: {error}") from error

    def _children(self, owner_key: str, family: Literal["acquisition", "use"]) -> _Children:
        with self._db.connect() as connection:
            conditions = tuple(
                _database_condition(row)
                for row in connection.execute(
                    f"SELECT * FROM item_{family}_conditions WHERE owner_key = ? "
                    "ORDER BY gate_key, group_index, atom_index, scope",
                    (owner_key,),
                )
            )
            locations: list[dict[str, object]] = []
            for row in connection.execute(
                f"SELECT * FROM item_{family}_locations WHERE owner_key = ? ORDER BY location_key",
                (owner_key,),
            ):
                data: dict[str, object] = dict(row)
                del data["owner_key"]
                for field in ("conditions", "entry_zone_line_keys"):
                    value = data[field]
                    if not isinstance(value, str):
                        raise ValueError(f"Location {field} must be JSON text")
                    data[field] = json.loads(value)
                locations.append(data)
            evidence = tuple(
                {key: value for key, value in dict(row).items() if key != "owner_key"}
                for row in connection.execute(
                    "SELECT * FROM item_provenance_evidence "
                    "WHERE owner_key = ? ORDER BY input_relation, input_primary_key",
                    (owner_key,),
                )
            )
        return {"conditions": conditions, "locations": tuple(locations), "evidence": evidence}

    def _hydrate(
        self,
        row: sqlite3.Row,
        family: Literal["acquisition", "use"],
        decoder: Callable[[object], _Fact],
    ) -> _Fact:
        try:
            data: dict[str, object] = dict(row)
            identity = data["acquisition_key" if family == "acquisition" else "use_key"]
            if not isinstance(identity, str):
                raise ValueError("Fact identity must be text")
            children = self._children(identity, family)
            data["conditions"] = children["conditions"]
            data["locations"] = children["locations"]
            data["evidence"] = children["evidence"]
            return decoder(data)
        except (KeyError, ValueError) as error:
            raise RepositoryError(f"Invalid item provenance {family}: {error}") from error

    def get_acquisitions(self, item_key: str) -> list[ItemAcquisition]:
        with self._db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM item_acquisitions WHERE item_stable_key = ? ORDER BY acquisition_key",
                (item_key,),
            ).fetchall()
        return [self._hydrate(row, "acquisition", acquisition_from_dict) for row in rows]

    def get_character_drop_acquisitions(self, character_copy_keys: Iterable[str]) -> list[ItemAcquisition]:
        """Project named loot facts for actual copies, never global substitution sources."""
        keys = tuple(sorted(set(character_copy_keys)))
        if not keys:
            return []
        placeholders = ",".join("?" for _ in keys)
        with self._db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM item_acquisitions WHERE kind = 'character_drop' "
                f"AND source_copy_stable_key IN ({placeholders}) ORDER BY acquisition_key",
                keys,
            ).fetchall()
        return [self._hydrate(row, "acquisition", acquisition_from_dict) for row in rows]

    def get_common_world_character_keys(self) -> frozenset[str]:
        """Resolve contributing copies through canonical evidence, not an independent loot selector."""
        with self._db.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT ld.character_stable_key "
                "FROM item_acquisitions a "
                "JOIN item_provenance_evidence e ON e.owner_key = a.acquisition_key "
                "JOIN loot_drops ld ON ld.character_stable_key = json_extract(e.input_primary_key, '$[0]') "
                "AND ld.item_stable_key = json_extract(e.input_primary_key, '$[1]') "
                "WHERE a.kind = 'common_world_item' AND a.player_access_state = 'verified_player' "
                "AND a.probability_stage = 'final_acquisition' AND e.input_relation = 'loot_drops' "
                "AND ld.drop_probability > 0 "
                "ORDER BY ld.character_stable_key"
            ).fetchall()
        return frozenset(str(row[0]) for row in rows)

    def get_uses(self, item_key: str) -> list[ItemUse]:
        with self._db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM item_uses WHERE item_stable_key = ? ORDER BY use_key",
                (item_key,),
            ).fetchall()
        return [self._hydrate(row, "use", use_from_dict) for row in rows]

    def get_uses_targeting(self, target_key: str) -> list[ItemUse]:
        with self._db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM item_uses WHERE target_stable_key = ? ORDER BY use_key",
                (target_key,),
            ).fetchall()
        return [self._hydrate(row, "use", use_from_dict) for row in rows]

    def get_disposition(self, item_key: str) -> ItemDisposition | None:
        with self._db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM item_dispositions WHERE item_stable_key = ?", (item_key,)
            ).fetchone()
        if row is None:
            return None
        return self._decode_disposition(dict(row))

    @staticmethod
    def _decode_disposition(data: dict[str, object]) -> ItemDisposition:
        try:
            for field in ("current_pages", "former_pages"):
                value = data[field]
                if not isinstance(value, str):
                    raise ValueError(f"Disposition {field} must be JSON text")
                data[field] = json.loads(value)
            return disposition_from_dict(data)
        except (KeyError, ValueError) as error:
            raise RepositoryError(f"Invalid item provenance disposition: {error}") from error

    def get_player_access(self, item_key: str) -> Literal["verified_player", "unconfirmed_player", "no_verified_path"]:
        disposition = self.get_disposition(item_key)
        if disposition is None or disposition.disposition != "current":
            return "no_verified_path"
        acquisitions = self.get_acquisitions(item_key)
        access_states: tuple[Literal["verified_player", "unconfirmed_player"], ...] = (
            "verified_player",
            "unconfirmed_player",
        )
        for access in access_states:
            if any(
                fact.player_access_state == access
                and fact.probability_stage == "final_acquisition"
                and not (fact.probability_max is not None and fact.probability_max <= 0)
                and conditions_satisfiable(fact.conditions)
                and (
                    not fact.locations
                    or any(conditions_satisfiable(fact.conditions + location.conditions) for location in fact.locations)
                )
                for fact in acquisitions
            ):
                return access
        return "no_verified_path"

    def iter_acquisitions(self) -> Iterator[ItemAcquisition]:
        with self._db.connect() as connection:
            keys = connection.execute(
                "SELECT DISTINCT item_stable_key FROM item_acquisitions ORDER BY item_stable_key",
            ).fetchall()
        for row in keys:
            yield from self.get_acquisitions(row[0])

    def iter_uses(self) -> Iterator[ItemUse]:
        with self._db.connect() as connection:
            keys = connection.execute(
                "SELECT DISTINCT item_stable_key FROM item_uses ORDER BY item_stable_key"
            ).fetchall()
        for row in keys:
            yield from self.get_uses(row[0])

    def iter_dispositions(self) -> Iterator[ItemDisposition]:
        with self._db.connect() as connection:
            rows = connection.execute("SELECT * FROM item_dispositions ORDER BY item_stable_key").fetchall()
        for row in rows:
            yield self._decode_disposition(dict(row))
