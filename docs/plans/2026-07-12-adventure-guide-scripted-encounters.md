---
title: Adventure Guide Implicit Workflow Quests & Location Steps
type: plan
status: draft
created: 2026-07-12
parent: 2026-07-09-erenshor-planning-overview
---

# Adventure Guide Implicit Workflow Quests & Location Steps

Keep scripted arena and Malaroth workflows in the existing quest experience.
Generate guide-only `QuestEntry` records with `acceptance=implicit` and
`flags.repeatable=true`, backed by an explicit guide-only lifecycle rather than
`GameData.HasQuest` / `GameData.CompletedQuests`. Purchase steps use the generic
`Buy <item>` contract; coordinate-backed `go_to` steps represent passive event
triggers independently. Keep `travel` reserved for quest-completing zone entry.

The real `VithTokenMOB1..8` quests remain first-clear vendor-unlock turn-ins, and
the real `MalarothFeedMade` variants remain feed-crafting turn-ins. The generated
workflow quests reference those facts but never extend or masquerade as those
game quest identities.

## File map

- Modify `src/Assets/Editor/Database/DynamicCharacterSpawnRecord.cs`: persist
  the item consumed by a scripted spawn trigger plus trigger semantics, bounds,
  and a display label.
- Modify `src/Assets/Editor/Database/ArenaRoundRecord.cs`: persist the arena
  entry anchor, bounds, and trigger metadata once per round.
- Modify `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnCatalog.cs`:
  parse declarative trigger-item and event metadata.
- Modify `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnSourceListener.cs`:
  resolve configured trigger items and write event metadata with dynamic spawn
  rows.
- Modify `src/Assets/Editor/ExportSystem/AssetScanner/Listener/VithArenaListener.cs`:
  export the passive arena entry independently from combat and reward
  positions.
- Modify `src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml`:
  map normal and odd Malaroth feed inputs and host trigger bounds without
  guide-side name checks.
- Modify `src/erenshor/application/processor/characters.py`: carry scripted
  trigger metadata into clean spawn and arena records.
- Modify `src/erenshor/application/processor/writer.py`: define the clean
  trigger columns consumed by guide generation.
- Create `tests/unit/application/processor/test_scripted_workflows.py`: defend
  trigger inputs, priorities, labels, and coordinate separation.
- Modify `src/erenshor/application/guide/schema.py`: add a guide-only quest flag,
  location nodes, and navigation-only `STEP_GO_TO` edges.
- Modify `src/erenshor/application/guide/graph_builder.py`: generate namespaced
  implicit repeatable workflow quests from arena and Malaroth facts while
  preserving the real quests unchanged.
- Modify `src/erenshor/application/guide/compiler.py`: carry guide-only workflow
  descriptors without placing synthetic records in game-quest topology or
  completion analysis.
- Modify `tests/unit/application/guide/test_compiler.py`: cover identity,
  isolation, ordering, trigger evidence, and enum stability.
- Modify `src/erenshor/application/guide/mod_writer.py`: emit workflow quests in
  the existing `quests` collection with vendor-neutral actions, structured
  sources, fixed locations, and cycle evidence.
- Modify `tests/unit/application/guide/test_mod_writer.py`: cover deterministic
  guide-only quest output and separation from real quest DB names.
- Modify `src/mods/AdventureGuide/src/Data/QuestEntry.cs`: deserialize
  `guide_only`, workflow-cycle metadata, structured item sources, and locations.
- Modify `src/mods/AdventureGuide/src/Data/GuideData.cs`: index guide-only quests
  with collision checks while preserving the single quest list/search surface.
- Create `src/mods/AdventureGuide/src/State/GuideWorkflowState.cs`: evaluate the
  current cycle stage from bounded inventory, trigger, entity, and loot evidence.
- Modify `src/mods/AdventureGuide/src/State/QuestStateTracker.cs`: expose one
  entry-aware status API that delegates game-backed and guide-only lifecycle
  correctly.
