"""Compare two clean databases table by table and render the result.

Rows are matched by each table's primary key. A table without a primary key
is compared as a multiset of whole rows. Only columns present in both
databases take part in the comparison; added and removed columns are listed.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Row = tuple[Any, ...]

_NAME_COLUMNS = ("display_name", "name", "zone_name", "quest_name", "book_title", "title")
_VALUE_WIDTH = 80


@contextmanager
def _read_only(db_path: Path, *, base_db: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open a database read-only, optionally attaching a base database.

    Read-only URIs make a missing path an error instead of an empty new file.
    """
    with closing(sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)) as connection:
        if base_db is not None:
            connection.execute("ATTACH DATABASE ? AS base", (f"{base_db.resolve().as_uri()}?mode=ro",))
        yield connection


def recorded_build_id(db_path: Path) -> str:
    """Return the game build ID that the clean database was built from.

    Raises:
        ValueError: If the database does not record its game build.
        sqlite3.Error: If the database cannot be opened or read.
    """
    rebuild = "Rebuild it with 'erenshor extract build'."
    with _read_only(db_path) as connection:
        has_provenance = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'code_facts_meta'"
        ).fetchone()
        if has_provenance is None:
            raise ValueError(f"{db_path} has no build provenance. {rebuild}")
        row = connection.execute("SELECT game_build_id FROM code_facts_meta").fetchone()
    if row is None or row[0] is None:
        raise ValueError(f"{db_path} does not record its game build ID. {rebuild}")
    return str(row[0])


@dataclass(frozen=True, slots=True)
class ChangedRow:
    """A row present in both databases whose shared columns differ."""

    key: Row
    changes: tuple[tuple[str, Any, Any], ...]


@dataclass(frozen=True, slots=True)
class TableDiff:
    """The difference of one table between an old and a new database."""

    name: str
    status: Literal["added", "removed", "compared"]
    columns: tuple[str, ...]
    key_columns: tuple[str, ...]
    old_rows: int
    new_rows: int
    added_columns: tuple[str, ...] = ()
    removed_columns: tuple[str, ...] = ()
    added: tuple[Row, ...] = ()
    removed: tuple[Row, ...] = ()
    changed: tuple[ChangedRow, ...] = ()

    @property
    def unchanged(self) -> bool:
        return (
            self.status == "compared"
            and not self.added_columns
            and not self.removed_columns
            and not self.added
            and not self.removed
            and not self.changed
        )


