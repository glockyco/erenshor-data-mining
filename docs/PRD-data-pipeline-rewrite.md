# PRD: Data Pipeline Rewrite

## Problem Statement

The current data pipeline exports game data from Unity directly into SQLite,
mixing raw extraction with data cleaning in a single step. This creates
cascading problems:

1. **No centralized data cleaning.** Deduplication, name normalization, and
   entity exclusion happen ad-hoc in each output layer (wiki, sheets, maps)
   rather than once in a shared processing step.

2. **Inconsistent outputs.** Wiki deduplicates characters in-memory during page
   generation. Sheets and maps do not deduplicate at all. Display name
   resolution uses mapping.json for wiki but not for sheets or maps.

3. **Messy source data.** The game contains SimPlayer prefab templates,
   duplicate spawn instances of the same NPC, name conflicts (ObjectName vs
   NPCName), and null references. The current pipeline handles these
   inconsistently across outputs.

4. **Monolithic export step.** Unity exports directly to SQLite, combining
   extraction and cleaning. There is no intermediate representation to inspect,
   debug, or version. Re-running the pipeline requires re-launching Unity batch
   mode even if only the cleaning logic changed.

5. **Logic duplication.** Null handling is implemented three different ways
   (C# ternary operators, SQL COALESCE, Python `or ""`). Source filtering and
   deduplication logic is duplicated across wiki generators.

6. **No clear module boundaries.** Business logic leaks into presentation
   layers. The wiki section generator `item.py` is 1,228 lines with vendor
   filtering, deduplication, and sorting mixed into template rendering code.
   Enrichers duplicate work that should happen once during data processing.

7. **mapping.json as a band-aid.** 645 rules and 186 exclusions exist in
   mapping.json to compensate for data quality issues that should be resolved
   during processing. This file is only consumed by the wiki layer, leaving
   sheets and maps with unresolved data.

## Goals

1. Separate raw data extraction from data cleaning into distinct pipeline
   stages with a well-defined intermediate representation (JSON).

2. Produce a single clean, fully normalized SQLite database that all output
   layers (wiki, sheets, maps) can consume without additional cleaning logic.

3. Eliminate duplicate cleaning logic across output layers. Each output should
   only contain formatting and presentation code.

4. Make the processing pipeline independently runnable. Changing cleaning logic
   should not require re-exporting from Unity.

5. Ensure all data in the core database is clean: no duplicates, no excluded
   entities, no unresolved names, no broken references. If an entity is in the
   database, it is valid and ready for use.

## Non-Goals

- Changing the game data itself or influencing what Unity exports.
- Adding new entity types or data fields beyond what currently exists.
- Modifying the output formats (wiki templates, sheets structure, map UI).
- Optimizing Unity batch mode performance.
- Denormalizing data in the core database for query performance. The core
  database is normalized. If denormalization is needed for a specific output,
  that output handles it.

## Architecture

### Three-Layer Pipeline

```
Layer 1: Unity --> Raw JSON Export
  - Export ALL entities as-is from Unity
  - Zero processing, zero filtering, zero cleaning
  - Hierarchical structure preserved (nested arrays for relationships)
  - Includes SimPlayer prefabs, duplicates, excluded entities, everything

Layer 2: JSON --> Clean Normalized SQLite
  - Validate JSON with Pydantic models
  - Apply mapping.json (name overrides, image names)
  - Filter excluded entities (do not insert into DB)
  - Remove references to excluded entities (cascade cleanup)
  - Delete SimPlayer prefabs
  - Deduplicate truly identical entities (merge spawn locations)
  - Insert into fully normalized schema (junction tables)
  - Record deduplication metadata

Layer 3: SQLite --> Output Formats (Wiki / Sheets / Maps)
  - Read clean data via JOINs and aggregation
  - Pure formatting and presentation logic
  - No mapping.json, no deduplication, no exclusion filtering
```

### Data Flow Diagram

```
Unity ScriptableObjects
        |
        v
[JSON Exporter (C#)]  -- Layer 1
        |
        v
  exported-data/
  +-- characters.json     (all 1,269 characters)
  +-- items.json
  +-- spells.json
  +-- quests.json
  +-- zones.json
  +-- ...
        |
        v
[Processing Pipeline (Python)]  -- Layer 2
  1. Load & validate (Pydantic)
  2. Apply mapping.json overrides
  3. Filter excluded entities
  4. Remove references to excluded entities
  5. Delete SimPlayer prefabs
  6. Deduplicate identical entities
  7. Insert into normalized schema
  8. Record deduplication metadata
  9. VACUUM & ANALYZE
        |
        v
  erenshor-{variant}.sqlite
  (clean, normalized, no duplicates, no excluded entities)
        |
        +----> Wiki generators (formatting only)
        +----> Sheets queries (simple SELECTs with JOINs)
        +----> Maps data export (simple reads)
```

## Layer 1: Unity JSON Export

### Responsibility

Export every entity from Unity ScriptableObjects as raw JSON. No filtering, no
cleaning, no deduplication. The JSON files are a faithful dump of the game data.

### JSON Structure

Each entity type is a single JSON file containing an array of objects.
Relationships are preserved as nested arrays using StableKeys for references.

Example `characters.json`:

```json
[
  {
    "stable_key": "character:a bank rift",
    "object_name": "A Bank Rift",
    "npc_name": "Summoned: Pocket Bank",
    "level": 25,
    "health": 5000,
    "is_prefab": true,
    "is_common": 0,
    "is_rare": 1,
    "is_unique": 0,
    "vendor_inventories": [
      {
        "item_stable_key": "item:potion of healing",
        "quantity": 1,
        "cost": 10
      }
    ],
    "dialog_choices": [
      {
        "quest_stable_key": "quest:repair the anvil",
        "dialog_text": "About that anvil..."
      }
    ],
    "spells": ["spell:fireball", "spell:heal"],
    "loot_drops": [
      {
        "item_stable_key": "item:ring of decay",
        "drop_probability": 0.8
      }
    ],
    "spawn_locations": [
      {
        "zone_stable_key": "zone:reliquary",
        "position_x": 279.22,
        "position_y": 1.44,
        "position_z": 358.33
      }
    ]
  }
]
```

### Key Principles

- Export ALL entities including SimPlayer prefabs, disabled variants, and
  entities that will later be excluded.
- Preserve null values. If a field is null in Unity, export it as null in JSON.
- Use StableKeys for all cross-entity references (not Unity instance IDs).
- Nested arrays for one-to-many relationships (vendors, dialogs, spawns).
- Indent JSON for human readability and version control diffing.

### Output Location

```
variants/{variant}/exported-data/
+-- characters.json
+-- items.json
+-- spells.json
+-- quests.json
+-- zones.json
+-- skills.json
+-- stances.json
+-- ...
```

## Layer 2: Processing Pipeline

### Responsibility

Transform raw JSON exports into a clean, fully normalized SQLite database.
All data cleaning, deduplication, exclusion, and reference validation happens
in this layer. The resulting database contains only valid, unique, properly
named entities with intact referential integrity.

### Processing Steps (Ordered)

Processing order matters because of foreign key dependencies between entity
types (e.g., characters reference items, quests reference items).

For each entity type, in dependency order:

1. **Load & Validate.** Read JSON file. Validate every record against a
   Pydantic model. Fail loudly on validation errors.

2. **Apply Mapping.** For entities with a mapping.json rule: override
   `npc_name` / `item_name` / etc. with the mapped `display_name`. Set
   `wiki_page_name` and `image_name` from the rule. For entities without a
   rule: copy the entity's natural name to `wiki_page_name` and `image_name`.

3. **Filter Excluded.** Remove entities where mapping.json sets
   `wiki_page_name` to null. These entities do not enter the database at all.

4. **Entity-Specific Cleaning.** For characters: remove all SimPlayer prefabs.
   Other entity types may have their own cleaning rules as needed.

5. **Remove Invalid References.** After earlier entity types are inserted, scan
   remaining entities for references to excluded/removed entities. Remove those
   references (e.g., a vendor entry selling an excluded item, a dialog choice
   referencing an excluded quest).

6. **Deduplicate.** Identify groups of truly identical entities (differing only
   in spawn locations and object names). Merge spawn locations into a single
   canonical entity. Record which raw entities were merged in a deduplication
   metadata table.

7. **Insert.** Write the canonical entity to the main table. Write all
   relationships to junction tables.

After all entity types are processed:

8. **Optimize.** Run VACUUM and ANALYZE on the database.

### Entity Processing Order

Entities must be processed in foreign key dependency order so that
`remove_invalid_references` can check which entities exist in the database.

1. Zones (no dependencies)
2. Items (no dependencies)
3. Spells (may reference items via proc effects)
4. Skills (may reference spells)
5. Stances (may reference skills)
6. Quests (reference items as rewards/requirements)
7. Characters (reference items, spells, quests, zones)

### Deduplication Rules

Two entities are duplicates if and only if they are identical across ALL fields
except:

- `object_name` (Unity asset name; irrelevant for identity)
- `spawn_locations` (merged into canonical entity)

Specifically for characters, all of the following must be identical:

- `npc_name` (after mapping applied)
- `level`, `health`, and all stat fields
- `is_prefab`, `is_common`, `is_rare`, `is_unique`
- Vendor inventories (compared as sets, order-independent)
- Dialog choices (compared as sets, order-independent)
- Spells (compared as sets)
- Loot drops (compared as sets)
- All other gameplay-relevant fields

If any of these differ, the entities are NOT duplicates and both remain in the
database as separate records.

When choosing which entity becomes the canonical record:

- Prefer the prefab (`is_prefab = true`) if one exists in the group.
- Otherwise, pick any entity in the group (arbitrary).
- The chosen entity's `object_name` is stored in the characters table.
- All merged entities are recorded in `character_deduplication` with their
  original `stable_key` and `object_name`.

### mapping.json Behavior

mapping.json is a processing-time artifact. It is consumed during Layer 2 and
its rules are NOT stored in the database. Only the resulting mapped values are
persisted.

Each rule maps a StableKey to overrides:

```json
{
  "rules": {
    "character:a bank rift": {
      "display_name": "Summoned: Pocket Bank",
      "wiki_page_name": null,
      "image_name": "Summoned: Pocket Bank"
    }
  }
}
```

- `display_name`: Overrides the entity's name in the DB (`npc_name` column for
  characters, `item_name` for items, etc.).