- Modify `src/mods/AdventureGuide/src/State/StepProgress.cs`: delegate
  guide-only current-step selection to the workflow state instead of
  `GameData` completion.
- Modify `src/mods/AdventureGuide/src/State/TrackerState.cs`: keep guide-only
  repeatable pins out of completed-game-quest pruning.
- Modify `src/mods/AdventureGuide/src/UI/QuestListPanel.cs`: reuse the existing
  filters, search, sort, and `[R]` presentation with guide-only status.
- Modify `src/mods/AdventureGuide/src/UI/QuestDetailPanel.cs`: reuse the existing
  step/source/navigation rendering with cycle-aware state.
- Modify `src/mods/AdventureGuide/src/UI/TrackerWindow.cs`: show and advance the
  current workflow stage without terminal auto-untracking.
- Modify `src/mods/AdventureGuide/src/Navigation/NavigationController.cs`: route
  to a fixed scene coordinate and preserve tracked synthetic quest identity.
- Modify `src/mods/AdventureGuide/src/Navigation/WorldMarkerSystem.cs`: emit the
  current coordinate or scripted-target objective through the existing marker
  system.
- Modify `src/mods/AdventureGuide/src/Navigation/EntityRegistry.cs`: discover
  scripted `Object.Instantiate` characters through bounded, descriptor-scoped
  registration rather than only `SpawnPoint.SpawnNPC`.
- Modify `src/mods/AdventureGuide/src/Navigation/LootScanner.cs`: expose
  descriptor-scoped reward-container evidence without making global scans part
  of per-frame step evaluation.
- Modify `src/mods/AdventureGuide/src/Patches/InventoryPatch.cs`: notify workflow
  state after inventory changes so trigger-item acquisition/consumption is
  observed with a before/after count.
- Modify `src/mods/AdventureGuide/src/Patches/DeathPatch.cs`: notify workflow
  state when a scripted target dies.
- Create `src/mods/AdventureGuide/src/Patches/ScriptedEntityPatch.cs`: observe
  descriptor-matched `Character.Start` instances created outside
  `SpawnPoint.SpawnNPC`.
- Modify `src/mods/AdventureGuide/src/Plugin.cs`: construct, wire, revalidate,
  and dispose the workflow state service.
- Create `tests/unit/mods/test_adventure_guide_workflows.py`: defend the
  guide-only semantic firewall, cycle transitions, shared quest UI, navigation,
  markers, and bounded-update contract.
- Regenerate `quest_guides/guide.json` and `quest_guides/quest-guide.json`
  through the canonical guide commands.

## Tasks

### Task 1: Export passive trigger facts

**Files:**
- Modify: `src/Assets/Editor/Database/DynamicCharacterSpawnRecord.cs`
- Modify: `src/Assets/Editor/Database/ArenaRoundRecord.cs`
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnCatalog.cs`
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnSourceListener.cs`
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/Listener/VithArenaListener.cs`
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/TriggerBoundsResolver.cs`
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml`
- Modify: `src/erenshor/application/processor/characters.py`
- Modify: `src/erenshor/application/processor/writer.py`
- Create: `tests/unit/application/processor/test_scripted_workflows.py`

- [x] Add `trigger_item_field`, `event_display_name`, `trigger_mode`, and host
  trigger-bounds capture to the dynamic-spawn catalog contract. Split the
  `MalarothFeed.Malaroth` and `.Demented` outputs so they resolve
  `MalarothFood` and `BadFood` respectively; both use the existing host
  `EventX/Y/Z` anchor and `proximity_auto_consume` mode.
- [x] Resolve the configured Unity `Item` reference in
  `DynamicSpawnSourceListener` and persist its stable key beside the spawned
  character. Fail the export when a declared trigger item cannot be resolved.
- [x] Extend every `ArenaRoundRecord` with the `VithArena` host transform and
  trigger collider bounds as the entry area, display label `Vitheo's arena`,
  and `proximity_auto_consume`. Keep `SpawnLoc1/2/3` and `ChestSpawnPos` as
  combat and reward locations, not the trigger destination.
