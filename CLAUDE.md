# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a data mining project for Erenshor, a single-player simulated MMORPG. The project extracts Unity projects from game files using AssetRipper, exports game data to SQLite databases via custom Unity Editor scripts, and deploys data to MediaWiki and Google Sheets.

**CRITICAL**: Only code in `src/Assets/Editor/` and `src/erenshor/` should be modified. All other code, assets, and files from the original game MUST NOT be changed under any circumstances.

## Project Context

- **Solo Developer**: Hobby project maintained by a single developer
- **Zero Cost**: Everything must be free (SteamCMD, AssetRipper, Unity Personal, Google Sheets API)
- **Automated Pipeline**: Full automation from Steam download to Google Sheets deployment
- **Multi-Variant Support**: Handles main game, playtest, and demo versions separately
- **Unity Constraints**: Non-Editor code cannot be included in git (belongs to game developer)
- **Output**: SQLite databases and formatted data for wiki generation and spreadsheets

## Architecture

### Two-Layer CLI System

The project uses a **hybrid Bash + Python CLI architecture**:

```
┌────────────────────────────────────────────┐
│         Bash CLI (Orchestration)           │
│  • Pipeline automation                     │
│  • System operations                       │
│  • Unity/SteamCMD/AssetRipper integration  │
└────────────┬───────────────────────────────┘
             │ python_exec()
             ↓
┌────────────────────────────────────────────┐
│       Python CLI (Business Logic)          │
│  • Database operations                     │
│  • Wiki operations                         │
│  • Google Sheets deployment                │
│  • Data formatting and transformation      │
└────────────────────────────────────────────┘
```

**Key Principle**: Bash orchestrates the pipeline and system operations, Python handles business logic and data processing.

### Directory Structure

```
erenshor/
├── .erenshor/                  # Project state (NOT in git)
│   ├── state.json              # Pipeline state tracking
│   └── config.local.toml       # User config overrides
├── cli/                        # Bash CLI
│   ├── bin/erenshor            # Main CLI entry point
│   ├── commands/               # Bash command implementations
│   │   ├── download.sh         # SteamCMD game download
│   │   ├── extract.sh          # AssetRipper extraction
│   │   ├── export.sh           # Unity batch mode export
│   │   └── deploy.sh           # Deploy to wiki/sheets
│   └── lib/
│       ├── core/               # Core utilities
│       │   ├── config.sh       # Configuration management
│       │   ├── logging.sh      # Logging utilities
│       │   └── state.sh        # State management
│       └── modules/            # Feature modules
│           ├── python.sh       # Python CLI integration
│           ├── steamcmd.sh     # SteamCMD integration
│           ├── assetripper.sh  # AssetRipper integration
│           ├── unity.sh        # Unity Editor automation
│           └── database.sh     # Database operations
├── src/                        # Source code
│   ├── erenshor/               # Python package
│   │   ├── application/        # Application services
│   │   │   ├── formatters/     # Data formatters
│   │   │   │   └── sheets/     # Google Sheets formatters
│   │   │   │       └── queries/  # SQL query files
│   │   │   └── services/       # Business services
│   │   ├── cli/                # Python CLI implementation
│   │   │   └── commands/       # Python command implementations
│   │   ├── domain/             # Domain models
│   │   ├── infrastructure/     # Infrastructure layer
│   │   │   └── publishers/     # Google Sheets, MediaWiki
│   │   └── registry/           # Entity registries
│   ├── export.sh               # Unity batch mode export wrapper
│   └── Assets/
│       ├── Editor/             # Unity export scripts (symlinked to Unity)
│       │   ├── ExportBatch.cs  # Batch mode export entry
│       │   ├── Database/       # SQLite table records
│       │   ├── ExportSystem/   # Asset scanning system
│       │   │   ├── AssetScanner.cs
│       │   │   └── AssetScanner/Listener/  # Entity listeners
│       │   └── WikiUtils/      # Wiki comparison tools
│       └── Packages/           # NuGet packages (copied to Unity)
├── variants/                   # Working directories (NOT in git)
│   ├── main/                   # Main game (App ID 2382520)
│   │   ├── game/               # Downloaded from Steam
│   │   ├── unity/              # Unity project from AssetRipper
│   │   │   └── Assets/Editor -> ../../../../src/Assets/Editor/
│   │   ├── logs/               # Variant-specific logs
│   │   └── erenshor-main.sqlite
│   ├── playtest/               # Playtest (App ID 3090030)
│   └── demo/                   # Demo (App ID 2522260)
├── docs/                       # Documentation
├── tests/                      # Python tests
├── config.toml                 # Main config
└── pyproject.toml              # Python dependencies
```

