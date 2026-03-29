"""Integration tests for the entity graph pipeline.

Tests run against the real clean SQLite database.  They verify that the
graph builder produces the expected node/edge counts and captures known
relationships from the game data.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import pytest

from erenshor.application.guide.graph_builder import build_graph
from erenshor.application.guide.schema import EdgeType, NodeType

if TYPE_CHECKING:
    from erenshor.application.guide.graph import EntityGraph


@pytest.fixture(scope="module")
def graph(integration_db: Path) -> EntityGraph:
    """Build the entity graph once for the entire test module."""
    return build_graph(integration_db)


# ---------------------------------------------------------------------------
# Structural tests — node counts by type
# ---------------------------------------------------------------------------


class TestNodeCounts:
    """Verify the graph contains expected entity counts."""

    def test_has_quest_nodes(self, graph: EntityGraph) -> None:
        quests = list(graph.nodes_of_type(NodeType.QUEST))
        assert len(quests) >= 170, f"Expected 170+ quests, got {len(quests)}"

    def test_has_item_nodes(self, graph: EntityGraph) -> None:
        items = list(graph.nodes_of_type(NodeType.ITEM))
        assert len(items) >= 1300, f"Expected 1300+ items, got {len(items)}"

    def test_has_character_nodes(self, graph: EntityGraph) -> None:
        chars = list(graph.nodes_of_type(NodeType.CHARACTER))
        assert len(chars) >= 900, f"Expected 900+ characters, got {len(chars)}"

    def test_has_zone_nodes(self, graph: EntityGraph) -> None:
        zones = list(graph.nodes_of_type(NodeType.ZONE))
        assert len(zones) >= 40, f"Expected 40+ zones, got {len(zones)}"

    def test_has_spawn_point_nodes(self, graph: EntityGraph) -> None:
        spawns = list(graph.nodes_of_type(NodeType.SPAWN_POINT))
        assert len(spawns) >= 3000, f"Expected 3000+ spawn points, got {len(spawns)}"

    def test_has_zone_line_nodes(self, graph: EntityGraph) -> None:
        zls = list(graph.nodes_of_type(NodeType.ZONE_LINE))
        assert len(zls) >= 120, f"Expected 120+ zone lines, got {len(zls)}"

    def test_has_mining_node_nodes(self, graph: EntityGraph) -> None:
        nodes = list(graph.nodes_of_type(NodeType.MINING_NODE))
        assert len(nodes) >= 100, f"Expected 100+ mining nodes, got {len(nodes)}"

    def test_has_recipe_nodes(self, graph: EntityGraph) -> None:
        recipes = list(graph.nodes_of_type(NodeType.RECIPE))
        assert len(recipes) >= 15, f"Expected 15+ recipes, got {len(recipes)}"

    def test_has_faction_nodes(self, graph: EntityGraph) -> None:
        factions = list(graph.nodes_of_type(NodeType.FACTION))
        assert len(factions) >= 20, f"Expected 20+ factions, got {len(factions)}"

    def test_total_nodes(self, graph: EntityGraph) -> None:
        assert graph.node_count >= 7000, f"Expected 7000+ nodes, got {graph.node_count}"

    def test_total_edges(self, graph: EntityGraph) -> None:
        assert graph.edge_count >= 20000, f"Expected 20000+ edges, got {graph.edge_count}"


# ---------------------------------------------------------------------------
# Edge type coverage — every edge type has at least one edge
# ---------------------------------------------------------------------------


class TestEdgeTypeCoverage:
    """Verify every EdgeType is represented in the graph."""

    # Edge types not produced by build_graph alone:
    # - ENABLES_INTERACTION, REMOVES_INVULNERABILITY: manual overrides only
    # - REQUIRES_QUEST: no prerequisite table in DB; the C# mod derives
    #   quest prerequisites by traversing item/character unlock chains
    # - PROTECTS: no protector data in clean DB; comes from overrides
    _NOT_FROM_DB: ClassVar[set[EdgeType]] = {
        EdgeType.ENABLES_INTERACTION,
        EdgeType.REMOVES_INVULNERABILITY,
        EdgeType.REQUIRES_QUEST,
        EdgeType.PROTECTS,
    }

    @pytest.mark.parametrize("edge_type", list(EdgeType))
    def test_edge_type_present(self, graph: EntityGraph, edge_type: EdgeType) -> None:
        if edge_type in self._NOT_FROM_DB:
            pytest.skip(f"{edge_type.value} not produced from DB data alone")
        edges = [e for e in graph.all_edges() if e.type == edge_type]
        assert len(edges) > 0, f"No edges of type {edge_type.value}"


# ---------------------------------------------------------------------------
# Specific known relationships
# ---------------------------------------------------------------------------


class TestAnglerRingChain:
    """Verify the Angler's Ring quest and its full crafting chain."""

    def test_quest_exists(self, graph: EntityGraph) -> None:
        node = graph.get_node("quest:anglerring")
        assert node is not None
        assert node.display_name == "The Angler's Ring"

    def test_requires_item(self, graph: EntityGraph) -> None:
        edges = graph.out_edges("quest:anglerring", EdgeType.REQUIRES_ITEM)
        assert len(edges) == 1
        assert edges[0].target == "item:ring - 6 - angler's ring"
        assert edges[0].quantity == 1

    def test_completed_by_liani(self, graph: EntityGraph) -> None:
        edges = graph.out_edges("quest:anglerring", EdgeType.COMPLETED_BY)
        assert any("liani bosh" in e.target for e in edges)

    def test_item_crafted_from_recipe(self, graph: EntityGraph) -> None:
        edges = graph.out_edges("item:ring - 6 - angler's ring", EdgeType.CRAFTED_FROM)
        assert len(edges) == 1
        recipe_key = edges[0].target
        assert recipe_key.startswith("recipe:")

    def test_recipe_has_materials(self, graph: EntityGraph) -> None:
        edges = graph.out_edges("item:ring - 6 - angler's ring", EdgeType.CRAFTED_FROM)
        recipe_key = edges[0].target
        materials = graph.out_edges(recipe_key, EdgeType.REQUIRES_MATERIAL)
        # 4 ingredients + 1 mold (template item consumed in Smithing.DoSuccess)
        assert len(materials) == 5, f"Expected 5 materials (4 ingredients + mold), got {len(materials)}"

    def test_recipe_includes_mold_as_material(self, graph: EntityGraph) -> None:
        """The template item (mold) must appear as a required material of its recipe.

        Smithing.DoSuccess() sets Template.MyItem = Empty on a successful craft,
        confirming the mold is consumed like any other ingredient.
        """
        edges = graph.out_edges("item:ring - 6 - angler's ring", EdgeType.CRAFTED_FROM)
        recipe_key = edges[0].target
        materials = graph.out_edges(recipe_key, EdgeType.REQUIRES_MATERIAL)
        mold_key = recipe_key[len("recipe:") :]  # template item key = recipe key minus prefix
        assert any(m.target == mold_key for m in materials), (
            f"Recipe {recipe_key} must include its template item {mold_key} as a required material"
        )

    def test_mold_from_liani(self, graph: EntityGraph) -> None:
        """Liani Bosh gives the mold via dialog."""
        edges = [
            e
            for e in graph.all_edges()
            if e.type == EdgeType.GIVES_ITEM and "liani bosh" in e.source and "template" in e.target
        ]
        assert len(edges) == 1

    def test_unlocks_bassle(self, graph: EntityGraph) -> None:
        edges = graph.out_edges("quest:anglerring", EdgeType.UNLOCKS_CHARACTER)
        assert any("bassle" in e.target for e in edges)

    def test_is_implicit(self, graph: EntityGraph) -> None:
        """Angler's Ring has no acquisition source — it's implicit."""
        node = graph.get_node("quest:anglerring")
        assert node is not None
        assert node.implicit is True


