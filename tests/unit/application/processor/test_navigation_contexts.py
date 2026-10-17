import sqlite3
from collections.abc import Iterator

import pytest

from erenshor.application.processor.navigation_contexts import build_zone_line_destination_rows


@pytest.fixture
def return_databases() -> Iterator[tuple[sqlite3.Connection, sqlite3.Connection]]:
    raw, clean = sqlite3.connect(":memory:"), sqlite3.connect(":memory:")
    raw.executescript("""
        CREATE TABLE ScriptedActivators (
            SourceKey TEXT, RuleId TEXT, ComponentIsEnabled INTEGER, IsEnabled INTEGER
        );
        CREATE TABLE ScriptedActivatorReferences (
            SourceKey TEXT, Field TEXT, ReferenceKind TEXT, ReferenceKey TEXT, BoolValue INTEGER, ReferenceId TEXT
        );
        CREATE TABLE ScriptedActivatorTargets (ReferenceId TEXT, ResolutionMode TEXT, Kind TEXT, Key TEXT);
        CREATE TABLE code_facts (fact_id TEXT, key TEXT, value TEXT, value_type TEXT);
        INSERT INTO ScriptedActivators VALUES ('native-controller','reliquary_return_portal',1,0);
        INSERT INTO ScriptedActivatorReferences VALUES
            ('native-controller','ReliqZL','zone_line','line:actual',NULL,'line-ref'),
            ('native-controller','ReliqPort','object','object:portal',NULL,'portal-ref'),
            ('native-controller','$portal_active_self','bool',NULL,0,'activity-ref');
        INSERT INTO ScriptedActivatorTargets VALUES ('portal-ref','enable','zone_line','line:actual');
        INSERT INTO code_facts VALUES ('guide.gates.reliquary_return_portal','ok','true','bool');
    """)
    clean.executescript("""
        CREATE TABLE zone_lines (stable_key TEXT, destination_zone_stable_key TEXT);
        INSERT INTO zone_lines VALUES ('line:actual','zone:serialized-default');
        INSERT INTO zone_lines VALUES ('line:other','zone:serialized-default');
    """)
    try:
        yield raw, clean
    finally:
        raw.close()
        clean.close()


def test_stored_return_uses_actual_reference_and_character_state_not_serialized_destination(return_databases):
    assert build_zone_line_destination_rows(*return_databases) == [
        {
            "zone_line_stable_key": "line:actual",
            "kind": "stored_return",
            "destination_state_key": "character_state:reliquary_return_zone",
            "landing_state_key": "character_state:reliquary_return_landing",
            "source_key": "native-controller",
        }
    ]


@pytest.mark.parametrize("value", [None, 1])
def test_start_guard_requires_native_inactive_self_value(return_databases, value):
    raw, clean = return_databases
    raw.execute("UPDATE ScriptedActivatorReferences SET BoolValue = ? WHERE Field = '$portal_active_self'", (value,))
    with pytest.raises(ValueError, match="initially inactive native portal"):
        build_zone_line_destination_rows(raw, clean)


def test_old_export_missing_self_activity_does_not_use_hierarchy_activity_as_a_substitute(return_databases):
    raw, clean = return_databases
    raw.execute("DELETE FROM ScriptedActivatorReferences WHERE Field = '$portal_active_self'")
    with pytest.raises(ValueError, match="initially inactive native portal"):
        build_zone_line_destination_rows(raw, clean)


def test_portal_target_must_be_exact_bound_line_even_if_another_line_has_same_destination(return_databases):
    raw, clean = return_databases
    raw.execute("UPDATE ScriptedActivatorTargets SET Key = 'line:other'")
    with pytest.raises(ValueError, match="exactly its referenced zone line"):
        build_zone_line_destination_rows(raw, clean)


def test_disabled_start_component_does_not_imply_an_executed_return_override(return_databases):
    raw, clean = return_databases
    raw.execute("UPDATE ScriptedActivators SET ComponentIsEnabled = 0")
    assert build_zone_line_destination_rows(raw, clean) == []


def test_missing_native_start_proof_fails(return_databases):
    raw, clean = return_databases
    raw.execute("UPDATE code_facts SET value = 'false'")
    with pytest.raises(ValueError, match="verified native Start fact"):
        build_zone_line_destination_rows(raw, clean)


def test_missing_clean_line_does_not_create_a_placeholder_route(return_databases):
    raw, clean = return_databases
    clean.execute("DELETE FROM zone_lines WHERE stable_key = 'line:actual'")
    with pytest.raises(ValueError, match="exactly its referenced zone line"):
        build_zone_line_destination_rows(raw, clean)


def test_variant_without_native_return_controller_has_no_synthetic_destination(return_databases):
    raw, clean = return_databases
    raw.execute("DELETE FROM ScriptedActivators")
    assert build_zone_line_destination_rows(raw, clean) == []