### Multi-Variant System

Three game variants with separate pipelines:
- **main** (App ID 2382520): Production game
- **playtest** (App ID 3090030): Public test branch
- **demo** (App ID 2522260): Free demo version

Each variant has:
- Separate game downloads (`variants/{variant}/game/`)
- Separate Unity projects (`variants/{variant}/unity/`)
- Separate databases (`erenshor-{variant}.sqlite`)
- Separate logs (`variants/{variant}/logs/`)

## CLI Commands

### Bash CLI Commands

```bash
# Full pipeline (download → extract → export → deploy)
erenshor update [--variant <variant>]

# Individual pipeline steps
erenshor download [--variant <variant>]  # Download from Steam via SteamCMD
erenshor extract [--variant <variant>]   # Extract Unity project via AssetRipper
erenshor export [--variant <variant>]    # Export to SQLite via Unity batch mode
erenshor deploy [--variant <variant>]    # Deploy to wiki/sheets

# Utilities
erenshor status [--all-variants]         # Show system status
erenshor config get [<key>]              # View configuration
erenshor symlink check|create|status     # Manage symlinks
erenshor doctor                          # System health check
erenshor test-python                     # Test Python integration
```

### Python CLI Commands

```bash
# Direct invocation (for development/testing)
uv run python -m erenshor.cli.main <command>

# Database operations
python_exec db stats                     # Database statistics
python_exec db validate                  # Validate schema

# Wiki operations
python_exec wiki fetch                   # Fetch wiki templates
python_exec wiki update                  # Update wiki pages

# Google Sheets deployment
python_exec sheets list                  # List available sheets
python_exec sheets validate              # Validate credentials
python_exec sheets deploy --all-sheets   # Deploy all sheets

# Utilities
python_exec check-paths                  # Show path configuration
```

### Python Integration

The Bash CLI calls Python CLI commands via `python_exec()`:

```bash
# In Bash command scripts
python_exec wiki update "$@"                    # Simple delegation
python_exec_variant "$variant" sheets deploy    # With variant context
python_exec_with_config db.path "/custom/path" db stats  # With config override
```

See `docs/PYTHON_INTEGRATION.md` for detailed integration guide.

## Common Workflows

### Running Full Pipeline

```bash
# Update all data for main variant
erenshor update

# Update specific variant
erenshor update --variant playtest

# Deploy to Google Sheets after export
erenshor export && python_exec sheets deploy --all-sheets
```

### Adding New Export Type

1. Create record class: `src/Assets/Editor/Database/MyRecord.cs`
2. Create listener: `src/Assets/Editor/ExportSystem/AssetScanner/Listener/MyListener.cs`
3. Register in `ExportBatch.cs` (CLI) or `AssetScannerExporterWindow.cs` (GUI)
4. Test: `erenshor export`

### Adding New Google Sheets Query

1. Create SQL file: `src/erenshor/application/formatters/sheets/queries/my-sheet.sql`
2. Write SQL query (returns header + data rows)
3. Deploy: `python_exec sheets deploy --sheets my-sheet`

### Creating Bash Command that Calls Python

Pattern 1 - Simple delegation:
```bash
#!/usr/bin/env bash
command_main() {
    python_exec my-command "$@"
}
```

