"""Named shipping-content contracts for the shared progression graph."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer import Typer
from typer.testing import CliRunner

from erenshor.cli.commands.progression import app as progression_app
from erenshor.cli.context import CLIContext
from erenshor.infrastructure.config import load_config
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.progression import ProgressionRepository

if TYPE_CHECKING:
    from click.testing import Result


@pytest.fixture
def clean(main_clean_db: Path) -> Iterator[sqlite3.Connection]:
    with sqlite3.connect(f"{main_clean_db.as_uri()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        yield connection


def _ways(clean: sqlite3.Connection, key: str) -> dict[str, list[sqlite3.Row]]:
    ways = {
        row[0]: [] for row in clean.execute("SELECT way_key FROM progression_ways WHERE node_stable_key = ?", (key,))
    }
    for need in clean.execute(
        "SELECT * FROM progression_needs WHERE node_stable_key = ? ORDER BY way_key, need_index", (key,)
    ):
        ways[need["way_key"]].append(need)
    return ways


def _pairs(needs: list[sqlite3.Row]) -> set[tuple[str, str | None]]:
    return {(need["relation"], need["need_stable_key"]) for need in needs}


def _node(clean: sqlite3.Connection, key: str) -> sqlite3.Row:
    row = clean.execute("SELECT * FROM progression_nodes WHERE stable_key = ?", (key,)).fetchone()
    assert row is not None, f"Missing progression node: {key}"
    return row


def test_plane_of_elements_uses_its_dedicated_planning_slot(clean: sqlite3.Connection) -> None:
    ways = _ways(clean, "zone:planeofbrax")
    assert len(ways) == 1, ways
    needs = next(iter(ways.values()))
    assert _pairs(needs) == {
        ("zone line", "zone:reliquary"),
        ("planning slot", "item:gen - raid rune of brax"),
    }
    slot = next(need["slot"] for need in needs if need["relation"] == "planning slot")
    recorded_slots = clean.execute(
        """SELECT p.slot, p.slot_kind FROM planning_portal_slots p
        JOIN zone_lines z ON z.stable_key = p.zone_line_stable_key
        WHERE z.destination_zone_stable_key = 'zone:planeofbrax'"""
    ).fetchall()
    assert [tuple(row) for row in recorded_slots] == [(slot, "dedicated")]


def test_fallen_braxonia_uses_one_shared_keyed_barrier(clean: sqlite3.Connection) -> None:
    ways = _ways(clean, "zone:braxonia")
    assert len(ways) == 1, ways
    needs = next(iter(ways.values()))
    barrier = "door:braxonian:1057.49:89.37:571.76"
    assert _pairs(needs) == {("zone line", "zone:braxonian"), ("barrier", barrier)}
    assert _node(clean, barrier)["kind"] == "barrier"
    openings = _ways(clean, barrier)
    assert len(openings) == 1, openings
    assert _pairs(next(iter(openings.values()))) == {("key", "item:key -  ancient braxonian key")}
    facts = clean.execute(
        """SELECT g.gate, g.atom_stable_key FROM gate_conditions g
        JOIN zone_lines z ON z.stable_key = g.subject_stable_key
        WHERE g.subject_kind = 'zone_line' AND z.destination_zone_stable_key = 'zone:braxonia'
        AND g.atom_kind = 'key_held'"""
    ).fetchall()
    assert {tuple(row) for row in facts} == {(barrier, "item:key -  ancient braxonian key")}


def test_dusken_portal_requires_ritual_and_its_first_way_follows_it(clean: sqlite3.Connection) -> None:
    key = "zone:duskenportal"
    ways = _ways(clean, key)
    assert len(ways) == 1, ways
    portal = _node(clean, key)
    ritual = _node(clean, "quest:theduskenlightritual")
    assert _pairs(ways[portal["first_way_key"]]) == {
        ("zone line", "zone:duskenlight"),
        ("quest done", "quest:theduskenlightritual"),
    }
    assert ritual["tier"] is not None
    assert portal["tier"] > ritual["tier"]


def test_azynthian_resting_place_requires_breena_vendor_unlock(clean: sqlite3.Connection) -> None:
    ways = _ways(clean, "item:furniture - azynthi coffin")
    assert len(ways) == 1, ways
    assert _pairs(next(iter(ways.values()))) == {
        ("sells", "character:breena carpenter"),
        ("quest done", "quest:furniture-azynth-coffin"),
    }


def test_stowaway_exits_are_three_distinct_alternatives(clean: sqlite3.Connection) -> None:
    origin = ("zone line", "zone:stowaway")
    ways = [needs for needs in _ways(clean, "zone:hidden").values() if origin in _pairs(needs)]
    assert len(ways) == 3, [list(_pairs(needs)) for needs in ways]
    assert {frozenset(_pairs(needs) - {origin}) for needs in ways} == {
        frozenset({("held", "item:gen - beta test note")}),
        frozenset({("quest done", "quest:a way to erenshor")}),
        frozenset({("quest done", "quest:wyland's note")}),
    }


def test_rune_of_sands_has_one_way_not_six_interchangeable_slots(clean: sqlite3.Connection) -> None:
    origin = ("zone line", "zone:reliquary")
    ways = [needs for needs in _ways(clean, "zone:braxonian").values() if origin in _pairs(needs)]
    assert len(ways) == 1, ways
    assert _pairs(ways[0]) == {origin, ("planning slot", "item:gen - rune of sands")}
    assert next(need["slot"] for need in ways[0] if need["relation"] == "planning slot") == "rune slot"


def test_orion_part_two_keeps_both_turnins_and_requires_its_start(clean: sqlite3.Connection) -> None:
    key = "quest:tempeststone3"
    starts = _ways(clean, f"quest_start:{key}")
    assert len(starts) == 1, starts
    assert _pairs(next(iter(starts.values()))) == {("after", "quest:tempeststone2")}
    ways = _ways(clean, key)
    assert len(ways) == 2, ways
    assert {
        need["need_stable_key"] for needs in ways.values() for need in needs if need["relation"] == "turn in to"
    } == {"character:parmalee gemlyn", "character:violetta smithfield 1"}
    for way, needs in ways.items():
        assert ("started", f"quest_start:{key}") in _pairs(needs), way
        assert {
            (need["need_stable_key"], need["quantity"], need["slot"])
            for need in needs
            if need["relation"] == "required item"
        } == {
            ("item:ring - 0 - unsocketed ring", 1, "1"),
            ("item:gen - elderstone shard", 1, "2"),
            ("item:ore - citrine sandsilver", 1, "3"),
        }, way


def test_completing_ritual_finishes_active_loss_stone(clean: sqlite3.Connection) -> None:
    ways = _ways(clean, "quest:lossstoneritual")
    active = [
        needs for needs in ways.values() if ("quest active", "quest_start:quest:lossstoneritual") in _pairs(needs)
    ]
    assert len(active) == 1, ways
    assert _pairs(active[0]) == {
        ("after", "quest:stowawayritualcomplete"),
        ("quest active", "quest_start:quest:lossstoneritual"),
    }


def test_she_sees_you_has_a_source_free_scripted_event(clean: sqlite3.Connection) -> None:
    ways = _ways(clean, "quest:jawsseen")
    assert len(ways) == 1, ways
    needs = next(iter(ways.values()))
    assert len(needs) == 1
    assert needs[0]["relation"] == "event"
    assert needs[0]["need_stable_key"] is None
    route = clean.execute(
        "SELECT route_key FROM quest_routes WHERE quest_stable_key = 'quest:jawsseen' AND phase = 'completion'"
    ).fetchone()
    assert route is not None
    assert needs[0]["condition_key"] == f"event:{route[0]}"


def test_eldrich_crystal_names_the_actual_keeper_copy_and_sanctuary(clean: sqlite3.Connection) -> None:
    drops = [
        needs
        for needs in _ways(clean, "item:gen - eldrich crystal").values()
        if any(need["relation"] == "drops" for need in needs)
    ]
    assert len(drops) == 1, drops
    assert _pairs(drops[0]) == {("drops", "character:azynthian keeper")}
    placements = _ways(clean, "character:azynthian keeper")
    assert len(placements) == 1, placements
    assert _pairs(next(iter(placements.values()))) == {("in zone", "zone:stowawayportal")}
    assert {
        row[0]
        for row in clean.execute(
            "SELECT DISTINCT zone_stable_key FROM character_spawns "
            "WHERE character_stable_key = 'character:azynthian keeper'"
        )
    } == {"zone:stowawayportal"}


def test_candlekeeper_placement_requires_the_summoning_figurine(clean: sqlite3.Connection) -> None:
    ways = _ways(clean, "character:candlekeeper")
    assert len(ways) == 1, ways
    assert _pairs(next(iter(ways.values()))) == {
        ("in zone", "zone:braxonian"),
        ("summoned with", "item:quest - game piece the candlekeeper"),
    }


def test_stardust_kill_requires_lost_faith_but_turnin_does_not(clean: sqlite3.Connection) -> None:
    drops = [
        needs
        for needs in _ways(clean, "item:ore - stardust").values()
        if ("drops", "character:stardust") in _pairs(needs)
    ]
    assert len(drops) == 1, drops
    assert _pairs(drops[0]) == {("drops", "character:stardust"), ("release", "item:gen - lost faith")}
    release = next(need for need in drops[0] if need["relation"] == "release")
    assert (release["quantity"], release["slot"]) == (1, "1")
    turnins = _ways(clean, "quest:lostfaith")
    assert len(turnins) == 1, turnins
    assert _pairs(next(iter(turnins.values()))) == {
        ("turn in to", "character:stardust"),
        ("required item", "item:gen - lost faith"),
    }
    for needs in _ways(clean, "character:stardust").values():
        assert not any(need["relation"] == "release" for need in needs)


def test_evadne_rain_release_has_no_invented_producer_or_reachable_dependents(clean: sqlite3.Connection) -> None:
    rain = "world_state:weather:raining:zone:braxonian"
    key = "item:key -  ancient braxonian key"
    ways = _ways(clean, key)
    assert len(ways) == 1, ways
    assert _pairs(next(iter(ways.values()))) == {("drops", "character:evadne"), ("release", rain)}
    assert not _ways(clean, rain), "Rain has no recorded weather producer on the shipping main build"
    for dependent in (rain, key, "zone:braxonia", "item:gen - raid rune of brax", "zone:planeofbrax"):
        node = _node(clean, dependent)
        assert node["tier"] is None and node["first_way_key"] is None, dict(node)


def test_saved_return_is_excluded_but_rune_of_hills_planning_portal_remains(clean: sqlite3.Connection) -> None:
    stored = clean.execute(
        """SELECT z.stable_key FROM zone_lines z JOIN zone_line_destination_contexts d
        ON d.zone_line_stable_key = z.stable_key
        WHERE z.scene = 'Reliquary' AND z.destination_zone_stable_key = 'zone:hidden' AND d.kind = 'stored_return'"""
    ).fetchall()
    assert len(stored) == 1, stored
    origin = ("zone line", "zone:reliquary")
    from_hall = [needs for needs in _ways(clean, "zone:hidden").values() if origin in _pairs(needs)]
    assert len(from_hall) == 1, from_hall
    assert _pairs(from_hall[0]) == {origin, ("planning slot", "item:gen - rune of the hills")}
    assert next(need["slot"] for need in from_hall[0] if need["relation"] == "planning slot") == "rune slot"


@pytest.mark.parametrize(
    ("zone", "start"),
    [
        ("zone:stowaway", "mechanic:new_character_start"),
        ("zone:willowwatch", "mechanic:alternate_start"),
    ],
)
def test_fresh_character_starts_have_tier_zero(clean: sqlite3.Connection, zone: str, start: str) -> None:
    node = _node(clean, zone)
    assert node["tier"] == 0, dict(node)
    assert _pairs(_ways(clean, zone)[node["first_way_key"]]) == {("from", start)}
    mechanism = _node(clean, start)
    assert mechanism["tier"] == 0
    assert _ways(clean, start)[mechanism["first_way_key"]] == []


def test_ancient_key_is_a_milestone_but_wolf_meat_is_not(clean: sqlite3.Connection) -> None:
    assert _node(clean, "item:key -  ancient braxonian key")["is_milestone"] == 1
    assert _node(clean, "item:gen - wolf meat")["is_milestone"] == 0


def _show(main_clean_db: Path, *arguments: str) -> Result:
    # Mount the production group without root logging setup, which writes log files.
    app = Typer()
    app.add_typer(progression_app, name="progression")
    context = CLIContext(
        config=load_config(), variant="main", dry_run=False, repo_root=Path(__file__).resolve().parents[2]
    )
    assert context.config.variants["main"].resolved_database(context.repo_root) == main_clean_db
    return CliRunner().invoke(app, ["progression", "show", *arguments], obj=context, color=False)


def test_cli_dusken_portal_prints_named_needs_and_tier_ordered_first_way(main_clean_db: Path) -> None:
    result = _show(main_clean_db, "zone:duskenportal")
    assert result.exit_code == 0, result.output
    assert "Mysterious Portal (1) [zone:duskenportal]" in result.output
    assert "Ways (1)" in result.output
    assert "zone line The Duskenlight Coast [zone:duskenlight]" in result.output
    assert "quest done The Duskenlight Ritual [quest:theduskenlightritual]" in result.output
    assert "First-way milestones" in result.output
    with DatabaseConnection(main_clean_db, read_only=True) as database:
        repository = ProgressionRepository(database)
        milestones = repository.first_way_milestones("zone:duskenportal")
        assert milestones
        assert milestones[0].tier == 0
        assert milestones[0].stable_key in {"zone:stowaway", "zone:willowwatch"}
        assert any(node.stable_key == "quest:theduskenlightritual" for node in milestones)
        tiers = [node.tier for node in milestones if node.tier is not None]
        assert len(tiers) == len(milestones)
        assert tiers == sorted(tiers)
        rendered = result.output.split("First-way milestones", 1)[1]
        lines = [line.strip() for line in rendered.splitlines() if line.strip()]
        assert lines == [f"tier {node.tier}: {node.name} [{node.stable_key}]" for node in milestones]


def test_cli_plane_explains_its_unreachable_way_and_rain_gap(main_clean_db: Path) -> None:
    result = _show(main_clean_db, "zone:planeofbrax")
    assert result.exit_code == 0, result.output
    assert "Brax's Plane of Elements [zone:planeofbrax]" in result.output
    assert "Tier unreachable" in result.output
    assert "Ways (1)" in result.output
    assert "Rune of Elements [item:gen - raid rune of brax]" in result.output
    assert "Reliquary Hall [zone:reliquary]" in result.output
    assert "No way reaches it from a start." in result.output
    assert "Rain in Braxonian Desert [world_state:weather:raining:zone:braxonian]" in result.output
    assert "no recorded way" in result.output
    with DatabaseConnection(main_clean_db, read_only=True) as database:
        repository = ProgressionRepository(database)
        chain = repository.unreachable_chain("zone:planeofbrax")
        assert chain[0].stable_key == "zone:planeofbrax"
        assert chain[-1].stable_key == "world_state:weather:raining:zone:braxonian"
        assert all(node.tier is None for node in chain)
        assert repository.first_way_milestones("zone:planeofbrax") == ()
        for source, target in pairwise(chain):
            assert any(
                need.need_stable_key == target.stable_key
                for way in repository.get_ways(source.stable_key)
                for need in way.needs
            ), (source.stable_key, target.stable_key)


def test_cli_gaps_reports_the_persisted_unreachable_nodes(main_clean_db: Path, clean: sqlite3.Connection) -> None:
    result = _show(main_clean_db, "--gaps")
    assert result.exit_code == 0, result.output
    expected = {
        row[0]
        for row in clean.execute(
            """SELECT n.stable_key FROM progression_nodes n WHERE n.tier IS NULL OR NOT EXISTS (
        SELECT 1 FROM progression_ways w WHERE w.node_stable_key = n.stable_key)"""
        )
    }
    assert "world_state:weather:raining:zone:braxonian" in expected
    assert f"Gaps ({len(expected)} nodes)" in result.output
    with DatabaseConnection(main_clean_db, read_only=True) as database:
        repository = ProgressionRepository(database)
        assert {node.stable_key for node in repository.gaps()} == expected
    rendered_keys = {line.split("[", 1)[1].split("]", 1)[0] for line in result.output.splitlines() if " [" in line}
    assert rendered_keys == expected


def test_repository_named_content_matches_persisted_facts(main_clean_db: Path, clean: sqlite3.Connection) -> None:
    keys = (
        "zone:planeofbrax",
        "zone:braxonia",
        "zone:duskenportal",
        "zone:braxonian",
        "zone:hidden",
        "zone:stowaway",
        "zone:willowwatch",
        "item:furniture - azynthi coffin",
        "quest:tempeststone3",
        "quest:lossstoneritual",
        "quest:jawsseen",
        "item:gen - eldrich crystal",
        "character:azynthian keeper",
        "character:candlekeeper",
        "item:ore - stardust",
        "quest:lostfaith",
        "item:key -  ancient braxonian key",
        "world_state:weather:raining:zone:braxonian",
        "item:gen - wolf meat",
    )
    with DatabaseConnection(main_clean_db, read_only=True) as database:
        repository = ProgressionRepository(database)
        for key in keys:
            row = _node(clean, key)
            node = repository.get_node(key)
            assert node is not None, key
            assert (node.stable_key, node.kind, node.is_milestone, node.tier, node.first_way_key) == (
                key,
                row["kind"],
                bool(row["is_milestone"]),
                row["tier"],
                row["first_way_key"],
            ), key
            sql_ways = _ways(clean, key)
            ways = repository.get_ways(key)
            assert {way.way_key for way in ways} == set(sql_ways), key
            for way in ways:
                assert [
                    (
                        need.relation,
                        need.need_stable_key,
                        need.quantity,
                        need.slot,
                        need.keywords,
                        need.condition_key,
                        need.advisory,
                        need.unconfirmed,
                    )
                    for need in way.needs
                ] == [
                    (
                        need["relation"],
                        need["need_stable_key"],
                        need["quantity"],
                        need["slot"],
                        need["keywords"],
                        need["condition_key"],
                        bool(need["advisory"]),
                        bool(need["unconfirmed"]),
                    )
                    for need in sql_ways[way.way_key]
                ], (key, way.way_key)
        expected = clean.execute(
            """WITH RECURSIVE visited(stable_key) AS (
                SELECT 'zone:duskenportal'
                UNION
                SELECT need.need_stable_key FROM visited v
                JOIN progression_nodes node ON node.stable_key = v.stable_key
                JOIN progression_needs need ON need.node_stable_key = node.stable_key
                    AND need.way_key = node.first_way_key
                WHERE need.need_stable_key IS NOT NULL AND need.relation != 'quest not done'
            )
            SELECT node.stable_key, node.tier FROM progression_nodes node
            JOIN visited v ON v.stable_key = node.stable_key
            WHERE node.is_milestone OR node.stable_key IN ('zone:stowaway', 'zone:willowwatch')
            ORDER BY node.tier, node.stable_key"""
        ).fetchall()
        assert [(node.stable_key, node.tier) for node in repository.first_way_milestones("zone:duskenportal")] == [
            tuple(row) for row in expected
        ]
