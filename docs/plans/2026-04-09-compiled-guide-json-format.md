# Compiled Guide JSON Format

> **For agentic workers:** REQUIRED SUB-SKILL: Use skill://superpowers:subagent-driven-development (recommended) or skill://superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the custom AGCG binary format with JSON serialization for the compiled guide, eliminating ~1,100 lines of manual byte-layout coordination between Python and C#.

**Architecture:** The Python compiler produces `CompiledData` (unchanged). A new `json_writer.py` serializes it as JSON using `dataclasses.asdict()`. The C# loader deserializes via Newtonsoft.Json into mirror DTOs, then `CompiledGuide` builds its internal indexes from those DTOs. The binary format code is deleted entirely.

**Tech Stack:** Python `json` stdlib, C# Newtonsoft.Json 13.0.3 (already a dependency).

**Context:** Work happens in worktree at `/Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture`. The previous agent left uncommitted changes expanding the binary format to v2 — those changes to `compiler.py` (new `CompiledNode`/`CompiledEdge` fields) and `test_compiler.py` are keepers. All binary format changes (`binary_writer.py`, `BinaryFormat.cs`, `CompiledGuideLoader.cs`, etc.) are superseded by this plan.

---

## Prerequisite: Reset binary format changes

Before starting, discard the previous agent's uncommitted binary-format-specific changes while keeping the compiler field additions.

```bash
cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture

# Stage the compiler changes we want to keep
git stash push -m "wip-binary-v2" -- \
  src/erenshor/application/guide/compiler.py \
  tests/unit/application/guide/test_compiler.py

# Discard all other uncommitted changes
git checkout -- .

# Restore the compiler changes
git stash pop
```

After this, only `compiler.py` and `test_compiler.py` should show as modified.

---

## JSON format schema

The JSON mirrors `CompiledData` fields with integer IDs (same as the Python data model). Nodes carry their string key alongside their integer ID, so the C# side can build `key→ID` mappings without a separate string table.

```json
{
  "nodes": [
    {
      "node_id": 0,
      "key": "character:hunter",
      "node_type": 2,
      "display_name": "Hunter",
      "scene": "Forest",
      "x": 100.0, "y": 50.0, "z": 200.0,
      "flags": 0,
      "level": 10,
      "zone_key": "zone:forest",
      "db_name": null,
      "description": null,
      "keyword": null,
      "zone_display": "Whispering Forest",
      "xp_reward": 0,
      "gold_reward": 0,
      "reward_item_key": null,
      "disabled_text": null,
      "key_item_key": null,
      "destination_zone_key": null,
      "destination_display": null
    }
  ],
  "edges": [
    {
      "source_id": 0,
      "target_id": 1,
      "edge_type": 16,
      "flags": 0,
      "group": null,
      "ordinal": 0,
      "quantity": 0,
      "keyword": null,
      "chance": 0,
      "note": null,
      "amount": 0
    }
  ],
  "forward_adjacency": [[0, 1], [2], []],
  "reverse_adjacency": [[], [0], [1]],
  "quest_node_ids": [3, 7],
  "item_node_ids": [1, 5],
  "quest_specs": [
    {
      "quest_id": 3,
      "quest_index": 0,
      "prereq_quest_ids": [],
      "prereq_quest_indices": [],
      "required_items": [{"item_id": 1, "qty": 3, "group": 0}],
      "steps": [{"step_type": 3, "target_id": 5, "ordinal": 0}],
      "giver_node_ids": [0],
      "completer_node_ids": [0],
      "chains_to_ids": [],
      "is_implicit": false,
      "is_infeasible": false,
      "display_name": "The Hunt"
    }
  ],
  "item_sources": [
    [
      {
        "source_id": 0,
        "source_type": 2,
        "edge_type": 16,
        "direct_item_id": 0,
        "scene": "Forest",
        "positions": [{"spawn_id": 4, "x": 10.0, "y": 20.0, "z": 30.0}]
      }
    ]
  ],
  "unlock_predicates": [
    {
      "target_id": 8,
      "conditions": [{"source_id": 3, "check_type": 0, "group": 1}],
      "group_count": 1,
      "semantics": 1
    }
  ],
  "topo_order": [0, 1],
  "item_to_quest_indices": [[], [0]],
  "quest_to_dependent_quest_indices": [[], []],
  "zone_node_ids": [10, 11],
  "zone_adjacency": [[1], [0]],
  "zone_line_ids": [[42], [43]],
  "giver_blueprints": [
    {
      "quest_id": 3,
      "character_id": 0,
      "position_id": 4,
      "interaction_type": 1,
      "keyword": "hail",
      "required_quest_db_names": ["PREQ"]
    }
  ],
  "completion_blueprints": [
    {
      "quest_id": 3,
      "character_id": 0,
      "position_id": 4,
      "interaction_type": 0,
      "keyword": null
    }
  ],
  "infeasible_node_ids": [7]
}
```

