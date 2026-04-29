"""Integration tests for the guide compiler and JSON serializer.

Runs against the real SQLite database to verify:
- CompiledData structural invariants
- Topological order correctness
- JSON serialization integrity for the compiled guide contract

All tests skip if the database is not available.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from erenshor.application.guide.json_writer import serialize

if TYPE_CHECKING:
    from erenshor.application.guide.compiler import CompiledData
    from erenshor.application.guide.graph import EntityGraph


EXPECTED_TOP_LEVEL_KEYS = {
    "nodes",
    "edges",
    "node_keys",
    "node_levels",
    "node_key_to_id",
    "node_quest_index",
    "node_item_index",
    "quest_node_ids",
    "item_node_ids",
    "forward_adjacency",
    "reverse_adjacency",
    "quest_specs",
    "item_sources",
    "unlock_predicates",
    "topo_order",
    "quest_to_dependent_quest_indices",
    "zone_node_ids",
    "zone_adjacency",
    "zone_line_ids",
    "giver_blueprints",
    "completion_blueprints",
    "infeasible_node_ids",
    "detail_goals",
    "detail_dependencies",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def graph(integration_db: Path) -> EntityGraph:
    from erenshor.application.guide.generator import generate

    overrides = Path("quest_guides/graph_overrides.toml")
    return generate(integration_db, overrides if overrides.exists() else None)


@pytest.fixture(scope="module")
def compiled(graph: EntityGraph) -> CompiledData:
    from erenshor.application.guide.compiler import compile_graph

    return compile_graph(graph)


@pytest.fixture(scope="module")
def serialized(compiled: CompiledData) -> dict[str, object]:
    return json.loads(serialize(compiled))


# ---------------------------------------------------------------------------
# Structural invariants on CompiledData
# ---------------------------------------------------------------------------


class TestCompiledDataInvariants:
    """Verify CompiledData is internally consistent."""

    def test_quest_count(self, compiled: CompiledData) -> None:
        assert len(compiled.quest_node_ids) >= 165, f"Expected 165+ quests, got {len(compiled.quest_node_ids)}"

    def test_item_count(self, compiled: CompiledData) -> None:
        assert len(compiled.item_node_ids) >= 1300, f"Expected 1300+ items, got {len(compiled.item_node_ids)}"

    def test_zone_count(self, compiled: CompiledData) -> None:
        assert len(compiled.zone_node_ids) >= 40, f"Expected 40+ zones, got {len(compiled.zone_node_ids)}"

    def test_node_id_range(self, compiled: CompiledData) -> None:
        """All node IDs fit in u16-compatible ranges used by downstream consumers."""
        n = len(compiled.node_keys)
        assert n <= 65535, f"Node count {n} exceeds u16 max"

    def test_node_levels_non_negative(self, compiled: CompiledData) -> None:
        """node_levels must all be >= 0 (bug fix: -1 values are clamped)."""
        negatives = [(i, lvl) for i, lvl in enumerate(compiled.node_levels) if lvl < 0]
        assert not negatives, f"Negative levels at node IDs: {negatives[:5]}"

    def test_dense_quest_index_roundtrip(self, compiled: CompiledData) -> None:
        """node_quest_index is the exact inverse of quest_node_ids."""
        for qi, nid in enumerate(compiled.quest_node_ids):
            assert compiled.node_quest_index[nid] == qi, f"Quest index roundtrip failed at qi={qi}, nid={nid}"

    def test_dense_item_index_roundtrip(self, compiled: CompiledData) -> None:
        """node_item_index is the exact inverse of item_node_ids."""
        for ii, nid in enumerate(compiled.item_node_ids):
            assert compiled.node_item_index[nid] == ii, f"Item index roundtrip failed at ii={ii}, nid={nid}"

    def test_quest_specs_count(self, compiled: CompiledData) -> None:
        """One QuestSpec per quest node."""
        assert len(compiled.quest_specs) == len(compiled.quest_node_ids)

    def test_item_sources_count(self, compiled: CompiledData) -> None:
        """One item_sources entry per item node."""
        assert len(compiled.item_sources) == len(compiled.item_node_ids)

    def test_topo_order_covers_all_quests(self, compiled: CompiledData) -> None:
        """topo_order contains every quest index exactly once."""
        expected = set(range(len(compiled.quest_node_ids)))
        actual = set(compiled.topo_order)
        assert actual == expected, f"topo_order missing: {expected - actual}; extra: {actual - expected}"

    def test_reverse_deps_counts(self, compiled: CompiledData) -> None:
        """quest_to_dependent_quest_indices is sized correctly."""
        assert len(compiled.quest_to_dependent_quest_indices) == len(compiled.quest_node_ids)

    def test_quest_spec_prereq_indices_valid(self, compiled: CompiledData) -> None:
        """All prereq_quest_indices in every QuestSpec are valid quest indices."""
        q = len(compiled.quest_node_ids)
        for qi, spec in enumerate(compiled.quest_specs):
            for prereq_qi in spec.prereq_quest_indices:
                assert 0 <= prereq_qi < q, f"QuestSpec[{qi}] has invalid prereq index {prereq_qi}"

    def test_quest_spec_giver_node_ids_valid(self, compiled: CompiledData) -> None:
        """All giver_node_ids in every QuestSpec are valid global node IDs."""
        n = len(compiled.node_keys)
        for qi, spec in enumerate(compiled.quest_specs):
            for nid in spec.giver_node_ids:
                assert 0 <= nid < n, f"QuestSpec[{qi}] has invalid giver node ID {nid}"


# ---------------------------------------------------------------------------
# Topological order correctness
# ---------------------------------------------------------------------------


class TestTopologicalOrder:
    """Verify that the Kahn's-based topo sort is correct."""

    def test_prereqs_before_dependents(self, compiled: CompiledData) -> None:
        """For every quest with prerequisites, every prereq appears before it
        in topo_order. This is the core soundness property of the topo sort.
        """
        position = {qi: pos for pos, qi in enumerate(compiled.topo_order)}
        violations: list[str] = []

        for qi, spec in enumerate(compiled.quest_specs):
            if spec.is_infeasible:
                continue
            for prereq_qi in spec.prereq_quest_indices:
                prereq_spec = compiled.quest_specs[prereq_qi]
                if prereq_spec.is_infeasible:
                    continue
                if position[prereq_qi] >= position[qi]:
                    violations.append(
                        f"prereq qi={prereq_qi} ({prereq_spec.display_name!r}) "
                        f"appears at pos {position[prereq_qi]}, "
                        f"after qi={qi} ({spec.display_name!r}) at pos {position[qi]}"
                    )

        assert not violations, f"Topo order violations ({len(violations)}): {violations[:5]}"

    def test_infeasible_quests_present(self, compiled: CompiledData) -> None:
        """Infeasible quests are still present in topo_order."""
        topo_set = set(compiled.topo_order)
        infeasible_indices = [
            compiled.node_quest_index[nid]
            for nid in compiled.infeasible_node_ids
            if compiled.node_quest_index[nid] != -1
        ]
        for qi in infeasible_indices:
            assert qi in topo_set, f"Infeasible quest index {qi} missing from topo_order"


