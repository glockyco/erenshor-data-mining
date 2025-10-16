# Erenshor Project: Functional Requirements Analysis

## Overview

Erenshor is a data mining and publishing pipeline for a single-player MMORPG called Erenshor. It extracts game data from Unity game files, stores it in SQLite, and publishes it to a MediaWiki instance and Google Sheets. The system is designed to automate the entire workflow from game download to wiki page updates.

**Key Characteristic**: This is a 100% automated pipeline requiring zero manual wiki editing—content is generated from database queries and published autonomously.

---

## Core User Workflows

### Workflow 1: Full Pipeline Update
**What the user needs to accomplish**: Keep all game data synchronized across all destination systems (wiki + Google Sheets).

**Steps**:
1. Check if game has been updated on Steam
2. Download game files if updated
3. Extract Unity assets (produces 2021.3.45f2 project)
4. Export all game entities to SQLite database
5. Deploy database to wiki working directory
6. Generate and publish wiki pages
7. Deploy data to Google Sheets

**Trigger**: Manual (`erenshor update`)

**Frequency**: After game patches

---

### Workflow 2: Generate and Update Wiki Content
**What the user needs to accomplish**: Convert current database state to wiki markup and push updates.

**Steps**:
1. Fetch current wiki page content (cache locally)
2. Generate new wiki markup from database
3. Detect what changed
4. Upload modified pages to wiki (with edit summaries)
5. Track upload status

**Variations**:
- Full update: all entity types (items, characters, abilities, fishing, overviews)
- Partial update: specific entity types only
- Dry-run: preview without uploading
- Validate-only: check for errors without generating
- Filter: update specific entities by name or ID

---

### Workflow 3: Compare Local and Wiki Data
**What the user needs to accomplish**: Understand what would change before uploading.

**Steps**:
1. Fetch pages from wiki (cache)
2. Generate new markup from database
3. Show diff for each page
4. Show summary statistics
5. Allow filtering by entity type or name

---

### Workflow 4: Image Processing and Upload
**What the user needs to accomplish**: Extract game icons, resize/format them, and publish to wiki.

**Steps**:
1. Extract icon filenames from database
2. Locate PNG files in Unity texture assets
3. Resize to 150x150, add borders for spells/skills
4. Save processed images
5. Compare with cached wiki images
6. Upload new/changed images to wiki
7. Create filename redirects for compatibility

---

### Workflow 5: Google Sheets Deployment
**What the user needs to accomplish**: Publish game data to multiple Google Sheets for reference/analysis.

**Available sheets** (21 total):
- Items, Weapons, Armor, Auras, Consumables
- Characters, Spells, Skills, Abilities
- Drop Chances, Spawn Points, Fishing, Mining
- Quests, Books, Factions, Classes, Ascensions
- Item Bags, Treasure Locations, Wishing Wells, Achievement Triggers, Teleports
- Character Dialogs

**Data flow**: SQL query → execute on database → format as rows → publish to sheet

---

### Workflow 6: Multi-Variant Support
**What the user needs to accomplish**: Maintain separate data for main game, playtest, and demo.

**Variants**:
- **main**: Production (App ID 2382520)
- **playtest**: Beta/Alpha (App ID 3090030, optional)
- **demo**: Free demo (App ID 2522260, optional)

**Independence**: Each variant has its own:
- Steam download directory
- Unity project
- SQLite database
- Wiki database copy
- Image output
- Logs

**Workflow**: Can run full pipeline for all variants or specific variant

---

## Data Pipeline Stages

### Stage 1: Extraction (Source → SQLite)

**Sources**:
- Steam Game Files (downloaded via SteamCMD)
- Unity Project Assets (extracted by AssetRipper)

**Process**:
1. SteamCMD downloads game files from Steam
2. AssetRipper extracts Unity project (produces readable asset files)
3. Custom Unity Editor scripts scan assets and extract data
4. Export system writes data to SQLite database

