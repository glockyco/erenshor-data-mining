from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from erenshor.application.processor.item_provenance import ProvenanceBuilder
from erenshor.application.processor.quest_routes import process_quest_routes
from erenshor.application.processor.writer import Writer


@pytest.fixture
def writer(tmp_path: Path) -> Iterator[Writer]:
    writer = Writer(tmp_path / "routes.sqlite")
    writer.create_schema()
    writer.insert_quests(
        [
            {"stable_key": key, "display_name": key, "image_name": key}
            for key in ("quest:q", "quest:other", "quest:required")
        ]
    )
    writer.insert_characters(
        [
            {
                "stable_key": "character:copy",
                "display_name": "Copy",
                "image_name": "Copy",
                "encounter_tier": "npc",
                "level_scales_with_player": 0,
            }
        ]
    )
    writer.insert_character_deduplications(
        [{"group_key": "character:group", "member_stable_key": "character:copy", "is_wiki_generated": 1}]
    )
    variant(writer)
    yield writer
    writer.conn.close()


def variant(writer: Writer, resource: str = "Resource", **changes: object) -> None:
    writer.insert_quest_variants(
        [
            {
                "resource_name": resource,
                "quest_stable_key": "quest:q",
                "repeatable": 0,
                "assign_this_quest_on_partial_complete": 1,
                "dialog_on_partial_success": "More",
            }
            | changes
        ]
    )


def source(
    writer: Writer,
    method: str,
    kind: str,
    phase: str = "completion",
    key: str | None = None,
    quest: str = "quest:q",
    note: str | None = None,
) -> None:
    key = (
        key
        if key is not None
        else {
            "character": "character:copy",
            "quest": "quest:other",
            "item": "item:read",
            "zone": "zone:here",
            "scripted": None,
        }.get(kind)
    )
    table = "quest_acquisition_sources" if phase == "start" else "quest_completion_sources"
    writer.conn.execute(f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?)", (quest, method, kind, key, note))


def manager(writer: Writer, quest: str = "quest:q", resource: str = "Resource", slot: int = 0) -> None:
    writer.conn.execute(
        "INSERT INTO character_quest_manager_quests VALUES (?, ?, ?, ?)", ("character:copy", quest, slot, resource)
    )


def routes(writer: Writer) -> list[dict[str, object]]:
    process_quest_routes(writer.conn)
    cursor = writer.conn.execute("SELECT * FROM quest_routes ORDER BY route_key")
    return [dict(zip([column[0] for column in cursor.description], row, strict=True)) for row in cursor]


@pytest.mark.parametrize(
    ("phase", "method", "kind"),
    [
        ("start", "dialog", "character"),
        ("start", "quest_chain", "quest"),
        ("start", "item_read", "item"),
        ("start", "zone_entry", "zone"),
        ("start", "partial_turnin", "character"),
        ("start", "scripted", "scripted"),
        ("completion", "item_turnin", "character"),
        ("completion", "talk", "character"),
        ("completion", "zone", "zone"),
        ("completion", "read", "item"),
        ("completion", "death", "character"),
        ("completion", "chain", "quest"),
        ("completion", "scripted", "scripted"),
        ("completion", "shout", "character"),
    ],
)
def test_every_native_method(writer: Writer, phase: str, method: str, kind: str) -> None:
    source(writer, method, kind, phase, note="Native script.cs" if kind == "scripted" else None)
    if method == "item_turnin":
        manager(writer)
    if method == "partial_turnin":
        writer.conn.execute("INSERT INTO quest_required_items VALUES ('Resource', 0, 'item:required', 2)")
    if method == "chain":
        source(writer, "item_turnin", "character", quest="quest:other")
        manager(writer, "quest:other")
    row = next(row for row in routes(writer) if row["method"] == method)
    assert row["phase"] == phase
    assert row["source_kind"] == kind
    assert row["grants_resource_rewards"] == int(method == "item_turnin")
    if kind == "character":
        assert row["source_stable_key"] == "character:copy"
        assert row["source_group_key"] == "character:group"
    if kind == "scripted":
        assert row["source_stable_key"] is None
        assert row["note"] == "Native script.cs"


