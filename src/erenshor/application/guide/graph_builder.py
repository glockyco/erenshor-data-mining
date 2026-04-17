"""Build the entity graph from the clean SQLite database.

One function per entity type (nodes), one per relationship (edges).
The graph builder is the sole consumer of the database for the guide
pipeline.  Everything the C# mod needs is encoded as nodes and edges.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .graph import EntityGraph
from .schema import Edge, EdgeType, Node, NodeType


def build_graph(db_path: Path) -> EntityGraph:
    """Build the full entity graph from the clean SQLite DB."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    graph = EntityGraph()

    # Zone lookup needed by multiple builders for scene → zone resolution
    scene_to_zone = _build_scene_to_zone(conn)

    # --- Entity nodes ---
    _add_quest_nodes(conn, graph)
    _add_item_nodes(conn, graph)
    _add_character_nodes(conn, graph, scene_to_zone)
    _add_zone_nodes(conn, graph)
    _add_zone_line_nodes(conn, graph, scene_to_zone)
    _add_spawn_point_nodes(conn, graph, scene_to_zone)
    _add_mining_node_nodes(conn, graph, scene_to_zone)
    _add_water_nodes(conn, graph, scene_to_zone)
    _add_forge_nodes(conn, graph, scene_to_zone)
    _add_item_bag_nodes(conn, graph, scene_to_zone)
    _add_recipe_nodes(conn, graph)
    _add_door_nodes(conn, graph, scene_to_zone)
    _add_faction_nodes(conn, graph)
    _add_spell_nodes(conn, graph)
    _add_skill_nodes(conn, graph)
    _add_teleport_nodes(conn, graph, scene_to_zone)
    _add_achievement_trigger_nodes(conn, graph, scene_to_zone)
    _add_secret_passage_nodes(conn, graph, scene_to_zone)
    _add_wishing_well_nodes(conn, graph, scene_to_zone)
    _add_treasure_location_nodes(conn, graph, scene_to_zone)
    _add_book_nodes(conn, graph)
    _add_class_nodes(conn, graph)
    _add_stance_nodes(conn, graph)
    _add_ascension_nodes(conn, graph)

    # --- Relationship edges ---
    _add_quest_acquisition_edges(conn, graph)
    _add_quest_completion_edges(conn, graph)
    _add_quest_required_item_edges(conn, graph)
    _add_quest_chain_edges(conn, graph)
    _add_quest_also_completes_edges(conn, graph)
    _add_quest_reward_edges(conn, graph)
    _add_quest_faction_edges(conn, graph)
    _add_quest_unlock_zone_line_edges(conn, graph)
    _add_quest_unlock_character_edges(conn, graph)
    _add_quest_step_edges(conn, graph)
    _add_quest_dialog_prerequisite_edges(conn, graph)
    _add_character_drop_edges(conn, graph)
    _add_character_vendor_edges(conn, graph)
    _add_vendor_quest_unlock_edges(conn, graph)
    _add_character_dialog_give_edges(conn, graph)
    _add_character_spawn_edges(conn, graph)
    _add_character_faction_edges(conn, graph)
    _add_spawn_point_gate_edges(conn, graph)
    _add_spawn_point_stop_edges(conn, graph)
    _add_spawn_point_protector_edges(conn, graph)
    _add_zone_line_connect_edges(conn, graph)
    _add_zone_connect_edges(conn, graph, scene_to_zone)
    _add_zone_contain_edges(conn, graph, scene_to_zone)
    _add_mining_yield_edges(conn, graph)
    _add_water_yield_edges(conn, graph)
    _add_item_bag_yield_edges(conn, graph)
    _add_crafting_edges(conn, graph)
    _add_item_craft_edges(conn, graph)
    _add_item_quest_edges(conn, graph)
    _add_item_spell_edges(conn, graph)
    _add_item_door_edges(conn, graph)

    # --- Denormalization (zone/source levels only) ---
    # Quest metadata denormalization runs later, after graph overrides are
    # merged, so that manual unlock/gate edges affect level estimation.
    graph.build_indexes()
    _denormalize_zone_and_source_levels(conn, graph)

    conn.close()
    return graph


