# Dynamic Spawn Coverage — Design Spec

**Date:** 2026-05-28
**Scope:** Close the export-pipeline gap for characters spawned by event-scrip
MonoBehaviours and by chained `Spawns[]` lists on Character prefabs. Add an
explicit fail-fast classification gate so future game updates surface new spawn
sources to the maintainer instead of silently regressing coverage. Concurrently
clean up the project's agent-facing skill catalog against 2026 best practices.

**Categories covered (per audit doc `docs/plans/2026-05-28-spawn-coverage-audit.md`):**

- **A. Direct event-script spawns** (~100 orphans) — MonoBehaviour in a scene
  with serialized prefab fields, instantiated at runtime at the host's transform.
- **B. Chained Character→Spawns[] spawns** (~10 orphans, mainly
  `Constellation*` family) — MonoBehaviour on a Character prefab that spawns a
  pool when it dies/triggers; spawn location is wherever the parent itself was
  placed.

**Out of scope (deferred):**

- **C. Scene-wide random spawners** (~5 orphans, Sivakayan spectre family
  driven by `ZoneAnnounce.SpawnSivakayanSpecter` + `Misc.SivakayanSpectres[]`)
  — needs a new `zone_random_spawns` table and a new wiki/map renderer ("may
  appear in {zone}"). Tracked as follow-up; the discovery half of the
  implementation in this spec WILL surface these candidates, but Category C
  classifications get a `denied` entry with `reason = "category-c-pending"`
  until the follow-up ships.

---

## 1. Architecture

```
                  ┌─────────────────────────────────────┐
                  │  variants/{v}/unity/                │
                  │    ExportedProject/                 │
                  │      Assets/Scripts/Assembly-CSharp/│
                  │  (read-only decompiled game code)   │
                  └──────────────┬──────────────────────┘
                                 │ scans
                                 ▼
  src/Assets/Editor/ExportSystem/AssetScanner/
  ├── AssetScanner.cs              ◀── refactored: typed delegates + precomputed dispatch table
  ├── Listener/
  │   ├── SpawnPointListener.cs           (unchanged)
  │   ├── SpawnPointTriggerListener.cs    (unchanged)
  │   ├── CharacterListener.cs            (unchanged)
  │   └── DynamicSpawnSourceListener.cs   ◀── NEW
  ├── DynamicSpawnCatalog.cs              ◀── NEW (loads + validates TOML)
  ├── DynamicSpawnErrorEnvelope.cs        ◀── NEW (RFC-9457 + extensions)
  └── dynamic-spawn-catalog.toml          ◀── NEW (checked-in tristate catalog)

src/erenshor/application/processor/characters.py
  └── expand_chained_spawns()             ◀── NEW (Category B expansion)

src/Assets/Editor/Database/
  ├── CharacterSpawnRecord.cs             ◀── + source_script column
  └── CharacterChainedSpawnRecord.cs      ◀── NEW

variants/{v}/.export/
  └── dynamic-spawn-errors.json           ◀── written on exit code 3

.agent/skills/
  ├── auditing-spawn-coverage/SKILL.md    ◀── rewritten around envelope
  ├── refreshing-game-data/SKILL.md       (link already added)
  ├── unity-export-system/SKILL.md        ◀── + brief pointer to new listener
  ├── tile-capture/SKILL.md               ◀── + frontmatter (currently missing)
  ├── cli-commands/SKILL.md               ◀── pushier description
  ├── sheets-queries/SKILL.md             ◀── pushier description
  ├── mod-pipeline/SKILL.md               ◀── pushier description
  └── writing-skills/                     ◀── REMOVED entirely
```

Two-phase delivery: Phase 1 lands the export changes; Phase 2 lands the skill
cleanup. Implementation plan will sequence both.

---

## 2. Phase 1 — Dynamic spawn coverage

### 2.1 `DynamicSpawnSourceListener`

**Type:** `IAssetScanListener<MonoBehaviour>`, registered against `MonoBehaviour`
in `ExportBatch.cs`. The refactored dispatcher (§2.5) routes every
MonoBehaviour to this listener.

**Per-component algorithm:**

1. **Assembly filter:** if `comp.GetType().Assembly.GetName().Name !=
   "Assembly-CSharp"`, return. Cuts the discovery surface ~10× by excluding
   Unity built-ins, TextMeshPro, third-party plugins, and our own export code.
2. **Skip already-handled types:** if the component is `SpawnPoint` or
   `SpawnPointTrigger`, return (covered by existing listeners).
3. **Enumerate serialized object-reference fields** via
   `new SerializedObject(comp).GetIterator()` + `NextVisible(true)`, filtering
   on `propertyType == SerializedPropertyType.ObjectReference`. Recurse into
   array/list elements (`isArray && arrayElementType == "PPtr<$GameObject>"`
   etc.) by iterating their children.
4. **Resolve to source prefab:** for each non-null `objectReferenceValue`, call
   `PrefabUtility.GetCorrespondingObjectFromSource(value) ?? value`. Reject if
   the resolved object is not a `GameObject` and not a `Component`.
5. **Filter to Character prefabs:** require the resolved GameObject to have a
   `Character` component. Skip otherwise (effect/UI/projectile prefabs).
6. **Catalog lookup:** consult `DynamicSpawnCatalog` with `(scriptTypeName,
   fieldName)`:
   - `Allowed` → emit row(s) per §2.2 (Category A) or §2.6 (Category B,
     when the host itself has a sibling `Character` component on the same
     GameObject — write to `character_chained_spawns` instead).
   - `Denied` → no row emitted; the catalog entry is tracked so that, on
     `OnScanFinished`, any catalog entries that match no script in
     `Assembly-CSharp` get listed as `stale_entries`.
   - `Unknown` → record as a finding for the error envelope (§2.4); **no
     `character_spawns` row emitted** for the entire export run.
7. On `OnScanFinished()`, if any unknown findings exist OR if any stale catalog
   entries are detected, write `dynamic-spawn-errors.json` and signal the
   scanner to exit with code 3. The export does NOT write a partial database
   — that would let downstream consumers see inconsistent state.

**Performance:** SerializedObject construction is allocation-heavy. The
`Assembly-CSharp` filter does the bulk of the work. Estimated upper bound:
~1500 prefabs × ~20 scenes × ~50 game-script MonoBehaviours per scene/prefab,
worst case ~50K iterations. Acceptable.

### 2.2 Spawn row emission

When an `Allowed` `(scriptType, fieldName)` resolves to a Character prefab,
the listener emits one `character_spawns` row per (host transform × prefab),
treating each list element as a distinct host transform.

For each row:

| Column | Value |
|---|---|
| `character_stable_key` | `_characterKeyResolver.GetStableKey(character)` against the resolved prefab |
| `spawn_point_stable_key` | NULL |
| `zone_stable_key` | derived from host scene via the existing zone-by-scene index |
| `scene` | host transform's scene name |
| `x, y, z` | host transform's world position (or `spawnLoc.position` if the script's catalog entry specifies a `position_field`) |
| `is_enabled` | `1` (the host being in the scene implies enabled at start) |
| `is_directly_placed` | `0` |
| `is_trigger_spawn` | `1` |
| `source_script` | scripting type name, e.g. `"Chessboard"` (NEW column) |
| all other columns | NULL / defaults |

