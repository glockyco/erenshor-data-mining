---
title: Dynamic Spawn Coverage — Implementation Plan
type: plan
status: active
created: 2026-06-28
parent: 2026-05-28-dynamic-spawn-coverage-design
---

# Dynamic Spawn Coverage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task inline in the main working tree. Steps use checkbox (`- [ ]`) syntax for tracking. Read `skill://unity-export-system`, `skill://auditing-spawn-coverage`, and `skill://refreshing-game-data` before starting. No subagents, no worktrees — inline execution only.

**Goal:** Close the export-pipeline gap for characters spawned by event-script MonoBehaviours (Category A: ~120 orphans) and chained `Spawns[]` lists on Character prefabs (Category B: ~10 orphans), with a fail-fast classification gate so future game updates surface new spawn sources to the maintainer instead of silently regressing coverage. Category C (zone-wide random spawners) is explicitly deferred — tracked as a follow-up plan, not in scope here.

**Architecture:** A single `DynamicSpawnSourceListener` registered against `MonoBehaviour` walks every component in every scanned prefab/scene, reads serialized `Character`/`GameObject` fields by reflection, and emits `character_spawns` rows for fields classified `Allowed` in a checked-in TOML catalog. Unknown fields fail the export with exit code 3 + a structured JSON envelope. Chained spawns (Category B — host MonoBehaviour on a Character prefab) write to a new `character_chained_spawns` table, expanded by Python into `character_spawns` at build time. A scanner refactor (typed delegates + precomputed dispatch table) removes the reflection overhead the new listener exposes.

**Tech Stack:** C# Unity export (`src/Assets/Editor/`), Python clean-build processor (`src/erenshor/application/processor/`), SQLite, pytest, the playtest variant as the working source of truth.

**Variant scope:** Playtest only. Main inherits the catalog and listener at the playtest→main merge (~July 13). No cross-variant fallbacks. The catalog is checked in once and validated against whichever variant is being exported — if a script in the catalog doesn't exist in that variant's `Assembly-CSharp`, it surfaces as a `stale_entries` finding (not a crash).

**Pre-execution prerequisite:** The playtest export pipeline requires a valid Unity license. Run `uv run erenshor -V playtest extract export` once to confirm it succeeds before starting Task 1; if it fails with `Unity licensing validation failed`, open Unity Hub > Preferences > Licenses and reactivate before proceeding. The plan's verification steps re-export against playtest, so the license must be valid.

**Open questions resolved (from spec §7):**

1. **TOML parser:** hand-rolled. The catalog grammar is trivial (`[[allowed]]`/`[[denied]]` sections with `script`, `fields`, optional `position_field`, optional `reason`). Adding a NuGet/UPM dep for ~40 lines of parsing is unjustified. The hand-rolled parser lives in `DynamicSpawnCatalog.cs`.
2. **`source_script` on SpawnPoint listeners:** leave NULL for the existing `SpawnPointListener`/`SpawnPointTriggerListener` (backward compatible — NULL means "canonical SpawnPoint path"). The new `DynamicSpawnSourceListener` sets it to the MonoBehaviour's scripting type name.
3. **Position field resolution:** confirmed against playtest source. `WaveEvent.SpawnLocations` is `List<Transform>` (emit one row per element). `Chessboard.SpawnLoc` is a single `Transform`. `PhantomFightEvent.WardSpawnPoints` is `List<Transform>`. The catalog's `position_field` handles both — single Transform uses `.position`, list Transform iterates elements.

---

## File map (created / modified)

