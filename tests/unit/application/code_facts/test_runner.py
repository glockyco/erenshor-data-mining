"""The writer owns the raw `code_facts` tables; tested with a fake tool payload."""

import sqlite3
from pathlib import Path
from typing import Any

from erenshor.application.code_facts.runner import write_code_facts

PAYLOAD: dict[str, Any] = {
    "schema": 1,
    "assembly": "/x/Managed/Assembly-CSharp.dll",
    "facts": [
        {
            "id": "loot.world_drop.maps",
            "mode": "extract",
            "values": {"rate": "0.0125", "min_level": "0"},
            "ok": None,
        },
        {"id": "loot.guarantee_one_drop", "mode": "assert", "values": None, "ok": True},
    ],
    "errors": [],
}


def test_writer_creates_and_replaces_only_its_tables(tmp_path: Path) -> None:
    db = tmp_path / "raw.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE other (x)")  # pre-existing export table must survive

    write_code_facts(
        db,
        PAYLOAD,
        assembly_sha256="abc123",
        game_build_id="24362350",
        game_build_published_at="2026-07-23T21:53:44+00:00",
    )
    write_code_facts(  # idempotent re-run
        db,
        PAYLOAD,
        assembly_sha256="abc123",
        game_build_id="24362350",
        game_build_published_at="2026-07-23T21:53:44+00:00",
    )

    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT fact_id, key, value FROM code_facts ORDER BY fact_id, key").fetchall()
        assert ("loot.world_drop.maps", "min_level", "0") in rows
        assert ("loot.world_drop.maps", "rate", "0.0125") in rows
        assert ("loot.guarantee_one_drop", "ok", "true") in rows
        assert conn.execute("SELECT assembly_sha256 FROM code_facts_meta").fetchone()[0] == "abc123"
        assert conn.execute("SELECT game_build_id FROM code_facts_meta").fetchone()[0] == "24362350"
        assert (
            conn.execute("SELECT game_build_published_at FROM code_facts_meta").fetchone()[0]
            == "2026-07-23T21:53:44+00:00"
        )
        assert conn.execute("SELECT count(*) FROM other").fetchone() is not None


def test_publish_date_survives_re_extraction(tmp_path: Path) -> None:
    """Re-extracting without a game update must not advance the build date.

    ``extracted_at`` tracks the run and moves every time; the provenance a
    consumer renders must track the game build instead, or a re-run would claim
    freshness the data does not have.
    """
    db = tmp_path / "raw.sqlite"
    build_date = "2026-07-23T21:53:44+00:00"

    write_code_facts(db, PAYLOAD, assembly_sha256="abc", game_build_id="1", game_build_published_at=build_date)
    with sqlite3.connect(db) as conn:
        first_extracted = conn.execute("SELECT extracted_at FROM code_facts_meta").fetchone()[0]

    write_code_facts(db, PAYLOAD, assembly_sha256="abc", game_build_id="1", game_build_published_at=build_date)
    with sqlite3.connect(db) as conn:
        second_extracted, second_build_date = conn.execute(
            "SELECT extracted_at, game_build_published_at FROM code_facts_meta"
        ).fetchone()

    assert second_extracted != first_extracted
    assert second_build_date == build_date


def test_writer_records_unknown_build_id_as_null(tmp_path: Path) -> None:
    """A missing or unresolvable SteamDB build must persist as NULL, never as a
    placeholder string.

    Downstream provenance rendering keys on NULL to omit the line entirely, so a
    stringified 'None' or 'unknown' would surface as a fabricated build number.
    """
    db = tmp_path / "raw.sqlite"

    write_code_facts(db, PAYLOAD, assembly_sha256="abc123", game_build_id=None, game_build_published_at=None)

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT game_build_id FROM code_facts_meta").fetchone()[0] is None
        assert conn.execute("SELECT game_build_published_at FROM code_facts_meta").fetchone()[0] is None
