"""Canonical repository hydration rejects drift and retains typed facts."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from erenshor.application.processor.item_provenance import ProvenanceBuilder
from erenshor.application.processor.writer import Writer
from erenshor.domain.value_objects.item_provenance import (
    CONDITION_PHASES,
    PROVENANCE_SCHEMA_VERSION,
    ConditionPhase,
    ItemAcquisition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceEvidence,
    ProvenanceLocation,
)
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository
from erenshor.infrastructure.database.repository import RepositoryError


@pytest.fixture
def database(tmp_path: Path) -> Iterator[tuple[Writer, DatabaseConnection]]:
    path = tmp_path / "provenance.sqlite"
    writer = Writer(path)
    writer.create_schema()
    writer.conn.execute(
        "INSERT INTO item_provenance_meta VALUES (?, 'fixture-build', '{}')",
        (PROVENANCE_SCHEMA_VERSION,),
    )
    writer.conn.execute(
        "INSERT INTO items (stable_key, display_name, image_name) VALUES ('item:one', 'One', '')",
    )
    writer.conn.execute(
        "INSERT INTO item_dispositions VALUES ('item:one', 'current', NULL, NULL, '[]', '[]')",
    )
    writer.conn.commit()
    db = DatabaseConnection(path, read_only=True)
    try:
        yield writer, db
    finally:
        db.close()
        writer.conn.close()


def _facts(
    writer: Writer,
    count: int | None = 3,
    phase: ConditionPhase = "availability",
) -> tuple[ItemAcquisition, ItemUse]:
    condition = ProvenanceCondition("quest", 0, 0, "quest_done", "quest:one", phase=phase)
    location_condition = ProvenanceCondition(
        "furnishing",
        0,
        0,
        "room_furnished",
        "item:furniture",
        "2",
        scope="placement",
        phase=phase,
    )
    location = ProvenanceLocation(
        "placement",
        "possible_treasure",
        "Scene",
        "zone:one",
        "placement",
        "point:one",
        1.125,
        -2.25,
        3.5,
        "placement",
        10,
        20,
        (location_condition,),
        ("entry:one",),
        "character:copy",
    )
    acquisition = ItemAcquisition(
        "acquisition:one",
        "item:one",
        "character_drop",
        "group:one",
        source_group_key="group:one",
        source_copy_stable_key="character:copy",
        variant_key="variant:one",
        mechanic="mechanic:one",
        probability_kind="bounded",
        probability_min=1.23456789,
        probability_max=35.75,
        probability_basis="per_kill",
        quantity_min=0.5,
        quantity_max=3.75,
        quantity_kind="bounded",
        expected_quantity=0.123456789,
        count_distribution="[0.75,0.2,0.05]",
        guarantee_scope="pool",
        guaranteed_roll_count=count,
        conditions=(condition,),
        locations=(location,),
        evidence=(ProvenanceEvidence("fixture", '["item:one","copy"]'),),
    )
    use = ItemUse(
        "use:one",
        "item:one",
        "item:one",
        "crafting_material",
        "variant:one",
        2,
        0.5,
        3.75,
        "bounded",
        "mechanic:one",
        acquisition.acquisition_key,
        acquisition.conditions,
        acquisition.locations,
        acquisition.evidence,
    )
    builder = ProvenanceBuilder(writer.conn)
    builder.acquisitions.append(acquisition)
    builder.uses.append(use)
    builder.persist()
    writer.conn.commit()
    return acquisition, use


def _corrupt(writer: Writer, sql: str) -> None:
    # Corrupt persisted contracts deliberately so repository validation runs.
    writer.conn.execute("PRAGMA ignore_check_constraints = ON")
    try:
        writer.conn.execute(sql)
        writer.conn.commit()
    finally:
        writer.conn.execute("PRAGMA ignore_check_constraints = OFF")


@pytest.mark.parametrize("count", [None, 0, 3])
def test_all_repository_apis_preserve_complete_facts(
    database: tuple[Writer, DatabaseConnection],
    count: int | None,
) -> None:
    writer, db = database
    acquisition, use = _facts(writer, count)
    repository = ItemProvenanceRepository(db)
    assert repository.get_acquisitions("item:one") == [acquisition]
    assert repository.get_uses("item:one") == [use]
    assert repository.get_uses_targeting("item:one") == [use]
    assert list(repository.iter_acquisitions()) == [acquisition]
    assert list(repository.iter_uses()) == [use]
    assert repository.get_player_access("item:one") == "verified_player"


@pytest.mark.parametrize("versions", [[], [0], [2], [1, 1]])
def test_repository_rejects_missing_duplicate_or_incompatible_metadata(
    database: tuple[Writer, DatabaseConnection],
    versions: list[int],
) -> None:
    writer, db = database
    writer.conn.execute("DELETE FROM item_provenance_meta")
    writer.conn.executemany("INSERT INTO item_provenance_meta VALUES (?, 'fixture', '{}')", [(v,) for v in versions])
    writer.conn.commit()
    with pytest.raises(RepositoryError, match="Unsupported item provenance schema"):
        ItemProvenanceRepository(db)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE item_provenance_meta SET schema_version=1.5",
        "UPDATE item_provenance_meta SET schema_version='future'",
        "UPDATE item_provenance_meta SET game_build_id=''",
        "UPDATE item_provenance_meta SET input_digests='[]'",
        "UPDATE item_provenance_meta SET input_digests='null'",
        "UPDATE item_provenance_meta SET input_digests='invalid'",
        'UPDATE item_provenance_meta SET input_digests=\'{"items":"invalid"}\'',
        "ALTER TABLE item_provenance_meta ADD COLUMN new_mandatory_field TEXT",
        "DROP TABLE item_provenance_meta",
    ],
)
def test_repository_rejects_malformed_schema_metadata(
    database: tuple[Writer, DatabaseConnection],
    sql: str,
) -> None:
    writer, db = database
    writer.conn.execute(sql)
    writer.conn.commit()
    with pytest.raises(RepositoryError, match="Unsupported item provenance schema"):
        ItemProvenanceRepository(db)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE item_acquisitions SET kind='future'",
        "UPDATE item_acquisitions SET player_access_state='maybe'",
        "UPDATE item_acquisitions SET probability_kind='likely'",
        "UPDATE item_acquisitions SET probability_min='string'",
        "UPDATE item_acquisitions SET probability_max=101",
        "UPDATE item_acquisitions SET probability_stage='intermediate'",
        "UPDATE item_acquisitions SET quantity_min=-1",
        "UPDATE item_acquisitions SET guaranteed_roll_count=2.5",
        "UPDATE item_acquisitions SET guaranteed_roll_count=-1",
        "UPDATE item_acquisitions SET count_distribution='invalid'",
        "UPDATE item_acquisition_conditions SET minimum_inclusive=2",
        "UPDATE item_acquisition_conditions SET maximum_inclusive='false'",
        "UPDATE item_acquisition_conditions SET predicate='unknown'",
        "UPDATE item_acquisition_conditions SET group_index=-1",
        "UPDATE item_acquisition_conditions SET phase='unknown_phase'",
        "ALTER TABLE item_acquisition_conditions RENAME COLUMN phase TO unsupported_phase",
        "UPDATE item_acquisition_locations SET relation='unknown'",
        "UPDATE item_acquisition_locations SET x='invalid'",
        "UPDATE item_acquisition_locations SET conditions='{}'",
        "UPDATE item_acquisition_locations SET entry_zone_line_keys='[null]'",
        "UPDATE item_provenance_evidence SET input_relation=''",
        "ALTER TABLE item_acquisitions ADD COLUMN unknown_mandatory TEXT",
        "ALTER TABLE item_acquisition_conditions ADD COLUMN unknown_mandatory TEXT",
        "ALTER TABLE item_acquisition_locations ADD COLUMN unknown_mandatory TEXT",
        "ALTER TABLE item_provenance_evidence ADD COLUMN unknown_mandatory TEXT",
        "ALTER TABLE item_acquisitions DROP COLUMN guaranteed_roll_count",
    ],
)
def test_repository_rejects_malformed_acquisition_or_lost_dimensions(
    database: tuple[Writer, DatabaseConnection],
    sql: str,
) -> None:
    writer, db = database
    _facts(writer)
    _corrupt(writer, sql)
    with pytest.raises(RepositoryError, match="Invalid item provenance acquisition"):
        ItemProvenanceRepository(db).get_acquisitions("item:one")


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE item_uses SET kind='unknown'",
        "UPDATE item_uses SET material_slot=-1",
        "UPDATE item_uses SET quantity_max='invalid'",
        "UPDATE item_use_conditions SET minimum_inclusive=2",
        "UPDATE item_use_locations SET conditions='[null]'",
        "ALTER TABLE item_uses ADD COLUMN unknown_mandatory TEXT",
    ],
)
def test_repository_rejects_malformed_uses_through_both_apis(
    database: tuple[Writer, DatabaseConnection],
    sql: str,
) -> None:
    writer, db = database
    _facts(writer)
    writer.conn.execute(sql)
    writer.conn.commit()
    repository = ItemProvenanceRepository(db)
    with pytest.raises(RepositoryError, match="Invalid item provenance use"):
        repository.get_uses("item:one")
    with pytest.raises(RepositoryError, match="Invalid item provenance use"):
        repository.get_uses_targeting("item:one")


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE item_dispositions SET disposition='unknown'",
        "UPDATE item_dispositions SET current_pages='[null]'",
        "UPDATE item_dispositions SET former_pages='{}'",
        "ALTER TABLE item_dispositions ADD COLUMN unknown_mandatory TEXT",
    ],
)
def test_repository_rejects_malformed_disposition(
    database: tuple[Writer, DatabaseConnection],
    sql: str,
) -> None:
    writer, db = database
    _corrupt(writer, sql)
    with pytest.raises(RepositoryError, match="Invalid item provenance disposition"):
        ItemProvenanceRepository(db).get_disposition("item:one")


@pytest.mark.parametrize("state", ["removed", "unused", "unobtainable"])
def test_retired_dispositions_never_advertise_player_access(
    database: tuple[Writer, DatabaseConnection],
    state: str,
) -> None:
    writer, db = database
    _facts(writer)
    writer.conn.execute("UPDATE item_dispositions SET disposition=?", (state,))
    writer.conn.commit()
    assert ItemProvenanceRepository(db).get_player_access("item:one") == "no_verified_path"


def test_player_access_preserves_or_alternatives_and_impossible_groups(
    database: tuple[Writer, DatabaseConnection],
) -> None:
    writer, db = database
    conditions = (
        ProvenanceCondition("unlock", 0, 0, "quest_done", "quest:one"),
        ProvenanceCondition("unlock", 0, 1, "quest_not_done", "quest:one"),
        ProvenanceCondition("unlock", 1, 0, "quest_done", "quest:two"),
    )
    builder = ProvenanceBuilder(writer.conn)
    builder.acquisitions.append(
        ItemAcquisition(
            "acquisition:one",
            "item:one",
            "ui_grant",
            "ui:one",
            conditions=conditions,
        )
    )
    builder.persist()
    writer.conn.commit()
    assert ItemProvenanceRepository(db).get_player_access("item:one") == "verified_player"
    writer.conn.execute("DELETE FROM item_acquisition_conditions WHERE group_index=1")
    writer.conn.commit()
    assert ItemProvenanceRepository(db).get_player_access("item:one") == "no_verified_path"


def test_nested_location_conditions_use_strict_json_boolean_types(
    database: tuple[Writer, DatabaseConnection],
) -> None:
    writer, db = database
    acquisition, _ = _facts(writer)
    condition = asdict(acquisition.locations[0].conditions[0])
    condition["minimum_inclusive"] = 1
    writer.conn.execute(
        "UPDATE item_acquisition_locations SET conditions=?",
        (json.dumps([condition]),),
    )
    writer.conn.commit()
    with pytest.raises(RepositoryError, match="boolean"):
        ItemProvenanceRepository(db).get_acquisitions("item:one")


@pytest.mark.parametrize("phase", CONDITION_PHASES)
def test_repository_preserves_condition_phase_in_rows_and_location_json(
    database: tuple[Writer, DatabaseConnection],
    phase: ConditionPhase,
) -> None:
    writer, db = database
    acquisition, use = _facts(writer, phase=phase)
    repository = ItemProvenanceRepository(db)
    assert repository.get_acquisitions("item:one") == [acquisition]
    assert repository.get_uses("item:one") == [use]
    assert repository.get_uses_targeting("item:one") == [use]
    assert acquisition.conditions[0].phase == phase
    assert acquisition.locations[0].conditions[0].phase == phase


@pytest.mark.parametrize("mutation", ["missing", "unknown"])
def test_repository_rejects_missing_or_unknown_phase_in_location_json(
    database: tuple[Writer, DatabaseConnection],
    mutation: str,
) -> None:
    writer, db = database
    acquisition, _ = _facts(writer)
    condition = asdict(acquisition.locations[0].conditions[0])
    if mutation == "missing":
        del condition["phase"]
    else:
        condition["phase"] = "unknown_phase"
    writer.conn.execute(
        "UPDATE item_acquisition_locations SET conditions=?",
        (json.dumps([condition]),),
    )
    writer.conn.commit()
    with pytest.raises(RepositoryError, match="phase"):
        ItemProvenanceRepository(db).get_acquisitions("item:one")


@pytest.mark.parametrize("minimum,maximum", [(1, None), (None, 5)])
def test_repository_preserves_one_sided_bounded_quantities(
    database: tuple[Writer, DatabaseConnection],
    minimum: float | None,
    maximum: float | None,
) -> None:
    writer, db = database
    acquisition, use = _facts(writer)
    for table in ("item_acquisitions", "item_uses"):
        writer.conn.execute(
            f"UPDATE {table} SET quantity_kind='bounded', quantity_min=?, quantity_max=?",
            (minimum, maximum),
        )
    writer.conn.commit()
    repository = ItemProvenanceRepository(db)
    assert repository.get_acquisitions("item:one") == [
        replace(acquisition, quantity_kind="bounded", quantity_min=minimum, quantity_max=maximum),
    ]
    expected_use = replace(use, quantity_kind="bounded", quantity_min=minimum, quantity_max=maximum)
    assert repository.get_uses("item:one") == [expected_use]
    assert repository.get_uses_targeting("item:one") == [expected_use]


def test_repository_rejects_bounded_quantities_without_known_endpoints(
    database: tuple[Writer, DatabaseConnection],
) -> None:
    writer, db = database
    _facts(writer)
    for table in ("item_acquisitions", "item_uses"):
        writer.conn.execute(f"UPDATE {table} SET quantity_kind='bounded', quantity_min=NULL, quantity_max=NULL")
    writer.conn.commit()
    repository = ItemProvenanceRepository(db)
    with pytest.raises(RepositoryError, match="at least one numeric bound"):
        repository.get_acquisitions("item:one")
    with pytest.raises(RepositoryError, match="at least one numeric bound"):
        repository.get_uses("item:one")


def test_common_world_membership_comes_only_from_loot_capable_native_contributors(
    database: tuple[Writer, DatabaseConnection],
) -> None:
    writer, db = database
    for fact in (
        "loot.start_initialization_sequence",
        "loot.character_component_binding",
        "loot.corpse_component_binding",
        "treasure.chest_break_roll",
        "treasure.strike_melee",
        "treasure.strike_bolt",
    ):
        writer.conn.execute("INSERT INTO code_facts (fact_id,key,value) VALUES (?, 'ok', 'true')", (fact,))
    for copy, immune, damageable, chest in (
        ("mortal", 0, 1, 0),
        ("released", 1, 1, 0),
        ("immune", 1, 0, 0),
        ("chest", 1, 0, 1),
    ):
        key = "character:" + copy
        writer.conn.execute(
            "INSERT INTO characters "
            "(stable_key,display_name,image_name,encounter_tier,level_scales_with_player,"
            "invulnerable,can_be_damaged,treasure_chest) VALUES (?,?,'','npc',0,?,?,?)",
            (key, copy, immune, damageable, chest),
        )
        writer.conn.execute(
            "INSERT INTO character_deduplications (group_key,member_stable_key) VALUES ('group:shared',?)",
            (key,),
        )
        writer.conn.execute(
            "INSERT INTO character_spawns (character_stable_key,is_directly_placed) VALUES (?,1)",
            (key,),
        )
        writer.conn.execute(
            "INSERT INTO loot_drops "
            "(character_stable_key,item_stable_key,loot_table_stable_key,source_component_is_enabled,"
            "drop_probability,drop_count_distribution,is_common_world_item) VALUES (?,'item:one',?,1,10,'[0.9,0.1]',1)",
            (key, "loot-table:" + copy),
        )
    builder = ProvenanceBuilder(writer.conn)
    builder.loot()
    builder.persist()
    writer.conn.commit()
    repository = ItemProvenanceRepository(db)
    assert repository.get_common_world_character_keys() == frozenset(
        {"character:mortal", "character:released", "character:chest"}
    )
    assert builder.input_exclusions == {("loot_drops", '["character:immune","item:one"]'): "loot_host_undamageable"}
