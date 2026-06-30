"""Tests that character gameplay flags are present in the clean schema."""

from erenshor.application.processor.writer import Writer


def test_character_gameplay_flag_columns_exist(tmp_path):
    """The clean characters table has columns for the exported gameplay flags."""
    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()

    cols = {row[1] for row in writer._conn.execute("PRAGMA table_info(characters)").fetchall()}
    assert "can_never_see_invis" in cols
    assert "dps_dummy" in cols
    assert "is_wyrm" in cols
    assert "no_run" in cols

    writer._conn.close()
