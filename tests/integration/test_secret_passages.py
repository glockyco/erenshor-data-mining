"""Integration tests for secret-passage candidate classification."""

from __future__ import annotations

import sqlite3


def _rows(db_path, query: str, parameters: tuple[object, ...] = ()) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return list(connection.execute(query, parameters))


def test_secret_passage_candidates_keep_audit_metadata(exported_db) -> None:
    """Every exported candidate has an explicit accepted or excluded outcome."""
    rows = _rows(
        exported_db,
        """
        SELECT object_name, is_excluded, exclusion_reason
        FROM secret_passages
        """,
    )

    assert rows
    assert all(
        (row["is_excluded"] == 0 and row["exclusion_reason"] is None)
        or (row["is_excluded"] == 1 and row["exclusion_reason"])
        for row in rows
    )


def test_known_infrastructure_candidates_are_excluded(exported_db) -> None:
    """Navigation and event geometry never reaches curated consumers."""
    expected_names = {
        "RAIDWELCOME": "event_anchor",
        "ARENA EVENT": "event_anchor",
        "OFFNAV": "off_nav_marker",
        "OFFNAV BOT": "off_nav_marker",
        "Room L1": "room_marker",
        "Room R1": "room_marker",
        "ShiverClouds": "environment_volume",
    }

    for object_name, reason in expected_names.items():
        rows = _rows(
            exported_db,
            """
            SELECT is_excluded, exclusion_reason
            FROM secret_passages
            WHERE object_name = ?
            """,
            (object_name,),
        )
        assert rows, f"Expected candidate {object_name!r} was not exported"
        assert all(row["is_excluded"] == 1 and row["exclusion_reason"] == reason for row in rows)

    navmesh_rows = _rows(
        exported_db,
        """
        SELECT is_excluded, exclusion_reason
        FROM secret_passages
        WHERE lower(object_name) LIKE 'navmeshlink%'
        """,
    )
    assert navmesh_rows
    assert all(row["is_excluded"] == 1 and row["exclusion_reason"] == "navigation_link" for row in navmesh_rows)


def test_ordinary_passage_geometry_remains_curated(exported_db) -> None:
    """Ordinary wall, floor, and bookshelf names remain visible candidates."""
    rows = _rows(
        exported_db,
        """
        SELECT object_name, is_excluded
        FROM secret_passages
        WHERE object_name IN (
            'SM_Prop_Bookshelf_Double_01 (5)',
            'SM_Env_Wall_01',
            'SM_Env_Tiles_Ornate_01 (165)'
        )
        """,
    )

    assert {row["object_name"] for row in rows} == {
        "SM_Prop_Bookshelf_Double_01 (5)",
        "SM_Env_Wall_01",
        "SM_Env_Tiles_Ornate_01 (165)",
    }
    assert all(row["is_excluded"] == 0 for row in rows)
