"""Binary serialization for the compiled guide format."""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass

from .compiler import CompiledData, SectionId

MAGIC = b"AGCG"
FORMAT_VERSION = 1


@dataclass(slots=True)
class _StringTable:
    _offsets: dict[str, int]
    _data: bytearray

    def __init__(self) -> None:
        self._offsets = {"": 0}
        self._data = bytearray(b"\x00")

    def intern(self, value: str | None) -> int:
        if not value:
            return 0
        if value in self._offsets:
            return self._offsets[value]
        offset = len(self._data)
        self._offsets[value] = offset
        self._data.extend(value.encode("utf-8"))
        self._data.append(0)
        return offset

    def to_bytes(self) -> bytes:
        return bytes(self._data)


class _SectionWriter:
    def __init__(self) -> None:
        self._sections: dict[SectionId, bytes] = {}

    def set(self, section: SectionId, payload: bytes) -> None:
        self._sections[section] = payload

    def get(self, section: SectionId) -> bytes:
        return self._sections.get(section, b"")


class _Csr:
    @staticmethod
    def encode(rows: list[list[int]]) -> bytes:
        buffer = io.BytesIO()
        offset = 0
        offsets: list[int] = []
        for row in rows:
            offsets.append(offset)
            offset += len(row)
        offsets.append(offset)
        for value in offsets:
            buffer.write(struct.pack("<I", value))
        for row in rows:
            for value in row:
                buffer.write(struct.pack("<I", value))
        return buffer.getvalue()


_SECTION_ORDER = list(SectionId)


def write(compiled: CompiledData) -> bytes:
    """Serialize :class:`CompiledData` into the AGCG binary format."""

    strings = _StringTable()
    sections = _SectionWriter()

    sections.set(SectionId.NODE_TABLE, _write_nodes(compiled, strings))
    sections.set(SectionId.EDGE_TABLE, _write_edges(compiled, strings))
    sections.set(SectionId.FORWARD_ADJACENCY, _Csr.encode(compiled.forward_adjacency))
    sections.set(SectionId.REVERSE_ADJACENCY, _Csr.encode(compiled.reverse_adjacency))
    sections.set(SectionId.QUEST_SPECS, _write_quest_specs(compiled))
    sections.set(SectionId.ITEM_SOURCE_INDEX, _write_item_sources(compiled, strings))
    sections.set(SectionId.UNLOCK_PREDICATES, _write_unlock_predicates(compiled))
    sections.set(SectionId.TOPOLOGICAL_ORDER, _write_topological_order(compiled))
    sections.set(SectionId.REVERSE_DEPS, _write_reverse_deps(compiled))
    sections.set(SectionId.ZONE_CONNECTIVITY, _write_zone_connectivity(compiled))
    sections.set(SectionId.QUEST_GIVER_BLUEPRINTS, _write_giver_blueprints(compiled, strings))
    sections.set(SectionId.QUEST_COMPLETION_BLUEPRINTS, _write_completion_blueprints(compiled, strings))
    sections.set(SectionId.FEASIBILITY, _write_feasibility(compiled))
    sections.set(SectionId.STRING_TABLE, strings.to_bytes())

    header_size = 17 + len(_SECTION_ORDER) * 9
    offsets: dict[SectionId, int] = {}
    cursor = header_size
    for section in _SECTION_ORDER:
        payload = sections.get(section)
        offsets[section] = cursor
        cursor += len(payload)

    buffer = io.BytesIO()
    buffer.write(MAGIC)
    buffer.write(struct.pack("<H", FORMAT_VERSION))
    buffer.write(struct.pack("<H", len(compiled.nodes)))
    buffer.write(struct.pack("<I", len(compiled.edges)))
    buffer.write(struct.pack("<H", len(compiled.quest_node_ids)))
    buffer.write(struct.pack("<H", len(compiled.item_node_ids)))
    buffer.write(struct.pack("<B", len(_SECTION_ORDER)))

    for section in _SECTION_ORDER:
        payload = sections.get(section)
        buffer.write(struct.pack("<BII", section.value, offsets[section], len(payload)))

    for section in _SECTION_ORDER:
        buffer.write(sections.get(section))

    return buffer.getvalue()


def serialize(compiled: CompiledData) -> bytes:
    """Alias matching the architecture plan wording."""

    return write(compiled)


def _write_nodes(compiled: CompiledData, strings: _StringTable) -> bytes:
    buffer = io.BytesIO()
    for node in compiled.nodes:
        buffer.write(struct.pack("<I", strings.intern(node.key)))
        buffer.write(struct.pack("<B", node.node_type))
        buffer.write(struct.pack("<I", strings.intern(node.display_name)))
        buffer.write(struct.pack("<I", strings.intern(node.scene)))
        buffer.write(struct.pack("<fff", node.x, node.y, node.z))
        buffer.write(struct.pack("<H", node.flags))
        buffer.write(struct.pack("<H", node.level))
        buffer.write(struct.pack("<I", strings.intern(node.zone_key)))
        buffer.write(struct.pack("<I", strings.intern(node.db_name)))
    return buffer.getvalue()


def _write_edges(compiled: CompiledData, strings: _StringTable) -> bytes:
    buffer = io.BytesIO()
    for edge in compiled.edges:
        buffer.write(struct.pack("<HH", edge.source_id, edge.target_id))
        buffer.write(struct.pack("<BB", edge.edge_type, edge.flags))
        buffer.write(struct.pack("<I", strings.intern(edge.group)))
        buffer.write(struct.pack("<B", edge.ordinal))
        buffer.write(struct.pack("<H", edge.quantity))
        buffer.write(struct.pack("<I", strings.intern(edge.keyword)))
        buffer.write(struct.pack("<H", edge.chance))
    return buffer.getvalue()