def denormalize_quest_metadata(graph: EntityGraph, db_path: Path) -> None:
    """Public entry point for quest zone + level denormalization.

    Must be called AFTER graph overrides are merged, so that manual
    unlock edges (unlocks_character, unlocks_zone_line) are visible
    to the level estimation algorithm.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _denormalize_quest_metadata(conn, graph)
    conn.close()


# ---------------------------------------------------------------------------
# Quest metadata denormalization (zone + level)
# ---------------------------------------------------------------------------


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

    quest_keys = [n.key for n in graph.nodes_of_type(NodeType.QUEST)]
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


def _build_scene_to_zone(conn: sqlite3.Connection) -> dict[str, str]:
    """Map scene name → zone stable key for scene→zone resolution."""
    rows = conn.execute("SELECT stable_key, scene_name FROM zones WHERE scene_name IS NOT NULL")
    return {r["scene_name"]: r["stable_key"] for r in rows}


def _zone_display(conn: sqlite3.Connection) -> dict[str, str]:
    """Map zone stable key → display name."""
    rows = conn.execute("SELECT stable_key, display_name FROM zones")
    return {r["stable_key"]: r["display_name"] for r in rows}


def _resolve_zone(scene: str | None, scene_to_zone: dict[str, str]) -> str | None:
    """Resolve a scene name to a zone stable key, or None."""
    if scene is None:
        return None
    return scene_to_zone.get(scene)


def _zone_display_name(
    zone_key: str | None,
    zone_displays: dict[str, str],
    fallback: str | None = None,
) -> str | None:
    """Resolve zone key to display name, with optional fallback."""
    if zone_key is not None:
        name = zone_displays.get(zone_key)
        if name is not None:
            return name
    return fallback


# ---------------------------------------------------------------------------
# Node builders
# ---------------------------------------------------------------------------


def _add_quest_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    # Determine which quests are implicitly completable (no acquisition source).
    # A quest with no row in quest_acquisition_sources AND no 'giver' role in
    # quest_character_roles can be completed without formal acceptance.
    explicit_quests: set[str] = set()
    for r in conn.execute("SELECT DISTINCT quest_stable_key FROM quest_acquisition_sources"):
        explicit_quests.add(r["quest_stable_key"])
    for r in conn.execute("SELECT DISTINCT quest_stable_key FROM quest_character_roles WHERE role = 'giver'"):
        explicit_quests.add(r["quest_stable_key"])

    # Some quests have multiple variants (e.g., Disarming the Sivakayans has
    # sword/sceptre variants).  Pick the primary variant per quest: the one
    # whose resource_name sorts first alphabetically.
    rows = conn.execute("""
        SELECT q.stable_key, q.db_name, q.display_name,
               qv.quest_desc, qv.xp_on_complete, qv.gold_on_complete,
               qv.item_on_complete_stable_key,
               qv.assign_new_quest_on_complete_stable_key,
               qv.repeatable, qv.disable_quest, qv.disable_text,
               qv.kill_turn_in_holder, qv.destroy_turn_in_holder,
               qv.drop_invuln_on_holder, qv.once_per_spawn_instance
        FROM quests q
        LEFT JOIN quest_variants qv ON qv.quest_stable_key = q.stable_key
            AND qv.resource_name = (
                SELECT MIN(qv2.resource_name)
                FROM quest_variants qv2
                WHERE qv2.quest_stable_key = q.stable_key
            )
        WHERE q.is_map_visible = 1
    """)
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.QUEST,
                display_name=r["display_name"],
                db_name=r["db_name"],
                description=r["quest_desc"],
                xp_reward=r["xp_on_complete"],
                gold_reward=r["gold_on_complete"],
                reward_item_key=r["item_on_complete_stable_key"],
                repeatable=bool(r["repeatable"]),
                disabled=bool(r["disable_quest"]),
                disabled_text=r["disable_text"],
                implicit=r["stable_key"] not in explicit_quests,
                kill_turn_in_holder=bool(r["kill_turn_in_holder"]) if r["kill_turn_in_holder"] else False,
                destroy_turn_in_holder=bool(r["destroy_turn_in_holder"]) if r["destroy_turn_in_holder"] else False,
                drop_invuln_on_holder=bool(r["drop_invuln_on_holder"]) if r["drop_invuln_on_holder"] else False,
                once_per_spawn_instance=bool(r["once_per_spawn_instance"]) if r["once_per_spawn_instance"] else False,
            )
        )


def _add_item_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("""
        SELECT stable_key, display_name, item_level, stackable, is_unique,
               template, teach_spell_stable_key, assign_quest_on_read_stable_key,
               complete_on_read_stable_key, lore
        FROM items
        WHERE is_map_visible = 1
    """)
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.ITEM,
                display_name=r["display_name"],
                item_level=r["item_level"],
                stackable=bool(r["stackable"]),
                is_unique=bool(r["is_unique"]),
                template=bool(r["template"]),
                description=r["lore"],
            )
        )


def _add_character_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("""
        SELECT stable_key, display_name, scene, x, y, z,
               level, is_vendor, is_friendly, invulnerable,
               my_world_faction_stable_key, is_enabled
        FROM characters
        WHERE is_map_visible = 1
    """)
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.CHARACTER,
                display_name=r["display_name"],
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                level=r["level"],
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                is_vendor=bool(r["is_vendor"]),
                is_friendly=bool(r["is_friendly"]),
                invulnerable=bool(r["invulnerable"]),
                faction_key=r["my_world_faction_stable_key"],
                is_enabled=bool(r["is_enabled"]) if r["is_enabled"] is not None else True,
            )
        )


def _add_zone_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("""
        SELECT stable_key, display_name, scene_name, is_dungeon
        FROM zones
        WHERE is_map_visible = 1
    """)
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.ZONE,
                display_name=r["display_name"],
                scene=r["scene_name"],
                is_dungeon=bool(r["is_dungeon"]),
            )
        )


def _add_zone_line_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("""
        SELECT zl.stable_key, zl.scene, zl.x, zl.y, zl.z,
               zl.is_enabled, zl.display_text,
               zl.destination_zone_stable_key,
               zl.landing_position_x, zl.landing_position_y, zl.landing_position_z,
               z.display_name AS dest_display
        FROM zone_lines zl
        LEFT JOIN zones z ON z.stable_key = zl.destination_zone_stable_key
    """)
    for r in rows:
        zone_key = _resolve_zone(r["scene"], scene_to_zone)
        # Display name: "Zone A → Zone B" or fallback to display_text
        dest = r["dest_display"] or "?"
        src_display = _zone_display_name(zone_key, zone_displays, r["scene"])
        display = f"{src_display} → {dest}"
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.ZONE_LINE,
                display_name=display,
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=r["scene"],
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                is_enabled=bool(r["is_enabled"]) if r["is_enabled"] is not None else True,
                destination_zone_key=r["destination_zone_stable_key"],
                destination_display=dest,
                landing_x=r["landing_position_x"],
                landing_y=r["landing_position_y"],
                landing_z=r["landing_position_z"],
            )
        )


def _add_spawn_point_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("""
        SELECT cs.spawn_point_stable_key, cs.character_stable_key,
               cs.scene, cs.x, cs.y, cs.z, cs.is_enabled,
               cs.night_spawn, cs.spawn_chance, cs.is_rare,
               cs.is_directly_placed, cs.is_trigger_spawn,
               cs.spawn_upon_quest_complete_stable_key,
               cs.zone_stable_key,
               c.display_name AS char_display
        FROM character_spawns cs
        JOIN characters c ON c.stable_key = cs.character_stable_key
        WHERE COALESCE(cs.is_map_visible, 1) = 1 AND cs.spawn_point_stable_key IS NOT NULL
    """)
    seen: set[str] = set()
    for r in rows:
        sp_key = r["spawn_point_stable_key"]
        if sp_key in seen:
            continue
        seen.add(sp_key)
        scene = r["scene"]
        zone_key = r["zone_stable_key"] or _resolve_zone(scene, scene_to_zone)
        # Respawn delay: average of the four spawn_delay columns
        graph.add_node(
            Node(
                key=sp_key,
                type=NodeType.SPAWN_POINT,
                display_name=r["char_display"],
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                is_enabled=bool(r["is_enabled"]) if r["is_enabled"] is not None else True,
                night_spawn=bool(r["night_spawn"]),
                spawn_chance=r["spawn_chance"],
                is_rare=bool(r["is_rare"]),
                is_directly_placed=bool(r["is_directly_placed"]),
                is_trigger_spawn=bool(r["is_trigger_spawn"]),
            )
        )


def _add_mining_node_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z, npc_name, respawn_time FROM mining_nodes")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.MINING_NODE,
                display_name=r["npc_name"] or "Mining Node",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                respawn_time=r["respawn_time"],
            )
        )


def _add_water_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z FROM waters")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.WATER,
                display_name="Fishing",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
            )
        )


def _add_forge_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z FROM forges")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.FORGE,
                display_name=f"Forge ({_zone_display_name(zone_key, zone_displays, scene)})",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
            )
        )


def _add_item_bag_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("""
        SELECT ib.stable_key, ib.scene, ib.x, ib.y, ib.z,
               ib.item_stable_key, ib.respawns, ib.respawn_timer,
               i.display_name AS item_display
        FROM item_bags ib
        LEFT JOIN items i ON i.stable_key = ib.item_stable_key
    """)
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        item_name = r["item_display"] or "Item"
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.ITEM_BAG,
                display_name=f"{item_name} (pickup)",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                respawns=bool(r["respawns"]) if r["respawns"] is not None else True,
                respawn_time=r["respawn_timer"],
            )
        )


def _add_recipe_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """Add recipe nodes for template items that are crafting bases."""
    rows = conn.execute("""
        SELECT DISTINCT cr.recipe_item_stable_key, i.display_name
        FROM crafting_recipes cr
        JOIN items i ON i.stable_key = cr.recipe_item_stable_key
    """)
    for r in rows:
        key = f"recipe:{r['recipe_item_stable_key']}"
        graph.add_node(
            Node(
                key=key,
                type=NodeType.RECIPE,
                display_name=f"Recipe: {r['display_name']}",
            )
        )


def _add_door_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z, key_item_stable_key FROM doors")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.DOOR,
                display_name=f"Door ({_zone_display_name(zone_key, zone_displays, scene)})",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                key_item_key=r["key_item_stable_key"],
            )
        )


def _add_faction_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("SELECT stable_key, display_name, default_value, refname FROM factions")
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.FACTION,
                display_name=r["display_name"],
                default_value=r["default_value"],
                refname=r["refname"],
            )
        )


def _add_spell_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("""
        SELECT stable_key, display_name, required_level, spell_desc
        FROM spells
        WHERE is_map_visible = 1
    """)
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.SPELL,
                display_name=r["display_name"],
                level=r["required_level"],
                description=r["spell_desc"],
            )
        )


def _add_skill_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("SELECT stable_key, display_name, skill_desc FROM skills WHERE is_map_visible = 1")
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.SKILL,
                display_name=r["display_name"],
                description=r["skill_desc"],
            )
        )


def _add_teleport_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z, teleport_item_stable_key FROM teleports")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.TELEPORT,
                display_name=f"Teleport ({_zone_display_name(zone_key, zone_displays, scene)})",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                teleport_item_key=r["teleport_item_stable_key"],
            )
        )


def _add_achievement_trigger_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z, achievement_name FROM achievement_triggers")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.ACHIEVEMENT_TRIGGER,
                display_name=r["achievement_name"] or "Achievement",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
                achievement_name=r["achievement_name"],
            )
        )


def _add_secret_passage_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z, object_name FROM secret_passages")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.SECRET_PASSAGE,
                display_name=r["object_name"] or "Secret Passage",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
            )
        )


def _add_wishing_well_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z FROM wishing_wells")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.WISHING_WELL,
                display_name=f"Wishing Well ({_zone_display_name(zone_key, zone_displays, scene)})",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
            )
        )


def _add_treasure_location_nodes(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    zone_displays = _zone_display(conn)
    rows = conn.execute("SELECT stable_key, scene, x, y, z FROM treasure_locations")
    for r in rows:
        scene = r["scene"]
        zone_key = _resolve_zone(scene, scene_to_zone)
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.TREASURE_LOCATION,
                display_name=f"Treasure ({_zone_display_name(zone_key, zone_displays, scene)})",
                x=r["x"],
                y=r["y"],
                z=r["z"],
                scene=scene,
                zone=_zone_display_name(zone_key, zone_displays),
                zone_key=zone_key,
            )
        )


def _add_book_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """Add one node per distinct book title."""
    rows = conn.execute("SELECT DISTINCT book_title FROM books")
    for r in rows:
        title = r["book_title"]
        key = f"book:{title}"
        graph.add_node(
            Node(
                key=key,
                type=NodeType.BOOK,
                display_name=title,
                book_title=title,
            )
        )


def _add_class_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("SELECT class_name, display_name FROM classes")
    for r in rows:
        key = f"class:{r['class_name']}"
        graph.add_node(
            Node(
                key=key,
                type=NodeType.CLASS,
                display_name=r["display_name"] or r["class_name"],
            )
        )


def _add_stance_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("SELECT stable_key, display_name, stance_desc FROM stances WHERE is_map_visible = 1")
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.STANCE,
                display_name=r["display_name"],
                description=r["stance_desc"],
            )
        )


def _add_ascension_nodes(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    rows = conn.execute("SELECT stable_key, skill_name, skill_desc FROM ascensions")
    for r in rows:
        graph.add_node(
            Node(
                key=r["stable_key"],
                type=NodeType.ASCENSION,
                display_name=r["skill_name"] or r["stable_key"],
                description=r["skill_desc"],
            )
        )


# ---------------------------------------------------------------------------
# Edge builders
# ---------------------------------------------------------------------------


def _add_quest_acquisition_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → source (ASSIGNED_BY) from quest_acquisition_sources + quest_character_roles.

    Handles all 6 acquisition methods:
    - dialog: NPC gives quest via conversation (keyword)
    - item_read: reading an item assigns the quest
    - zone_entry: entering a zone assigns the quest
    - quest_chain: completing another quest assigns this one
    - partial_turnin: partial item turn-in assigns the quest
    - scripted: hardcoded game event assigns the quest

    Quests with no acquisition source are implicitly completable:
    the player can walk up and complete them without formal acceptance.
    """
    rows = conn.execute("""
        SELECT quest_stable_key, method, source_type, source_stable_key, note
        FROM quest_acquisition_sources
    """)
    seen: set[tuple[str, str | None]] = set()
    for r in rows:
        quest_key = r["quest_stable_key"]
        target_key = r["source_stable_key"]
        method = r["method"]

        # Skip if nodes don't exist in graph
        if not graph.has_node(quest_key):
            continue
        if target_key and not graph.has_node(target_key):
            continue

        pair = (quest_key, target_key)
        if pair in seen:
            continue
        seen.add(pair)

        # Determine keyword for dialog-based assignments
        keyword = None
        if method == "dialog" and target_key:
            keyword = _find_dialog_keyword(conn, target_key, quest_key, "assign")

        if target_key:
            # For non-dialog methods, store the method as note so the C#
            # side knows the assignment mechanism (quest_chain, partial_turnin, etc.)
            note = r["note"]
            if not note and method != "dialog":
                note = method
            graph.add_edge(
                Edge(
                    source=quest_key,
                    target=target_key,
                    type=EdgeType.ASSIGNED_BY,
                    keyword=keyword,
                    note=note,
                )
            )

    # Giver role fallback: quest_character_roles 'giver' entries that
    # don't already have an acquisition source edge.
    rows = conn.execute("""
        SELECT quest_stable_key, character_stable_key
        FROM quest_character_roles
        WHERE role = 'giver'
    """)
    for r in rows:
        quest_key = r["quest_stable_key"]
        char_key = r["character_stable_key"]
        pair = (quest_key, char_key)
        if pair in seen:
            continue
        seen.add(pair)
        if not graph.has_node(quest_key) or not graph.has_node(char_key):
            continue
        keyword = _find_dialog_keyword(conn, char_key, quest_key, "assign")
        graph.add_edge(
            Edge(
                source=quest_key,
                target=char_key,
                type=EdgeType.ASSIGNED_BY,
                keyword=keyword,
            )
        )