- `wiki_page_name`: Sets the `wiki_page_name` column. If null, the entity is
  excluded from the database entirely.
- `image_name`: Sets the `image_name` column.

Entities without mapping rules use their natural game name for all three
columns.

### Output

```
variants/{variant}/erenshor-{variant}.sqlite
```

A single SQLite file per variant containing clean, normalized data ready for
all output layers.

## Database Schema

### Design Principles

1. **Fully normalized.** All many-to-many and one-to-many relationships use
   junction tables. No JSON arrays stored in columns.
2. **Clean data only.** No excluded entities. No duplicates. No SimPlayers.
   No broken foreign key references.
3. **CASCADE deletes.** Junction tables use `ON DELETE CASCADE` so removing an
   entity automatically removes all its relationships.
4. **Mapped names.** The `npc_name` / `item_name` / etc. columns contain the
   final display name (after mapping.json is applied), not the raw game name.

### Core Tables

Each entity type has a main table with scalar fields plus one or more junction
tables for relationships.

**Characters:**
- `characters` - Main table (stable_key, object_name, npc_name,
  wiki_page_name, image_name, level, health, stats, flags)
- `character_spawns` - Spawn locations (zone, position)
- `character_vendors` - Items sold (item reference, quantity, cost)
- `character_dialogs` - Dialog choices (quest reference, text)
- `character_spells` - Spells known (spell reference)
- `character_loot` - Loot drops (item reference, probability)