**Position resolution:** by default the host MonoBehaviour's own
`transform.position` is used. A catalog entry MAY specify `position_field =
"SpawnLoc"` to point at a sibling Transform/GameObject field; in that case the
listener reads that field's `transform.position` instead. List-typed position
fields emit one row per list element.

### 2.3 `dynamic-spawn-catalog.toml`

**Location:** `src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml`.

**Format:**

```toml
# Schema documented in:
#   .agent/skills/auditing-spawn-coverage/SKILL.md
# Update this file when the export's dynamic-spawn-errors.json reports unknown
# candidates. Each (script, fields[]) pair must be classified as allowed or
# denied.

schema_version = 1

[[allowed]]
script = "Chessboard"
fields = [
  "PeonNPC", "EmberNPC", "BlazeNPC", "MonarchNPC",
  "KingsmanNPC", "CandlekeeperNPC",
  "FacelessDuel", "FacelessArc", "FacelessPal",
  "FacelessDru", "FacelessStorm", "FacelessReaver",
]
# Optional: position_field = "SpawnLoc" if positions come from a sibling field

[[allowed]]
script = "FernallaPortalEvent"
fields = ["Arcanist", "Knight", "Hound", "Invader"]

# … (full initial content derived during implementation from audit doc) …

[[denied]]
script = "FaithEvent"
fields = ["Faith"]
reason = "Runtime-rebound from MySpawn.SpawnedNPC; the originating SpawnPoint already covers placement."

[[denied]]
script = "RewardListener"
fields = ["Frost", "Inferno"]
reason = "Runtime tracker fields, not world placements."

# Category C deferred — see docs/plans/2026-05-28-dynamic-spawn-coverage-design.md §1
[[denied]]
script = "Misc"
fields = ["SivakayanSpectres"]
reason = "category-c-pending: zone-wide random spawner; needs zone_random_spawns table in follow-up plan."
```