**C# export:**
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnCatalog.cs` — TOML loader + `Classify(scriptType, fieldName) → Allowed|Denied|Unknown`
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnSourceListener.cs` — the listener
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnErrorEnvelope.cs` — RFC-9457 JSON writer
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml` — checked-in tristate catalog
- Modify: `src/Assets/Editor/Database/CharacterSpawnRecord.cs` — add `source_script` column
- Modify: `src/Assets/Editor/Database/CharacterChainedSpawnRecord.cs` — NEW table record
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/AssetScanner.cs` — typed-delegate dispatcher refactor
- Modify: `src/Assets/Editor/ExportBatch.cs` — register `DynamicSpawnSourceListener`, add exit-code-3 path

**Python build:**
- Modify: `src/erenshor/application/processor/writer.py` — add `source_script` column to `character_spawns` schema, add `character_chained_spawns` table
- Modify: `src/erenshor/application/processor/characters.py` — add `expand_chained_spawns()` after main spawn insert

**Catalog seeding data:** derived from `docs/plans/2026-05-28-spawn-coverage-audit.md` (playtest), verified against the live playtest decompiled source during Task 1.

**Skills (Phase 2):**
- Modify: `.agent/skills/auditing-spawn-coverage/SKILL.md` — rewrite around the structured envelope
- Modify: `.agent/skills/unity-export-system/SKILL.md` — add `DynamicSpawnSourceListener` pointer
- Modify: `.agent/skills/tile-capture/SKILL.md` — add YAML frontmatter
- Modify: `.agent/skills/cli-commands/SKILL.md`, `sheets-queries/SKILL.md`, `mod-pipeline/SKILL.md` — improved descriptions
- Delete: `.agent/skills/writing-skills/` — superseded by Anthropic's canonical guidance
- Modify: `AGENTS.md` — remove the `writing-skills` row

**Tests:**
- Create: `tests/unit/application/processor/test_chained_spawns.py`
- Create: `tests/unit/test_dynamic_spawn_catalog.py` (C# logic mirrored in Python for the catalog parser, if feasible — otherwise covered by C# fixture tests)

**Verification commands (used throughout):**

```bash
uv run erenshor -V playtest extract export     # Unity batch -> raw SQLite
uv run erenshor -V playtest extract build      # raw -> clean SQLite
uv run pytest tests/unit/application/processor/test_chained_spawns.py -v
uv run erenshor golden capture                 # MAIN variant only — never on playtest
sqlite3 variants/playtest/erenshor-playtest.sqlite "<orphan SQL from audit doc>"
```

---

## Sub-phase 1A — Schema & records (no behavior change)

Outcome: new column and table exist in the Python clean schema; existing exports unaffected (column is nullable, table is empty until the listener ships).

**Grounding note:** There is no `CharacterSpawnRecord.cs` — the C# export writes `SpawnPoints` + `SpawnPointCharacters` (junction) and `SpawnPointTriggers` + `SpawnPointTriggerCharacters` (junction). The Python build (`characters.py`) flattens these into the clean `character_spawns` table. The `source_script` column is clean-DB-only — the dynamic listener's raw record (`DynamicCharacterSpawnRecord`, Task B5) carries its own `SourceScript` column, and the Python build maps it through.

### Task A1: Add `source_script` column to the clean `character_spawns` schema

**Files:**
- Modify: `src/erenshor/application/processor/writer.py` (`character_spawns` CREATE TABLE, ~line 869)
- Modify: `src/erenshor/application/processor/characters.py` (spawn row dict, ~line 748)

- [x] **Step 1:** Add `source_script TEXT,` to the `CREATE TABLE character_spawns (...)` body in `writer.py`, grouped after `is_map_visible`.
- [x] **Step 2:** Add `"source_script": s.source_script,` to the spawn row dict in `characters.py:748` (the existing SpawnPoint/SpawnPointTrigger paths don't set it; the dynamic spawn build in Task B5 and the chained-spawn expansion in Task C2 will populate it). `source_script` is an optional field on `_SpawnRow` defaulting to `None`.
- [x] **Step 3:** Run the clean build and confirm the column exists: 8786 rows, 0 with source_script (all NULL).
- [x] **Step 4: Commit** — `feat(pipeline): add source_script column to clean character_spawns` (1080c28d)

### Task A3: Create `CharacterChainedSpawnRecord` (Category B intermediate table)

**Files:**
- Create: `src/Assets/Editor/Database/CharacterChainedSpawnRecord.cs`

- [x] **Step 1:** Create the record class mirroring `QuestRequiredItemRecord.cs` (junction, composite unique index). Uses indexed FKs instead of a composite `[PrimaryKey]` string to match the codebase convention.

- [ ] **Step 2:** The table is NOT created by the record class alone — `_db.CreateTable<T>()` is called in the listener's `OnScanFinished`. Table creation is deferred to Task B4 (`DynamicSpawnSourceListener.OnScanFinished`). Commit the record now; verify the table exists after Task B4.

- [ ] **Step 3: Commit** — `feat(export): add character_chained_spawns record for Category B spawns`

### Task A4: Mirror `character_chained_spawns` in the Python clean schema

**Files:**
- Modify: `src/erenshor/application/processor/writer.py`
- Modify: `src/erenshor/application/processor/characters.py`

- [ ] **Step 1:** Add the table to `writer.py` after `character_spawns`:

```sql
CREATE TABLE character_chained_spawns (
    parent_stable_key  TEXT NOT NULL,
    child_stable_key   TEXT NOT NULL,
    source_script      TEXT NOT NULL,
    PRIMARY KEY (parent_stable_key, child_stable_key, source_script)
);
```

- [ ] **Step 2:** Add an `insert_character_chained_spawns` method to `Writer` mirroring `insert_character_spawns`.

- [ ] **Step 3:** In `characters.py`, after the existing `character_spawns` insert (line 781), add a pass-through copy from raw → clean (the table is populated by the listener in Task B2; this just carries it through the build):

```python
# character_chained_spawns (Category B — expanded into character_spawns in Task C3)
chained_rows = _load_rows(raw_db, "SELECT ParentStableKey, ChildStableKey, SourceScript FROM CharacterChainedSpawns")
writer.insert_character_chained_spawns([
    {"parent_stable_key": r["ParentStableKey"], "child_stable_key": r["ChildStableKey"], "source_script": r["SourceScript"]}
    for r in chained_rows
])
```

- [ ] **Step 4:** Build and confirm the clean table exists and is empty:

```bash
uv run erenshor -V playtest extract build
sqlite3 variants/playtest/erenshor-playtest.sqlite "SELECT COUNT(*) FROM character_chained_spawns"
```
Expected: `0`.

- [ ] **Step 5: Commit** — `feat(pipeline): carry character_chained_spawns into clean DB`

---

## Sub-phase 1B — The catalog + listener (core functionality)

Outcome: `DynamicSpawnSourceListener` runs, reads the catalog, emits `character_spawns` rows for `Allowed` fields, and fails the export with exit 3 + JSON envelope for `Unknown` fields.

### Task B1: `DynamicSpawnCatalog` — TOML loader and classifier

**Files:**
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnCatalog.cs`

- [ ] **Step 1:** Implement the hand-rolled TOML parser. The grammar is: sections `[[allowed]]` and `[[denied]]`, each with `script = "..."`, `fields = [...]` (string array), optional `position_field = "..."`, optional `reason = "..."`. No nested tables, no inline tables, no dotted keys. The parser reads line-by-line, tracks the current section, and builds two `Dictionary<(string script, string field), CatalogEntry>` maps.

```csharp
#nullable enable
using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public enum DynamicSpawnClassification { Allowed, Denied, Unknown }

public readonly struct CatalogEntry
{
    public DynamicSpawnClassification Classification { get; init; }
    public string? PositionField { get; init; }   // null = use host transform
    public string? Reason { get; init; }          // denied reason; null for allowed
}

public class DynamicSpawnCatalog
{
    private readonly Dictionary<(string script, string field), CatalogEntry> _entries = new();
    private readonly HashSet<string> _knownScripts = new();

    public static DynamicSpawnCatalog Load(string path)
    {
        var catalog = new DynamicSpawnCatalog();
        if (!File.Exists(path))
        {
            Debug.LogError($"[DynamicSpawnCatalog] Catalog file not found: {path}");
            return catalog; // empty catalog = everything is Unknown = export fails with all findings
        }

        string? currentSection = null;
        string? currentScript = null;
        List<string>? currentFields = null;
        string? currentPositionField = null;
        string? currentReason = null;

        foreach (var rawLine in File.ReadAllLines(path))
        {
            var line = rawLine.Trim();
            if (line.StartsWith('#') || line.Length == 0) continue;

            if (line == "[[allowed]]" || line == "[[denied]]")
            {
                // Flush previous section
                if (currentScript != null && currentFields != null)
                    catalog.AddSection(currentSection!, currentScript, currentFields, currentPositionField, currentReason);
                currentSection = line == "[[allowed]]" ? "allowed" : "denied";
                currentScript = null; currentFields = null; currentPositionField = null; currentReason = null;
            }
            else if (line.StartsWith("script = "))
            {
                currentScript = ParseStringValue(line);
            }
            else if (line.StartsWith("fields = "))
            {
                currentFields = ParseStringArrayValue(line);
            }
            else if (line.StartsWith("position_field = "))
            {
                currentPositionField = ParseStringValue(line);
            }
            else if (line.StartsWith("reason = "))
            {
                currentReason = ParseStringValue(line);
            }
        }
        // Flush last section
        if (currentScript != null && currentFields != null)
            catalog.AddSection(currentSection!, currentScript, currentFields, currentPositionField, currentReason);

        return catalog;
    }

    private void AddSection(string section, string script, List<string> fields, string? positionField, string? reason)
    {
        var classification = section == "allowed" ? DynamicSpawnClassification.Allowed : DynamicSpawnClassification.Denied;
        _knownScripts.Add(script);
        foreach (var field in fields)
        {
            _entries[(script, field)] = new CatalogEntry
            {
                Classification = classification,
                PositionField = positionField,
                Reason = reason,
            };
        }
    }

    public CatalogEntry Classify(string scriptType, string fieldName)
    {
        return _entries.TryGetValue((scriptType, fieldName), out var entry) ? entry : default;
    }

    public bool IsScriptKnown(string scriptType) => _knownScripts.Contains(scriptType);

    // ... ParseStringValue / ParseStringArrayValue helpers (strip quotes, split on comma)
}
```

