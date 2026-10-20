from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer import Typer
from typer.testing import CliRunner

from erenshor.cli.commands import progression
from erenshor.domain.value_objects.progression import PROGRESSION_SCHEMA_VERSION
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.progression import ProgressionRepository
from erenshor.infrastructure.database.repository import RepositoryError

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

runner = CliRunner()
app = Typer()
app.add_typer(progression.app)


@pytest.fixture
def graph_path(cli_context: CLIContext) -> Path:
    path = cli_context.config.variants[cli_context.variant].resolved_database(cli_context.repo_root)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("INSERT INTO progression_meta VALUES (?, 'build-123')", (PROGRESSION_SCHEMA_VERSION,))
        for key, scene, name in (
            ("zone:start", "Start", "Starter Bay"),
            ("zone:goal", "Goal", "Secret Garden"),
            ("zone:blocked", "Blocked", "Lost Land"),
        ):
            connection.execute(
                "INSERT INTO zones(stable_key,scene_name,zone_name,display_name,image_name,zone_type) "
                "VALUES (?,?,?,?,?,'Outdoor')",
                (key, scene, name, name, name),
            )
        for key, name in (
            ("quest:gate", "Open the Gate"),
            ("quest:gap", "No Producer"),
            ("quest:negative", "Before the Gate"),
        ):
            connection.execute(
                "INSERT INTO quests(stable_key,display_name,image_name) VALUES (?,?,?)", (key, name, name)
            )
        connection.execute("INSERT INTO classes(class_name,display_name) VALUES ('Fighter','Fighter')")
        nodes = [
            ("mechanic:new_character_start", "mechanism", 0, 0, "initial"),
            ("zone:start", "zone", 0, 0, "start"),
            ("quest:gate", "quest", 1, 1, "quest"),
            ("zone:goal", "zone", 1, 2, "goal"),
            ("world_state:weather:raining:zone:start", "world_state", 0, None, None),
            ("zone:blocked", "zone", 0, None, None),
            ("quest:gap", "quest", 1, None, None),
            ("quest:negative", "quest", 1, 1, "negative"),
        ]
        connection.executemany("INSERT INTO progression_nodes VALUES (?,?,?,?,?)", nodes)
        for node, key in (
            ("mechanic:new_character_start", "initial"),
            ("zone:start", "start"),
            ("quest:gate", "quest"),
            ("zone:goal", "goal"),
            ("zone:blocked", "blocked"),
            ("quest:negative", "negative"),
        ):
            connection.execute("INSERT INTO progression_ways (node_stable_key, way_key) VALUES (?,?)", (node, key))
        for node, way, index, relation, need, quantity, slot, keywords, advisory, unconfirmed in (
            ("zone:start", "start", 0, "from", "mechanic:new_character_start", None, None, None, 0, 0),
            ("quest:gate", "quest", 0, "enter", "zone:start", None, None, None, 0, 0),
            ("zone:goal", "goal", 0, "zone line", "zone:start", None, None, None, 0, 0),
            ("zone:goal", "goal", 1, "quest done", "quest:gate", 2, "L1", "hello", 1, 1),
            ("zone:blocked", "blocked", 0, "zone line", "zone:start", None, None, None, 0, 0),
            ("zone:blocked", "blocked", 1, "release", "world_state:weather:raining:zone:start", None, None, None, 0, 0),
            ("quest:negative", "negative", 0, "quest not done", "quest:gap", None, None, None, 0, 0),
        ):
            connection.execute(
                "INSERT INTO progression_needs VALUES (?,?,?,?,?,?,?,?,NULL,?,?,NULL)",
                (node, way, index, relation, need, quantity, slot, keywords, advisory, unconfirmed),
            )
    return path


@pytest.fixture
def repository(graph_path: Path) -> Iterator[ProgressionRepository]:
    with DatabaseConnection(graph_path, read_only=True) as database:
        yield ProgressionRepository(database)