**`DynamicSpawnCatalog` (C# loader):**

- Loads at scanner startup (in `OnScanStarted`).
- Parses TOML via a vendored parser (e.g. `Tomlyn` already used elsewhere; otherwise add it as a UPM dep).
- Validates: no `(script, field)` pair appears in both lists; each `script`
  matches a `Type` in `Assembly-CSharp` (warn on stale entries — write them
  into the error envelope's `stale_entries` array).
- Provides `Classify(string scriptType, string fieldName) → Allowed | Denied |
  Unknown` and `GetPositionField(string scriptType) → string?`.

**Initial seeding:** during implementation, derive the initial `[[allowed]]`
and `[[denied]]` content from the 145 orphans enumerated in the audit doc.
Expect ~20 `[[allowed]]` entries and ~5–10 `[[denied]]` entries to start.

### 2.4 Structured error envelope

**File:** `variants/{variant}/.export/dynamic-spawn-errors.json`. The `.export/`
directory is added to `.gitignore`.

**Envelope shape** (RFC 9457 Problem Details + agent-oriented extensions):

```json
{
  "type": "erenshor://export/unclassified-spawn-candidates",
  "title": "Dynamic spawn candidates not classified in catalog",
  "status": 3,
  "detail": "Export found N MonoBehaviour serialized fields referencing Character prefabs that are not classified in dynamic-spawn-catalog.toml. Each must be marked 'allowed' (emit spawn rows) or 'denied' (skip, with reason). Re-run after editing the catalog.",
  "instance": "erenshor://export/{variant}/{iso8601-timestamp}",
  "docs_url": "skill://auditing-spawn-coverage",
  "catalog_path": "src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml",
  "findings": [
    {
      "script_type": "NewBossEvent",
      "field_name": "AdditionalMinion",
      "field_kind": "GameObject | GameObject[] | List<GameObject> | Character | Character[] | List<Character>",
      "example_prefabs": [
        {
          "asset_path": "Assets/Prefabs/Characters/bone_minion.prefab",
          "stable_key": "character:bone minion",
          "display_name": "Bone Minion"
        }
      ],
      "example_hosts": [
        {
          "scene_path": "Assets/Scenes/NewZone.unity",
          "transform_path": "/Events/NewBossEventTrigger"
        }
      ],
      "investigation": {
        "script_path": "variants/{variant}/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/NewBossEvent.cs",
        "test": "Look for Object.Instantiate(AdditionalMinion, ...). If the result chains .GetComponent<Character>() or .GetComponent<NPC>() AND is NOT reassigned from MySpawn.SpawnedNPC or similar runtime source, the field is a fresh world placement → allow. Otherwise → deny."
      },
      "suggested_fix": {
        "applicability": "needs_review",
        "options": [
          {
            "kind": "allow",
            "when": "Field is a fresh world placement",
            "toml_append": "[[allowed]]\nscript = \"NewBossEvent\"\nfields = [\"AdditionalMinion\"]\n"
          },
          {
            "kind": "deny",
            "when": "Runtime-rebound, template, tracker, or non-Character prefab",
            "toml_append": "[[denied]]\nscript = \"NewBossEvent\"\nfields = [\"AdditionalMinion\"]\nreason = \"<one sentence>\"\n"
          }
        ]
      }
    }
  ],
  "stale_entries": [
    {
      "kind": "allowed",
      "script_type": "OldRemovedEvent",
      "field_name": "OldMinion",
      "suggested_fix": {
        "applicability": "machine_applicable",
        "action": "Remove the entry from dynamic-spawn-catalog.toml — the script no longer exists in Assembly-CSharp."
      }
    }
  ]
}
```

**Mirror to stderr (human view):**

```
ERROR: Dynamic spawn coverage gate failed.

3 unclassified spawn candidates and 1 stale catalog entry must be resolved.
Structured details: variants/playtest/.export/dynamic-spawn-errors.json
Workflow:           skill://auditing-spawn-coverage

Unclassified candidates:
  • NewBossEvent.AdditionalMinion  (example: Bone Minion)
  • NewBossEvent.SecondaryMinion   (example: Skeleton Captain)
  • NewDialogEvent.SummonChar      (example: Loyal Malaroth)

Stale catalog entries (script/field no longer exists):
  • allowed: OldRemovedEvent.OldMinion

Exit code 3.
```

**Caps and bounds (per AX research — token efficiency):**

- `example_prefabs` capped at 3 per finding.
- `example_hosts` capped at 3 per finding.
- If there are more than 50 findings in one run, group them by `script_type` and
  list one finding per script. (Practically never happens; defensive bound.)

**Python CLI integration:** `erenshor extract export` already invokes Unity in
batch mode. When the Unity process exits with code 3, the CLI reads the JSON
envelope, prints the human stderr summary, and surfaces the JSON path as a tool
output (so an agent driver sees both forms).

### 2.5 Scanner refactor (typed delegates + precomputed dispatch)

Independent improvement, folded in because the new listener exposes the curren
dispatcher's reflection overhead.

**Current** (`AssetScanner.ScanGameObjectsAndComponentsInHierarchy`):

```csharp
foreach (var kvp in _componentListeners) {
  if (kvp.Key.IsAssignableFrom(compType)) {
    foreach (var listenerObj in kvp.Value) {
      var method = listenerType.GetMethod("OnAssetFound");
      method.Invoke(listenerObj, new object[] { comp });
    }
  }
}
```

`O(components × listeners)` `IsAssignableFrom` checks plus `GetMethod` lookup
+ `Invoke` + `object[]` allocation per dispatch.

**Refactored:**

- `RegisterComponentListener<T>(IAssetScanListener<T> listener)` captures a
  delegate at registration time:
  ```csharp
  Action<Component> dispatch = comp => listener.OnAssetFound((T)comp);
  _componentDispatchers.Add((typeof(T), dispatch));
  ```
- Build a `Dictionary<Type, List<Action<Component>>> _dispatchersByType` lazily
  on first scan: for each concrete `Type` we encounter, populate by walking
  `_componentDispatchers` once and matching via `IsAssignableFrom`.
- Hot loop becomes:
  ```csharp
  if (_dispatchersByType.TryGetValue(comp.GetType(), out var dispatchers))
    foreach (var d in dispatchers) d(comp);
  ```
- Same shape for `_gameObjectListeners` and `_scriptableObjectListeners`.
- External `IAssetScanListener<T>` interface unchanged; no listener code
  changes. The two existing default-interface-method dispatches in
  `OnScanStarted` / `OnScanFinished` get the same delegate caching.

### 2.6 Category B — chained spawns

**New table:** `character_chained_spawns`

```sql
CREATE TABLE character_chained_spawns (
    parent_stable_key  TEXT NOT NULL REFERENCES characters (stable_key),
    child_stable_key   TEXT NOT NULL REFERENCES characters (stable_key),
    source_script      TEXT NOT NULL,
    PRIMARY KEY (parent_stable_key, child_stable_key, source_script)
)
```

**Population path:** the same `DynamicSpawnSourceListener` writes here instead
of `character_spawns` when the host MonoBehaviour lives on a Character prefab
(detected via `comp.GetComponent<Character>() != null`, where `comp` is a
sibling component on the same GameObject as the iterated MonoBehaviour, and
the GameObject is a prefab root not a scene root).

**Python expansion:** in
`src/erenshor/application/processor/characters.py`, after the raw→clean pass
that produces `character_spawns`, add `expand_chained_spawns()`:

```python
def expand_chained_spawns(raw_db, clean_db):
    """For each (parent, child) in character_chained_spawns,
    emit one character_spawns row per existing parent spawn,
    using the parent's (scene, x, y, z) and is_trigger_spawn=1."""
    for parent, child, source in raw_db.iter_chained():
        for parent_spawn in clean_db.spawns_for(parent):
            clean_db.insert_spawn(
                character_stable_key=child,
                scene=parent_spawn.scene,
                x=parent_spawn.x, y=parent_spawn.y, z=parent_spawn.z,
                zone_stable_key=parent_spawn.zone_stable_key,
                spawn_point_stable_key=None,
                is_directly_placed=0,
                is_trigger_spawn=1,
                source_script=source,
            )
```

Deduplicate at insert time on `(character_stable_key, scene, x, y, z,
source_script)` to handle the case where a parent has multiple spawn rows
that happen to collide.

### 2.7 Schema changes summary

| Table | Change | Rationale |
|---|---|---|
| `character_spawns` | + `source_script TEXT NULL` column | Debuggability; lets `auditing-spawn-coverage` SQL group orphans by the listener that emitted them. NULL means "from SpawnPoint listener" (backward compatible). |
| `character_chained_spawns` | NEW (see §2.6) | Category B intermediate; expanded by Python into `character_spawns`. |

No breaking changes to existing tables. The new column is nullable and
unused by current consumers; renderers can opt in.

---

## 3. Phase 2 — Skill hygiene

### 3.1 Delete `writing-skills`

**Rationale:** Anthropic publishes authoritative skill-authoring guidance a
`platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices` and
maintains the canonical `skill-creator` skill a
`github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md`. A
project-local copy of that guidance is bound to drift; the project-specific
slice (e.g. "we use `.agent/skills/`, not `.claude/skills/`") is trivial enough
to not warrant a skill.

**Removals:**

- `rm -rf .agent/skills/writing-skills/`
- `AGENTS.md`: remove the row from the Skill Directory table (currently a
  line 144).

No other references found (`search "writing-skills"` returns only the skill
itself and the AGENTS.md row).

### 3.2 Add frontmatter to `tile-capture`

Currently the file starts with `# Tile Capture` and has no YAML block. This
makes it invisible to skill discovery.

**Add at top of `.agent/skills/tile-capture/SKILL.md`:**

```yaml
---
name: tile-capture
description: Capture map tiles for Erenshor zones via the in-game MapTileCapture BepInEx mod. Use when generating new tile pyramids after a zone changes, debugging tile capture/stitching, configuring `zone-capture-config.json`, or working with the Wine path conversion or chunk-grid suppression logic in `src/erenshor/application/capture/`.
---
```

### 3.3 Improve narrow descriptions

Apply Anthropic's "pushy" description guidance — include explicit trigger
phrases an agent's user might say. Touched skills:

| Skill | New description |
|---|---|
| `cli-commands` | `Typer CLI command patterns under src/erenshor/cli/. Use when adding a new subcommand, modifying an existing one, debugging Typer errors, fixing CLI arg/option handling, or wiring a Python module into the CLI entry point.` |
| `sheets-queries` | `Google Sheets SQL queries against the clean SQLite DB. Use when adding a new sheet, modifying an existing query, changing a sheet schema or column set, debugging sheets deploy failures, or working with anything under src/erenshor/sheets/.` |
| `mod-pipeline` | `Companion mod build, deploy, and Thunderstore publish lifecycle, including CalVer versioning from git commit history. Use when building or deploying any mod under src/mods/, publishing to Thunderstore, debugging the mod packaging or installation, or modifying CalVer/version-generation logic.` |

Other descriptions are fine as-is.

### 3.4 Rewrite `auditing-spawn-coverage` around the structured envelope

The current draft of `auditing-spawn-coverage` is built around the manual SQL
audit. With Phase 1 shipping a fail-fast gate, the skill's primary workflow
becomes:

1. Run `erenshor -V {v} extract export`.
2. If it exits 0, no action.
3. If it exits 3, read `variants/{v}/.export/dynamic-spawn-errors.json` and:
   - For each `findings[]` entry: follow `investigation.test`, decide allow vs
     deny, append the matching `suggested_fix.toml_append` snippet to
     `dynamic-spawn-catalog.toml`.
   - For each `stale_entries[]` entry: remove the matching block from
     `dynamic-spawn-catalog.toml`.
4. Re-run the export. Repeat until exit 0.

The SQL recipe in the existing skill stays as the **safety net** for anything
the listener can't see — Category C zone-wide random spawners, and Category B
chained spawns if `expand_chained_spawns()` has a bug — and as a one-sho
consistency check against the eventual `zone_random_spawns` table when
Category C ships.

### 3.5 Update `unity-export-system` and `refreshing-game-data`

- `unity-export-system/SKILL.md`: one short paragraph pointing a
  `DynamicSpawnSourceListener` and the catalog file as the canonical example of
  a listener that emits to `character_spawns` without a `SpawnPoint`.
- `refreshing-game-data/SKILL.md`: already links to `auditing-spawn-coverage`
  from step 4 (validate gate). No further change.

---

## 4. Testing strategy

### 4.1 Phase 1

| Concern | How it's tested |
|---|---|
| Listener finds every `Allowed` field and emits correct row count | Integration test: scan a fixture scene + prefab with a known `Chessboard` host; assert 12 expected rows in `character_spawns`. |
| Listener correctly skips `Denied` fields | Same fixture: add a `FaithEvent`-shaped host with `Faith` field; assert zero rows for `character:faith`. |
| Unknown field fails the export with exit 3 + valid envelope | Test fixture with a fake `MysteryEvent.Whatever` field pointing at a Character prefab. Run export; assert exit 3, valid JSON at the expected path, schema-validates. |
| Stale catalog entries surface | Add a catalog entry for a script that doesn't exist; run export; assert stale_entries[] populated. |
| Category B chained spawns expand correctly | Fixture with a `Constellation`-bearing Character prefab placed at one SpawnPoint; assert post-build clean DB has spawn rows for each `Spawns[]` entry at the parent's coordinates. |
| Scanner refactor preserves existing output | Snapshot test: run full export on main variant before and after the refactor; assert byte-equal clean DB. |
| Pre-existing orphan list shrinks | Re-run the audit SQL after seeding the catalog from the audit doc; assert orphan count drops to the Category C residual (~5 rows). |

### 4.2 Phase 2

| Concern | How it's tested |
|---|---|
| `tile-capture` has valid frontmatter | New unit test that walks `.agent/skills/*/SKILL.md`, parses YAML frontmatter, asserts presence of `name`, `description`, and that `name == basename(dirname)`. |
| `writing-skills` removal complete | Same test asserts no `writing-skills` directory; assert no `writing-skills` substring in `AGENTS.md`. |
| Description quality | The skill-validity test additionally asserts each description is in third person (no leading "I ", "You ", "We ") and contains the substring "Use when". |

The skill-validity test belongs in `tests/unit/test_skills.py` (does not exis
yet — created in Phase 2). Cheap regression guard for the future.

---

## 5. Risk & rollback

| Risk | Mitigation |
|---|---|
| Catalog seeding misclassifies a Category A as Denied | Re-running the audit SQL after Phase 1 lists every orphan whose `source_script` is NULL — these are the misclassifications; correct in catalog and re-export. Cost: one re-export per error. |
| Scanner refactor introduces a subtle regression | Snapshot test (4.1) catches byte-level differences in the clean DB. If snapshot fails, revert the dispatcher commit (atomic, isolated). |
| `Tomlyn` dependency for catalog parsing not already in project | If not present, fall back to a tiny hand-rolled parser (the catalog grammar is trivial: `[[allowed]]` / `[[denied]]` sections with `script`, `fields`, `position_field`, `reason`). Decision deferred to implementation. |
| Exit code 3 collides with a hypothetical existing convention | Check `ExportBatch.cs` exit codes; current code uses 0 and 1 only (confirmed by reading the file header during audit). Safe. |
| Schema change to `character_spawns` breaks Python build | Add column at the C# record level; Python processor copies through unchanged. Existing wiki/map renderers ignore the new column. |

---

## 6. Non-goals

- **Category C** (Sivakayan spectre family / scene-wide random spawners): a
  separate plan will define the `zone_random_spawns` schema and the wiki/map
  rendering. Until then, Category C entries are denied with
  `reason = "category-c-pending"`.
- **Renaming existing skills to gerund form**: stylistic improvement; no
  worth the cost of breaking `skill://` references and AGENTS.md entries.
- **Removing the per-frame yielding in `ScanAllAssetsCoroutine`**: micro-
  optimization for batch mode; independent of this work.
- **Replacing `Resources.LoadAll<ScriptableObject>` with pure `AssetDatabase`**:
  pre-existing wart, independent.

---

## 7. Open implementation questions

These are not blocking for the spec but will be resolved during the
implementation plan:

1. **TOML parser dependency** — pick `Tomlyn` (if present) or hand-roll for
   our minimal grammar.
2. **`source_script` column on the SpawnPoint listener's output** — set to
   `"SpawnPoint"` and `"SpawnPointTrigger"` for clarity? Or leave NULL to
   signal "from the canonical SpawnPoint path"? Leaning NULL for backward
   compatibility.
3. **Position field resolution** — when the catalog says `position_field =
   "SpawnLocations"` and that field is `List<Transform>`, we emit one row per
   element. Confirm this matches the runtime behavior for each entry tha
   uses lists (`WaveEvent`, `PhantomFightEvent`, etc.) during catalog seeding.