@pytest.mark.parametrize(
    ("quantity", "assign", "dialog", "expected"),
    [
        (0, 1, "More", 0),
        (1, 1, "More", 0),
        (2, 0, "More", 0),
        (2, 1, "", 0),
        (2, 1, "More", 1),
    ],
)
def test_partial_turnin_requires_executable_subset(
    writer: Writer, quantity: int, assign: int, dialog: str, expected: int
) -> None:
    source(writer, "partial_turnin", "character", "start")
    writer.conn.execute(
        "UPDATE quest_variants SET assign_this_quest_on_partial_complete=?, dialog_on_partial_success=?",
        (assign, dialog),
    )
    writer.conn.execute("INSERT INTO quest_required_items VALUES ('Resource', 0, 'item:required', ?)", (quantity,))
    assert len(routes(writer)) == expected


def test_chain_completions_require_trade_execution(writer: Writer) -> None:
    source(writer, "chain", "quest")
    source(writer, "talk", "character", quest="quest:other")
    assert [row["method"] for row in routes(writer)] == ["talk"]


def test_chain_start_keeps_each_assigning_resource(writer: Writer) -> None:
    source(writer, "quest_chain", "quest", "start", key="quest:q", quest="quest:other")
    writer.conn.execute("UPDATE quest_variants SET assign_new_quest_on_complete_stable_key='quest:other'")
    variant(writer, "Second", assign_new_quest_on_complete_stable_key="quest:other")
    assert {row["variant_resource_name"] for row in routes(writer)} == {"Resource", "Second"}


def add_dialog(writer: Writer, repeatable: int = 0) -> None:
    source(writer, "dialog", "character", "start")
    source(writer, "talk", "character")
    writer.conn.execute("UPDATE quest_variants SET repeatable=?", (repeatable,))
    writer.conn.execute(
        "INSERT INTO character_dialogs (character_stable_key, dialog_index, keywords, "
        "assign_quest_stable_key, complete_quest_stable_key, required_quest_stable_key, "
        "give_item_stable_key) VALUES ('character:copy', 4, 'they', 'quest:q', 'quest:q', "
        "'quest:required', 'item:gift')"
    )


def test_dialog_conditions_stay_on_exact_dialog_not_placement(writer: Writer) -> None:
    add_dialog(writer)
    result = routes(writer)
    assert len(result) == 2
    assert all(row["dialog_index"] == 4 and row["keywords"] == "they" for row in result)
    atoms = writer.conn.execute("SELECT atom_kind, atom_stable_key FROM quest_route_conditions").fetchall()
    assert sorted(tuple(atom) for atom in atoms) == sorted(
        [("quest_done", "quest:required"), ("quest_not_done", "quest:q"), ("item_not_owned", "item:gift")] * 2
    )
    assert all(row["grants_resource_rewards"] == 0 for row in result)


def test_repeatable_dialog_does_not_block_done_quest(writer: Writer) -> None:
    add_dialog(writer, repeatable=1)
    routes(writer)
    assert (
        writer.conn.execute("SELECT COUNT(*) FROM quest_route_conditions WHERE atom_kind='quest_not_done'").fetchone()[
            0
        ]
        == 0
    )


def test_turnin_keeps_all_variants_and_ignores_disable_quest(writer: Writer) -> None:
    source(writer, "item_turnin", "character")
    variant(writer, "Second", disable_quest=1)
    manager(writer)
    manager(writer, resource="Second", slot=1)
    result = routes(writer)
    assert {row["variant_resource_name"] for row in result} == {"Resource", "Second"}
    assert all(row["grants_resource_rewards"] == 1 for row in result)


@pytest.mark.parametrize(
    ("phase", "method", "kind", "message"),
    [
        ("start", "future", "character", "method 'future'"),
        ("completion", "future", "character", "method 'future'"),
        ("start", "dialog", "future", "source kind 'future'"),
        ("completion", "talk", "item", "source kind 'item'"),
    ],
)
def test_unmapped_sources_fail_with_quest(writer: Writer, phase: str, method: str, kind: str, message: str) -> None:
    source(writer, method, kind, phase)
    with pytest.raises(ValueError, match=f"Quest quest:q:.*{message}"):
        routes(writer)


def test_ambiguous_dialog_assignment_fails(writer: Writer) -> None:
    add_dialog(writer)
    variant(writer, "Second", repeatable=1)
    with pytest.raises(ValueError, match=r"Quest quest:q:.*assignment condition"):
        routes(writer)


