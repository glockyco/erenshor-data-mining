# Erenshor Project: Requirements Summary

## What Is Erenshor?

Erenshor is a **fully automated data mining and publishing pipeline** for a single-player MMORPG. It extracts game data, stores it in a database, and publishes it to a wiki and Google Sheets with zero manual intervention.

**Core Philosophy**: One command (`erenshor update`) triggers the entire workflow from game download to wiki page publication.

---

## The Six Core Workflows

### 1. Full Pipeline Update
Sync all game data from Steam to wiki to sheets in one operation.
- Detect game updates on Steam
- Download and extract game files
- Export data to SQLite
- Generate wiki markup
- Upload to wiki and Google Sheets
- Track all changes

### 2. Wiki Content Generation & Upload
Convert database state to wiki pages and push updates.
- Generate wiki markup from current database
- Detect what changed
- Dry-run preview
- Batch upload with rate limiting
- Skip unchanged content
- Track upload history

### 3. Data Comparison
Understand what will change before uploading.
- Fetch current wiki content
- Generate new markup
- Show diffs
- Summary statistics

### 4. Image Processing & Upload
Extract game icons, process them, and publish to wiki.
- Extract icon filenames from database
- Resize/format for wiki
- Compare with cached versions
- Upload new/changed images
- Create filename redirects

### 5. Google Sheets Deployment
Publish game data across 21 spreadsheets.
- Execute SQL query per sheet
- Format as spreadsheet rows
- Batch upload via API
- Retry on failures

### 6. Multi-Variant Management
Maintain separate instances for main game, playtest, and demo.
- Independent databases per variant
- Separate wiki/sheets per variant
- Run specific or all variants
- Track state per variant

---

## The Data Pipeline

### Source → SQLite (Extraction)
```
Steam Files → AssetRipper → Unity Project → Custom Editor Scripts → SQLite
```
- 30+ entity types extracted
- 20,600+ normalized junction table rows
- All relationships captured

### SQLite → Wiki Pages (Transformation)
```
Query Database → Build Context → Render Template → Normalize → Generate Content
```
- Streaming generation (one entity at a time)
- Link resolution (database names → wiki pages)
- Display name overrides
- Image name mapping
- Multi-entity page detection

### Generated Content → Wiki & Sheets (Publishing)
```
Change Detection → Upload → Rate Limiting → Progress Tracking
```
- Skip unchanged pages
- Dry-run validation
- Batch limits
- Real-time progress
- Upload history tracking

---

## Core Entity Types

**Combat**
- Characters (NPCs/Enemies/Bosses)
- Spells (abilities)
- Skills (abilities)
- Items (weapons, armor, consumables)

**Systems**
- Spawn Points (respawn timers, spawn chances)
- Loot Tables (drop probability)
- Quests (objectives, rewards)
- Factions (reputation)
- Classes (player classes, restrictions)

**Locations**
- Fishing zones
- Mining nodes
- Treasure locations
- Wishing wells
- Teleport points
- Secret passages

**Other**
- Books (lore)
- Ascensions (progression)
- Vendors (NPC shops)
- Pet summons

---

## State & Change Tracking

**Registry System** tracks:
- Entity → Wiki page mappings
- Manual overrides (renamed/moved entities)
- Display names and image names
- Page upload status and timestamps
- Content hashes (detect changes)

**Upload Status**:
- Never uploaded
- Local changes pending
- Modified from original
- Up to date
- Unable to verify

---

## Key Features

| Feature | Purpose |
|---------|---------|
| **Multi-Variant** | Support main, playtest, demo versions independently |
| **Dry-Run** | Preview changes without credentials or wiki access |
| **Registry** | Map database entities to wiki pages with overrides |
| **Streaming** | Process 1000s of entities without loading all to memory |
| **Link Resolution** | Automatically resolve cross-references in wiki content |
| **Change Detection** | Only upload when content actually changes |
| **Rate Limiting** | Respect API throttling (configurable delays) |
| **Batch Processing** | Limit concurrent operations |
| **Progress Tracking** | Real-time stats during operations |
| **Backup/Restore** | Keep wiki content copies for safety |

---

## Multi-Variant Independence

