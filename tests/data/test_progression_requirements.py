"""Named shipping-content contracts for the shared progression graph."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
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
        ("quest done", "quest:claimreliquary"),
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
    assert _pairs(ways[0]) == {
        origin,
        ("planning slot", "item:gen - rune of sands"),
        ("quest done", "quest:claimreliquary"),
    }
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


def test_she_sees_you_needs_the_awakened_statue_in_jaws(clean: sqlite3.Connection) -> None:
    ways = _ways(clean, "quest:jawsseen")
    assert len(ways) == 1, ways
    needs = next(iter(ways.values()))
    assert _pairs(needs) == {("event", "zone:jaws"), ("quest done", "quest:jawsentry")}


def test_siraethe_waits_behind_the_gaze_wall_and_the_wards_of_sivakaya(clean: sqlite3.Connection) -> None:
    ways = _ways(clean, "character:siraethe")
    assert len(ways) == 1, ways
    assert _pairs(next(iter(ways.values()))) == {
        ("barrier", "object:jaws:pietytrigger[645]"),
        ("barrier", "object:jaws:sm_bld_castle_wall_02%20%288%29[2016]"),
        ("in zone", "zone:jaws"),
    }


def test_shivering_tomb_two_opens_behind_the_angel_statue(clean: sqlite3.Connection) -> None:
    ways = _ways(clean, "zone:shiveringtomb2")
    assert len(ways) == 1, ways
    assert _pairs(next(iter(ways.values()))) == {
        ("barrier", "object:shiveringstep:sm_prop_statue_angel_01[397]"),
        ("zone line", "zone:shiveringstep"),
    }
    assert _node(clean, "zone:shiveringtomb2")["tier"] is not None


def test_both_twin_giants_must_die_to_open_the_cliffs_of_the_plane_of_elements(clean: sqlite3.Connection) -> None:
    for cliff in ("object:planeofbrax:frostcliff[633]", "object:planeofbrax:infernocliff[557]"):
        ways = _ways(clean, cliff)
        assert len(ways) == 1, ways
        assert _pairs(next(iter(ways.values()))) == {
            ("defeated", "character:frost"),
            ("defeated", "character:inferno"),
        }


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
    assert _pairs(next(iter(placements.values()))) == {
        ("in zone", "zone:stowawayportal"),
        *(("defeated", f"character:shadow of {god}") for god in ("brax", "fernalla", "soluna", "vitheo")),
    }
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


def test_evadne_rain_release_needs_invoke_storm_from_ring_or_scroll(clean: sqlite3.Connection) -> None:
    rain = "world_state:weather:raining:zone:braxonian"
    spell = "spell:dru - invoke storm"
    key = "item:key -  ancient braxonian key"
    ways = _ways(clean, key)
    assert len(ways) == 1, ways
    assert _pairs(next(iter(ways.values()))) == {("drops", "character:evadne"), ("release", rain)}
    weather = _ways(clean, rain)
    assert len(weather) == 1, weather
    assert _pairs(next(iter(weather.values()))) == {("in zone", "zone:braxonian"), ("cast", spell)}
    spell_ways = list(_ways(clean, spell).values())
    assert {frozenset(_pairs(needs)) for needs in spell_ways} == {
        frozenset({("casts", "item:ring - 20 - tempestalia")}),
        frozenset({("teaches", "item:spell scroll - invoke storm"), ("class", "class:druid")}),
    }
    assert {
        (need["relation"], need["required_level"])
        for needs in spell_ways
        for need in needs
        if need["relation"] in {"casts", "teaches"}
    } == {("casts", None), ("teaches", 8)}
    for dependent in (rain, key):
        node = _node(clean, dependent)
        assert node["tier"] is not None and node["first_way_key"] is not None, dict(node)


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
    assert _pairs(from_hall[0]) == {
        origin,
        ("planning slot", "item:gen - rune of the hills"),
        ("quest done", "quest:claimreliquary"),
    }
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


def test_cli_key_names_evadne_rain_and_storm_sources(main_clean_db: Path) -> None:
    result = _show(main_clean_db, "item:key -  ancient braxonian key")
    assert result.exit_code == 0, result.output
    assert "drops Evadne the Corrupted [character:evadne]" in result.output
    assert "release Rain in Braxonian Desert [world_state:weather:raining:zone:braxonian]" in result.output
    rain = _show(main_clean_db, "world_state:weather:raining:zone:braxonian")
    assert rain.exit_code == 0, rain.output
    assert "cast Invoke Storm [spell:dru - invoke storm]" in rain.output
    assert "natural weather" not in rain.output
    spell = _show(main_clean_db, "spell:dru - invoke storm")
    assert spell.exit_code == 0, spell.output
    assert "casts Tempestalia, Ring of Storms [item:ring - 20 - tempestalia]" in spell.output
    assert "teaches Spell Scroll: Invoke Storm [item:spell scroll - invoke storm] (level 8)" in spell.output
    assert "class Druid [class:druid]" in spell.output


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
    assert "world_state:weather:raining:zone:braxonian" not in expected
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
                        need.required_level,
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
                        need["required_level"],
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


def test_exported_weather_limits_keep_four_scenes_from_natural_rain(clean: sqlite3.Connection) -> None:
    trends = clean.execute(
        "SELECT scene,max_natural_rainy FROM weather_trends WHERE is_enabled=1 ORDER BY scene"
    ).fetchall()
    assert dict(trends) == pytest.approx(
        {
            "AzynthiClear": 0.5,
            "Braxonian": 0.15,
            "Krakengard": 0.3,
            "Underspine": 0.35,
        }
    )
    for scene, _ in trends:
        state = clean.execute(
            "SELECT s.stable_key,s.uses_sun,s.natural_rain_can_start FROM world_states s"
            " JOIN zones z ON z.stable_key=s.zone_stable_key WHERE z.scene_name=?",
            (scene,),
        ).fetchone()
        assert state is not None, scene
        assert tuple(state)[1:] == (1, 0), scene
        producers = clean.execute(
            "SELECT mechanism,spell_stable_key FROM world_state_producers WHERE state_stable_key=?", (state[0],)
        ).fetchall()
        assert [tuple(row) for row in producers] == [("spell", "spell:dru - invoke storm")]


def test_fallen_fernalla_rune_phase_needs_a_dying_wish_part_four(clean: sqlite3.Connection) -> None:
    phase = _ways(clean, "character:final fernalla 1")
    assert phase
    assert all(("quest done", "quest:sepulcher4") in _pairs(way) for way in phase.values())


def test_astra_needs_all_nine_stardust_and_their_nine_release_items(clean: sqlite3.Connection) -> None:
    ways = _ways(clean, "character:astral_ guardian of stars")
    assert len(ways) == 1
    needs = next(iter(ways.values()))
    quantities = {(need["relation"], need["need_stable_key"]): need["quantity"] for need in needs}
    assert quantities["defeated", "character:stardust"] == 9
    assert quantities["release", "item:gen - lost faith"] == 9


def test_freed_spirit_of_raval_needs_ravals_defeat(clean: sqlite3.Connection) -> None:
    ways = _ways(clean, "character:freed spirit of raval")
    assert ways
    assert all(("defeated", "character:raval") in _pairs(way) for way in ways.values())


def test_all_forty_planning_slot_roles_need_the_claimed_desk(clean: sqlite3.Connection) -> None:
    roles = clean.execute("SELECT zone_line_stable_key, slot FROM planning_portal_slots").fetchall()
    assert len(roles) == 40
    for line in {row[0] for row in roles}:
        groups = clean.execute(
            "SELECT group_index, MAX(atom_kind='quest_done' AND atom_stable_key='quest:claimreliquary')"
            " FROM gate_conditions WHERE subject_kind='zone_line' AND subject_stable_key=?"
            " AND gate LIKE 'activation:%' GROUP BY gate, group_index",
            (line,),
        ).fetchall()
        assert groups and all(row[1] for row in groups), line


def test_every_exported_subject_and_controller_names_its_complete_hierarchy(main_raw_db: Path) -> None:
    with sqlite3.connect(f"{main_raw_db.as_uri()}?mode=ro", uri=True) as raw:
        for table, column in (
            ("Characters", "ObjectKey"),
            ("SpawnPoints", "ObjectKey"),
            ("SpawnPointTriggers", "ObjectKey"),
            ("ZoneLines", "ObjectKey"),
            ("ItemBags", "ObjectKey"),
            ("Doors", "ObjectKey"),
            ("UiItemAccessTargets", "ObjectKey"),
            ("ScriptedActivators", "ObjectKey"),
            ("DynamicCharacterSpawns", "ControllerObjectKey"),
            ("CharacterChainedSpawns", "ControllerObjectKey"),
        ):
            total, missing = raw.execute(
                f"SELECT COUNT(*),SUM(h.ObjectKey IS NULL) FROM {table} s"
                f" LEFT JOIN ObjectHierarchy h ON h.ObjectKey=s.{column}"
            ).fetchone()
            assert total > 0 and missing == 0, table
        assert (
            raw.execute(
                "SELECT COUNT(*) FROM ObjectHierarchy h LEFT JOIN ObjectHierarchy p ON p.ObjectKey=h.ParentObjectKey"
                " WHERE h.ParentObjectKey IS NOT NULL AND p.ObjectKey IS NULL"
            ).fetchone()[0]
            == 0
        )
        assert raw.execute(
            "SELECT SourceObjectName FROM ScriptedActivators WHERE Script='PlanningTable'"
        ).fetchall() == [("PlanningDesk",)]


def test_box_of_portals_keeps_the_claimed_desks_shared_gate(clean: sqlite3.Connection) -> None:
    locations = clean.execute(
        "SELECT locations.conditions FROM item_acquisition_locations locations"
        " JOIN item_acquisitions source ON source.acquisition_key=locations.owner_key"
        " WHERE source.item_stable_key='item:gen - box of portals' AND source.kind='ui_grant'"
    ).fetchall()
    assert locations
    for location in locations:
        assert any(
            atom["predicate"] == "quest_done" and atom["reference_stable_key"] == "quest:claimreliquary"
            for atom in json.loads(location[0])
        )


def test_first_ways_have_their_nodes_tier_and_the_lowest_rank(clean: sqlite3.Connection) -> None:
    misranked = clean.execute(
        "SELECT n.stable_key FROM progression_nodes n"
        " JOIN progression_ways first ON first.node_stable_key=n.stable_key AND first.way_key=n.first_way_key"
        " WHERE first.tier IS NOT n.tier OR EXISTS (SELECT 1 FROM progression_ways other"
        " WHERE other.node_stable_key=n.stable_key AND other.way_key != first.way_key"
        " AND (other.tier, other.depth, other.way_key) < (first.tier, first.depth, first.way_key))"
    ).fetchall()
    assert misranked == []


def test_the_arena_fee_trade_ranks_before_the_round_8_chest_and_the_buy_back(clean: sqlite3.Connection) -> None:
    rows = clean.execute(
        "SELECT f.fact FROM progression_ways w JOIN progression_way_facts f USING (node_stable_key, way_key)"
        " WHERE w.node_stable_key='item:quest - vithean arena token 1' ORDER BY w.tier, w.depth, w.way_key"
    ).fetchall()
    kinds = [json.loads(row[0].removeprefix("acquisition:"))[0:2] for row in rows]
    assert kinds == [
        ["quest_reward", "ArenaToken"],
        ["vendor", "character:master of arms:planeofvitheo:463.87:25.16:417.06"],
        ["character_drop", "character:arenachest 8"],
    ]


def test_a_way_that_needs_an_unreached_node_has_no_rank(clean: sqlite3.Connection) -> None:
    rows = clean.execute(
        "SELECT w.tier, w.depth, EXISTS (SELECT 1 FROM progression_needs p JOIN progression_nodes target"
        " ON target.stable_key=p.need_stable_key WHERE p.node_stable_key=w.node_stable_key AND p.way_key=w.way_key"
        " AND p.relation != 'quest not done' AND target.tier IS NULL) FROM progression_ways w"
    ).fetchall()
    assert rows and all((tier is None) == bool(unreached) for tier, _depth, unreached in rows)