class TestImplicitQuests:
    """Verify implicit quest detection."""

    def test_implicit_count(self, graph: EntityGraph) -> None:
        implicit = [n for n in graph.nodes_of_type(NodeType.QUEST) if n.implicit]
        total = list(graph.nodes_of_type(NodeType.QUEST))
        # At least 30% of quests should be implicit based on game data
        ratio = len(implicit) / len(total)
        assert ratio > 0.3, f"Only {len(implicit)}/{len(total)} quests implicit ({ratio:.0%})"

    def test_quest_with_giver_is_explicit(self, graph: EntityGraph) -> None:
        """A quest with an assigned_by edge should not be implicit."""
        node = graph.get_node("quest:goodsoil")
        assert node is not None
        assert node.implicit is False
        # Verify it actually has an assigned_by edge
        edges = graph.out_edges("quest:goodsoil", EdgeType.ASSIGNED_BY)
        assert len(edges) > 0


class TestZoneLineGating:
    """Verify zone line quest gating edges."""

    def test_stowaway_to_hidden_gated(self, graph: EntityGraph) -> None:
        """The Stowaway→Hidden zone line is gated by quests."""
        zl_key = "zoneline:stowaway:hidden:424.04:10.79:820.42"
        gate_edges = graph.out_edges(zl_key, EdgeType.GATED_BY_QUEST)
        assert len(gate_edges) > 0, "Expected gating edges on Stowaway→Hidden zone line"

    def test_gate_edges_have_groups(self, graph: EntityGraph) -> None:
        """Zone line gate edges should have group for AND/OR semantics."""
        gate_edges = [e for e in graph.all_edges() if e.type == EdgeType.GATED_BY_QUEST]
        with_group = [e for e in gate_edges if e.group is not None]
        assert len(with_group) > 0, "Expected some gate edges to have groups"