- [ ] **Step 2:** Verify it compiles (Unity will compile on next export attempt). No standalone test — the listener integration test in Task B4 covers it.

- [ ] **Step 3: Commit** — `feat(export): add DynamicSpawnCatalog TOML loader and classifier`

### Task B2: Seed the catalog from the audit doc

**Files:**
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml`

- [ ] **Step 1:** Write the catalog. Derive `[[allowed]]` entries from the audit doc's script taxonomy (verified against playtest source in plan research). Each `script` + `fields` pair is one section. `[[denied]]` entries cover runtime-rebound trackers and Category C deferrals.

```toml
# Dynamic Spawn Source Catalog
# Classifies serialized Character/GameObject fields on event-script MonoBehaviours.
# Update this file when the export's dynamic-spawn-errors.json reports unknown
# candidates. Each (script, field) pair must be classified as allowed or denied.
# See: skill://auditing-spawn-coverage

schema_version = 1

# --- Category A: direct event-script spawns (emit to character_spawns) ---

[[allowed]]
script = "Chessboard"
fields = ["PeonNPC", "EmberNPC", "BlazeNPC", "MonarchNPC", "KingsmanNPC", "CandlekeeperNPC", "FacelessDuel", "FacelessArc", "FacelessPal", "FacelessDru", "FacelessStorm", "FacelessReaver"]
position_field = "SpawnLoc"

[[allowed]]
script = "Constellation"
fields = ["Spawns"]

[[allowed]]
script = "FernallaFightEvent"
fields = ["FinalFernalla", "FawnToSpawn", "Phase2Ward", "Phase2Assault"]

[[allowed]]
script = "FernallaPortalEvent"
fields = ["Arcanist", "Knight", "Hound", "Invader"]

[[allowed]]
script = "FernallaPortalBoss"
fields = ["Ward1", "Ward2", "Ward3"]

[[allowed]]
script = "MizukiEvent"
fields = ["Remnants", "FinalPush", "DoubleSpawn"]

[[allowed]]
script = "AstraListener"
fields = ["Dragon", "Beam"]

[[allowed]]
script = "PhantomFightEvent"
fields = ["WardsToSpawn"]
position_field = "WardSpawnPoints"

[[allowed]]
script = "SiraetheEvent"
fields = ["WardSpawnable"]

[[allowed]]
script = "SprinklesEvent"
fields = ["ForestWard"]

[[allowed]]
script = "StowawayPortal"
fields = ["Keeper", "Skeletons", "KeeperSac"]
position_field = "SpawnPointsForAdds"

[[allowed]]
script = "TreasureChestEvent"
fields = ["Guardians"]

[[allowed]]
script = "VithArena"
fields = ["Coin1Fight", "Coin2Fight", "Coin3Fight", "Coin4Fight", "Coin5Fight", "Coin6Fight", "Coin7Fight"]
position_field = "SpawnLoc1"

[[allowed]]
script = "WaveEvent"
fields = ["WeakWave", "StrongWave", "StrongestWave", "BossMob"]
position_field = "SpawnLocations"

[[allowed]]
script = "ZenithNadirScript"
fields = ["ConstellationMobs", "ConstellationStar", "Syzygy"]

[[allowed]]
script = "HonsusScript"
fields = ["AddToSpawn"]

[[allowed]]
script = "GraceEvent"
fields = ["AnimDupe"]

# --- Category B: chained spawns (host is a Character prefab → character_chained_spawns) ---
# Constellation is Category B: it lives on a Character prefab and spawns a pool on death.
# The listener detects Category B via a sibling Character component and writes to
# character_chained_spawns instead of character_spawns. Python expands these in Task C3.

# --- Denied: runtime-rebound trackers (host SpawnPoint already covers placement) ---

[[denied]]
script = "FaithEvent"
fields = ["Faith"]
reason = "Runtime-rebound from MySpawn.SpawnedNPC; the originating SpawnPoint already covers placement."

[[denied]]
script = "FaithEvent"
fields = ["HealObject"]
reason = "Heal effect prefab, not a Character."

[[denied]]
script = "GraceEvent"
fields = ["Grace"]
reason = "Runtime-rebound from MySpawn.SpawnedNPC; the originating SpawnPoint already covers placement."

[[denied]]
script = "RewardListener"
fields = ["Frost", "Inferno"]
reason = "Runtime tracker fields, not world placements."

[[denied]]
script = "SprinklesEvent"
fields = ["Sprinkles"]
reason = "Runtime-rebound from MySpawn.SpawnedNPC; the originating SpawnPoint already covers placement."

[[denied]]
script = "MizukiEvent"
fields = ["MizChar"]
reason = "Runtime-rebound from MySpawn.SpawnedNPC; the originating SpawnPoint already covers placement."

[[denied]]
script = "ZenithNadirScript"
fields = ["Zenith", "Nadir", "SyzygyChar"]
reason = "Runtime-rebound or direct Character references already placed via SpawnPoint."