def _add_quest_completion_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → character/zone/item (COMPLETED_BY) from quest_completion_sources."""
    rows = conn.execute("""
        SELECT quest_stable_key, method, source_type, source_stable_key, note
        FROM quest_completion_sources
    """)
    for r in rows:
        if not graph.has_node(r["quest_stable_key"]):
            continue
        target = r["source_stable_key"]
        if target and not graph.has_node(target):
            continue
        if target is None:
            continue
        keyword = None
        if r["source_type"] == "character" and r["method"] in {"item_turnin", "talk"}:
            keyword = _find_dialog_keyword(conn, target, r["quest_stable_key"], "complete")

        graph.add_edge(
            Edge(
                source=r["quest_stable_key"],
                target=target,
                type=EdgeType.COMPLETED_BY,
                keyword=keyword,
                note=r["note"],
            )
        )


def _add_quest_required_item_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → item (REQUIRES_ITEM) from quest_required_items.

    For multi-variant quests (same quest_stable_key, different variants),
    items from different variants are OR-grouped: the player needs any
    one variant's items, not all variants' items.  Items within the same
    variant are AND (all required).  Single-variant quests get no group
    (unconditional).
    """
    rows = conn.execute("""
        SELECT qri.quest_variant_resource_name, qri.item_stable_key, qri.quantity,
               qv.quest_stable_key
        FROM quest_required_items qri
        JOIN quest_variants qv ON qv.resource_name = qri.quest_variant_resource_name
    """)
    # Check which quests have multiple distinct variants (count resource_names,
    # not rows — a single variant with N items must not be treated as N variants).
    variant_resource_names: dict[str, set[str]] = {}
    for r in rows:
        qk = r["quest_stable_key"]
        variant_resource_names.setdefault(qk, set()).add(r["quest_variant_resource_name"])
    is_multi_variant = {qk: len(names) > 1 for qk, names in variant_resource_names.items()}

    # Re-execute to iterate (sqlite3 cursors are single-pass)
    rows = conn.execute("""
        SELECT qri.quest_variant_resource_name, qri.item_stable_key, qri.quantity,
               qv.quest_stable_key
        FROM quest_required_items qri
        JOIN quest_variants qv ON qv.resource_name = qri.quest_variant_resource_name
    """)
    for r in rows:
        quest_key = r["quest_stable_key"]
        item_key = r["item_stable_key"]
        if not graph.has_node(quest_key) or not graph.has_node(item_key):
            continue
        # Use variant resource_name as group only for genuinely multi-variant quests.
        group = r["quest_variant_resource_name"] if is_multi_variant.get(quest_key) else None
        graph.add_edge(
            Edge(
                source=quest_key,
                target=item_key,
                type=EdgeType.REQUIRES_ITEM,
                quantity=r["quantity"],
                group=group,
            )
        )