**Entity Types Extracted** (30+):
- **Combat Entities**: Characters, Spells, Skills, Items
- **Game Systems**: Spawn Points, Loot Drops, Quests, Factions
- **Environmental**: Zones, Locations (Fishing, Mining, Treasure, Wishing Wells)
- **Mechanics**: Ascensions, Classes, Abilities, Relationships
- **Special**: Books, NPCs, Dialogs, Vendors, Pets

**Output**: Normalized SQLite database with 20,600+ junction table rows

---

### Stage 2: Transformation (Database → Wiki Content)

**Input**: SQLite database

**Process**:
1. Query database for entity type
2. Fetch all related data (stats, relationships, loot, vendors, etc.)
3. Build template context (Pydantic model)
4. Render Jinja2 template with context
5. Normalize wikitext (clean formatting)
6. Create GeneratedContent with rendered blocks

**Generators** (one per entity type):
- `ItemGenerator` → item infobox + stat tables
- `CharacterGenerator` → enemy infobox + stats/loot/spawn info
- `AbilityGenerator` → spell/skill infobox
- `FishingGenerator` → fishing zone table
- `OverviewGenerator` → weapon/armor comparison tables

**Key Features**:
- Streaming generation (yield one entity at a time)
- Link resolution (name → wiki page title)
- Display name overrides (registry)
- Image name mapping (database name → wiki filename)
- Multi-entity page detection (skip if multiple DBobjects → one page)

---

### Stage 3: Publishing (Content → Destinations)

#### Destination 3a: MediaWiki

**Process**:
1. Setup wiki environment (registry, storage, auth)
2. Load registry (entity → page mappings)
3. For each page title:
   - Get from cache (if exists)
   - Read new content from output storage
   - Compare hashes (detect changes)
   - Skip if unchanged
   - Upload if changed
4. Track timestamps (fetched, updated, pushed)

**Upload Flow**:
- Dry-run mode: simulate without actual upload
- Batch uploads: limit concurrent uploads
- Rate limiting: delay between uploads
- Progress tracking: real-time stats (uploaded/skipped/failed)

#### Destination 3b: Google Sheets

**Process**:
1. Execute SQL query for sheet
2. Format results as spreadsheet rows
3. Batch upload to Google Sheets API
4. Handle partial failures with retry

**Sheets**: 21 total, each with custom SQL query

**Data Integrity**:
- Append-only (no deletes, only updates)
- Batch inserts (1000 rows per batch)
- Retry on transient failures

---

## Entity Types and Relationships

### Core Entities