# --- Denied: Category C deferred (zone-wide random spawners) ---

[[denied]]
script = "Misc"
fields = ["SivakayanSpectres"]
reason = "category-c-pending: zone-wide random spawner; needs zone_random_spawns table in follow-up plan."

# --- Denied: non-Character GameObject fields ---

[[denied]]
script = "MizukiEvent"
fields = ["MizGameObject", "SpawnSmoke", "WarpSmoke", "EndNode", "CondensedNodes"]
reason = "UI/FX/node prefabs, not Characters."

[[denied]]
script = "AstraListener"
fields = ["Astra", "SpawnLoc"]
reason = "Astra is the host NPC (placed via SpawnPoint); SpawnLoc is a position marker."

[[denied]]
script = "SiraetheEvent"
fields = ["WardOne", "WardTwo", "WardThree"]
reason = "Position markers, not Character prefabs."

[[denied]]
script = "ZenithNadirScript"
fields = ["ConstPt1", "ConstPt2", "SyzSpawn", "Chest", "ChestPos"]
reason = "Position/chest prefabs, not Characters."

[[denied]]
script = "VithArena"
fields = ["SpawnLoc1", "SpawnLoc2", "SpawnLoc3", "ChestSpawnPos", "AwardChests"]
reason = "Position markers and chest prefabs, not Characters."

[[denied]]
script = "WaveEvent"
fields = ["SpawnLocations"]
reason = "Position marker list; the actual spawn fields are WeakWave/StrongWave/etc."

[[denied]]
script = "HonsusScript"
fields = ["NavPoints"]
reason = "Navigation waypoints, not Character prefabs."

[[denied]]
script = "MalarothFeed"
fields = ["Malaroth", "Demented"]
reason = "Malaroth is the host; Demented is spawned via a runtime _npc argument, not a serialized field."

[[denied]]
script = "TreasureChestEvent"
fields = ["LiveGuardians", "Lid"]
reason = "LiveGuardians is a runtime list; Lid is a chest mesh."

[[denied]]
script = "StowawayPortal"
fields = ["KeeperSpawn"]
reason = "Position marker; Keeper is the spawn field."

[[denied]]
script = "PhantomFightEvent"
fields = ["LivingWards"]
reason = "Runtime list of live ward instances; WardsToSpawn is the prefab field."

[[denied]]
script = "NPCFightEvent"
fields = ["SpawnAdds", "SpawnOnDeath"]
reason = "These are List<GameObject> of prefabs; verify they have Character components before allowing — pending review."
```

- [ ] **Step 2: Commit** — `feat(export): seed dynamic-spawn-catalog.toml from playtest audit`

### Task B3: `DynamicSpawnErrorEnvelope` — structured error writer

**Files:**
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnErrorEnvelope.cs`

- [ ] **Step 1:** Implement the envelope writer. It collects `Unknown` findings (script + field + example prefab + example host) and `stale_entries` (catalog scripts not found in `Assembly-CSharp`), serializes to JSON at `variants/{variant}/.export/dynamic-spawn-errors.json`, and prints a human-readable stderr summary.

```csharp
#nullable enable
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

public class DynamicSpawnErrorEnvelope
{
    public List<Finding> Findings { get; } = new();
    public List<StaleEntry> StaleEntries { get; } = new();

    public readonly struct Finding
    {
        public string ScriptType { get; init; }
        public string FieldName { get; init; }
        public string FieldKind { get; init; }  // "GameObject" | "Character" | "List<GameObject>" etc.
        public string? ExamplePrefabPath { get; init; }
        public string? ExampleStableKey { get; init; }
        public string? ExampleDisplayName { get; init; }
        public string? HostScenePath { get; init; }
    }

    public readonly struct StaleEntry
    {
        public string Kind { get; init; }      // "allowed" | "denied"
        public string ScriptType { get; init; }
        public string FieldName { get; init; }
    }

    public bool HasErrors => Findings.Count > 0 || StaleEntries.Count > 0;

    public void WriteToFile(string path)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var sb = new StringBuilder();
        sb.AppendLine("{");
        sb.AppendLine("  \"type\": \"erenshor://export/unclassified-spawn-candidates\",");
        sb.AppendLine("  \"title\": \"Dynamic spawn candidates not classified in catalog\",");
        sb.AppendLine($"  \"status\": 3,");
        sb.AppendLine($"  \"detail\": \"Export found {Findings.Count} unclassified and {StaleEntries.Count} stale entries.\",");
        sb.AppendLine("  \"findings\": [");
        for (int i = 0; i < Findings.Count; i++)
        {
            var f = Findings[i];
            sb.AppendLine("    {");
            sb.AppendLine($"      \"script_type\": \"{f.ScriptType}\",");
            sb.AppendLine($"      \"field_name\": \"{f.FieldName}\",");
            sb.AppendLine($"      \"field_kind\": \"{f.FieldKind}\"");
            if (f.ExamplePrefabPath != null) sb.AppendLine($"      ,\"example_prefab_path\": \"{f.ExamplePrefabPath}\"");
            if (f.ExampleStableKey != null) sb.AppendLine($"      ,\"example_stable_key\": \"{f.ExampleStableKey}\"");
            if (f.ExampleDisplayName != null) sb.AppendLine($"      ,\"example_display_name\": \"{f.ExampleDisplayName}\"");
            if (f.HostScenePath != null) sb.AppendLine($"      ,\"host_scene_path\": \"{f.HostScenePath}\"");
            sb.Append("    }");
            if (i < Findings.Count - 1) sb.AppendLine(",");
            else sb.AppendLine();
        }
        sb.AppendLine("  ],");
        sb.AppendLine("  \"stale_entries\": [");
        for (int i = 0; i < StaleEntries.Count; i++)
        {
            var s = StaleEntries[i];
            sb.AppendLine("    {");
            sb.AppendLine($"      \"kind\": \"{s.Kind}\",");
            sb.AppendLine($"      \"script_type\": \"{s.ScriptType}\",");
            sb.AppendLine($"      \"field_name\": \"{s.FieldName}\"");
            sb.Append("    }");
            if (i < StaleEntries.Count - 1) sb.AppendLine(",");
            else sb.AppendLine();
        }
        sb.AppendLine("  ]");
        sb.AppendLine("}");
        File.WriteAllText(path, sb.ToString());
    }

    public void PrintHumanSummary()
    {
        if (!HasErrors) return;
        Debug.LogError("[DYNAMIC_SPAWN_GATE] Dynamic spawn coverage gate failed.");
        Debug.LogError($"  {Findings.Count} unclassified candidates, {StaleEntries.Count} stale catalog entries.");
        foreach (var f in Findings)
            Debug.LogError($"  • {f.ScriptType}.{f.FieldName}  (example: {f.ExampleDisplayName ?? f.ExampleStableKey ?? "unknown"})");
        foreach (var s in StaleEntries)
            Debug.LogError($"  stale: {s.Kind} {s.ScriptType}.{s.FieldName} (script not found in Assembly-CSharp)");
    }
}
```

