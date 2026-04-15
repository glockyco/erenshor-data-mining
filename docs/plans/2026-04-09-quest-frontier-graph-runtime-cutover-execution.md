# Quest Frontier Graph Runtime Cutover Execution Plan

> For implementation on `quest-frontier-architecture`. Follow TDD per subsystem slice: add/adjust the failing test first, watch it fail, then implement the minimal production change.

## Goal
Remove `EntityGraph`, `GraphLoader`, `GraphIndexes`, and `entity-graph.json` from the AdventureGuide runtime and CLI pipeline so the compiled guide binary is the sole structural artifact.

## Architecture
Extend the compiled guide binary until it can carry every runtime and UI field still being read from graph nodes and edges, then cut over consumers from graph-backed helpers to compiled-guide-backed helpers one subsystem at a time. The runtime keeps live Unity state in `LiveStateTracker`, but all static metadata, routing topology, unlock predicates, blueprints, quest search inputs, and diagnostics metadata move behind compiled-guide accessors.

## Planned commits
1. `refactor(mod): expand compiled guide runtime contract`
   - Add the missing compiled node/edge metadata and zone-routing indexes needed to remove graph-backed runtime lookups.
   - Update Python compiler/binary writer, C# loader/types, and their focused tests.
2. `refactor(mod): cut over state and routing to compiled guide`
   - Replace graph-backed quest dependency, implicit quest, unlock, routing, and live-position adapters with compiled-guide-backed equivalents.
   - Delete graph-specific state helpers that become obsolete.
3. `refactor(mod): migrate ui and markers off graph metadata`
   - Move quest list, detail panel, marker blueprints, and action semantics onto compiled-guide metadata.
   - Remove `GraphIndexes` from the composition root and tests.
4. `refactor(cli): remove entity graph json pipeline`
   - Delete `guide generate`, JSON serializer plumbing, embedded JSON resource usage, remaining graph runtime types, and update docs/tests so `guide.bin` is the only guide artifact.

## Concrete work map

### Slice 1: Expand compiled guide metadata
- Python:
  - `src/erenshor/application/guide/compiler.py`
  - `src/erenshor/application/guide/binary_writer.py`
  - `src/erenshor/application/guide/schema.py` (docstrings/comments only if needed)
  - `tests/unit/application/guide/test_compiler.py`
  - `tests/unit/application/guide/test_binary_writer.py`
- C#:
  - `src/mods/AdventureGuide/src/CompiledGuide/BinaryFormat.cs`
  - `src/mods/AdventureGuide/src/CompiledGuide/CompiledGuide.cs`
  - `src/mods/AdventureGuide/src/CompiledGuide/CompiledGuideLoader.cs`
  - `src/mods/AdventureGuide/tests/AdventureGuide.Tests/CompiledGuideLoaderTests.cs`
  - `src/mods/AdventureGuide/tests/AdventureGuide.Tests/CompiledGuideTypesTests.cs`
- Required additions:
  - node metadata now only present on `Graph.Node`: description, zone display text, keyword, rewards, disabled text, door/zone-line fields, etc.
  - edge metadata now only present on `Graph.Edge`: note/vendor source key, amount/faction delta, and any other fields still read by UI/runtime.
  - compiled indexes for zone routing and live-source invalidation currently provided by `GraphIndexes`: zone-line adjacency with line IDs, scene-local quest giver/completion/static-source blueprints, item->quest deps, quest->quest deps, source->quest deps, implicit quest activation scenes, and scene->zone display lookup.

### Slice 2: Cut over state and routing
- Replace graph-backed state helpers with compiled equivalents:
  - `src/mods/AdventureGuide/src/State/QuestStateTracker.cs`
  - `src/mods/AdventureGuide/src/State/GameState.cs`
  - `src/mods/AdventureGuide/src/State/UnlockEvaluator.cs` or compiled replacement
  - `src/mods/AdventureGuide/src/State/Resolvers/DoorStateResolver.cs`
  - `src/mods/AdventureGuide/src/State/Resolvers/CompiledGuideLivePositionProvider.cs`
  - `src/mods/AdventureGuide/src/State/LiveStateTracker.cs`
  - `src/mods/AdventureGuide/src/Position/ZoneRouter.cs`
  - `src/mods/AdventureGuide/src/Position/ZoneAccessResolver.cs`
- Replace graph lookups with compiled equivalents for:
  - quest db-name/key/index mapping
  - implicit quest activation scenes
  - reverse dependency expansion on item / prerequisite changes
  - unlock evaluation labels and target-type dispatch
  - zone-line routing graph and first locked hop metadata
  - live source -> affected quest invalidation
- Delete obsolete graph-backed helpers as their last callers disappear.

### Slice 3: Cut over UI, markers, and action semantics
- Files:
  - `src/mods/AdventureGuide/src/UI/QuestListPanel.cs`
  - `src/mods/AdventureGuide/src/UI/ViewRenderer.cs`
  - `src/mods/AdventureGuide/src/Markers/MarkerComputer.cs`
  - `src/mods/AdventureGuide/src/Resolution/NavigationTargetResolver.cs`
  - `src/mods/AdventureGuide/src/Resolution/ResolvedActionSemanticBuilder.cs`
  - `src/mods/AdventureGuide/src/Navigation/NavigationEngine.cs`
  - `src/mods/AdventureGuide/src/Navigation/NavigationTargetSelector.cs`
  - tests alongside each subsystem
- Replace graph-backed metadata reads with compiled accessors for:
  - quest list filter/search inputs and zone labels
  - detail header/rewards/chain/unlock/faction text
  - marker blueprints and pending/implicit completion metadata
  - synthetic node creation for explanations and nav text
  - any fallback graph node reconstruction still performed by navigation/marker code

### Slice 4: Remove graph runtime and JSON pipeline
- C# deletions once no callers remain:
  - `src/mods/AdventureGuide/src/Graph/EntityGraph.cs`
  - `src/mods/AdventureGuide/src/Graph/GraphLoader.cs`
  - `src/mods/AdventureGuide/src/Graph/GraphIndexes.cs`
  - graph-only node/edge/blueprint helpers no longer needed
  - graph-based test helpers (`TestGraphBuilder`, `SnapshotHarness`) after replacing them with compiled-guide builders where still needed
- Composition root and project file:
  - `src/mods/AdventureGuide/src/Plugin.cs`
  - `src/mods/AdventureGuide/AdventureGuide.csproj`
- CLI/pipeline:
  - `src/erenshor/cli/commands/guide.py`
  - `src/erenshor/application/guide/serializer.py`
  - any JSON-only tests
- Docs/comments:
  - update plan/follow-up docs touched by this work if they still claim JSON is active
  - ensure no `entity-graph.json` reference remains in AdventureGuide mod source, csproj, or CLI path

## Verification checkpoints
- Slice 1:
  - `uv run pytest tests/unit/application/guide/test_compiler.py tests/unit/application/guide/test_binary_writer.py`
  - `dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests --filter "CompiledGuide"`
- Slice 2:
  - targeted AdventureGuide tests for quest state, unlocks, zone access, and navigation selection
- Slice 3:
  - targeted AdventureGuide tests for view rendering, markers, explanations, and tracker summaries
- Final:
  - `uv run erenshor mod build --mod adventure-guide`
  - grep the worktree for `entity-graph.json`, `GraphLoader`, `EntityGraph`, and `GraphIndexes` to confirm only intentionally retained docs/tests remain until the final deletion commit, then confirm zero live references
