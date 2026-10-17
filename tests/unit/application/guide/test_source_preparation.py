"""Preparation remains per source and authored wording fails on mechanic drift."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from erenshor.application.guide.combat_guidance import combat_preparations
from erenshor.application.guide.compiler import compile_graph
from erenshor.application.guide.graph_overrides import merge_overrides
from erenshor.application.guide.mod_writer import serialize_mod_guide
from erenshor.application.guide.schema import Edge, EdgeType

from .fixtures import build_graph, character_node, item_node, quest_node

if TYPE_CHECKING:
    from erenshor.application.guide.graph import EntityGraph


def _graph() -> EntityGraph:
    return build_graph(
        quest_node("quest:main", "MAIN", implicit=True),
        item_node("item:loot"),
        item_node("item:rain"),
        character_node("character:a", "Same name"),
        character_node("character:b", "Same name"),
        edges=[
            Edge("quest:main", "item:loot", EdgeType.REQUIRES_ITEM),
            Edge("character:a", "item:loot", EdgeType.DROPS_ITEM, chance=17.5),
            Edge("character:b", "item:loot", EdgeType.DROPS_ITEM, chance=31.0),
        ],
    )


def _database(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE character_damage_releases (
            character_stable_key TEXT, mechanism TEXT, source_stable_key TEXT,
            condition_kind TEXT, condition_stable_key TEXT, can_release INTEGER, controller_enabled INTEGER
        );
        CREATE TABLE items (stable_key TEXT, display_name TEXT);
        CREATE TABLE quest_required_items (quest_variant_resource_name TEXT, item_stable_key TEXT, quantity INTEGER);
        CREATE TABLE quest_variants (resource_name TEXT, repeatable INTEGER, once_per_spawn_instance INTEGER);
    """)
    return conn


def _sources(graph: EntityGraph) -> dict[str, dict[str, Any]]:
    payload = json.loads(serialize_mod_guide(graph, compile_graph(graph)))
    return {source["source_key"]: source for source in payload["quests"][0]["required_items"][0]["sources"]}


def test_trade_preparation_uses_exact_variant_and_does_not_unlock_other_copies(tmp_path: Path) -> None:
    with _database(tmp_path / "data.sqlite") as conn:
        conn.executemany(
            "INSERT INTO items VALUES (?, ?)", [("item:actual", "Actual Offering"), ("item:wrong", "Wrong Offering")]
        )
        conn.executemany("INSERT INTO quest_variants VALUES (?, 1, 1)", [("Actual Variant",), ("Other Variant",)])
        conn.executemany(
            "INSERT INTO quest_required_items VALUES (?, ?, 1)",
            [("Actual Variant", "item:actual"), ("Other Variant", "item:wrong")],
        )
        conn.execute(
            "INSERT INTO character_damage_releases VALUES (?, ?, ?, ?, ?, 1, 1)",
            ("character:a", "trade_turn_in", "holder:a", "quest_variant", "Actual Variant"),
        )
        preparations = combat_preparations(conn)
    graph = _graph()
    for edge in graph.all_edges():
        if edge.type == EdgeType.DROPS_ITEM:
            edge.note = preparations.get(edge.source)
    sources = _sources(graph)
    assert "Actual Offering" in sources["character:a"]["instruction"]
    assert "Wrong Offering" not in sources["character:a"]["instruction"]
    assert "respawn" in sources["character:a"]["instruction"].lower()
    assert "instruction" not in sources["character:b"]
    assert all("condition" not in source for source in sources.values())


def test_authored_preparation_changes_only_the_matching_source_and_preserves_odds(tmp_path: Path) -> None:
    db = tmp_path / "data.sqlite"
    with _database(db) as conn:
        conn.execute(
            "INSERT INTO character_damage_releases VALUES (?, ?, ?, ?, ?, 1, 1)",
            ("character:a", "npc_protector_weather", "weather:a", "state", "raining"),
        )
    graph = _graph()
    graph.out_edges("character:a", EdgeType.DROPS_ITEM)[0].note = "Vulnerable during rain."
    overrides = tmp_path / "notes.toml"
    overrides.write_text(
        "[[source_notes]]\n"
        'source="character:a"\n'
        'mechanism="npc_protector_weather"\n'
        'items=["item:rain"]\n'
        'text="Rain extinguishes the brazier."\n'
    )
    merge_overrides(graph, overrides, db_path=db)
    sources = _sources(graph)
    assert sources["character:a"]["instruction"] == "Rain extinguishes the brazier."
    assert sources["character:a"]["chance"] == 17.5
    assert "instruction" not in sources["character:b"]
    assert sources["character:b"]["chance"] == 31.0


@pytest.mark.parametrize("drift", ["disabled", "different_mechanism", "additional_release", "missing_item"])
def test_authored_preparation_rejects_drift_in_its_supporting_facts(tmp_path: Path, drift: str) -> None:
    db = tmp_path / "data.sqlite"
    with _database(db) as conn:
        conn.execute(
            "INSERT INTO character_damage_releases VALUES (?, ?, ?, ?, ?, 1, 1)",
            ("character:a", "npc_protector_weather", "weather:a", "state", "raining"),
        )
        if drift == "disabled":
            conn.execute("UPDATE character_damage_releases SET controller_enabled=0")
        elif drift == "different_mechanism":
            conn.execute("UPDATE character_damage_releases SET mechanism='trade_turn_in'")
        elif drift == "additional_release":
            conn.execute(
                "INSERT INTO character_damage_releases VALUES (?, ?, ?, ?, ?, 1, 1)",
                ("character:a", "npc_protector_null", "automatic:a", "state", "null"),
            )
    graph = _graph()
    graph.out_edges("character:a", EdgeType.DROPS_ITEM)[0].note = "Vulnerable during rain."
    item = "item:missing" if drift == "missing_item" else "item:rain"
    overrides = tmp_path / "notes.toml"
    overrides.write_text(
        "[[source_notes]]\n"
        'source="character:a"\n'
        'mechanism="npc_protector_weather"\n'
        f'items=["{item}"]\n'
        'text="Rain extinguishes the brazier."\n'
    )
    with pytest.raises(ValueError):
        merge_overrides(graph, overrides, db_path=db)