class TestCharacterSpawns:
    """Verify character ↔ spawn_point edges."""

    def test_character_has_spawn_edges(self, graph: EntityGraph) -> None:
        has_spawn = [e for e in graph.all_edges() if e.type == EdgeType.HAS_SPAWN]
        assert len(has_spawn) >= 5000, f"Expected 5000+ HAS_SPAWN edges, got {len(has_spawn)}"

    def test_spawn_has_character_edges(self, graph: EntityGraph) -> None:
        spawns_char = [e for e in graph.all_edges() if e.type == EdgeType.SPAWNS_CHARACTER]
        assert len(spawns_char) >= 5000, f"Expected 5000+ SPAWNS_CHARACTER edges, got {len(spawns_char)}"


class TestMultiVariantQuests:
    """Verify OR-grouped required items for multi-variant quests."""

    def test_disarm_sivakayans_has_or_groups(self, graph: EntityGraph) -> None:
        edges = graph.out_edges("quest:disarmsivakayans", EdgeType.REQUIRES_ITEM)
        assert len(edges) == 3, f"Expected 3 variant items, got {len(edges)}"
        groups = {e.group for e in edges}
        # Each variant has its own group
        assert len(groups) == 3, f"Expected 3 distinct groups, got {groups}"
        # No None groups — all should be grouped
        assert None not in groups, "Multi-variant items should all have group keys"


class TestAcquisitionMethods:
    """Verify all 6 acquisition methods produce edges."""

    def test_dialog_acquisition(self, graph: EntityGraph) -> None:
        """Dialog-based quest assignment."""
        edges = graph.out_edges("quest:goodsoil", EdgeType.ASSIGNED_BY)
        assert len(edges) > 0

    def test_quest_chain_acquisition(self, graph: EntityGraph) -> None:
        """Quest chain auto-assignment has ASSIGNED_BY with quest_chain note."""
        assigned = [e for e in graph.all_edges() if e.type == EdgeType.ASSIGNED_BY and e.note == "quest_chain"]
        assert len(assigned) >= 20, f"Expected 20+ quest_chain assignments, got {len(assigned)}"

    def test_item_read_acquisition(self, graph: EntityGraph) -> None:
        """Item-read quest assignment."""
        assigned = [e for e in graph.all_edges() if e.type == EdgeType.ASSIGNED_BY and e.note == "item_read"]
        assert len(assigned) >= 10, f"Expected 10+ item_read assignments, got {len(assigned)}"