def test_node_ways_and_milestones_have_clean_names_and_exact_need_fields(repository):
    nodes = repository.get_nodes()
    assert len(nodes) == 8
    assert [node.stable_key for node in nodes] == sorted(node.stable_key for node in nodes)
    node = repository.get_node("zone:goal")
    assert node is not None
    assert (node.name, node.tier, node.is_milestone) == ("Secret Garden", 2, True)
    ways = repository.get_ways(node.stable_key)
    assert len(ways) == 1
    need = ways[0].needs[1]
    assert (
        need.relation,
        need.need_stable_key,
        need.quantity,
        need.slot,
        need.keywords,
        need.advisory,
        need.unconfirmed,
    ) == ("quest done", "quest:gate", 2, "L1", "hello", True, True)
    assert [(entry.name, entry.tier) for entry in repository.first_way_milestones(node.stable_key)] == [
        ("Starter Bay", 0),
        ("Open the Gate", 1),
        ("Secret Garden", 2),
    ]
    assert repository.get_node("unknown") is None
    assert repository.get_ways("unknown") == ()


def test_negative_condition_is_initial_truth_not_an_unreachable_ancestor(repository):
    assert [node.stable_key for node in repository.first_way_milestones("quest:negative")] == ["quest:negative"]
    assert repository.unreachable_chain("quest:negative") == ()


def test_gaps_and_unreachable_chain_preserve_leaf_without_a_way(repository):
    assert [node.stable_key for node in repository.unreachable_chain("zone:blocked")] == [
        "zone:blocked",
        "world_state:weather:raining:zone:start",
    ]
    assert repository.first_way_milestones("zone:blocked") == ()
    assert {node.stable_key for node in repository.gaps()} == {
        "zone:blocked",
        "world_state:weather:raining:zone:start",
        "quest:gap",
    }


@pytest.mark.parametrize("failure", ["missing", "duplicate", "future", "missing build", "missing table"])
def test_unsupported_metadata_fails_closed(graph_path: Path, failure: str):
    with closing(sqlite3.connect(graph_path)) as connection, connection:
        if failure == "missing":
            connection.execute("DELETE FROM progression_meta")
        elif failure == "duplicate":
            connection.execute("INSERT INTO progression_meta SELECT * FROM progression_meta")
        elif failure == "future":
            connection.execute("UPDATE progression_meta SET contract_version=999")
        elif failure == "missing build":
            connection.execute("UPDATE progression_meta SET game_build_id=''")
        else:
            connection.execute("DROP TABLE progression_meta")
    with (
        DatabaseConnection(graph_path, read_only=True) as database,
        pytest.raises(RepositoryError, match="Unsupported progression schema"),
    ):
        ProgressionRepository(database)


def test_cyclic_first_ways_fail_instead_of_printing_a_partial_chain(graph_path: Path, repository):
    with closing(sqlite3.connect(graph_path)) as connection, connection:
        connection.execute(
            "UPDATE progression_needs SET need_stable_key='zone:goal' WHERE node_stable_key='quest:gate'"
        )
    with pytest.raises(RepositoryError, match="Cyclic progression first way"):
        repository.first_way_milestones("zone:goal")


def test_unreachable_cycle_is_reportable_even_without_a_leaf(graph_path: Path, repository):
    with closing(sqlite3.connect(graph_path)) as connection, connection:
        connection.execute(
            "UPDATE progression_needs SET need_stable_key='zone:blocked' WHERE node_stable_key='zone:blocked'"
        )
    assert [node.stable_key for node in repository.unreachable_chain("zone:blocked")] == [
        "zone:blocked",
        "zone:blocked",
    ]


def test_show_prints_ways_metadata_and_ordered_first_way_milestones(cli_context, graph_path):
    result = runner.invoke(app, ["show", "zone:goal"], obj=cli_context)
    assert result.exit_code == 0, result.output
    assert "Secret Garden [zone:goal]" in result.output
    assert "Kind zone. Tier 2. Build build-123." in result.output
    assert "goal (first): Travel from Starter Bay to Secret Garden, after Open the Gate (not confirmed in play)." in (
        result.output
    )
    assert (
        "quest done Open the Gate [quest:gate] (quantity 2, slot L1, keywords 'hello', advisory, unconfirmed)"
        in result.output
    )
    assert (
        result.output.index("tier 0: Starter Bay")
        < result.output.index("tier 1: Open the Gate")
        < result.output.index("tier 2: Secret Garden")
    )
    assert "not a save-state assessment" in result.output