def test_missing_turnin_variant_fails(writer: Writer) -> None:
    source(writer, "item_turnin", "character")
    with pytest.raises(ValueError, match=r"Quest quest:q:.*no resource variant"):
        routes(writer)


def test_unknown_canonical_dialog_condition_fails(writer: Writer) -> None:
    add_dialog(writer)
    writer.conn.execute("INSERT INTO items (stable_key, display_name, image_name) VALUES ('item:gift', 'Gift', 'Gift')")
    writer.conn.execute("INSERT INTO character_spawns (character_stable_key) VALUES ('character:copy')")
    builder = ProvenanceBuilder(writer.conn)
    builder.vendors_and_dialog()
    builder.persist()
    writer.conn.execute("UPDATE item_acquisition_conditions SET predicate='future' WHERE gate_key='not_owned'")
    with pytest.raises(ValueError, match="Quest quest:q: unmapped condition not_owned:future"):
        routes(writer)


def test_route_identity_and_output_do_not_depend_on_input_order(writer: Writer) -> None:
    source(writer, "read", "item")
    source(writer, "zone", "zone")
    first = routes(writer)
    writer.conn.execute("DELETE FROM quest_routes")
    writer.conn.execute(
        "INSERT INTO quest_completion_sources SELECT * FROM quest_completion_sources ORDER BY method DESC"
    )
    assert routes(writer) == first


@pytest.mark.parametrize("kind", ["dialog", "quest_reward"])
@pytest.mark.parametrize("exact", [True, False])
def test_canonical_item_grants_keep_route_without_resource_reward_leakage(
    writer: Writer, kind: str, exact: bool
) -> None:
    writer.conn.execute("INSERT INTO items (stable_key, display_name, image_name) VALUES ('item:gift', 'Gift', 'Gift')")
    writer.conn.execute("INSERT INTO character_spawns (character_stable_key) VALUES ('character:copy')")
    if kind == "dialog":
        add_dialog(writer)
        builder = ProvenanceBuilder(writer.conn)
        builder.vendors_and_dialog()
    else:
        source(writer, "item_turnin", "character")
        manager(writer)
        writer.conn.execute("UPDATE quest_variants SET item_on_complete_stable_key='item:gift'")
        builder = ProvenanceBuilder(writer.conn)
        builder.quests()
    builder.persist()
    assert writer.conn.execute("SELECT COUNT(*) FROM item_acquisitions").fetchone()[0] == 1
    if not exact:
        writer.conn.execute("UPDATE item_acquisitions SET quantity_max=2")
        with pytest.raises(ValueError, match=r"Quest quest:q:.*has no exact quantity"):
            routes(writer)
    else:
        result = routes(writer)
        assert all(row["grants_resource_rewards"] == int(kind == "quest_reward") for row in result)
        assert len(result) == (2 if kind == "dialog" else 1)


def test_conflicting_native_route_notes_fail_instead_of_overwriting(writer: Writer) -> None:
    source(writer, "scripted", "scripted", note="First.cs")
    source(writer, "scripted", "scripted", note="Second.cs")
    with pytest.raises(ValueError, match=r"Quest quest:q: conflicting route"):
        routes(writer)


def test_source_furniture_is_not_a_route_condition(writer: Writer) -> None:
    add_dialog(writer)
    writer.conn.execute("INSERT INTO items (stable_key, display_name, image_name) VALUES ('item:seed', 'Seed', 'Seed')")
    writer.conn.execute(
        "INSERT INTO character_spawns (character_stable_key, furniture_item_stable_key, furniture_slot) "
        "VALUES ('character:copy', 'item:seed', 'Room1')"
    )
    result = routes(writer)
    assert len(result) == 2
    assert (
        writer.conn.execute("SELECT COUNT(*) FROM quest_route_conditions WHERE atom_stable_key='item:seed'").fetchone()[
            0
        ]
        == 0
    )


@pytest.mark.parametrize("placed", [True, False])
def test_character_sources_share_the_encountered_copy_boundary(writer: Writer, placed: bool) -> None:
    writer.conn.execute("UPDATE character_deduplications SET is_wiki_generated=0")
    source(writer, "dialog", "character", "start")
    source(writer, "item_turnin", "character")
    manager(writer)
    if placed:
        writer.conn.execute("INSERT INTO character_spawns (character_stable_key) VALUES ('character:copy')")
    assert len(routes(writer)) == (2 if placed else 0)
