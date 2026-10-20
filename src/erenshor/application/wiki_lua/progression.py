"""Project the shared requirement graph into a checked wiki data view."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from loguru import logger

from erenshor.application.progression_wording import (
    ACTIONS,
    LEADS,
    ProgressionSentences,
    ProgressionWordingError,
    condition_text,
    node_text,
)
from erenshor.application.wiki_lua.lua_writer import module_text
from erenshor.application.wiki_lua.views import DataView, ViewDataError, ViewField, view_module_text
from erenshor.domain.value_objects.progression import UNMET_RELATIONS

if TYPE_CHECKING:
    from erenshor.domain.value_objects.progression import ProgressionNode, ProgressionWay

_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")

PROGRESSION = DataView(
    module="Progression",
    description="Requirement graph. Ways are alternatives. All needs of a way are required. "
    "Tiers are a playthrough order from a new character, not an assessment of a reader's save. "
    "A way row preserves a way even when it has no needs. The first flag marks the selected way. "
    "A way that needs its own node is left out, because it cannot be how a player gets the node.",
    entity="progression node",
    fields=(
        ViewField("type", "text", "node, way, or need."),
        ViewField("kind", "text", "Persisted node kind.", optional=True),
        ViewField("tier", "integer", "Playthrough tier. Absent when unreachable.", optional=True),
        ViewField("milestone", "boolean", "Whether the node is a milestone.", optional=True),
        ViewField("label", "reference", "Native identity with its label and optional page.", optional=True),
        ViewField("reward", "text", "Quest whose reward alone gives this item.", optional=True),
        ViewField("way", "text", "Persisted way key within the owning node.", optional=True),
        ViewField("first", "boolean", "Whether this is the node's first way.", optional=True),
        ViewField("sentence", "text", "Plain sentence of the way. A node appears as {stable key}.", optional=True),
        ViewField("relation", "text", "Persisted relation of this need.", optional=True),
        ViewField("need", "text", "Exact target node key. Absent for a worded condition.", optional=True),
        ViewField("quantity", "number", "Required quantity.", optional=True),
        ViewField("slot", "text", "Native slot or furnished room.", optional=True),
        ViewField("keywords", "text", "Dialog keywords.", optional=True),
        ViewField("text", "text", "Player wording of a typed condition.", optional=True),
        ViewField("advisory", "boolean", "Whether the need is advisory.", optional=True),
        ViewField("unconfirmed", "boolean", "Whether player access is unconfirmed.", optional=True),
        ViewField("required_level", "integer", "Required character level for this need.", optional=True),
    ),
)


class ProgressionDataRepository(Protocol):
    """Persisted graph records needed by the wiki view."""

    def get_nodes(self) -> tuple[ProgressionNode, ...]: ...

    def get_ways(self, key: str) -> tuple[ProgressionWay, ...]: ...


@dataclass(frozen=True)
class ProgressionData:
    """Checked rows and their serialized page sizes."""

    rows: dict[str, list[dict[str, object]]]
    content: str
    json_bytes: int
    node_count: int
    way_count: int
    need_count: int
    omitted_counts: dict[str, int]
    circular_ways: int

    @property
    def module_bytes(self) -> int:
        return len(self.content.encode("utf-8"))


def build_progression_data(
    repository: ProgressionDataRepository,
    known_keys: Collection[str],
    *,
    native_catalog: Mapping[str, Mapping[str, object]],
) -> ProgressionData:
    """Retain and validate connected requirement records before compact serialization."""
    all_nodes = sorted(repository.get_nodes(), key=lambda node: node.stable_key)
    ways_by_node = {node.stable_key: repository.get_ways(node.stable_key) for node in all_nodes}
    referenced = {
        need.need_stable_key
        for ways in ways_by_node.values()
        for way in ways
        for need in way.needs
        if need.need_stable_key is not None
    }
    # A start's sentence names its quest, so the quest stays even when it has no way of its own.
    referenced |= {
        node.stable_key.removeprefix("quest_start:")
        for node in all_nodes
        if node.kind == "quest_start" and ways_by_node[node.stable_key]
    }
    nodes = [node for node in all_nodes if ways_by_node[node.stable_key] or node.stable_key in referenced]
    omitted = Counter(
        node.kind for node in all_nodes if not ways_by_node[node.stable_key] and node.stable_key not in referenced
    )
    node_keys = {node.stable_key for node in nodes}
    catalog = {
        key: {field: value for field, value in entry.items() if field != "page" or key in known_keys}
        for key, entry in native_catalog.items()
    }
    names = {key: str(entry["name"]) for key, entry in native_catalog.items() if entry.get("name")}
    for node in nodes:
        if node.stable_key not in catalog and node.kind in {
            "mechanism",
            "barrier",
            "world_state",
            "account_state",
            "faction_standing",
        }:
            try:
                catalog[node.stable_key] = {"name": node_text(node, names)}
            except ProgressionWordingError as error:
                raise ViewDataError(f"{PROGRESSION.title}: node {node.stable_key}: {error}") from error
    # A way that needs its own node cannot be how a player first gets that node.
    kept = {
        node.stable_key: tuple(
            way
            for way in sorted(ways_by_node[node.stable_key], key=lambda way: way.way_key)
            if all(need.need_stable_key != node.stable_key for need in way.needs)
        )
        for node in nodes
    }
    circular_ways = sum(len(ways_by_node[key]) - len(ways) for key, ways in kept.items())
    writer = ProgressionSentences({node.stable_key: node for node in nodes}, kept, names)
    rows: dict[str, list[dict[str, object]]] = {}
    way_count = 0
    need_count = 0
    for node in nodes:
        key = node.stable_key
        identity_key = key.removeprefix("quest_start:") if node.kind == "quest_start" else key
        if identity_key not in catalog:
            raise ViewDataError(f"{PROGRESSION.title}: node {key}: unknown native identity {identity_key!r}")
        entry = catalog[identity_key]
        label = {"key": identity_key, "name": entry.get("name")}
        if entry.get("page") is not None:
            label["page"] = entry["page"]
        node_row: dict[str, object] = {
            "type": "node",
            "kind": node.kind,
            "milestone": node.is_milestone,
            "label": label,
        }
        if node.tier is not None:
            node_row["tier"] = node.tier
        rows[key] = [node_row]
        ways = kept[key]
        if node.first_way_key is not None and node.first_way_key not in {way.way_key for way in ways}:
            raise ViewDataError(f"{PROGRESSION.title}: node {key}: missing first way {node.first_way_key}")
        way_rows: list[dict[str, object]] = []
        for way in ways:
            way_count += 1
            way_row: dict[str, object] = {"type": "way", "way": way.way_key, "first": way.way_key == node.first_way_key}
            way_rows.append(way_row)
            rows[key].append(way_row)
            for index, need in enumerate(way.needs):
                need_count += 1
                where = f"{PROGRESSION.title}: node {key} way {way.way_key} need {index}"
                row: dict[str, object] = {"type": "need", "way": way.way_key, "relation": need.relation}
                if need.need_stable_key is not None:
                    if need.need_stable_key not in node_keys:
                        raise ViewDataError(f"{where}: unknown identity {need.need_stable_key!r}")
                    row["need"] = need.need_stable_key
                if need.condition_key is not None:
                    try:
                        row["text"] = condition_text(need.condition_key)
                    except ProgressionWordingError as error:
                        raise ViewDataError(f"{where}: {error}") from error
                if "need" not in row and "text" not in row:
                    raise ViewDataError(f"{where}: neither a target nor a condition")
                for field in ("quantity", "slot", "keywords", "required_level"):
                    value = getattr(need, field)
                    if value is not None:
                        row[field] = value
                if need.advisory:
                    row["advisory"] = True
                if need.unconfirmed:
                    row["unconfirmed"] = True
                rows[key].append(row)
        try:
            sentences = writer.sentences(key)
            reward = writer.reward_of(key)
        except ProgressionWordingError as error:
            raise ViewDataError(f"{PROGRESSION.title}: node {error}") from error
        for way_row, sentence in zip(way_rows, sentences, strict=True):
            unknown = sorted(set(_PLACEHOLDER.findall(sentence)) - node_keys)
            if unknown:
                raise ViewDataError(
                    f"{PROGRESSION.title}: node {key} way {way_row['way']}: names unknown nodes {unknown}"
                )
            way_row["sentence"] = sentence
        if reward is not None:
            node_row["reward"] = reward
    view_module_text(PROGRESSION, rows, known_keys, reference_catalog=catalog, entity_keys=node_keys)
    compact = compact_progression_data(rows)
    header = (
        f"-- {PROGRESSION.title}\n"
        "-- Generated by `erenshor wiki generate-lua`. The bot overwrites every edit of this page.\n"
        "-- Nodes contain kind, optional tier, milestone, name, optional page, optional first, optional\n"
        "-- reward, and ways. An omitted page means page=name. page=false means no page. first is a\n"
        "-- one-based way index. reward names the quest whose reward alone gives an item.\n"
        "-- Each way is a JSON array: the way's plain sentence, then one array per need. A sentence\n"
        "-- names a node as {stable key}. Need fields are relation, need, quantity, slot, keywords,\n"
        "-- text, advisory, unconfirmed, required_level. Internal nulls retain positions, and\n"
        "-- trailing nulls are omitted.\n"
        "-- _meta holds dedicated planning-slot defaults, the unmet relations, whose targets must stay\n"
        "-- undone and are no prerequisites, the action of each relation for map lines, and the lead of\n"
        "-- each node kind for titles.\n"
    )
    content = header + module_text(compact)
    json_bytes = len(json.dumps(compact, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return ProgressionData(
        rows,
        content,
        json_bytes,
        len(nodes),
        way_count,
        need_count,
        dict(sorted(omitted.items())),
        circular_ways,
    )


_NEED_FIELDS = ("relation", "need", "quantity", "slot", "keywords", "text", "advisory", "unconfirmed", "required_level")


def _packed_way(sentence: str, needs: Sequence[Mapping[str, object]]) -> str:
    """Encode a way as a JSON array: its sentence, then each need in _NEED_FIELDS order.

    Trailing null fields are omitted. Internal nulls retain positional meaning.
    JSON escaping preserves player text for lazy mw.text.jsonDecode in Lua.
    """
    packed: list[object] = [sentence]
    for row in needs:
        values = [row.get(field) for field in _NEED_FIELDS]
        while values and values[-1] is None:
            values.pop()
        packed.append(values)
    return json.dumps(packed, ensure_ascii=False, separators=(",", ":"))


def compact_progression_data(
    rows: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    """Keep node labels and pack each way for lazy decoding by the wiki renderer.

    An omitted page means the name is its page title. False means no page.
    First is a one-based way index and is absent without a persisted first way.
    The reserved _meta record carries dedicated planning-slot defaults, the
    relations whose targets must stay unmet, which no route follows, the action
    of each relation, and the title lead of each node kind.
    """
    compact: dict[str, object] = {}
    defaults: list[str] = []
    for key, records in sorted(rows.items()):
        source = records[0]
        label = source["label"]
        assert isinstance(label, Mapping)
        node: dict[str, object] = {
            "kind": source["kind"],
            "milestone": source["milestone"],
            "name": label["name"],
        }
        if "tier" in source:
            node["tier"] = source["tier"]
        if "reward" in source:
            node["reward"] = source["reward"]
        if label.get("page") is None:
            node["page"] = False
        elif label["page"] != label["name"]:
            node["page"] = label["page"]
        ways = [row for row in records if row["type"] == "way"]
        needs: dict[str, list[Mapping[str, object]]] = {str(way["way"]): [] for way in ways}
        for row in records:
            if row["type"] == "need":
                needs[str(row["way"])].append(row)
        node["ways"] = [_packed_way(str(way["sentence"]), needs[str(way["way"])]) for way in ways]
        for index, way in enumerate(ways, start=1):
            if way["first"]:
                node["first"] = index
        compact[key] = node
        if source["kind"] == "zone" and any(
            row["type"] == "need" and row["relation"] == "planning slot" and row.get("slot") != "rune slot"
            for row in records
        ):
            defaults.append(key)
    compact["_meta"] = {
        "defaults": defaults,
        "unmet": sorted(UNMET_RELATIONS),
        "actions": dict(sorted(ACTIONS.items())),
        "leads": dict(sorted(LEADS.items())),
    }
    return compact


def write_progression_module(
    repository: ProgressionDataRepository,
    known_keys: Collection[str],
    output_root: Path,
    *,
    native_catalog: Mapping[str, Mapping[str, object]],
    max_page_bytes: int,
) -> Path:
    """Write the checked module only when it fits the configured page budget."""
    data = build_progression_data(repository, known_keys, native_catalog=native_catalog)
    logger.info(
        "{}: {} Lua bytes, {} JSON bytes. Page budget {} bytes. Nodes {}, ways {}, needs {}. Omitted {}. "
        "Left out {} ways that need their own node.",
        PROGRESSION.title,
        data.module_bytes,
        data.json_bytes,
        max_page_bytes,
        data.node_count,
        data.way_count,
        data.need_count,
        data.omitted_counts,
        data.circular_ways,
    )
    if data.module_bytes > max_page_bytes:
        raise ViewDataError(
            f"{PROGRESSION.title}: {data.module_bytes} Lua bytes, {data.json_bytes} JSON bytes. "
            f"Page budget {max_page_bytes} bytes."
        )
    path = output_root / "Erenshor" / "Data" / "Progression.lua"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data.content, encoding="utf-8")
    return path
