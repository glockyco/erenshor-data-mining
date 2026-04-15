# Quest Frontier Graph/JSON Runtime Cutover Follow-up

## Why this update is needed

The approved quest-frontier architecture plan assumed that once the legacy
quest-plan runtime and UI projection were deleted, the remaining graph and JSON
artifacts could be removed in the same cleanup phase. After the clean-cut
runtime deletion, that assumption is no longer true.

The work completed on this branch removed `QuestResolutionService`, the
quest-plan/projection types, `LazyTreeProjector`, and their tests. The live mod
now resolves navigation, markers, tracker text, and detail-tree structure from
compiled-guide data. However, the runtime still has broad first-class
`EntityGraph` and `GraphLoader` dependencies that are not fallback shims:

- `Plugin` still loads `entity-graph.json` through `GraphLoader.Load(...)`.
- `GraphIndexes`, `QuestStateTracker`, `GameState`, `UnlockEvaluator`,
  `ZoneRouter`, `LiveStateTracker`, and multiple position resolvers still depend
  on `EntityGraph` as their canonical structural model.
- `QuestListPanel`, `ViewRenderer`, `MarkerComputer`, and diagnostics still read
  metadata and reward/scene information from graph nodes and graph-derived
  blueprints.
- The CLI `guide generate` command, the embedded `entity-graph.json` resource in
  `AdventureGuide.csproj`, and graph-specific docs still describe JSON as an
  active artifact.

Deleting the JSON graph pipeline now would not be cleanup; it would be a second
major architecture project: replacing graph-backed world metadata, unlock/routing
inputs, and UI metadata with compiled-guide-backed equivalents.

## Clean-cut rule for the follow-up

Do not reintroduce any legacy quest-plan or `QuestResolutionService` types.
Continue forward from the compiled-guide architecture only. If a graph-backed
capability is still needed, replace it with a compiled-guide-backed
representation and then delete the graph-based code in the same phase.

## Proposed next phases

### Phase A: Define the remaining graph contract explicitly

Document the exact `EntityGraph` responsibilities that still survive after the
quest-plan cutover, grouped by subsystem:

- gameplay state / unlock checks
- zone routing
- quest list search and metadata
- detail panel rewards and descriptions
- marker scene blueprints
- diagnostics and snapshot export

For each responsibility, decide whether the compiled guide should absorb it or
whether a smaller non-JSON structural artifact should remain. Do not start code
changes until this contract is explicit.

### Phase B: Extend compiled-guide data for graph-owned UI/runtime metadata

Add the missing compiled fields needed to make graph removal possible, including
at minimum the metadata currently consumed directly from graph nodes and edges:

- quest descriptions and reward fields used by `ViewRenderer`
- reward / chain / unlock edge data used by the detail panel and quest list
- zone-routing edge metadata now read through `EntityGraph` / `ZoneRouter`
- any node flags or scene indexes still only derivable from graph parsing

This phase touches both Python compilation and C# loading/tests. The binary must
become the authoritative source for every field that would otherwise force
runtime graph loading.

### Phase C: Replace graph-derived runtime helpers subsystem by subsystem

Cut over the remaining graph-backed helpers in isolation, with focused tests and
one commit per subsystem:

1. routing + unlock prerequisites (`ZoneRouter`, `UnlockEvaluator` and related
   state resolvers)
2. quest list / detail metadata readers (`QuestListPanel`, `ViewRenderer`)
3. marker scene blueprints (`GraphIndexes` quest giver/completion/static source
   helpers)
4. diagnostics / snapshot metadata assumptions

Each slice must delete the old graph-backed helper as soon as the compiled
replacement is live.

### Phase D: Remove graph loading and JSON generation entirely

Only after Phases B and C leave no live callers:

- delete `GraphLoader`, `EntityGraph`, `GraphIndexes`, and any graph-only node /
  edge helpers that no longer serve another subsystem
- delete `guide generate` and JSON serializer paths in `src/erenshor`
- remove the `entity-graph.json` embedded resource from
  `src/mods/AdventureGuide/AdventureGuide.csproj`
- update README / AGENTS / docs so the compiled guide is the sole data artifact

## Verification expectations

For every follow-up slice, require both:

- focused `dotnet test` coverage for the affected subsystem
- `uv run erenshor mod build --mod adventure-guide`

For the final graph/JSON removal slice, also verify that no `entity-graph.json`
reference remains in the AdventureGuide mod source, csproj, or CLI path.

## Current branch state this plan builds on

These commits are already complete and should not be revisited except as callers
are deleted:

- `refactor(mod): require compiled runtime navigation stack`
- `feat(mod): project detail panel from compiled specs`
- `refactor(mod): delete legacy quest plan runtime`
