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

    write_code_facts(db, PAYLOAD, assembly_sha256="abc123")
    write_code_facts(db, PAYLOAD, assembly_sha256="abc123")  # idempotent re-run

    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT fact_id, key, value FROM code_facts ORDER BY fact_id, key").fetchall()
        assert ("loot.world_drop.maps", "min_level", "0") in rows
        assert ("loot.world_drop.maps", "rate", "0.0125") in rows
        assert ("loot.guarantee_one_drop", "ok", "true") in rows
        assert conn.execute("SELECT assembly_sha256 FROM code_facts_meta").fetchone()[0] == "abc123"
        assert conn.execute("SELECT count(*) FROM other").fetchone() is not None
