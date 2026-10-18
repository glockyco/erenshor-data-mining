from __future__ import annotations

import sqlite3
from dataclasses import asdict
from typing import TYPE_CHECKING

import pytest

from erenshor.application.processor.gates import _select_planning_portals, process_gates
from erenshor.application.processor.writer import Writer
from erenshor.domain.value_objects.item_provenance import ProvenanceCondition, condition_from_dict

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_PORTALS = (
    ("FernPort", "PlanarFern", "134379"),
    ("BraxPort", "PlanarBrax", "12094245"),
    ("VithPort", "PlanarVith", "96186750"),
    ("SolPort", "PlanarSol", "25900083"),
    ("Braxonian", None, "2096280"),
    ("Ripper", None, "2810120"),
    ("Silkengrass", None, "71979710"),
    ("Soluna", None, "5388624"),
    ("Hidden", None, "36740470"),
    ("Windwashed", None, "5016816"),
)
_RUNES = tuple(f"Rune{index}" for index in range(1, 7))


@pytest.fixture
def portal_pair(tmp_path: Path) -> Iterator[tuple[sqlite3.Connection, Writer]]:
    raw = sqlite3.connect(":memory:")
    raw.executescript("""
        CREATE TABLE ScriptedActivators (
            SourceKey TEXT, RuleId TEXT, ComponentIsEnabled INTEGER,
            IsEnabled INTEGER, HostCharacterStableKey TEXT, SourceScene TEXT, SourceObjectName TEXT, ObjectKey TEXT
        );
        CREATE TABLE ScriptedActivatorReferences (
            ReferenceId TEXT, SourceKey TEXT, Field TEXT, ReferenceKind TEXT, ReferenceKey TEXT, BoolValue INTEGER
        );
        CREATE TABLE ScriptedActivatorTargets (ReferenceId TEXT, ResolutionMode TEXT, Kind TEXT, Key TEXT);
        CREATE TABLE QuestActivationEffects (
            TargetKind TEXT, TargetStableKey TEXT, Effect TEXT, ListenerKey TEXT,
            GroupIndex INTEGER, AtomKind TEXT, AtomStableKey TEXT,
            TargetObjectKey TEXT, ListenerObjectKey TEXT, ListenerComponentIsEnabled INTEGER
        );
        CREATE TABLE ObjectHierarchy (
            ObjectKey TEXT PRIMARY KEY, ParentObjectKey TEXT, ActiveSelf INTEGER, IsSceneObject INTEGER
        );
        CREATE TABLE DynamicCharacterSpawns (
            Key TEXT, CharacterStableKey TEXT, ControllerObjectKey TEXT, ControllerComponentIsEnabled INTEGER
        );
        CREATE TABLE CharacterChainedSpawns (
            ParentStableKey TEXT, ChildStableKey TEXT, SourceScript TEXT,
            ControllerObjectKey TEXT, ControllerComponentIsEnabled INTEGER
        );
        CREATE TABLE PlanningTableFurnishings (
            ObjectKey TEXT, ControllerObjectKey TEXT, Slot TEXT, Furnishing TEXT
        );
        INSERT INTO ObjectHierarchy VALUES ('object:desk', NULL, 1, 1);
        INSERT INTO ObjectHierarchy VALUES ('object:table', 'object:desk', 1, 1);
        INSERT INTO ObjectHierarchy VALUES ('object:quest-listener', NULL, 1, 1);
        INSERT INTO ScriptedActivators VALUES (
            'table', 'planning_portals', 1, 0, NULL, 'Source', 'Table', 'object:table'
        );
    """)
    for table in (
        "Characters",
        "SpawnPoints",
        "SpawnPointTriggers",
        "ZoneLines",
        "ItemBags",
        "Doors",
        "UiItemAccessTargets",
    ):
        raw.execute(f"CREATE TABLE {table} (StableKey TEXT, ObjectKey TEXT, ComponentIsEnabled INTEGER)")
    raw.execute("ALTER TABLE SpawnPoints ADD COLUMN IsDirectlyPlaced INTEGER DEFAULT 0")
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    conn = writer.conn
    for index, (field, _slot, game_id) in enumerate(_PORTALS):
        item, line, zone = f"item:portal{index}", f"zoneline:{field}", f"zone:destination{index}"
        conn.execute(
            "INSERT INTO items (stable_key,id,display_name,image_name) VALUES (?,?,?,?)",
            (item, game_id, field, field),
        )
        conn.execute(
            "INSERT INTO zones (stable_key,scene_name,zone_name,display_name,image_name,zone_type)"
            " VALUES (?,?,?,?,?,?)",
            (zone, f"Destination{index}", field, field, field, "Outdoor"),
        )
        conn.execute(
            "INSERT INTO zone_lines (stable_key,scene,x,y,z,destination_zone_stable_key,is_enabled)"
            " VALUES (?, 'Source', ?, 0, 0, ?, 0)",
            (line, index, zone),
        )
        raw.execute(
            "INSERT INTO ScriptedActivatorReferences VALUES (?, 'table', ?, 'object', ?, NULL)",
            (field, field, f"object:{field}"),
        )
        raw.executemany(
            "INSERT INTO ScriptedActivatorTargets VALUES (?, 'enable', ?, ?)",
            [(field, "object", f"object:{field}"), (field, "zone_line", line)],
        )
        raw.execute("INSERT INTO ObjectHierarchy VALUES (?, NULL, 0, 1)", (f"object:{field}",))
        raw.execute("INSERT INTO ObjectHierarchy VALUES (?, ?, 1, 1)", (f"object:{line}", f"object:{field}"))
        raw.execute("INSERT INTO ZoneLines VALUES (?, ?, 1)", (line, f"object:{line}"))
    conn.execute(
        "INSERT INTO zone_lines (stable_key,scene,x,y,z,destination_zone_stable_key,is_enabled)"
        " VALUES ('zoneline:unrelated', 'Source', 99, 0, 0, 'zone:destination0', 1)"
    )
    raw.execute("INSERT INTO ObjectHierarchy VALUES ('object:unrelated', NULL, 1, 1)")
    raw.execute("INSERT INTO ZoneLines VALUES ('zoneline:unrelated', 'object:unrelated', 1)")
    yield raw, writer
    raw.close()
    conn.close()