# ---------------------------------------------------------------------------
# JSON serialization integrity
# ---------------------------------------------------------------------------


class TestJsonSerialization:
    """Verify the serialized JSON stays aligned with compiled guide data."""

    def test_top_level_keys_match_contract(self, serialized: dict[str, object]) -> None:
        assert set(serialized.keys()) == EXPECTED_TOP_LEVEL_KEYS

    def test_serialized_counts_match_compiled(self, serialized: dict[str, object], compiled: CompiledData) -> None:
        assert len(serialized["nodes"]) == len(compiled.nodes)
        assert len(serialized["edges"]) == len(compiled.edges)
        assert len(serialized["quest_node_ids"]) == len(compiled.quest_node_ids)
        assert len(serialized["item_node_ids"]) == len(compiled.item_node_ids)
        assert len(serialized["zone_node_ids"]) == len(compiled.zone_node_ids)
        assert len(serialized["quest_specs"]) == len(compiled.quest_specs)
        assert len(serialized["completion_blueprints"]) == len(compiled.completion_blueprints)

    def test_serialized_node_key_map_roundtrips_real_quest(
        self, serialized: dict[str, object], compiled: CompiledData
    ) -> None:
        quest_id = compiled.node_key_to_id["quest:meetbassle"]
        quest_node = serialized["nodes"][quest_id]

        assert serialized["node_key_to_id"]["quest:meetbassle"] == quest_id
        assert serialized["node_keys"][quest_id] == "quest:meetbassle"
        assert quest_node["key"] == "quest:meetbassle"
        assert quest_node["display_name"] == "Meet the Fisherman"

    def test_serialized_completion_blueprints_keep_real_talk_keyword(
        self, serialized: dict[str, object], compiled: CompiledData
    ) -> None:
        quest_id = compiled.node_key_to_id["quest:meetbassle"]
        character_id = compiled.node_key_to_id["character:bassle wavebreak"]

        assert {
            "quest_id": quest_id,
            "character_id": character_id,
            "position_id": next(
                blueprint.position_id
                for blueprint in compiled.completion_blueprints
                if blueprint.quest_id == quest_id and blueprint.character_id == character_id
            ),
            "interaction_type": 1,
            "keyword": "taking",
        } in serialized["completion_blueprints"]