NaN floats serialize as `null` in JSON. The C# loader converts `null` back to `float.NaN`.

---

## File map

### Delete
- `src/erenshor/application/guide/binary_writer.py` (291 lines)
- `tests/unit/application/guide/test_binary_writer.py` (113 lines)
- `src/mods/AdventureGuide/src/CompiledGuide/BinaryFormat.cs` (114 lines)

### Create
- `src/erenshor/application/guide/json_writer.py` (~50 lines)
- `tests/unit/application/guide/test_json_writer.py` (~60 lines)
- `src/mods/AdventureGuide/src/CompiledGuide/CompiledGuideData.cs` (~120 lines, JSON DTOs)

### Modify
- `src/erenshor/cli/commands/guide.py` — `compile` command uses `json_writer`, outputs `.json`
- `src/mods/AdventureGuide/src/CompiledGuide/CompiledGuideLoader.cs` — rewrite: JSON deserialization
- `src/mods/AdventureGuide/src/CompiledGuide/CompiledGuide.cs` — rewrite constructor: accept DTOs
- `src/mods/AdventureGuide/AdventureGuide.csproj` — embedded resource `guide.json`
- `src/mods/AdventureGuide/tests/.../CompiledGuideTypesTests.cs` — rewrite for JSON-based construction
- `src/mods/AdventureGuide/tests/.../CompiledGuideLoaderTests.cs` — rewrite for JSON round-trip
- `src/mods/AdventureGuide/tests/.../Helpers/CompiledGuideBuilder.cs` — rewrite: build from DTOs

### Unchanged
- `src/erenshor/application/guide/compiler.py` — still produces `CompiledData`
- `src/erenshor/application/guide/serializer.py` — still writes raw `entity-graph.json`
- `tests/unit/application/guide/test_compiler.py` — tests compilation logic, not format
- All `CompiledGuide` public API consumers (state, routing, UI, markers, etc.)

---

## Task 1: Python JSON writer + tests

**Files:**
- Create: `src/erenshor/application/guide/json_writer.py`
- Create: `tests/unit/application/guide/test_json_writer.py`
- Delete: `src/erenshor/application/guide/binary_writer.py`
- Delete: `tests/unit/application/guide/test_binary_writer.py`
- Modify: `src/erenshor/cli/commands/guide.py`

- [ ] **Step 1: Write failing test for JSON writer**

