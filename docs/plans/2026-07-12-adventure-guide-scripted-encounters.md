---
title: Adventure Guide Scripted Encounters & Location Steps
type: plan
status: draft
created: 2026-07-12
parent: 2026-07-09-erenshor-planning-overview
---

# Adventure Guide Scripted Encounters & Location Steps

Separate item acquisition from physical destinations: purchase steps use the
generic `Buy <item>` contract, while coordinate-backed `go_to` steps navigate to
passive scripted-event triggers. Keep `travel` reserved for quest-completing zone
entry. Represent repeatable arena and Malaroth workflows as encounters rather
than post-completion steps on game quests.

## File map

- Modify `src/Assets/Editor/Database/DynamicCharacterSpawnRecord.cs`: persist
  the item consumed by a scripted spawn trigger plus its trigger semantics and
  display name.
- Modify `src/Assets/Editor/Database/ArenaRoundRecord.cs`: persist the arena
  entry trigger anchor and display metadata once per round.
- Modify `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnCatalog.cs`:
  parse declarative trigger-item and event metadata.
- Modify `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnSourceListener.cs`:
  resolve configured trigger items and write event metadata with dynamic spawn
  rows.
- Modify `src/Assets/Editor/ExportSystem/AssetScanner/Listener/VithArenaListener.cs`:
  export the passive arena trigger anchor independently from enemy/chest spawn
  positions.
- Modify `src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml`:
  declare the normal and odd Malaroth feed inputs without guide-side
  script-name conditionals.
- Modify `src/erenshor/application/processor/characters.py`: carry scripted
  trigger metadata into clean character-spawn and arena-round records.
- Modify `src/erenshor/application/processor/writer.py`: define the clean
  columns used by encounter generation.
- Create `tests/unit/application/processor/test_scripted_encounters.py`:
  defend trigger metadata, item precedence, and coordinate separation.
- Modify `src/erenshor/application/guide/schema.py`: append encounter/location
  node types and a navigation-only `STEP_GO_TO` edge type.
- Modify `src/erenshor/application/guide/graph_builder.py`: build arena and
  Malaroth encounters, their prerequisites, locations, and ordered steps.
- Modify `src/erenshor/application/guide/compiler.py`: compile encounter specs
  without changing existing enum byte assignments.
- Modify `tests/unit/application/guide/test_compiler.py`: cover encounter
  structure, step order, and removal of post-completion arena quest steps.
- Modify `src/erenshor/application/guide/mod_writer.py`: project encounters and
  locations into the shipping wrapper; keep buy text vendor-neutral and attach
  item-source choices separately.
- Modify `tests/unit/application/guide/test_mod_writer.py`: cover generic buy
  wording, source lists, location payloads, and deterministic encounter output.
- Create `src/mods/AdventureGuide/src/Data/EncounterEntry.cs`: deserialize
  encounter workflows, item-source choices, and coordinate-backed locations.
- Modify `src/mods/AdventureGuide/src/Data/GuideData.cs`: load and index the
  top-level encounter collection.
- Create `src/mods/AdventureGuide/src/UI/EncounterListPanel.cs`: list scripted
  encounters independently from game quest state.
- Create `src/mods/AdventureGuide/src/UI/EncounterDetailPanel.cs`: render an
  ordered reference workflow with source and location navigation controls,
  without false quest-completion coloring.
- Modify `src/mods/AdventureGuide/src/UI/GuideWindow.cs`: add the Encounters tab
  and preserve existing quest navigation/history behavior.
- Modify `src/mods/AdventureGuide/src/Navigation/NavigationController.cs`:
  navigate directly to a fixed scene coordinate, including existing cross-zone
  routing before the local ground path.
- Create `tests/unit/mods/test_adventure_guide_encounters.py`: defend wrapper
  parsing, generic action labels, fixed-position navigation, and separation
  from `QuestStateTracker` / `StepProgress`.
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
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml`
- Modify: `src/erenshor/application/processor/characters.py`
- Modify: `src/erenshor/application/processor/writer.py`
- Create: `tests/unit/application/processor/test_scripted_encounters.py`

- [ ] Add `trigger_item_field`, `event_display_name`, and `trigger_mode` to the
  dynamic-spawn catalog contract. Split the two `MalarothFeed` outputs into
  separate allowed entries so `Malaroth` resolves `MalarothFood` and `Demented`
  resolves `BadFood`; both use the existing host `EventX/Y/Z` anchor and the
  `proximity_auto_consume` mode.
- [ ] Resolve the configured Unity `Item` reference in
  `DynamicSpawnSourceListener` and persist its stable key beside the spawned
  character. Fail the export when an allowed entry declares a trigger item that
  cannot be resolved; never silently emit a location without its prerequisite.
- [ ] Extend each `ArenaRoundRecord` with the `VithArena` host transform as the
  entry anchor, the display name `Vitheo's arena`, and
  `proximity_auto_consume`. Keep `ChestSpawnPos` and `SpawnLoc1/2/3` as reward
  and combat positions, not the entry destination.
