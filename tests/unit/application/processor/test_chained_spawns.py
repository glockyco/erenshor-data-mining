"""Tests for Category B chained spawn expansion."""

import pytest

from erenshor.application.processor.characters import expand_chained_spawns
from erenshor.application.processor.writer import Writer


@pytest.fixture
def clean_db(tmp_path):
    """A clean DB with the minimal schema for chained spawn expansion."""
    db_path = tmp_path / "test.sqlite"
    writer = Writer(db_path)
    writer.create_schema()
    yield writer._conn
    writer._conn.close()


def _insert_character(conn, stable_key, display_name):
    conn.execute(
        "INSERT INTO characters (stable_key, display_name, image_name) VALUES (?, ?, ?)",
        (stable_key, display_name, display_name),
    )


def _insert_spawn(conn, char_key, scene, x, y, z):
    conn.execute(
        """INSERT INTO character_spawns
           (character_stable_key, spawn_point_stable_key, zone_stable_key, scene,
            x, y, z, is_enabled, is_directly_placed, is_trigger_spawn, spawn_chance)
           VALUES (?, ?, NULL, ?, ?, ?, ?, 1, 0, 0, 1.0)""",
        (char_key, f"spawn:{scene}:{x}:{y}:{z}", scene, x, y, z),
    )


def _insert_chain(conn, parent, child, source):
    conn.execute(
        "INSERT INTO character_chained_spawns (parent_stable_key, child_stable_key, source_script) VALUES (?, ?, ?)",
        (parent, child, source),
    )


def test_expand_creates_child_at_parent_coords(clean_db):
    """Child inherits the parent's spawn position."""
    conn = clean_db
    _insert_character(conn, "character:parent", "Parent")
    _insert_character(conn, "character:child", "Child")
    _insert_spawn(conn, "character:parent", "TestScene", 10.0, 20.0, 30.0)
    _insert_chain(conn, "character:parent", "character:child", "Constellation")
    conn.commit()

    expand_chained_spawns(conn)

    rows = conn.execute(
        "SELECT scene, x, y, z, source_script FROM character_spawns WHERE character_stable_key = 'character:child'"
    ).fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row["scene"] == "TestScene"
    assert row["x"] == 10.0
    assert row["y"] == 20.0
    assert row["z"] == 30.0
    assert row["source_script"] == "Constellation"


def test_expand_multiple_parent_spawns(clean_db):
    """Parent with multiple spawns → child gets one row per parent spawn."""
    conn = clean_db
    _insert_character(conn, "character:parent", "Parent")
    _insert_character(conn, "character:child", "Child")
    _insert_spawn(conn, "character:parent", "Scene1", 1.0, 2.0, 3.0)
    _insert_spawn(conn, "character:parent", "Scene2", 4.0, 5.0, 6.0)
    _insert_chain(conn, "character:parent", "character:child", "NPCFightEvent")
    conn.commit()

    expand_chained_spawns(conn)

    rows = conn.execute(
        "SELECT scene FROM character_spawns WHERE character_stable_key = 'character:child' ORDER BY scene"
    ).fetchall()
    assert len(rows) == 2
    assert [r["scene"] for r in rows] == ["Scene1", "Scene2"]


def test_expand_recursive_chain(clean_db):
    """Multi-level chain: grandparent → parent → child.

    The parent is itself a chained child with no direct spawn. Expansion
    must recurse so the grandchild inherits the grandparent's position.
    """
    conn = clean_db
    _insert_character(conn, "character:gp", "Grandparent")
    _insert_character(conn, "character:parent", "Parent")
    _insert_character(conn, "character:child", "Child")
    _insert_spawn(conn, "character:gp", "GrandScene", 100.0, 200.0, 300.0)
    _insert_chain(conn, "character:gp", "character:parent", "NPCFightEvent")
    _insert_chain(conn, "character:parent", "character:child", "NPCFightEvent")
    conn.commit()

    expand_chained_spawns(conn)

    parent_rows = conn.execute(
        "SELECT scene, x, y, z FROM character_spawns WHERE character_stable_key = 'character:parent'"
    ).fetchall()
    assert len(parent_rows) == 1
    assert parent_rows[0]["scene"] == "GrandScene"
    assert parent_rows[0]["x"] == 100.0

    child_rows = conn.execute(
        "SELECT scene, x, y, z FROM character_spawns WHERE character_stable_key = 'character:child'"
    ).fetchall()
    assert len(child_rows) == 1
    assert child_rows[0]["scene"] == "GrandScene"
    assert child_rows[0]["x"] == 100.0


def test_expand_cycle_does_not_infinite_loop(clean_db):
    """A cycle in chained spawns (A→B→A) terminates without hanging."""
    conn = clean_db
    _insert_character(conn, "character:a", "A")
    _insert_character(conn, "character:b", "B")
    _insert_spawn(conn, "character:a", "CycleScene", 1.0, 2.0, 3.0)
    _insert_chain(conn, "character:a", "character:b", "CycleScript")
    _insert_chain(conn, "character:b", "character:a", "CycleScript")
    conn.commit()

    expand_chained_spawns(conn)

    b_rows = conn.execute("SELECT scene FROM character_spawns WHERE character_stable_key = 'character:b'").fetchall()
    assert len(b_rows) == 1
    assert b_rows[0]["scene"] == "CycleScene"