- [x] Carry all new columns into the clean DB. Preserve the Malaroth NPC spawn
  `(428.40, 28.37, 642.20)` separately from the feeding trigger
  `(336.06, 32.31, 673.63)` and the arena trigger separately from the chest
  `(521.90, 25.21, 485.60)`.
- [x] Add processor tests proving good feed maps to Shivunax, odd feed
  maps to Demented Malaroth, bad-food priority is retained, and trigger/spawn
  coordinates cannot be interchanged.
- [x] Run `uv run pytest tests/unit/application/processor/test_scripted_workflows.py tests/unit/application/export_surface/test_listener_coverage.py`.
  Expected: trigger metadata is complete and unrelated spawn rows are unchanged.
- [x] Run `uv run erenshor --variant playtest extract export`, then inspect the
  raw rows. Expected: eight arena rounds carry one finite entry area each and
  both Malaroth outputs carry the correct input item and shared finite feeding
  area.
- [x] Commit. Message: `feat(export): capture scripted workflow triggers`

### Task 2: Generate guide-only implicit repeatable quests

**Files:**
- Modify: `src/erenshor/application/guide/schema.py`
- Modify: `src/erenshor/application/guide/graph_builder.py`
- Modify: `src/erenshor/application/guide/compiler.py`
- Modify: `tests/unit/application/guide/test_compiler.py`
- Modify: `tests/unit/application/guide/test_regression.py`

**Status:** [x] Complete

- [x] Append a `GUIDE_ONLY` node flag, `LOCATION` node type, and `STEP_GO_TO`
  edge type so all existing compiled enum bytes remain unchanged.
  `STEP_TRAVEL` continues to mean `zones.complete_quest_on_enter*` and never
  accepts an arbitrary coordinate.
- [x] Generate one synthetic quest per arena round with globally unique
  `guide-quest:arena:<round-stable-key>` and
  `guide.arena.<round-stable-key>` stable/DB-name namespaces. Set
  `implicit=true`, `repeatable=true`, and `guide_only=true`; emit conditional
  item-source alternatives followed by `go_to` → ordered `kill` → `loot`.
  A vendor alternative renders `Buy <item>` only when its unlock quest is
  complete; the prior-round chest remains a distinct loot source for first-run
  progression.
- [x] Keep `quest:vithtokenmob1..8` as their real non-repeatable first-clear
  token turn-ins. Remove post-completion buy/combat/reward steps from those
  nodes; retain their vendor-unlock facts as conditions on the synthetic
  workflow's purchase source, never as synthetic GameData completion.
- [x] Generate guide-only implicit repeatable quests for Shivunax and Demented
  Malaroth from exported rows: obtain the matching feed, `go_to` the feeding
  anchor, then defeat the matching character. Keep the real
  `quest:malarothfeedmade` variants as oven crafting turn-ins.
- [x] Compile workflow metadata needed for bounded cycle evaluation: workflow
  stable key, trigger item and quantity, trigger mode/location, expected
  scripted targets and counts, optional reward container, and reset evidence.
  Do not branch on script or display names after export.
- [x] Exclude guide-only quests from game-quest DB-name validation against the
  clean `quests` table, quest-chain topology, infeasible-cycle marking,
  GameData completion assumptions, quest-count regression parity, and
  cross-quest level propagation. Include them in deterministic guide output,
  zone/search metadata, source display, and local step level estimates.
- [x] Add compiler tests for ten guide-only workflows, namespace collisions,
  duplicate identities, stable enum bytes, correct arena enemy quantities,
  correct feed inputs, and isolation from all real quest lifecycle structures.