```python
# tests/unit/application/guide/test_json_writer.py
"""Unit tests for compiled guide JSON serialization."""

from __future__ import annotations

import json
import math

from erenshor.application.guide.compiler import compile_graph
from erenshor.application.guide.graph import EntityGraph
from erenshor.application.guide.json_writer import serialize
from erenshor.application.guide.schema import Edge, EdgeType, Node, NodeType


def _graph(*nodes: Node, edges: list[Edge] | None = None) -> EntityGraph:
    graph = EntityGraph()
    for node in nodes:
        graph.add_node(node)
    for edge in edges or []:
        graph.add_edge(edge)
    graph.build_indexes()
    return graph


def _quest(key: str, db_name: str | None = None) -> Node:
    return Node(key=key, type=NodeType.QUEST, display_name=key, db_name=db_name)


def _item(key: str) -> Node:
    return Node(key=key, type=NodeType.ITEM, display_name=key)


def test_serialize_produces_valid_json_with_expected_keys() -> None:
    compiled = compile_graph(_graph(_quest("quest:a", db_name="QUESTA"), _item("item:x")))
    output = serialize(compiled)
    data = json.loads(output)

    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)
    assert isinstance(data["quest_specs"], list)
    assert isinstance(data["topo_order"], list)
    assert isinstance(data["forward_adjacency"], list)
    assert isinstance(data["reverse_adjacency"], list)
    assert isinstance(data["quest_node_ids"], list)
    assert isinstance(data["item_node_ids"], list)
    assert isinstance(data["infeasible_node_ids"], list)
    assert len(data["nodes"]) == 2
    assert len(data["quest_specs"]) == 1


def test_serialize_round_trips_node_metadata() -> None:
    graph = _graph(
        Node(
            key="quest:root",
            type=NodeType.QUEST,
            display_name="Quest Root",
            db_name="ROOT",
            description="Recover the key.",
            zone="Starter Coast",
            zone_key="zone:starter",
            keyword="hail",
            xp_reward=120,
            gold_reward=34,
            reward_item_key="item:key",
            disabled_text="Night only",
        ),
        _item("item:key"),
    )
    compiled = compile_graph(graph)
    data = json.loads(serialize(compiled))

    quest = next(n for n in data["nodes"] if n["key"] == "quest:root")
    assert quest["description"] == "Recover the key."
    assert quest["keyword"] == "hail"
    assert quest["zone_display"] == "Starter Coast"
    assert quest["xp_reward"] == 120
    assert quest["gold_reward"] == 34
    assert quest["reward_item_key"] == "item:key"
    assert quest["disabled_text"] == "Night only"


def test_serialize_nan_positions_as_null() -> None:
    compiled = compile_graph(_graph(_quest("quest:a")))
    data = json.loads(serialize(compiled))

    node = data["nodes"][0]
    assert node["x"] is None
    assert node["y"] is None
    assert node["z"] is None


def test_serialize_round_trips_edge_metadata() -> None:
    graph = _graph(
        _quest("quest:root"),
        _item("item:key"),
        edges=[
            Edge(source="quest:root", target="item:key", type=EdgeType.REWARDS_ITEM, note="char:vendor", amount=5),
        ],
    )
    compiled = compile_graph(graph)
    data = json.loads(serialize(compiled))

    edge = data["edges"][0]
    assert edge["note"] == "char:vendor"
    assert edge["amount"] == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture && uv run pytest tests/unit/application/guide/test_json_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'erenshor.application.guide.json_writer'`

- [ ] **Step 3: Write the JSON writer**

