---
title: Dynamic Spawn Coverage — Implementation Plan
type: plan
status: active
created: 2026-06-28
parent: 2026-05-28-dynamic-spawn-coverage-design
---

# Dynamic Spawn Coverage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Read `skill://auditing-spawn-coverage`, `skill://unity-export-system`, and `skill://refreshing-game-data` before starting.

**Goal:** Close the export-pipeline gap for characters spawned by event-script
MonoBehaviours (Category A) and chained `Spawns[]` lists on Character prefabs
(Category B), with a fail-fast classification gate so future game updates
surface new spawn sources. Category C (zone-wide random spawners) is explicitly
deferred. Concurrently audit `mapping.json` exclusions for false positives and
clean up the project's skill catalog.

**Architecture:** `DynamicSpawnSourceListener` (registered against
`MonoBehaviour`) walks every component, filters to Assembly-CSharp, skips
`SpawnPoint`/`SpawnPointTrigger`, enumerates serialized object-reference fields
by reflection, resolves to Character prefabs, consults the tristate catalog
(`dynamic-spawn-catalog.toml`), and emits rows. Category A emits to a raw
`DynamicCharacterSpawns` table merged into `character_spawns` by the Python
build. Category B emits to `character_chained_spawns` and is expanded by
`expand_chained_spawns()`. Unknown fields fail export with exit code 3 + a
structured JSON envelope.

**Tech Stack:** C# Unity export (`src/Assets/Editor/`), Python clean-build
processor (`src/erenshor/application/processor/`), SQLite, pytest, audit
scripts (`src/tools/`).

**Variant scope:** Playtest only. Main inherits at the playtest→main merge
(~July 13). No cross-variant fallbacks.

**Constraints:** Unity 2021.3 (no `IsExternalInit`, no `System.Text.Json`).
Items keyed by `itemStableKey` not display name. `is_enabled=0` is not a
reachability verdict (may be runtime-enabled). `is_enabled=1` on serialized
spawns doesn't guarantee in-game reachability. Wiki inclusion and map
visibility are independent questions.

---

## Sub-phase 1A — Schema & records

### Task A1: `source_script` column

- [x] Add `source_script TEXT` column to clean `character_spawns` schema in `writer.py`; thread through `_SpawnRow` in `characters.py`.

### Task A2: `character_chained_spawns` table

- [x] Create `CharacterChainedSpawnRecord.cs` — junction with indexed FKs.
- [x] Add `character_chained_spawns` table to clean schema (`writer.py`); guarded pass-through in `characters.py`.

---

## Sub-phase 1B — Catalog, listener, gate

### Task B1: `DynamicSpawnCatalog` + `DynamicSpawnErrorEnvelope`

- [x] Create `DynamicSpawnCatalog.cs` — hand-rolled TOML loader. `Unknown = 0` enum default prevents silent `Allowed` on unlisted fields. Duplicate detection throws. Uses regular struct (Unity 2021.3 lacks `IsExternalInit`).
- [x] Create `DynamicSpawnErrorEnvelope.cs` — RFC-9457-style JSON writer with `Findings` and `StaleEntries`. Uses `StringBuilder` (no `System.Text.Json` in Unity 2021.3).

### Task B2: `dynamic-spawn-catalog.toml` — tristate classification catalog