@dataclass(frozen=True, slots=True)
class DatabaseDiff:
    """The table-by-table difference between two databases."""

    tables: tuple[TableDiff, ...] = field(default_factory=tuple)

    @property
    def changed_tables(self) -> tuple[TableDiff, ...]:
        return tuple(table for table in self.tables if not table.unchanged)


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _tables(connection: sqlite3.Connection, schema: str) -> set[str]:
    rows = connection.execute(
        f"SELECT name FROM {schema}.sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _columns(connection: sqlite3.Connection, schema: str, table: str) -> list[tuple[str, int]]:
    """Return (column, primary-key position) pairs in declaration order."""
    rows = connection.execute(f"PRAGMA {schema}.table_info({_quote(table)})").fetchall()
    return [(str(row[1]), int(row[5])) for row in rows]


def _count(connection: sqlite3.Connection, schema: str, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {schema}.{_quote(table)}").fetchone()[0])


def _keyed_diff(
    connection: sqlite3.Connection, table: str, columns: Sequence[str], key: Sequence[str]
) -> tuple[tuple[Row, ...], tuple[Row, ...], tuple[ChangedRow, ...]]:
    name = _quote(table)
    select = ", ".join(f"n.{_quote(column)}" for column in columns)
    select_old = ", ".join(f"o.{_quote(column)}" for column in columns)
    match = " AND ".join(f"o.{_quote(column)} IS n.{_quote(column)}" for column in key)
    added = connection.execute(
        f"SELECT {select} FROM main.{name} n WHERE NOT EXISTS (SELECT 1 FROM base.{name} o WHERE {match}) "
        f"ORDER BY {', '.join('n.' + _quote(column) for column in key)}"
    ).fetchall()
    removed = connection.execute(
        f"SELECT {select_old} FROM base.{name} o WHERE NOT EXISTS (SELECT 1 FROM main.{name} n WHERE {match}) "
        f"ORDER BY {', '.join('o.' + _quote(column) for column in key)}"
    ).fetchall()
    compared = [column for column in columns if column not in key]
    changed: list[ChangedRow] = []
    if compared:
        differs = " OR ".join(f"n.{_quote(column)} IS NOT o.{_quote(column)}" for column in compared)
        key_select = ", ".join(f"n.{_quote(column)}" for column in key)
        pairs = ", ".join(f"o.{_quote(column)}, n.{_quote(column)}" for column in compared)
        rows = connection.execute(
            f"SELECT {key_select}, {pairs} FROM main.{name} n JOIN base.{name} o ON {match} "
            f"WHERE {differs} ORDER BY {', '.join('n.' + _quote(column) for column in key)}"
        ).fetchall()
        for row in rows:
            values = row[len(key) :]
            changes = tuple(
                (column, values[2 * index], values[2 * index + 1])
                for index, column in enumerate(compared)
                if values[2 * index] != values[2 * index + 1]
            )
            changed.append(ChangedRow(tuple(row[: len(key)]), changes))
    return tuple(map(tuple, added)), tuple(map(tuple, removed)), tuple(changed)


def _multiset_diff(
    connection: sqlite3.Connection, table: str, columns: Sequence[str]
) -> tuple[tuple[Row, ...], tuple[Row, ...]]:
    select = ", ".join(_quote(column) for column in columns)
    new = Counter(map(tuple, connection.execute(f"SELECT {select} FROM main.{_quote(table)}").fetchall()))
    old = Counter(map(tuple, connection.execute(f"SELECT {select} FROM base.{_quote(table)}").fetchall()))

    def expand(counter: Counter[Row]) -> tuple[Row, ...]:
        return tuple(sorted(counter.elements(), key=repr))

    return expand(new - old), expand(old - new)


def diff_databases(old_db: Path, new_db: Path) -> DatabaseDiff:
    """Compare every table of two databases.

    Raises:
        sqlite3.Error: If either database cannot be opened or read.
    """
    diffs: list[TableDiff] = []
    with _read_only(new_db, base_db=old_db) as connection:
        new_tables = _tables(connection, "main")
        old_tables = _tables(connection, "base")
        for table in sorted(new_tables | old_tables):
            if table not in old_tables:
                columns = tuple(column for column, _ in _columns(connection, "main", table))
                diffs.append(TableDiff(table, "added", columns, (), 0, _count(connection, "main", table)))
                continue
            if table not in new_tables:
                columns = tuple(column for column, _ in _columns(connection, "base", table))
                diffs.append(TableDiff(table, "removed", columns, (), _count(connection, "base", table), 0))
                continue
            new_columns = _columns(connection, "main", table)
            old_names = {column for column, _ in _columns(connection, "base", table)}
            new_names = {column for column, _ in new_columns}
            shared = tuple(column for column, _ in new_columns if column in old_names)
            key = tuple(column for column, position in sorted(new_columns, key=lambda item: item[1]) if position)
            if not set(key) <= old_names:
                key = ()
            if key:
                added, removed, changed = _keyed_diff(connection, table, shared, key)
            else:
                added, removed = _multiset_diff(connection, table, shared)
                changed = ()
            diffs.append(
                TableDiff(
                    table,
                    "compared",
                    shared,
                    key,
                    _count(connection, "base", table),
                    _count(connection, "main", table),
                    added_columns=tuple(sorted(new_names - old_names)),
                    removed_columns=tuple(sorted(old_names - new_names)),
                    added=added,
                    removed=removed,
                    changed=changed,
                )
            )
    return DatabaseDiff(tuple(diffs))


def _value(value: Any) -> str:
    text = " ".join(str(value).split()) if value is not None else "NULL"
    return text if len(text) <= _VALUE_WIDTH else text[: _VALUE_WIDTH - 1] + "…"


def _describe(table: TableDiff, row: Row) -> str:
    values = dict(zip(table.columns, row, strict=True))
    shown = list(table.key_columns) or list(table.columns)
    shown += [column for column in _NAME_COLUMNS if values.get(column) not in (None, "") and column not in shown]
    return ", ".join(f"{column}={_value(values[column])}" for column in shown)


def _section(title: str, lines: Sequence[str], limit: int) -> list[str]:
    output = [f"\n**{title} ({len(lines)})**\n\n"]
    shown = lines if limit == 0 else lines[:limit]
    output.extend(f"- {line}\n" for line in shown)
    if len(shown) < len(lines):
        output.append(f"- … {len(lines) - len(shown)} more (use --limit 0 to list all)\n")
    return output


def render_report(diff: DatabaseDiff, old_label: str, new_label: str, *, limit: int = 50) -> str:
    """Render a Markdown report of ``diff``. ``limit`` caps rows per category; 0 lists all."""
    changed_tables = diff.changed_tables
    report = [
        f"# Erenshor data changes: {old_label} → {new_label}\n\n",
        f"**Old**: {old_label}  \n**New**: {new_label}\n\n",
        f"{len(changed_tables)} of {len(diff.tables)} tables changed.\n\n",
    ]
    if not changed_tables:
        return "".join(report)
    report += ["| Table | Old rows | New rows | Added | Removed | Changed |\n", "|---|---|---|---|---|---|\n"]
    for table in changed_tables:
        report.append(
            f"| {table.name} | {table.old_rows:,} | {table.new_rows:,} | {len(table.added):,} | "
            f"{len(table.removed):,} | {len(table.changed):,} |\n"
        )
    for table in changed_tables:
        report.append(f"\n## {table.name}\n")
        if table.status != "compared":
            report.append(f"\nTable {table.status}.\n")
            continue
        matched = ", ".join(table.key_columns) if table.key_columns else "whole rows (no primary key)"
        report.append(f"\nMatched on: {matched}\n")
        if table.added_columns:
            report.append(f"\nAdded columns: {', '.join(table.added_columns)}\n")
        if table.removed_columns:
            report.append(f"\nRemoved columns: {', '.join(table.removed_columns)}\n")
        if table.added:
            report += _section("Added rows", [_describe(table, row) for row in table.added], limit)
        if table.removed:
            report += _section("Removed rows", [_describe(table, row) for row in table.removed], limit)
        if table.changed:
            lines = [
                ", ".join(f"{column}={_value(value)}" for column, value in zip(table.key_columns, row.key, strict=True))
                + ": "
                + "; ".join(f"{column}: {_value(old)} → {_value(new)}" for column, old, new in row.changes)
                for row in table.changed
            ]
            report += _section("Changed rows", lines, limit)
    return "".join(report)