- [ ] Carry all new columns into the clean DB. Preserve the existing Malaroth
  NPC spawn `(428.40, 28.37, 642.20)` separately from the feeding trigger
  `(336.06, 32.31, 673.63)`; preserve the arena entry independently from the
  chest `(521.90, 25.21, 485.60)`.
- [ ] Add processor tests proving normal feed maps to ordinary Malaroth, odd
  feed maps to Demented Malaroth, trigger-item priority is retained from the
  catalog, and event/spawn coordinates cannot be interchanged.
- [ ] Run `uv run pytest tests/unit/application/processor/test_scripted_encounters.py tests/unit/application/export_surface/test_listener_coverage.py`.
  Expected: the trigger metadata contract passes without changing unrelated
  spawn rows.
- [ ] Run `uv run erenshor --variant playtest extract export`, then inspect the
  raw trigger rows. Expected: eight arena rounds have one arena-entry anchor
  each; both Malaroth outputs have item stable keys, the same feeding-site
  anchor, and distinct spawned-character identities.
- [ ] Commit. Message: `feat(export): capture scripted encounter triggers`

### Task 2: Compile encounters and location steps

**Files:**
- Modify: `src/erenshor/application/guide/schema.py`
- Modify: `src/erenshor/application/guide/graph_builder.py`
- Modify: `src/erenshor/application/guide/compiler.py`
- Modify: `tests/unit/application/guide/test_compiler.py`

- [ ] Append `ENCOUNTER` and `LOCATION` node types plus `STEP_GO_TO` to their
  enum registries so every existing compiled byte remains unchanged.
  `STEP_TRAVEL` continues to mean `zones.complete_quest_on_enter*`; it must not
  accept arbitrary coordinates.
- [ ] Build one repeatable encounter per arena round. Derive its unlock quest
  from the fee item's existing `quest_required_items` / vendor-unlock
  relationship, then emit `buy` → `go_to` → ordered `kill` → `loot` steps. The
  location target is the arena entry anchor, not the Master of Battle, enemy
  spawn positions, or reward chest.
- [ ] Remove arena-only `buy` / `kill` / `loot` steps from
  `quest:vithtokenmob{N}`. Those game quests end when the first-clear token is
  turned in; post-completion arena actions must not be colored completed or
  pruned by `QuestStateTracker`.
- [ ] Build Malaroth encounters from exported trigger metadata: obtain the
  corresponding feed item, `go_to` the feeding-site anchor, then defeat the
  exported character. Generate ordinary and Demented workflows from data; do
  not branch on `MalarothFeed` or character names in the guide compiler.
- [ ] Compile an `EncounterSpec` with ordered `StepSpec` values and a location
  target ID. Keep `go_to` out of quest level estimation and preserve existing
  OR-group and ordinal behavior.
- [ ] Add compiler tests for all eight arena encounters, both Malaroth feed
  variants, stable enum bytes, arena fee priority, repeated enemy quantities,
  and absence of post-completion steps on the token quests.
- [ ] Run `uv run pytest tests/unit/application/guide/test_compiler.py`.
  Expected: encounter workflows compile deterministically and all existing
  quest-step tests remain green.
- [ ] Commit. Message: `feat(guide): compile scripted encounter workflows`

### Task 3: Export a vendor-neutral shipping contract

**Files:**
- Modify: `src/erenshor/application/guide/mod_writer.py`
- Modify: `tests/unit/application/guide/test_mod_writer.py`

- [ ] Add a top-level `encounters` collection to `quest-guide.json`. Each entry
  carries a stable key, display name, repeatability, unlock prerequisite, and
  ordered steps. A `go_to` step carries a nested location with stable key,
  display name, scene, and finite `x/y/z` values.