Pattern 2 - Hybrid (Bash + Python):
```bash
#!/usr/bin/env bash
command_main() {
    local variant="${1:-main}"

    # Bash operations
    validate_database "$variant" || return 1

    # Python business logic
    python_exec_variant "$variant" process-data
}
```

Pattern 3 - Orchestration:
```bash
#!/usr/bin/env bash
command_main() {
    python_exec wiki fetch || return 1
    unity_export "$variant" || return 1
    python_exec wiki update || return 1
}
```

## Data Mining Architecture

### Unity Export System

**Location**: `src/Assets/Editor/ExportSystem/`

**Core Components:**
- `ExportBatch.cs` - Entry point for batch mode exports
- `AssetScanner.cs` - Scans Unity project for game assets
- `Repository.cs` - Database operations and table management

**Listeners**: Each listener extracts specific game data:
- `ItemListener.cs` - Items and equipment
- `CharacterListener.cs` - NPCs and creatures
- `SpawnPointListener.cs` - Enemy spawn locations
- `QuestListener.cs` - Quest data
- `LootTableListener.cs` - Drop tables
- And 20+ more...

### Database Schema

**Junction Tables**: junction tables for many-to-many relationships:
- Character abilities: `CharacterAttackSpells`, `CharacterBuffSpells`
- Quest relationships: `QuestRequiredItems`, `QuestRewards`
- Class restrictions: `ItemClasses`, `SpellClasses`
- Spawn mechanics: `SpawnPointCharacters`, `SpawnPointPatrolPoints`

**Total**: 20,600+ normalized rows across all junction tables.

### Google Sheets Deployment

**Architecture**: SQL queries → Formatter → Publisher → Google Sheets

**Components**:
1. **SQL Query Files**: `src/erenshor/application/formatters/sheets/queries/*.sql`
2. **SheetsFormatter**: Executes SQL, formats results as spreadsheet rows
3. **GoogleSheetsPublisher**: Publishes via Google Sheets API v4
4. **SheetsDeployService**: Orchestrates deployment workflow

**Available Sheets**: various sheets including items, characters, spells, quests, drop-chances, spawn-points, and more.

See `docs/GOOGLE_SHEETS_DEPLOYMENT.md` for complete guide.

## Configuration

Two-layer configuration system (NO environment variables):
1. `config.toml` (project defaults, tracked in git)
2. `.erenshor/config.local.toml` (user overrides, NOT tracked in git)

**Key config values**:
```toml
[unity]
path = "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity"
version = "2021.3.45f2"

[google_sheets]
credentials_file = "$HOME/.config/erenshor/google-credentials.json"
batch_size = 1000

[variants.main]
app_id = 2382520
database = "$REPO_ROOT/variants/main/erenshor-main.sqlite"

[variants.main.google_sheets]
spreadsheet_id = "1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E"
```

## Development Guidelines

1. **Only modify `src/Assets/Editor/` and `src/erenshor/`** - Never change game files
2. **Use Bash for orchestration** - Pipeline steps, system operations, Unity/Steam integration
3. **Use Python for business logic** - Data processing, formatting, API interactions
4. **Test exports** - Verify exported data matches game
5. **Maintain Unity 2021.3.45f2 compatibility** - Game's exact version
6. **Work with variants** - Test changes across main, playtest, and demo
7. **Follow Python best practices** - Type hints, tests, domain-driven design

## Code Quality Principles

1. **Fail Fast and Loud**
   - No fallback functionality that hides errors
   - Fail immediately with clear error messages

2. **No Backward Compatibility**
   - Clean breaks when changing behavior
   - No legacy code paths "just in case"
   - One-off migration scripts OK, but don't leave migration code

3. **Keep It Simple**
   - No extra config options, flags, or features
   - Suggest improvements proactively, but only implement after discussion

4. **Clean Cuts Only**
   - Remove old code entirely when refactoring
   - No "legacy support" or "fallback paths"
   - Less code = less maintenance

