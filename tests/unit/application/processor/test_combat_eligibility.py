"""Combat eligibility follows actual copies and explicit release references."""

import sqlite3

import pytest

from erenshor.application.processor.combat_eligibility import process_combat_eligibility
from erenshor.application.processor.writer import Writer


@pytest.fixture
def databases(tmp_path):
    raw = sqlite3.connect(":memory:")
    raw.row_factory = sqlite3.Row
    raw.executescript(
        """
        CREATE TABLE Characters (StableKey TEXT PRIMARY KEY, Invulnerable INTEGER);
        CREATE TABLE CharacterDamageReleaseRules (
            RuleKey TEXT PRIMARY KEY, CharacterStableKey TEXT, Mechanism TEXT,
            SourceStableKey TEXT, ConditionKind TEXT, ConditionStableKey TEXT,
            CanRelease INTEGER, ControllerEnabled INTEGER
        );
        CREATE TABLE QuestVariants (
            ResourceName TEXT PRIMARY KEY, QuestStableKey TEXT,
            DropInvulnOnHolder INTEGER, DisableQuest INTEGER
        );
        CREATE TABLE QuestCharacterRoles (QuestStableKey TEXT, CharacterStableKey TEXT, Role TEXT);
        CREATE TABLE QuestCompletionSources (
            QuestStableKey TEXT, Method TEXT, SourceType TEXT, SourceStableKey TEXT
        );
        CREATE TABLE ScriptedActivators (
            SourceKey TEXT, RuleId TEXT, IsEnabled INTEGER, HostCharacterStableKey TEXT,
            ComponentIsEnabled INTEGER, SourceScene TEXT
        );
        CREATE TABLE ScriptedActivatorReferences (
            SourceKey TEXT, Field TEXT, ReferenceKind TEXT, ReferenceKey TEXT
        );
        CREATE TABLE SpawnPoints (StableKey TEXT PRIMARY KEY);
        CREATE TABLE SpawnPointCharacters (SpawnPointStableKey TEXT, CharacterStableKey TEXT);
        CREATE TABLE SpawnPointEssentialLinks (
            SourceSpawnPointStableKey TEXT, EssentialSpawnPointStableKey TEXT
        );
        """
    )
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    yield raw, writer
    raw.close()
    writer.conn.close()


def _character(databases, key, *, immune=True):
    raw, writer = databases
    raw.execute("INSERT INTO Characters VALUES (?, ?)", (key, int(immune)))
    writer.insert_characters(
        [
            {
                "stable_key": key,
                "display_name": key,
                "image_name": key,
                "encounter_tier": "enemy",
                "level_scales_with_player": 0,
                "invulnerable": int(immune),
            }
        ]
    )


def _release(databases, key, *, enabled=True, feasible=True, mechanism="npc_protector_weather", source="controller:1"):
    raw, _writer = databases
    raw.execute(
        "INSERT INTO CharacterDamageReleaseRules VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (source + ":rule", key, mechanism, source, "object", "object:protector", int(feasible), int(enabled)),
    )


def _flags(databases):
    return dict(databases[1].conn.execute("SELECT stable_key, can_be_damaged FROM characters"))


def _trade_release(databases, holder, *, variant="ReleaseAsset", drop=True, disabled=False):
    raw, _writer = databases
    raw.execute(
        "INSERT INTO QuestVariants VALUES (?, 'quest:release', ?, ?)",
        (variant, int(drop), int(disabled)),
    )
    raw.execute(
        "INSERT INTO QuestCharacterRoles VALUES ('quest:release', ?, 'item_turnin')",
        (holder,),
    )
    raw.execute(
        "INSERT INTO QuestCompletionSources VALUES ('quest:release', 'item_turnin', 'character', ?)",
        (holder,),
    )
    raw.execute(
        "INSERT INTO CharacterDamageReleaseRules VALUES "
        "('trade:rule', ?, 'trade_turn_in', 'component:quest_manager:ReleaseAsset', 'quest_variant', ?, 1, 1)",
        (holder, variant),
    )


