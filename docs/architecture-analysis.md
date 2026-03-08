# Architecture Analysis: Data Pipeline Rewrite

## Purpose

This document defines the target architecture for the Erenshor data pipeline
and how to get there safely. It is the canonical specification for the
three-layer pipeline rewrite. `docs/PRD-data-pipeline-rewrite.md` is the
earlier problem statement that motivated this work; this document supersedes
it on all implementation decisions.

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

This is the architecture the codebase converges to.

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
| `RegistryResolver` class | Resolves stable_key → display name, page title, links | **Deleted.** `display_name`, `wiki_page_name`, `image_name` are columns on every clean DB entity. Wiki link objects are constructed directly from those columns — no runtime lookup service. |
| `registry/operations.py` | Builds registry from NPCName + mapping.json | **Deleted.** Logic moves to Layer 2 Python processor. |
| `registry/resolver.py` | Runtime lookup for wiki generators | **Deleted.** |
| `registry/schema.py` | SQLModel entity table | **Deleted.** |
| `application/enrichers/` | Augments Character/Item/etc. with related data via resolver lookups | **Deleted.** `EntityPageGenerator` assembles multi-entity data inline from direct repo calls. Enricher *classes* gone; enriched data *shapes* survive as local dataclasses. |
| `CharacterEnricher`, `ItemEnricher`, etc. | Per-entity enrichment service classes | **Deleted.** |
| `domain/enriched_data/` | Enrichment result DTOs | **Deleted.** Replaced by local dataclasses in `generators/pages/entities.py` assembled inline without resolver. |
| `SourceInfo` stable-key lists | Raw stable keys in `vendors`, `drops`, `quest_rewards`, etc. | **Replaced.** `SourceInfo` fields carry pre-built `WikiLink` objects (`CharacterLink`, `ItemLink`, `QuestLink`, etc.) populated via DB JOINs at query time. Section generators iterate link objects and call `str(link)` — no lookup at generation time. |
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
- **Simplify**: `generators/pages/entities.py` — no enricher classes, no
  deduplication. Instead: load entities from DB → assemble multi-entity data
  inline via direct repo calls → pass data packages to section generators →
  yield page. Multi-entity data (spawn infos, loot drops, spell links, source
  info) assembled as local dataclasses defined in `entities.py`.
- **Simplify**: section generators (`character.py`, `item.py`, `spell.py`,
  `skill.py`, `stance.py`) — no resolver, no enricher imports. All name/page
  resolution becomes direct attribute access on entity fields (`entity.display_name`,
  `entity.wiki_page_name`, `entity.image_name`). Cross-entity links (`ItemLink`,
  `AbilityLink`, `CharacterLink`, etc.) are pre-built at query time and passed
  in as data; section generators just call `str(link)`.
- **Simplify**: `infrastructure/database/repositories/` — all queries use
  snake_case clean DB schema. No COALESCE, no exclusion filters, no
  `pascal_to_snake`. Repositories JOIN related tables and return pre-built
  `WikiLink` objects where links are needed (e.g., spawn repo JOINs zones and
  populates `zone_display_name`/`zone_wiki_page_name` on `CharacterSpawnInfo`;
  item source queries return `CharacterLink`/`ItemLink`/`QuestLink` objects
  ready for section generators to render).
- **Keep unchanged**: `WikiLink` value objects (`ItemLink`, `AbilityLink`,
  `StandardLink`, `QuestLink`) — these are the link rendering layer. They are
  still constructed and rendered the same way; only the construction site moves
  from resolver methods to direct instantiation from entity columns.
- **Keep unchanged**: Jinja2 templates, field preservation, MediaWiki client,
  deploy service. Fetch service loses `registry_resolver` param; the one
  reverse-lookup (`get_stable_keys_for_page`) is replaced by an inline SQL
  UNION across entity tables queried by `wiki_page_name`.

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
4. Computes SHA-256 hashes of all captured files and writes three hash manifests:
   `tests/golden/wiki-hashes.json`, `tests/golden/sheets-hashes.json`,
   `tests/golden/map-hashes.json`

Golden files are committed to the repository so that CI can run regression
tests without local databases or prior capture runs. The initial commit is
large (2,436 wiki pages + 23 CSVs) but subsequent changes are small diffs.