**Characters** (NPCs/Enemies):
- **Identity**: Guid (Unity prefab), Id (DB row), ObjectName (asset name)
- **Classification**: IsFriendly, IsUnique, IsRare, IsPrefab, IsVendor, IsMiningNode
- **Stats**: Level, XP, HP, Mana, Armor, Attributes (Str/End/Dex/Agi/Int/Wis/Cha)
- **Resistances**: Magic/Elemental/Poison/Void min/max
- **Relations**: 
  - AggressiveFactions (what they're hostile to)
  - AlliedFactions (what they're friendly to)
  - AttackSpells/BuffSpells/HealSpells/etc.
  - VendorItems (what they sell)
  - FactionModifiers (faction changes on interaction)
  - LootDrops (what they drop)
  - SpawnPoints (where they appear)

**Items**:
- **Identity**: Id (DB), ResourceName (asset name)
- **Classification**: RequiredSlot, ThisWeaponType, Quality (Normal/Blessed/Godly)
- **Stats**: Level, HP, AC, Mana, Attributes, Resistances
- **Scaling**: Per-attribute scaling multipliers
- **Combat**: WeaponDmg, WeaponDly (melee), Wand range/effect, Bow range/effect
- **Special**: TeachSpell, TeachSkill, ItemEffectOnClick, WornEffect, Aura
- **Value**: ItemValue, SellValue, Stackable, Unique, NoTrade, Relic
- **Relations**:
  - ItemClasses (what classes can use)
  - LootDrops (what character drops it)
  - VendorSells (what vendor sells it)
  - QuestRewards (quest reward)
  - CraftingRecipe (craftable from what ingredients)

**Spells** (Abilities):
- **Identity**: Id (DB), ResourceName (asset)
- **Classification**: SpellType, Duration
- **Effects**: DamageFormula, ManaCost, CastTime
- **Restrictions**: RequiredClass, RequiredLevel
- **Character Relations**: AttackSpells, BuffSpells, CCSpells, HealSpells, etc.

**Skills** (Abilities):
- Similar to Spells but different table schema
- Can be taught via items (TeachSkill)

**Locations**:
- Fishing Zones
- Mining Nodes
- Treasure Locations
- Wishing Wells
- Teleports (entrances/exits)
- Secret Passages

**Systems**:
- Spawn Points (where enemies spawn, respawn timer, spawn chance)
- Loot Tables (what drops from what)
- Quest Data (objectives, rewards, requirements)
- Factions (reputation groups)
- Classes (player classes, class restrictions on items/spells)
- Ascensions (progression system)
- Books (lore/readable items)

---

## State and Change Tracking

### Registry System

**Purpose**: Map database entities to wiki pages with override support

**Data Structures**:
```
WikiRegistry:
  ├── pages: title → WikiPage
  ├── by_entity: entity.uid → WikiPage
  ├── by_page_id: page_id → WikiPage
  ├── manual_mappings: entity.stable_key → page_title
  ├── display_name_overrides: entity.stable_key → display_name
  └── image_name_overrides: entity.stable_key → image_name

WikiPage:
  ├── title: exact wiki page title
  ├── page_id: stable ID (00001234)
  ├── entities: list of EntityRef (what DB entities are on this page)
  ├── last_fetched: datetime
  ├── last_updated: datetime
  ├── last_pushed: datetime
  ├── original_content_hash: sha256 of original wiki content
  └── updated_content_hash: sha256 of generated content

EntityRef:
  ├── entity_type: ITEM|CHARACTER|SPELL|SKILL|etc.
  ├── db_id: database identifier (Id or Guid)
  ├── db_name: display name from database
  ├── resource_name: asset name (stable across patches)
  ├── uid: current version key (type:db_id)
  └── stable_key: permanent key for manual mapping (type:resource_name)
```

**Usage**:
1. Entity uniqueness tracking across game updates
2. Manual overrides for renamed/moved entities
3. Image name mapping (DB name vs wiki filename)
4. Page change detection (compare hashes)
5. Upload status tracking

---

### Upload Status Tracking

**WikiPage.needs_upload()** returns true if:
1. Never uploaded before (last_pushed is None)
2. Local content changed since last upload
3. Content differs from original wiki version
4. No original hash (can't verify wiki state)

**Upload States**:
- "never uploaded" → needs initial upload
- "local changes pending" → local update after last push
- "modified from original" → diverged from wiki source
- "up to date" → synced
- "no content hash" → unable to verify

---

## Configuration and Multi-Variant System

### Configuration Hierarchy

**Priority** (highest to lowest):
1. Environment variables (`ERENSHOR_*` prefix)
2. `.erenshor/config.local.toml` (user overrides, NOT tracked)
3. `config.toml` (project defaults, tracked)

### Variant Configuration

Each variant can override:
- Unity project path
- Game files directory
- Database path
- Logs directory
- Image output directory
- Google Sheets spreadsheet ID

**Default Variants**:
- main: Enabled by default
- playtest: Disabled (enable in config.local.toml)
- demo: Disabled

### Paths and State

**Project State** (`.erenshor/`):
- `state.json`: Pipeline state tracking
- `config.local.toml`: User configuration
- `logs/`: System logs

**Variant Directories** (`variants/{variant}/`):
- `game/`: Downloaded game files
- `unity/`: Extracted Unity project
- `logs/`: Variant-specific logs
- `backups/`: Database backups
- `erenshor-{variant}.sqlite`: Game database
- `images/processed/`: Processed game icons

---

## Integration Points with External Systems

### Steam (Source)

**Integration**: SteamCMD
- Downloads game files via App ID
- Tracks game build version
- Detects updates

### Unity (Extraction)

**Integration**: Custom Editor scripts + batch mode
- Scans project assets (AssetRipper output)
- Extracts game data to SQLite
- Scriptable approach (Listeners pattern)

### MediaWiki (Destination)

**Integration**: API v4
- List pages
- Fetch page content
- Upload new/modified content
- Create/update pages
- Upload images to File: namespace
- Query templates

**Authentication**: Bot credentials (username + password from Special:BotPasswords)

### Google Sheets (Destination)

**Integration**: Google Sheets API v4
- Service account authentication
- Batch inserts/updates
- Multiple sheets per variant

**Data Format**: SQL query results → rows

---

## Publishing Requirements

### Wiki Page Requirements

1. **Page Structure**: Each content type has defined template structure
   - Items: Infobox + stat tables (weapons/armor tiers)
   - Characters: Enemy template + stats/loot/faction/spawns
   - Abilities: Spell/skill infobox
   - System pages: Various table formats

2. **Linking**: All cross-references must resolve to correct wiki page
   - Item links in loot tables
   - Character links in spell effects
   - Faction links with correct resource names
   - Zone links from coordinates

3. **Image References**: Must use correct image names
   - Database name vs wiki filename mapping
   - Sanitization for MediaWiki compatibility
   - Filename redirects for compatibility

4. **Validation**: All generated content must pass validation
   - No broken wiki syntax
   - All referenced pages exist
   - No missing required fields
   - Properly formatted numbers/strings

### Change Detection

Before uploading, detect:
1. **Content changes**: Has markup changed since last wiki version?
2. **Entity changes**: Are the entities the same?
3. **Forced updates**: --force flag overrides

Skip upload if:
1. Content identical (unless --force)
2. Page explicitly excluded (registry)
3. Multi-entity page (per CLAUDE.md policy)

### Upload Safety

1. **Dry-run validation**: Can preview without credentials
2. **Rate limiting**: Configurable delay between uploads
3. **Batch limits**: Can limit concurrent uploads
4. **Progress tracking**: Real-time stats
5. **Rollback via backups**: Old wiki content cached

---

## Multi-Variant Requirements

### Variant Independence

Each variant must:
1. Have separate database
2. Have separate wiki deployment directory
3. Have separate image output
4. Have separate Google Sheets spreadsheet
5. Have separate logs

### Cross-Variant Operations

User must be able to:
1. Run full pipeline for all enabled variants
2. Run specific pipeline steps for specific variant
3. Update only specific entity types across variants
4. Generate reports comparing variants

---

## Data Source Transformations

### Example: Item → Wiki Page

**Source Data** (Items table):
```
Id, ItemName, ResourceName, RequiredSlot, ThisWeaponType, 
Quality, ItemLevel, HP, AC, Mana, Str, End, Dex, Agi, Int, Wis, Cha,
Res, MR, ER, PR, VR, StrScaling, ..., WeaponDmg, WeaponDly,
ItemEffectOnClick, TeachSpell, TeachSkill, Aura, WornEffect,
ItemValue, SellValue, Stackable, Unique, Relic, NoTradeNoDestroy,
BookTitle, Mining, ItemIconName, ...
```

**Related Data** (Joins + Queries):
- ItemStats (per-quality variant stats)
- ItemClasses (what classes can use)
- LootDrops (what characters drop this)
- Characters selling (vendors)
- Quests rewarding
- Crafting recipes
- Spells taught (TeachSpell, TeachSkill lookups)

**Transformations**:
1. Group ItemStats by Quality (Normal/Blessed/Godly)
2. Create separate table for each tier if multi-tier weapon/armor
3. Build loot sources table (character → drop chance)
4. Build vendor sources table (vendor → purchase info)
5. Resolve item links to wiki page titles
6. Format numbers (stat scaling, damage formulas)
7. Create wiki template with all data
8. Resolve image name via registry

**Output**: Single wiki page with infobox + stat tables + sources

### Example: Character → Wiki Page

**Source Data** (Characters table + Coordinates):
```
Id, Guid, ObjectName, NPCName, Level, HP, Mana, Stats (Str/End/Dex/Agi/Int/Wis/Cha),
Resistances (MR/ER/PR/VR), IsUnique, IsRare, IsFriendly, IsVendor,
MyWorldFaction, MyFaction, X, Y, Z, Scene
```

**Related Data**:
- Coordinates (exact spawn location)
- SpawnPoints (respawn timers, spawn chances)
- LootDrops (what they drop)
- Factions (what factions they modify)
- Spells (what spells they use)
- Items (what vendors sell)

**Transformations**:
1. Determine character type (NPC|Enemy|Boss|Rare)
2. Extract coordinates from character record or first spawn point
3. Calculate XP (base × multiplier for bosses)
4. Format stats (ranges where min ≠ max)
5. Build loot table (guaranteed + regular drops)
6. Build faction change table
7. Build spawn information (zones, respawn times, spawn chances)
8. Create enemy template with all data
9. Resolve display names and image names via registry

**Output**: Single wiki page with enemy infobox + stats/loot/faction/spawn info

---

## Success Criteria

A working Erenshor system must:

1. **Extract Data**: Successfully export all entity types to SQLite without errors
2. **Generate Content**: Convert all database entities to valid wiki markup
3. **Publish Content**: Upload pages to wiki with correct links and images
4. **Publish Sheets**: Deploy data to Google Sheets with all rows
5. **Track State**: Maintain registry and upload tracking across runs
6. **Multi-Variant**: Run all variants independently without interference
7. **Detect Changes**: Only upload when content actually changes
8. **Handle Errors**: Fail gracefully with clear error messages
9. **Dry-Run**: Allow preview without credentials or wiki changes
10. **Resume**: Complete interrupted pipelines on re-run

---

## Key Constraints

1. **Zero Manual Wiki Editing**: Content generated entirely from database
2. **Automated Publishing**: No human approval step for wiki updates
3. **Batch Processing**: High-volume entity handling (1000s of items/characters)
4. **Rate Limiting**: Wiki/Sheets API throttling (configurable delays)
5. **Exact Unity Version**: Must use 2021.3.45f2 (game's version)
6. **Free Services Only**: SteamCMD, AssetRipper, Unity Personal, Google Sheets API
7. **No Game Code**: Cannot include non-Editor C# code in repo
8. **Symlink C#, Copy DLLs**: Unity assembly loading limitation

---

## Command Examples (User Perspective)

```bash
# Full pipeline update (detect changes, download, extract, export, deploy)
erenshor update

# Update specific entities only
erenshor update --entities items,spells,characters

# Dry-run (preview without changes)
erenshor update --dry-run

# Update all variants
erenshor update --all-variants

# Generate wiki content
erenshor-wiki update items
erenshor-wiki update characters --unique-only
erenshor-wiki update all --validate-only

# Upload to wiki
erenshor-wiki wiki push --all --dry-run
erenshor-wiki wiki push --characters
erenshor-wiki wiki push --weapons

# Deploy to Google Sheets
erenshor-wiki sheets deploy --all-sheets

# Image processing
erenshor-wiki images process
erenshor-wiki images upload --dry-run
erenshor-wiki images compare

# Utility commands
erenshor status --all-variants
erenshor doctor
erenshor config get
```

---

This analysis captures the functional requirements focusing on **WHAT needs to happen**, not the current HOW it's implemented. The system is fundamentally:
- **Pipeline**: Integrated workflow from source to multiple destinations
- **Multi-tenancy**: Support for multiple game variants
- **State-tracked**: Maintains registry and upload history
- **Automated**: No manual steps except triggering commands
- **Safe**: Dry-run, validation, backups