- [x] Run `uv run pytest tests/unit/application/guide/test_compiler.py tests/unit/application/guide/test_regression.py`.
  Expected: synthetic workflows compile deterministically while real quest
  parity and topology remain unchanged.
- [x] Commit. Message: `feat(guide): compile implicit scripted workflows`

### Task 3: Export workflows through the existing quest contract

**Files:**
- Modify: `src/erenshor/application/guide/mod_writer.py`
- Modify: `tests/unit/application/guide/test_mod_writer.py`

**Status:** [x] Complete

- [x] Keep a single top-level `quests` collection. Emit guide-only workflows as
  ordinary `QuestEntry`-shaped records plus `flags.guide_only=true` and a
  workflow-cycle descriptor; do not add an `encounters` collection or a second
  list/detail schema.
- [x] Render every purchase instruction as exactly `Buy <item>.`. Attach all
  vendor sources as structured step data so the UI can show and navigate every
  seller independently from the action sentence.
- [x] Emit a nested location `{stable_key, display_name, scene, x, y, z}` on
  each `go_to` step. Arena navigation targets the passive entry trigger;
  Malaroth navigation targets the feeding trigger. Neither targets the vendor,
  spawned NPC, or reward chest.
- [x] Encode the observed passive semantics: trigger entry automatically
  consumes the appropriate item. Never emit click, dialog, interact, or
  explicit item-use instructions for either workflow.
- [x] Reject a guide-only record whose synthetic DB name collides with any real
  quest DB name, whose stable key is duplicated, or whose location/evidence is
  missing or non-finite. Sort workflows, sources, targets, and steps
  deterministically.
- [x] Add writer tests for generic buy text with multiple vendors, one unified
  quest collection, guide-only flags, workflow evidence, fixed locations,
  collision failures, and byte-identical repeated serialization.
- [x] Run `uv run pytest tests/unit/application/guide/test_mod_writer.py`.
  Expected: no output contains `from the Master of Battle, then`, and no
  separate encounter schema or UI contract is required.
- [ ] Commit. Message: `feat(guide): export implicit workflow quests`

### Task 4: Reuse quest UI with a guide-only lifecycle