- [ ] **Step 2: Commit** — `feat(export): add DynamicSpawnErrorEnvelope for structured gate failures`

### Task B4: `DynamicSpawnSourceListener` — the core listener

**Files:**
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnSourceListener.cs`
- Modify: `src/Assets/Editor/ExportBatch.cs` (register the listener, ~line 320 in the `spawnpoints` block)

- [ ] **Step 1:** Implement the listener. It implements `IAssetScanListener<MonoBehaviour>`, walks every component, filters to `Assembly-CSharp`, skips `SpawnPoint`/`SpawnPointTrigger`, enumerates serialized object-reference fields via `SerializedObject`, resolves to Character prefabs, consults the catalog, and emits rows.

```csharp
#nullable enable
using System;
using System.Collections.Generic;
using System.Reflection;
using SQLite;
using UnityEditor;
using UnityEngine;

public class DynamicSpawnSourceListener : IAssetScanListener<MonoBehaviour>
{
    private readonly SQLiteConnection _db;
    private readonly CharacterStableKeyResolver _characterKeyResolver;
    private readonly DynamicSpawnCatalog _catalog;
    private readonly DynamicSpawnErrorEnvelope _envelope = new();
    private readonly List<SpawnPointCharacterRecord> _spawnRecords = new();
    private readonly List<CharacterChainedSpawnRecord> _chainedRecords = new();

    public DynamicSpawnErrorEnvelope Envelope => _envelope;

    public DynamicSpawnSourceListener(
        SQLiteConnection db,
        CharacterStableKeyResolver characterKeyResolver,
        DynamicSpawnCatalog catalog)
    {
        _db = db;
        _characterKeyResolver = characterKeyResolver;
        _catalog = catalog;
    }

    public void OnAssetFound(MonoBehaviour comp)
    {
        var type = comp.GetType();
        if (type.Assembly.GetName().Name != "Assembly-CSharp") return;
        if (type == typeof(SpawnPoint) || type == typeof(SpawnPointTrigger)) return;

        var scriptName = type.Name;
        var so = new SerializedObject(comp);
        var prop = so.GetIterator();
        if (!prop.NextVisible(true)) return;

        var hostTransform = comp.transform;
        var hostScene = comp.gameObject.scene.name ?? "";
        var isChainedHost = comp.GetComponent<Character>() != null
            && PrefabUtility.IsPartOfPrefabAsset(comp.gameObject);

        do
        {
            if (prop.propertyType != SerializedPropertyType.ObjectReference) continue;
            var fieldName = prop.name;
            var value = prop.objectReferenceValue;
            if (value == null) continue;

            var entry = _catalog.Classify(scriptName, fieldName);
            if (entry.Classification == DynamicSpawnClassification.Denied) continue;
            if (entry.Classification == DynamicSpawnClassification.Unknown)
            {
                RecordFinding(comp, fieldName, prop, value);
                continue;
            }

            // Allowed — resolve to Character prefab(s)
            var characters = ResolveCharacters(value);
            foreach (var character in characters)
            {
                var childKey = _characterKeyResolver.GetStableKey(character);
                if (isChainedHost)
                {
                    var parentKey = _characterKeyResolver.GetStableKey(comp.GetComponent<Character>()!);
                    _chainedRecords.Add(new CharacterChainedSpawnRecord
                    {
                        ParentStableKey = parentKey,
                        ChildStableKey = childKey,
                        SourceScript = scriptName,
                        Key = $"{parentKey}|{childKey}|{scriptName}",
                    });
                }
                else
                {
                    // Category A — emit directly to character_spawns
                    var positions = ResolvePositions(comp, entry.PositionField);
                    foreach (var pos in positions)
                    {
                        _spawnRecords.Add(new SpawnPointCharacterRecord
                        {
                            // Note: SpawnPointCharacterRecord is the junction table;
                            // for direct spawn rows we need CharacterSpawnRecord instead.
                            // See Task B5 for the correct record type.
                        });
                    }
                }
            }
        } while (prop.NextVisible(false));
    }

    private List<Character> ResolveCharacters(Object value)
    {
        var result = new List<Character>();
        if (value is GameObject go)
        {
            var c = go.GetComponent<Character>();
            if (c != null) result.Add(c);
        }
        else if (value is Character c) result.Add(c);
        return result;
    }

    private List<Vector3> ResolvePositions(MonoBehaviour host, string? positionField)
    {
        if (positionField == null) return new List<Vector3> { host.transform.position };
        // Reflect the position field — could be Transform or List<Transform>
        var field = host.GetType().GetField(positionField, BindingFlags.Public | BindingFlags.Instance);
        if (field == null) return new List<Vector3> { host.transform.position };
        var val = field.GetValue(host);
        if (val is Transform t) return new List<Vector3> { t.position };
        if (val is IList<Transform> list)
        {
            var result = new List<Vector3>();
            foreach (var item in list) if (item != null) result.Add(item.position);
            return result;
        }
        return new List<Vector3> { host.transform.position };
    }

    private void RecordFinding(MonoBehaviour comp, string fieldName, SerializedProperty prop, Object value)
    {
        // ... populate _envelope.Findings with script/field/example
    }

    public void OnScanFinished()
    {
        // Insert spawn + chained records, check for stale catalog entries,
        // and if _envelope.HasErrors, write the envelope file and signal exit 3.
    }
}
```

- [ ] **Step 2:** This is the most complex piece. The placeholder above has intentional gaps (record type, stale-entry detection, exit-code signaling). These are resolved in Task B5 (record type) and Task B6 (stale entries + exit code). Implement the listener incrementally — get Category A working first, then Category B, then the error gate.

- [ ] **Step 3: Commit** — `feat(export): add DynamicSpawnSourceListener for event-script spawns` (work in progress)

### Task B5: Correct the record type for Category A spawn rows

**Files:**
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnSourceListener.cs`

