"""Small graph builders shared by synthetic guide tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from erenshor.application.guide.canonical_sources import add_canonical_sources
from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.schema import AtomKind, Edge, Gate, GateAtom, Node, NodeType, SubjectKind
from erenshor.application.processor.item_provenance import ProvenanceBuilder
from erenshor.application.processor.writer import Writer
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository

if TYPE_CHECKING:
    from erenshor.domain.value_objects.item_provenance import ItemAcquisition, ItemUse


def build_graph(*nodes: Node, edges: list[Edge] | None = None, gates: list[Gate] | None = None) -> EntityGraph:
    """Build and index a graph from the supplied synthetic entities."""
    graph = EntityGraph()
    for node in nodes:
        graph.add_node(node)
    for edge in edges or []:
        graph.add_edge(edge)
    for gate in gates or []:
        graph.add_gate(gate)
    graph.build_indexes()
    return graph


def quest_gate(kind: SubjectKind, subject: str, *groups: tuple[str, ...], item: str | None = None) -> Gate:
    """A gate that opens once every quest of one of its groups is complete."""
    return Gate(
        subject_kind=kind,
        subject_key=subject,
        gate="activation",
        groups=tuple(tuple(GateAtom(AtomKind.QUEST_DONE, quest) for quest in group) for group in groups),
        item_key=item,
    )


def quest_node(key: str, db_name: str | None = None, **kwargs: object) -> Node:
    """Build a quest node with the stable synthetic-test defaults."""
    return Node(
        key=key,
        type=NodeType.QUEST,
        display_name=kwargs.pop("display_name", key),
        db_name=db_name,
        **kwargs,
    )


def item_node(key: str, name: str | None = None, **kwargs: object) -> Node:
    """Build an item node with an optional display name."""
    return Node(key=key, type=NodeType.ITEM, display_name=name or key, **kwargs)


def character_node(key: str, name: str | None = None, **kwargs: object) -> Node:
    """Build a character node with an optional display name."""
    return Node(key=key, type=NodeType.CHARACTER, display_name=name or key, **kwargs)


def spawn_node(
    key: str,
    *,
    scene: str = "Forest",
    zone_key: str = "zone:forest",
    x: float = 10.0,
    y: float = 20.0,
    z: float = 30.0,
    **kwargs: object,
) -> Node:
    """Build a positioned synthetic spawn point."""
    return Node(
        key=key,
        type=NodeType.SPAWN_POINT,
        display_name=key,
        scene=scene,
        zone_key=zone_key,
        x=x,
        y=y,
        z=z,
        **kwargs,
    )


def load_canonical_sources(
    tmp_path: Path,
    graph: EntityGraph,
    acquisitions: list[ItemAcquisition],
    uses: list[ItemUse] | None = None,
    raw_outcomes_sql: str = "",
) -> None:
    """Persist typed facts through the real producer and read them through its repository."""
    path = tmp_path / "canonical.sqlite"
    writer = Writer(path)
    writer.create_schema()
    conn = writer.conn
    item_keys = {fact.item_stable_key for fact in (*acquisitions, *(uses or []))}
    item_keys.update(node.key for node in graph.nodes_of_type(NodeType.ITEM))
    conn.executemany(
        "INSERT INTO items (stable_key,display_name,image_name) VALUES (?,?,?)",
        [(key, key, key) for key in sorted(item_keys)],
    )
    conn.execute("INSERT INTO item_provenance_meta VALUES (1,'fixture','{}')")
    builder = ProvenanceBuilder(conn)
    builder.acquisitions.extend(acquisitions)
    builder.uses.extend(uses or [])
    builder.persist()
    conn.executescript(raw_outcomes_sql)
    conn.commit()
    conn.close()
    with DatabaseConnection(path, read_only=True) as database, database.connect() as connection:
        add_canonical_sources(ItemProvenanceRepository(database), connection, graph)
    graph.build_indexes()