def _ward_controller(databases, host, ward1, ward2=None, *, enabled=True, active=True, source="controller:wards"):
    raw, _writer = databases
    raw.execute(
        "INSERT INTO ScriptedActivators VALUES (?, 'shivering_phantom_wards', ?, ?, ?, 'TestScene')",
        (source, int(enabled and active), host, int(enabled)),
    )
    for field, ward in (("ward1", ward1), ("ward2", ward2)):
        raw.execute(
            "INSERT INTO ScriptedActivatorReferences VALUES (?, ?, ?, ?)",
            (source, field, "null" if ward is None else "character", ward),
        )


def test_initial_immunity_and_vulnerability_are_populated_for_every_copy(databases):
    _character(databases, "character:immune")
    _character(databases, "character:vulnerable", immune=False)
    databases[1].conn.execute("UPDATE characters SET can_be_damaged = 1")

    process_combat_eligibility(*databases)

    assert _flags(databases) == {"character:immune": 0, "character:vulnerable": 1}


@pytest.mark.parametrize(("enabled", "feasible", "expected"), [(True, True, 1), (False, True, 0), (True, False, 0)])
def test_script_requires_enabled_feasible_branch(databases, enabled, feasible, expected):
    _character(databases, "character:host")
    _release(databases, "character:host", enabled=enabled, feasible=feasible)

    process_combat_eligibility(*databases)

    assert _flags(databases)["character:host"] == expected
    row = databases[1].conn.execute("SELECT * FROM character_damage_releases").fetchone()
    assert row["can_release"] == int(feasible)
    assert row["controller_enabled"] == int(enabled)


def test_initially_inactive_character_and_spawn_keep_feasible_release_capability(databases):
    raw, writer = databases
    _character(databases, "character:host")
    raw.executescript(
        """
        ALTER TABLE Characters ADD COLUMN IsEnabled INTEGER;
        ALTER TABLE SpawnPoints ADD COLUMN IsEnabled INTEGER;
        UPDATE Characters SET IsEnabled = 0;
        INSERT INTO SpawnPoints VALUES ('spawn:inactive', 0);
        INSERT INTO SpawnPointCharacters VALUES ('spawn:inactive', 'character:host');
        INSERT INTO CharacterDamageReleaseRules VALUES (
            'rule:phase', 'character:host', 'spawn_health_phase_timer',
            'spawn:inactive:script:phase', 'spawn_point', 'spawn:inactive', 1, 1
        );
        """
    )
    writer.conn.execute("UPDATE characters SET is_enabled = 0")
    writer.insert_character_spawns(
        [
            {
                "character_stable_key": "character:host",
                "spawn_point_stable_key": "spawn:inactive",
                "is_enabled": 0,
                "is_directly_placed": 0,
            }
        ]
    )

    process_combat_eligibility(*databases)

    assert _flags(databases)["character:host"] == 1
    assert writer.conn.execute("SELECT is_enabled FROM character_spawns").fetchone()[0] == 0


def test_weather_evidence_never_spreads_across_deduplicated_copies(databases):
    for key in ("character:wet", "character:other"):
        _character(databases, key)
        databases[1].insert_character_deduplications([{"group_key": "character:other", "member_stable_key": key}])
    _release(databases, "character:wet", source="spawn:wet:protector:weather:dry")

    process_combat_eligibility(*databases)

    assert _flags(databases) == {"character:wet": 1, "character:other": 0}
    assert databases[1].conn.execute(
        "SELECT source_stable_key, condition_stable_key FROM character_damage_releases"
    ).fetchone()[:] == ("spawn:wet:protector:weather:dry", "object:protector")