5. **Minimal Comments**
   - Don't comment what's obvious from code
   - No development history in comments
   - Comments explain *why*, not *what*

6. **Atomic Commits**
   - Commit regularly with logical, focused changes
   - One concept per commit
   - Clear, concise commit messages

## Testing

### Python Tests
```bash
# Run all tests
uv run pytest

# With coverage
uv run pytest --cov

# Integration tests only
uv run pytest -m integration

# Watch mode (run on file changes)
uv run pytest-watch
```

### Bash Integration Tests
```bash
# Test Python integration
erenshor test-python

# Test environment
erenshor test-python env

# Test CLI commands
erenshor test-python cli
```

## Python Environment

**Preferred**: Use `uv` for automatic dependency management
```bash
uv sync --dev              # Install dependencies
uv run pytest              # Run tests
uv run python -m erenshor.cli.main  # Run CLI
```

**Fallback**: System Python with pip
```bash
pip install -e src/        # Install package
python3 -m erenshor.cli.main  # Run CLI
```

**Environment Detection**: The Bash CLI automatically detects uv vs system Python.

## Debugging

### Export Issues
1. Check logs: `variants/{variant}/logs/export_*.log`
2. Check global logs: `.erenshor/logs/`
3. Verify Unity version: `erenshor config get unity.version`
4. Check ScriptableObject references are valid
5. Use SQLite viewer to inspect database
6. Run Unity in GUI mode for console errors

### Python CLI Issues
```bash
# Check environment
python_check_env

# Show environment info
python_show_env

# Validate integration
python_validate

# Enable debug logging
export LOG_LEVEL=DEBUG
python_exec <command>
```

### Google Sheets Issues
- **Authentication**: Check `~/.config/erenshor/google-credentials.json` exists
- **Permissions**: Service account needs **Editor** access (not just Viewer)
- **Validation**: Run `python_exec sheets validate` to test credentials
- **Dry-run**: Test without writing: `python_exec sheets deploy --dry-run`

## Important Constraints

1. **Unity Version**: MUST use Unity 2021.3.45f2 (game's exact version)
2. **Steam Credentials**: Requires valid Steam account with game ownership
3. **Git Ignore**: All variant directories, databases, `.erenshor/` not tracked
4. **Symlinks**: C# files symlinked, DLLs copied (Unity assembly loading limitation)
5. **Batch Mode**: Unity exports run headless via CLI (no GUI)
6. **Service Account**: Google Sheets requires Editor access for deployment

## Key Files

**Bash CLI**:
- `cli/bin/erenshor` - Main CLI entry point
- `cli/lib/modules/python.sh` - Python integration module
- `cli/commands/*.sh` - Bash command implementations

**Python CLI**:
- `src/erenshor/cli/main.py` - Python CLI entry point
- `src/erenshor/cli/commands/*.py` - Python command implementations
- `src/erenshor/application/services/` - Business services

**Unity Export**:
- `src/Assets/Editor/ExportBatch.cs` - Batch export entry point
- `src/Assets/Editor/ExportSystem/AssetScanner.cs` - Asset scanner
- `src/Assets/Editor/Database/*.cs` - SQLite table records

**Configuration**:
- `config.toml` - Main configuration
- `.erenshor/config.local.toml` - User overrides
- `pyproject.toml` - Python dependencies

## Quick Reference

```bash
# Full update pipeline
erenshor update

# Export Unity data
erenshor export

# Deploy to Google Sheets
python_exec sheets deploy --all-sheets

# Check system health
erenshor doctor

# View configuration
erenshor config get

# Test Python integration
erenshor test-python

# Run Python tests
uv run pytest

# Check logs
erenshor logs

# View status
erenshor status --all-variants
```

## Notes

For AI assistance: Focus on the separation of concerns - Bash handles orchestration and system operations, Python handles data processing and API integrations. Always respect the "only modify src/" constraint.