The existing `SpawnPointCharacterRecord` is a junction table (`SpawnPointStableKey` + `CharacterStableKey`) — it requires a `SpawnPoint` parent row. Dynamic spawns have no `SpawnPoint`; they emit directly to `character_spawns` (the clean table). But the C# raw side uses `SpawnPointCharacterRecord` as the junction, and the Python build flattens `SpawnPointCharacters` + `SpawnPoints` into `character_spawns`.

**Decision:** The dynamic listener needs its own raw record that the Python build recognizes. The cleanest path is to write directly to a new raw table `DynamicCharacterSpawns` that the Python build reads alongside `SpawnPointCharacters`.

- [ ] **Step 1:** Create `src/Assets/Editor/Database/DynamicCharacterSpawnRecord.cs`:

```csharp
#nullable enable
using SQLite;

[Table("DynamicCharacterSpawns")]
public class DynamicCharacterSpawnRecord
{
    public const string TableName = "DynamicCharacterSpawns";

    [PrimaryKey]
    public string Key { get; set; } = string.Empty;  // "{character_stable_key}|{scene}|{x}|{y}|{z}|{source_script}"
    public string CharacterStableKey { get; set; } = string.Empty;
    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }
    public string SourceScript { get; set; } = string.Empty;
}
```

- [ ] **Step 2:** Update `DynamicSpawnSourceListener` to emit `DynamicCharacterSpawnRecord` for Category A rows instead of the placeholder.

- [ ] **Step 3:** Update the Python build (`characters.py`) to read `DynamicCharacterSpawns` and insert into `character_spawns` with `is_directly_placed=0`, `is_trigger_spawn=1`, `spawn_point_stable_key=NULL`, `source_script=<script>`:

```python
# Dynamic spawns (Category A) — from event-script MonoBehaviours
for r in _load_rows(raw_db, "SELECT * FROM DynamicCharacterSpawns"):
    spawn_out.append({
        "character_stable_key": r["CharacterStableKey"],
        "spawn_point_stable_key": None,
        "zone_stable_key": _zone_by_scene.get(r["Scene"]),
        "scene": r["Scene"],
        "x": r["X"], "y": r["Y"], "z": r["Z"],
        "is_enabled": 1,
        "is_directly_placed": 0,
        "is_trigger_spawn": 1,
        "source_script": r["SourceScript"],
        # ... all other fields default/None
    })
```

- [ ] **Step 4:** Re-export and confirm dynamic spawn rows appear:

```bash
uv run erenshor -V playtest extract export
uv run erenshor -V playtest extract build
sqlite3 variants/playtest/erenshor-playtest.sqlite "SELECT COUNT(*) FROM character_spawns WHERE source_script IS NOT NULL"
```
Expected: non-zero (the Chessboard, WaveEvent, etc. spawns should now appear).

- [ ] **Step 5: Commit** — `feat(export): emit dynamic spawn rows via DynamicCharacterSpawnRecord`

### Task B6: Stale-entry detection and exit-code-3 gate

**Files:**
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/DynamicSpawnSourceListener.cs` (`OnScanFinished`)
- Modify: `src/Assets/Editor/ExportBatch.cs` (handle exit code 3)

- [ ] **Step 1:** In `OnScanFinished`, after inserting rows, detect stale catalog entries — scripts in the catalog that don't exist in `Assembly-CSharp`:

```csharp
// Stale entry detection: catalog scripts not present in Assembly-CSharp
var assemblyTypes = System.AppDomain.CurrentDomain.GetAssemblies()
    .Where(a => a.GetName().Name == "Assembly-CSharp")
    .SelectMany(a => a.GetTypes())
    .Select(t => t.Name)
    .ToHashSet();
foreach (var scriptName in _catalog.KnownScripts)
{
    if (!assemblyTypes.Contains(scriptName))
    {
        // Find all fields for this script in the catalog and record as stale
        _envelope.StaleEntries.Add(new DynamicSpawnErrorEnvelope.StaleEntry
        {
            Kind = "allowed", // or denied — track both
            ScriptType = scriptName,
            FieldName = "<all fields>"
        });
    }
}
```

- [ ] **Step 2:** If `_envelope.HasErrors`, write the envelope to `variants/{variant}/.export/dynamic-spawn-errors.json`, print the human summary, and set a flag that `ExportBatch` checks after the scan to call `EditorApplication.Exit(3)`.

- [ ] **Step 3:** In `ExportBatch.Run()`, after `ExecuteScanSynchronously`, check the listener's envelope and exit 3 if it has errors. Add `.export/` to `.gitignore` (per variant).

- [ ] **Step 4:** Test the gate: temporarily add a fake `[[allowed]]` entry for a non-existent script `MysteryEvent` with field `Whatever`, re-export, and confirm exit 3 + the envelope file is written with the stale entry. Then remove the fake entry.

- [ ] **Step 5: Commit** — `feat(export): gate export on dynamic spawn catalog classification`

---

## Sub-phase 1C — Category B chained spawn expansion (Python)

Outcome: `character_chained_spawns` rows (parent→child) are expanded into `character_spawns` rows at the parent's coordinates.

### Task C1: Write the failing test for `expand_chained_spawns`

**Files:**
- Create: `tests/unit/application/processor/test_chained_spawns.py`

- [ ] **Step 1:** Write a test that sets up a clean DB with a parent character, a parent spawn row, and a `character_chained_spawns` row (parent→child), then calls the expansion and asserts the child gets a spawn row at the parent's coordinates:

```python
import pytest
import sqlite3
from erenshor.application.processor.characters import expand_chained_spawns

