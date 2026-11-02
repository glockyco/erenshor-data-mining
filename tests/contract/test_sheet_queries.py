"""Exercise Sheets against the public item view without game data or live writes."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine

import erenshor.application.sheets as sheets_package
from erenshor.application.processor.writer import Writer
from erenshor.application.sheets.formatter import SheetsFormatter
from erenshor.domain.value_objects.item_provenance import PROVENANCE_SCHEMA_VERSION
from erenshor.infrastructure.database.repository import RepositoryError

QUERIES_DIR = Path(sheets_package.__file__).parent / "queries"
SOURCE_KINDS = (
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
    "auction_house",
    "item_bag",
    "starting_class",
    "ui_grant",
    "item_conversion",
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


def _item(writer: Writer, key: str = "item:bread", name: str = "Bread", status: str = "current") -> None:
    _insert(writer, "items", {"stable_key": key, "display_name": name, "image_name": name})
    _insert(
        writer,
        "item_statuses",
        {
            "item_stable_key": key,
            "disposition": status,
            "current_pages": "[]",
            "former_pages": "[]",
        },
    )


def _source(writer: Writer, key: str, kind: str = "character_drop", **values: Any) -> dict[str, Any]:
    row = {
        "source_key": key,
        "item_stable_key": "item:bread",
        "kind": kind,
        "source_stable_key": None,
        "source_group_key": None,
        "source_copy_stable_key": None,
        "variant_key": None,
        "mechanic": None,
        "probability_kind": "exact",
        "probability_min": 12.345678901,
        "probability_max": 12.345678901,
        "probability_basis": "per_kill",
        "quantity_kind": "exact",
        "quantity_min": 1.0,
        "quantity_max": 1.0,
        "expected_quantity": 0.123456789,
        "guaranteed": 0,
        "place_set_key": None,
        **values,
    }
    _insert(writer, "item_sources", row)
    return row


def _use(writer: Writer, key: str, kind: str, **values: Any) -> None:
    _insert(
        writer,
        "item_usages",
        {
            "use_key": key,
            "kind": kind,
            "item_stable_key": "item:bread",
            "quantity_kind": "exact",
            "quantity_min": 1,
            "quantity_max": 1,
            **values,
        },
    )


def _condition(writer: Writer, owner: str, **values: Any) -> None:
    _insert(
        writer,
        "item_conditions",
        {
            "owner_key": owner,
            "gate_index": 0,
            "alternative_index": 0,
            "atom_index": 0,
            "gate_key": "gate:fixture",
            "predicate": "quest_done",
            "reference_stable_key": "quest:fixture",
            "minimum_inclusive": 1,
            "maximum_inclusive": 1,
            "phase": "availability",
            **values,
        },
    )


def _place(writer: Writer, key: str = "place:fixture", **values: Any) -> None:
    _insert(
        writer,
        "item_places",
        {
            "place_set_key": "places:fixture",
            "place_key": key,
            "relation": "fixed",
            "zone_stable_key": "zone:fixture",
            "marker_stable_key": "point:fixture",
            "x": 1.123456789,
            "y": 2.5,
            "z": 3.75,
            **values,
        },
    )


def _character(writer: Writer, key: str, name: str) -> None:
    _insert(
        writer,
        "characters",
        {
            "stable_key": key,
            "display_name": name,
            "image_name": name,
            "encounter_tier": "npc",
            "level_scales_with_player": 0,
        },
    )


def _quest(writer: Writer) -> None:
    _insert(writer, "quests", {"stable_key": "quest:fixture", "display_name": "Quest", "image_name": "Quest"})


def test_every_sheet_query_runs_without_complete_tables(writer: Writer, tmp_path: Path) -> None:
    writer.conn.commit()
    engine = create_engine(f"sqlite:///{tmp_path / 'clean.sqlite'}")
    try:
        formatter = SheetsFormatter(engine, QUERIES_DIR, map_base_url="https://maps.example.invalid")
        sheets = formatter.format_all_sheets()
        assert set(sheets) == {path.stem for path in QUERIES_DIR.glob("*.sql")}
        assert all(rows and rows[0] for rows in sheets.values())
        assert "item-sources" in sheets
        assert (
            not {"item-acquisitions", "item-conditions", "item-dispositions", "item-locations", "item-uses"}
            & sheets.keys()
        )
    finally:
        engine.dispose()


def test_sources_have_one_row_per_public_source_and_preserve_numeric_fields(writer: Writer) -> None:
    _item(writer)
    _item(writer, "item:bread-copy", "Bread")
    expected = [_source(writer, f"source:{kind}", kind) for kind in SOURCE_KINDS]
    expected.append(_source(writer, "source:copy", item_stable_key="item:bread-copy"))
    _place(writer)
    _place(writer, "place:second", x=5)
    writer.conn.execute("UPDATE item_sources SET place_set_key = 'places:fixture'")
    rows = _rows(writer, "item-sources")
    assert len(rows) == len(expected)
    assert {row["source_key"] for row in rows} == {row["source_key"] for row in expected}
    labels = {row["source_key"]: row["Kind"] for row in rows}
    assert labels["source:character_drop"] == "Dropped by"
    assert labels["source:vendor"] == "Sold by"
    assert labels["source:ui_grant"] == "Available from"
    assert {row["item_stable_key"] for row in rows} == {"item:bread", "item:bread-copy"}
    for row in rows:
        assert row["probability_min"] == 12.345678901
        assert row["expected_quantity"] == 0.123456789
        assert [float(value) for value in re.findall(r"\d+(?:\.\d+)?", row["Quantity"])] == [1.0, 0.123]
        assert list(row)[:7] == ["Item", "Kind", "Source", "Chance", "Quantity", "Conditions", "Zones"]
        assert not {"player_access_state", "probability_stage", "count_distribution", "guarantee_scope"} & row.keys()


def test_conditions_preserve_gates_alternatives_atoms_and_phases_without_filtering(writer: Writer) -> None:
    _item(writer)
    _quest(writer)
    _source(writer, "conditional")
    _condition(writer, "conditional")
    _condition(writer, "conditional", atom_index=1, predicate="item_held", reference_stable_key="item:bread", minimum=1)
    _condition(writer, "conditional", alternative_index=1, predicate="quest_not_done")
    _condition(
        writer,
        "conditional",
        gate_index=1,
        predicate="actor_level",
        reference_stable_key=None,
        actor="player",
        minimum=10,
        maximum=20,
        minimum_inclusive=0,
        phase="operation_input",
    )
    # A consumer must word even a phase the build would ordinarily omit, not reapply that rule.
    _condition(
        writer,
        "conditional",
        gate_index=2,
        predicate="item_not_owned",
        reference_stable_key="item:bread",
        phase="source_initialization",
    )
    row = _rows(writer, "item-sources")[0]
    # Atoms join within a branch, branches of one gate read as "or", and every gate holds.
    assert re.search(r"\(\(.*Quest and .*Bread\) or .*Quest\)", row["Conditions"])
    assert re.search(r"\b10\b.*\b20\b", row["Conditions"])
    assert row["Conditions"].count("Bread") == 1


def test_zones_keep_place_conditions_level_ranges_and_unlocated_sources(writer: Writer) -> None:
    _item(writer)
    _quest(writer)
    _insert(
        writer,
        "zones",
        {
            "stable_key": "zone:fixture",
            "zone_name": "Zone",
            "display_name": "Zone",
            "image_name": "Zone",
            "zone_type": "Outdoor",
        },
    )
    _source(writer, "located", place_set_key="places:fixture")
    _source(writer, "unlocated")
    _place(writer, player_level_min=10, player_level_max=20)
    _place(writer, "place:other", zone_stable_key=None, scene="Other scene")
    _insert(
        writer,
        "item_place_conditions",
        {
            "place_set_key": "places:fixture",
            "place_key": "place:fixture",
            "gate_index": 0,
            "alternative_index": 0,
            "atom_index": 0,
            "gate_key": "entry",
            "predicate": "quest_done",
            "reference_stable_key": "quest:fixture",
            "minimum_inclusive": 1,
            "maximum_inclusive": 1,
            "phase": "availability",
        },
    )
    rows = {row["source_key"]: row for row in _rows(writer, "item-sources")}
    zones = rows["located"]["Zones"]
    assert re.fullmatch(r"Other scene; Zone \([^()]*Quest[^()]*10.*20\)", zones)
    assert rows["unlocated"]["Zones"] is None
    assert rows["located"]["Conditions"] is None


def test_global_fishing_is_one_any_water_source_without_invented_places(writer: Writer) -> None:
    _item(writer)
    _source(
        writer, "global", "fishing", mechanic="fishing_global_replacement", probability_basis="per_successful_catch"
    )
    row = _rows(writer, "item-sources")[0]
    assert row["Source"] == row["Zones"] == "Any water"
    assert row["Conditions"] is None
    fishing = _rows(writer, "fishing")
    assert len(fishing) == 1
    assert fishing[0]["position_x"] is None


def test_drop_sheet_lists_contributors_without_claiming_explicit_drops(writer: Writer) -> None:
    _item(writer)
    _character(writer, "character:copy", "Contributor")
    _source(
        writer,
        "world",
        "common_world_item",
        probability_kind="bounded",
        probability_min=0.123456789,
        probability_max=0.987654321,
    )
    _insert(writer, "item_source_contributors", {"source_key": "world", "character_stable_key": "character:copy"})
    row = _rows(writer, "drop-chances")[0]
    assert row["Source"] == "Common world item"
    assert row["Drop Chance (%)"] is None
    assert row["contributors"] == "Contributor"
    assert row["source_copy_stable_key"] is None
    assert _rows(writer, "item-sources")[0]["contributors"] == "Contributor"


@pytest.mark.parametrize("sheet,kind", [("fishing", "fishing"), ("mining-nodes", "mining"), ("item-bags", "item_bag")])
def test_located_sheets_keep_public_sources_and_marker_links(writer: Writer, sheet: str, kind: str) -> None:
    _item(writer)
    _source(writer, "unlocated", kind)
    _source(writer, "located", kind, place_set_key="places:fixture")
    _place(writer)
    rows = {row["source_key"]: row for row in _rows(writer, sheet)}
    assert set(rows) == {"unlocated", "located"}
    assert rows["located"]["position_x"] == 1.123456789
    assert rows["unlocated"]["position_x"] is None
    if sheet == "item-bags":
        assert rows["unlocated"]["MapLink"] is None
        assert rows["located"]["MapLink"].endswith("marker:point:fixture")


def test_item_summaries_keep_status_recipe_slots_and_public_auction_routes(writer: Writer) -> None:
    _item(writer)
    _item(writer, "item:recipe", "Recipe", "unused")
    for slot in (1, 2):
        _source(
            writer,
            f"reward:{slot}",
            "crafting",
            source_stable_key="item:recipe",
            variant_key=str(slot),
            quantity_min=slot,
            quantity_max=slot,
        )
        _use(writer, f"material:{slot}", "crafting_material", target_stable_key="item:recipe", material_slot=slot)
    _source(writer, "auction", "auction_house")
    rows = {row["stable_key"]: row for row in _rows(writer, "items")}
    assert rows["item:recipe"]["template_ingredient_stable_keys"] == "item:bread, item:bread"
    assert rows["item:recipe"]["template_reward_stable_key"] == "item:bread, item:bread"
    assert rows["item:bread"]["can_be_listed_by_sims"] == 1
    assert rows["item:recipe"]["can_be_listed_by_sims"] == 0
    assert rows["item:bread"]["status"] == "current"
    assert rows["item:recipe"]["status"] == "unused"


def test_character_vendor_summary_uses_public_copy(writer: Writer) -> None:
    _item(writer)
    _character(writer, "character:copy", "Actual copy")
    _character(writer, "character:representative", "Representative")
    _source(
        writer,
        "vendor",
        "vendor",
        source_stable_key="character:representative",
        source_copy_stable_key="character:copy",
    )
    rows = {row["stable_key"]: row for row in _rows(writer, "characters")}
    assert rows["character:copy"]["vendor_item_stable_keys"] == "item:bread"
    assert rows["character:representative"]["vendor_item_stable_keys"] is None


def test_quest_summaries_keep_variant_rewards_requirements_and_unlocks(writer: Writer) -> None:
    _quest(writer)
    for slot, name in enumerate(("Bread", "Other Bread"), start=1):
        key = f"item:bread:{slot}"
        _item(writer, key, name)
        variant = f"quest-resource:{slot}"
        _insert(
            writer,
            "quest_variants",
            {"resource_name": variant, "quest_stable_key": "quest:fixture", "quest_name": variant},
        )
        _source(
            writer,
            f"quest-reward:{slot}",
            "quest_reward",
            item_stable_key=key,
            source_stable_key="quest:fixture",
            variant_key=variant,
        )
        for material_slot in (1, 2):
            _use(
                writer,
                f"quest-required:{slot}:{material_slot}",
                "quest_requirement",
                item_stable_key=key,
                target_stable_key="quest:fixture",
                variant_key=variant,
                material_slot=material_slot,
            )
    _source(writer, "vendor:locked", "vendor", item_stable_key="item:bread:1")
    _condition(writer, "vendor:locked", gate_key="stock_unlock")
    rows = {row["quest_name"]: row for row in _rows(writer, "quests")}
    assert rows["quest-resource:1"]["reward_item"] == "Bread"
    assert rows["quest-resource:2"]["reward_item"] == "Other Bread"
    assert rows["quest-resource:1"]["required_items"] == "Bread, Bread"
    assert rows["quest-resource:2"]["required_items"] == "Other Bread, Other Bread"
    assert all(row["unlock_item_for_vendor"] == "Bread" for row in rows.values())


def test_sheet_formatter_preserves_numeric_and_unknown_values(writer: Writer, tmp_path: Path) -> None:
    _item(writer)
    _source(writer, "exact")
    _source(
        writer,
        "unknown",
        probability_kind="unknown",
        probability_min=None,
        probability_max=None,
        quantity_kind="unknown",
        quantity_min=None,
        quantity_max=None,
        expected_quantity=None,
    )
    writer.conn.commit()
    engine = create_engine(f"sqlite:///{tmp_path / 'clean.sqlite'}")
    try:
        formatter = SheetsFormatter(engine, QUERIES_DIR, map_base_url="https://maps.example.invalid")
        headers, *values = formatter.format_sheet("item-sources")
        rows = {row["source_key"]: row for row in (dict(zip(headers, cells, strict=True)) for cells in values)}
        assert rows["exact"]["probability_min"] == 12.345678901
        assert rows["unknown"]["probability_min"] == ""
        assert rows["unknown"]["quantity_min"] == ""
        assert rows["unknown"]["Chance"] == "Chance unknown per kill"
        assert rows["unknown"]["Quantity"] == "Quantity unknown"
    finally:
        engine.dispose()


@pytest.mark.parametrize("versions", [[], [0], [PROVENANCE_SCHEMA_VERSION + 1], [PROVENANCE_SCHEMA_VERSION] * 2, None])
def test_sheet_formatter_rejects_missing_or_incompatible_metadata(
    writer: Writer,
    tmp_path: Path,
    versions: list[int] | None,
) -> None:
    if versions is None:
        writer.conn.execute("DROP TABLE item_provenance_meta")
    else:
        writer.conn.execute("DELETE FROM item_provenance_meta")
        writer.conn.executemany(
            "INSERT INTO item_provenance_meta VALUES (?, 'fixture-build', '{}')", [(v,) for v in versions]
        )
    writer.conn.commit()
    engine = create_engine(f"sqlite:///{tmp_path / 'clean.sqlite'}")
    try:
        with pytest.raises(RepositoryError, match="Unsupported item provenance schema"):
            SheetsFormatter(engine, QUERIES_DIR, map_base_url="https://maps.example.invalid").format_sheet(
                "item-sources"
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "predicate,values,named",
    [
        ("key_held", {"reference_stable_key": "item:bread"}, "Bread"),
        ("room_furnished", {"reference_stable_key": "item:bread", "reference_slot": "L1"}, "L1"),
        ("encounter_won", {"reference_stable_key": "character:copy"}, "Actual copy"),
        ("actor_class", {"reference_stable_key": "class:arcanist", "actor": "player"}, "Arcanist"),
        ("account_state", {"reference_stable_key": "account_state:reliquary_claimed", "value": "false"}, "Reliquary"),
        ("time_of_day", {"value": "night"}, "night"),
        ("zone_use", {"reference_stable_key": "zone:missing"}, "missing"),
        ("quality", {"minimum": 2, "maximum": 3, "maximum_inclusive": 0}, "Blessed"),
        ("route", {"value": "normal_pointer_inventory_transfer", "reference_stable_key": None}, "inventory"),
        ("never", {}, "Never"),
    ],
)
def test_stored_condition_predicates_are_worded_without_being_omitted(
    writer: Writer,
    predicate: str,
    values: dict[str, Any],
    named: str,
) -> None:
    _item(writer)
    _character(writer, "character:copy", "Actual copy")
    _insert(writer, "classes", {"class_name": "Arcanist", "display_name": "Arcanist"})
    _source(writer, "conditional")
    _condition(writer, "conditional", predicate=predicate, **values)
    conditions = _rows(writer, "item-sources")[0]["Conditions"]
    assert named in conditions
    # Players read names, not stored keys or internal labels.
    assert ":" not in conditions and "_" not in conditions


def test_source_chance_quantity_and_names_use_public_values(writer: Writer) -> None:
    _item(writer)
    _item(writer, "item:recipe", "Recipe")
    _source(
        writer,
        "bounded",
        "crafting",
        source_stable_key="item:recipe",
        probability_kind="bounded",
        probability_min=10,
        probability_max=20,
        probability_basis="per_use",
        quantity_kind="bounded",
        quantity_min=1,
        quantity_max=3,
        expected_quantity=2,
        guaranteed=1,
    )
    row = _rows(writer, "item-sources")[0]
    assert row["Source"] == "Recipe"
    assert row["Chance"] == "10% to 20% per use"
    assert row["Quantity"] == "Quantity 1 to 3, Average 2, Guaranteed"


@pytest.mark.parametrize(
    "kind,mechanic,expected",
    [
        ("common_world_item", None, "Any enemy with common drops"),
        ("special_world_drop", None, "Any enemy"),
        ("auction_house", None, "Auction House"),
        ("ui_grant", "cosmetic_panel", "Cosmetic panel"),
        ("ui_grant", "planning_table", "Planning table"),
        ("mining", None, "Mining node"),
        ("fishing", None, "Fishable water"),
        ("item_bag", None, "Ground item"),
        ("fishing", "fishing_global_replacement", "Any water"),
    ],
)
def test_source_names_reuse_map_names_instead_of_stable_keys(
    writer: Writer,
    kind: str,
    mechanic: str | None,
    expected: str,
) -> None:
    _item(writer)
    _source(writer, "named", kind, mechanic=mechanic, source_stable_key="source:raw-stable-key")
    assert _rows(writer, "item-sources")[0]["Source"] == expected


def test_source_name_uses_character_copy_and_kind_falls_back_to_words(writer: Writer) -> None:
    _item(writer)
    _character(writer, "character:copy", "Actual copy")
    _source(writer, "copy", "new_kind", source_stable_key="character:missing", source_copy_stable_key="character:copy")
    row = _rows(writer, "item-sources")[0]
    assert row["Source"] == "Actual copy"
    assert row["Kind"] == "new kind"


@pytest.mark.parametrize(
    "probability,expected",
    [(5.5882352941176468, "5.59%"), (1.25, "1.25%"), (1.2, "1.2%"), (100.0, "100%"), (0.0, "0%")],
)
def test_readable_numbers_drop_float_noise_without_changing_numeric_columns(
    writer: Writer,
    probability: float,
    expected: str,
) -> None:
    _item(writer)
    _source(writer, "rounded", probability_min=probability, probability_max=probability, expected_quantity=None)
    _condition(
        writer, "rounded", predicate="actor_level", reference_stable_key=None, actor="player", minimum=1, maximum=5
    )
    row = _rows(writer, "item-sources")[0]
    assert row["Chance"] == f"{expected} per kill"
    assert row["Quantity"] == "Quantity 1"
    assert re.search(r"\b1\b.*\b5\b", row["Conditions"]) and ".0" not in row["Conditions"]
    assert row["probability_min"] == probability
    assert row["probability_max"] == probability
    assert row["quantity_min"] == 1.0