def test_quest_release_requires_actual_item_turn_in_holder(databases):
    raw, writer = databases
    for key in ("character:holder", "character:copy", "character:talker", "character:giver"):
        _character(databases, key)
        writer.insert_character_deduplications([{"group_key": "character:copy", "member_stable_key": key}])
    _trade_release(databases, "character:holder")
    for key, role, method in (
        ("character:holder", "giver", "talk"),
        ("character:talker", "completer", "talk"),
        ("character:giver", "giver", "item_turnin"),
    ):
        raw.execute("INSERT INTO QuestCharacterRoles VALUES ('quest:release', ?, ?)", (key, role))
        raw.execute("INSERT INTO QuestCompletionSources VALUES ('quest:release', ?, 'character', ?)", (method, key))

    process_combat_eligibility(*databases)

    assert _flags(databases) == {
        "character:holder": 1,
        "character:copy": 0,
        "character:talker": 0,
        "character:giver": 0,
    }
    row = writer.conn.execute("SELECT * FROM character_damage_releases").fetchone()
    assert (row["mechanism"], row["condition_kind"], row["condition_stable_key"]) == (
        "trade_turn_in",
        "quest_variant",
        "ReleaseAsset",
    )


def test_disable_quest_flag_does_not_change_trade_window_availability(databases):
    _character(databases, "character:holder")
    _trade_release(databases, "character:holder", disabled=True)

    process_combat_eligibility(*databases)

    assert _flags(databases)["character:holder"] == 1


def test_exact_holder_variant_does_not_inherit_other_variant_release(databases):
    raw, _writer = databases
    _character(databases, "character:holder")
    _trade_release(databases, "character:holder", variant="NonReleaseAsset", drop=False)
    raw.execute("INSERT INTO QuestVariants VALUES ('ReleaseAsset', 'quest:release', 1, 0)")

    with pytest.raises(ValueError, match="does not drop holder invulnerability"):
        process_combat_eligibility(*databases)


def test_missing_exact_holder_variant_fails(databases):
    _character(databases, "character:holder")
    _trade_release(databases, "character:holder")
    databases[0].execute("DELETE FROM QuestVariants")

    with pytest.raises(ValueError, match="Missing exact quest variant"):
        process_combat_eligibility(*databases)


def test_trade_release_without_actual_holder_relation_fails(databases):
    _character(databases, "character:holder")
    _trade_release(databases, "character:holder")
    databases[0].execute("UPDATE QuestCharacterRoles SET Role = 'completer'")

    with pytest.raises(ValueError, match="no actual item-turn-in holder relation"):
        process_combat_eligibility(*databases)


def test_real_ward_references_release_only_the_controller_host(databases):
    _character(databases, "character:host")
    _character(databases, "character:copy")
    _character(databases, "character:ward", immune=False)
    _ward_controller(databases, "character:host", "character:ward")

    process_combat_eligibility(*databases)

    assert _flags(databases) == {"character:host": 1, "character:copy": 0, "character:ward": 1}
    assert (
        databases[1]
        .conn.execute(
            "SELECT condition_stable_key FROM character_damage_releases WHERE condition_kind = 'character_dead'"
        )
        .fetchone()[0]
        == "character:ward"
    )


def test_all_referenced_wards_must_have_feasible_release_paths(databases):
    _character(databases, "character:host")
    _character(databases, "character:first", immune=False)
    _character(databases, "character:second")
    _ward_controller(databases, "character:host", "character:first", "character:second")

    process_combat_eligibility(*databases)

    assert _flags(databases)["character:host"] == 0


def test_ward_dependency_can_be_released_by_its_own_enabled_branch(databases):
    _character(databases, "character:host")
    _character(databases, "character:ward")
    _release(databases, "character:ward")
    _ward_controller(databases, "character:host", "character:ward")

    process_combat_eligibility(*databases)

    assert _flags(databases) == {"character:host": 1, "character:ward": 1}


def test_permanently_immune_ward_and_disabled_controller_do_not_release(databases):
    _character(databases, "character:host")
    _character(databases, "character:disabled")
    _character(databases, "character:ward")
    _ward_controller(databases, "character:host", "character:ward")
    _ward_controller(databases, "character:disabled", None, enabled=False, source="controller:disabled")

    process_combat_eligibility(*databases)

    assert set(_flags(databases).values()) == {0}


def test_immune_ward_cycle_cannot_bootstrap(databases):
    _character(databases, "character:first")
    _character(databases, "character:second")
    _ward_controller(databases, "character:first", "character:second", source="controller:first")
    _ward_controller(databases, "character:second", "character:first", source="controller:second")

    process_combat_eligibility(*databases)

    assert set(_flags(databases).values()) == {0}