def _add_quest_chain_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → quest (CHAINS_TO) from quest_variants.assign_new_quest_on_complete_stable_key."""
    rows = conn.execute("""
        SELECT quest_stable_key, assign_new_quest_on_complete_stable_key
        FROM quest_variants
        WHERE assign_new_quest_on_complete_stable_key IS NOT NULL
    """)
    for r in rows:
        src = r["quest_stable_key"]
        tgt = r["assign_new_quest_on_complete_stable_key"]
        if not graph.has_node(src) or not graph.has_node(tgt):
            continue
        graph.add_edge(Edge(source=src, target=tgt, type=EdgeType.CHAINS_TO))


def _add_quest_also_completes_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → quest (ALSO_COMPLETES) from quest_complete_other_quests."""
    rows = conn.execute("""
        SELECT qv.quest_stable_key, qcoq.completed_quest_stable_key
        FROM quest_complete_other_quests qcoq
        JOIN quest_variants qv ON qv.resource_name = qcoq.quest_variant_resource_name
    """)
    for r in rows:
        src = r["quest_stable_key"]
        tgt = r["completed_quest_stable_key"]
        if not graph.has_node(src) or not graph.has_node(tgt):
            continue
        graph.add_edge(Edge(source=src, target=tgt, type=EdgeType.ALSO_COMPLETES))


def _add_quest_reward_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → item (REWARDS_ITEM) from quest_variants.item_on_complete_stable_key.

    When different variants of the same quest reward different items, each edge
    carries group=resource_name so the renderer can show per-variant outcomes.
    When all variants give the same item (or only one variant has a reward),
    a single ungrouped edge is emitted instead.
    """
    rows = conn.execute("""
        SELECT quest_stable_key, resource_name, item_on_complete_stable_key
        FROM quest_variants
        WHERE item_on_complete_stable_key IS NOT NULL
    """).fetchall()

    # Group by quest: {quest_key: {resource_name: item_key}}
    by_quest: dict[str, dict[str, str]] = {}
    for r in rows:
        by_quest.setdefault(r["quest_stable_key"], {})[r["resource_name"]] = r["item_on_complete_stable_key"]

    for quest_key, variant_rewards in by_quest.items():
        if not graph.has_node(quest_key):
            continue
        distinct_items = set(variant_rewards.values())
        if len(distinct_items) <= 1:
            # All variants give the same item — one ungrouped edge, no duplication.
            item_key = next(iter(distinct_items))
            if graph.has_node(item_key):
                graph.add_edge(Edge(source=quest_key, target=item_key, type=EdgeType.REWARDS_ITEM))
        else:
            # Different rewards per variant — group each edge by variant so the
            # renderer can show which recipe produces which item.
            for resource_name, item_key in variant_rewards.items():
                if graph.has_node(item_key):
                    graph.add_edge(
                        Edge(source=quest_key, target=item_key, type=EdgeType.REWARDS_ITEM, group=resource_name)
                    )


def _add_quest_faction_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → faction (AFFECTS_FACTION) from quest_faction_affects.

    Deduplicated across variants: same (quest, faction) only emits once.
    """
    rows = conn.execute("""
        SELECT DISTINCT qv.quest_stable_key, qfa.faction_stable_key, qfa.modifier_value
        FROM quest_faction_affects qfa
        JOIN quest_variants qv ON qv.resource_name = qfa.quest_variant_resource_name
    """)
    seen: set[tuple[str, str]] = set()
    for r in rows:
        src = r["quest_stable_key"]
        tgt = r["faction_stable_key"]
        pair = (src, tgt)
        if pair in seen:
            continue
        seen.add(pair)
        if not graph.has_node(src) or not graph.has_node(tgt):
            continue
        graph.add_edge(
            Edge(
                source=src,
                target=tgt,
                type=EdgeType.AFFECTS_FACTION,
                amount=r["modifier_value"],
            )
        )