**Items:**
- `items` - Main table (stable_key, item_name, wiki_page_name, image_name,
  type, quality, stats)
- Junction tables for item-specific relationships as needed.

**Spells:**
- `spells` - Main table
- `spell_procs` - Proc chains (spell-to-spell references)

**Quests:**
- `quests` - Main table
- `quest_rewards` - Item rewards (item reference, quantity)
- `quest_requirements` - Required items (item reference, quantity)

**Zones:**
- `zones` - Main table

**Skills, Stances, and other entity types follow the same pattern.**

### Deduplication Metadata Tables

One deduplication table per entity type:

- `character_deduplication` (canonical_stable_key, merged_stable_key,
  merged_object_name)
- `item_deduplication` (canonical_stable_key, merged_stable_key,
  merged_object_name)
- etc.

These record which raw entities were merged into each canonical entity during
Layer 2 processing. Useful for debugging and auditing.

## Layer 3: Output Simplification

### Responsibility

Output layers (wiki, sheets, maps) read from the clean database and produce
formatted output. They contain only presentation logic. No deduplication, no
exclusion filtering, no mapping.json lookups, no name resolution.

### Wiki Changes

- Delete all enrichers (`application/enrichers/`). Their logic is now in
  Layer 2 processors or unnecessary because the database is already clean.
