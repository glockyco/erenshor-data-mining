"""Exercise sheet SQL and conserve canonical item facts without game data or live writes."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine

import erenshor.application.sheets as sheets_package
from erenshor.application.processor.writer import Writer
from erenshor.application.sheets.formatter import SheetsFormatter
from erenshor.domain.value_objects.item_provenance import (
    PROVENANCE_SCHEMA_VERSION,
    ItemAcquisition,
    ItemDisposition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceEvidence,
    ProvenanceLocation,
    fact_to_dict,
)
from erenshor.infrastructure.database.repository import RepositoryError

QUERIES_DIR = Path(sheets_package.__file__).parent / "queries"
ACQUISITION_KINDS = (
    "character_drop",
    "common_world_item",
    "special_world_drop",
    "vendor",
    "dialog",
    "quest_reward",
    "crafting",
    "item_drop",
    "spell_created",
    "mining",
    "fishing",
    "fishing_bonus",
    "auction_house",
    "item_bag",
    "starting_class",
    "ui_grant",
    "item_conversion",
    "internal_equipment",
)
USE_KINDS = (
    "crafting_material",
    "crafting_recipe",
    "quest_requirement",
    "item_drop",
    "spell_created",
    "item_conversion",
    "smithing",
    "quality_offering",
    "zone_restriction",
)


@pytest.fixture
def writer(tmp_path: Path) -> Iterator[Writer]:
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    writer.conn.execute(
        "INSERT INTO item_provenance_meta VALUES (?, 'fixture-build', '{}')", (PROVENANCE_SCHEMA_VERSION,)
    )
    writer.conn.create_function("map_marker_url", 1, lambda key: f"https://maps.example.invalid/map?sel=marker:{key}")
    try:
        yield writer
    finally:
        writer.conn.close()


def _rows(writer: Writer, sheet: str) -> list[dict[str, Any]]:
    return [dict(row) for row in writer.conn.execute((QUERIES_DIR / f"{sheet}.sql").read_text(encoding="utf-8"))]


def _insert(writer: Writer, table: str, values: dict[str, Any]) -> None:
    columns = ", ".join(values)
    parameters = ", ".join("?" for _ in values)
    writer.conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({parameters})", tuple(values.values()))


def _insert_fact(writer: Writer, fact: ItemAcquisition | ItemUse) -> None:
    data: dict[str, Any] = fact_to_dict(fact)
    conditions = data.pop("conditions")
    locations = data.pop("locations")
    evidence = data.pop("evidence")
    family = "acquisition" if isinstance(fact, ItemAcquisition) else "use"
    key = fact.acquisition_key if isinstance(fact, ItemAcquisition) else fact.use_key
    _insert(writer, f"item_{family}s", data)
    for condition in conditions:
        _insert(writer, f"item_{family}_conditions", {"owner_key": key, **condition})
    for location in locations:
        _insert(
            writer,
            f"item_{family}_locations",
            {
                "owner_key": key,
                **location,
                "conditions": json.dumps(location["conditions"]),
                "entry_zone_line_keys": json.dumps(location["entry_zone_line_keys"]),
            },
        )
    for record in evidence:
        _insert(writer, "item_provenance_evidence", {"owner_key": key, **record})


def _condition(group: int = 0, atom: int = 0, **values: Any) -> ProvenanceCondition:
    return ProvenanceCondition(
        group_index=group,
        atom_index=atom,
        **{
            "gate_key": "gate:fixture",
            "predicate": "actor_level",
            "reference_stable_key": "quest:fixture",
            "reference_slot": "room:2",
            "actor": "player",
            "value": "night",
            "minimum": 10.5,
            "maximum": 20.25,
            "minimum_inclusive": False,
            "maximum_inclusive": True,
            "scope": "source",
            **values,
        },
    )


def _acquisition(key: str, kind: str, **values: Any) -> ItemAcquisition:
    return ItemAcquisition(
        acquisition_key=key,
        kind=kind,
        **{
            "item_stable_key": "item:bread",
            "source_stable_key": f"source:{kind}",
            "source_group_key": "group:fixture",
            "source_copy_stable_key": "character:copy",
            "variant_key": "route:fixture",
            "mechanic": "mechanic:fixture",
            "player_access_state": "internal_only" if kind == "internal_equipment" else "verified_player",
            "probability_kind": "unknown" if kind == "auction_house" else "exact",
            "probability_min": None if kind == "auction_house" else 12.345678901,
            "probability_max": None if kind == "auction_house" else 12.345678901,
            "probability_basis": "per_use",
            "probability_stage": "final_acquisition",
            "quantity_min": 0.5,
            "quantity_max": 3.25,
            "quantity_kind": "bounded",
            "expected_quantity": 0.123456789,
            "count_distribution": '{"0":0.8,"1":0.2}',
            "guarantee_scope": "pool_roll",
            "guaranteed_roll_count": 2 if kind == "character_drop" else None,
            "conditions": (_condition(), _condition(atom=1, predicate="room_furnished"), _condition(group=1)),
            "locations": (ProvenanceLocation(location_key="location:unlocated", relation="unlocated"),),
            "evidence": (ProvenanceEvidence("fixture_inputs", key),),
            **values,
        },
    )


@pytest.fixture
def canonical_facts(writer: Writer) -> tuple[list[ItemAcquisition], list[ItemUse], list[ItemDisposition]]:
    for key, name in (("item:bread", "Bread"), ("item:bread-copy", "Bread"), ("item:recipe", "Recipe")):
        _insert(writer, "items", {"stable_key": key, "display_name": name, "image_name": name})
    for key, name in (("character:copy", "Actual copy"), ("character:backup", "Unused backup")):
        _insert(
            writer,
            "characters",
            {
                "stable_key": key,
                "display_name": name,
                "image_name": name,
                "encounter_tier": "enemy",
                "level_scales_with_player": 0,
            },
        )
    acquisitions = [_acquisition(f"acquisition:{kind}", kind) for kind in ACQUISITION_KINDS]
    acquisitions.extend(
        [
            _acquisition(
                "acquisition:copy-two",
                "character_drop",
                source_copy_stable_key="character:backup",
                probability_min=27.891234567,
                probability_max=27.891234567,
            ),
            _acquisition("acquisition:same-name", "crafting", item_stable_key="item:bread-copy", variant_key="2"),
            _acquisition(
                "acquisition:zero",
                "item_drop",
                probability_min=0.0,
                probability_max=0.0,
                player_access_state="non_acquirable",
            ),
            _acquisition(
                "acquisition:unknown",
                "ui_grant",
                probability_kind="unknown",
                probability_min=None,
                probability_max=None,
                quantity_min=None,
                quantity_max=None,
                quantity_kind="unknown",
                expected_quantity=None,
                count_distribution=None,
                guarantee_scope=None,
                player_access_state="unconfirmed_player",
            ),
            _acquisition(
                "acquisition:internal",
                "internal_equipment",
                probability_kind="not_applicable",
                probability_min=None,
                probability_max=None,
                player_access_state="internal_only",
            ),
            _acquisition("acquisition:fishing-native", "fishing", probability_stage="native_pool"),
            _acquisition(
                "acquisition:auction-replacement",
                "auction_house",
                variant_key="replacement",
                conditions=(_condition(actor="sim_player", minimum=30, maximum=35),),
            ),
            _acquisition(
                "acquisition:auction-surplus",
                "auction_house",
                variant_key="gear_surplus",
                conditions=(_condition(actor="player", minimum=40, maximum=50),),
            ),
        ]
    )
    common_index = ACQUISITION_KINDS.index("common_world_item")
    acquisitions[common_index] = _acquisition(
        "acquisition:common_world_item",
        "common_world_item",
        source_stable_key=None,
        source_group_key=None,
        source_copy_stable_key=None,
        probability_kind="bounded",
        probability_min=0.123456789,
        probability_max=0.987654321,
        evidence=(
            ProvenanceEvidence("loot_drops", '["character:swap-one","item:bread"]'),
            ProvenanceEvidence("loot_drops", '["character:swap-two","item:bread"]'),
        ),
    )
    treasure = (
        ProvenanceLocation(
            location_key="treasure:01-low",
            relation="possible_treasure",
            scene="SceneWithoutWikiPage",
            zone_stable_key="zone:unpublished",
            placement_key="placement:low",
            coordinate_stable_key="point:low",
            x=1.123456789,
            y=2.234567891,
            z=3.345678912,
            gate_scope="placement:low",
            player_level_min=1,
            player_level_max=10,
            conditions=(_condition(scope="placement"),),
            entry_zone_line_keys=("entry:allowed", "entry:alternate"),
            source_copy_stable_key="character:copy",
        ),
        ProvenanceLocation(
            location_key="treasure:02-high",
            relation="possible_treasure",
            player_level_min=30,
            player_level_max=40,
            source_copy_stable_key="character:backup",
        ),
    )
    acquisitions[0] = _acquisition("acquisition:character_drop", "character_drop", locations=treasure)
    uses = [
        ItemUse(
            use_key=f"use:{kind}",
            item_stable_key="item:bread",
            target_stable_key="item:recipe",
            kind=kind,
            variant_key="variant:one",
            material_slot=2,
            quantity_min=2.5,
            quantity_max=4.5,
            quantity_kind="bounded",
            mechanic="mechanic:fixture",
            outcome_key="acquisition:crafting",
            conditions=(_condition(),),
            locations=treasure,
            evidence=(ProvenanceEvidence("fixture_uses", kind),),
        )
        for kind in USE_KINDS
    ]
    for fact in [*acquisitions, *uses]:
        _insert_fact(writer, fact)
    dispositions = [
        ItemDisposition("item:bread", "current", current_pages=("Bread",)),
        ItemDisposition("item:removed", "removed", "Reviewed removal", "review:fixture", (), ("Old Bread",)),
        ItemDisposition("item:unobtainable", "unobtainable", "Reviewed player restriction"),
        ItemDisposition("item:unused", "unused", current_pages=("Unused Bread",), former_pages=("Unused",)),
    ]
    for disposition in dispositions:
        data = fact_to_dict(disposition)
        for field in ("current_pages", "former_pages"):
            data[field] = json.dumps(data[field])
        _insert(writer, "item_dispositions", data)
    return acquisitions, uses, dispositions


def _projected_contract(writer: Writer) -> dict[str, list[dict[str, Any]]]:
    """Reassemble normalized sheet rows for an offline lossless coverage assertion."""
    conditions = _rows(writer, "item-conditions")
    locations = _rows(writer, "item-locations")
    evidence = _rows(writer, "item-evidence")
    result: dict[str, list[dict[str, Any]]] = {}
    for family in ("acquisition", "use"):
        facts = _rows(writer, f"item-{family}s")
        for fact in facts:
            fact.pop("item_name")
            key = fact[f"{family}_key"]
            fact["conditions"] = []
            for row in conditions:
                if row["fact_type"] == family and row["owner_key"] == key:
                    condition = {k: v for k, v in row.items() if k not in {"fact_type", "owner_key"}}
                    for field in ("minimum_inclusive", "maximum_inclusive"):
                        condition[field] = bool(condition[field])
                    fact["conditions"].append(condition)
            fact["locations"] = []
            for row in locations:
                if row["fact_type"] == family and row["owner_key"] == key:
                    location = {k: v for k, v in row.items() if k not in {"fact_type", "owner_key"}}
                    for field in ("conditions", "entry_zone_line_keys"):
                        location[field] = json.loads(location[field])
                    fact["locations"].append(location)
            fact["evidence"] = [
                {k: v for k, v in row.items() if k != "owner_key"} for row in evidence if row["owner_key"] == key
            ]
        result[family] = facts
    result["disposition"] = _rows(writer, "item-dispositions")
    for disposition in result["disposition"]:
        disposition.pop("item_name")
        for field in ("current_pages", "former_pages"):
            disposition[field] = json.loads(disposition[field])
    return result


def _assert_coverage(
    actual: dict[str, list[dict[str, Any]]],
    expected: tuple[list[ItemAcquisition], list[ItemUse], list[ItemDisposition]],
) -> None:
    for family, facts in zip(("acquisition", "use", "disposition"), expected, strict=True):
        identity = "item_stable_key" if family == "disposition" else f"{family}_key"
        projected = {row[identity]: row for row in actual[family]}
        required = {getattr(fact, identity): json.loads(json.dumps(fact_to_dict(fact))) for fact in facts}
        assert len(actual[family]) == len(projected), f"Duplicate {family} identity"
        assert projected == required, f"Lost {family} identities or dimensions"


def test_every_sheet_query_runs_against_the_clean_schema(writer: Writer, tmp_path: Path) -> None:
    writer.conn.commit()
    engine = create_engine(f"sqlite:///{tmp_path / 'clean.sqlite'}")
    try:
        formatter = SheetsFormatter(engine, QUERIES_DIR, map_base_url="https://maps.example.invalid")
        sheets = formatter.format_all_sheets()
        assert set(sheets) == {path.stem for path in QUERIES_DIR.glob("*.sql")}
        assert all(rows and rows[0] for rows in sheets.values())
    finally:
        engine.dispose()


def test_normalized_item_sheets_conserve_every_dimension(
    writer: Writer,
    canonical_facts: tuple[list[ItemAcquisition], list[ItemUse], list[ItemDisposition]],
) -> None:
    _assert_coverage(_projected_contract(writer), canonical_facts)
    assert {row["kind"] for row in _rows(writer, "item-acquisitions")} == set(ACQUISITION_KINDS)
    assert {row["kind"] for row in _rows(writer, "item-uses")} == set(USE_KINDS)


@pytest.mark.parametrize(
    "dimension",
    [
        "acquisition_key",
        "item_stable_key",
        "source_stable_key",
        "source_copy_stable_key",
        "source_group_key",
        "variant_key",
        "mechanic",
        "player_access_state",
        "probability_kind",
        "probability_min",
        "probability_max",
        "probability_basis",
        "probability_stage",
        "quantity_min",
        "quantity_max",
        "quantity_kind",
        "expected_quantity",
        "count_distribution",
        "guarantee_scope",
        "guaranteed_roll_count",
        "conditions",
        "locations",
        "evidence",
    ],
)
def test_offline_coverage_rejects_a_lost_acquisition_dimension(
    writer: Writer,
    canonical_facts: tuple[list[ItemAcquisition], list[ItemUse], list[ItemDisposition]],
    dimension: str,
) -> None:
    projected = _projected_contract(writer)
    projected["acquisition"][0].pop(dimension)
    with pytest.raises((AssertionError, KeyError)):
        _assert_coverage(projected, canonical_facts)


def test_offline_coverage_rejects_a_missing_kind(
    writer: Writer,
    canonical_facts: tuple[list[ItemAcquisition], list[ItemUse], list[ItemDisposition]],
) -> None:
    projected = _projected_contract(writer)
    projected["acquisition"] = [row for row in projected["acquisition"] if row["kind"] != "ui_grant"]
    with pytest.raises(AssertionError, match="Lost acquisition"):
        _assert_coverage(projected, canonical_facts)


def test_drop_sheet_keeps_common_world_evidence_without_named_swapped_sources(
    writer: Writer,
    canonical_facts: tuple[list[ItemAcquisition], list[ItemUse], list[ItemDisposition]],
) -> None:
    rows = _rows(writer, "drop-chances")
    world = [row for row in rows if row["Source Type"] == "Common world item"]
    assert len(world) == 1
    assert world[0]["Source"] == "Common world item"
    assert world[0]["Drop Chance (%)"] is None
    assert (world[0]["probability_min"], world[0]["probability_max"]) == (0.123456789, 0.987654321)
    assert world[0]["source_copy_stable_key"] is None
    own = {row["source_copy_stable_key"]: row["Drop Chance (%)"] for row in rows if row["Source Type"] == "Character"}
    assert own == {"character:copy": 12.345678901, "character:backup": 27.891234567}
    evidence = [row for row in _rows(writer, "item-evidence") if row["owner_key"] == world[0]["acquisition_key"]]
    assert {row["input_primary_key"] for row in evidence} == {
        '["character:swap-one","item:bread"]',
        '["character:swap-two","item:bread"]',
    }
    assert "acquisition:zero" not in {row["acquisition_key"] for row in rows}


def test_fishing_preserves_time_routes_and_does_not_add_native_probabilities(writer: Writer) -> None:
    _insert(writer, "items", {"stable_key": "item:bread", "display_name": "Bread", "image_name": "Bread"})
    for key, chance, stage, time in (
        ("day", 11.123456789, "final_acquisition", "day"),
        ("night", 4.987654321, "final_acquisition", "night"),
        ("native", 13.123456789, "native_pool", "day"),
    ):
        _insert_fact(
            writer,
            _acquisition(
                key,
                "fishing",
                source_stable_key="water:fixture",
                probability_min=chance,
                probability_max=chance,
                probability_stage=stage,
                conditions=(_condition(predicate="time_of_day", value=time),),
            ),
        )
    rows = _rows(writer, "fishing")
    assert {row["acquisition_key"]: row["Chance (%)"] for row in rows} == {"day": 11.123456789, "night": 4.987654321}
    assert all(row["zone_name"] is None and row["position_x"] is None for row in rows)
    assert {row["value"] for row in _rows(writer, "item-conditions")} == {"day", "night"}
    assert len(_rows(writer, "item-acquisitions")) == 3


@pytest.mark.parametrize(
    "sheet,kind", [("fishing", "fishing_bonus"), ("mining-nodes", "mining"), ("item-bags", "item_bag")]
)
def test_located_sheets_keep_unpublished_and_unlocated_sources(writer: Writer, sheet: str, kind: str) -> None:
    _insert(writer, "items", {"stable_key": "item:bread", "display_name": "Bread", "image_name": "Bread"})
    _insert_fact(writer, _acquisition("unlocated", kind))
    _insert_fact(
        writer,
        _acquisition(
            "located",
            kind,
            locations=(
                ProvenanceLocation(
                    location_key="place:fixture",
                    relation="fixed",
                    zone_stable_key="zone:missing",
                    coordinate_stable_key="point:fixture",
                    x=1.123456789,
                    y=2.5,
                    z=3.75,
                ),
            ),
        ),
    )
    rows = {row["acquisition_key"]: row for row in _rows(writer, sheet)}
    assert set(rows) == {"unlocated", "located"}
    assert rows["located"]["position_x"] == 1.123456789
    assert rows["unlocated"]["position_x"] is None
    if sheet == "item-bags":
        assert rows["unlocated"]["MapLink"] is None
        assert rows["located"]["MapLink"].endswith("marker:point:fixture")


def test_sheet_formatter_preserves_numeric_and_unknown_values(
    writer: Writer,
    canonical_facts: tuple[list[ItemAcquisition], list[ItemUse], list[ItemDisposition]],
    tmp_path: Path,
) -> None:
    writer.conn.commit()
    engine = create_engine(f"sqlite:///{tmp_path / 'clean.sqlite'}")
    try:
        formatter = SheetsFormatter(engine, QUERIES_DIR, map_base_url="https://maps.example.invalid")
        headers, *values = formatter.format_sheet("item-acquisitions")
        rows = {row["acquisition_key"]: row for row in (dict(zip(headers, cells, strict=True)) for cells in values)}
        assert rows["acquisition:character_drop"]["probability_min"] == 12.345678901
        assert rows["acquisition:zero"]["probability_min"] == 0.0
        assert rows["acquisition:unknown"]["probability_min"] == ""
        assert rows["acquisition:unknown"]["quantity_min"] == ""
        assert rows["acquisition:internal"]["probability_kind"] == "not_applicable"
    finally:
        engine.dispose()


@pytest.mark.parametrize("versions", [[], [0], [PROVENANCE_SCHEMA_VERSION + 1], [PROVENANCE_SCHEMA_VERSION] * 2])
def test_sheet_formatter_rejects_missing_or_incompatible_provenance(
    writer: Writer,
    tmp_path: Path,
    versions: list[int],
) -> None:
    writer.conn.execute("DELETE FROM item_provenance_meta")
    writer.conn.executemany(
        "INSERT INTO item_provenance_meta VALUES (?, 'fixture-build', '{}')", [(v,) for v in versions]
    )
    writer.conn.commit()
    engine = create_engine(f"sqlite:///{tmp_path / 'clean.sqlite'}")
    try:
        with pytest.raises(RepositoryError, match="Unsupported item provenance schema"):
            formatter = SheetsFormatter(engine, QUERIES_DIR, map_base_url="https://maps.example.invalid")
            formatter.format_sheet("item-acquisitions")
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "dimension",
    [
        "use_key",
        "item_stable_key",
        "target_stable_key",
        "kind",
        "variant_key",
        "material_slot",
        "quantity_min",
        "quantity_max",
        "quantity_kind",
        "mechanic",
        "outcome_key",
        "conditions",
        "locations",
        "evidence",
    ],
)
def test_offline_coverage_rejects_a_lost_use_dimension(
    writer: Writer,
    canonical_facts: tuple[list[ItemAcquisition], list[ItemUse], list[ItemDisposition]],
    dimension: str,
) -> None:
    projected = _projected_contract(writer)
    projected["use"][0].pop(dimension)
    with pytest.raises((AssertionError, KeyError)):
        _assert_coverage(projected, canonical_facts)


@pytest.mark.parametrize(
    "dimension",
    [
        "item_stable_key",
        "disposition",
        "reason",
        "evidence",
        "current_pages",
        "former_pages",
    ],
)
def test_offline_coverage_rejects_a_lost_lifecycle_dimension(
    writer: Writer,
    canonical_facts: tuple[list[ItemAcquisition], list[ItemUse], list[ItemDisposition]],
    dimension: str,
) -> None:
    projected = _projected_contract(writer)
    projected["disposition"][0].pop(dimension)
    with pytest.raises((AssertionError, KeyError)):
        _assert_coverage(projected, canonical_facts)


def test_item_summaries_keep_every_recipe_reward_and_material_slot(writer: Writer) -> None:
    for key, name in (("item:bread", "Bread"), ("item:recipe", "Recipe")):
        _insert(writer, "items", {"stable_key": key, "display_name": name, "image_name": name, "is_auctionable": 1})
    for slot in (1, 2):
        _insert_fact(
            writer,
            _acquisition(
                f"reward:{slot}",
                "crafting",
                source_stable_key="item:recipe",
                variant_key=str(slot),
                quantity_min=slot,
                quantity_max=slot,
                quantity_kind="exact",
            ),
        )
        _insert_fact(
            writer,
            ItemUse(
                use_key=f"material:{slot}",
                item_stable_key="item:bread",
                target_stable_key="item:recipe",
                kind="crafting_material",
                variant_key="operation:fixture",
                material_slot=slot,
                quantity_min=slot + 1,
                quantity_max=slot + 1,
                quantity_kind="exact",
            ),
        )
    _insert_fact(writer, _acquisition("auction:direct", "auction_house", variant_key="direct"))
    rows = {row["stable_key"]: row for row in _rows(writer, "items")}
    assert rows["item:recipe"]["template_ingredient_stable_keys"] == "item:bread, item:bread"
    assert rows["item:recipe"]["template_reward_stable_key"] == "item:bread, item:bread"
    assert rows["item:bread"]["can_be_listed_by_sims"] == 1
    assert rows["item:recipe"]["can_be_listed_by_sims"] == 0
    assert {row["quantity_min"] for row in _rows(writer, "item-acquisitions") if row["kind"] == "crafting"} == {1, 2}
    assert {row["material_slot"] for row in _rows(writer, "item-uses")} == {1, 2}


def test_character_vendor_summary_uses_the_encountered_copy(writer: Writer) -> None:
    _insert(writer, "items", {"stable_key": "item:bread", "display_name": "Bread", "image_name": "Bread"})
    for key in ("character:copy", "character:representative"):
        _insert(
            writer,
            "characters",
            {
                "stable_key": key,
                "display_name": key,
                "image_name": key,
                "encounter_tier": "npc",
                "level_scales_with_player": 0,
            },
        )
    _insert_fact(
        writer,
        _acquisition(
            "vendor:copy",
            "vendor",
            source_stable_key="character:representative",
            source_copy_stable_key="character:copy",
        ),
    )
    rows = {row["stable_key"]: row for row in _rows(writer, "characters")}
    assert rows["character:copy"]["vendor_item_stable_keys"] == "item:bread"
    assert rows["character:representative"]["vendor_item_stable_keys"] is None


def test_quest_summaries_keep_variant_rewards_and_required_slots(writer: Writer) -> None:
    for key, name in (("item:bread", "Bread"), ("item:bread-copy", "Other Bread")):
        _insert(writer, "items", {"stable_key": key, "display_name": name, "image_name": name})
    _insert(writer, "quests", {"stable_key": "quest:fixture", "display_name": "Quest", "image_name": "Quest"})
    for slot, item_key in enumerate(("item:bread", "item:bread-copy"), start=1):
        variant = f"quest-resource:{slot}"
        _insert(
            writer,
            "quest_variants",
            {
                "resource_name": variant,
                "quest_stable_key": "quest:fixture",
                "quest_db_index": slot,
                "quest_name": variant,
            },
        )
        _insert_fact(
            writer,
            ItemAcquisition(
                acquisition_key=f"quest-reward:{slot}",
                item_stable_key=item_key,
                kind="quest_reward",
                source_stable_key="quest:fixture",
                variant_key=variant,
            ),
        )
        for material_slot in (1, 2):
            _insert_fact(
                writer,
                ItemUse(
                    use_key=f"quest-required:{slot}:{material_slot}",
                    item_stable_key=item_key,
                    target_stable_key="quest:fixture",
                    kind="quest_requirement",
                    variant_key=variant,
                    material_slot=material_slot,
                    quantity_min=material_slot,
                    quantity_max=material_slot,
                    quantity_kind="exact",
                ),
            )
    rows = {row["quest_name"]: row for row in _rows(writer, "quests")}
    assert rows["quest-resource:1"]["reward_item"] == "Bread"
    assert rows["quest-resource:2"]["reward_item"] == "Other Bread"
    assert rows["quest-resource:1"]["required_items"] == "Bread, Bread"
    assert rows["quest-resource:2"]["required_items"] == "Other Bread, Other Bread"


def test_vendor_unlock_summary_uses_typed_canonical_conditions(writer: Writer) -> None:
    _insert(writer, "items", {"stable_key": "item:bread", "display_name": "Bread", "image_name": "Bread"})
    _insert(writer, "quests", {"stable_key": "quest:fixture", "display_name": "Quest", "image_name": "Quest"})
    _insert(
        writer,
        "quest_variants",
        {
            "resource_name": "quest-resource:fixture",
            "quest_stable_key": "quest:fixture",
            "quest_name": "Quest",
        },
    )
    _insert_fact(
        writer,
        _acquisition(
            "vendor:locked",
            "vendor",
            conditions=(
                _condition(
                    gate_key="stock_unlock",
                    predicate="quest_done",
                    reference_stable_key="quest:fixture",
                ),
            ),
        ),
    )
    rows = _rows(writer, "quests")
    assert len(rows) == 1
    assert rows[0]["unlock_item_for_vendor"] == "Bread"


def test_sheet_formatter_rejects_an_absent_provenance_table(writer: Writer, tmp_path: Path) -> None:
    writer.conn.execute("DROP TABLE item_provenance_meta")
    writer.conn.commit()
    engine = create_engine(f"sqlite:///{tmp_path / 'clean.sqlite'}")
    try:
        with pytest.raises(RepositoryError, match="Unsupported item provenance schema"):
            formatter = SheetsFormatter(engine, QUERIES_DIR, map_base_url="https://maps.example.invalid")
            formatter.format_sheet("item-acquisitions")
    finally:
        engine.dispose()


@pytest.mark.parametrize("family", ["acquisition", "use"])
def test_offline_coverage_rejects_a_lost_location_source_copy(
    writer: Writer,
    canonical_facts: tuple[list[ItemAcquisition], list[ItemUse], list[ItemDisposition]],
    family: str,
) -> None:
    projected = _projected_contract(writer)
    fact = next(row for row in projected[family] if row["locations"][0]["source_copy_stable_key"] is not None)
    fact["locations"][0].pop("source_copy_stable_key")
    with pytest.raises(AssertionError, match=f"Lost {family}"):
        _assert_coverage(projected, canonical_facts)


def test_drop_sheet_retains_pool_roll_count_without_guaranteeing_the_item(writer: Writer) -> None:
    _insert(writer, "items", {"stable_key": "item:bread", "display_name": "Bread", "image_name": "Bread"})
    _insert_fact(
        writer,
        _acquisition(
            "drop:pool",
            "character_drop",
            probability_min=25.0,
            probability_max=25.0,
            guarantee_scope="pool_roll",
            guaranteed_roll_count=2,
        ),
    )
    rows = _rows(writer, "drop-chances")
    assert len(rows) == 1
    assert rows[0]["Drop Chance (%)"] == 25.0
    assert rows[0]["guarantee_scope"] == "pool_roll"
    assert rows[0]["guaranteed_roll_count"] == 2
