# Entity Graph Runtime Removal — Design Spec

## Goal

Remove `EntityGraph`, `GraphLoader`, `GraphIndexes`, the `entity-graph.json`
embedded resource, and the `guide generate` CLI command from the AdventureGuide
mod runtime. After this change, `CompiledGuide` is the sole data source for all
runtime, UI, marker, navigation, state, and diagnostic surfaces.

## Non-goals

- Changing the Python build pipeline. `graph_builder.py`, `graph.py`,
  `schema.py`, `graph_overrides.py`, and `generator.py` stay. The compiler
  still builds `EntityGraph` at compile time to produce `CompiledData`. The
  Python graph is a build-time artifact.
- Removing the `Graph/` C# namespace. `Node.cs`, `Edge.cs`, `NodeType.cs`,
  `EdgeType.cs`, and the blueprint types survive — `CompiledGuide` returns
  these types.
- Performance optimization of CompiledGuide internals. This is a cutover,
  not an optimization pass.

## Key Insight

`CompiledGuide` already mirrors the full `EntityGraph` + `GraphIndexes` public
API. It returns the same `Node` and `Edge` types and exposes identically-named
methods: `GetNode(string)`, `GetQuestByDbName(string)`, `NodesOfType(NodeType)`,
`OutEdges(string, EdgeType)`, `InEdges(string, EdgeType)`, `AllNodes`,
`NodeCount`, `EdgeCount`, `GetQuestsDependingOnItem(string)`,
`GetQuestsDependingOnQuest(string)`, `GetQuestGiversInScene(string)`,
`GetQuestCompletionsInScene(string)`, `GetStaticSourcesInScene(string)`,
`GetQuestsTouchingSource(string)`.

The migration is therefore mechanical: replace constructor parameters, field
types, and call sites. No new compiled data sections are needed.

## Changes by category

### 1. Mechanical constructor/call-site replacement (24 files)

Every file that accepts `EntityGraph` or `GraphIndexes` as a constructor
parameter changes to accept `CompiledGuide` instead. Field types change
accordingly. Call sites change from `_graph.Method()` / `_indexes.Method()` to
`_guide.Method()`.

Files affected:

| Layer | Files |
|---|---|
| Plugin | `Plugin.cs` |
| State | `GameState.cs`, `QuestStateTracker.cs`, `LiveStateTracker.cs`, `LiveSceneScope.cs`, `NavigationSetPersistence.cs`, `CompiledGuideLivePositionProvider.cs`, `DoorStateResolver.cs` |
| Position | `ZoneRouter.cs`, `ZoneAccessResolver.cs`, `PositionResolverRegistry.cs`, `CharacterPositionResolver.cs`, `WaterPositionResolver.cs`, `ZonePositionResolver.cs` |
| Resolution | `NavigationTargetResolver.cs`, `ResolvedActionSemanticBuilder.cs` |
| Markers | `MarkerComputer.cs` |
| Navigation | `NavigationEngine.cs`, `NavigationTargetSelector.cs` |
| UI | `QuestListPanel.cs`, `ViewRenderer.cs`, `TrackerPanel.cs` |
| Diagnostics | `DebugAPI.cs` |

The call-site mapping is 1:1 — every `EntityGraph` method has a
`CompiledGuide` method with the same name, parameters, and return type.

### 2. UnlockEvaluator rewrite

`UnlockEvaluator` currently traverses graph edges to find unlock conditions:

```csharp
_graph.InEdges(targetKey, EdgeType.UnlocksZoneLine)
_graph.GetNode(edge.Source) // → check if quest is completed
```

Replace with the pre-compiled unlock predicates already in CompiledGuide:

```csharp
_guide.TryGetUnlockPredicate(nodeId, out var predicate)
// iterate predicate.Conditions — same live-state checks, no graph traversal
```

The live-state evaluation logic (is quest completed? is item possessed?) stays.
Only the structural lookup changes.

### 3. Plugin.cs simplification

Delete:
- `GraphLoader.Load(Log)` call
- `new GraphIndexes(_graph)` call
- `_graph` and `_graphIndexes` fields
- All downstream threading of these through constructor calls

`CompiledGuide` (already loaded via `CompiledGuideLoader.Load`) becomes the
sole data parameter passed to all layers.

### 4. Bridge file elimination

`CompiledGuideLivePositionProvider` exists solely to convert compiled guide
int IDs back to EntityGraph `Node` objects for LiveStateTracker. Since
CompiledGuide already returns `Node` objects via `GetNode(string)`, this
bridge layer collapses. The provider can call `_guide.GetNode(key)` directly.

`NavigationTargetResolver.CreateSyntheticNode` already demonstrates building
Node from CompiledNodeData as a fallback path. With the graph removed, the
primary path uses `_guide.GetNode(key)` which returns the same projected Node.

### 5. Deletions

**C# files to delete:**
- `src/mods/AdventureGuide/src/Graph/EntityGraph.cs`
- `src/mods/AdventureGuide/src/Graph/GraphIndexes.cs`
- `src/mods/AdventureGuide/src/Graph/GraphLoader.cs`

**C# files that survive in Graph/:**
- `Node.cs`, `Edge.cs`, `NodeType.cs`, `EdgeType.cs`
- `QuestGiverBlueprint.cs`, `QuestCompletionBlueprint.cs`, `StaticSourceBlueprint.cs`
- `MarkerInteraction.cs`, `MarkerInteractionKind.cs` (if present)

**Embedded resource removal:**
- Remove `entity-graph.json` from `AdventureGuide.csproj`
- Delete `quest_guides/entity-graph.json` (5.1 MB)

**Python deletions:**
- Delete `src/erenshor/application/guide/serializer.py` (raw graph JSON writer)
- Delete `guide generate` command from `src/erenshor/cli/commands/guide.py`

**Python files that survive:**
- `graph_builder.py`, `graph.py`, `schema.py`, `graph_overrides.py`,
  `generator.py` — used by `guide compile`
- `compiler.py`, `json_writer.py` — the compiled guide pipeline

### 6. Test updates

Any test that constructs `EntityGraph` or `GraphIndexes` directly for testing
runtime consumers must switch to `CompiledGuideBuilder`. Tests for the
compiler itself (`test_compiler.py`) still use `EntityGraph` because that's
the compiler's input.

Tests for `EntityGraph`/`GraphIndexes`/`GraphLoader` themselves are deleted.

## Verification

- `dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests` — all pass
- `uv run erenshor mod build --mod adventure-guide` — build succeeds
- `uv run pytest tests/unit/application/guide/ -v` — all pass
- `grep -rn 'EntityGraph\|GraphLoader\|GraphIndexes' src/mods/AdventureGuide/src/ --include='*.cs'` — only hits in surviving `Graph/*.cs` DTO files, not in consumers
- `grep -rn 'entity-graph\.json' src/mods/AdventureGuide/` — no hits
- `grep -rn 'guide generate\|serializer' src/erenshor/cli/` — no hits for the deleted command