- Remove in-memory character deduplication from `pages/entities.py`.
- Remove source filtering from section generators (`item.py`).
- Simplify repository queries to simple SELECTs with JOINs.
- Keep field preservation system (wiki-specific requirement for preserving
  manual edits during regeneration).

### Sheets Changes

- Remove COALESCE wrappers (no null values in clean DB).
- Remove DISTINCT aggregations (no duplicates in clean DB).
- Remove WHERE clauses filtering blanks/SimPlayers.
- Simple SELECT with JOINs on junction tables.

### Maps Changes

- Remove any data cleaning from TypeScript/SvelteKit code.
- Read clean data directly from SQLite.

## CLI Commands

### Updated Command Structure

```bash
# Layer 1: Export raw JSON from Unity
uv run erenshor extract export

# Layer 2: Process JSON into clean SQLite
uv run erenshor extract build

# Layer 3: Deploy to outputs
uv run erenshor wiki deploy
uv run erenshor sheets deploy

# Variant support
uv run erenshor --variant playtest extract export
uv run erenshor --variant playtest extract build
```

The key change is splitting the current `extract export` (which does
Unity-to-SQLite in one step) into two commands: `extract export`
(Unity-to-JSON) and `extract build` (JSON-to-SQLite). This allows re-running
the build step without re-launching Unity.

## Validation Strategy

The migration is validated by comparing outputs before and after the rewrite.

1. **Before rewrite:** Generate wiki pages and sheets from the current
   pipeline. Save these as reference outputs.

2. **After rewrite:** Generate wiki pages and sheets from the new pipeline.
   Compare with reference outputs.

3. **Acceptable differences:** Display name changes where mapping.json was
   previously not applied (sheets, maps). Removal of duplicate entries that
   were previously included. These are improvements, not regressions.

4. **Unacceptable differences:** Missing entities that should be present.
   Incorrect stats, levels, or other data fields. Broken relationships
   (character selling items they shouldn't, quests missing rewards).

## Migration Strategy

Big bang. The current pipeline code is replaced entirely. No incremental
migration, no backward compatibility, no legacy fallbacks.

### What Gets Deleted

- Unity SQLite export code (Listeners, Database utilities)
- Python enrichers (`application/enrichers/`)
- In-memory deduplication in wiki generators
- Source filtering in section generators
- Complex COALESCE/DISTINCT patterns in sheets queries
- Any data cleaning in maps TypeScript code

### What Gets Created

- Unity JSON exporter (C#)
- Pydantic validation models
- Processing pipeline (loaders, processors, build command)
- Normalized database schema (`schema.sql`)
- Updated CLI commands

### What Gets Modified

- Wiki generators (simplified to pure formatting)
- Sheets queries (simplified to simple JOINs)
- Maps data loading (simplified to simple reads)
- CLI entry points (new `build` command)

## Risks

1. **Deduplication too aggressive.** Merging entities that appear identical but
   serve different gameplay purposes. Mitigation: strict equality check across
   all fields. Start conservative; refine the logic based on output comparison.

2. **Deduplication too conservative.** Not merging enough because minor field
   differences prevent deduplication. Mitigation: compare outputs and adjust
   which fields are included in the deduplication key.

3. **Missing entity types.** The current pipeline handles entity types that may
   not be covered in this PRD. Mitigation: audit the current C# Listener
   classes to identify all entity types before implementation.

4. **Broken wiki field preservation.** The field preservation system depends on
   specific template field names. Schema changes might break the matching.
   Mitigation: preserve the field preservation system as-is and test thoroughly.

5. **mapping.json incompleteness.** Entities that need mapping rules but do not
   have them will use their raw game names. This may produce wiki pages with
   unexpected titles. Mitigation: log all unmapped entities during build and
   review the list.

## Open Questions

1. What is the complete list of entity types exported from Unity? The current
   C# Listeners should be audited to ensure all types are covered in the JSON
   export and processing pipeline.

2. Are there entity types beyond characters that need deduplication? Items,
   spells, quests?

3. Should the processing pipeline detect and warn about unmapped entities that
   might need mapping.json rules?

4. Are there cross-entity deduplication scenarios? For example, two characters
   that are identical except one has an extra spell - should this be flagged
   for manual review?

5. What fields beyond the ones discussed (npc_name, level, health, vendors,
   dialogs, spells, loot) should be included in the character deduplication
   key? A complete field audit is needed.
