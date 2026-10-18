from __future__ import annotations

from pathlib import Path

from erenshor.application.processor.writer import Writer
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.zones import ZoneRepository


def test_overview_repository_retains_native_capability_and_connection_conditions(tmp_path: Path) -> None:
    path = tmp_path / "overview.sqlite"
    writer = Writer(path)
    writer.create_schema()
    writer.conn.executemany(
        "INSERT INTO zones (stable_key, scene_name, zone_name, display_name, wiki_page_name, image_name, zone_type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("zone:one", "One", "One", "One", "One", "One", "Outdoor"),
            ("zone:two", "Two", "Two", "Two", "Two", "Two", "Dungeon"),
        ],
    )
    writer.conn.executemany(
        "INSERT INTO characters (stable_key, display_name, image_name, encounter_tier, level, "
        "is_friendly, invulnerable, can_be_damaged, level_scales_with_player) "
        "VALUES (?, 'Fixture', 'Fixture', ?, ?, ?, ?, ?, 0)",
        [
            ("character:releasable", "enemy", 34, 0, 1, 1),
            ("character:permanent", "enemy", 99, 0, 1, 0),
            ("character:town", "npc", 99, 1, 0, 1),
        ],
    )
    writer.conn.execute(
        "INSERT INTO character_deduplications (group_key, member_stable_key, is_wiki_generated) "
        "VALUES ('character:group', 'character:releasable', 1)"
    )
    writer.conn.executemany(
        "INSERT INTO character_spawns (character_stable_key, spawn_point_stable_key, zone_stable_key, "
        "is_directly_placed, spawn_chance, level_mod) VALUES (?, ?, 'zone:one', 0, ?, ?)",
        [
            ("character:releasable", "spawn:a", 50, 1),
            ("character:releasable", "spawn:b", 50, 1),
            ("character:permanent", "spawn:c", 50, 0),
            ("character:town", "spawn:d", 50, 0),
            ("character:releasable", "spawn:zero", 0, 20),
        ],
    )
    writer.conn.executemany(
        "INSERT INTO zone_lines (stable_key, scene, destination_zone_stable_key, component_is_enabled, "
        "collider_is_trigger, has_enabled_trigger, is_enabled) VALUES (?, 'One', 'zone:two', 1, 1, ?, ?)",
        [
            ("line:open", 1, 1),
            ("line:locked", 1, 1),
            ("line:inactive", 1, 0),
            ("line:return", 1, 0),
            ("line:not-physical", 0, 1),
        ],
    )
    writer.conn.execute(
        "INSERT INTO gate_conditions (subject_kind, subject_stable_key, gate, group_index, atom_kind, atom_stable_key) "
        "VALUES ('zone_line', 'line:locked', 'fixture', 0, 'quest_done', 'quest:gate')"
    )
    writer.conn.execute(
        "INSERT INTO zone_line_destination_contexts "
        "VALUES ('line:return', 'stored_return', 'destination', 'landing', 'source')"
    )
    writer.conn.commit()
    connection = DatabaseConnection(path, read_only=True)
    try:
        repo = ZoneRepository(connection)
        spawns = repo.get_zone_overview_spawns()
        releasable = [row for row in spawns if row["character"] == "character:group"]
        assert len(releasable) == 1
        assert releasable[0]["damageable"] == 1 and releasable[0]["levelMod"] == 1
        assert any(row["damageable"] == 0 for row in spawns)
        assert any(row["tier"] == "npc" for row in spawns)
        connections = {row["line"]: row for row in repo.get_zone_overview_connections()}
        assert set(connections) == {"line:open", "line:locked", "line:inactive", "line:return"}
        assert connections["line:open"]["conditional"] == 0
        assert connections["line:locked"]["conditional"] == 1
        assert connections["line:inactive"]["conditional"] == 1
        assert connections["line:return"]["kind"] == "stored_return"
        assert connections["line:return"]["destination"] is None
    finally:
        connection.close()
        writer.conn.close()
