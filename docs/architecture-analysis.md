# Architecture Analysis: Data Pipeline Rewrite

## Purpose

This document defines the target architecture for the Erenshor data pipeline
and how to get there safely. It supersedes the provisional analysis that
hedged toward partial fixes. The direction is the full three-layer rewrite
described in `docs/PRD-data-pipeline-rewrite.md`, with no compromises for
backward compatibility.

The display name unification problem (wiki↔map links, `IsUnique` misclassifi-
cation, sheets showing raw game names) is not a feature gap — it is a symptom
of the current architecture's fundamental flaw. Patching it piecemeal would
entrench the flaw further. The right answer is to fix the pipeline.

---

## 1. Current Pipeline: The Problem in Full

### Architecture diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  GAME ASSETS                                                    │
│  Unity ScriptableObjects, scene files, prefabs                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │  Unity batch mode
                           │  C# Listeners (4,073 lines)
                           │  - extract game data
                           │  - compute IsUnique (grouped by NPCName ← BUG)
                           │  - compute IsCommon/IsRare
                           │  - write SQLite directly
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  RAW GAME DATABASE  variants/{v}/erenshor-{v}.sqlite            │
│                                                                 │
│  Contents: every entity the game contains, including:           │
│    - SimPlayer prefab templates (should never be visible)       │
│    - Duplicate instances of the same NPC                        │
│    - Excluded entities (mapping.json says to hide them)         │
│    - Wrong IsUnique flags (NPCName grouping ignores renames)    │
│    - Raw game names (NPCName) throughout, no display overrides  │
│                                                                 │
│  Schema: 60+ tables, 4,000+ characters, ~90 columns/character   │
└──────┬────────────────────────┬──────────────────────┬──────────┘
       │                        │                      │
       │ Python                 │ shutil.copy2         │ SQLAlchemy
       │ RegistryResolver       │ (raw game DB)        │ direct read
       │ (auto-build from       │                      │
       │  NPCName + mapping)    │                      │
       ▼                        ▼                      ▼
┌──────────────────┐  ┌─────────────────────┐  ┌──────────────────┐
│  REGISTRY DB     │  │  MAP SQLITE         │  │  SHEETS SQL      │
│  registry.db     │  │  (raw copy of game  │  │  22 .sql files   │
│  (wiki-only      │  │   DB, no overrides) │  │  (run on raw DB) │
│   artifact)      │  │                     │  │                  │
│                  │  │  TypeScript reads   │  │  - use NPCName   │
│  entities table: │  │  NPCName for:       │  │  - hardcode URL  │
│  stable_key      │  │  - display labels   │  │    ?marker= fmt  │
│  display_name    │  │  - wiki link URLs   │  │  - no exclusion  │
│  page_title      │  │  - search index     │  │    filtering     │
│  image_name      │  │                     │  │  - duplicates    │
│  excluded        │  │  IsUnique from C#   │  │    included      │
│                  │  │  (wrong for renamed │  │                  │
│  (rebuilt from   │  │   characters)       │  │                  │
│   NPCName +      │  │                     │  │                  │
│   mapping.json)  │  │  All excluded and   │  │                  │
│                  │  │  SimPlayer entities │  │                  │
│                  │  │  visible on map     │  │                  │
└──────┬───────────┘  └──────────┬──────────┘  └──────────────────┘
       │                         │
       │ Python enrichers,       │ npm build embeds SQLite
       │ generators, templates   │ as static asset
       ▼                         ▼
┌──────────────────┐  ┌─────────────────────┐
│  WIKI (MediaWiki)│  │  MAP (Cloudflare)   │
│                  │  │                     │
│  Correct names   │  │  Wrong names:       │
│  (registry used) │  │  NPCName everywhere │
│                  │  │                     │
│  Correct pages   │  │  Broken wiki links: │
│  (page_title     │  │  NPCName → wrong    │
│   from registry) │  │  wiki page for any  │
│                  │  │  renamed character  │
└──────────────────┘  └─────────────────────┘
```

### Root causes

Every visible symptom traces to one of three root causes:

**Root cause 1: Unity writes cleaning artefacts into the export.**
`IsUnique` is computed in C# by grouping characters by their raw `NPCName`.
This is wrong for any character that has a display name override in
`mapping.json`. The Braxonian Planar Guards (`NPCName = "Braxonian Planar
Guard"`) are two distinct entities renamed to different display names, but
Unity sees one name shared across two spawn points and marks both as common.
Fixing this in C# would require Unity to know about `mapping.json` — which
violates the separation between raw extraction and data cleaning.

**Root cause 2: The registry is a wiki-only side-car.**
`mapping.json` is consumed by the Python registry builder (`operations.py`)
to produce `registry.db`. This artifact is read by the wiki pipeline's
`RegistryResolver` during page generation. The map and sheets never see it.
So every display name override, every wiki page title, every image name
override is invisible to the map and sheets.

