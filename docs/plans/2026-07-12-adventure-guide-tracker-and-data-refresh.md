---
title: Adventure Guide Tracker Fixes & Quest Data Refresh
type: plan
status: active
created: 2026-07-12
---

# Adventure Guide Tracker Fixes & Quest Data Refresh

Fix the two reported tracker/marker bugs, then reconnect the mod's quest data
pipeline so the 22 new playtest quests (and future refreshes) actually reach
players. Ordered by reliability: mod-only bug fixes first, then the data
pipeline, then gated content/metadata work.

Grounding (investigated 2026-07-12, file:line anchors verified):

- The shipping mod embeds `quest_guides/quest-guide.json` as a resource
  (`AdventureGuide.csproj:22`, loaded at `GuideData.cs:68`). That artifact is
  frozen at 176 quests (last regenerated 2026-03-27); commit `83ebf4ae7`
  deleted its producer (`assembler.py`, ~1024 lines) when the entity-graph
  pipeline replaced the quest-centric one. `uv run erenshor guide compile`
  emits the dense `quest_guides/guide.json`, which **no shipping code
  consumes**. New quest content therefore cannot reach players today.
- The abandoned rewrite branch (`1a3b034b3`, 89 commits, +12k/-10.8k) died on
  runtime fixed-point derivation: every loot/inventory event re-ran
  transitive dependency/unlock resolution and cleared all nav/marker caches
  on the main thread. Architecture rule for every task below: transitive
  resolution happens offline in the Python compiler; the mod does depth-1
  lookups against precomputed data plus cheap live checks. Do not port
  branch code (`DerivationDatabase`, `Incremental/*`, BepInEx/Thunderstore
  cutover).

## File map

- Modify `src/mods/AdventureGuide/src/UI/QuestDetailPanel.cs`: inline
  Track/Untrack button visibility (`:68-80`).
- Modify `src/mods/AdventureGuide/src/UI/TrackerWindow.cs`: completion-timer
  pruning currently gated on `Draw` (`:163-178`, `:629-643`).
- Modify `src/mods/AdventureGuide/src/State/TrackerState.cs`: tracked-set
  persistence and `PruneCompleted` (`:95-110`, `:143-170`).
- Modify `src/mods/AdventureGuide/src/Plugin.cs`: lifecycle wiring — initial
  sync without prune (`:64-69`, `:175-180`) vs scene-load path (`:319-329`).
- Modify `src/mods/AdventureGuide/src/Navigation/WorldMarkerSystem.cs`:
  ZoneReentry decision (`:322-436`).
- Modify `src/mods/AdventureGuide/src/Data/GuideData.cs`: wrapper schema —
  `SpawnPoint` parses only scene/x/y/z/night_spawn (`:191-216`);
  `CharacterQuestUnlocks` parsed (`:43-46`, `:165-166`) but unused by markers.
- Create `src/erenshor/application/guide/mod_writer.py`: serialize the
  compiled graph into the mod wrapper schema (quest entries per
  `QuestEntry.cs:5-62`, `_character_spawns`, `_character_quest_unlocks`).
- Modify `src/erenshor/cli/commands/guide.py`: add the export command.
- Modify `src/erenshor/application/guide/graph_builder.py` and
  `compiler.py`: arena-round steps (Task 5).
- Regenerate `quest_guides/quest-guide.json` (via the new exporter only).
- Modify `src/mods/AdventureGuide/README.md`: stale `guide generate` /
  `manual/*.json` claims (`:58-64`).
- Modify `docs/plans/2026-07-10-wiki-deferred-mechanics.md`: Task 8 moves
  into this plan (Task 5 below).

## Tasks

### Task 1: Tracker — reliable auto-untrack and visible Untrack

**Files:**
- Modify: `src/mods/AdventureGuide/src/UI/QuestDetailPanel.cs`
- Modify: `src/mods/AdventureGuide/src/UI/TrackerWindow.cs`
- Modify: `src/mods/AdventureGuide/src/Plugin.cs`
- Modify: `src/mods/AdventureGuide/src/State/TrackerState.cs`