- [ ] Render every purchase action as exactly `Buy <item>.`. Attach zero or more
  vendor/item-source records as structured step data so the UI can show and
  navigate all available sellers without naming one in the action text.
- [ ] Render arena entry as its own `go_to` action and preserve the observed
  passive behavior: entering the trigger auto-consumes the first matching fee;
  no interact, dialog, or explicit item-use instruction is emitted.
- [ ] Render Malaroth feed acquisition and feeding-site navigation as separate
  actions. Do not tell the player to click the bowl or use the feed—the game
  automatically consumes the appropriate item on trigger entry.
- [ ] Reject missing/non-finite location coordinates and duplicate encounter
  stable keys. Sort encounters and their sources deterministically.
- [ ] Add writer tests for generic buy text with multiple vendors, arena and
  Malaroth location payloads, missing-coordinate failure, and byte-identical
  repeated serialization.
- [ ] Run `uv run pytest tests/unit/application/guide/test_mod_writer.py`.
  Expected: no generated instruction contains `from the Master of Battle, then`
  and location/source data remains independently navigable.
- [ ] Commit. Message: `feat(guide): export location-aware encounters`

### Task 4: Browse and navigate encounters in the mod

**Files:**
- Create: `src/mods/AdventureGuide/src/Data/EncounterEntry.cs`
- Modify: `src/mods/AdventureGuide/src/Data/GuideData.cs`
- Create: `src/mods/AdventureGuide/src/UI/EncounterListPanel.cs`
- Create: `src/mods/AdventureGuide/src/UI/EncounterDetailPanel.cs`
- Modify: `src/mods/AdventureGuide/src/UI/GuideWindow.cs`
- Modify: `src/mods/AdventureGuide/src/Navigation/NavigationController.cs`
- Create: `tests/unit/mods/test_adventure_guide_encounters.py`

- [ ] Deserialize and index encounters separately from `QuestEntry`. Do not add
  synthetic DB names or feed encounters through `QuestStateTracker`,
  `StepProgress`, completed-quest pruning, or quest status colors.
- [ ] Add an Encounters tab with a deterministic list and ordered detail view.
  Render each action independently; show all structured item sources under
  acquisition/purchase steps and one `[NAV]` control for every navigable source
  or fixed location.
- [ ] Add fixed-position navigation to `NavigationController`. From another
  scene, reuse existing zone-line routing; in the destination scene, switch to
  `NavigationTarget.Position` and the existing ground-path/distance rendering.
- [ ] Keep encounter workflows informational rather than fabricating automatic
  completion. Arrival at a coordinate does not prove a collider fired, an item
  was consumed, or an explicit interaction happened; no proximity-only
  completion state is persisted.
- [ ] Preserve quest history, filtering, tracking, world markers, and shortcut
  behavior when switching between Quests and Encounters.
- [ ] Add focused tests proving encounters deserialize, quest state never marks
  encounter steps complete, multi-vendor sources remain separate from action
  text, and position navigation carries the correct scene and coordinates.
- [ ] Run `uv run pytest tests/unit/mods/test_adventure_guide_encounters.py tests/unit/mods/test_adventure_guide_markers.py tests/unit/mods/test_adventure_guide_vault.py` and `uv run erenshor mod build --mod adventure-guide`.
  Expected: focused tests pass and the Lunaris mod builds with zero errors.
- [ ] Commit. Message: `feat(mod): browse scripted encounter guides`

### Task 5: Regenerate and verify playtest guides

**Files:**
- Regenerate: `quest_guides/guide.json`
- Regenerate: `quest_guides/quest-guide.json`

- [ ] Run `uv run erenshor --variant playtest guide compile` and
  `uv run erenshor --variant playtest guide export-mod`.
- [ ] Inspect all generated encounter workflows. Expected: eight arena entries
  use generic buy text and the `ARENA EVENT` anchor; ordinary and Demented
  Malaroth entries use the feeding-site anchor and their respective feed items;
  no encounter uses an NPC spawn or chest coordinate as its trigger location.
- [ ] Run `uv run pytest`, `uv run ruff check src/erenshor tests`,
  `uv run mypy src/erenshor`, and
  `uv run erenshor mod build --mod adventure-guide`.
  Expected: the full suite, lint, type checking, and mod build pass.
- [ ] Commit. Message: `chore(guide): regenerate scripted encounter data`