def test_scene_inactive_host_retains_enabled_ward_controller_capability(databases):
    _character(databases, "character:host")
    _ward_controller(databases, "character:host", None, active=False)

    process_combat_eligibility(*databases)

    assert _flags(databases)["character:host"] == 1
    assert (
        databases[1].conn.execute("SELECT DISTINCT controller_enabled FROM character_damage_releases").fetchone()[0]
        == 1
    )


@pytest.mark.parametrize(("component_enabled", "expected"), [(True, 1), (False, 0)])
def test_reliquary_prefab_uses_component_capability_and_actual_spawn_links(databases, component_enabled, expected):
    raw, writer = databases
    _character(databases, "character:host")
    _character(databases, "character:copy")
    _character(databases, "character:ward", immune=False)
    raw.executemany("INSERT INTO SpawnPoints VALUES (?)", [("spawn:host",), ("spawn:ward",)])
    raw.executemany(
        "INSERT INTO SpawnPointCharacters VALUES (?, ?)",
        [("spawn:host", "character:host"), ("spawn:ward", "character:ward")],
    )
    raw.execute("INSERT INTO SpawnPointEssentialLinks VALUES ('spawn:host', 'spawn:ward')")
    raw.execute(
        "INSERT INTO ScriptedActivators VALUES ('controller:fiend', 'reliquary_wards', 0, 'character:host', ?, NULL)",
        (int(component_enabled),),
    )
    raw.execute(
        "INSERT INTO ScriptedActivators VALUES ('controller:copy', 'reliquary_wards', 0, 'character:copy', 1, NULL)"
    )

    process_combat_eligibility(*databases)

    assert _flags(databases) == {"character:host": expected, "character:copy": 0, "character:ward": 1}
    assert writer.conn.execute(
        "SELECT source_stable_key, condition_stable_key FROM character_damage_releases "
        "WHERE mechanism = 'reliquary_wards' AND condition_kind = 'spawn_point_cleared'"
    ).fetchone()[:] == ("spawn:host", "spawn:ward")


@pytest.mark.parametrize(
    "table", ["CharacterDamageReleaseRules", "ScriptedActivatorReferences", "QuestCompletionSources"]
)
def test_missing_contract_fails_instead_of_marking_permanent_immunity(databases, table):
    _character(databases, "character:host")
    databases[0].execute(f"DROP TABLE {table}")

    with pytest.raises(ValueError, match="Missing combat eligibility export contract"):
        process_combat_eligibility(*databases)


def test_missing_ward_component_capability_contract_fails(databases):
    _character(databases, "character:host")
    databases[0].executescript(
        """
        DROP TABLE ScriptedActivators;
        CREATE TABLE ScriptedActivators (
            SourceKey TEXT, RuleId TEXT, IsEnabled INTEGER, HostCharacterStableKey TEXT
        );
        """
    )

    with pytest.raises(ValueError, match="Missing combat eligibility export contract: ScriptedActivators"):
        process_combat_eligibility(*databases)


def test_unknown_mechanism_fails(databases):
    _character(databases, "character:host")
    _release(databases, "character:host", mechanism="unreviewed_release")

    with pytest.raises(ValueError, match="Unknown combat eligibility mechanism"):
        process_combat_eligibility(*databases)


def test_missing_ward_field_fails(databases):
    _character(databases, "character:host")
    _ward_controller(databases, "character:host", None)
    databases[0].execute("DELETE FROM ScriptedActivatorReferences WHERE Field = 'ward2'")

    with pytest.raises(ValueError, match="Missing or ambiguous ward reference"):
        process_combat_eligibility(*databases)


def test_inconsistent_script_evidence_group_fails(databases):
    _character(databases, "character:host")
    _release(databases, "character:host")
    databases[0].execute(
        "INSERT INTO CharacterDamageReleaseRules VALUES "
        "('other', 'character:host', 'npc_protector_weather', 'controller:1', 'state', 'rain', 0, 1)"
    )

    with pytest.raises(ValueError, match="Inconsistent damage release group"):
        process_combat_eligibility(*databases)