```python
# src/erenshor/application/guide/json_writer.py
"""JSON serialization for the compiled guide format.

Replaces the custom binary (AGCG) format. The JSON mirrors CompiledData
fields directly — no string table, no CSR encoding, no section directory.
Adding a field means adding it to the Python dataclass and the C# DTO.
"""

from __future__ import annotations

import dataclasses
import json
import math
from typing import Any

from .compiler import CompiledData


def _sanitize(obj: Any) -> Any:
    """Replace NaN floats with None for JSON compatibility."""
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(item) for item in obj]
    if isinstance(obj, set):
        return sorted(obj)
    return obj


def to_dict(compiled: CompiledData) -> dict[str, Any]:
    """Convert CompiledData to a JSON-serializable dict."""
    return _sanitize(dataclasses.asdict(compiled))


def serialize(compiled: CompiledData) -> str:
    """Serialize CompiledData to a JSON string."""
    return json.dumps(to_dict(compiled), ensure_ascii=False, separators=(",", ":"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture && uv run pytest tests/unit/application/guide/test_json_writer.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Delete old binary writer and its tests**

```bash
cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture
rm -f src/erenshor/application/guide/binary_writer.py
rm -f tests/unit/application/guide/test_binary_writer.py
```

- [ ] **Step 6: Update CLI `compile` command to use JSON writer**

In `src/erenshor/cli/commands/guide.py`, update the `compile` function:
- Change default output from `guide.bin` to `guide.json`
- Replace `from erenshor.application.guide.binary_writer import write` with `from erenshor.application.guide.json_writer import serialize`
- Replace `binary = write(compiled)` / `output.write_bytes(binary)` with `output.write_text(serialize(compiled), encoding="utf-8")`
- Update the size reporting to use `output.stat().st_size`
- Update help text and option description

- [ ] **Step 7: Run compiler tests to verify nothing broke**

Run: `cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture && uv run pytest tests/unit/application/guide/ -v`
Expected: All tests in `test_compiler.py` and `test_json_writer.py` PASS. No tests reference `binary_writer`.

- [ ] **Step 8: Commit**

```bash
cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture
git add -A
git commit -m "refactor(pipeline): replace binary guide writer with JSON

The custom AGCG binary format required synchronized struct.pack
calls in Python and BinaryReader calls in C# — every field addition
touched five files and needed a format version bump.

The new JSON writer serializes CompiledData via dataclasses.asdict()
and json.dumps(). Adding a field means adding it to the Python
dataclass. NaN floats serialize as null.

