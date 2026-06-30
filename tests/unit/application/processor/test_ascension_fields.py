"""Tests that Stormcaller/Reaver ascension scalar fields flow from raw to clean DB."""

from erenshor.application.processor.entities import _rename_cols
from erenshor.application.processor.writer import Writer


def _raw_row(**overrides: object) -> dict[str, object]:
    """A minimal raw Ascensions row; defaults all five new fields to non-zero."""
    base: dict[str, object] = {
        "StableKey": "ascension:test",
        "AscensionDBIndex": 0,
        "Id": "1",
        "UsedBy": "Stormcaller",
        "SkillName": "Test",
        "SkillDesc": "desc",
        "MaxRank": 3,
        "SimPlayerWeight": 1,
        "ResourceName": "TEST",
        # New Stormcaller/Reaver fields
        "ReloadHaste": 5.0,
        "LightningProcChance": 10.0,
        "NoCDPenaltyChance": 15.0,
        "KillshotChance": 20.0,
        "TripleAttackChanceReav": 25.0,
    }
    base.update(overrides)
    return base


def test_stormcaller_reaver_fields_flow_to_clean(tmp_path):
    """Raw Ascensions ReloadHaste/LightningProcChance/NoCDPenaltyChance/
    KillshotChance/TripleAttackChanceReav become clean ascensions columns."""
    writer = Writer(tmp_path / "test.sqlite")
    writer.create_schema()

    raw_rows = _rename_cols([_raw_row()])
    writer.insert_ascensions(raw_rows)

    row = writer._conn.execute(
        "SELECT reload_haste, lightning_proc_chance, no_cd_penalty_chance, "
        "killshot_chance, triple_attack_chance_reav FROM ascensions WHERE stable_key = ?",
        ("ascension:test",),
    ).fetchone()
    assert row is not None
    assert row[0] == 5.0
    assert row[1] == 10.0
    assert row[2] == 15.0
    assert row[3] == 20.0
    assert row[4] == 25.0

    writer._conn.close()
