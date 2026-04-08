"""Unit tests for guide binary serialization."""

from __future__ import annotations

import struct

from erenshor.application.guide.binary_writer import FORMAT_VERSION, MAGIC, write
from erenshor.application.guide.compiler import SectionId, compile_graph
from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.schema import Node, NodeType


def _graph(*nodes: Node) -> EntityGraph:
    graph = EntityGraph()
    for node in nodes:
        graph.add_node(node)
    graph.build_indexes()
    return graph


def _quest(key: str, db_name: str | None = None) -> Node:
    return Node(key=key, type=NodeType.QUEST, display_name=key, db_name=db_name)


def _item(key: str) -> Node:
    return Node(key=key, type=NodeType.ITEM, display_name=key)


def test_magic_and_version() -> None:
    binary = write(compile_graph(_graph(_quest("quest:a"))))

    assert binary[:4] == MAGIC
    assert struct.unpack_from("<H", binary, 4)[0] == FORMAT_VERSION


def test_header_counts_match_compiled_data() -> None:
    compiled = compile_graph(_graph(_quest("quest:a"), _item("item:x")))
    binary = write(compiled)

    assert struct.unpack_from("<H", binary, 6)[0] == len(compiled.nodes)
    assert struct.unpack_from("<I", binary, 8)[0] == len(compiled.edges)
    assert struct.unpack_from("<H", binary, 12)[0] == len(compiled.quest_node_ids)
    assert struct.unpack_from("<H", binary, 14)[0] == len(compiled.item_node_ids)
    assert struct.unpack_from("<B", binary, 16)[0] == len(SectionId)


def test_section_directory_contains_all_sections() -> None:
    binary = write(compile_graph(_graph(_quest("quest:a"))))

    section_count = struct.unpack_from("<B", binary, 16)[0]
    ids = [struct.unpack_from("<B", binary, 17 + index * 9)[0] for index in range(section_count)]
    assert ids == [section.value for section in SectionId]