### Comparison strategy

The regression test uses hash-based comparison for performance: it hashes
freshly generated output and compares against the stored manifests. On any
hash mismatch it reads the specific file to produce a human-readable diff.
The full files are kept on disk as the diff-readable reference.

The golden files ARE the expected output. If a change is intentional (a bug
fix), the golden files are updated in the same commit as the code change. The
commit message explains the intentional change. There is no whitelist of
"known diffs" in test code — every diff is either an intentional update to
golden or a regression to fix.

Row ordering must be deterministic: all SQL queries use explicit `ORDER BY`,
and wiki pages are sorted by title.

### What counts as a regression

- Any entity present in golden but missing from new output
- Any entity absent from golden but present in new output
- Any field value change (name, level, stat, coordinate, probability, etc.)
- Any spawn point missing or added
- Any wiki page title change
- Any loot drop, vendor item, spell, or faction relationship missing or added

### Automated regression test

```python
# tests/integration/test_golden.py — hash-based, no whitelist
def test_wiki_golden():
    hashes = load_hash_manifest("tests/golden/wiki-hashes.json")
    for filename, expected_hash in hashes.items():
        actual = hash_file(WIKI_GENERATED_DIR / filename)
        assert actual == expected_hash, diff(GOLDEN_WIKI_DIR / filename,
                                             WIKI_GENERATED_DIR / filename)

def test_sheets_golden(golden_sheets_engine):
    hashes = load_hash_manifest("tests/golden/sheets-hashes.json")
    for sheet_name, expected_hash in hashes.items():
        actual_csv = format_as_csv(formatter.format_sheet(sheet_name))
        assert sha256(actual_csv) == expected_hash, diff(...)

def test_map_golden():
    hashes = load_hash_manifest("tests/golden/map-hashes.json")
    actual_csv = run_spawn_points_query_as_csv(DB_PATH)
    assert sha256(actual_csv) == hashes["spawn-points.csv"], diff(...)
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

Steps (✓ = complete):

1. ✓ **Capture golden outputs** (before any code changes).
   Run `wiki generate`, then `golden capture` to snapshot all wiki pages,
   all sheet query results, and the map spawn-points query output.
   Committed to `tests/golden/`: 2,436 wiki pages, 23 sheet CSVs, 7,904
   map rows. Also fixed five bugs in the golden command and test harness
   (`None`→`""` for NULL, `GROUP_CONCAT(... ORDER BY ...)` aggregate
   syntax, atomic wiki capture, `pytest.skip` for missing golden dirs,
   `golden_sheets_engine` fixture rename, no KNOWN_DIFFS whitelist).

2. ✓ **Add `database_raw` config field.**
   Added `database_raw` to `VariantConfig` in `schema.py` and to
   `config.toml` for all three variants. `extract export` writes to
   `database_raw`; all consumers read from `database` (the clean DB).
   The raw path is an intermediate artifact, not a consumer-facing path.
   Also removed `doctor`, `extract full`, and `registry` CLI commands from
   the router, help text, `README.md`, `TROUBLESHOOTING.md`, and the
   `debugging` skill. Note: `cli/commands/registry.py` still exists on disk
   — it is removed as part of step 6.

3. ✓ **Update `extract export` to write to `database_raw`.**
   Pass `database_raw` to Unity as `dbPath` instead of `database`.

   **Bootstrap note**: The existing `variants/{v}/erenshor-{v}.sqlite` is
   the raw DB — it predates this separation and lives at the `database` path
   rather than `database_raw`. Before running `extract build` for the first
   time (without a fresh `extract export`), copy it manually:
   ```
   cp variants/main/erenshor-main.sqlite \
      variants/main/erenshor-main-raw.sqlite
   ```
   After the next `extract export` this is no longer needed — Unity will
   write directly to `database_raw`.

4. ✓ **Write the Layer 2 processor** (`src/erenshor/application/processor/`).
   - `build.py` — top-level orchestrator
   - `mapping.py` — loads and applies `mapping.json`
   - `characters.py` — filter, dedup, `is_unique` computation
   - `entities.py` — generic processor for other entity types
   - `writer.py` — writes clean SQLite with snake_case schema

   All entity types processed in dependency order: zones → factions →
   items → spells → skills → stances → quests → characters.

   The `character_deduplication` table is included in the clean DB schema,
   mapping each merged raw stable key to its canonical stable key. No
   current consumer reads it; it exists for diagnostics and future use.

   Deduplication identity: two characters are duplicates if all scalar
   fields, all type flags, and all relationship sets (spells, loot, vendor
   items, dialogs) match after mapping is applied. Spawn locations are NOT
   part of identity — they are merged into the canonical record.

   `is_unique` computation: count total spawn points per `display_name`
   group across all canonical characters. A character is unique if its
   group has exactly one spawn point in the world. This replaces the C#
   bug where grouping by `NPCName` misclassified renamed characters (e.g.,
   Braxonian Planar Guards).

5. **Add `extract build` CLI command.**
   Reads `database_raw`, writes `database`. Standalone: does not require
   a fresh `extract export`. Fails fast if `database_raw` does not exist,
   with a clear message pointing to `extract export` or the manual copy
   described in step 3. Also update `database_has_items` precondition to
   check `items` (snake_case) instead of `Items` — the clean DB uses
   snake_case table names throughout.

6. **Rewrite wiki pipeline and delete registry/enrichers in one sweep.**
   Steps 6–8 from the original plan are merged into a single commit because
   `RegistryResolver` is threaded through every section generator, not just
   the factory; there is no valid intermediate state where the factory is
   decoupled but the generators still use the resolver.

   **Prerequisites within this step (done first, as part of the same commit):**
   - Move `ItemKind` and `classify_item_kind` from `registry/item_classifier.py`
     to `src/erenshor/domain/entities/item_kind.py`. Five wiki generator files
     and one test import from `registry.item_classifier`; all import sites are
     updated. This unblocks deletion of the registry package.

   **Value objects and domain entities — carry pre-built links from DB JOINs:**

   The resolver's link methods (`item_link`, `ability_link`, `faction_link`,
   etc.) are removed along with the resolver. Their replacement is not a
   service but data: repositories JOIN related tables and populate link fields
   directly on value objects. Section generators receive pre-built `WikiLink`
   objects and call `str(link)` — no lookup at generation time.

   Specific changes:
   - `CharacterSpawnInfo`: add `zone_display_name: str` and
     `zone_wiki_page_name: str` (populated by JOIN in `spawn_points.py`).
   - `LootDropInfo`: add `item_display_name: str` and
     `item_wiki_page_name: str` (populated by JOIN in `loot_tables.py`).
   - `FactionModifier`: add `faction_display_name: str` and
     `faction_wiki_page_name: str | None` (populated by JOIN in
     `characters.py`).
   - `Character` entity: add `my_world_faction_display_name: str | None` and
     `my_world_faction_wiki_page_name: str | None` (populated by JOIN on load).
   - `Spell` entity: add `add_proc_link: AbilityLink | None` and
     `status_effect_link: AbilityLink | None` (pre-built from JOINs in
     `spells.py`).
   - `SourceInfo`: rewrite all fields from raw stable keys to pre-built link
     objects (`vendors: list[CharacterLink]`, `drops: list[tuple[CharacterLink,
     float]]`, `quest_rewards: list[QuestLink]`, `craft_sources: list[ItemLink]`,
     etc.). Constructed in `EntityPageGenerator` from direct repo calls.
   - `ProcInfo`: add `proc_link: AbilityLink` (replaces `stable_key` lookup
     in section generator).
   - `EnrichedCharacterData.spells`: change from `list[str]` (stable keys) to
     `list[AbilityLink]` (pre-built in `EntityPageGenerator`).
   - `EnrichedSpellData`: change `items_with_effect`, `teaching_items` from
     `list[str]` to `list[ItemLink]`; `used_by_characters` from `list[str]`
     to `list[CharacterLink]`; add `pet_to_summon: CharacterLink | None`,
     `status_effect: AbilityLink | None`, `add_proc: AbilityLink | None`.

   **Entity page generator (`generators/pages/entities.py`):**
   - Remove all enricher imports and instantiation.
   - Remove `_deduplicate_characters()` — deduplication is done in the
     processor; the clean DB contains only canonical characters.
   - Grouping by page title: replace `resolver.resolve_page_title(key)`
     with `entity.wiki_page_name` (a direct column on clean DB entities).
   - Assemble `EnrichedCharacterData`, `EnrichedItemData`, `EnrichedSpellData`,
     etc. **inline** via direct repo calls. These data shapes survive — only the
     enricher *classes* are deleted. The shapes move to local dataclasses
     defined at the top of `entities.py` (not in `domain/enriched_data/`).
   - All link objects in assembled data are pre-built from entity columns
     (`ItemLink(page_title=item.wiki_page_name, display_name=item.display_name,
     image_name=item.image_name)`). No resolver calls anywhere.

   **Section generators (character, item, spell, skill, stance, categories):**
   - Remove all `RegistryResolver` imports (runtime and TYPE_CHECKING).
   - Remove resolver from constructors: `__init__(self)` with no resolver param.
   - Replace all resolver calls with direct attribute access or pre-built link
     objects from the data passed in. `_format_*` methods iterate link objects
     and call `str(link)` — trivially simple.
   - `CategoryGenerator`: use `info.zone_wiki_page_name` from
     `CharacterSpawnInfo` (already populated by JOIN in spawn repo).

   **Wiki factory (`cli/commands/wiki.py`):**
   - Remove `RegistryResolver` import and instantiation from
     `_create_wiki_service()`. The factory no longer builds or passes a resolver.

   **Service layer (wiki_service.py, generate_service.py, fetch_service.py):**
   - Remove `registry_resolver` parameter from all three constructors and
     all call sites.
   - `fetch_service.py`: replace `resolver.get_stable_keys_for_page(page_title)`
     with an inline SQL UNION across entity tables (`characters`, `items`,
     `spells`, `skills`, `stances`, `zones`, `factions`, `quests`) querying
     `wiki_page_name = ?`. No new repository class needed — one place, inline.

   **Generator context (`generators/context.py`):**
   - Remove `resolver: RegistryResolver` field from `GeneratorContext`.

   **Helpers (`services/helpers.py`):**
   - Remove `RegistryResolver`. `group_entities_by_page_title` uses
     `entity.wiki_page_name` directly instead of resolver lookup.

   **Repositories (all 9 entity repos + `_case_utils.py`):**
   - Rewrite all query methods for snake_case clean DB schema: table names
     and column names lowercase. Remove `COALESCE`, SimPlayer/blank-name
     filters (clean DB already filtered). Remove `_row_to_xxx` + `pascal_to_snake`
     conversion — clean DB columns already match snake_case Pydantic field names,
     so `model_validate(dict(row))` works directly.
   - Delete `_case_utils.py` (no longer needed by any consumer).
   - Source/cross-entity query methods (vendors, droppers, spell users, etc.)
     return pre-built `WikiLink` objects via JOINs on `display_name` and
     `wiki_page_name` columns — not raw stable keys.

   **images.py and image_processor.py:**
   - Remove `RegistryResolver` from `cli/commands/images.py` and
     `application/services/image_processor.py`. The processor's
     `discover_images()` currently queries PascalCase raw DB columns and uses
     the resolver for `entity_name` and `image_name`. Rewrite to query the
     clean DB (`items`, `spells`, `skills` tables, snake_case columns) and read
     `wiki_page_name` and `image_name` directly — no resolver needed.

   **Delete entirely:**
   - `src/erenshor/registry/` (5 remaining files after `item_classifier.py` moved)
   - `src/erenshor/application/enrichers/` (5 files)
   - `src/erenshor/domain/enriched_data/` (5 files)
   - `src/erenshor/cli/commands/registry.py`
   - `src/erenshor/infrastructure/database/repositories/_case_utils.py`
   - `tests/unit/registry/` (3 test files + `conftest.py`)
   - `tests/unit/application/services/test_character_enricher.py`
   - `tests/unit/application/services/test_item_enricher.py`

   **Update tests:**
   - `tests/unit/application/generators/conftest.py`: remove `mock_resolver`
     fixture; generators no longer accept a resolver.
   - `tests/unit/application/services/test_wiki_service.py`: remove
     `mock_registry_resolver` fixture and its usage.
   - Generator tests that import `ItemKind` from `registry.item_classifier`:
     update import path to `domain.entities.item_kind`.

   **Commit message**: `refactor(wiki): rewrite pipeline for clean DB, delete registry and enrichers`

7. **Rewrite all 23 sheets SQL queries, `image_processor.py`, and scripts.**
   snake_case column names throughout. Remove COALESCE. Remove SimPlayer/
   exclusion WHERE clauses. Fix `?marker=` → `?sel=marker:`. Use
   `display_name` where appropriate. Update `scripts/validate_database.py`,
   `scripts/compare_variants.py`, and `scripts/zone_discrepancy_report.py`
   for snake_case clean DB schema. All concerns ship in one commit since
   they share the same schema change.

   Note: `image_processor.py` SQL is updated as part of step 6 (where the
   `RegistryResolver` dependency is also removed). Step 7 covers only the
   sheets SQL and scripts.

8. **Update golden files and run regression tests.**
    After steps 5–7 are committed, run `extract build` locally to populate
    the clean DB, then run `wiki generate` and all sheet queries and compare
    against the golden baselines. Before updating any golden file, evaluate
    every diff: unexpected diffs indicate an implementation bug and must be
    fixed; only intentional changes (IsUnique fix for Braxonian Planar
    Guards, SimPlayer rows removed, excluded entity rows removed) are
    applied to the golden files. Commit updated golden files with an
    explanation of each intentional change. Run regression tests — zero
    unexpected diffs.

**Done when**: Regression tests pass. The registry does not exist. The
enrichers do not exist. All consumers read the clean DB. `extract full` is
deleted (replaced by running `download`, `rip`, `export`, and `build`
individually).

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

| Component | Lines | Notes |
|-----------|-------|-------|
| `registry/` Python package (5 files) | ~750 | `item_classifier.py` moved, not deleted |
| `application/enrichers/` (5 files) | ~400 | |
| `domain/enriched_data/` (5 files) | ~150 | |
| `_deduplicate_characters()` in `entities.py` | ~100 | |
| `cli/commands/registry.py` | ~200 | Registry CLI command group |
| `cli/commands/extract.py` `full` command | ~70 | Replaced by running steps individually |
| Registry health section in `doctor` command | ~40 | `main.py` lines 387–424 |
| `infrastructure/database/repositories/_case_utils.py` | ~50 | No longer needed after snake_case clean DB |
| `tests/unit/registry/` (3 test files + conftest) | ~300 | |
| `tests/unit/application/services/test_character_enricher.py` | ~100 | |
| `tests/unit/application/services/test_item_enricher.py` | ~100 | |

### Phase 1: To be created

| Component | Purpose |
|-----------|---------|
| `domain/entities/item_kind.py` | `ItemKind` + `classify_item_kind` moved from `registry/item_classifier.py` |

### Phase 1: To be simplified / updated

| Component | Change |
|-----------|--------|
| `extract.py` | Add `build` subcommand; update `export` to use `database_raw` |
| `schema.py` `VariantConfig` | Add `database_raw` field and `resolved_database_raw()` method |
| `config.toml` | Add `database_raw` for all three variants |
| `wiki.py` | Remove `RegistryResolver` from `_create_wiki_service()` |
| `generators/context.py` | Remove `resolver` field |
| `generators/pages/entities.py` | Remove enrichers, remove `_deduplicate_characters()`; assemble enriched data inline via direct repo calls; group by `entity.wiki_page_name`; define local enriched dataclasses |
| `generators/sections/character.py` | Remove resolver; use `entity.display_name`, `entity.wiki_page_name`, `entity.image_name`; use pre-built link objects from spawn/loot/spell data |
| `generators/sections/item.py` | Remove resolver; use pre-built `WikiLink` objects from `SourceInfo`, `ProcInfo`; import `ItemKind` from `domain.entities.item_kind` |
| `generators/sections/spell.py` | Remove resolver; use entity columns and pre-built link objects from `EnrichedSpellData` |
| `generators/sections/skill.py` | Remove resolver TYPE_CHECKING import |
| `generators/sections/stance.py` | Remove resolver; use pre-built `AbilityLink` list for activated_by skills |
| `generators/sections/categories.py` | Remove resolver; use `info.zone_wiki_page_name` from `CharacterSpawnInfo`; import `ItemKind` from `domain.entities.item_kind` |
| `generators/pages/armor_overview.py` | Import `classify_item_kind` from `domain.entities.item_kind` |
| `generators/pages/weapons_overview.py` | Import `classify_item_kind` from `domain.entities.item_kind` |
| `generators/item_type_display.py` | Import `ItemKind` from `domain.entities.item_kind` |
| `services/wiki_service.py` | Remove `registry_resolver` parameter |
| `services/generate_service.py` | Remove `registry_resolver` parameter |
| `services/fetch_service.py` | Remove `registry_resolver` parameter; replace `get_stable_keys_for_page` with inline SQL UNION across entity tables by `wiki_page_name` |
| `services/helpers.py` | Remove `RegistryResolver`; use `entity.wiki_page_name` directly |
| `cli/commands/images.py` | Remove `RegistryResolver` |
| `application/services/image_processor.py` | Remove resolver; query clean DB snake_case columns directly |
| `preconditions/checks/database.py` | Update `database_has_items` to check `items` (snake_case) |
| `domain/value_objects/spawn.py` `CharacterSpawnInfo` | Add `zone_display_name: str`, `zone_wiki_page_name: str` |
| `domain/value_objects/loot.py` `LootDropInfo` | Add `item_display_name: str`, `item_wiki_page_name: str` |
| `domain/value_objects/proc_info.py` `ProcInfo` | Add `proc_link: AbilityLink` (replaces stable_key lookup) |
| `domain/value_objects/source_info.py` `SourceInfo` | Rewrite all fields from raw stable keys to pre-built `WikiLink` objects |
| `domain/entities/character.py` | Add `my_world_faction_display_name: str \| None`, `my_world_faction_wiki_page_name: str \| None` |
| `domain/entities/spell.py` | Add `add_proc_link: AbilityLink \| None`, `status_effect_link: AbilityLink \| None` |
| `infrastructure/database/repositories/characters.py` | JOIN factions for faction display/wiki fields; JOIN for `FactionModifier` display names |
| `infrastructure/database/repositories/spawn_points.py` | JOIN zones, populate `zone_display_name`, `zone_wiki_page_name` on `CharacterSpawnInfo` |
| `infrastructure/database/repositories/loot_tables.py` | JOIN items, populate `item_display_name`, `item_wiki_page_name` on `LootDropInfo` |
| `infrastructure/database/repositories/spells.py` | JOIN spells for `add_proc_link`, `status_effect_link` pre-built on `Spell` entity |
| `infrastructure/database/repositories/items.py` | Source queries return pre-built `WikiLink` objects via JOINs on display/wiki columns |
| All other entity repositories | Queries rewritten for snake_case clean DB; remove `pascal_to_snake` |
| All 23 sheets SQL files | snake_case columns, no COALESCE, fix map URL format |
| `scripts/validate_database.py` | Update SQL for snake_case clean DB |
| `scripts/compare_variants.py` | Update SQL for snake_case clean DB |
| `scripts/zone_discrepancy_report.py` | Update SQL for snake_case clean DB |

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
- The three-variant pipeline (main, playtest, demo)
- Jinja2 templates and field preservation system
- MediaWiki API client and deploy service
- Google Sheets API client and deploy service
- SvelteKit map app structure and components (Phase 3 updates TypeScript only)
- BepInEx mod pipeline

## 13. CI and Testing

### Golden files are committed to the repository

The golden files (`tests/golden/`) must be committed before the pipeline
rewrite begins. This is not primarily about enabling CI — it is about
preservation. Once the registry and enrichers are deleted, the pre-rewrite
output can never be regenerated. The golden files are the only record of what
the pipeline produced before the rewrite, and they must exist in the
repository before that code is removed.

A secondary benefit: any developer with a local database can run the
regression tests immediately without needing to re-run `golden capture`.

### Golden files are not a permanent freeze

The golden files will be updated deliberately throughout the rewrite as
intentional output changes are made (bug fixes, name corrections, SimPlayer
removal). Each update is a commit that shows exactly which outputs changed
and why. The files are a living record of expected output, not a snapshot
of the original buggy state.

### CI does not run golden regression tests

The golden tests require a local variant database, which is not available
in CI. They will always skip in CI. This is an accepted limitation — the
golden tests are a local developer tool for the duration of the rewrite.
CI continues to run unit tests and the existing integration tests that use
committed fixture databases.