**Root cause 3: There is no clean database.**
The raw game SQLite is the only SQLite. It contains SimPlayers, excluded
entities, wrong `IsUnique` flags, and raw game names. Each output layer
works around this in its own way: the wiki uses the registry; the map filters
some things at query time; sheets use COALESCE and DISTINCT to patch around
nulls and duplicates. None of this is centralised or consistent.

---

## 2. Target Architecture: Three-Layer Pipeline

This is the architecture the codebase converges to. It is described in full
in `docs/PRD-data-pipeline-rewrite.md`. This document adds precision on the
migration strategy, validation, and the C# rewrite scope.

### Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  GAME ASSETS (Unity)                                             │
│  ScriptableObjects, scenes, prefabs                              │
└──────────────────────────┬───────────────────────────────────────┘
                           │  extract export  (Unity batch mode)
                           │  C# JSON Exporters — pure extraction,
                           │  zero computation, zero filtering
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  RAW JSON   variants/{v}/exported-data/                          │
│                                                                  │
│  characters.json, items.json, spells.json, zones.json, ...       │
│  One file per entity type. Nested arrays for relationships.      │
│  Faithful dump of Unity data. Includes everything.               │
│  Human-readable. Diffable in version control.                    │
│  Inspectable without Unity or Python.                            │
└──────────────────────────┬───────────────────────────────────────┘
                           │  extract build  (Python, seconds)
                           │  - validate JSON (Pydantic)
                           │  - apply mapping.json overrides
                           │  - filter excluded entities
                           │  - remove SimPlayers
                           │  - cascade-remove broken references
                           │  - deduplicate identical entities
                           │  - compute IsUnique (per display name)
                           │  - compute IsRare, IsCommon
                           │  - insert into normalised schema
                           │  - VACUUM + ANALYZE
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  CLEAN DATABASE  variants/{v}/erenshor-{v}.sqlite                │
│                                                                  │
│  Every entity in this database is:                               │
│    - valid (no broken references)                                │
│    - correctly named (display_name from mapping.json applied)    │
│    - linked to its wiki page (wiki_page_name column)             │
│    - correctly classified (IsUnique per display name group)      │
│    - deduplicated (spawn locations merged, no duplicate rows)    │
│    - present only if it should be (no excluded, no SimPlayers)   │
│                                                                  │
│  All consumers read this database. No further cleaning needed.   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
          ┌────────────────┼───────────────────┐
          │                │                   │
          ▼                ▼                   ▼
┌──────────────┐  ┌────────────────┐  ┌───────────────────┐
│  WIKI        │  │  SHEETS        │  │  MAP              │
│  (MediaWiki) │  │  (Google)      │  │  (Cloudflare)     │
│              │  │                │  │                   │
│  Pure format │  │  Simple SQL    │  │  display_name     │
│  + deploy    │  │  SELECTs with  │  │  → char.name      │
│              │  │  JOINs         │  │                   │
│  No cleaning │  │                │  │  wiki_page_name   │
│  No registry │  │  No COALESCE   │  │  → wiki link URL  │
│  No enrichers│  │  No DISTINCT   │  │                   │
│  No dedup    │  │  No exclusion  │  │  IsUnique (clean) │
│              │  │  filters       │  │  → rarity marker  │
└──────────────┘  └────────────────┘  └───────────────────┘
```

### What each layer owns

**Layer 1 (C# Exporters)**: Extract. Nothing else. Every field the game has
is serialised to JSON as-is. No computed fields, no filtering, no SQLite
dependency. The output is a faithful snapshot of Unity's data at export time.

**Layer 2 (Python Processor)**: Clean. Everything else before formatting.
Applies `mapping.json`, filters, deduplicates, validates, and writes the
clean database. This is the only place where `mapping.json` is read, the
only place where `IsUnique` is computed, and the only place where an entity
can be excluded from all downstream consumers.

**Layer 3 (Wiki / Sheets / Map)**: Format and deliver. Each consumer reads
the clean database and produces its output. No consumer does any cleaning.

---

## 3. What Goes Away

The three-layer rewrite eliminates several components entirely. These are not
simplified — they are deleted.

| Component | Current role | Fate |
|-----------|-------------|------|
| `registry.db` | Wiki-only name/page lookup | **Deleted.** Clean DB has `display_name` and `wiki_page_name` columns. |
| `RegistryResolver` class | Resolves stable_key → display name, page title, links | **Deleted.** Replaced by direct SQL queries on the clean DB. |
| `registry/operations.py` | Builds registry from NPCName + mapping.json | **Deleted.** Logic moves to Layer 2 Python processor. |
| `registry/resolver.py` | Runtime lookup for wiki generators | **Deleted.** |
| `registry/schema.py` | SQLModel entity table | **Deleted.** |
| `application/enrichers/` | Augments Character/Item/etc. with related data | **Deleted.** The clean DB schema makes enrichment unnecessary (JOINs provide the data directly). |
| `CharacterEnricher`, `ItemEnricher`, etc. | Per-entity enrichment services | **Deleted.** |
| `EnrichedCharacterData` | Enrichment result object | **Deleted.** |
| `_deduplicate_characters()` in `entities.py` | In-memory dedup during page generation | **Deleted.** Deduplication happens in Layer 2. |
| C# `Database/` record types (60+ files) | SQLite schema C# side | **Deleted.** JSON serialisation replaces them. |
| C# `IsUnique`, `IsCommon`, `IsRare` SQL UPDATEs in `CharacterListener` | Rarity classification | **Deleted.** Moved to Layer 2 Python. |
| `SheetsFormatter` COALESCE/DISTINCT | Null and duplicate workarounds | **Deleted.** Clean DB has no nulls or duplicates needing this. |

---

## 4. What the C# Rewrite Looks Like

The C# side shrinks dramatically. The Listeners go from ~4,000 lines of
SQLite-writing code with record types, transactions, and SQL UPDATEs to
~1,500 lines of JSON serialisation.

### Current C# structure (to be replaced)

```
ExportSystem/
  AssetScanner/
    Listener/               ← 29 listener files (~4,000 lines)
      CharacterListener.cs  ← 997 lines (SQLite writes, SQL UPDATEs, rarity logic)
      ItemListener.cs       ← 445 lines
      SpawnPointListener.cs ← 258 lines (spawn chance maths, IsCommon/IsRare)
      ... 26 more
  IAssetScanListener.cs
  AssetScanner.cs           ← orchestrates listeners