Each variant (main/playtest/demo) has its own:
- Steam download directory
- Unity project
- SQLite database
- Wiki deployment directory
- Google Sheets spreadsheet
- Image output directory
- Logs

Operations can target:
- Single variant
- All enabled variants
- Specific pipeline steps

---

## Configuration

**Hierarchy** (highest to lowest):
1. Environment variables (`ERENSHOR_*`)
2. `.erenshor/config.local.toml` (user overrides, not tracked)
3. `config.toml` (project defaults, tracked)

**Per-variant overrides**:
- Unity project path
- Game files directory
- Database path
- Image output
- Google Sheets ID

---

## External System Integrations

| System | Role | Integration |
|--------|------|-------------|
| **Steam** | Source | SteamCMD downloads game files |
| **Unity** | Extraction | Custom Editor scripts export to SQLite |
| **AssetRipper** | Extraction | Converts binary assets to readable form |
| **MediaWiki** | Destination | API v4 for pages and images |
| **Google Sheets** | Destination | API v4 for batch data uploads |

---

## Publishing to Wiki

**Page Structure**:
- Items: Infobox + stat tables
- Characters: Enemy template + stats/loot/faction/spawns
- Abilities: Spell/skill infobox
- System pages: Various table formats

**Requirements**:
- All links must resolve to existing pages
- Images must use correct names (with aliases)
- No broken wiki syntax
- All referenced entities must exist

**Safety**:
- Dry-run validation
- Rate limiting (configurable)
- Batch size limits (configurable)
- Real-time progress
- Wiki content cache for rollback

---

## Publishing to Google Sheets

**Format**: SQL query → Rows

**Available Sheets** (21 total):
- Items, Weapons, Armor, Auras, Consumables
- Characters, Spells, Skills, Abilities
- Drop Chances, Spawn Points, Fishing, Mining
- Quests, Books, Factions, Classes, Ascensions
- Item Bags, Treasure, Wishing Wells, Achievements, Teleports
- Dialog transcripts

**Data Integrity**:
- Append-only (no deletes)
- Batch inserts (1000 rows per batch)
- Retry on failures

---

## User Commands

```bash
# Full pipeline
erenshor update [--variant VARIANT] [--all-variants]

# Wiki generation
erenshor-wiki update items|characters|abilities|fishing|overviews|all
erenshor-wiki update items --filter "Sword"
erenshor-wiki update characters --unique-only

# Wiki upload
erenshor-wiki wiki push --all [--dry-run]
erenshor-wiki wiki push --characters
erenshor-wiki wiki push --weapons --armor

# Image operations
erenshor-wiki images process [--force] [--dry-run]
erenshor-wiki images upload [--dry-run]
erenshor-wiki images compare

# Data publishing
erenshor-wiki sheets deploy --all-sheets

# Utilities
erenshor status [--all-variants]
erenshor doctor
erenshor config get
```

---

## Success Criteria

A working Erenshor implementation must:

1. Extract all entity types to SQLite without errors
2. Generate valid wiki markup from database
3. Upload pages to wiki with correct links and images
4. Deploy data to Google Sheets
5. Maintain registry for entity tracking
6. Support multi-variant operation
7. Detect and skip unchanged content
8. Provide meaningful error messages
9. Support dry-run mode
10. Resume interrupted pipelines

---

## Key Constraints

- **Zero manual wiki editing**: 100% automated
- **Unity 2021.3.45f2**: Exact game version
- **Free services only**: No paid tools
- **Batch processing**: Handle 1000s of entities
- **API rate limiting**: Respect throttling
- **No game code in repo**: Only Editor scripts
- **Symlink/Copy limitation**: Unity assembly loading

---

## File Structure

```
erenshor/
├── cli/                    # Bash CLI orchestration
├── src/erenshor/          # Python business logic
│   ├── cli/               # Python CLI commands
│   ├── application/       # Data transformation
│   ├── infrastructure/    # External systems (wiki, sheets, DB)
│   ├── domain/            # Domain models (entities, registry)
│   └── registry/          # Entity-to-page mappings
├── src/Assets/Editor/     # Unity export scripts
├── variants/              # Game data (per variant)
├── docs/                  # Documentation
└── config.toml            # Configuration
```

---

This is a requirements-focused analysis. For implementation details, see `/docs/CLAUDE.md`.
