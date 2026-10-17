"""The shared coordinate view resolves real native placement identities."""

from pathlib import Path

from erenshor.application.processor.writer import Writer


def test_spawn_coordinates_use_native_spawn_point_key(tmp_path: Path) -> None:
    writer = Writer(tmp_path / "coordinates.sqlite")
    writer.create_schema()
    try:
        writer.conn.execute(
            "INSERT INTO characters (stable_key, display_name, image_name, encounter_tier, level_scales_with_player) "
            "VALUES ('character:host', 'Host', '', 'enemy', 0)"
        )
        writer.conn.execute(
            "INSERT INTO character_spawns "
            "(character_stable_key, spawn_point_stable_key, scene, x, y, z, is_directly_placed) "
            "VALUES ('character:host', 'spawn:native', 'One', 1, 2, 3, 0)"
        )
        rows = writer.conn.execute(
            "SELECT stable_key, scene, x, y, z FROM coordinates WHERE category='SpawnPoint'"
        ).fetchall()
        assert [tuple(row) for row in rows] == [("spawn:native", "One", 1.0, 2.0, 3.0)]
    finally:
        writer.conn.close()