def test_expand_dedup_same_position(clean_db):
    """Two chains pointing the same child to the same position deduplicate."""
    conn = clean_db
    _insert_character(conn, "character:p1", "Parent1")
    _insert_character(conn, "character:p2", "Parent2")
    _insert_character(conn, "character:child", "Child")
    _insert_spawn(conn, "character:p1", "SameScene", 5.0, 5.0, 5.0)
    _insert_spawn(conn, "character:p2", "SameScene", 5.0, 5.0, 5.0)
    _insert_chain(conn, "character:p1", "character:child", "ScriptA")
    _insert_chain(conn, "character:p2", "character:child", "ScriptB")
    conn.commit()

    expand_chained_spawns(conn)

    rows = conn.execute(
        "SELECT source_script FROM character_spawns WHERE character_stable_key = 'character:child' "
        "ORDER BY source_script"
    ).fetchall()
    assert len(rows) == 2
    assert [r["source_script"] for r in rows] == ["ScriptA", "ScriptB"]


def test_expand_parent_no_spawns_skips(clean_db):
    """Parent with no spawn rows → child gets nothing (no position to inherit)."""
    conn = clean_db
    _insert_character(conn, "character:parent", "Parent")
    _insert_character(conn, "character:child", "Child")
    _insert_chain(conn, "character:parent", "character:child", "OrphanScript")
    conn.commit()

    expand_chained_spawns(conn)

    rows = conn.execute("SELECT * FROM character_spawns WHERE character_stable_key = 'character:child'").fetchall()
    assert len(rows) == 0


def test_expand_idempotent(clean_db):
    """Running expansion twice doesn't duplicate rows."""
    conn = clean_db
    _insert_character(conn, "character:parent", "Parent")
    _insert_character(conn, "character:child", "Child")
    _insert_spawn(conn, "character:parent", "Scene1", 1.0, 2.0, 3.0)
    _insert_chain(conn, "character:parent", "character:child", "Script")
    conn.commit()

    expand_chained_spawns(conn)
    expand_chained_spawns(conn)

    rows = conn.execute("SELECT * FROM character_spawns WHERE character_stable_key = 'character:child'").fetchall()
    assert len(rows) == 1


def test_expand_multiple_children_from_one_parent(clean_db):
    """One parent spawns multiple different children — each inherits the parent's position."""
    conn = clean_db
    _insert_character(conn, "character:parent", "Parent")
    _insert_character(conn, "character:child_a", "Child A")
    _insert_character(conn, "character:child_b", "Child B")
    _insert_spawn(conn, "character:parent", "Scene1", 1.0, 2.0, 3.0)
    _insert_chain(conn, "character:parent", "character:child_a", "Script")
    _insert_chain(conn, "character:parent", "character:child_b", "Script")
    conn.commit()

    expand_chained_spawns(conn)

    a_rows = conn.execute(
        "SELECT scene, x, y, z FROM character_spawns WHERE character_stable_key = 'character:child_a'"
    ).fetchall()
    b_rows = conn.execute(
        "SELECT scene, x, y, z FROM character_spawns WHERE character_stable_key = 'character:child_b'"
    ).fetchall()
    assert len(a_rows) == 1
    assert len(b_rows) == 1
    assert a_rows[0]["scene"] == "Scene1"
    assert b_rows[0]["scene"] == "Scene1"
    assert a_rows[0]["x"] == 1.0
    assert b_rows[0]["x"] == 1.0


def test_expand_child_with_own_direct_spawns(clean_db):
    """Child already has a direct spawn row — expansion adds the inherited
    chain spawn without overwriting the existing one."""
    conn = clean_db
    _insert_character(conn, "character:parent", "Parent")
    _insert_character(conn, "character:child", "Child")
    _insert_spawn(conn, "character:parent", "ParentScene", 10.0, 20.0, 30.0)
    _insert_spawn(conn, "character:child", "ChildScene", 40.0, 50.0, 60.0)
    _insert_chain(conn, "character:parent", "character:child", "ChainScript")
    conn.commit()

    expand_chained_spawns(conn)

    rows = conn.execute(
        "SELECT scene, x, y, z, source_script FROM character_spawns "
        "WHERE character_stable_key = 'character:child' ORDER BY scene"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["scene"] == "ChildScene"
    assert rows[0]["source_script"] is None
    assert rows[1]["scene"] == "ParentScene"
    assert rows[1]["source_script"] == "ChainScript"


def test_expand_diamond_chain_dedup(clean_db):
    """Diamond: A→B, A→C, B→D, C→D. D inherits from both paths.
    Same position from both parents deduplicates to one row per source."""
    conn = clean_db
    _insert_character(conn, "character:a", "A")
    _insert_character(conn, "character:b", "B")
    _insert_character(conn, "character:c", "C")
    _insert_character(conn, "character:d", "D")
    _insert_spawn(conn, "character:a", "DiamondScene", 5.0, 5.0, 5.0)
    _insert_chain(conn, "character:a", "character:b", "Script")
    _insert_chain(conn, "character:a", "character:c", "Script")
    _insert_chain(conn, "character:b", "character:d", "ScriptB")
    _insert_chain(conn, "character:c", "character:d", "ScriptC")
    conn.commit()

    expand_chained_spawns(conn)

    d_rows = conn.execute(
        "SELECT scene, x, y, z, source_script FROM character_spawns "
        "WHERE character_stable_key = 'character:d' ORDER BY source_script"
    ).fetchall()
    assert len(d_rows) == 2
    assert all(r["scene"] == "DiamondScene" for r in d_rows)
    assert all(r["x"] == 5.0 for r in d_rows)
    assert {r["source_script"] for r in d_rows} == {"ScriptB", "ScriptC"}


def test_expand_empty_chained_table_is_noop(clean_db):
    """No chained spawns in the table — expansion does nothing."""
    conn = clean_db
    _insert_character(conn, "character:lonely", "Lonely")
    _insert_spawn(conn, "character:lonely", "SoloScene", 1.0, 2.0, 3.0)
    conn.commit()

    expand_chained_spawns(conn)

    rows = conn.execute("SELECT * FROM character_spawns").fetchall()
    assert len(rows) == 1