def _add_quest_unlock_zone_line_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → zone_line (UNLOCKS_ZONE_LINE) from zone_line_quest_unlocks.

    Uses unlock_group for AND/OR semantics: edges in the same group are
    AND (all quests in the group must be complete), different groups are
    OR (any complete group unlocks the zone line).
    """
    rows = conn.execute("""
        SELECT zone_line_stable_key, unlock_group, quest_db_name
        FROM zone_line_quest_unlocks
    """)
    # quest_db_name needs resolution to stable_key
    db_to_key = _quest_dbname_to_key(conn)
    for r in rows:
        zl_key = r["zone_line_stable_key"]
        quest_key = db_to_key.get(r["quest_db_name"])
        if not quest_key or not graph.has_node(zl_key) or not graph.has_node(quest_key):
            continue
        # Edge goes from quest → zone_line (completing quest unlocks zone line)
        graph.add_edge(
            Edge(
                source=quest_key,
                target=zl_key,
                type=EdgeType.UNLOCKS_ZONE_LINE,
                group=str(r["unlock_group"]),
            )
        )


def _add_quest_unlock_character_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → character (UNLOCKS_CHARACTER) from character_quest_unlocks."""
    rows = conn.execute("""
        SELECT character_stable_key, unlock_group, quest_db_name
        FROM character_quest_unlocks
    """)
    db_to_key = _quest_dbname_to_key(conn)
    for r in rows:
        char_key = r["character_stable_key"]
        quest_key = db_to_key.get(r["quest_db_name"])
        if not quest_key or not graph.has_node(char_key) or not graph.has_node(quest_key):
            continue
        graph.add_edge(
            Edge(
                source=quest_key,
                target=char_key,
                type=EdgeType.UNLOCKS_CHARACTER,
                group=str(r["unlock_group"]),
            )
        )


def _add_quest_step_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """Build step edges from various game data sources.

    Step edges encode the quest walkthrough: talk to NPC, kill NPC,
    travel to zone, shout at NPC, read item.  Sources:
    - Kill: characters.quest_complete_on_death
    - Travel: zones.complete_quest_on_enter_stable_key
    - Read: items.complete_on_read_stable_key
    - Talk: quest_completion_sources (method='talk')
    - Shout: characters.shout_trigger_quest_stable_key
    """

    # Travel steps from zone-triggered quests
    rows = conn.execute("""
        SELECT stable_key, complete_quest_on_enter_stable_key,
               complete_second_quest_on_enter_stable_key
        FROM zones
        WHERE complete_quest_on_enter_stable_key IS NOT NULL
           OR complete_second_quest_on_enter_stable_key IS NOT NULL
    """)
    for r in rows:
        zone_key = r["stable_key"]
        for col in ("complete_quest_on_enter_stable_key", "complete_second_quest_on_enter_stable_key"):
            quest_key = r[col]
            if quest_key and graph.has_node(quest_key) and graph.has_node(zone_key):
                graph.add_edge(
                    Edge(
                        source=quest_key,
                        target=zone_key,
                        type=EdgeType.STEP_TRAVEL,
                    )
                )

    # Read steps from items that complete quests
    rows = conn.execute("""
        SELECT stable_key, complete_on_read_stable_key
        FROM items
        WHERE complete_on_read_stable_key IS NOT NULL
    """)
    for r in rows:
        item_key = r["stable_key"]
        quest_key = r["complete_on_read_stable_key"]
        if graph.has_node(item_key) and graph.has_node(quest_key):
            graph.add_edge(
                Edge(
                    source=quest_key,
                    target=item_key,
                    type=EdgeType.STEP_READ,
                )
            )

    # Kill steps from characters.quest_complete_on_death
    rows = conn.execute("""
        SELECT stable_key, quest_complete_on_death
        FROM characters
        WHERE quest_complete_on_death IS NOT NULL
    """)
    for r in rows:
        char_key = r["stable_key"]
        quest_key = r["quest_complete_on_death"]
        if graph.has_node(char_key) and graph.has_node(quest_key):
            graph.add_edge(
                Edge(
                    source=quest_key,
                    target=char_key,
                    type=EdgeType.STEP_KILL,
                )
            )

    # Talk steps from quest_completion_sources where method is 'talk'
    rows = conn.execute("""
        SELECT quest_stable_key, source_stable_key
        FROM quest_completion_sources
        WHERE method = 'talk' AND source_type = 'character'
    """)
    for r in rows:
        quest_key = r["quest_stable_key"]
        char_key = r["source_stable_key"]
        if not quest_key or not char_key:
            continue
        if graph.has_node(quest_key) and graph.has_node(char_key):
            keyword = _find_dialog_keyword(conn, char_key, quest_key, "complete")
            graph.add_edge(
                Edge(
                    source=quest_key,
                    target=char_key,
                    type=EdgeType.STEP_TALK,
                    keyword=keyword,
                )
            )

    # Shout steps from characters with shout_trigger_quest_stable_key
    rows = conn.execute("""
        SELECT stable_key, shout_trigger_quest_stable_key, shout_trigger_keyword
        FROM characters
        WHERE shout_trigger_quest_stable_key IS NOT NULL
              AND shout_trigger_quest_stable_key != ''
    """)
    for r in rows:
        char_key = r["stable_key"]
        quest_key = r["shout_trigger_quest_stable_key"]
        if graph.has_node(char_key) and graph.has_node(quest_key):
            graph.add_edge(
                Edge(
                    source=quest_key,
                    target=char_key,
                    type=EdgeType.STEP_SHOUT,
                    keyword=r["shout_trigger_keyword"],
                )
            )


