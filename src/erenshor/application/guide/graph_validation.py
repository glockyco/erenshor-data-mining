"""Graph-level validation and derived metadata calculations.

This module runs after nodes and edges are built. It owns quest zone/level
denormalization and source-level derivation without changing graph shape.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from .node_builder import _zone_display
from .schema import Edge, EdgeType, Node, NodeType

if TYPE_CHECKING:
    from .graph import EntityGraph


def _denormalize_quest_metadata(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """Backfill zone, zone_key, and level on quest nodes.

    Runs after all nodes and edges are built.  Uses graph edges to infer
    the quest's primary zone (from its giver or completer NPC) and
    estimates a recommended level from mob levels and zone medians.

    Level estimation considers the full dependency tree:
    - Kill targets: character accessibility (combat level + unlock requirements)
    - NPC interactions: zone median of the NPC's zone
    - Read targets: item obtainability (OR — any item completes)
    - Required items: item obtainability through crafting chains
    - Turn-in targets: min accessibility across alternatives
    - Quest chains: prerequisite quest levels propagated via topological sort
    - Assignment sources: min zone/item level across alternative givers
    """
    zone_displays = _zone_display(conn)
    zone_medians = _build_zone_medians(conn)
    char_levels = _build_char_levels(conn)
    char_zones = _build_char_zone_keys(conn)

    # Shared caches across all quest estimations
    item_cache: dict[str, int | None] = {}  # item_key → obtainability level
    quest_levels: dict[str, int] = {}  # quest_key → estimated level

    # First pass: zone + direct level factors (no quest-chain propagation)
    for quest in graph.nodes_of_type(NodeType.QUEST):
        _fill_quest_zone(quest, graph, char_zones, zone_displays, zone_medians)
        level = _estimate_quest_level(
            quest,
            graph,
            zone_medians,
            char_levels,
            char_zones,
            quest_levels,
            item_cache,
        )
        if level is not None:
            quest.level = level
            quest_levels[quest.key] = level

    # Second pass: propagate through quest chains (chains_to / rewards_item)
    # Process in topological order so prerequisite levels are available.
    topo = _quest_topological_order(graph)
    for quest_key in topo:
        quest_node = graph.get_node(quest_key)
        if quest_node is None:
            continue
        level = _estimate_quest_level(
            quest_node,
            graph,
            zone_medians,
            char_levels,
            char_zones,
            quest_levels,
            item_cache,
        )
        if level is not None:
            quest_node.level = level
            quest_levels[quest_node.key] = level


def _target_zone_key(
    target_key: str,
    graph: EntityGraph,
    char_zones: dict[str, str],
) -> str | None:
    """Resolve the interaction zone for an edge target.

    Characters use the spawn-derived char_zones map. Other node types fall back
    to their graph node's own zone_key (useful for quest-chain assigned_by).
    """
    zone_key = char_zones.get(target_key)
    if zone_key is not None:
        return zone_key
    target = graph.get_node(target_key)
    return target.zone_key if target is not None else None


def _best_interaction_zone_key(
    target_keys: list[str],
    graph: EntityGraph,
    char_zones: dict[str, str],
    zone_medians: dict[str, int],
) -> str | None:
    """Pick the easiest interaction zone across alternative targets.

    Lower zone median wins. Missing medians sort last. Ties break
    lexicographically by zone key for deterministic output.
    """
    candidates: list[tuple[int, str]] = []
    fallback: list[str] = []
    for target_key in target_keys:
        zone_key = _target_zone_key(target_key, graph, char_zones)
        if zone_key is None:
            continue
        fallback.append(zone_key)
        median = zone_medians.get(zone_key)
        if median is not None:
            candidates.append((median, zone_key))

    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][1]
    if fallback:
        return sorted(fallback)[0]
    return None


def _fill_quest_zone(
    quest: Node,
    graph: EntityGraph,
    char_zones: dict[str, str],
    zone_displays: dict[str, str],
    zone_medians: dict[str, int],
) -> None:
    """Set quest.zone and quest.zone_key from the easiest assignment or turn-in alternative."""
    assign_targets = [edge.target for edge in graph.out_edges(quest.key, EdgeType.ASSIGNED_BY)]
    zone_key = _best_interaction_zone_key(assign_targets, graph, char_zones, zone_medians)
    if zone_key is None:
        complete_targets = [edge.target for edge in graph.out_edges(quest.key, EdgeType.COMPLETED_BY)]
        zone_key = _best_interaction_zone_key(complete_targets, graph, char_zones, zone_medians)

    if zone_key is not None:
        quest.zone_key = zone_key
        quest.zone = zone_displays.get(zone_key, zone_key)


# ---------------------------------------------------------------------------
# Level estimation helpers
# ---------------------------------------------------------------------------


def _estimate_quest_level(
    quest: Node,
    graph: EntityGraph,
    zone_medians: dict[str, int],
    char_levels: dict[str, int],
    char_zones: dict[str, str],
    quest_levels: dict[str, int],
    item_cache: dict[str, int | None],
) -> int | None:
    """Estimate recommended level for a quest.

    Returns the max across all step/requirement level factors,
    or None if no level data is available.  Each factor category
    uses the correct aggregation (OR for alternatives, AND for
    requirements that must all be met).
    """
    factors: list[int] = []
    ctx = _LevelContext(graph, zone_medians, char_levels, char_zones, quest_levels, item_cache)

    # Kill targets (AND — all must die): character accessibility
    for edge in graph.out_edges(quest.key, EdgeType.STEP_KILL):
        lvl = _character_accessibility_level(edge.target, ctx, set())
        if lvl is not None:
            factors.append(lvl)

    # Talk/shout targets (AND): zone median of NPC's zone
    for edge in graph.out_edges(quest.key, EdgeType.STEP_TALK):
        _add_zone_factor(edge.target, char_zones, zone_medians, factors)
    for edge in graph.out_edges(quest.key, EdgeType.STEP_SHOUT):
        _add_zone_factor(edge.target, char_zones, zone_medians, factors)

    # Travel targets (AND): zone median of destination
    # Guide workflow locations use the same zone-median estimate as travel.
    for edge in graph.out_edges(quest.key, EdgeType.STEP_GO_TO):
        target = graph.get_node(edge.target)
        if target and target.zone_key in zone_medians:
            factors.append(zone_medians[target.zone_key])
    for edge in graph.out_edges(quest.key, EdgeType.STEP_TRAVEL):
        target = graph.get_node(edge.target)
        if target and target.key in zone_medians:
            factors.append(zone_medians[target.key])

    # Read targets (OR — reading any one completes): min across alternatives
    read_levels: list[int] = []
    for edge in graph.out_edges(quest.key, EdgeType.STEP_READ):
        lvl = _item_obtainability_level(edge.target, ctx, set())
        if lvl is not None:
            read_levels.append(lvl)
    if read_levels:
        factors.append(min(read_levels))

    # Turn-in targets (OR — any alternative): min accessibility
    completion_levels: list[int] = []
    for edge in graph.out_edges(quest.key, EdgeType.COMPLETED_BY):
        target = graph.get_node(edge.target)
        if target is None:
            continue
        if target.type == NodeType.CHARACTER:
            lvl = _character_accessibility_level(edge.target, ctx, set())
        else:
            zone_key = _target_zone_key(edge.target, graph, char_zones)
            lvl = zone_medians.get(zone_key) if zone_key else None
        if lvl is not None:
            completion_levels.append(lvl)
    if completion_levels:
        factors.append(min(completion_levels))

    # Required items — with variant group support (OR-of-AND)
    _add_required_item_factors(
        quest.key,
        graph,
        ctx,
        factors,
    )

    # Quest chain prerequisites (AND): prerequisite quest levels
    for edge in graph.out_edges(quest.key, EdgeType.CHAINS_TO):
        prereq_level = quest_levels.get(edge.target)
        if prereq_level is not None:
            factors.append(prereq_level)

    # Assignment sources (OR — only need one giver): min across alternatives
    assign_levels: list[int] = []
    for edge in graph.out_edges(quest.key, EdgeType.ASSIGNED_BY):
        if edge.note == "quest_chain":
            # Already handled via CHAINS_TO — skip to avoid double-counting
            continue
        target = graph.get_node(edge.target)
        if target is None:
            continue
        if target.type == NodeType.CHARACTER:
            zone_key = char_zones.get(edge.target)
            lvl = zone_medians.get(zone_key) if zone_key else None
        elif target.type == NodeType.ITEM:
            lvl = _item_obtainability_level(edge.target, ctx, set())
        else:
            lvl = zone_medians.get(target.zone_key) if target.zone_key else None
        if lvl is not None:
            assign_levels.append(lvl)
    if assign_levels:
        factors.append(min(assign_levels))

    if not factors:
        # Fallback: quest giver zone median (for quests with no edges at all)
        if quest.zone_key and quest.zone_key in zone_medians:
            return zone_medians[quest.zone_key]
        return None

    return max(factors)


def _add_required_item_factors(
    quest_key: str,
    graph: EntityGraph,
    ctx: _LevelContext,
    factors: list[int],
) -> None:
    """Add required-item level factors with variant group support.

    Same group = AND (all items needed, max). Different groups = OR
    (any group suffices, min of per-group maxes). Null/empty group is
    treated as a single default group.
    """
    edges = graph.out_edges(quest_key, EdgeType.REQUIRES_ITEM)
    if not edges:
        return

    # Partition edges by group
    groups: dict[str, list[Edge]] = {}
    for edge in edges:
        key = edge.group or ""
        groups.setdefault(key, []).append(edge)

    if len(groups) <= 1:
        # No variant groups — flat AND (each item is a factor)
        for edge in edges:
            lvl = _item_obtainability_level(edge.target, ctx, set())
            if lvl is not None:
                factors.append(lvl)
    else:
        # OR-of-AND: min across groups, max within each group
        group_levels: list[int] = []
        for group_edges in groups.values():
            mat_levels: list[int] = []
            for edge in group_edges:
                lvl = _item_obtainability_level(edge.target, ctx, set())
                if lvl is not None:
                    mat_levels.append(lvl)
            if mat_levels:
                group_levels.append(max(mat_levels))
        if group_levels:
            factors.append(min(group_levels))


class _LevelContext:
    """Shared state threaded through level estimation to avoid long arg lists."""

    __slots__ = ("char_levels", "char_zones", "graph", "item_cache", "quest_levels", "zone_medians")

    def __init__(
        self,
        graph: EntityGraph,
        zone_medians: dict[str, int],
        char_levels: dict[str, int],
        char_zones: dict[str, str],
        quest_levels: dict[str, int],
        item_cache: dict[str, int | None],
    ) -> None:
        self.graph = graph
        self.zone_medians = zone_medians
        self.char_levels = char_levels
        self.char_zones = char_zones
        self.quest_levels = quest_levels
        self.item_cache = item_cache


def _item_obtainability_level(
    item_key: str,
    ctx: _LevelContext,
    visiting: set[str],
) -> int | None:
    """Min level at which an item is obtainable across all sources.

    Sources: drops_item, sells_item, gives_item, yields_item (water/mining),
    rewards_item (quest reward), produces (crafting — recursive).

    Uses memoization (ctx.item_cache) and cycle detection (visiting set).
    Multiple sources are alternatives (OR) — returns min across all.
    Crafting requires ALL ingredients (AND) — uses max within a recipe.
    """
    if item_key in ctx.item_cache:
        return ctx.item_cache[item_key]
    if item_key in visiting:
        return None  # cycle — break without caching

    visiting.add(item_key)
    source_levels: list[int] = []

    for edge in ctx.graph.in_edges(item_key):
        if edge.type == EdgeType.DROPS_ITEM:
            # Kill the mob: character accessibility (combat + unlock reqs)
            lvl = _character_accessibility_level(edge.source, ctx, visiting)
            if lvl is not None:
                source_levels.append(lvl)

        elif edge.type in (EdgeType.SELLS_ITEM, EdgeType.GIVES_ITEM):
            # Visit the vendor/NPC: zone median
            zone_key = ctx.char_zones.get(edge.source)
            if zone_key and zone_key in ctx.zone_medians:
                source_levels.append(ctx.zone_medians[zone_key])

        elif edge.type == EdgeType.YIELDS_ITEM:
            # Gather from water/mining node: zone median
            source_node = ctx.graph.get_node(edge.source)
            if source_node and source_node.zone_key and source_node.zone_key in ctx.zone_medians:
                source_levels.append(ctx.zone_medians[source_node.zone_key])

        elif edge.type == EdgeType.REWARDS_ITEM:
            # Quest reward: rewarding quest's level
            ql = ctx.quest_levels.get(edge.source)
            if ql is not None:
                source_levels.append(ql)

        elif edge.type == EdgeType.PRODUCES:
            # Crafting: recipe produces this item.
            # Need ALL materials → max(ingredient obtainability levels).
            recipe_key = edge.source
            mat_levels: list[int] = []
            for mat_edge in ctx.graph.out_edges(recipe_key, EdgeType.REQUIRES_MATERIAL):
                mat_lvl = _item_obtainability_level(mat_edge.target, ctx, visiting)
                if mat_lvl is not None:
                    mat_levels.append(mat_lvl)
            if mat_levels:
                source_levels.append(max(mat_levels))

    visiting.discard(item_key)
    result = min(source_levels) if source_levels else None
    # Only cache definitive results.  None means "no sources found yet" and
    # may become resolvable in the second pass once more quest levels are known
    # (e.g., an item is only obtainable as a quest reward).
    if result is not None:
        ctx.item_cache[item_key] = result
    return result


def _character_accessibility_level(
    char_key: str,
    ctx: _LevelContext,
    visiting: set[str],
) -> int | None:
    """Level to access a character: combat level plus unlock requirements.

    Base: max(char_level, zone_median) — the existing combat factor.
    Plus: if the character has incoming UNLOCKS_CHARACTER edges, include
    the cost of satisfying those unlock requirements.
    """
    base = _character_level_factor(
        char_key,
        ctx.char_levels,
        ctx.char_zones,
        ctx.zone_medians,
    )
    unlock = _unlock_requirement_level(
        char_key,
        EdgeType.UNLOCKS_CHARACTER,
        ctx,
        visiting,
    )
    if base is not None and unlock is not None:
        return max(base, unlock)
    return base if base is not None else unlock


def _unlock_requirement_level(
    target_key: str,
    edge_type: EdgeType,
    ctx: _LevelContext,
    visiting: set[str],
) -> int | None:
    """Level to satisfy unlock requirements on a target node.

    Uses OR-of-AND group semantics:
    - Same group = AND: all sources in the group must be obtained → max
    - Different groups = OR: any group suffices → min across groups
    - Null group = unconditional standalone source
    """
    edges = ctx.graph.in_edges(target_key, edge_type)
    if not edges:
        return None

    # Partition by group. Null-group edges are standalone (each is its own group).
    unconditional: list[int] = []
    groups: dict[str, list[Edge]] = {}
    for edge in edges:
        if edge.group is None:
            source = ctx.graph.get_node(edge.source)
            if source is None:
                continue
            lvl = _unlock_source_level(source, ctx, visiting)
            if lvl is not None:
                unconditional.append(lvl)
        else:
            groups.setdefault(edge.group, []).append(edge)

    # Each named group is AND (max within), groups are OR (min across)
    group_levels: list[int] = []
    for group_edges in groups.values():
        and_levels: list[int] = []
        for edge in group_edges:
            source = ctx.graph.get_node(edge.source)
            if source is None:
                continue
            lvl = _unlock_source_level(source, ctx, visiting)
            if lvl is not None:
                and_levels.append(lvl)
        if and_levels:
            group_levels.append(max(and_levels))

    # Combine: unconditional sources are standalone alternatives
    all_alternatives = unconditional + group_levels
    return min(all_alternatives) if all_alternatives else None


def _unlock_source_level(
    source: Node,
    ctx: _LevelContext,
    visiting: set[str],
) -> int | None:
    """Level contributed by a single unlock source (item or quest)."""
    if source.type == NodeType.ITEM:
        return _item_obtainability_level(source.key, ctx, visiting)
    if source.type == NodeType.QUEST:
        return ctx.quest_levels.get(source.key)
    return None


def _character_level_factor(
    char_key: str,
    char_levels: dict[str, int],
    char_zones: dict[str, str],
    zone_medians: dict[str, int],
) -> int | None:
    """Level to fight a character: max(char_level, zone_median)."""
    char_level = char_levels.get(char_key)
    zone_key = char_zones.get(char_key)
    zone_med = zone_medians.get(zone_key) if zone_key else None

    if char_level is not None and zone_med is not None:
        return max(char_level, zone_med)
    return char_level or zone_med


def _add_zone_factor(
    char_key: str,
    char_zones: dict[str, str],
    zone_medians: dict[str, int],
    factors: list[int],
) -> None:
    """Append a zone-median factor for a character's zone."""
    zone_key = char_zones.get(char_key)
    if zone_key and zone_key in zone_medians:
        factors.append(zone_medians[zone_key])


