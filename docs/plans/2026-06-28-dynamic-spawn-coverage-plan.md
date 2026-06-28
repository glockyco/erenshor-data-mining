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

## Sub-phase 1D — Scanner refactor (performance)

Outcome: `AssetScanner` dispatch uses precomputed typed delegates instead of per-call reflection. The dynamic listener processes every MonoBehaviour, so this eliminates the overhead it exposes.

**Files:** `src/Assets/Editor/ExportSystem/AssetScanner/AssetScanner.cs`

### Task E1: Typed-delegate dispatch

- [ ] Replace per-call `GetMethod` + `Invoke` with a precomputed `Dictionary<Type, List<Action<Component>>>` built lazily on first scan. `RegisterComponentListener<T>` captures a delegate at registration time. The hot loop becomes a `TryGetValue` + delegate invocation.
- [ ] Verify no regression — run a full playtest export before and after, diff the raw DB dump. Expected: no differences in table content.
- [ ] **Commit** — `refactor(export): precompute typed dispatch delegates`

---

## Sub-phase 1E — Orphan reduction verification

**Current state:** 71 true orphans (down from 132 baseline). 35 already
excluded by `mapping.json` (including the 5 Sivakayan Spectres — Category C
deferred). 36 unexcluded orphans need GUID tracing to classify them.

### Task F1: Investigate unexcluded orphans

For each of the 36 unexcluded orphans, run
`trace_character_sources.py --stable-key <key>` and determine:
- GUID has scene/prefab references → trace the referencing script and add to
  catalog if it's an `Instantiate` spawn source.
- GUID has no references → dead prefab. Add exclusion rule to
  `mapping.json` with `is_wiki_generated=0, is_map_visible=0`.

```bash
uv run python src/tools/audit_spawn_coverage.py --variant playtest
uv run python src/tools/trace_character_sources.py --stable-key "character:faith"
uv run python src/tools/audit_mapping_exclusions.py --only-content
```

- [ ] Investigate and resolve all 36 unexcluded orphans.

### Task F2: Add dead-prefab exclusion rules

- [ ] Add exclusion rules for GUID-confirmed dead prefabs.
- [ ] Re-export and verify orphan count approaches the Category C residual
  (the 5 Sivakayan Spectres).

---

## Mapping exclusion audit — disabled spawns

**Current state:** 182 characters have all spawns initially disabled (`is_enabled=0`). Of these, 93 are currently excluded by `mapping.json`. Data alone can't distinguish:
- **Intentionally disabled** (training dummies, pocket vendors, flame wells) — correctly excluded.
- **Quest-gated** (enabled by `SetActive(true)` in event scripts like `MorphTrigger.Enable`, `QuestSpawnListener.EnableOnQuestComplete`) — should be wiki-visible.
- **Disabled-and-never-enabled** (e.g., Highwayman in Elderstone) — correctly excluded.

### Task G1: Trace `SetActive(true)` patterns

Trace `SetActive(true)` calls in event scripts to identify which disabled characters are quest-gated (should be unhidden) vs permanently disabled (correctly excluded). Search the decompiled source for patterns like `SetActive(value: true)`, `EnableOnQuestComplete`, `spawn_upon_quest_complete_stable_key`.

```bash
uv run python src/tools/audit_spawn_coverage.py --variant playtest --include-disabled
uv run python src/tools/trace_character_sources.py --only-excluded --verdict initially_disabled_spawns
```

**Decision criteria per character:**
1. Has `SetActive(true)` in a script → quest-gated, unhide.
2. Has `spawn_upon_quest_complete_stable_key` set → quest-gated, unhide.
3. No enabling path found → intentionally disabled, keep excluded.

- [ ] Trace `SetActive(true)` patterns for all 93 excluded disabled characters (pocket vendors/training dummies can be batch-skipped via the `is_intentional_exclusion` heuristic in `audit_mapping_exclusions.py`).
- [ ] Unhide quest-gated characters. Update exclusion reasons for confirmed permanently-disabled characters.

---

## Mapping exclusion audit — stale rules

**Current state:** 25 mapping rules reference stable keys that no longer exist in the DB (all `character:simplayer*` and `character:template` keys).

### Task G2: Remove stale rules

- [x] Remove stale rules from `mapping.json`.

---

## Mapping exclusion audit — dead prefab verification

**Current state:** 37 excluded characters are `dead` (no GUID references in scenes or prefabs). These are likely correct exclusions but haven't been individually verified against in-game knowledge.

**Warning:** A `dead` verdict is not final. Shivunax was originally classified as `dead` but is actually spawned by `MalarothFeed.Malaroth` (the field name doesn't match the prefab name). The Occuphage instances in ShiveringTomb and ShiveringTomb2 are placed and `is_enabled=1` but at unreachable coordinates within reachable zones (user-confirmed). Both cases required GUID tracing and in-game knowledge to resolve correctly.

### Task G3: Verify dead-prefab exclusions

- [ ] Verify remaining dead-prefab exclusions against in-game knowledge. Re-trace each `dead` verdict via GUID to confirm no undiscovered spawn source exists.

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