def _add_quest_dialog_prerequisite_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → quest (REQUIRES_QUEST) from character_dialogs.required_quest_stable_key."""
    rows = conn.execute("""
        SELECT required_quest_stable_key, complete_quest_stable_key
        FROM character_dialogs
        WHERE required_quest_stable_key IS NOT NULL
          AND complete_quest_stable_key IS NOT NULL
    """)
    for r in rows:
        src = r["complete_quest_stable_key"]
        tgt = r["required_quest_stable_key"]
        if src == tgt:
            continue
        if not graph.has_node(src) or not graph.has_node(tgt):
            continue
        graph.add_edge(Edge(source=src, target=tgt, type=EdgeType.REQUIRES_QUEST))


def _add_character_drop_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """character → item (DROPS_ITEM) from loot_drops."""
    rows = conn.execute("""
        SELECT character_stable_key, item_stable_key, drop_probability
        FROM loot_drops
    """)
    for r in rows:
        if not graph.has_node(r["character_stable_key"]) or not graph.has_node(r["item_stable_key"]):
            continue
        graph.add_edge(
            Edge(
                source=r["character_stable_key"],
                target=r["item_stable_key"],
                type=EdgeType.DROPS_ITEM,
                chance=r["drop_probability"],
            )
        )


def _add_character_vendor_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """character → item (SELLS_ITEM) from character_vendor_items."""
    rows = conn.execute("SELECT character_stable_key, item_stable_key FROM character_vendor_items")
    for r in rows:
        if not graph.has_node(r["character_stable_key"]) or not graph.has_node(r["item_stable_key"]):
            continue
        graph.add_edge(
            Edge(
                source=r["character_stable_key"],
                target=r["item_stable_key"],
                type=EdgeType.SELLS_ITEM,
            )
        )


def _add_vendor_quest_unlock_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """quest → item (UNLOCKS_VENDOR_ITEM) for quest-unlocked vendor inventory.

    Also emits a SELLS_ITEM edge from vendor → item so the item appears in
    obtainability chains.
    """
    rows = conn.execute("""
        SELECT cvqu.character_stable_key,
               cvqu.quest_stable_key,
               qv.unlock_item_for_vendor_stable_key
        FROM character_vendor_quest_unlocks cvqu
        JOIN quest_variants qv ON qv.quest_stable_key = cvqu.quest_stable_key
            AND qv.resource_name = (
                SELECT MIN(qv2.resource_name)
                FROM quest_variants qv2
                WHERE qv2.quest_stable_key = cvqu.quest_stable_key
            )
        WHERE qv.unlock_item_for_vendor_stable_key IS NOT NULL
    """)
    for r in rows:
        quest_key = r["quest_stable_key"]
        char_key = r["character_stable_key"]
        item_key = r["unlock_item_for_vendor_stable_key"]
        if not graph.has_node(quest_key) or not graph.has_node(item_key):
            continue
        # Quest → item: shown in rewards section with vendor name from note
        graph.add_edge(
            Edge(
                source=quest_key,
                target=item_key,
                type=EdgeType.UNLOCKS_VENDOR_ITEM,
                note=char_key,  # vendor character key for display name lookup
            )
        )
        # Vendor → item: for item obtainability chains
        if graph.has_node(char_key):
            graph.add_edge(
                Edge(
                    source=char_key,
                    target=item_key,
                    type=EdgeType.SELLS_ITEM,
                )
            )


def _add_character_dialog_give_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """character → item (GIVES_ITEM) from character_dialogs.give_item_stable_key."""
    rows = conn.execute("""
        SELECT character_stable_key, give_item_stable_key, keywords
        FROM character_dialogs
        WHERE give_item_stable_key IS NOT NULL
    """)
    for r in rows:
        if not graph.has_node(r["character_stable_key"]) or not graph.has_node(r["give_item_stable_key"]):
            continue
        # keywords is comma-separated; take first as the primary keyword
        keywords = r["keywords"]
        keyword = keywords.split(",")[0].strip() if keywords else None
        graph.add_edge(
            Edge(
                source=r["character_stable_key"],
                target=r["give_item_stable_key"],
                type=EdgeType.GIVES_ITEM,
                keyword=keyword,
            )
        )


def _add_character_spawn_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """character ↔ spawn_point edges.

    character → spawn_point (HAS_SPAWN)
    spawn_point → character (SPAWNS_CHARACTER)
    character → zone (SPAWNS_IN) — one edge per distinct zone
    """
    rows = conn.execute("""
        SELECT character_stable_key, spawn_point_stable_key,
               zone_stable_key, spawn_chance, is_rare
        FROM character_spawns
        WHERE COALESCE(is_map_visible, 1) = 1 AND spawn_point_stable_key IS NOT NULL
    """)
    char_zones: dict[str, set[str]] = {}
    for r in rows:
        char_key = r["character_stable_key"]
        sp_key = r["spawn_point_stable_key"]
        zone_key = r["zone_stable_key"]

        if graph.has_node(char_key) and graph.has_node(sp_key):
            graph.add_edge(
                Edge(
                    source=char_key,
                    target=sp_key,
                    type=EdgeType.HAS_SPAWN,
                )
            )
            graph.add_edge(
                Edge(
                    source=sp_key,
                    target=char_key,
                    type=EdgeType.SPAWNS_CHARACTER,
                    chance=r["spawn_chance"],
                )
            )

        # Track zones for SPAWNS_IN dedup
        if zone_key and graph.has_node(char_key) and graph.has_node(zone_key):
            char_zones.setdefault(char_key, set()).add(zone_key)

    for char_key, zones in char_zones.items():
        for zone_key in zones:
            graph.add_edge(
                Edge(
                    source=char_key,
                    target=zone_key,
                    type=EdgeType.SPAWNS_IN,
                )
            )


def _add_character_faction_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """character → faction (BELONGS_TO_FACTION) from characters.my_world_faction_stable_key."""
    rows = conn.execute("""
        SELECT stable_key, my_world_faction_stable_key
        FROM characters
        WHERE my_world_faction_stable_key IS NOT NULL AND is_map_visible = 1
    """)
    for r in rows:
        if not graph.has_node(r["stable_key"]) or not graph.has_node(r["my_world_faction_stable_key"]):
            continue
        graph.add_edge(
            Edge(
                source=r["stable_key"],
                target=r["my_world_faction_stable_key"],
                type=EdgeType.BELONGS_TO_FACTION,
            )
        )


def _add_spawn_point_gate_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """spawn_point → quest (GATED_BY_QUEST) from character_spawns.spawn_upon_quest_complete_stable_key."""
    rows = conn.execute("""
        SELECT DISTINCT spawn_point_stable_key, spawn_upon_quest_complete_stable_key
        FROM character_spawns
        WHERE spawn_upon_quest_complete_stable_key IS NOT NULL AND spawn_point_stable_key IS NOT NULL
    """)
    for r in rows:
        sp_key = r["spawn_point_stable_key"]
        quest_key = r["spawn_upon_quest_complete_stable_key"]
        if graph.has_node(sp_key) and graph.has_node(quest_key):
            graph.add_edge(
                Edge(
                    source=sp_key,
                    target=quest_key,
                    type=EdgeType.GATED_BY_QUEST,
                )
            )


def _add_spawn_point_stop_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """spawn_point → quest (STOPS_AFTER_QUEST) from spawn_point_stop_quests."""
    rows = conn.execute("SELECT spawn_point_stable_key, quest_stable_key FROM spawn_point_stop_quests")
    for r in rows:
        sp_key = r["spawn_point_stable_key"]
        quest_key = r["quest_stable_key"]
        if graph.has_node(sp_key) and graph.has_node(quest_key):
            graph.add_edge(
                Edge(
                    source=sp_key,
                    target=quest_key,
                    type=EdgeType.STOPS_AFTER_QUEST,
                )
            )


def _add_spawn_point_protector_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """character → character (PROTECTS) from character_spawns.protector_stable_key."""
    rows = conn.execute("""
        SELECT DISTINCT character_stable_key, protector_stable_key
        FROM character_spawns
        WHERE protector_stable_key IS NOT NULL
    """)
    for r in rows:
        protector = r["protector_stable_key"]
        protected = r["character_stable_key"]
        if graph.has_node(protector) and graph.has_node(protected):
            graph.add_edge(
                Edge(
                    source=protector,
                    target=protected,
                    type=EdgeType.PROTECTS,
                )
            )


def _add_zone_line_connect_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """zone_line → zone (CONNECTS_ZONES) for the destination zone."""
    rows = conn.execute("""
        SELECT stable_key, destination_zone_stable_key
        FROM zone_lines
        WHERE destination_zone_stable_key IS NOT NULL
    """)
    for r in rows:
        zl_key = r["stable_key"]
        zone_key = r["destination_zone_stable_key"]
        if graph.has_node(zl_key) and graph.has_node(zone_key):
            graph.add_edge(
                Edge(
                    source=zl_key,
                    target=zone_key,
                    type=EdgeType.CONNECTS_ZONES,
                )
            )


def _add_zone_connect_edges(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    """zone → zone (CONNECTS_TO) derived from zone lines.

    If zone A has a zone line whose destination is zone B, then A connects_to B.
    Deduplicated: only one edge per (source_zone, dest_zone) pair.
    """
    rows = conn.execute("""
        SELECT zl.scene, zl.destination_zone_stable_key
        FROM zone_lines zl
        WHERE zl.destination_zone_stable_key IS NOT NULL
    """)
    seen: set[tuple[str, str]] = set()
    for r in rows:
        dest_zone = r["destination_zone_stable_key"]
        src_zone = scene_to_zone.get(r["scene"] or "")
        if not src_zone or src_zone == dest_zone:
            continue
        pair = (src_zone, dest_zone)
        if pair in seen:
            continue
        seen.add(pair)
        if graph.has_node(src_zone) and graph.has_node(dest_zone):
            graph.add_edge(
                Edge(
                    source=src_zone,
                    target=dest_zone,
                    type=EdgeType.CONNECTS_TO,
                )
            )


def _add_zone_contain_edges(
    conn: sqlite3.Connection,
    graph: EntityGraph,
    scene_to_zone: dict[str, str],
) -> None:
    """zone → resource nodes (CONTAINS) inferred from scene→zone mapping.

    Connects zones to their mining nodes, waters, forges, and item bags.
    """
    for node in graph.all_nodes():
        if (
            node.type in (NodeType.MINING_NODE, NodeType.WATER, NodeType.FORGE, NodeType.ITEM_BAG)
            and node.zone_key
            and graph.has_node(node.zone_key)
        ):
            graph.add_edge(
                Edge(
                    source=node.zone_key,
                    target=node.key,
                    type=EdgeType.CONTAINS,
                )
            )


def _add_mining_yield_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """mining_node → item (YIELDS_ITEM) from mining_node_items."""
    rows = conn.execute("SELECT mining_node_stable_key, item_stable_key, drop_chance FROM mining_node_items")
    for r in rows:
        if graph.has_node(r["mining_node_stable_key"]) and graph.has_node(r["item_stable_key"]):
            graph.add_edge(
                Edge(
                    source=r["mining_node_stable_key"],
                    target=r["item_stable_key"],
                    type=EdgeType.YIELDS_ITEM,
                    chance=r["drop_chance"],
                )
            )


def _add_water_yield_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """water → item (YIELDS_ITEM) from water_fishables, deduplicated per (water, item)."""
    rows = conn.execute("SELECT water_stable_key, item_stable_key, type, drop_chance FROM water_fishables")
    # Group by (water, item) to merge day/night entries.
    pairs: dict[tuple[str, str], dict[str, float | None]] = {}
    for r in rows:
        key = (r["water_stable_key"], r["item_stable_key"])
        if key not in pairs:
            pairs[key] = {}
        pairs[key][r["type"]] = r["drop_chance"]

    for (water_key, item_key), types in pairs.items():
        if not (graph.has_node(water_key) and graph.has_node(item_key)):
            continue

        has_day = "DayFishable" in types
        has_night = "NightFishable" in types
        if has_day and has_night:
            time_restriction = None
            chance = max(c for c in types.values() if c is not None) if any(types.values()) else None
        elif has_day:
            time_restriction = "day"
            chance = types.get("DayFishable")
        else:
            time_restriction = "night"
            chance = types.get("NightFishable")

        graph.add_edge(
            Edge(
                source=water_key,
                target=item_key,
                type=EdgeType.YIELDS_ITEM,
                chance=chance,
                time_restriction=time_restriction,
            )
        )


def _add_item_bag_yield_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """item_bag → item (YIELDS_ITEM) from item_bags.item_stable_key."""
    rows = conn.execute("SELECT stable_key, item_stable_key FROM item_bags WHERE item_stable_key IS NOT NULL")
    for r in rows:
        if graph.has_node(r["stable_key"]) and graph.has_node(r["item_stable_key"]):
            graph.add_edge(
                Edge(
                    source=r["stable_key"],
                    target=r["item_stable_key"],
                    type=EdgeType.YIELDS_ITEM,
                )
            )


def _add_crafting_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """recipe → item (REQUIRES_MATERIAL) + recipe → item (PRODUCES) from crafting tables."""
    # Materials
    rows = conn.execute("""
        SELECT recipe_item_stable_key, material_slot, material_item_stable_key, material_quantity
        FROM crafting_recipes
    """)
    for r in rows:
        recipe_key = f"recipe:{r['recipe_item_stable_key']}"
        item_key = r["material_item_stable_key"]
        if graph.has_node(recipe_key) and graph.has_node(item_key):
            graph.add_edge(
                Edge(
                    source=recipe_key,
                    target=item_key,
                    type=EdgeType.REQUIRES_MATERIAL,
                    quantity=r["material_quantity"],
                    slot=r["material_slot"],
                )
            )

    # Mold (template item): the template is consumed on a successful craft.
    # Smithing.DoSuccess() clears Template.MyItem just like the ingredients,
    # confirming it is an ingredient. Its key is derived by stripping "recipe:"
    # from the recipe key — that naming convention is enforced by _add_recipe_nodes.
    # Slot 0 is reserved for the template; ingredient slots come from the DB.
    for recipe_node in graph.nodes_of_type(NodeType.RECIPE):
        template_key = recipe_node.key[len("recipe:") :]
        if graph.has_node(template_key):
            graph.add_edge(
                Edge(
                    source=recipe_node.key,
                    target=template_key,
                    type=EdgeType.REQUIRES_MATERIAL,
                    quantity=1,
                    slot=0,
                )
            )

    # Products
    rows = conn.execute("""
        SELECT recipe_item_stable_key, reward_slot, reward_item_stable_key, reward_quantity
        FROM crafting_rewards
    """)
    for r in rows:
        recipe_key = f"recipe:{r['recipe_item_stable_key']}"
        item_key = r["reward_item_stable_key"]
        if graph.has_node(recipe_key) and graph.has_node(item_key):
            graph.add_edge(
                Edge(
                    source=recipe_key,
                    target=item_key,
                    type=EdgeType.PRODUCES,
                    quantity=r["reward_quantity"],
                    slot=r["reward_slot"],
                )
            )


def _add_item_craft_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """item → recipe (CRAFTED_FROM) — reverse link from product to recipe."""
    rows = conn.execute("""
        SELECT recipe_item_stable_key, reward_item_stable_key
        FROM crafting_rewards
    """)
    for r in rows:
        recipe_key = f"recipe:{r['recipe_item_stable_key']}"
        item_key = r["reward_item_stable_key"]
        if graph.has_node(item_key) and graph.has_node(recipe_key):
            graph.add_edge(
                Edge(
                    source=item_key,
                    target=recipe_key,
                    type=EdgeType.CRAFTED_FROM,
                )
            )


def _add_item_quest_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """item → quest (ASSIGNS_QUEST / COMPLETES_QUEST) from items table."""
    rows = conn.execute("""
        SELECT stable_key, assign_quest_on_read_stable_key, complete_on_read_stable_key
        FROM items
        WHERE assign_quest_on_read_stable_key IS NOT NULL
           OR complete_on_read_stable_key IS NOT NULL
    """)
    for r in rows:
        item_key = r["stable_key"]
        if r["assign_quest_on_read_stable_key"]:
            quest_key = r["assign_quest_on_read_stable_key"]
            if graph.has_node(item_key) and graph.has_node(quest_key):
                graph.add_edge(
                    Edge(
                        source=item_key,
                        target=quest_key,
                        type=EdgeType.ASSIGNS_QUEST,
                    )
                )
        if r["complete_on_read_stable_key"]:
            quest_key = r["complete_on_read_stable_key"]
            if graph.has_node(item_key) and graph.has_node(quest_key):
                graph.add_edge(
                    Edge(
                        source=item_key,
                        target=quest_key,
                        type=EdgeType.COMPLETES_QUEST,
                    )
                )


def _add_item_spell_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """item → spell (TEACHES_SPELL) from items.teach_spell_stable_key."""
    rows = conn.execute("""
        SELECT stable_key, teach_spell_stable_key
        FROM items
        WHERE teach_spell_stable_key IS NOT NULL
    """)
    for r in rows:
        item_key = r["stable_key"]
        spell_key = r["teach_spell_stable_key"]
        if graph.has_node(item_key) and graph.has_node(spell_key):
            graph.add_edge(
                Edge(
                    source=item_key,
                    target=spell_key,
                    type=EdgeType.TEACHES_SPELL,
                )
            )


def _add_item_door_edges(conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """item → door (UNLOCKS_DOOR) from doors.key_item_stable_key."""
    rows = conn.execute("""
        SELECT stable_key, key_item_stable_key
        FROM doors
        WHERE key_item_stable_key IS NOT NULL
    """)
    for r in rows:
        item_key = r["key_item_stable_key"]
        door_key = r["stable_key"]
        if graph.has_node(item_key) and graph.has_node(door_key):
            graph.add_edge(
                Edge(
                    source=item_key,
                    target=door_key,
                    type=EdgeType.UNLOCKS_DOOR,
                )
            )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _quest_dbname_to_key(conn: sqlite3.Connection) -> dict[str, str]:
    """Map quest db_name → stable_key."""
    rows = conn.execute("SELECT stable_key, db_name FROM quests WHERE db_name IS NOT NULL")
    return {r["db_name"]: r["stable_key"] for r in rows}


def _find_dialog_keyword(
    conn: sqlite3.Connection,
    character_key: str,
    quest_key: str,
    role: str,
) -> str | None:
    """Find the dialog keyword a player says to trigger quest assign/complete.

    Searches character_dialogs for a dialog entry that references the quest.
    """
    if role == "assign":
        row = conn.execute(
            "SELECT keywords FROM character_dialogs WHERE character_stable_key = ? AND assign_quest_stable_key = ?",
            (character_key, quest_key),
        ).fetchone()
    elif role == "complete":
        row = conn.execute(
            "SELECT keywords FROM character_dialogs WHERE character_stable_key = ? AND complete_quest_stable_key = ?",
            (character_key, quest_key),
        ).fetchone()
    else:
        return None

    if row and row["keywords"]:
        keywords: str = row["keywords"]
        return keywords.split(",")[0].strip()
    return None