def test_learning_level_round_trips_and_prints_without_becoming_a_tier(cli_context, graph_path):
    with closing(sqlite3.connect(graph_path)) as connection, connection:
        connection.execute(
            "UPDATE progression_needs SET required_level=8 WHERE node_stable_key='zone:goal' AND need_index=1"
        )
    with DatabaseConnection(graph_path, read_only=True) as database:
        repository = ProgressionRepository(database)
        assert repository.get_ways("zone:goal")[0].needs[1].required_level == 8
        assert repository.get_node("zone:goal").tier == 2
    result = runner.invoke(app, ["show", "zone:goal"], obj=cli_context)
    assert result.exit_code == 0, result.output
    assert "level 8" in result.output
    assert "after Open the Gate, at level 8 or higher" in result.output
    assert "Tier 2." in result.output


def test_show_unreachable_node_prints_its_way_and_missing_producer(cli_context, graph_path):
    result = runner.invoke(app, ["show", "zone:blocked"], obj=cli_context)
    assert result.exit_code == 0, result.output
    assert "Ways (1)" in result.output
    assert "No way reaches it from a start." in result.output
    assert "Rain in Starter Bay" in result.output
    assert "no recorded way" in result.output


def test_show_gaps_counts_and_lists_missing_ways_and_tiers(cli_context, graph_path):
    result = runner.invoke(app, ["show", "--gaps"], obj=cli_context)
    assert result.exit_code == 0, result.output
    assert "Gaps (3 nodes)" in result.output
    assert "Without a way (2): quest=1, world_state=1" in result.output
    assert "Without a tier (3): quest=1, world_state=1, zone=1" in result.output
    assert "Lost Land [zone:blocked] (no tier)" in result.output


@pytest.mark.parametrize("arguments", [["show"], ["show", "zone:goal", "--gaps"]])
def test_show_requires_one_inspection_mode(cli_context, graph_path, arguments):
    result = runner.invoke(app, arguments, obj=cli_context)
    assert result.exit_code == 2
    assert "Provide one stable key or --gaps" in result.output


def test_show_unknown_node_reports_a_clear_error(cli_context, graph_path):
    result = runner.invoke(app, ["show", "zone:absent"], obj=cli_context)
    assert result.exit_code == 1
    assert "Unknown progression node: zone:absent" in result.output


def test_read_only_inspection_obeys_root_dry_run_without_changing_the_database(cli_context, graph_path):
    before = graph_path.read_bytes()
    result = runner.invoke(app, ["show", "zone:goal"], obj=replace(cli_context, dry_run=True))
    assert result.exit_code == 0, result.output
    assert graph_path.read_bytes() == before


def test_missing_database_does_not_create_one(cli_context, tmp_path):
    missing = tmp_path / "absent.sqlite"
    cli_context.config.variants[cli_context.variant].database = str(missing)
    result = runner.invoke(app, ["show", "zone:goal"], obj=cli_context)
    assert result.exit_code == 1
    assert "Database file not found" in result.output
    assert not missing.exists()


@pytest.mark.parametrize(
    "condition",
    [
        "event:script",
        "release:health_phase_timer:controller",
        "release:spawn_health_phase_timer:controller",
        "release:combat_empty_wards:controller",
        "unknown:condition",
    ],
)
def test_condition_keys_have_explicit_wording_or_fail(cli_context, graph_path, condition):
    with closing(sqlite3.connect(graph_path)) as connection, connection:
        if condition.startswith("event:"):
            connection.execute(
                "UPDATE progression_needs SET relation='event',need_stable_key=NULL,condition_key=? "
                "WHERE node_stable_key='quest:gate'",
                (condition,),
            )
        else:
            connection.execute(
                "INSERT INTO progression_needs "
                "VALUES ('quest:gate','quest',1,'release',NULL,NULL,NULL,NULL,?,0,0,NULL)",
                (condition,),
            )
    result = runner.invoke(app, ["show", "quest:gate"], obj=cli_context)
    assert result.exit_code == (1 if condition.startswith("unknown:") else 0), result.output
    assert condition in result.output
    assert "quest:gate" in result.output


def test_empty_clean_names_keep_the_node_identity_readable(graph_path, repository):
    with closing(sqlite3.connect(graph_path)) as connection, connection:
        connection.execute("UPDATE zones SET display_name='' WHERE stable_key='zone:goal'")
    node = repository.get_node("zone:goal")
    assert node is not None
    assert node.name == "zone:goal"