The CLI 'guide compile' command now produces guide.json instead of
guide.bin."
```

---

## Task 2: C# JSON DTOs and loader

**Files:**
- Create: `src/mods/AdventureGuide/src/CompiledGuide/CompiledGuideData.cs`
- Delete: `src/mods/AdventureGuide/src/CompiledGuide/BinaryFormat.cs`
- Modify: `src/mods/AdventureGuide/src/CompiledGuide/CompiledGuideLoader.cs`
- Modify: `src/mods/AdventureGuide/src/CompiledGuide/CompiledGuide.cs`
- Modify: `src/mods/AdventureGuide/AdventureGuide.csproj`
- Modify: `src/mods/AdventureGuide/tests/.../CompiledGuideLoaderTests.cs`
- Modify: `src/mods/AdventureGuide/tests/.../CompiledGuideTypesTests.cs`
- Modify: `src/mods/AdventureGuide/tests/.../Helpers/CompiledGuideBuilder.cs`

- [ ] **Step 1: Create CompiledGuideData.cs with JSON DTOs**

Create `src/mods/AdventureGuide/src/CompiledGuide/CompiledGuideData.cs` with:
- `CompiledGuideData` — top-level container with all arrays/lists matching the JSON schema above
- `CompiledNodeData` — mirrors Python `CompiledNode` fields (key, node_type, display_name, scene, x/y/z as `float?`, flags, level, zone_key, db_name, description, keyword, zone_display, xp_reward, gold_reward, reward_item_key, disabled_text, key_item_key, destination_zone_key, destination_display)
- `CompiledEdgeData` — mirrors Python `CompiledEdge` fields
- `CompiledQuestSpecData` — mirrors Python `QuestSpec` fields
- `CompiledItemRequirementData` — mirrors Python `ItemRequirement`
- `CompiledStepData` — mirrors Python `StepSpec`
- `CompiledSourceSiteData` — mirrors Python `SourceSite`
- `CompiledSpawnPositionData` — mirrors Python `SpawnPosition`
- `CompiledUnlockPredicateData` — mirrors Python `UnlockPredicate`
- `CompiledUnlockConditionData` — mirrors Python `UnlockCondition`
- `CompiledGiverBlueprintData` — mirrors Python `QuestGiverBlueprint`
- `CompiledCompletionBlueprintData` — mirrors Python `QuestCompletionBlueprint`

All properties use `[JsonProperty("snake_case")]` attributes matching the Python field names. Nullable floats (`float?`) handle the NaN→null→NaN round-trip.

- [ ] **Step 2: Delete BinaryFormat.cs**

```bash
cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture
rm -f src/mods/AdventureGuide/src/CompiledGuide/BinaryFormat.cs
```

This removes `NodeRecord`, `EdgeRecord`, `SectionId`, `NodeFlags` (the binary-format copy), and the magic/version constants. The `NodeFlags` enum used by `CompiledGuide.BuildProjectedNode` moves into `CompiledGuideData.cs` (it represents domain flags, not format mechanics).

- [ ] **Step 3: Rewrite CompiledGuideLoader.cs**

Replace the 415-line `ParseCore` method (manual `BinaryReader` calls, string table, CSR decoding) with:
- `Load(ManualLogSource log)` — reads embedded resource `AdventureGuide.guide.json`, calls `ParseJson`
- `ParseJson(string json)` — `JsonConvert.DeserializeObject<CompiledGuideData>(json)`, returns `new CompiledGuide(data)`
- Resource name changes from `AdventureGuide.guide.bin` to `AdventureGuide.guide.json`

The entire method body becomes ~20 lines.

- [ ] **Step 4: Rewrite CompiledGuide constructor**

Replace the 30-parameter constructor that accepted binary-format arrays with a single-parameter constructor accepting `CompiledGuideData`.

The constructor:
1. Builds `_keyToId` dictionary from `data.Nodes` (key→index)
2. Builds `_projectedNodesById` by converting `CompiledNodeData` → `Node` (same projection logic as `BuildProjectedNode`, but reading DTO properties instead of `NodeRecord` + string table)
3. Builds `_projectedEdgesById` by converting `CompiledEdgeData` → `Edge` (resolving source/target keys from node array)
4. Builds forward/reverse adjacency from `data.ForwardAdjacency` / `data.ReverseAdjacency` (simple `int[][]` → `IReadOnlyList<Edge>[]`)
5. Builds quest/item indexes from `data.QuestNodeIds`, `data.ItemNodeIds`
6. Stores quest specs, item sources, unlock predicates, zone connectivity, blueprints from the DTO arrays
7. Builds all derived indexes (same as current: `_nodesByType`, `_questsByDbName`, `_typedOutEdges`, `_questsByItemKey`, scene maps, etc.)

The key change: no `byte[] _stringTable`, no `NodeRecord[]`, no `EdgeRecord[]`, no CSR arrays. All data comes from the DTO's typed properties.

Public API methods that currently use `NodeRecord` (`GetNode(int)`, `GetEdge(int)`, `GetString(uint)`, `GetNodeKey(int)`, `GetDisplayName(int)`, `GetScene(int)`, `ForwardEdgeIds(int)`, `ReverseEdgeIds(int)`) either:
- Change to use the projected `Node`/`Edge` arrays directly, or
- Get removed if they only existed to expose binary-format internals

Methods that return `ref readonly NodeRecord` or `ref readonly EdgeRecord` are replaced with methods returning `Node` / `Edge`.

Low-level int-based accessors (`QuestNodeId(int)`, `PrereqQuestIds(int)`, `RequiredItems(int)`, `GiverIds(int)`, etc.) continue to work but read from DTO arrays instead of binary-parsed arrays. The `ItemReq`, `StepEntry`, `SourceSiteEntry`, `SpawnPositionEntry`, `UnlockConditionEntry`, `UnlockPredicateEntry`, `QuestGiverEntry`, `QuestCompletion` structs that are currently in `CompiledGuide.cs` can remain as internal value types used by the int-based API — they're constructed from the DTO data at load time.

- [ ] **Step 5: Update csproj embedded resource**

In `src/mods/AdventureGuide/AdventureGuide.csproj`, change:
```xml
<!-- Before (will be added) -->
<EmbeddedResource Include="../../../quest_guides/guide.json" LogicalName="AdventureGuide.guide.json" />
```

The `entity-graph.json` resource stays for now (removed in a later cutover phase).

- [ ] **Step 6: Rewrite CompiledGuideBuilder test helper**

Rewrite `Helpers/CompiledGuideBuilder.cs` to build `CompiledGuideData` instead of manually constructing binary-format arrays. The builder's `Build()` method returns `CompiledGuide` by creating a `CompiledGuideData` instance and passing it to the new constructor. This eliminates the string table interning, CSR encoding, and the 30-parameter constructor call.

- [ ] **Step 7: Rewrite CompiledGuideLoaderTests.cs**

Replace `BuildMinimalBinary()` and `BuildBlueprintBinary()` (which manually construct binary byte arrays) with JSON string construction. The `Parse_reads_minimal_binary` test becomes `Parse_reads_minimal_json`. The `Parse_reads_blueprint_metadata` test uses a JSON fixture string.

The `Builder_creates_*` tests stay but use the rewritten builder.

- [ ] **Step 8: Rewrite CompiledGuideTypesTests.cs**

Replace manual `NodeRecord`/`EdgeRecord` construction with `CompiledGuideData` construction. The tests exercise the same public API but build guides from JSON DTOs.

Remove `BinaryFormat_constants_match_expected_values` (no more binary format constants).

- [ ] **Step 9: Build and run C# tests**

```bash
cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests --filter "CompiledGuideTypesTests|CompiledGuideLoaderTests"
```

Expected: All tests PASS.

- [ ] **Step 10: Run full mod build**

```bash
cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture
uv run erenshor mod build --mod adventure-guide
```

Expected: `Build succeeded.`

- [ ] **Step 11: Run full C# test suite**

```bash
cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests
```

Expected: All tests pass. Any test referencing `NodeRecord`, `EdgeRecord`, `BinaryFormat`, or `SectionId` has been updated.

- [ ] **Step 12: Commit**

```bash
cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture
git add -A
git commit -m "refactor(mod): replace binary guide loader with JSON deserialization