def _write_quest_specs(compiled: CompiledData) -> bytes:
    buffer = io.BytesIO()
    for quest_node_id in compiled.quest_node_ids:
        buffer.write(struct.pack("<H", quest_node_id))
    for spec in compiled.quest_specs:
        buffer.write(struct.pack("<B", len(spec.prereq_quest_ids)))
        for prereq_id in spec.prereq_quest_ids:
            buffer.write(struct.pack("<H", prereq_id))
        buffer.write(struct.pack("<B", len(spec.required_items)))
        for item in spec.required_items:
            buffer.write(struct.pack("<HHB", item.item_id, item.qty, item.group))
        buffer.write(struct.pack("<B", len(spec.steps)))
        for step in spec.steps:
            buffer.write(struct.pack("<BHB", step.step_type, step.target_id, step.ordinal))
        buffer.write(struct.pack("<B", len(spec.giver_node_ids)))
        for giver_id in spec.giver_node_ids:
            buffer.write(struct.pack("<H", giver_id))
        buffer.write(struct.pack("<B", len(spec.completer_node_ids)))
        for completer_id in spec.completer_node_ids:
            buffer.write(struct.pack("<H", completer_id))
        buffer.write(struct.pack("<B", len(spec.chains_to_ids)))
        for chained_id in spec.chains_to_ids:
            buffer.write(struct.pack("<H", chained_id))
        flags = (1 if spec.is_implicit else 0) | (2 if spec.is_infeasible else 0)
        buffer.write(struct.pack("<B", flags))
    return buffer.getvalue()


def _write_item_sources(compiled: CompiledData, strings: _StringTable) -> bytes:
    buffer = io.BytesIO()
    for item_node_id in compiled.item_node_ids:
        buffer.write(struct.pack("<H", item_node_id))
    for item_index, sources in enumerate(compiled.item_sources):
        buffer.write(struct.pack("<HH", item_index, len(sources)))
        for source in sources:
            buffer.write(
                struct.pack(
                    "<HBBHI",
                    source.source_id,
                    source.source_type,
                    source.edge_type,
                    source.direct_item_id,
                    strings.intern(source.scene),
                )
            )
            buffer.write(struct.pack("<B", len(source.positions)))
            for position in source.positions:
                buffer.write(struct.pack("<Hfff", position.spawn_id, position.x, position.y, position.z))
    return buffer.getvalue()


def _write_unlock_predicates(compiled: CompiledData) -> bytes:
    buffer = io.BytesIO()
    buffer.write(struct.pack("<H", len(compiled.unlock_predicates)))
    for predicate in compiled.unlock_predicates:
        buffer.write(struct.pack("<HB", predicate.target_id, len(predicate.conditions)))
        for condition in predicate.conditions:
            buffer.write(struct.pack("<HBB", condition.source_id, condition.check_type, condition.group))
        buffer.write(struct.pack("<BB", predicate.group_count, predicate.semantics))
    return buffer.getvalue()


def _write_topological_order(compiled: CompiledData) -> bytes:
    return b"".join(struct.pack("<H", quest_index) for quest_index in compiled.topo_order)


def _write_reverse_deps(compiled: CompiledData) -> bytes:
    return _Csr.encode(compiled.item_to_quest_indices) + _Csr.encode(compiled.quest_to_dependent_quest_indices)


def _write_zone_connectivity(compiled: CompiledData) -> bytes:
    buffer = io.BytesIO()
    buffer.write(struct.pack("<H", len(compiled.zone_node_ids)))
    for zone_node_id in compiled.zone_node_ids:
        buffer.write(struct.pack("<H", zone_node_id))
    buffer.write(_Csr.encode(compiled.zone_adjacency))
    for row in compiled.zone_line_ids:
        for zone_line_id in row:
            buffer.write(struct.pack("<H", zone_line_id))
    return buffer.getvalue()


def _write_giver_blueprints(compiled: CompiledData, strings: _StringTable) -> bytes:
    buffer = io.BytesIO()
    buffer.write(struct.pack("<H", len(compiled.giver_blueprints)))
    for blueprint in compiled.giver_blueprints:
        buffer.write(
            struct.pack(
                "<HHHB",
                blueprint.quest_id,
                blueprint.character_id,
                blueprint.position_id,
                blueprint.interaction_type,
            )
        )
        buffer.write(struct.pack("<I", strings.intern(blueprint.keyword)))
        buffer.write(struct.pack("<B", len(blueprint.required_quest_db_names)))
        for db_name in blueprint.required_quest_db_names:
            buffer.write(struct.pack("<I", strings.intern(db_name)))
    return buffer.getvalue()


def _write_completion_blueprints(compiled: CompiledData, strings: _StringTable) -> bytes:
    buffer = io.BytesIO()
    buffer.write(struct.pack("<H", len(compiled.completion_blueprints)))
    for blueprint in compiled.completion_blueprints:
        buffer.write(
            struct.pack(
                "<HHHBI",
                blueprint.quest_id,
                blueprint.character_id,
                blueprint.position_id,
                blueprint.interaction_type,
                strings.intern(blueprint.keyword),
            )
        )
    return buffer.getvalue()


def _write_feasibility(compiled: CompiledData) -> bytes:
    bit_count = len(compiled.nodes)
    bytes_needed = (bit_count + 7) // 8
    payload = bytearray(bytes_needed)
    for node_id in compiled.infeasible_node_ids:
        payload[node_id // 8] |= 1 << (node_id % 8)
    return bytes(payload)