def test_ten_routes_and_forty_roles_share_exact_selection(portal_pair, tmp_path):
    raw, writer = portal_pair
    barriers = tmp_path / "barriers.toml"
    barriers.write_text("")
    raw.execute(
        "INSERT INTO QuestActivationEffects VALUES"
        " ('zone_line', 'zoneline:FernPort', 'enable', 'old-quest', 0, 'quest_done', 'quest:obsolete',"
        " 'object:zoneline:FernPort', 'object:quest-listener', 1)"
    )
    process_gates(raw, writer, barriers)
    conn = writer.conn
    roles = conn.execute("SELECT zone_line_stable_key,slot,slot_kind FROM planning_portal_slots").fetchall()
    actual_roles = {tuple(row) for row in roles}
    expected_roles = {
        (f"zoneline:{field}", choice, "dedicated" if slot else "rune")
        for field, slot, _ in _PORTALS
        for choice in ((slot,) if slot else _RUNES)
    }
    assert actual_roles == expected_roles
    selections = _select_planning_portals(raw, conn, "table")
    assert {(entry.line, entry.slot, entry.slot_kind) for entry in selections} == expected_roles
    for index, (field, slot, _game_id) in enumerate(_PORTALS):
        line = f"zoneline:{field}"
        rows = conn.execute(
            "SELECT gate,group_index,atom_kind,atom_stable_key,atom_slot FROM gate_conditions"
            " WHERE subject_stable_key=?",
            (line,),
        ).fetchall()
        expected_slots = (slot,) if slot else _RUNES
        assert {tuple(row) for row in rows} == {
            (f"activation:object:{line}", group, "planning_slot_item", f"item:portal{index}", chosen)
            for group, chosen in enumerate(expected_slots)
        }
        assert {entry.destination_zone_stable_key for entry in selections if entry.line == line} == {
            f"zone:destination{index}"
        }
    assert (
        conn.execute("SELECT COUNT(*) FROM gate_conditions WHERE subject_stable_key='zoneline:unrelated'").fetchone()[0]
        == 0
    )