The custom AGCG binary format required a 415-line ParseCore method
with manual BinaryReader calls, a string table, CSR decoding, and
14 section parsers. The loader now deserializes a single JSON file
via Newtonsoft.Json into typed DTOs.

CompiledGuide accepts CompiledGuideData instead of 30 binary-format
arrays. Node and Edge projections build directly from DTO properties
instead of NodeRecord/EdgeRecord structs with string table offsets.

BinaryFormat.cs (NodeRecord, EdgeRecord, SectionId) is deleted.
CompiledGuideBuilder builds from DTOs instead of string interning
and CSR encoding.

The embedded resource changes from guide.bin to guide.json. The
entity-graph.json resource stays until the graph runtime cutover
completes."
```

---

## Task 3: Verify full pipeline

- [ ] **Step 1: Run all Python tests**

```bash
cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture
uv run pytest tests/unit/application/guide/ -v
```

Expected: All tests pass. No references to `binary_writer` remain.

- [ ] **Step 2: Run all C# tests**

```bash
cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests
```

Expected: All tests pass.

- [ ] **Step 3: Verify no stale references**

```bash
cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture
grep -rn "binary_writer\|BinaryFormat\|NodeRecord\|EdgeRecord\|SectionId\|FORMAT_VERSION\|MAGIC\|guide\.bin\|AGCG" \
  src/erenshor/application/guide/ \
  src/mods/AdventureGuide/src/CompiledGuide/ \
  src/mods/AdventureGuide/tests/ \
  --include='*.py' --include='*.cs' || echo "Clean: no stale references"
```

Expected: No matches (or only comments/docs mentioning the old format in past tense).

- [ ] **Step 4: Build the mod**

```bash
cd /Users/joaichberger/.config/superpowers/worktrees/Erenshor/quest-frontier-architecture
uv run erenshor mod build --mod adventure-guide
```

Expected: `Build succeeded.`
