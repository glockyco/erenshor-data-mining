"""Writer inserts skip a repeated key and fail on any other broken constraint."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from erenshor.application.processor.writer import Writer

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def writer(tmp_path: Path) -> Iterator[Writer]:
    writer = Writer(tmp_path / "inserts.sqlite")
    writer.create_schema()
    try:
        yield writer
    finally:
        writer.conn.close()


def test_a_repeated_key_keeps_the_first_row(writer: Writer) -> None:
    writer.insert_barriers(
        [
            {"barrier_key": "door:a", "kind": "door", "name": "First"},
            {"barrier_key": "door:a", "kind": "door", "name": "Second"},
        ]
    )
    assert [tuple(row) for row in writer.conn.execute("SELECT name FROM barriers")] == [("First",)]


@pytest.mark.parametrize(
    "row",
    [
        {"barrier_key": "door:a", "kind": "gate", "name": "Unknown kind"},
        {"barrier_key": "door:a", "kind": "door", "name": None},
    ],
)
def test_a_broken_constraint_fails_instead_of_dropping_the_row(writer: Writer, row: dict[str, object]) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        writer.insert_barriers([row])