def test_planning_slots_inherit_the_claimed_desk_host(portal_pair, tmp_path):
    raw, writer = portal_pair
    writer.conn.execute(
        "INSERT INTO quests (stable_key, db_name, display_name, image_name)"
        " VALUES ('quest:claim', 'CLAIMRELIQUARY', 'Claiming the Reliquary', '')"
    )
    raw.execute("UPDATE ObjectHierarchy SET ActiveSelf=0 WHERE ObjectKey='object:desk'")
    raw.execute(
        "INSERT INTO QuestActivationEffects VALUES"
        " ('object', 'object:desk', 'enable', 'claim-listener', 0, 'quest_done', 'quest:claim',"
        " 'object:desk', 'object:quest-listener', 1)"
    )
    barriers = tmp_path / "barriers.toml"
    barriers.write_text("")
    process_gates(raw, writer, barriers)
    rows = writer.conn.execute(
        "SELECT subject_stable_key, group_index, atom_kind, atom_stable_key FROM gate_conditions"
        " WHERE subject_kind='zone_line'"
    ).fetchall()
    groups = {}
    for line, group, kind, key in rows:
        groups.setdefault((line, group), set()).add((kind, key))
    assert len(groups) == 40
    assert all(("quest_done", "quest:claim") in atoms for atoms in groups.values())
    assert all(any(kind == "planning_slot_item" for kind, _ in atoms) for atoms in groups.values())


@pytest.mark.parametrize("missing", ["item", "reference", "target", "destination", "ambiguous_item", "ambiguous_line"])
def test_missing_or_ambiguous_native_binding_fails(portal_pair, missing):
    raw, writer = portal_pair
    conn = writer.conn
    if missing == "item":
        conn.execute("DELETE FROM items WHERE id='134379'")
    elif missing == "reference":
        raw.execute("DELETE FROM ScriptedActivatorReferences WHERE Field='FernPort'")
    elif missing == "target":
        raw.execute("DELETE FROM ScriptedActivatorTargets WHERE ReferenceId='FernPort' AND Kind='zone_line'")
    elif missing == "destination":
        conn.execute("UPDATE zone_lines SET destination_zone_stable_key=NULL WHERE stable_key='zoneline:FernPort'")
    elif missing == "ambiguous_item":
        conn.execute(
            "INSERT INTO items (stable_key,id,display_name,image_name)"
            " VALUES ('item:duplicate',134379,'Duplicate','duplicate')"
        )
    else:
        raw.execute(
            "INSERT INTO ScriptedActivatorTargets VALUES ('FernPort','enable','zone_line','zoneline:unrelated')"
        )
    with pytest.raises(ValueError, match="Missing or ambiguous"):
        _select_planning_portals(raw, conn, "table")


@pytest.mark.parametrize("slot", ["PlanarFern", "PlanarBrax", "PlanarVith", "PlanarSol", *_RUNES])
def test_canonical_stored_slot_codec_preserves_exact_item_and_slot(slot):
    condition = ProvenanceCondition(
        "planning", 0, 0, "planning_slot_item", "item:portal", slot, scope="zoneline:actual"
    )
    assert condition_from_dict(asdict(condition)) == condition
    invalid = asdict(condition)
    invalid["reference_slot"] = "L1"
    with pytest.raises(ValueError):
        condition_from_dict(invalid)
    invalid = asdict(condition)
    invalid["phase"] = "operation_outcome"
    with pytest.raises(ValueError):
        condition_from_dict(invalid)


def test_account_codec_keeps_existing_operation_outcome_without_alias():
    condition = ProvenanceCondition(
        "claim",
        0,
        0,
        "account_state",
        "account_state:reliquary_claimed",
        actor="account",
        value="true",
        scope="spawn:actual",
        phase="operation_outcome",
    )
    assert condition_from_dict(asdict(condition)) == condition
    invalid = asdict(condition)
    invalid["phase"] = "outcome"
    with pytest.raises(ValueError):
        condition_from_dict(invalid)