Database/
  *.cs                      ← ~60 record types with SQLite-ORM attributes (~1,900 lines)
  Repository.cs             ← SQLite connection management
```

### Target C# structure

```
ExportSystem/
  AssetScanner/
    Exporter/               ← replaces Listener/
      CharacterExporter.cs  ← ~150 lines (extract fields, serialise to JSON)
      ItemExporter.cs
      SpawnPointExporter.cs
      ... one per entity type
  IAssetExporter.cs         ← replaces IAssetScanListener
  AssetScanner.cs           ← minimal changes (swap Listener → Exporter)
Export/
  *.cs                      ← JSON data contracts (~30 files, ~500 lines total)
                               (plain C# classes, no ORM attributes)
```

Key changes per listener:

1. **Remove SQLite dependency.** No `SQLiteConnection`, no `_db.CreateTable`,
   no `_db.InsertAll`, no `_db.RunInTransaction`.
2. **Remove computed fields.** `IsUnique`, `IsCommon`, `IsRare` SQL UPDATEs
   move to Layer 2 Python. The exporter records raw flags from the game
   component only where they exist (e.g., the raw `IsRare` flag on a spawn
   point character slot).
3. **Remove `StableKeyGenerator` from SQL writes.** Stable keys are still
   computed in C# (same logic), but written to JSON instead of SQLite.
4. **Serialise to JSON.** Each exporter accumulates its records into a list
   and writes to `exported-data/{entity-type}.json` at scan completion.
   Use Unity's `JsonUtility` or `Newtonsoft.Json` (already available via
   the Unity package).
5. **Preserve nested structure.** Instead of flat junction tables, the JSON
   uses nested arrays (e.g., `character.spells: ["spell:fireball"]`). Layer 2
   flattens these into junction tables when writing the clean DB.

### Scope of C# changes

| File category | Files | Lines | Change |
|--------------|-------|-------|--------|
| Listener files | 29 | ~4,000 | Rewrite as Exporters (~1,500 lines) |
| Database record types | ~60 | ~1,900 | Replace with JSON contracts (~500 lines) |
| Repository.cs | 1 | ~50 | Delete |
| IAssetScanListener.cs | 1 | ~20 | Replace with IAssetExporter.cs |
| AssetScanner.cs | 1 | ~200 | Minor changes (swap interface) |
| ExportBatch.cs | 1 | ~100 | Minor changes (output path) |

Total C# to rewrite: ~6,000 lines → ~2,000 lines. A net deletion of 4,000
lines of C#.

---

## 5. What the Layer 2 Python Processor Looks Like

Layer 2 is a new `extract build` command in the Python CLI. It replaces and
absorbs the current `registry/` package.

### Processing pipeline per entity type

```python
# Pseudocode for one entity type — all types follow the same pattern
def process_characters(json_path, mapping, db):
    # 1. Load and validate
    raw = json_path.read_text()
    records = [CharacterRecord(**r) for r in json.loads(raw)]  # Pydantic validation

    # 2. Apply mapping overrides (display_name, wiki_page_name, image_name)
    for record in records:
        override = mapping.get(record.stable_key)
        record.display_name = override.display_name if override else record.npc_name
        record.wiki_page_name = override.wiki_page_name if override else record.npc_name
        record.image_name = override.image_name if override else record.npc_name

    # 3. Filter excluded (wiki_page_name is null after mapping) + SimPlayers
    records = [r for r in records
               if r.wiki_page_name is not None and not r.is_sim_player]

    # 4. Remove references to excluded entities (cascade cleanup)
    valid_keys = {r.stable_key for r in records}
    for record in records:
        record.spells = [s for s in record.spells if s in valid_spell_keys]
        record.loot_drops = [l for l in record.loot_drops if l.item_stable_key in valid_item_keys]
        # ... etc.

    # 5. Deduplicate (identical records differing only in spawn locations)
    canonical, dedup_map = deduplicate(records)

    # 6. Compute IsUnique, IsRare, IsCommon per display_name group
    compute_rarity(canonical)

    # 7. Insert canonical records and junction rows
    db.insert_characters(canonical)
    db.insert_deduplication_map(dedup_map)
```

### Entity processing order (dependency graph)

```
Zones      ─────────────────────────────────┐
Items      ─────────────────────────────┐   │
Spells     ──────────────────────────┐  │   │
Skills     ───────────────────────┐  │  │   │
Stances    ────────────────────┐  │  │  │   │
Quests     ─────────────────┐  │  │  │  │   │
Factions   ──────────────┐  │  │  │  │  │   │
Characters ──────────────┴──┴──┴──┴──┴──┴───┘
```

Each entity type waits for its dependencies to be inserted before its own
cross-reference cleanup runs. Characters are last because they reference
all other types.

### Deduplication semantics (characters)

Two characters are duplicates if and only if ALL of the following match
after mapping is applied:

- `display_name` (post-mapping name)
- `level` and all base stat fields
- Spell set (as a frozenset of stable keys)
- Loot drop set (as a frozenset of (item_key, probability) pairs)
- Vendor inventory set (as a frozenset of item_key)
- Dialog quest set (as a frozenset of quest_key)
- All type flags (`is_friendly`, `is_npc`, `is_vendor`, etc.)
- All combat fields

Spawn locations (`character_spawns`) are NOT part of the identity — they
are merged into the canonical entity.

### IsUnique computation (replacing the C# bug)

```python
def compute_rarity(characters: list[Character]) -> None:
    # Count distinct spawn points per display_name group
    spawn_counts: dict[str, int] = defaultdict(int)
    for char in characters:
        spawn_counts[char.display_name] += len(char.spawn_locations)

    for char in characters:
        total_spawns = spawn_counts[char.display_name]
        # A character is unique if its display_name group has exactly one
        # spawn point in the entire world.
        char.is_unique = (total_spawns == 1)
        # IsRare/IsCommon preserved from raw spawn data (not recomputed here)
```

This correctly handles the Braxonian Planar Guards: "Braxonian Planar Guard
(Fire)" has one spawn point, "Braxonian Planar Guard (Ice)" has one spawn
point. Both are unique. Under the old C# logic, "Braxonian Planar Guard"
(the shared NPCName) had two spawn points and neither was unique.

### The `mapping.json` contract

`mapping.json` is unchanged in format. It is consumed once, at Layer 2,
and its effects are persisted into the clean DB. The file is never read
again by any consumer (wiki, sheets, map). Conflict detection (two entities
with the same display_name) runs during `extract build` and fails loudly
if unresolved conflicts are found.

---

## 6. Clean Database Schema

The clean DB is a fresh SQLite file, not a mutation of the raw export.
It has a designed schema, not a reflection of the game's internal structure.

### Column naming convention

All columns in the clean DB use **snake_case**. The raw SQLite produced by
Unity uses PascalCase (dictated by C# conventions). The clean DB is authored
entirely by Python and follows Python conventions throughout. This eliminates
the `pascal_to_snake()` conversion step in every repository and makes the
boundary between raw and clean data visually obvious.

Consequence: all 23 sheets SQL files and the TypeScript map queries are
updated to use snake_case column names. This update happens as part of the
same Phase 1 pass that rewrites the SQL anyway (removing COALESCE, adding
`display_name`), so there is no additional churn cost.

### Core tables (characters as example)

```sql
CREATE TABLE characters (
    stable_key      TEXT PRIMARY KEY,
    object_name     TEXT NOT NULL,
    npc_name        TEXT NOT NULL,      -- raw game name, preserved for reference
    display_name    TEXT NOT NULL,      -- from mapping.json or = npc_name
    wiki_page_name  TEXT NOT NULL,      -- wiki page title; excluded entities absent
    image_name      TEXT NOT NULL,      -- from mapping.json or = npc_name
    level           INTEGER NOT NULL,
    is_unique       INTEGER NOT NULL,   -- recomputed per display_name group
    is_rare         INTEGER NOT NULL,
    is_common       INTEGER NOT NULL,
    is_friendly     INTEGER NOT NULL,
    is_vendor       INTEGER NOT NULL,
    -- ... all other scalar game fields in snake_case ...
);

CREATE TABLE character_spawns (
    character_stable_key   TEXT NOT NULL REFERENCES characters(stable_key) ON DELETE CASCADE,
    zone_stable_key        TEXT NOT NULL REFERENCES zones(stable_key),
    spawn_point_stable_key TEXT,        -- NULL for directly-placed characters
    x REAL, y REAL, z REAL,
    spawn_chance           REAL NOT NULL,
    level_mod              INTEGER NOT NULL DEFAULT 0,
    base_respawn           REAL,
    PRIMARY KEY (character_stable_key, spawn_point_stable_key)
);

CREATE TABLE character_deduplication (
    canonical_stable_key TEXT NOT NULL REFERENCES characters(stable_key),
    merged_stable_key    TEXT NOT NULL,  -- original stable_key before merge
    merged_object_name   TEXT NOT NULL,
    PRIMARY KEY (merged_stable_key)
);

-- Similar pattern for: character_spells, character_loot, character_vendor_items,
-- character_faction_modifiers, character_dialogs, etc.
```

### Design invariants

Every row in the clean DB satisfies:

1. `display_name` is set (never null, never empty)
2. `wiki_page_name` is set (excluded entities are not in the DB at all)
3. All foreign key references point to rows that exist in the DB
4. No SimPlayer characters
5. No duplicate canonical entities (entities differing only in spawn
   locations are merged)
6. `is_unique` reflects the display_name-grouped spawn count, not the
   NPCName-grouped count

---

## 7. Output Layer Simplification

### Wiki

The wiki pipeline loses its most complex components:

- **Delete**: `registry/` package (6 files)
- **Delete**: `application/enrichers/` package (5 files)
- **Delete**: `domain/enriched_data/` package (5 files)
- **Delete**: `_deduplicate_characters()` in `generators/pages/entities.py`
- **Simplify**: `generators/pages/entities.py` — page generation becomes a
  simple loop: load entities from DB → generate template → apply field
  preservation → yield page
- **Simplify**: `generators/sections/character.py` — all name/page resolution
  becomes direct attribute access (`character.display_name`,
  `character.wiki_page_name`) instead of `resolver.resolve_display_name(key)`
- **Simplify**: `infrastructure/database/repositories/characters.py` — the
  query no longer needs COALESCE or complex filtering; clean DB has no nulls
  or excluded entities
- **Keep unchanged**: Jinja2 templates, field preservation, MediaWiki client,
  deploy service, fetch service

### Sheets

SQL queries become simple JOINs with no cleanup workarounds:

```sql
-- Before (current spawn-points.sql, simplified):
SELECT c.NPCName, ...
    COALESCE(za.ZoneName, '') AS ZoneName,
    'https://erenshor-maps.wowmuch1.workers.dev/map?marker=' || sp.StableKey AS MapLink
FROM SpawnPoints sp
JOIN Characters c ON ...
JOIN Zones za ON ...
WHERE spc.SpawnChance > 0

-- After:
SELECT c.display_name, ...
    za.display_name AS zone_name,
    'https://erenshor-maps.wowmuch1.workers.dev/map?sel=marker:' || sp.stable_key AS map_link
FROM character_spawns cs
JOIN characters c ON cs.character_stable_key = c.stable_key
JOIN zones za ON cs.zone_stable_key = za.stable_key
```

No COALESCE (no nulls), no exclusion filters (excluded entities absent),
no DISTINCT for deduplication (already done in Layer 2). Map URL format is
updated to use current `sel=marker:` format.

### Map

The map TypeScript gains correctness for free because the clean DB has the
right columns:

- `character.display_name` → `char.name` (display label)
- `character.wiki_page_name` → `char.wikiTitle` (wiki link URL fragment)
- `character.is_unique` (correctly computed) → rarity classification

The map's `database.base.ts` spawn point query adds two columns to the
existing SELECT and removes no existing logic. The `SpawnCharacter` type
gains `wikiTitle: string | null`.

`WikiLink.svelte` gains a `wikiTitle` prop (separate from the display label).
All callers in spawn point and search popups pass both.

The `maps dev` command continues to symlink the clean DB (it's stable
between game re-exports, just like it was previously).

---

## 8. Golden Output Validation Strategy

Golden baselines are the migration's primary safety net. Manual spot-checks
do not scale across thousands of wiki pages and 23 sheets tabs. Any approach
other than capturing and diffing full output is insufficiently reliable for a
rewrite of this scope.

### What we capture

Three sets of golden files, stored in `tests/golden/` and committed to the
repository before any code changes. They capture the current pipeline's full
output — bugs and all. Intentional bug fixes are applied to the golden files
explicitly, with documentation of why they differ from the original.

**Wiki golden** (`tests/golden/wiki/*.wiki`)
One file per page title, named `{page_title}.wiki`, containing the complete
wikitext string (`GeneratedPage.content`). Captured by running
`wiki generate` and copying the generated files.

**Sheets golden** (`tests/golden/sheets/*.csv`)
One CSV per query name (23 files), containing the full formatted output from
`SheetsFormatter.format_sheet()`. Row 0 is the header. Captured by running
each SQL query through the formatter and writing CSV.

**Map golden** (`tests/golden/map/spawn-points.csv`)
Output of the TypeScript-side spawn-points query (`getSpawnPointMarkers`)
executed directly against the current DB via Python's `sqlite3`. One row per
spawn-character pair. Captured by running the query and writing CSV.

### Capture commands

```bash
# Before any code changes:
uv run erenshor wiki generate
uv run erenshor golden capture  # new CLI command, see Phase 1 plan
```

The `golden capture` command:
1. Copies all files from `variants/main/wiki/generated/` to `tests/golden/wiki/`
2. Runs all 23 sheet queries through `SheetsFormatter`, writes CSVs to
   `tests/golden/sheets/`
3. Runs the map spawn-points SQL against the current DB, writes to
   `tests/golden/map/spawn-points.csv`

### Comparison strategy

Golden files are the expected output. After each code change, the regression
test generates fresh output and diffs against them. The test fails on any
unexpected difference. Intentional differences (bug fixes) must be committed
to the golden files with an explicit annotation.

The diff is line-level for sheets and map CSVs, and full-text for wiki pages.
Row ordering must be deterministic: all SQL queries use explicit `ORDER BY`,
and wiki pages are sorted by title.

### Intentional differences (bug fixes committed to golden)

These known improvements will be reflected in the golden files before Phase 1
regression tests run. Each is explicitly updated in golden and annotated:

| Change | Why it differs from original |
|--------|------------------------------|
| `is_unique = 1` for Braxonian Planar Guard (Fire) and (Ice) | `IsUnique` now grouped by `display_name`, not `NPCName` |
| SimPlayer rows absent from sheets golden | Correctly excluded in clean DB |
| Excluded entity rows absent from sheets golden | Correctly excluded in clean DB |

All other differences from original output are regressions.

### Unacceptable differences (regressions)

- Any entity present in golden but missing from new output
- Any entity absent from golden but present in new output (unless it is a
  known SimPlayer or excluded entity — those should disappear)
- Any field value change (name, level, stat, coordinate, probability, etc.)
- Any spawn point missing or added
- Any wiki page title change not matching a known mapping.json override
- Any loot drop, vendor item, spell, or faction relationship missing or added

### Automated regression test

```python
# tests/integration/test_golden.py
def test_sheets_golden(sheets_engine, golden_sheets_dir):
    formatter = SheetsFormatter(sheets_engine, queries_dir)
    for query_name in ALL_QUERIES:
        actual = formatter.format_sheet(query_name)
        golden = read_golden_csv(golden_sheets_dir / f"{query_name}.csv")
        assert actual == golden, f"Regression in {query_name}"

def test_wiki_golden(clean_db_path, golden_wiki_dir):
    pages = {p.title: p.content for p in generate_wiki_pages(clean_db_path)}
    for wiki_file in golden_wiki_dir.glob("*.wiki"):
        title = wiki_file.stem
        assert title in pages, f"Missing wiki page: {title}"
        assert pages[title] == wiki_file.read_text(), f"Regression in {title}"

def test_map_golden(clean_db_path, golden_map_dir):
    actual = run_spawn_points_query(clean_db_path)
    golden = read_golden_csv(golden_map_dir / "spawn-points.csv")
    assert actual == golden, "Regression in map spawn-points"
```

### `extract build` is independently runnable

`extract build` reads from the existing raw SQLite
(`variants/{v}/erenshor-{v}-raw.sqlite`) and writes the clean DB
(`variants/{v}/erenshor-{v}.sqlite`). It does not require a fresh
`extract export` — changing build logic and re-running `extract build`
takes seconds, not the hours a full export requires. This is the primary
reason `export` and `build` are separate commands.

---

## 9. Migration Sequence

The rewrite proceeds in three phases. Each phase has a clearly defined
"done" state that is independently testable. No half-measures: each phase
is a complete, deployable state — no parallel code paths, no legacy baggage.

### Phase 1: Build Layer 2 and switch all consumers

**Goal**: `extract build` produces a clean DB. All consumers (wiki, sheets,
map) read exclusively from the clean DB. The registry, enrichers, and
deduplication code are deleted. Golden regression tests pass.

**No backward compatibility is maintained.** The registry and enrichers are
deleted in the same phase that introduces the clean DB — there is no
transitional state where both exist.

Steps:

1. **Capture golden outputs** (before any code changes).
   Run `wiki generate`, then `golden capture` to snapshot all wiki pages,
   all sheet query results, and the map spawn-points query output.
   Commit golden files to `tests/golden/`.

2. **Rename raw DB path.**
   `extract export` writes to `variants/{v}/erenshor-{v}-raw.sqlite`
   instead of `variants/{v}/erenshor-{v}.sqlite`. This frees the canonical
   path for the clean DB.

3. **Write the Layer 2 processor** (`src/erenshor/application/processor/`).
   - `build.py` — top-level orchestrator
   - `mapping.py` — loads and applies `mapping.json`
   - `characters.py` — filter, dedup, `is_unique` computation
   - `entities.py` — generic processor for other entity types
   - `writer.py` — writes clean SQLite with snake_case schema
   All entity types processed: characters, items, spells, skills, stances,
   quests, factions, zones.

4. **Add `extract build` CLI command.**
   Reads `erenshor-{v}-raw.sqlite`, writes `erenshor-{v}.sqlite`.
   Standalone: does not require a fresh `extract export`.
   Add `build` to `extract full` pipeline.

5. **Delete registry, enrichers, domain enriched data.**
   `registry/`, `application/enrichers/`, `domain/enriched_data/` — all
   deleted. Their tests deleted too. No transitional compatibility shim.

6. **Rewrite wiki pipeline to read from clean DB.**
   Remove `RegistryResolver` from `wiki.py`. Remove enricher instantiation
   from `entities.py`. Delete `_deduplicate_characters()`. Simplify
   repository queries (no COALESCE, no exclusion filters). All name/page
   resolution becomes direct attribute access on clean DB rows.

7. **Rewrite all 23 sheets SQL queries.**
   snake_case column names throughout. Remove COALESCE. Remove SimPlayer/
   exclusion WHERE clauses. Fix `?marker=` → `?sel=marker:`. Use
   `display_name` where appropriate.

8. **Update golden files for intentional bug fixes.**
   Update golden rows for Braxonian Planar Guards (`is_unique` fix),
   SimPlayer rows (removed), excluded entity rows (removed). Document each.

9. **Run regression tests.** All golden diffs should show only the
   intentional changes from step 8. Zero unexpected diffs.

**Done when**: Regression tests pass with only documented intentional diffs.
The registry does not exist. The enrichers do not exist. All consumers read
the clean DB.

### Phase 2: C# rewrite (Layer 1 → JSON)

**Goal**: C# produces JSON files. `extract build` reads JSON instead of raw
SQLite. The clean DB and all downstream output is identical to Phase 1.

Steps:
1. Write C# JSON exporters (one per entity type, replacing Listeners).
2. Write plain C# export data contracts (no ORM attributes).
3. Update `AssetScanner.cs` and `ExportBatch.cs` to use exporters.
4. Delete C# `Database/` record types and `Repository.cs`.
5. Update `extract export` to write JSON to `variants/{v}/exported-data/`.
6. Update `extract build` to read from JSON files (Pydantic validation).
7. Run Unity batch mode export → `extract build` → regression tests.

**Done when**: JSON → clean DB → all outputs match Phase 1 golden baseline
exactly (bit-for-bit identical clean DB).

### Phase 3: Map and wiki→map links

**Goal**: Map uses display names and wiki page titles. Wiki pages link to
the map. All links are correct for renamed and ambiguous characters.

Steps:
1. Update `database.base.ts` spawn point query: add `display_name` and
   `wiki_page_name` columns.
2. Update `SpawnCharacter` type and all callers to use `display_name` for
   display and `wiki_page_name` for wiki link construction.
3. Update search providers (`enemy-provider.ts`, `npc-provider.ts`) to
   index by `display_name` instead of `npc_name`.
4. Update `WikiLink.svelte` to accept separate `label` and `wikiTitle` props.
5. Update all spawn point and search popups to pass both props.
6. Add `|maplink=` parameter to `character.jinja2` Jinja2 template.
7. Create `{{MapLink}}` MediaWiki template (encapsulates map base URL).
8. Update `{{Enemy}}` MediaWiki infobox to render map link row.
9. Update map golden baseline (`tests/golden/map/spawn-points.csv`).

**Done when**: Map shows correct display names; map→wiki links resolve to
correct wiki pages for all characters including renamed ones; wiki character
pages include working map links.

---

## 10. Components Inventory

### Phase 1: To be created

| Component | Purpose |
|-----------|---------|
| `src/erenshor/application/processor/build.py` | Top-level Layer 2 orchestrator |
| `src/erenshor/application/processor/mapping.py` | Loads and applies `mapping.json` |
| `src/erenshor/application/processor/characters.py` | Character filter, dedup, `is_unique` |
| `src/erenshor/application/processor/entities.py` | Generic processor for other entity types |
| `src/erenshor/application/processor/writer.py` | Writes clean SQLite (snake_case schema) |
| `extract build` CLI command | Added to `extract.py`; standalone, no re-export required |
| `golden capture` CLI command | Snapshots current output to `tests/golden/` |
| `tests/golden/wiki/*.wiki` | One file per wiki page title |
| `tests/golden/sheets/*.csv` | One CSV per sheet query (23 files) |
| `tests/golden/map/spawn-points.csv` | Map spawn-points query output |
| `tests/integration/test_golden.py` | Regression test: actual vs. golden |

### Phase 1: To be deleted

| Component | Lines |
|-----------|-------|
| `registry/` Python package (6 files) | ~800 |
| `application/enrichers/` (5 files) | ~400 |
| `domain/enriched_data/` (5 files) | ~150 |
| `_deduplicate_characters()` in `entities.py` | ~100 |
| `tests/unit/registry/` (3 test files) | ~300 |
| `tests/unit/application/services/test_character_enricher.py` | ~100 |
| `tests/unit/application/services/test_item_enricher.py` | ~100 |

### Phase 1: To be simplified

| Component | Change |
|-----------|--------|
| `extract.py` | Add `build` subcommand; rename raw DB output path |
| `wiki.py` | Remove `RegistryResolver`; wire to clean DB |
| `generators/pages/entities.py` | Remove enrichers, remove `_deduplicate_characters()` |
| `generators/sections/character.py` | Direct attribute access instead of resolver calls |
| All 11 Python repositories | Queries rewritten for snake_case clean DB schema |
| All 23 sheets SQL files | snake_case columns, no COALESCE, fix map URL format |

### Phase 2: To be created

| Component | Purpose |
|-----------|---------|
| C# JSON exporters (~29 files) | Replace Listeners; pure extraction to JSON |
| C# export data contracts (~30 files) | Plain serialisable classes, no ORM |
| Pydantic JSON models (~10 files) | Validate Layer 1 JSON output in `extract build` |

### Phase 2: To be deleted

| Component | Lines |
|-----------|-------|
| C# Listener files (29) | ~4,000 |
| C# `Database/` record types (~60) | ~1,900 |
| C# `Repository.cs` | ~50 |
| C# `IAssetScanListener.cs` | ~20 |

### Phase 3: To be created / updated

| Component | Change |
|-----------|--------|
| `database.base.ts` | Add `display_name`, `wiki_page_name` to spawn query |
| `SpawnCharacter` TypeScript type | Add `wikiTitle: string \| null` |
| `enemy-provider.ts`, `npc-provider.ts` | Index by `display_name` |
| `WikiLink.svelte` | Accept separate `label` and `wikiTitle` props |
| Spawn point and search popups | Pass both props |
| `character.jinja2` | Add `\|maplink=` parameter |
| `{{MapLink}}` MediaWiki template | Encapsulate map base URL |
| `{{Enemy}}` MediaWiki infobox | Add map link row |

---

## 11. Format and Naming Decisions

These decisions were made explicitly during planning and are not up for
re-evaluation without a documented reason.

### Layer 1 → Layer 2 transport format: JSON + Pydantic

**Decision**: JSON files out of C#, validated by Pydantic models in Python.

**Rationale**: XSD is a more mature schema standard than JSON Schema (which
remains in draft), but XSD's advantages (namespaces, mixed content, complex
inheritance) are irrelevant for flat record export. The real schema authority
is the Pydantic models in Layer 2 — defined once in Python with `strict=True`,
they catch all type and structure errors at ingest. `Newtonsoft.Json` is
already a project dependency; no new packages needed on either side.

XML + XSD would be the right choice if the data were naturally hierarchical
or if the schema needed to be published for external implementors. Neither
applies here.

### Clean DB column naming: snake_case

**Decision**: All columns in the clean DB use snake_case.

**Rationale**: The clean DB is authored entirely by Python. Python convention
(PEP 8) is snake_case. Using PascalCase "for consistency with the raw DB"
would carry forward a C#/Unity constraint that no longer applies. The cost
— updating 23 SQL files and TypeScript queries — is paid once and coincides
with other required changes to those files (removing COALESCE, adding
`display_name`), so there is no extra churn. The benefit is permanent:
`pascal_to_snake()` conversion is eliminated from all repositories.

### `extract build` is standalone

**Decision**: `extract build` reads from the existing raw SQLite and writes
the clean DB. It does not require a fresh `extract export`.

**Rationale**: The entire point of separating `export` from `build` is to
allow build logic to be changed and re-run in seconds rather than hours.
Build logic (mapping, dedup, rarity classification) will change far more
frequently than game data. Coupling `build` to `export` would negate this.

---

## 12. What Does Not Change

- `mapping.json` format
- `config.toml` structure (map URL can be added as a new optional field)
- The three-variant pipeline (main, playtest, demo)
- Jinja2 templates and field preservation system
- MediaWiki API client and deploy service
- Google Sheets API client and deploy service
- SvelteKit map app structure and components
- BepInEx mod pipeline
- All tests unrelated to the registry or enrichers
