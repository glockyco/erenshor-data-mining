"""Native evidence preserves source bindings, denominators and unused inputs."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

from erenshor.application.processor.native_item_inputs import NativeItemInputs

if TYPE_CHECKING:
    from erenshor.domain.value_objects.item_provenance import ProvenanceEvidence


@pytest.fixture
def raw() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        "CREATE TABLE Characters (StableKey TEXT, DestroyOnDeath INTEGER, "
        "DoNotLeaveCorpse INTEGER, IsSimPlayer INTEGER);"
        "CREATE TABLE LootTableSources (StableKey TEXT, CharacterStableKey TEXT, MiningNodeStableKey TEXT, "
        "ComponentIndex INTEGER, "
        "ComponentIsEnabled INTEGER, MaxNumberDrops INTEGER, MaxNonCommonDrops INTEGER, "
        "NumberOfGuaranteedDrops INTEGER, UltraRareDropCount INTEGER, LegendaryDropCount INTEGER, "
        "RareDropCount INTEGER, UncommonDropCount INTEGER, CommonDropCount INTEGER, "
        "GuaranteeOneDropCount INTEGER, ActualDropsCount INTEGER);"
        "CREATE TABLE LootDrops (LootTableStableKey TEXT, CharacterStableKey TEXT, ItemStableKey TEXT);"
        "CREATE TABLE LootTablePoolSlots (LootTableStableKey TEXT, Pool TEXT, Position INTEGER, ItemStableKey TEXT);"
        "CREATE TABLE CommonWorldItems (Position INTEGER, ItemStableKey TEXT);"
        "CREATE TABLE SpecialWorldDropItems (Pool TEXT, Position INTEGER, ItemStableKey TEXT);"
        "CREATE TABLE SpecialWorldDropFlags (Name TEXT, Value INTEGER);"
        "CREATE TABLE MiningNodes (StableKey TEXT, CommonCount INTEGER, RareCount INTEGER, LegendCount INTEGER);"
        "CREATE TABLE MiningNodeItems (MiningNodeStableKey TEXT, ItemStableKey TEXT);"
        "CREATE TABLE MiningNodePoolSlots (MiningNodeStableKey TEXT, Pool TEXT, Position INTEGER, ItemStableKey TEXT);"
        "CREATE TABLE MiningFallbackItems (SourceKey TEXT, ItemStableKey TEXT);"
        "CREATE TABLE Waters (StableKey TEXT);"
        "CREATE TABLE WaterFishables (WaterStableKey TEXT, Type TEXT, Position INTEGER, ItemStableKey TEXT);"
        "CREATE TABLE ItemDrops (SourceItemStableKey TEXT, DroppedItemStableKey TEXT, PoolStableKey TEXT);"
        "CREATE TABLE ItemDropPools (PoolStableKey TEXT, SourceComponentKey TEXT, SlotCount INTEGER);"
        "CREATE TABLE ItemDropPoolSlots (PoolStableKey TEXT, Position INTEGER, ItemStableKey TEXT);"
        "INSERT INTO SpecialWorldDropFlags VALUES ('DropMasks', 0), ('DemoBuild', 0);"
        "INSERT INTO MiningFallbackItems VALUES ('GameManager.GuaranteeMine', 'item:fallback');"
    )
    yield connection
    connection.close()


def _identity(table: str, *primary: object) -> tuple[str, str]:
    return "raw." + table, json.dumps(primary, ensure_ascii=False, separators=(",", ":"))


def _keys(evidence: tuple[ProvenanceEvidence, ...]) -> set[tuple[str, str]]:
    return {(entry.input_relation, entry.input_primary_key) for entry in evidence}


def _loot(raw: sqlite3.Connection, copy: str = "copy", table: str = "actual:table") -> None:
    raw.execute("INSERT INTO Characters VALUES (?, 0, 0, 0)", (copy,))
    raw.execute(
        "INSERT INTO LootTableSources VALUES (?, ?, NULL, 0, 1, 2, 1, 1, 0, 0, 0, 0, 3, 0, 1)",
        (table, copy),
    )
    raw.executemany(
        "INSERT INTO LootTablePoolSlots VALUES (?, ?, ?, ?)",
        [
            (table, "CommonDrop", 0, "item:a"),
            (table, "CommonDrop", 1, None),
            (table, "CommonDrop", 2, "item:a"),
            (table, "ActualDrops", 0, "item:other"),
        ],
    )
    raw.execute("INSERT INTO LootDrops VALUES (?, ?, 'item:a')", (table, copy))


def test_loot_resolves_actual_table_and_retains_all_cdf_inputs(raw: sqlite3.Connection) -> None:
    _loot(raw)
    raw.executemany("INSERT INTO CommonWorldItems VALUES (?, ?)", [(0, "item:world"), (1, None)])
    helper = NativeItemInputs(raw)
    evidence = _keys(helper.evidence_for("character_drop", ("copy", "item:a")))
    assert evidence == {
        _identity("LootDrops", "actual:table", "item:a"),
        _identity("LootTableSources", "actual:table"),
        *(_identity("LootTablePoolSlots", "actual:table", "CommonDrop", position) for position in range(3)),
        _identity("LootTablePoolSlots", "actual:table", "ActualDrops", 0),
        _identity("CommonWorldItems", 0),
        _identity("CommonWorldItems", 1),
    }
    assert _identity("LootDrops", "copy", "item:a") not in evidence
    assert not evidence.intersection(helper.input_exclusions)
    assert helper.evidence_for("character_drop", ("copy", "item:a")) == helper.evidence_for(
        "character_drop", ("copy", "item:a")
    )


def test_common_attachment_does_not_add_unselected_copies(raw: sqlite3.Connection) -> None:
    _loot(raw, "selected", "table:selected")
    _loot(raw, "unencountered", "table:unencountered")
    raw.execute("INSERT INTO CommonWorldItems VALUES (0, 'item:world')")
    helper = NativeItemInputs(raw)
    assert helper.evidence_for("common_world_item", ("item:world",)) == ()
    helper.evidence_for("character_drop", ("selected", "item:a"))
    assert helper.input_exclusions[_identity("LootDrops", "table:unencountered", "item:a")] == "unencountered_copy"
    assert helper.input_exclusions[_identity("LootTableSources", "table:unencountered")] == "unencountered_copy"
    assert _identity("LootTableSources", "table:selected") not in helper.input_exclusions


def test_unavailable_common_contributor_has_explicit_native_exclusions(raw: sqlite3.Connection) -> None:
    _loot(raw)
    helper = NativeItemInputs(raw, unavailable_loot_copies=frozenset({"copy"}))
    helper.finalize()
    for origin in (
        _identity("LootDrops", "actual:table", "item:a"),
        _identity("LootTableSources", "actual:table"),
        _identity("LootTablePoolSlots", "actual:table", "CommonDrop", 1),
        _identity("LootTablePoolSlots", "actual:table", "ActualDrops", 0),
    ):
        assert helper.input_exclusions[origin] == "loot_host_undamageable"


@pytest.mark.parametrize(
    ("flags", "reason"),
    [
        ((1, 0, 0), "loot_host_destroy_on_death"),
        ((0, 1, 0), "loot_host_do_not_leave_corpse"),
        ((0, 0, 1), "non_player_host"),
        ((0, 0, 0), "unencountered_copy"),
    ],
)
def test_unselected_native_loot_preserves_host_reason(
    raw: sqlite3.Connection, flags: tuple[int, int, int], reason: str
) -> None:
    _loot(raw)
    raw.execute("UPDATE Characters SET DestroyOnDeath = ?, DoNotLeaveCorpse = ?, IsSimPlayer = ?", flags)
    helper = NativeItemInputs(raw)
    assert helper.input_exclusions[_identity("LootTableSources", "actual:table")] == reason
    assert helper.input_exclusions[_identity("LootTablePoolSlots", "actual:table", "CommonDrop", 1)] == reason
    assert helper.input_exclusions[_identity("LootDrops", "actual:table", "item:a")] == reason


def test_missing_host_and_empty_configs_remain_native_exclusions(raw: sqlite3.Connection) -> None:
    raw.execute("INSERT INTO LootTableSources VALUES ('orphan', NULL, NULL, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1)")
    raw.execute("INSERT INTO LootTablePoolSlots VALUES ('orphan', 'ActualDrops', 0, 'item:a')")
    raw.execute("INSERT INTO LootTableSources VALUES ('empty', 'copy:empty', NULL, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0)")
    raw.execute("INSERT INTO Characters VALUES ('copy:empty', 0, 0, 0)")
    helper = NativeItemInputs(raw)
    assert helper.input_exclusions[_identity("LootTableSources", "orphan")] == "loot_host_missing"
    assert helper.input_exclusions[_identity("LootTablePoolSlots", "orphan", "ActualDrops", 0)] == "loot_host_missing"
    assert helper.input_exclusions[_identity("LootTableSources", "empty")] == "empty_native_loot_configuration"


def test_mining_includes_null_denominators_empty_pool_config_and_native_fallback(raw: sqlite3.Connection) -> None:
    raw.execute("INSERT INTO MiningNodes VALUES ('node', 3, 0, 0)")
    raw.executemany("INSERT INTO MiningNodeItems VALUES ('node', ?)", [("item:a",), ("item:fallback",)])
    raw.executemany(
        "INSERT INTO MiningNodePoolSlots VALUES ('node', ?, ?, ?)",
        [("guarantee", 0, None), ("Common", 0, "item:a"), ("Common", 1, "item:a"), ("Common", 2, None)],
    )
    helper = NativeItemInputs(raw)
    keys = _keys(helper.evidence_for("mining", ("node", "item:fallback")))
    assert keys == {
        _identity("MiningNodeItems", "node", "item:fallback"),
        _identity("MiningNodes", "node"),
        _identity("MiningNodePoolSlots", "node", "guarantee", 0),
        *(_identity("MiningNodePoolSlots", "node", "Common", position) for position in range(3)),
        _identity("MiningFallbackItems", "GameManager.GuaranteeMine"),
    }
    assert not keys.intersection(helper.input_exclusions)


def test_native_mining_guarantee_does_not_claim_global_fallback(raw: sqlite3.Connection) -> None:
    raw.execute("INSERT INTO MiningNodes VALUES ('node', 0, 0, 0)")
    raw.execute("INSERT INTO MiningNodeItems VALUES ('node', 'item:a')")
    raw.execute("INSERT INTO MiningNodePoolSlots VALUES ('node', 'guarantee', 0, 'item:a')")
    helper = NativeItemInputs(raw)
    keys = _keys(helper.evidence_for("mining", ("node", "item:a")))
    fallback = _identity("MiningFallbackItems", "GameManager.GuaranteeMine")
    assert fallback not in keys
    assert helper.input_exclusions[fallback] == "unused_mining_fallback"


def _fishing(raw: sqlite3.Connection) -> None:
    raw.execute("INSERT INTO Waters VALUES ('water')")
    raw.executemany(
        "INSERT INTO WaterFishables VALUES ('water', 'DayFishable', ?, ?)",
        [(0, "item:fish"), (1, "item:fish"), (2, None)],
    )
    raw.executemany(
        "INSERT INTO SpecialWorldDropItems VALUES ('Maps', ?, ?)",
        [(0, "item:map"), (1, "item:map"), (2, None), (3, "item:other-map"), (4, "item:not-fishable")],
    )


def test_fishing_night_fallback_preserves_all_local_and_selected_global_slots(raw: sqlite3.Connection) -> None:
    _fishing(raw)
    helper = NativeItemInputs(raw)
    keys = _keys(helper.evidence_for("fishing", ("water", "NightFishable", "item:map")))
    assert keys == {
        _identity("Waters", "water"),
        *(_identity("WaterFishables", "water", "DayFishable", position) for position in range(3)),
        *(_identity("SpecialWorldDropItems", "Maps", position) for position in range(4)),
    }
    assert _identity("SpecialWorldDropItems", "Maps", 4) not in helper.input_exclusions
    bonus = _keys(helper.evidence_for("fishing_bonus", ("item:map",)))
    assert bonus == {_identity("SpecialWorldDropItems", "Maps", position) for position in range(4)}
    with pytest.raises(ValueError, match="no selected map slot"):
        helper.evidence_for("fishing_bonus", ("item:not-fishable",))


def test_distinct_native_night_pool_does_not_claim_day_positions(raw: sqlite3.Connection) -> None:
    _fishing(raw)
    raw.execute("INSERT INTO WaterFishables VALUES ('water', 'NightFishable', 0, 'item:night-fish')")
    helper = NativeItemInputs(raw)
    keys = _keys(helper.evidence_for("fishing", ("water", "NightFishable", "item:night-fish")))
    assert _identity("WaterFishables", "water", "NightFishable", 0) in keys
    assert _identity("WaterFishables", "water", "DayFishable", 0) not in keys


def test_special_pool_identity_is_distinct_and_all_weights_are_evidence(raw: sqlite3.Connection) -> None:
    raw.executemany(
        "INSERT INTO SpecialWorldDropItems VALUES (?, ?, ?)",
        [
            ("Maps", 0, "item:a"),
            ("Maps", 1, None),
            ("Maps", 2, "item:a"),
            ("WorldDropMolds", 0, "item:a"),
            ("Masks", 0, "item:mask"),
        ],
    )
    helper = NativeItemInputs(raw)
    maps = _keys(helper.evidence_for("special_world_drop", ("item:a", "Maps")))
    assert maps == {_identity("SpecialWorldDropItems", "Maps", position) for position in range(3)}
    assert _identity("SpecialWorldDropItems", "WorldDropMolds", 0) not in maps
    assert helper.input_exclusions[_identity("SpecialWorldDropItems", "Masks", 0)] == "native_world_drop_gate_disabled"
    with pytest.raises(ValueError, match="disabled by DropMasks"):
        helper.evidence_for("special_world_drop", ("item:mask", "Masks"))


def test_enabled_special_pool_attaches_actual_native_gate(raw: sqlite3.Connection) -> None:
    raw.execute("UPDATE SpecialWorldDropFlags SET Value = 1 WHERE Name = 'DropMasks'")
    raw.execute("INSERT INTO SpecialWorldDropItems VALUES ('Masks', 0, 'item:mask')")
    helper = NativeItemInputs(raw)
    assert _keys(helper.evidence_for("special_world_drop", ("item:mask", "Masks"))) == {
        _identity("SpecialWorldDropItems", "Masks", 0),
        _identity("SpecialWorldDropFlags", "DropMasks"),
    }


def test_item_drop_preserves_pool_and_click_source_binding_with_all_slots(raw: sqlite3.Connection) -> None:
    raw.executemany(
        "INSERT INTO ItemDropPools VALUES (?, ?, 3)", [("pool:a", "native:Misc:a"), ("pool:b", "native:Misc:b")]
    )
    raw.executemany("INSERT INTO ItemDropPoolSlots VALUES ('pool:a', ?, ?)", [(0, "item:a"), (1, None), (2, "item:a")])
    raw.executemany(
        "INSERT INTO ItemDropPoolSlots VALUES ('pool:b', ?, ?)", [(0, "item:a"), (1, "item:b"), (2, "item:b")]
    )
    raw.executemany(
        "INSERT INTO ItemDrops VALUES (?, 'item:a', ?)",
        [("click:one", "pool:a"), ("click:two", "pool:a"), ("click:one", "pool:b")],
    )
    helper = NativeItemInputs(raw)
    keys = _keys(helper.evidence_for("item_drop", ("click:two", "item:a", "pool:a")))
    assert keys == {
        _identity("ItemDrops", "click:two", "item:a", "pool:a"),
        _identity("ItemDropPools", "pool:a"),
        *(_identity("ItemDropPoolSlots", "pool:a", position) for position in range(3)),
    }
    assert _identity("ItemDrops", "click:one", "item:a", "pool:a") not in helper.input_exclusions
    assert _identity("ItemDropPools", "pool:b") not in helper.input_exclusions
    with pytest.raises(ValueError, match=r"Unconsumed mandatory native item inputs.*ItemDrops"):
        helper.finalize()
    with pytest.raises(ValueError, match="Missing native item input ItemDrops"):
        helper.evidence_for("item_drop", ("click:two", "item:a", "pool:b"))


@pytest.mark.parametrize(
    "table",
    [
        "LootTableSources",
        "LootTablePoolSlots",
        "MiningNodePoolSlots",
        "MiningFallbackItems",
        "ItemDropPools",
        "ItemDropPoolSlots",
    ],
)
def test_mandatory_new_native_tables_cannot_be_synthesized(raw: sqlite3.Connection, table: str) -> None:
    raw.execute(f'DROP TABLE "{table}"')
    with pytest.raises(ValueError, match=rf"require refreshed export tables: {table}.*extract export"):
        NativeItemInputs(raw)


def test_old_loot_identity_columns_are_rejected(raw: sqlite3.Connection) -> None:
    raw.execute("DROP TABLE LootDrops")
    raw.execute("CREATE TABLE LootDrops (CharacterStableKey TEXT, ItemStableKey TEXT)")
    with pytest.raises(ValueError, match=r"LootDrops.*LootTableStableKey.*extract export"):
        NativeItemInputs(raw)


def test_loot_host_binding_is_not_inferred_from_copy_name(raw: sqlite3.Connection) -> None:
    _loot(raw)
    raw.execute("UPDATE LootDrops SET CharacterStableKey = 'other-copy'")
    with pytest.raises(ValueError, match="does not match native LootTableSources binding"):
        NativeItemInputs(raw)


def test_duplicate_native_positions_fail_instead_of_collapsing(raw: sqlite3.Connection) -> None:
    raw.executemany("INSERT INTO CommonWorldItems VALUES (0, ?)", [("item:a",), ("item:a",)])
    with pytest.raises(ValueError, match="Duplicate native item input CommonWorldItems"):
        NativeItemInputs(raw)


def test_missing_denominator_slot_fails_without_consuming_evidence(raw: sqlite3.Connection) -> None:
    _loot(raw)
    raw.execute("INSERT INTO CommonWorldItems VALUES (0, 'item:world')")
    raw.execute("DELETE FROM LootTablePoolSlots WHERE Pool = 'CommonDrop' AND Position = 1")
    helper = NativeItemInputs(raw)
    before = dict(helper.input_exclusions)
    with pytest.raises(ValueError, match="positions do not match serialized count"):
        helper.evidence_for("character_drop", ("copy", "item:a"))
    assert helper.input_exclusions == before


def test_null_native_mining_list_is_a_named_prerequisite(raw: sqlite3.Connection) -> None:
    raw.execute("INSERT INTO MiningNodes VALUES ('node', NULL, 0, 0)")
    raw.execute("INSERT INTO MiningNodeItems VALUES ('node', 'item:a')")
    raw.execute("INSERT INTO MiningNodePoolSlots VALUES ('node', 'guarantee', 0, 'item:a')")
    helper = NativeItemInputs(raw)
    with pytest.raises(ValueError, match=r"MiningNodePoolSlots node Common.*null list prerequisite"):
        helper.evidence_for("mining", ("node", "item:a"))


def test_finalization_rejects_dropped_mining_outcome_even_after_config_was_consumed(
    raw: sqlite3.Connection,
) -> None:
    raw.execute("INSERT INTO MiningNodes VALUES ('node', 1, 0, 0)")
    raw.executemany("INSERT INTO MiningNodeItems VALUES ('node', ?)", [("item:a",), ("item:b",)])
    raw.executemany(
        "INSERT INTO MiningNodePoolSlots VALUES ('node', ?, 0, ?)",
        [("guarantee", "item:a"), ("Common", "item:b")],
    )
    helper = NativeItemInputs(raw)
    helper.evidence_for("mining", ("node", "item:a"))
    assert _identity("MiningNodeItems", "node", "item:b") not in helper.input_exclusions
    with pytest.raises(ValueError, match=r'raw.MiningNodeItems\["node","item:b"\]'):
        helper.finalize()
    helper.evidence_for("mining", ("node", "item:b"))
    helper.finalize()


def test_finalization_rejects_dropped_click_source_even_when_pool_was_consumed(
    raw: sqlite3.Connection,
) -> None:
    raw.execute("INSERT INTO ItemDropPools VALUES ('pool', 'native:Misc', 1)")
    raw.execute("INSERT INTO ItemDropPoolSlots VALUES ('pool', 0, 'item:a')")
    raw.executemany(
        "INSERT INTO ItemDrops VALUES (?, 'item:a', 'pool')",
        [("click:one",), ("click:two",)],
    )
    helper = NativeItemInputs(raw)
    helper.evidence_for("item_drop", ("click:one", "item:a", "pool"))
    with pytest.raises(ValueError, match=r'raw.ItemDrops\["click:two","item:a","pool"\]'):
        helper.finalize()
    helper.evidence_for("item_drop", ("click:two", "item:a", "pool"))
    helper.finalize()


def test_finalization_accepts_only_proved_empty_or_disabled_configurations(
    raw: sqlite3.Connection,
) -> None:
    raw.execute("INSERT INTO Waters VALUES ('water:empty')")
    raw.execute("INSERT INTO ItemDropPools VALUES ('pool:null', 'native:Misc', 1)")
    raw.execute("INSERT INTO ItemDropPoolSlots VALUES ('pool:null', 0, NULL)")
    raw.execute("INSERT INTO SpecialWorldDropItems VALUES ('Masks', 0, 'item:disabled')")
    raw.execute("INSERT INTO SpecialWorldDropItems VALUES ('WorldDropMolds', 0, NULL)")
    helper = NativeItemInputs(raw)
    helper.finalize()
    assert helper.input_exclusions[_identity("Waters", "water:empty")] == "empty_native_fishing_configuration"
    assert helper.input_exclusions[_identity("ItemDropPools", "pool:null")] == "empty_native_item_drop_configuration"
    assert helper.input_exclusions[_identity("SpecialWorldDropItems", "Masks", 0)] == "native_world_drop_gate_disabled"
    assert set(helper.input_exclusions.values()).isdisjoint({"no_executed_item_grant"})


def test_finalization_does_not_ignore_an_enabled_native_world_output(
    raw: sqlite3.Connection,
) -> None:
    raw.execute("INSERT INTO SpecialWorldDropItems VALUES ('WorldDropMolds', 0, 'item:mold')")
    helper = NativeItemInputs(raw)
    assert _identity("SpecialWorldDropItems", "WorldDropMolds", 0) not in helper.input_exclusions
    with pytest.raises(ValueError, match=r"raw\.SpecialWorldDropItems"):
        helper.finalize()
    helper.evidence_for("special_world_drop", ("item:mold", "WorldDropMolds"))
    helper.finalize()


def test_input_tables_exposes_full_captured_payload_without_requery_or_copy(
    raw: sqlite3.Connection,
) -> None:
    _loot(raw)
    helper = NativeItemInputs(raw)
    captured = helper.input_tables
    assert len(captured) == 16
    assert captured["LootTableSources"][0]["MaxNumberDrops"] == 2
    assert captured["LootTableSources"][0]["ComponentIsEnabled"] == 1
    assert captured["LootTablePoolSlots"][1]["ItemStableKey"] is None
    raw.execute("UPDATE LootTableSources SET MaxNumberDrops = 99")
    assert helper.input_tables["LootTableSources"] is captured["LootTableSources"]
    assert helper.input_tables["LootTableSources"][0]["MaxNumberDrops"] == 2
    assert captured["MiningNodePoolSlots"] == []


def _mining_loot(raw: sqlite3.Connection) -> None:
    raw.execute("INSERT INTO MiningNodes VALUES ('node', 0, 0, 0)")
    raw.execute("INSERT INTO MiningNodeItems VALUES ('node', 'item:ore')")
    raw.execute("INSERT INTO MiningNodePoolSlots VALUES ('node', 'guarantee', 0, 'item:ore')")
    raw.execute(
        "INSERT INTO LootTableSources VALUES ('opaque:mining:loot', NULL, 'node', 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)"
    )


def test_native_mining_loot_binding_is_excluded_without_world_host_fabrication(
    raw: sqlite3.Connection,
) -> None:
    _mining_loot(raw)
    helper = NativeItemInputs(raw)
    source = _identity("LootTableSources", "opaque:mining:loot")
    assert helper.input_exclusions[source] == "non_world_mining_host"
    assert helper.input_tables["LootDrops"] == []
    assert helper.input_tables["Characters"] == []
    helper.evidence_for("mining", ("node", "item:ore"))
    helper.finalize()


def test_null_slots_on_native_mining_loot_keep_the_actual_source_exclusion(
    raw: sqlite3.Connection,
) -> None:
    _mining_loot(raw)
    raw.execute("UPDATE LootTableSources SET ActualDropsCount = 1")
    raw.execute("INSERT INTO LootTablePoolSlots VALUES ('opaque:mining:loot', 'ActualDrops', 0, NULL)")
    helper = NativeItemInputs(raw)
    assert (
        helper.input_exclusions[_identity("LootTablePoolSlots", "opaque:mining:loot", "ActualDrops", 0)]
        == "non_world_mining_host"
    )


def test_native_mining_loot_rejects_simultaneous_world_host_binding(
    raw: sqlite3.Connection,
) -> None:
    _mining_loot(raw)
    raw.execute("UPDATE LootTableSources SET CharacterStableKey = 'world:host'")
    with pytest.raises(ValueError, match="links both world and mining hosts"):
        NativeItemInputs(raw)


def test_native_mining_loot_requires_the_actual_referenced_node(
    raw: sqlite3.Connection,
) -> None:
    _mining_loot(raw)
    raw.execute("DELETE FROM MiningNodes")
    with pytest.raises(ValueError, match="Missing native item input MiningNodes"):
        NativeItemInputs(raw)


@pytest.mark.parametrize("grant_relation", ["slot", "outcome"])
def test_native_mining_loot_cannot_hide_world_item_grants(
    raw: sqlite3.Connection,
    grant_relation: str,
) -> None:
    _mining_loot(raw)
    if grant_relation == "slot":
        raw.execute("INSERT INTO LootTablePoolSlots VALUES ('opaque:mining:loot', 'ActualDrops', 0, 'item:grant')")
    else:
        raw.execute("INSERT INTO LootDrops VALUES ('opaque:mining:loot', NULL, 'item:grant')")
    with pytest.raises(ValueError, match="mining loot source has world loot grants"):
        NativeItemInputs(raw)


def test_native_loot_requires_refreshed_typed_mining_binding_column(
    raw: sqlite3.Connection,
) -> None:
    raw.execute("ALTER TABLE LootTableSources DROP COLUMN MiningNodeStableKey")
    with pytest.raises(ValueError, match=r"LootTableSources.*MiningNodeStableKey.*extract export"):
        NativeItemInputs(raw)