**Files:**
- Modify: `src/mods/AdventureGuide/src/Data/QuestEntry.cs`
- Modify: `src/mods/AdventureGuide/src/Data/GuideData.cs`
- Create: `src/mods/AdventureGuide/src/State/GuideWorkflowState.cs`
- Modify: `src/mods/AdventureGuide/src/State/QuestStateTracker.cs`
- Modify: `src/mods/AdventureGuide/src/State/StepProgress.cs`
- Modify: `src/mods/AdventureGuide/src/State/TrackerState.cs`
- Modify: `src/mods/AdventureGuide/src/UI/QuestListPanel.cs`
- Modify: `src/mods/AdventureGuide/src/UI/QuestDetailPanel.cs`
- Modify: `src/mods/AdventureGuide/src/UI/TrackerWindow.cs`
- Modify: `src/mods/AdventureGuide/src/Navigation/NavigationController.cs`
- Modify: `src/mods/AdventureGuide/src/Navigation/WorldMarkerSystem.cs`
- Modify: `src/mods/AdventureGuide/src/Navigation/EntityRegistry.cs`
- Modify: `src/mods/AdventureGuide/src/Navigation/LootScanner.cs`
- Modify: `src/mods/AdventureGuide/src/Patches/InventoryPatch.cs`
- Modify: `src/mods/AdventureGuide/src/Patches/DeathPatch.cs`
- Create: `src/mods/AdventureGuide/src/Patches/ScriptedEntityPatch.cs`
- Modify: `src/mods/AdventureGuide/src/Plugin.cs`
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/WorkflowCycleStateTests.cs`
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/GuideContractTests.cs`
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/TrackerSorterTests.cs`

- [x] Deserialize guide-only/workflow/location metadata and reject duplicate or
  real-QuestDB-colliding synthetic identities. Keep all entries in
  `GuideData.All`, the Quests tab, existing search/sort/filter controls, and
  quest navigation history.
- [x] Add one entry-aware status path. Game-backed quests continue to use
  `GameData.HasQuest` / `CompletedQuests`; guide-only workflows never read,
  write, reset, or synthesize those lists. They are available cross-zone,
  actionable in their workflow scene, repeatable, and never terminally colored
  or pruned as completed game quests.
- [x] Implement a descriptor-driven cycle evaluator with the states
  `NeedItem` → `ItemReady` → `TriggerConsumed` → `TargetsActive` →
  `RewardAvailable` → reset. Malaroth omits `RewardAvailable`. Select the
  current step from the strongest available evidence rather than treating a
  consumed trigger item as regression to `Buy`/`Obtain`.
- [x] Observe item acquisition/consumption as before/after counts; accept a
  trigger decrement only in the expected scene and exported trigger bounds.
  Observe scripted targets through a descriptor-filtered `Character.Start`
  patch plus bounded reload discovery, and reward containers through
  descriptor-scoped loot evidence. Never infer an explicit interaction from
  proximity alone.
- [x] Keep evaluation bounded: event notifications mark a workflow dirty and a
  fixed-interval evaluator checks only active/tracked workflow descriptors.
  No per-frame `FindObjectsOfType`, graph traversal, transitive dependency
  resolution, or global marker/nav cache invalidation.
- [x] Persist only the selected workflow, cycle generation, and latched trigger
  evidence per character as recovery hints. On character/scene load or hot
  reload, revalidate them against inventory and bounded live entity/container
  discovery; ambiguous arena rounds remain `Unverifiable` rather than showing
  the wrong current step.
- [x] Reuse `QuestListPanel`, `QuestDetailPanel`, and `TrackerWindow`. Display
  the existing `[R]` marker, ordered steps, sources, track/untrack controls,
  current-step highlighting, and tracker pin. Do not create an Encounters tab
  or duplicate list/detail panels.
- [x] Add fixed-position `go_to` navigation. Reuse zone-line routing from other
  scenes, then `NavigationTarget.Position`, ground path, distance, and the
  existing objective marker in the destination scene.
- [x] Extend focused tests to cover two complete/reset cycles, inventory
  consumption at and away from the trigger, reload during a fight, repeated
  arena enemy keys, ambiguous-state fail-safe behavior, no completed-quest
  pruning, no GameData mutation, shared quest filters/history, and bounded
  discovery.
- [x] Run `dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj`, `uv run pytest tests/unit/mods/test_adventure_guide_markers.py tests/unit/mods/test_adventure_guide_vault.py tests/unit/mods/test_adventure_guide_quest_list.py`, and `uv run erenshor mod build --mod adventure-guide`.
  Expected: workflows use the existing quest UI/tracker and the mod builds with
  zero errors.
- [x] Commit. Message: `feat(mod): track implicit repeatable workflows`

### Task 5: Regenerate and verify playtest guides

**Files:**
- Regenerate: `quest_guides/guide.json`
- Regenerate: `quest_guides/quest-guide.json`

- [ ] Run `uv run erenshor --variant playtest guide compile` and
  `uv run erenshor --variant playtest guide export-mod`.
- [ ] Inspect all generated workflows. Expected: the eight arena and two
  Malaroth entries appear in the normal quest collection as guide-only,
  implicit, repeatable records; real token/crafting quests remain distinct;
  all buy text is generic; every trigger uses its event coordinate rather than
  a vendor, spawned enemy, or reward location.
- [ ] Run `uv run pytest`, `uv run ruff check src/erenshor tests`,
  `uv run mypy src/erenshor`, and
  `uv run erenshor mod build --mod adventure-guide`.
  Expected: full tests, lint, type checking, artifact generation, and mod build
  pass.
- [ ] Commit. Message: `chore(guide): regenerate implicit workflow data`