- [x] Create the catalog at `src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml` — 161 entries across 51 scripts. All field names verified against playtest decompiled source. All `allowed` fields confirmed to `Object.Instantiate`.
- [x] Reclassify `MalarothFeed.Malaroth` (field name doesn't match prefab name — references `Shivunax.prefab`), `MalarothFeed.Demented`, `FaithEvent.HealObject`, `VithArena.AwardChests`, `ZenithNadirScript.Chest`, `RewardListener.Chest` from denied to allowed after verifying they instantiate lootable Character prefabs.

### Task B3: `DynamicSpawnSourceListener` + `DynamicCharacterSpawnRecord`

- [x] Create `DynamicSpawnSourceListener.cs` + `DynamicCharacterSpawnRecord.cs` + register in `ExportBatch.cs`. The listener walks all Assembly-CSharp MonoBehaviours by reflection over public instance fields. `ResolveCharacters()` handles `GameObject`, `Character`, `IList`. `ResolvePositions()` supports comma-separated `position_field` values. Category A emits `DynamicCharacterSpawnRecord` rows; Category B emits `CharacterChainedSpawnRecord` rows.
- [x] Stale detection checks `_catalog.KnownScripts` against loaded assembly types. Gate deletes stale envelope on success.

### Task B4: Python merge of `DynamicCharacterSpawns`

- [x] Python build reads raw `DynamicCharacterSpawns` table and appends rows to `character_spawns` with `source_script` set. Uses raw `Key` column as `spawn_point_stable_key` (preserves exporter's stable identity).

---

## Sub-phase 1C — Category B chained spawn expansion (Python)

### Task C1: `expand_chained_spawns()` with TDD

- [x] Create `tests/unit/application/processor/test_chained_spawns.py` — TDD tests covering single/multi-spawn parents, recursive chains, cycles, dedup, orphan parents, idempotency.
- [x] Implement `expand_chained_spawns()` in `characters.py` — recursive resolution through chained ancestors, cycle-guarded via per-path visited set. Synthetic `spawn_point_stable_key` includes source script and coordinates to avoid PK collisions. Called after `insert_character_spawns`. Added `conn` property to `Writer`.

---

## Mapping exclusion audit — enabled-spawn pass

### Task D1: Audit scripts

- [x] Create three audit scripts in `src/tools/`:
  - `audit_spawn_coverage.py` — categorizes orphans by content (loot, dialog, vendor, treasure_chest, prefab_only) and cross-references `mapping.json` exclusion rules.
  - `audit_mapping_exclusions.py` — audits existing exclusions for false positives, separates high-risk named NPCs from likely intentional exclusions (pocket vendors, training dummies), detects stale rules.
  - `trace_character_sources.py` — reads prefab GUIDs from `characters.guid`, builds one-pass index across scene/prefab files, reports verdicts (`has_enabled_spawns`, `initially_disabled_spawns`, `dead`, etc.). Supports `--verdict` filter for reproducible queries.

### Task D2: Resolve excluded characters with enabled spawns

- [x] Found 4 excluded characters with enabled spawns. After validation:
  - `character:ancient canine` — unhidden. Boss spawned by AstraListener after killing all 5 Wild Ancestral Dogs in AzynthiClear. Dragon field GUID confirmed via `characters.guid`. Own wiki page.
  - `character:brackish crocodile small` — unhidden. 9 serialized SpawnPoint spawns in Vitheo. Shares wiki page with main variant.
  - `character:lighthouse demon:shiveringtomb:...` and `shiveringtomb2:...` — left excluded. Directly placed and `is_enabled=1`, but at unreachable coordinates within reachable zones. Exclusion reasons updated.

---

## Sub-phase 1E — Orphan reduction verification

**Current state:** 70 true orphans (down from 132 baseline). 61 excluded or
handled by `mapping.json`. 9 known deferred residual remain: 4 Lost Treasure
chests (wiki-visible, map-hidden — spawned by `PlayerControl.LeftClick()`
at a runtime-determined treasure marker position; the listener cannot emit
rows because the prefabs are singleton-accessed via `GameData.Misc`) and 5
Sivakayan Spectres (Category C, deferred to a follow-up plan).

Investigation findings from GUID tracing all 36 unexcluded orphans:

- 25 confirmed dead prefabs (no GUID references in scenes or prefabs) —
  excluded with `is_wiki_generated=0, is_map_visible=0`.
- 1 resolved via catalog fix: `NPCDialog.Spawn` reclassified from denied to
  allowed — `NPCDialogManager.DoExtras()` instantiates it at the dialog
  NPC's position. Acolyte of Azynthi now has a spawn row.
- 4 Lost Treasure chests — wiki-visible, map-hidden (`dynamic_spawn`
  mapping type). Spawned cross-script via `GameData.Misc.TreasureChest*`
  in `PlayerControl.LeftClick()`.
- 1 Trick Target — excluded. Combat-triggered spawn at a random NavMesh
  point via `NPC`/`PlayerCombat`. No loot or content.
- 5 Sivakayan Spectres — Category C deferred.

### Task F1: Investigate unexcluded orphans

- [x] Investigate and resolve all 36 unexcluded orphans.

### Task F2: Add dead-prefab exclusion rules

- [x] Add exclusion rules for GUID-confirmed dead prefabs.
- [x] Re-export and verify orphan count approaches the Category C residual
  (the 5 Sivakayan Spectres). Current residual: 9 (4 treasure chests + 5
  Sivakayan).

---

## Mapping exclusion audit — disabled spawns

**Current state:** 182 characters have all spawns initially disabled
(`is_enabled=0`). Of these, 93 are currently excluded by `mapping.json`.
Investigation found that `is_enabled=0` on these characters reflects the
standard SpawnPoint/SpawnPointTrigger initial scene state (the GameObject is
inactive until a player enters the trigger radius), not `SetActive(true)`
quest-gating in most cases. The 93 break down as:
- **Pocket vendors/banks/auctions** (~45) — intentionally disabled,
  activated by player interaction. Correctly excluded.
- **Training dummies** (~21) — no content, always disabled. Correctly
  excluded.
- **Flame wells** (8) — environmental, no content. Correctly excluded.
- **Golden Spirit** (1) — quest-gated via `ShiverEvent`: `Start()` disables
  SpawnTriggers via `SetActive(false)`, Phase 2/3 re-enables them after the
  SHIVER quest chain. 1% rare alt spawn. Unhidden (wiki + map visible).
- **Highwayman Raider in Elderstone** (1) — `m_IsActive: 0`, no enabling
  script. Disabled-and-never-enabled. Correctly excluded.
- **Azynthi Corruptor figures** (2) — statues with disabled character
  scripts. Correctly excluded.

### Task G1: Trace `SetActive(true)` patterns

- [x] Trace `SetActive(true)` patterns for all 93 excluded disabled
  characters. Found 1 quest-gated character (Golden Spirit via ShiverEvent).
- [x] Unhide quest-gated characters. Update exclusion reasons for confirmed
  permanently-disabled characters.

---

## Mapping exclusion audit — stale rules

**Current state:** 25 mapping rules reference stable keys that no longer exist in the DB (all `character:simplayer*` and `character:template` keys).

### Task G2: Remove stale rules

- [x] Remove stale rules from `mapping.json`.

---

## Mapping exclusion audit — dead prefab verification

**Current state:** 62 excluded characters are `dead` (no GUID references
in scenes or prefabs). All 62 GUIDs were re-traced via
`trace_character_sources.py` — no scene or prefab references found for
any of them. The 62 break down as: 25 dead prefabs newly excluded in
F1/F2 (Molorai variants, Fernallan bkp, etc.), 4 TOWNSPERSON templates
(inspector-time placeholders), 1 pocket bank rift, and 32 pre-existing
exclusions of named NPC prefabs with loot/dialog but no world placement
(cut content or renamed prefabs with alternate display names).

**Verification done:** GUID re-trace confirmed no scene/prefab
references for all 62. Dedup check confirmed no sibling spawns for the
pre-existing 37. GUID search across all `.cs` files found no references
for any of the 37. Name search for both display names and object names
in decompiled scripts found no matches. The Shivunax pattern (field name
references a prefab by a different name) is ruled out: the GUID is not
referenced in any scene, prefab, or script file, so no field of any name
can point to these prefabs.

**Warning:** A `dead` verdict is not final. Shivunax was originally
classified as `dead` but is actually spawned by `MalarothFeed.Malaroth`
(the field name doesn't match the prefab name). The Occuphage instances in
ShiveringTomb and ShiveringTomb2 are placed and `is_enabled=1` but at
unreachable coordinates within reachable zones (user-confirmed). Both
cases required GUID tracing and in-game knowledge to resolve correctly.

### Task G3: Verify dead-prefab exclusions

- [x] GUID re-trace all 62 dead-verdict exclusions. No scene/prefab
  references found. Dedup check confirmed no sibling spawns for the 37
  pre-existing exclusions.
- [x] Name-search the 37 pre-existing exclusions for alias-based script
  spawns (the Shivunax pattern). GUID not found in any `.cs` file.
  Display names and object names not found in decompiled scripts. The
  Shivunax pattern is ruled out: no GUID reference exists in any scene,
  prefab, or script file, so no field of any name can point to these
  prefabs.

---

## Phase 2 — Skill hygiene

Outcome: Skills reflect the new gate workflow; `writing-skills` removed; frontmatter/descriptions improved.

### Task H1: Rewrite `auditing-spawn-coverage` around the structured envelope

- [ ] Update the skill so the primary workflow is: run export → if exit 3, read `dynamic-spawn-errors.json`, classify findings, edit catalog, re-run. Reference the three `src/tools/` scripts.

### Task H2: Add frontmatter to `tile-capture`, improve descriptions

- [ ] Add YAML frontmatter to `tile-capture/SKILL.md`.
- [ ] Improve narrow descriptions for `cli-commands`, `sheets-queries`, `mod-pipeline`.

### Task H3: Delete `writing-skills`, update `AGENTS.md`

- [ ] Delete `.agent/skills/writing-skills/`.
- [ ] Remove the `writing-skills` row from the Skill Directory table in `AGENTS.md`.

### Task H4: Update `unity-export-system` skill

- [ ] Add a short paragraph pointing to `DynamicSpawnSourceListener` and the catalog file as the canonical example of a listener that emits to `character_spawns` without a `SpawnPoint`.

### Task H5: Add `tests/unit/test_skills.py`

- [ ] Write the skill-validity regression guard. Walks `.agent/skills/*/SKILL.md`, parses YAML frontmatter, and asserts: `name` field present and equals `basename(dirname(file))`, `description` field present, description is third person (no leading "I ", "You ", "We "), description contains "Use when", `writing-skills` directory does not exist, `AGENTS.md` contains no `writing-skills` substring.

---

## Sub-phase 1G — Edge-case tests

### Task I1: Expand chained-spawn test coverage

- [ ] Add edge-case tests to `test_chained_spawns.py` (parent with multiple spawns, duplicate paths, multiple children from one parent). The base 7 tests cover the core paths; these add coverage for less common shapes.

---

## Verification

- [ ] `uv run erenshor -V playtest extract export` exits 0 (gate passes).
- [ ] `uv run erenshor -V playtest extract build` succeeds.
- [ ] Orphan count at Category C residual (~5-10). Current: 71.
- [ ] `uv run pytest tests/unit/application/processor/test_chained_spawns.py -v` passes.
- [ ] `uv run pytest` (full suite) passes — no regressions.
- [ ] Skills updated per Phase 2.
- [ ] `AGENTS.md` no longer references `writing-skills`.
- [ ] No excluded characters with enabled spawns (verified via `trace_character_sources.py --only-excluded --verdict has_enabled_spawns`).
- [ ] Stale mapping rules removed.
- [ ] Disabled-character audit complete.