Root causes (verified): completion→untrack runs only inside
`TrackerWindow.Draw` → `PruneAnimations`, so it never fires while the tracker
is hidden or disabled (`TrackerWindow.cs:163-178`); the only completion hook
is the `GameData.FinishQuest` postfix (`QuestFinishPatch.cs:7-21`), so
completions that bypass it never schedule an untrack; the initial
`Awake`/character-load path syncs quest state but never calls
`TrackerState.PruneCompleted` — only `OnSceneLoaded` does (`Plugin.cs:64-69`,
`:175-180` vs `:319-329`); and the inline button is hidden entirely for
completed quests (`QuestDetailPanel.cs:69`), leaving no untrack affordance
when a pin goes stale.

- [x] Show `[Untrack]` for tracked-but-completed quests in
  `QuestDetailPanel`; keep `[Track]` hidden for completed quests.
- [x] Drive completion-timer expiry from the plugin update path instead of
  `Draw`, so linger→untrack fires while the tracker window is hidden or the
  tracker is disabled. Guard against mutating `_completionTimers` while
  iterating (collect-then-apply, as `PruneAnimations` already does).
- [x] Call `TrackerState.PruneCompleted` after the initial quest-state sync
  and after every character-load sync, not only on scene load. This is the
  catch-all for completions that bypass `GameData.FinishQuest` (implicit and
  partial turn-ins) and for saves loaded with stale tracked pins: any
  reconcile point that syncs `GameData.CompletedQuests` must also prune.
- [x] Automated verification: `uv run pytest
  tests/unit/mods/test_adventure_guide_quest_list.py
  tests/unit/mods/test_adventure_guide_style.py
  tests/unit/mods/test_adventure_guide_lunaris.py` passes;
  `uv run erenshor mod build --mod adventure-guide` succeeds.
- [ ] In-game verification (full restart, per mod AGENTS): complete a tracked
  quest with the tracker hidden → pin is gone when reopened; load a save whose
  tracked quest is already completed → pin pruned at load; completed quest
  detail page still offers Untrack while tracked.
- [x] Commit. Message: `fix(mod): untrack completed quests reliably`

### Task 2: Markers — stop false "Re-enter zone to respawn" for unlock-gated NPCs

**Files:**
- Modify: `src/mods/AdventureGuide/src/Navigation/WorldMarkerSystem.cs`

Root cause (verified): `SpawnPointBridge.GetState` classifies any absent
directly-placed NPC as `DirectlyPlacedDead` (`SpawnPointBridge.cs:128-170`);
`EmitPerSpawnMarkers` maps that state straight to the ZoneReentry marker
(`WorldMarkerSystem.cs:425-436`) without consulting
`GuideData.CharacterQuestUnlocks` — which the mod already parses
(`GuideData.cs:43-46`). Confirmed live cases: `Lucian Revald` and
`Revan Gavault` (Stowaway, kill-unlock group for `MEETBASSLE`).