def _quest_topological_order(graph: EntityGraph) -> list[str]:
    """Topologically sort quests by chains_to and quest-reward dependencies.

    A quest depends on another when:
    - It has a chains_to edge to the other quest
    - A required item has a rewards_item edge from another quest
    """
    from collections import deque

    quest_keys = [n.key for n in graph.nodes_of_type(NodeType.QUEST) if not n.guide_only]
    quest_set = set(quest_keys)
    in_degree: dict[str, int] = dict.fromkeys(quest_keys, 0)
    dependents: dict[str, list[str]] = {k: [] for k in quest_keys}

    for qk in quest_keys:
        seen: set[str] = set()
        # chains_to dependencies
        for edge in graph.out_edges(qk, EdgeType.CHAINS_TO):
            if edge.target in quest_set and edge.target not in seen:
                seen.add(edge.target)
                in_degree[qk] += 1
                dependents[edge.target].append(qk)

        # Quest-reward item dependencies: if a required item is only
        # obtainable via quest reward, that quest is a dependency.
        for req_edge in graph.out_edges(qk, EdgeType.REQUIRES_ITEM):
            for src_edge in graph.in_edges(req_edge.target, EdgeType.REWARDS_ITEM):
                if src_edge.source in quest_set and src_edge.source not in seen:
                    seen.add(src_edge.source)
                    in_degree[qk] += 1
                    dependents[src_edge.source].append(qk)

    queue: deque[str] = deque(k for k, d in in_degree.items() if d == 0)
    result: list[str] = []
    while queue:
        k = queue.popleft()
        result.append(k)
        for dep in dependents[k]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    # Append any cyclic quests at the end
    if len(result) < len(quest_keys):
        result.extend(k for k in quest_keys if k not in set(result))

    return result


