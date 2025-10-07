# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a data mining project for Erenshor, a single-player simulated MMORPG. The project uses AssetRipper to extract Unity projects from game files, then exports game data to SQLite databases via custom Unity Editor scripts.

**CRITICAL**: Only code in `src/Assets/Editor/` should be modified. All other code, assets, and files from the original project MUST NOT be changed under any circumstances.

## Project Context & Requirements

- **Solo Developer**: Hobby project maintained by a single developer
- **Zero Cost**: Everything must be free (SteamCMD, AssetRipper, Unity Personal)
- **Automated Pipeline**: Full automation from Steam download to database deployment
- **Multi-Variant Support**: Handles main game, playtest, and demo versions separately
- **Unity Constraints**: Non-Editor code cannot be included in git (belongs to game developer)
- **Output**: SQLite databases deployed to `erenshor-wiki` project for wiki generation

## Architecture Overview

### Directory Structure

```
erenshor/
├── .erenshor/              # Project-local state (NOT tracked in git)
│   ├── state.json          # Pipeline state tracking
│   └── config.local.toml   # User config overrides (machine-specific)
├── cli/                    # CLI automation scripts (tracked)
│   ├── bin/erenshor        # Main CLI entry point
│   ├── commands/           # Command implementations
│   │   ├── download.sh     # SteamCMD game download
│   │   ├── extract.sh      # AssetRipper extraction
│   │   ├── export.sh       # Unity batch mode export
│   │   ├── deploy.sh       # Deploy database to wiki
│   │   └── update.sh       # Full pipeline
│   ├── lib/
│   │   ├── core/           # Core utilities
│   │   │   ├── config.sh   # Configuration management
│   │   │   ├── logging.sh  # Logging utilities
│   │   │   └── state.sh    # State management
│   │   └── modules/        # Feature modules
│   │       ├── steamcmd.sh      # SteamCMD integration
│   │       ├── assetripper.sh   # AssetRipper integration
│   │       ├── unity.sh         # Unity Editor automation
│   │       └── database.sh      # Database operations
├── src/                    # Source code (tracked)
│   └── Assets/
│       ├── Editor/         # Unity export scripts (symlinked into Unity projects)
│       │   ├── ExportBatch.cs  # Batch mode export entry point
│       │   ├── Database/       # Record classes for SQLite tables
│       │   ├── ExportSystem/
│       │   │   ├── AssetScanner.cs
│       │   │   └── AssetScanner/
│       │   │       └── Listener/  # Listeners for each entity type
│       │   └── WikiUtils/      # Wiki comparison tools
│       └── Packages/       # NuGet packages (copied to Unity projects)
├── variants/               # Working directories (NOT tracked)
│   ├── main/               # Main game variant (App ID 2382520)
│   │   ├── game/           # Downloaded game files from Steam
│   │   ├── unity/          # Unity project extracted by AssetRipper
│   │   │   └── Assets/Editor -> ../../../../src/Assets/Editor/  # Symlink
│   │   ├── logs/           # Variant-specific logs
│   │   └── erenshor-main.sqlite
│   ├── playtest/           # Playtest variant (App ID 3090030)
│   └── demo/               # Demo variant (App ID 2522260)
├── config.toml             # Main configuration (tracked)
├── CLAUDE.md               # This file (tracked)
└── erenshor.sqlite         # Reference database copy (NOT tracked)
```

### Multi-Variant System

The project supports three game variants:
- **main** (App ID 2382520): Production game
- **playtest** (App ID 3090030): Public test branch
- **demo** (App ID 2522260): Free demo version

Each variant has separate:
- Game downloads (`variants/{variant}/game/`)
- Unity projects (`variants/{variant}/unity/`)
- SQLite databases (`erenshor-{variant}.sqlite`)
- Logs (`variants/{variant}/logs/`)

### Hybrid Symlink Approach

- **Symlink**: `src/Assets/Editor/` → `variants/{variant}/unity/Assets/Editor/`
  - Source code files (.cs) work fine through symlinks
  - Allows editing in one place, used by all variants
