import sqlite3
from collections.abc import Iterator

import pytest

from erenshor.application.processor.encounters import build_encounter_rows

ROOT = "spawn:unrelated:root"
SUPPORTS = tuple(f"spawn:unrelated:support{index}" for index in range(4))
QUEST = "quest:claimreliquary"
ACCOUNT = "account_state:reliquary_claimed"
FACTS = (
    "guide.gates.reliquary_sources",
    "guide.gates.reliquary_wards",
    "guide.gates.reliquary_claim_awake",
    "guide.gates.reliquary_claim_saved",
    "guide.gates.reliquary_claim_loaded",
)


@pytest.fixture
def encounter_databases() -> Iterator[tuple[sqlite3.Connection, sqlite3.Connection]]:
    raw, clean = sqlite3.connect(":memory:"), sqlite3.connect(":memory:")
    raw.executescript("""
        CREATE TABLE ScriptedActivators (SourceKey TEXT, RuleId TEXT, ComponentIsEnabled INTEGER);
        CREATE TABLE ScriptedActivatorReferences (SourceKey TEXT, Field TEXT, ReferenceKind TEXT, ReferenceKey TEXT);
        CREATE TABLE Quests (StableKey TEXT, DBName TEXT);
        CREATE TABLE code_facts (fact_id TEXT, key TEXT, value TEXT, value_type TEXT);
        INSERT INTO ScriptedActivators VALUES ('actual-controller', 'reliquary_account_claim', 0);
        INSERT INTO Quests VALUES ('quest:claimreliquary', 'CLAIMRELIQUARY');
    """)
    raw.execute(
        "INSERT INTO ScriptedActivatorReferences VALUES (?,?,?,?)",
        ("actual-controller", "$host_spawn_point", "spawn_point", ROOT),
    )
    raw.executemany("INSERT INTO code_facts VALUES (?, 'ok', 'true', 'bool')", [(fact,) for fact in FACTS])
    clean.executescript("""
        CREATE TABLE character_damage_releases (
            mechanism TEXT, source_stable_key TEXT, condition_kind TEXT, condition_stable_key TEXT
        );
        CREATE TABLE character_spawns (spawn_point_stable_key TEXT, character_stable_key TEXT);
        CREATE TABLE quests (stable_key TEXT);
        INSERT INTO quests VALUES ('quest:claimreliquary');
    """)
    clean.execute(
        "INSERT INTO character_damage_releases VALUES ('reliquary_wards',?,'controller',?)",
        (ROOT, "character:unrelated stone"),
    )
    clean.executemany(
        "INSERT INTO character_damage_releases VALUES ('reliquary_wards',?,'spawn_point_cleared',?)",
        [(ROOT, support) for support in SUPPORTS],
    )
    clean.executemany(
        "INSERT INTO character_spawns VALUES (?, 'character:unrelated stone')",
        [(member,) for member in (ROOT, *SUPPORTS, "spawn:unrelated:not-a-member")],
    )
    try:
        yield raw, clean
    finally:
        raw.close()
        clean.close()


def test_native_host_and_essential_links_define_actual_members_even_with_disabled_behaviour(encounter_databases):
    result = build_encounter_rows(*encounter_databases)
    members = result["encounter_placements"]
    assert {row["member_spawn_stable_key"] for row in members} == {ROOT, *SUPPORTS}
    assert {row["root_spawn_stable_key"] for row in members} == {ROOT}
    assert {row["encounter_key"] for row in members} == {"encounter:actual-controller"}
    assert {row["member_spawn_stable_key"] for row in members if row["role"] == "root"} == {ROOT}
    assert len([row for row in members if row["role"] == "support"]) == 4
    assert {(row["context_kind"], row["post_completion_role"]) for row in members} == {("account_claim", "player_home")}
    assert {
        (row["state_scope"], row["state_key"], row["required_value"]) for row in result["encounter_conditions"]
    } == {("account", ACCOUNT, "false"), ("character", QUEST, "false")}


@pytest.mark.parametrize(
    "account,quest,can_fight", [(False, False, True), (True, False, False), (False, True, False), (True, True, False)]
)
def test_guarded_awake_migration_and_account_completion_do_not_propose_repeat_fights(
    encounter_databases, account, quest, can_fight
):
    result = build_encounter_rows(*encounter_databases)
    state = {("account", ACCOUNT): str(account).lower(), ("character", QUEST): str(quest).lower()}
    available = all(
        state[(row["state_scope"], row["state_key"])] == row["required_value"] for row in result["encounter_conditions"]
    )
    assert available is can_fight
    for event in ("scene_awake_quest_completed", "scene_awake_account_claimed"):
        guards = [row for row in result["encounter_event_conditions"] if row["event_kind"] == event]
        assert len(guards) == 1
        if all(state[(row["state_scope"], row["state_key"])] == row["required_value"] for row in guards):
            for row in result["encounter_completions"]:
                if row["event_kind"] == event:
                    state[(row["state_scope"], row["state_key"])] = row["result_value"]
    assert state == {("account", ACCOUNT): str(not can_fight).lower(), ("character", QUEST): str(not can_fight).lower()}


def test_death_completes_claim_without_turning_first_aggro_into_a_death_prerequisite(encounter_databases):
    result = build_encounter_rows(*encounter_databases)
    death = [row for row in result["encounter_completions"] if row["event_kind"] == "host_death"]
    assert {(row["state_scope"], row["state_key"], row["result_value"]) for row in death} == {
        ("account", ACCOUNT, "true"),
        ("character", QUEST, "true"),
    }
    assert not any(row["event_kind"] == "host_death" for row in result["encounter_event_conditions"])
    assert not any(row["event_kind"] == "first_aggro" for row in result["encounter_completions"])


def test_old_export_without_actual_suppressor_binding_fails_closed(encounter_databases):
    raw, clean = encounter_databases
    raw.execute("DELETE FROM ScriptedActivators")
    with pytest.raises(ValueError, match="Missing native account-suppressor"):
        build_encounter_rows(raw, clean)


@pytest.mark.parametrize("fact", FACTS)
def test_account_behavior_requires_matching_verified_facts(encounter_databases, fact):
    raw, clean = encounter_databases
    raw.execute("UPDATE code_facts SET value = 'false' WHERE fact_id = ?", (fact,))
    with pytest.raises(ValueError, match="requires verified code fact"):
        build_encounter_rows(raw, clean)


def test_ambiguous_native_host_is_not_guessed(encounter_databases):
    raw, clean = encounter_databases
    raw.execute("INSERT INTO ScriptedActivatorReferences SELECT * FROM ScriptedActivatorReferences")
    with pytest.raises(ValueError, match="ambiguous scripted spawn_point reference"):
        build_encounter_rows(raw, clean)


def test_missing_actual_support_placement_is_not_replaced_with_a_canonical_copy(encounter_databases):
    raw, clean = encounter_databases
    clean.execute("DELETE FROM character_spawns WHERE spawn_point_stable_key = ?", (SUPPORTS[0],))
    with pytest.raises(ValueError, match="no actual exported placement"):
        build_encounter_rows(raw, clean)


def test_unrelated_variant_has_no_synthetic_claim_context(encounter_databases):
    raw, clean = encounter_databases
    raw.execute("DELETE FROM ScriptedActivators")
    clean.execute("DELETE FROM character_damage_releases")
    assert build_encounter_rows(raw, clean) == {
        "encounter_placements": [],
        "encounter_conditions": [],
        "encounter_completions": [],
        "encounter_event_conditions": [],
    }