- [x] Before emitting ZoneReentry for a `DirectlyPlacedDead` spawn, check the
  character stable key against `_data.CharacterQuestUnlocks`; when an unlock
  group exists, emit no marker (matches the documented "Quest-gated → no
  marker" contract, `WorldMarkerSystem.cs:17`).
- [x] Quest-gated direct placements (`spawn_upon_quest_complete`) are not in
  the embedded data and stay wrong until Task 4; this task fixes only the
  kill-unlock class, which is the reported bug.
- [x] Automated verification:
  `uv run pytest tests/unit/mods/test_adventure_guide_markers.py` passes;
  `uv run erenshor mod build --mod adventure-guide` succeeds.
- [ ] In-game verification: a kill-unlock NPC absent in Stowaway shows no
  re-enter marker; an ordinary directly-placed NPC still shows one after death.
- [x] Commit. Message: `fix(mod): suppress re-enter hint for unlock-gated spawns`

### Task 3: Reconnect the quest data pipeline (release-critical)

**Files:**
- Create: `src/erenshor/application/guide/mod_writer.py`
- Modify: `src/erenshor/cli/commands/guide.py`
- Modify: `src/mods/AdventureGuide/README.md`
- Create: `tests/unit/application/guide/test_mod_writer.py`
- Modify: `src/erenshor/application/guide/graph_builder.py`
- Modify: `src/mods/AdventureGuide/src/State/StepProgress.cs`
- Modify: `tests/unit/application/guide/test_compiler.py`
- Regenerate: `quest_guides/quest-guide.json`

Decision: keep the mod's wrapper schema and re-add a Python emitter, rather
than migrating `GuideData.cs` to the dense compiled schema. The mod AGENTS
mandates keeping the stable UI/behavior; the dense-consumer C# rewrite is
exactly what the abandoned branch failed at. The compiler already computes
everything the wrapper needs (quest specs and steps `compiler.py:463-504`,
unlock predicates `:583-627`, spawn nodes `graph_builder.py:936-982`).

- [x] Implement `mod_writer.py`: map the compiled graph to the wrapper JSON
  the mod parses — quest entries with acquisition/steps/required
  items/completion/rewards/chain/flags/level_estimate/acceptance
  (`QuestEntry.cs:5-62`), plus `_character_spawns` and
  `_character_quest_unlocks` maps and the `_version` field
  (`GuideData.cs:148-216`). Use the deleted assembler as the mapping
  reference (`git show 83ebf4ae7^:src/erenshor/application/guide/assembler.py`);
  implement against the compiled graph, not new SQL.
- [x] Preserve acquisition/completion OR semantics in graph edge groups and
  teach `StepProgress` to consume grouped alternatives without per-frame
  allocations.
- [x] Add `uv run erenshor guide export-mod` writing
  `quest_guides/quest-guide.json`; follow the existing `compile` command's
  precondition/option pattern in `cli/commands/guide.py:13-67`.
- [x] Contract test in `test_mod_writer.py`: every quest entry carries the
  keys `GuideData.cs`/`QuestEntry.cs` deserialize; implicit quests emit
  `acceptance: "implicit"` with a resolvable final-step scene; spot-assert
  one legacy quest (`Quest:MEETBASSLE` unlock map row) and one new playtest
  quest (`quest:vithtokenmob1` requires `Vithean Arena Fee (1)`).
- [x] Regenerate `quest_guides/quest-guide.json` from the playtest DB via the
  new command; verify quest count is 196, all 22 new quests are present, and
  the unobtainable `quest:amethikeys` / `quest:clearingthebonepits` entries
  carried by the frozen wrapper are excluded. Diff shared quests against the
  frozen artifact to catch mapping regressions.
- [x] Fix the stale README claims (`README.md:58-64`) to document
  `guide compile` + `guide export-mod` and TOML graph overrides (the only
  curation path; `manual/*.json` does not exist).
- [x] Automated verification:
  `uv run pytest tests/unit/application/guide/ tests/unit/mods/test_adventure_guide_vault.py`
  passes and `uv run erenshor mod build --mod adventure-guide` embeds the new
  artifact.
- [ ] In-game verification: the new quests appear in the guide list with
  steps.
- [x] Commit boundaries: `feat(guide): export mod quest-guide from compiled graph`,
  then `chore(guide): regenerate mod quest data for playtest release`.
- [ ] Vault republish of the rebuilt DLL ships the data; follow
  `src/mods/AdventureGuide/vault/AGENTS.md` (manual gate — coordinate with
  the game release; the DLL carries playtest-only quest names, so publish on
  or after release day, not before).

### Task 4: Emit per-spawn gate metadata (robust respawn semantics)

**Files:**
- Modify: `src/erenshor/application/guide/mod_writer.py` (depends on Task 3)
- Modify: `src/erenshor/application/guide/schema.py`
- Modify: `src/erenshor/application/guide/graph_builder.py`
- Modify: `src/mods/AdventureGuide/src/Data/GuideData.cs`
- Modify: `src/mods/AdventureGuide/src/Navigation/WorldMarkerSystem.cs`
- Test: `tests/unit/application/guide/test_mod_writer.py`
- Test: `tests/unit/application/guide/test_compiler.py`
- Test: `tests/unit/mods/test_adventure_guide_markers.py`

- [x] Extend the wrapper's spawn records with
  `spawn_upon_quest_complete_stable_key`, `is_directly_placed`, and
  `source_script`; parse them in `GuideData.SpawnPoint`.
- [x] In `EmitPerSpawnMarkers`, treat quest-gated
  (`spawn_upon_quest_complete` set and quest incomplete) and scripted
  (`source_script` non-empty, e.g. VithArena chests) rows reaching the
  `DirectlyPlacedDead` bridge state as gated: no ZoneReentry marker.
- [x] Verification: `test_mod_writer.py` asserts the new keys for a
  quest-gated spawn and a `VithArena` chest row;
  `uv run pytest tests/unit/mods/test_adventure_guide_markers.py` and
  `uv run erenshor mod build --mod adventure-guide` pass.
- [x] Commit. Message: `feat(guide,mod): gate respawn hints on spawn metadata`

### Task 5: Arena rounds as guide steps

Moved here from `2026-07-10-wiki-deferred-mechanics.md` Task 8 (guide-side
work does not belong in a wiki obtainability plan).

**Files:**
- Modify: `src/erenshor/application/guide/schema.py`
- Modify: `src/erenshor/application/guide/graph_builder.py`
- Modify: `src/erenshor/application/guide/compiler.py`
- Modify: `src/erenshor/application/guide/mod_writer.py`
- Modify: `src/mods/AdventureGuide/src/Navigation/WorldMarkerSystem.cs`
- Test: `tests/unit/application/guide/test_compiler.py`
- Test: `tests/unit/application/guide/test_mod_writer.py`
- Test: `tests/unit/mods/test_adventure_guide_markers.py`

- [x] Read `arena_rounds` / `arena_round_enemies` in `graph_builder` (no
  arena stage exists in the orchestration, `graph_builder.py:40-83`) and
  attach ordered steps to each `quest:vithtokenmob{N}` quest: collect and
  turn in the first-clear token, buy the newly unlocked fee from the Master
  of Battle, enter Vitheo's arena, defeat the wave enemies, and loot
  `arenachest N` for the round reward. Keep the first-clear drop distinct
  from the post-completion vendor re-buy (`unlock_item_for_vendor`) so it
  does not read as a circular token source.
- [x] Fold the steps through `_compile_quest_specs` and the mod writer so
  both `guide.json` and `quest-guide.json` carry typed, ordered
  `turn_in` / `buy` / `kill` / `loot` actions with quantities.
- [x] Teach the marker display to label the new action types without
  changing tracker progression semantics.
- [x] Verification: the focused guide/mod suite passes (91 tests), the mod
  builds, and temporary playtest artifacts show the complete ordered flow
  for rounds 1 and 6.
- [ ] Regenerate `guide.json` and `quest-guide.json` from playtest data.
- [ ] Commit. Message: `feat(guide): model scripted arena rounds as quest steps`

## Non-goals (investigated, deliberately rejected)

- **Abandoned-branch ports**: the relational fixed-point engine, global
  nav/marker cache invalidation, proof stores, and the BepInEx/Thunderstore
  cutover are not ported. Root cause of the freezes was unbounded transitive
  dependency/unlock resolution per loot/inventory event on the main thread
  (`DerivationDatabase.cs:566-601`, `:874-940`; `DerivationViewStore.cs:584-603`
  at `1a3b034b3`). Any future feature from that branch is re-specified as
  compile-time data + depth-1 runtime reads, behind its own design doc.
- **World-drop pool in the guide**: low priority per product owner; tracked
  as wiki Task 6 in `2026-07-10-wiki-deferred-mechanics.md`.
- **Dense-schema migration of `GuideData.cs`**: rejected while the wrapper
  emitter (Task 3) satisfies all current needs.