def test_expand_chained_spawns_creates_child_at_parent_coords(clean_db):
    # Parent has a spawn at (10, 20, 30) in "TestScene"
    clean_db.execute("INSERT INTO characters (stable_key, display_name) VALUES ('character:parent', 'Parent')")
    clean_db.execute("INSERT INTO characters (stable_key, display_name) VALUES ('character:child', 'Child')")
    clean_db.execute("""INSERT INTO character_spawns
        (character_stable_key, spawn_point_stable_key, scene, x, y, z, is_enabled, is_directly_placed, is_trigger_spawn)
        VALUES ('character:parent', NULL, 'TestScene', 10.0, 20.0, 30.0, 1, 0, 0)""")
    clean_db.execute("""INSERT INTO character_chained_spawns
        (parent_stable_key, child_stable_key, source_script)
        VALUES ('character:parent', 'character:child', 'Constellation')""")

    expand_chained_spawns(clean_db)

    child_spawns = clean_db.execute(
        "SELECT * FROM character_spawns WHERE character_stable_key = 'character:child'"
    ).fetchall()
    assert len(child_spawns) == 1
    row = child_spawns[0]
    assert row["scene"] == "TestScene"
    assert row["x"] == 10.0 and row["y"] == 20.0 and row["z"] == 30.0
    assert row["is_trigger_spawn"] == 1
    assert row["source_script"] == "Constellation"
    assert row["spawn_point_stable_key"] is None
```

- [ ] **Step 2:** Run it; expect failure (`expand_chained_spawns` not defined).

- [ ] **Step 3: Commit** — `test(pipeline): add failing test for chained spawn expansion`

### Task C2: Implement `expand_chained_spawns`

**Files:**
- Modify: `src/erenshor/application/processor/characters.py`

- [ ] **Step 1:** Add the function after the existing spawn insert block (after line 782):

```python
def expand_chained_spawns(conn: sqlite3.Connection) -> None:
    """Expand Category B chained spawns into character_spawns.

    For each (parent, child) in character_chained_spawns, emit one
    character_spawns row per existing parent spawn, using the parent's
    (scene, x, y, z) and is_trigger_spawn=1. Deduplicates on
    (character_stable_key, scene, x, y, z, source_script).
    """
    chained = conn.execute(
        "SELECT parent_stable_key, child_stable_key, source_script FROM character_chained_spawns"
    ).fetchall()
    if not chained:
        return

    inserted = set()
    rows_to_insert = []
    for parent, child, source in chained:
        parent_spawns = conn.execute(
            """SELECT scene, x, y, z, zone_stable_key FROM character_spawns
               WHERE character_stable_key = ?""", (parent,)
        ).fetchall()
        for ps in parent_spawns:
            key = (child, ps["scene"], ps["x"], ps["y"], ps["z"], source)
            if key in inserted:
                continue
            inserted.add(key)
            rows_to_insert.append({
                "character_stable_key": child,
                "spawn_point_stable_key": None,
                "zone_stable_key": ps["zone_stable_key"],
                "scene": ps["scene"],
                "x": ps["x"], "y": ps["y"], "z": ps["z"],
                "is_enabled": 1,
                "is_directly_placed": 0,
                "is_trigger_spawn": 1,
                "source_script": source,
            })

    if rows_to_insert:
        conn.executemany(
            """INSERT OR IGNORE INTO character_spawns
               (character_stable_key, spawn_point_stable_key, zone_stable_key, scene,
                x, y, z, is_enabled, is_directly_placed, is_trigger_spawn, source_script)
               VALUES (:character_stable_key, :spawn_point_stable_key, :zone_stable_key, :scene,
                :x, :y, :z, :is_enabled, :is_directly_placed, :is_trigger_spawn, :source_script)""",
            rows_to_insert
        )
        logger.info(f"Chained spawns: expanded {len(rows_to_insert)} rows")
```

- [ ] **Step 2:** Call it in `process_characters` after `writer.insert_character_spawns(spawn_out)`:

```python
    writer.insert_character_spawns(spawn_out)
    logger.info(f"Characters: wrote {len(spawn_out)} spawn rows")

    # Expand Category B chained spawns (Constellation family etc.)
    expand_chained_spawns(writer.conn)
```

- [ ] **Step 3:** Run the test; expect PASS.

- [ ] **Step 4: Commit** — `feat(pipeline): expand chained spawns into character_spawns`

---

## Sub-phase 1D — Scanner refactor (performance)

Outcome: `AssetScanner` dispatch uses precomputed typed delegates instead of per-call reflection. The dynamic listener processes every MonoBehaviour, so this eliminates the overhead.

### Task D1: Refactor `AssetScanner` to typed-delegate dispatch

**Files:**
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/AssetScanner.cs`

- [ ] **Step 1:** Read the full `AssetScanner.cs` to understand the current dispatch in `ScanGameObjectsAndComponentsInHierarchy` (the `InvokeOnAssetFound` path).

- [ ] **Step 2:** Replace the per-call `GetMethod` + `Invoke` with a precomputed `Dictionary<Type, List<Action<Component>>>` built lazily on first scan. The `RegisterComponentListener<T>` captures a delegate at registration time. The hot loop becomes a `TryGetValue` + delegate invocation.

- [ ] **Step 3:** Verify no regression — run a full playtest export before and after the refactor, diff the raw DB tables:

```bash
# Before refactor (save baseline)
cp variants/playtest/erenshor-playtest-raw.sqlite /tmp/raw-before.sqlite
# After refactor
uv run erenshor -V playtest extract export
# Compare
sqlite3 /tmp/raw-before.sqlite ".dump" > /tmp/before.sql
sqlite3 variants/playtest/erenshor-playtest-raw.sqlite ".dump" > /tmp/after.sql
diff /tmp/before.sql /tmp/after.sql | head -20
```
Expected: no differences in table content (the dispatch is purely mechanical).

- [ ] **Step 4: Commit** — `refactor(export): precompute typed dispatch delegates in AssetScanner`

---

## Sub-phase 1E — Verify orphan reduction

Outcome: the playtest orphan count drops from ~204 to the Category C residual (~5 Sivakayan spectres + a few known dead-data rows).

### Task E1: Re-export and run the orphan audit

- [ ] **Step 1:** Run the full pipeline:

```bash
uv run erenshor -V playtest extract export
uv run erenshor -V playtest extract build
```

- [ ] **Step 2:** Run the orphan audit SQL (from `skill://auditing-spawn-coverage` Step 1) against the clean DB. Confirm the count dropped from the pre-implementation baseline (~204) to the Category C residual (~5-10 rows, all Sivakayan spectres + known dead data like TOWNSPERSON templates).

