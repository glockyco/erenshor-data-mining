"""Adapt the public item view to guide acquisitions and operation requirements."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from erenshor.domain.value_objects.item_public_view import PublicSource, PublicUse

from .combat_guidance import combat_preparations
from .schema import Edge, EdgeType, Node, NodeType

if TYPE_CHECKING:
    import sqlite3

    from erenshor.infrastructure.database.repositories.item_public_view import ItemPublicViewRepository

    from .graph import EntityGraph

_SOURCE_EDGES = {
    "character_drop": EdgeType.DROPS_ITEM,
    "vendor": EdgeType.SELLS_ITEM,
    "dialog": EdgeType.GIVES_ITEM,
    "quest_reward": EdgeType.REWARDS_ITEM,
    "crafting": EdgeType.PRODUCES,
    "mining": EdgeType.YIELDS_ITEM,
    "fishing": EdgeType.YIELDS_ITEM,
    "item_bag": EdgeType.YIELDS_ITEM,
    "item_drop": EdgeType.CREATES_ITEM,
    "spell_created": EdgeType.CREATES_ITEM,
    "item_conversion": EdgeType.CREATES_ITEM,
}
EXPLANATORY_KINDS = frozenset(
    {
        "common_world_item",
        "special_world_drop",
        "fishing_bonus",
        "starting_class",
        "ui_grant",
        "auction_house",
    }
)


def _quantity(fact: PublicSource | PublicUse) -> int | None:
    value = fact.quantity_min
    return int(value) if value is not None and value >= 0 and int(value) == value else None


def _recipe(graph: EntityGraph, item_key: str) -> str:
    item = graph.get_node(item_key)
    if item is None:
        raise ValueError(f"Canonical recipe item missing: {item_key}")
    key = f"recipe:{item_key}"
    if not graph.has_node(key):
        graph.add_node(Node(key, NodeType.RECIPE, f"Recipe: {item.display_name}"))
    return key


def dialog_keyword(conn: sqlite3.Connection, fact: PublicSource) -> str | None:
    """Enrich only the selected native dialog copy and numeric slot."""
    if fact.source_copy_stable_key is None or fact.variant_key is None:
        raise ValueError(f"Canonical dialog identity missing: {fact.source_key}")
    try:
        slot = int(fact.variant_key)
    except ValueError as exc:
        raise ValueError(f"Canonical dialog index is not numeric: {fact.source_key}") from exc
    rows = conn.execute(
        "SELECT keywords FROM character_dialogs WHERE character_stable_key=? AND dialog_index=?",
        (fact.source_copy_stable_key, slot),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError(f"Canonical dialog metadata missing: {fact.source_key}")
    return rows[0][0].split(",")[0].strip() if rows[0][0] else None


def _require_item(conn: sqlite3.Connection, graph: EntityGraph, key: str) -> None:
    if graph.has_node(key):
        return
    row = conn.execute("SELECT id, display_name, item_level FROM items WHERE stable_key=?", (key,)).fetchone()
    if row is None:
        raise ValueError(f"Canonical required item missing: {key}")
    graph.add_node(Node(key, NodeType.ITEM, row["display_name"], game_id=row["id"], item_level=row["item_level"]))


def add_canonical_sources(repository: ItemPublicViewRepository, conn: sqlite3.Connection, graph: EntityGraph) -> None:
    """Retain public identities, including operation inputs and repeated slots."""
    acquisitions = repository.sources()
    uses = repository.uses()
    facts: tuple[PublicSource | PublicUse, ...] = (*acquisitions, *uses)
    graph.source_places = {
        fact.place_set_key: repository.places(fact.place_set_key) for fact in facts if fact.place_set_key is not None
    }
    preparations = combat_preparations(conn)
    required_items = {
        use.item_stable_key
        for use in uses
        if use.kind
        in {
            "crafting_recipe",
            "crafting_material",
            "quest_requirement",
            "item_drop",
            "spell_created",
            "item_conversion",
        }
    }
    required_items.update(
        fact.source_stable_key
        for fact in acquisitions
        if fact.kind in {"crafting", "item_drop", "spell_created", "item_conversion"}
        and fact.source_stable_key is not None
    )
    required_items.update(
        atom.reference_stable_key
        for fact in facts
        for atom in (
            *fact.conditions,
            *(atom for place in repository.places(fact.place_set_key) for atom in place.conditions),
        )
        if atom.predicate in {"item_held", "key_held", "room_furnished"} and atom.reference_stable_key is not None
    )
    for key in sorted(required_items):
        _require_item(conn, graph, key)
    for fact in facts:
        key = fact.source_key if isinstance(fact, PublicSource) else fact.use_key
        if key in graph.source_facts:
            raise ValueError(f"Duplicate canonical fact: {key}")
        graph.source_facts[key] = fact
    # An acquisition can produce several ways to its item, one per release or gate branch.
    for key, tier, depth in conn.execute(
        "SELECT f.fact, w.tier, w.depth FROM progression_way_facts f"
        " JOIN progression_ways w USING (node_stable_key, way_key)"
        " JOIN item_sources a ON a.source_key = f.fact AND a.item_stable_key = f.node_stable_key"
        " WHERE w.tier IS NOT NULL"
    ):
        rank = (tier, depth)
        if key not in graph.source_ranks or rank < graph.source_ranks[key]:
            graph.source_ranks[key] = rank
    for fact in acquisitions:
        if fact.kind not in _SOURCE_EDGES and fact.kind not in EXPLANATORY_KINDS:
            raise ValueError(f"unsupported canonical acquisition kind: {fact.kind}")
        if not graph.has_node(fact.item_stable_key):
            graph.source_exclusions[fact.source_key] = "item_not_in_guide"
            continue
        graph.source_uses[fact.source_key] = []
        if fact.kind == "quest_reward" and not graph.has_node(fact.source_stable_key or ""):
            continue
        if fact.kind in EXPLANATORY_KINDS:
            continue
        if fact.kind == "fishing" and fact.mechanic == "fishing_global_replacement":
            continue
        source = fact.source_copy_stable_key or fact.source_stable_key
        if (
            fact.kind in {"character_drop", "vendor", "dialog", "quest_reward"}
            and source is not None
            and not graph.has_node(source)
        ):
            row = conn.execute(
                "SELECT display_name, level, is_friendly, invulnerable FROM characters WHERE stable_key=?", (source,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Canonical character source missing: {fact.source_key}: {source}")
            graph.add_node(
                Node(
                    source,
                    NodeType.CHARACTER,
                    row["display_name"],
                    level=row["level"],
                    is_friendly=bool(row["is_friendly"]),
                    invulnerable=bool(row["invulnerable"]),
                )
            )
        if fact.kind == "crafting" and fact.mechanic != "remove_blessing":
            if fact.source_stable_key is None:
                raise ValueError(f"Canonical crafting source missing: {fact.source_key}")
            source = _recipe(graph, fact.source_stable_key)
        if source is None or not graph.has_node(source):
            raise ValueError(f"Canonical required source missing: {fact.source_key}: {source}")
        edge_source = source
        if fact.kind == "quest_reward":
            assert fact.source_stable_key is not None
            edge_source = fact.source_stable_key
        period = next((atom.value for atom in fact.conditions if atom.predicate == "time_of_day"), None)
        graph.add_edge(
            Edge(
                edge_source,
                fact.item_stable_key,
                _SOURCE_EDGES[fact.kind],
                quantity=_quantity(fact),
                chance=fact.probability_min,
                time_restriction=period,
                keyword=dialog_keyword(conn, fact) if fact.kind == "dialog" else None,
                note=preparations.get(source) if fact.kind == "character_drop" else None,
                provenance_key=fact.source_key,
            )
        )
        if fact.kind == "crafting" and fact.mechanic != "remove_blessing":
            graph.add_edge(Edge(fact.item_stable_key, source, EdgeType.CRAFTED_FROM, provenance_key=fact.source_key))
    variants: dict[str | None, set[str | None]] = defaultdict(set)
    crafts_by_recipe: dict[str | None, list[PublicSource]] = defaultdict(list)
    for acquisition in acquisitions:
        if acquisition.kind == "crafting" and acquisition.source_key in graph.source_uses:
            crafts_by_recipe[acquisition.source_stable_key].append(acquisition)
    for use in uses:
        if use.kind == "quest_requirement":
            variants[use.target_stable_key].add(use.variant_key)
    for use in uses:
        if use.outcome_key is not None:
            outcome = graph.source_facts.get(use.outcome_key)
            if not isinstance(outcome, PublicSource):
                raise ValueError(f"Canonical use outcome missing: {use.use_key}")
            if use.outcome_key not in graph.source_exclusions:
                graph.source_uses[use.outcome_key].append(use)
        if use.kind == "crafting_material":
            for acquisition in crafts_by_recipe.get(use.target_stable_key, ()):
                graph.source_uses[acquisition.source_key].append(use)
        if use.kind == "quest_requirement":
            source, target, kind = use.target_stable_key, use.item_stable_key, EdgeType.REQUIRES_ITEM
            if source is None or not graph.has_node(source):
                graph.source_exclusions[use.use_key] = "quest_not_in_guide"
                continue
            graph.quest_uses.setdefault((source, target), []).append(use)
        elif use.kind == "crafting_material" and use.target_stable_key in crafts_by_recipe:
            assert use.target_stable_key is not None
            source, target, kind = (
                _recipe(graph, use.target_stable_key),
                use.item_stable_key,
                EdgeType.REQUIRES_MATERIAL,
            )
        elif use.kind == "crafting_recipe" and use.outcome_key in graph.source_uses:
            source, target, kind = _recipe(graph, use.item_stable_key), use.item_stable_key, EdgeType.REQUIRES_MATERIAL
        else:
            continue
        if not graph.has_node(target):
            raise ValueError(f"Canonical required item missing: {use.use_key}: {target}")
        graph.add_edge(
            Edge(
                source,
                target,
                kind,
                quantity=_quantity(use),
                group=use.variant_key if len(variants.get(use.target_stable_key, ())) > 1 else None,
                slot=use.material_slot,
                provenance_key=use.use_key,
            )
        )
    linked = {use.use_key for members in graph.source_uses.values() for use in members}
    linked.update(use.use_key for members in graph.quest_uses.values() for use in members)
    for use in uses:
        if use.use_key not in linked and use.use_key not in graph.source_exclusions:
            graph.source_exclusions[use.use_key] = "operation_annotation_not_an_acquisition_requirement"


def source_coverage_report(graph: EntityGraph) -> dict[str, object]:
    """Return offline accounting for every canonical input, never runtime evidence."""
    result: dict[str, object] = {}
    for family, cls in (("acquisitions", PublicSource), ("uses", PublicUse)):
        records = []
        for key, fact in sorted(graph.source_facts.items()):
            if not isinstance(fact, cls):
                continue
            reason = graph.source_exclusions.get(key)
            records.append({"key": key, "status": "excluded" if reason else "represented", "reason": reason})
        result[family] = {
            "represented": sum(row["status"] == "represented" for row in records),
            "excluded": sum(row["status"] == "excluded" for row in records),
            "reasons": dict(sorted(Counter(row["reason"] for row in records if row["reason"]).items())),
            "records": records,
        }
    return result