def _denormalize_zone_and_source_levels(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """Set level on zone nodes (median enemy level) and on non-combat source
    nodes (water, mining, item bag) to their zone's median.

    This makes zone difficulty a first-class property in the graph, available
    to any consumer without recomputing from character spawns.
    """
    zone_medians = _build_zone_medians(conn)

    # Set level on zone nodes
    for zone_key, median_level in zone_medians.items():
        node = graph.get_node(zone_key)
        if node is not None:
            node.level = median_level

    # Set level on non-combat source nodes from their zone's median
    for node_type in (NodeType.WATER, NodeType.MINING_NODE, NodeType.ITEM_BAG):
        for node in graph.nodes_of_type(node_type):
            if node.level is None and node.zone_key is not None:
                median = zone_medians.get(node.zone_key)
                if median is not None:
                    node.level = median


def _build_zone_medians(conn: sqlite3.Connection) -> dict[str, int]:
    """Compute zone median mob level: {zone_key → median_level}.

    Only non-friendly characters with level > 0 contribute.
    """
    from statistics import median

    rows = conn.execute("""
        SELECT cs.zone_stable_key, c.level
        FROM character_spawns cs
        JOIN characters c ON cs.character_stable_key = c.stable_key
        WHERE c.is_friendly = 0 AND c.level > 0 AND c.is_map_visible = 1
            AND cs.spawn_point_stable_key IS NOT NULL
    """).fetchall()
    zone_levels: dict[str, list[int]] = {}
    for r in rows:
        zk = r["zone_stable_key"]
        if zk:
            zone_levels.setdefault(zk, []).append(r["level"])
    return {zk: int(median(levels)) for zk, levels in zone_levels.items()}


def _build_char_levels(conn: sqlite3.Connection) -> dict[str, int]:
    """Return {character_key → level} for non-friendly characters with level > 0."""
    rows = conn.execute(
        "SELECT stable_key, level FROM characters WHERE level > 0 AND is_friendly = 0 AND is_map_visible = 1"
    ).fetchall()
    return {r["stable_key"]: r["level"] for r in rows}


def _build_char_zone_keys(conn: sqlite3.Connection) -> dict[str, str]:
    """Return {character_key → zone_key} picking the first spawn's zone.

    Includes all characters (friendly and hostile) — quest givers are friendly.
    """
    rows = conn.execute("""
        SELECT cs.character_stable_key, cs.zone_stable_key
        FROM character_spawns cs
        WHERE cs.zone_stable_key IS NOT NULL
            AND cs.spawn_point_stable_key IS NOT NULL
        GROUP BY cs.character_stable_key
    """).fetchall()
    return {r["character_stable_key"]: r["zone_stable_key"] for r in rows}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