- **Copy**: `src/Assets/Packages/` → `variants/{variant}/unity/Assets/Packages/`
  - NuGet DLLs must be copied (Unity can't load assemblies through symlinks)
  - Managed by `erenshor symlink create` command

## CLI Automation Pipeline

The CLI provides a complete automation pipeline for data mining:

```bash
# Full pipeline: download → extract → export → deploy
erenshor update [--variant <variant>]

# Individual steps
erenshor download [--variant <variant>]  # Download game from Steam via SteamCMD
erenshor extract [--variant <variant>]   # Extract Unity project via AssetRipper
erenshor export [--variant <variant>]    # Export data to SQLite via Unity batch mode
erenshor deploy [--variant <variant>]    # Deploy database to wiki project

# Utilities
erenshor status [--all-variants]         # Show system status
erenshor config get <key>                # Get configuration value
erenshor symlink check|create|status     # Manage symlinks
```

### Pipeline Steps

1. **download**: Uses SteamCMD to download game files from Steam
   - Requires Steam credentials (stored in `~/.steam/`)
   - Downloads to `variants/{variant}/game/`
   - Validates App ID and manifest

2. **extract**: Uses AssetRipper to extract Unity project from game files
   - Extracts to `variants/{variant}/unity/`
   - Creates symlinks to `src/Assets/Editor/`
   - Copies NuGet packages to `Assets/Packages/`

3. **export**: Runs Unity in batch mode to export game data
   - Invokes `ExportBatch.Run()` method
   - Generates `erenshor-{variant}.sqlite` in variant directory
   - Logs to `variants/{variant}/logs/export_*.log`

4. **deploy**: Copies database to wiki project
   - Preserves variant-specific filename (`erenshor-{variant}.sqlite`)
   - Destination: `erenshor-wiki/`
   - Reference copy kept at project root (`erenshor.sqlite`)

### Configuration

Configuration is loaded from multiple sources (in order of precedence):

1. Environment variables (e.g., `ERENSHOR_UNITY_PATH`)
2. `.erenshor/config.local.toml` (user overrides, NOT tracked)
3. `config.toml` (project defaults, tracked)

**Important config values**:
- `unity.path`: Path to Unity 2021.3.45f2 executable
- `unity.version`: Unity version (must be 2021.3.45f2)
- `steamcmd.path`: Path to SteamCMD executable
- `assetripper.path`: Path to AssetRipper.ConsoleApp executable
- `variants.*.app_id`: Steam App ID for each variant
- `paths.*`: Various paths using `$REPO_ROOT` and `$HOME` for portability

## Data Mining Architecture

### Export System (`src/Assets/Editor/ExportSystem/`)

**Core Components:**
- `ExportBatch.cs` - Entry point for batch mode exports
- `AssetScanner.cs` - Scans Unity project for game assets
- `Repository.cs` - Database operations and table management

**Listeners** (`src/Assets/Editor/ExportSystem/AssetScanner/Listener/`):
Each listener extracts specific game data:
- `ItemListener.cs` - Items and equipment
- `CharacterListener.cs` - NPCs and creatures
- `SpawnPointListener.cs` - Enemy spawn locations
- `QuestListener.cs` - Quest data
- `LootTableListener.cs` - Drop tables
- `SpellListener.cs` / `SkillListener.cs` - Abilities
- And many more...

**Junction Tables**

The database schema uses junction tables for many-to-many relationships:

- **29 Junction Tables**: Characters (13), quests (6), items/spells (3), spawn points (3), crafting (2), gathering systems (2)
- **20,600+ Normalized Rows**: All relationships properly normalized
- **CSV Fields**: Comma-separated fields retained for backward compatibility
- **Deferred Foreign Key Resolution**: Junction records created after primary entities to handle Unity asset lifecycle
- **Database Location**: `erenshor-wiki/erenshor-{variant}.sqlite`

**Key Junction Tables:**
- Character abilities: `CharacterAttackSpells`, `CharacterBuffSpells`, `CharacterAggressiveFactions`, `CharacterVendorItems`
- Quest relationships: `QuestRequiredItems`, `QuestFactionAffects`, `QuestRewards`
- Class restrictions: `ItemClasses`, `SpellClasses`
- Spawn mechanics: `SpawnPointCharacters`, `SpawnPointPatrolPoints`
- Crafting: `CraftingRecipes`, `CraftingRewards`

Junction tables enable proper relational queries, referential integrity, and eliminate CSV field duplication.

### Database Schema (`src/Assets/Editor/Database/`)

Record classes map to SQLite tables:
- `ItemRecord.cs` / `ItemStatsRecord.cs` - Item data
- `CharacterRecord.cs` - NPC/creature data
- `SpawnPointRecord.cs` - Spawn locations
- `QuestRecord.cs` - Quest information
- `LootTableRecord.cs` - Loot drops
- Additional records for all game systems

### Wiki Integration (`src/Assets/Editor/WikiUtils/`)

Tools for comparing game data with wiki:
- `WikiTemplateExtractor.cs` - Extract wiki templates
- `WikiTemplateParser.cs` - Parse wiki markup
- `WikiItemComparer.cs` - Compare items
- Specialized comparers for armor, weapons, abilities

### Utility Tools

- `LootTableProbabilityCalculator.cs` - Calculate drop rates
- `StatsObjectFinder.cs` - Find objects with specific stats
- `SceneScriptSearchWindow.cs` - Search scenes for scripts
- `TileScreenshotter.cs` - Generate map tiles

## Development Guidelines

1. **Only modify files in `src/Assets/Editor/`** - Never change original game files
2. **Use CLI for pipeline operations** - Automates download, extract, export, deploy
3. **Test data exports** - Verify exported data matches game
4. **Maintain compatibility** - Ensure tools work with Unity 2021.3.45f2
5. **Validate against wiki** - Use comparison tools to check accuracy
6. **Work with variants** - Test changes across main, playtest, and demo variants

## Common Tasks

### Running Full Data Export Pipeline

```bash
# Update all data for main variant (download, extract, export, deploy)
erenshor update

# Update specific variant
erenshor update --variant playtest

# Run individual steps
erenshor download             # Download game from Steam
erenshor extract              # Extract Unity project
erenshor export               # Export to SQLite
erenshor deploy               # Deploy to wiki project
```

### Manual Unity Export (Alternative)

If you need to run exports manually through Unity Editor:
1. Open the Unity project in Unity 2021.3.45f2
   - Project location: `variants/{variant}/unity/`
2. Use **Tools > Export Game Data** menu
3. Monitor progress in the AssetScannerExporterWindow
4. Database output: `variants/{variant}/erenshor-{variant}.sqlite`

### Adding a New Export Type

1. Create a new Record class in `src/Assets/Editor/Database/`
2. Create a corresponding Listener in `src/Assets/Editor/ExportSystem/AssetScanner/Listener/`
3. Register the listener in `ExportBatch.cs` (for CLI) or `AssetScannerExporterWindow.cs` (for GUI)
4. Test with: `erenshor export`

### Working with Multiple Variants

```bash
# Check status of all variants
erenshor status --all-variants

# Export specific variant
erenshor export --variant playtest

# Compare databases between variants
sqlite3 variants/main/erenshor-main.sqlite "SELECT COUNT(*) FROM Items"
sqlite3 variants/playtest/erenshor-playtest.sqlite "SELECT COUNT(*) FROM Items"
```

### Managing Symlinks

```bash
# Check symlink status
erenshor symlink status

# Create missing symlinks
erenshor symlink create

# Verify symlinks
erenshor symlink check
```

### Debugging Export Issues

1. Check logs in `variants/{variant}/logs/export_*.log`
2. Check global logs in `.erenshor/logs/`
3. Verify Unity version: `erenshor config get unity.version`
4. Check ScriptableObject references are valid
5. Use external SQLite viewer to inspect database
6. Run Unity in GUI mode to see console errors

### Configuration Management

```bash
# View all configuration
erenshor config get

# Get specific value
erenshor config get unity.path

# Edit user overrides
vim .erenshor/config.local.toml

# Edit project defaults (use with caution)
vim config.toml
```

## Notes

- **Unity Version**: Must use Unity 2021.3.45f2 (game's version)
- **SteamCMD**: Requires valid Steam account with game ownership
- **AssetRipper**: Extracts game assets to Unity project format
- **Batch Mode**: Exports run in Unity batch mode (no GUI) via CLI
- **Git Ignore**: All variant directories, databases, and `.erenshor/` are not tracked
