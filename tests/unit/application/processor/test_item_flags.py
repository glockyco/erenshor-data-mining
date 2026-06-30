"""Tests that item interaction/economy flags flow from raw to clean DB."""

from erenshor.application.processor.entities import _rename_cols
from erenshor.application.processor.writer import Writer


def _raw_row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "StableKey": "item:test",
        "ItemDBIndex": 0,
        "Id": "1",
        "ItemName": "Test Item",
        "ResourceName": "TEST",
        "display_name": "Test Item",
        "image_name": "Test Item",
        "wiki_page_name": "Test Item",
        "MustBeEquippedToClick": True,
        "PlayerCannotSell": True,
        "RareItem": True,
    }
    base.update(overrides)
    return base


def test_item_flags_flow_to_clean(tmp_path):
    """Raw Items MustBeEquippedToClick/PlayerCannotSell/RareItem become clean
    items columns."""
    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()

    raw_rows = _rename_cols([_raw_row()])
    writer.insert_items(raw_rows)

    row = writer._conn.execute(
        "SELECT must_be_equipped_to_click, player_cannot_sell, rare_item FROM items WHERE stable_key = ?",
        ("item:test",),
    ).fetchone()
    assert row is not None
    assert row[0] == 1
    assert row[1] == 1
    assert row[2] == 1

    writer._conn.close()