- [ ] **Step 3:** If the count didn't drop as expected, diagnose: check the envelope for `findings` (unclassified fields that need catalog entries) and `stale_entries` (catalog scripts not found). Iterate on the catalog until the export exits 0 and the orphan count is at baseline.

- [ ] **Step 4:** Run `uv run pytest tests/unit/application/processor/test_chained_spawns.py -v` to confirm the Category B test passes against real data.

- [ ] **Step 5: Commit** — any catalog corrections needed during verification. Final commit if none: `test(export): verify dynamic spawn orphan reduction`

---

## Phase 2 — Skill hygiene

Outcome: skills reflect the new gate workflow; `writing-skills` removed; frontmatter/descriptions improved.

### Task F1: Rewrite `auditing-spawn-coverage` around the structured envelope

**Files:**
- Modify: `.agent/skills/auditing-spawn-coverage/SKILL.md`

- [ ] **Step 1:** Update the skill so the primary workflow is: run export → if exit 3, read `dynamic-spawn-errors.json`, classify findings, edit catalog, re-run. The SQL audit stays as the safety net (Step 5 in the skill) for Category C and consistency checks.

- [ ] **Step 2: Commit** — `docs(skills): rewrite auditing-spawn-coverage around structured envelope`

### Task F2: Add frontmatter to `tile-capture`, improve narrow descriptions

**Files:**
- Modify: `.agent/skills/tile-capture/SKILL.md`
- Modify: `.agent/skills/cli-commands/SKILL.md`
- Modify: `.agent/skills/sheets-queries/SKILL.md`
- Modify: `.agent/skills/mod-pipeline/SKILL.md`

- [ ] **Step 1:** Add YAML frontmatter to `tile-capture/SKILL.md` (spec §3.2).

- [ ] **Step 2:** Update descriptions per spec §3.3.

- [ ] **Step 3: Commit** — `docs(skills): add tile-capture frontmatter and improve descriptions`

### Task F3: Delete `writing-skills`, update `AGENTS.md`

**Files:**
- Delete: `.agent/skills/writing-skills/`
- Modify: `AGENTS.md`

- [ ] **Step 1:** `rm -rf .agent/skills/writing-skills/`

- [ ] **Step 2:** Remove the `writing-skills` row from the Skill Directory table in `AGENTS.md`.

- [ ] **Step 3: Commit** — `chore(skills): remove writing-skills, superseded by Anthropic canonical guidance`

### Task F4: Update `unity-export-system` skill

**Files:**
- Modify: `.agent/skills/unity-export-system/SKILL.md`

- [ ] **Step 1:** Add a short paragraph pointing to `DynamicSpawnSourceListener` and the catalog file as the canonical example of a listener that emits to `character_spawns` without a `SpawnPoint`.

- [ ] **Step 2: Commit** — `docs(skills): document DynamicSpawnSourceListener in unity-export-system`

### Task F5: Add `tests/unit/test_skills.py` — skill-validity regression guard

**Files:**
- Create: `tests/unit/test_skills.py`

- [ ] **Step 1:** Write the test (spec §4.2). It walks `.agent/skills/*/SKILL.md`, parses YAML frontmatter, and asserts:
  - `name` field present and equals `basename(dirname(file))`
  - `description` field present
  - description is third person (no leading "I ", "You ", "We ")
  - description contains "Use when"
  - `writing-skills` directory does not exist
  - `AGENTS.md` contains no `writing-skills` substring

```python
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / ".agent" / "skills"

def _parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).splitlines():
        if ':' in line:
            key, _, val = line.partition(':')
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm

def test_every_skill_has_valid_frontmatter():
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
            continue
        skill_file = skill_dir / "SKILL.md"
        assert skill_file.exists(), f"{skill_dir.name}/SKILL.md missing"
        fm = _parse_frontmatter(skill_file.read_text())
        assert fm.get("name") == skill_dir.name, \
            f"{skill_dir.name}: name field must match directory name"
        assert "description" in fm, f"{skill_dir.name}: missing description"
        desc = fm["description"]
        assert not re.match(r'^(I |You |We )', desc), \
            f"{skill_dir.name}: description must be third person"
        assert "Use when" in desc, \
            f"{skill_dir.name}: description must contain 'Use when'"

def test_writing_skills_removed():
    assert not (SKILLS_DIR / "writing-skills").exists()
    agents_md = (REPO_ROOT / "AGENTS.md").read_text()
    assert "writing-skills" not in agents_md
```

- [ ] **Step 2:** Run `uv run pytest tests/unit/test_skills.py -v`.

- [ ] **Step 3: Commit** — `test(skills): add skill-validity regression guard`

---

## Sub-phase 1F — Tests

### Task G1: C# listener integration test (if feasible)

**Note:** C# tests in the Unity Editor are hard to automate. The primary verification is the export run + orphan count (Task E1). If a fixture-based test is practical, add it; otherwise, the orphan audit is the test.

- [ ] **Step 1:** Assess whether a Unity `Test` fixture (in `src/Assets/Editor/Tests/` if it exists) can scan a prefab with a known `Chessboard` host and assert 12 spawn rows. If the infrastructure doesn't exist, skip — the export + audit is sufficient.

### Task G2: Python unit tests for `expand_chained_spawns`

**Files:**
- Modify: `tests/unit/application/processor/test_chained_spawns.py`

- [ ] **Step 1:** Add edge-case tests:
  - Parent with multiple spawns → child gets one row per parent spawn.
  - Duplicate (parent, child, source) → deduplicated.
  - Parent with no spawns → child gets no rows.
  - Multiple children from one parent.

- [ ] **Step 2:** Run `uv run pytest tests/unit/application/processor/test_chained_spawns.py -v`.

- [ ] **Step 3: Commit** — `test(pipeline): cover chained spawn expansion edge cases`

---

## Self-review checklist

After implementing all tasks, verify:

- [ ] `uv run erenshor -V playtest extract export` exits 0 (no unclassified/stale findings).
- [ ] `uv run erenshor -V playtest extract build` succeeds.
- [ ] Orphan count on playtest dropped to Category C residual (~5-10 rows).
- [ ] `uv run pytest tests/unit/application/processor/test_chained_spawns.py -v` passes.
- [ ] `uv run pytest` (full suite) passes — no regressions from schema changes.
- [ ] Skills updated per Phase 2.
- [ ] `AGENTS.md` no longer references `writing-skills`.
