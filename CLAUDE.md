# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a data mining project for Erenshor, a single-player simulated MMORPG. The project extracts Unity projects from game files using AssetRipper, exports game data to SQLite databases via custom Unity Editor scripts, and deploys data to MediaWiki and Google Sheets.

**CRITICAL**: Only code in `src/Assets/Editor/` and `src/erenshor/` should be modified. All other code, assets, and files from the original game MUST NOT be changed under any circumstances.

## Project Context

-   **Solo Developer**: Hobby project maintained by a single developer
-   **Zero Cost**: Everything must be free (SteamCMD, AssetRipper, Unity Personal, Google Sheets API)
-   **Automated Pipeline**: Full automation from Steam download to Google Sheets deployment
-   **Multi-Variant Support**: Handles main game, playtest, and demo versions separately
-   **Unity Constraints**: Non-Editor code cannot be included in git (belongs to game developer)
-   **Output**: SQLite databases and formatted data for wiki generation and spreadsheets

## Architecture

### Python CLI System

The project uses a **pure Python CLI** built with Typer:

```
┌────────────────────────────────────────────┐
│           Python CLI (Typer)               │
│  • Pipeline automation                     │
│  • System operations                       │
│  • Unity/SteamCMD/AssetRipper integration  │
│  • Database operations                     │
│  • Wiki operations                         │
│  • Google Sheets deployment                │
│  • Data formatting and transformation      │
└────────────────────────────────────────────┘
```

**Entry point**: `uv run erenshor` (console script via pyproject.toml)

### Directory Structure

```
erenshor/
├── .erenshor/                      # Project state (NOT in git)
│   ├── state.json                  # Pipeline state tracking
│   ├── config.local.toml           # User config overrides
│   └── logs/                       # Global logs
├── src/                            # Source code
│   ├── erenshor/                   # Python package
│   │   ├── cli/                    # Python CLI (Typer)
│   │   │   ├── main.py             # CLI entry point
│   │   │   ├── commands/           # Command implementations (extract, wiki, sheets, maps, backup)
│   │   │   ├── preconditions/      # Command precondition checks
│   │   │   └── context.py          # CLI context object
│   │   ├── application/            # Application layer
│   │   │   ├── generators/         # Wiki template generators (items, characters, spells, skills)
│   │   │   ├── formatters/         # Data formatters
│   │   │   │   └── sheets/         # Google Sheets formatters
│   │   │   │       └── queries/    # SQL query files (*.sql)
│   │   │   └── services/           # Business services (wiki, sheets, backup)
│   │   ├── domain/                 # Domain layer
│   │   │   ├── entities/           # Domain entities (item, character, spell, etc.)
│   │   │   └── value_objects/      # Value objects
│   │   ├── infrastructure/         # Infrastructure layer
│   │   │   ├── assetripper/        # AssetRipper automation
│   │   │   ├── steam/              # SteamCMD integration
│   │   │   ├── unity/              # Unity batch mode executor
│   │   │   ├── wiki/               # MediaWiki client
│   │   │   ├── publishers/         # Google Sheets publisher
│   │   │   ├── database/           # SQLite connection and repositories
│   │   │   ├── config/             # Configuration loader
│   │   │   └── logging/            # Logging setup
│   │   ├── registry/               # Entity-to-page resolver
│   │   │   ├── resolver.py         # Page title resolver
│   │   │   ├── operations.py       # Registry operations
│   │   │   └── item_classifier.py  # Item type classifier
│   │   └── shared/                 # Shared utilities
│   ├── Assets/Editor/              # Unity C# export scripts (symlinked to Unity)
│   │   ├── ExportBatch.cs          # Batch mode export entry
│   │   ├── Database/               # SQLite record models (ItemRecord, CharacterRecord, etc.)
│   │   └── ExportSystem/           # Asset scanning system
│   │       ├── AssetScanner.cs     # Main asset scanner
│   │       └── AssetScanner/Listener/  # Entity listeners (ItemListener, CharacterListener, etc.)
│   ├── mods/                       # BepInEx mods (C# plugins)
│   │   ├── CLAUDE.md               # Mod-specific documentation
│   │   ├── erenshor-mods.sln       # Visual Studio solution
│   │   └── InteractiveMapsCompanion/  # WebSocket companion for interactive maps
│   └── maps/                       # Interactive maps (SvelteKit web app)
├── variants/                       # Working directories (NOT in git)
│   ├── main/                       # Main game (App ID 2382520)
│   │   ├── game/                   # Downloaded from Steam
│   │   ├── unity/                  # Unity project from AssetRipper
│   │   │   └── Assets/Editor -> ../../../../src/Assets/Editor/
│   │   ├── wiki/                   # Wiki fetch/generate/deploy cache
│   │   │   ├── fetched/            # Pages fetched from MediaWiki
│   │   │   └── generated/          # Pages generated locally
│   │   ├── logs/                   # Variant-specific logs
│   │   └── erenshor-main.sqlite    # Exported database
│   ├── playtest/                   # Playtest (App ID 3090030)
│   └── demo/                       # Demo (App ID 2522260)
├── docs/                           # Documentation
│   ├── TROUBLESHOOTING.md          # Troubleshooting guide
│   ├── refactoring-plan/           # Refactoring documentation
│   └── reviews/                    # Code reviews
├── tests/                          # Python tests
│   ├── unit/                       # Unit tests
│   └── integration/                # Integration tests (requires database)
├── registry.db                     # Entity-to-page mapping database
├── config.toml                     # Main config (tracked in git)
├── pyproject.toml                  # Python dependencies and CLI entry point
└── README.md                       # User documentation
```

### Multi-Variant System

Three game variants with separate pipelines:

-   **main** (App ID 2382520): Production release
-   **playtest** (App ID 3090030): Beta/alpha testing
-   **demo** (App ID 2522260): Free demo version

Each variant maintains completely separate:

-   Game downloads (`variants/{variant}/game/`)
-   Unity projects (`variants/{variant}/unity/`)
-   Databases (`variants/{variant}/erenshor-{variant}.sqlite`)
-   Wiki caches (`variants/{variant}/wiki/fetched/` and `generated/`)
-   Logs (`variants/{variant}/logs/`)
-   Google Sheets spreadsheets (separate spreadsheet IDs in config)

## CLI Commands

All commands are pure Python via the Typer CLI:

```bash
# Main entry point
uv run erenshor --help              # Show all commands
uv run erenshor version             # Show version
uv run erenshor status              # Show system status
uv run erenshor doctor              # System health check

# Extract commands (download → rip → export)
uv run erenshor extract download    # Download from Steam via SteamCMD
uv run erenshor extract rip         # Extract Unity project via AssetRipper
uv run erenshor extract export      # Export to SQLite via Unity batch mode
uv run erenshor extract full        # Run complete pipeline

# Wiki operations
uv run erenshor wiki fetch          # Fetch wiki pages
uv run erenshor wiki generate       # Generate wiki pages locally
uv run erenshor wiki deploy         # Deploy wiki pages

# Google Sheets deployment
uv run erenshor sheets list         # List available sheets
uv run erenshor sheets deploy       # Deploy to Google Sheets

# Interactive Maps
uv run erenshor maps dev            # Start dev server
uv run erenshor maps preview        # Preview built site
uv run erenshor maps build          # Build for production
uv run erenshor maps deploy         # Deploy to Cloudflare static hosting

# BepInEx Mods (requires Mono on macOS)
cd src/mods
xbuild erenshor-mods.sln /p:Configuration=Debug    # Build mods in Debug
xbuild erenshor-mods.sln /p:Configuration=Release  # Build mods in Release

# Configuration
uv run erenshor config show         # View configuration

# Backup management
uv run erenshor backup list         # List backups

# Testing and documentation
uv run erenshor test                # Run tests
uv run erenshor docs                # Generate documentation
```

**Global Options**:

-   `--variant <variant>` - Specify variant (main, playtest, demo)
-   `--dry-run` - Preview without making changes
-   `--verbose` - Enable verbose output
-   `--quiet` - Suppress non-essential output

## Common Workflows

### Running Full Pipeline

```bash
# Run complete extraction pipeline (download → rip → export)
uv run erenshor extract full

# Run individual steps
uv run erenshor extract download          # Download from Steam
uv run erenshor extract rip               # Extract Unity project
uv run erenshor extract export            # Export to SQLite

# Update specific variant
uv run erenshor extract full --variant playtest

# Deploy to Google Sheets after export
uv run erenshor extract export
uv run erenshor sheets deploy --all-sheets
```

### Adding New Export Type

1. Create record class: `src/Assets/Editor/Database/MyRecord.cs`
2. Create listener: `src/Assets/Editor/ExportSystem/AssetScanner/Listener/MyListener.cs`
3. Register in `ExportBatch.cs` (CLI) or `AssetScannerExporterWindow.cs` (GUI)
4. Test: `uv run erenshor extract export`

### Adding New Google Sheets Query

1. Create SQL file: `src/erenshor/application/formatters/sheets/queries/my-sheet.sql`
2. Write SQL query (returns header + data rows)
3. Deploy: `uv run erenshor sheets deploy --sheets my-sheet`

### Adding New CLI Command

Add command in `src/erenshor/cli/commands/`:

```python
import typer
from typing_extensions import Annotated

app = typer.Typer(help="My new command group")

@app.command()
def my_action(
    variant: Annotated[str, typer.Option(help="Game variant")] = "main",
    dry_run: Annotated[bool, typer.Option(help="Preview only")] = False,
) -> None:
    """Perform my action."""
    # Implementation
    typer.echo(f"Running action on {variant}")
```

Register in `src/erenshor/cli/main.py`:

```python
from erenshor.cli.commands import my_command

app.add_typer(my_command.app, name="my-command")
```

## Data Mining Architecture

### Unity Export System

**Location**: `src/Assets/Editor/ExportSystem/`

**Core Components:**

-   `ExportBatch.cs` - Entry point for batch mode exports
-   `AssetScanner.cs` - Scans Unity project for game assets
-   `Repository.cs` - Database operations and table management

**Listeners**: Each listener extracts specific game data:

-   `ItemListener.cs` - Items and equipment
-   `CharacterListener.cs` - NPCs and creatures
-   `SpellListener.cs` - Spells and abilities
-   `SkillListener.cs` - Skills and professions
-   `QuestListener.cs` - Quest data
-   `SpawnPointListener.cs` - Enemy spawn locations
-   `LootTableListener.cs` - Drop tables
-   `TeleportLocListener.cs` - Teleport locations
-   `ItemBagListener.cs` - Item bag definitions
-   `BookListener.cs` - In-game books
-   `AchievementTriggerListener.cs` - Achievement triggers
-   `AscensionListener.cs` - Ascension system
-   `ClassListener.cs` - Character classes
-   `WorldFactionListener.cs` - Faction data
-   And 15+ more...

### Database Schema

**Junction Tables**: junction tables for many-to-many relationships:

-   Character abilities: `CharacterAttackSpells`, `CharacterBuffSpells`
-   Quest relationships: `QuestRequiredItems`, `QuestRewards`
-   Class restrictions: `ItemClasses`, `SpellClasses`
-   Spawn mechanics: `SpawnPointCharacters`, `SpawnPointPatrolPoints`

**Total**: 20,600+ normalized rows across all junction tables.

### Google Sheets Deployment

**Architecture**: SQL queries → Formatter → Publisher → Google Sheets

**Components**:

1. **SQL Query Files**: `src/erenshor/application/formatters/sheets/queries/*.sql`
2. **SheetsFormatter**: Executes SQL, formats results as spreadsheet rows
3. **GoogleSheetsPublisher**: Publishes via Google Sheets API v4
4. **SheetsDeployService**: Orchestrates deployment workflow

**Available Sheets** (20+ sheets):
- items, characters, spells, skills
- quests, achievement-triggers, ascensions
- drop-chances, spawn-points, loot tables
- teleports, item-bags, books
- fishing, mining-nodes, treasure-locations, wishing-wells
- classes, factions, zones
- secret-passages, character-dialogs

## Configuration

Two-layer configuration system (NO environment variables):

1. `config.toml` (project defaults, tracked in git)
2. `.erenshor/config.local.toml` (user overrides, NOT tracked in git)

**Key config values**:

```toml
[global.unity]
path = "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity"
version = "2021.3.45f2"

[global.google_sheets]
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
2. **Pure Python implementation** - All CLI commands are Python via Typer
3. **Test exports** - Verify exported data matches game
4. **Maintain Unity 2021.3.45f2 compatibility** - Game's exact version
5. **Work with variants** - Test changes across main, playtest, and demo
6. **Follow Python best practices** - Type hints, tests, domain-driven design
7. **Use uv for dependencies** - Preferred over pip for package management

## Code Quality Principles

1. **Be Thorough - Validate Every Claim**

    - NEVER make claims or decisions without validating them against actual code
    - When checking if something exists: grep for it, read the file, verify the implementation
    - When saying something is "not used": search the entire codebase, check imports, verify no references exist
    - Half-hearted checking is unacceptable - if you make a statement, it must be backed by verified data
    - Example: Don't claim ".env is not used" after only checking one file - search ALL Python files for dotenv/load_dotenv

2. **Fail Fast and Loud**

    - No fallback functionality that hides errors
    - Fail immediately with clear error messages

3. **No Backward Compatibility**

    - Clean breaks when changing behavior
    - No legacy code paths "just in case"
    - One-off migration scripts OK, but don't leave migration code

4. **Keep It Simple**

    - No extra config options, flags, or features
    - Suggest improvements proactively, but only implement after discussion

5. **Clean Cuts Only**

    - Remove old code entirely when refactoring
    - No "legacy support" or "fallback paths"
    - Less code = less maintenance

6. **Minimal Comments**

    - Don't comment what's obvious from code
    - No development history in comments
    - Comments explain _why_, not _what_

7. **Atomic Commits**

    - Commit regularly with logical, focused changes
    - One concept per commit
    - Clear, concise commit messages

8. **Fix All Errors**
    - Don't ignore errors, even if you didn't introduce them
    - When you discover bugs or validation failures during testing, fix them
    - Never leave broken functionality unaddressed

## Testing

### Local Testing

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

### Continuous Integration

The project uses GitHub Actions for automated testing on every push and pull request:

-   **Linting**: Ruff checks code style and formatting
-   **Type Checking**: MyPy validates type hints
-   **Security**: Gitleaks scans for secrets
-   **Testing**: Full pytest suite with coverage reporting

CI runs on all pushes to main and all pull requests. View results at:
https://github.com/glockyco/erenshor-data-mining/actions

### Pre-commit Hooks

Pre-commit hooks run fast local checks only (no tests):

```bash
# Install hooks
uv run pre-commit install

# Run manually
uv run pre-commit run --all-files
```

Hooks include:

-   Ruff linting and formatting
-   MyPy type checking
-   Gitleaks secret scanning

Tests are NOT run in pre-commit (too slow). They run in CI instead.

## Python Environment

**Preferred**: Use `uv` for automatic dependency management

```bash
uv sync --dev              # Install dependencies
uv run pytest              # Run tests
uv run erenshor --help     # Run CLI via console script
```

**Alternative invocations**:

```bash
# Via module (if not installed as console script)
uv run python -m erenshor.cli.main --help

# Direct pytest (if uv run is slow)
uv run pytest
```

## Debugging

### Export Issues

1. Check logs: `variants/{variant}/logs/export_*.log`
2. Check global logs: `.erenshor/logs/`
3. Verify Unity version: `uv run erenshor config show`
4. Check ScriptableObject references are valid
5. Use SQLite viewer to inspect database
6. Run Unity in GUI mode for console errors

### CLI Issues

```bash
# Check system health
uv run erenshor doctor

# View configuration
uv run erenshor config show

# Enable verbose logging
uv run erenshor --verbose <command>
```

### Google Sheets Issues

-   **Authentication**: Check `~/.config/erenshor/google-credentials.json` exists
-   **Permissions**: Service account needs **Editor** access (not just Viewer)
-   **Dry-run**: Test without writing: `uv run erenshor sheets deploy --dry-run`

## Important Constraints

1. **Unity Version**: MUST use Unity 2021.3.45f2 (game's exact version)
2. **Steam Credentials**: Requires valid Steam account with game ownership
3. **Git Ignore**: All variant directories, databases, `.erenshor/` not tracked
4. **Symlinks**: C# files symlinked, DLLs copied (Unity assembly loading limitation)
5. **Batch Mode**: Unity exports run headless via CLI (no GUI)
6. **Service Account**: Google Sheets requires Editor access for deployment

## Key Files

**Python CLI**:

-   `src/erenshor/cli/main.py` - Main CLI entry point (Typer)
-   `src/erenshor/cli/commands/extract.py` - Extract commands (download, rip, export, full)
-   `src/erenshor/cli/commands/wiki.py` - Wiki commands (fetch, generate, deploy)
-   `src/erenshor/cli/commands/sheets.py` - Google Sheets commands (list, deploy)
-   `src/erenshor/cli/commands/maps.py` - Interactive maps commands (dev, build, preview, deploy)
-   `src/erenshor/cli/commands/backup.py` - Backup commands
-   `src/erenshor/cli/preconditions/` - Command precondition checks

**Python Application**:

-   `src/erenshor/application/services/wiki_service.py` - Three-stage wiki workflow
-   `src/erenshor/application/services/sheets_service.py` - Google Sheets deployment
-   `src/erenshor/application/generators/item_template_generator.py` - Item wiki templates
-   `src/erenshor/application/generators/character_template_generator.py` - Character wiki templates
-   `src/erenshor/application/generators/spell_template_generator.py` - Spell wiki templates
-   `src/erenshor/application/generators/skill_template_generator.py` - Skill wiki templates
-   `src/erenshor/application/generators/field_preservation.py` - Preserve manually-edited fields
-   `src/erenshor/application/formatters/sheets/formatter.py` - SQL to sheets formatter
-   `src/erenshor/application/formatters/sheets/queries/*.sql` - SQL query files (20+ sheets)

**Python Infrastructure**:

-   `src/erenshor/infrastructure/steam/` - SteamCMD integration
-   `src/erenshor/infrastructure/assetripper/` - AssetRipper automation
-   `src/erenshor/infrastructure/unity/` - Unity batch mode executor
-   `src/erenshor/infrastructure/wiki/client.py` - MediaWiki API client
-   `src/erenshor/infrastructure/publishers/google_sheets.py` - Google Sheets API v4 publisher
-   `src/erenshor/infrastructure/database/repositories/` - SQLite repositories (items, characters, etc.)
-   `src/erenshor/infrastructure/config/loader.py` - Two-layer TOML config loader

**Python Registry**:

-   `src/erenshor/registry/resolver.py` - Entity-to-page title resolver
-   `src/erenshor/registry/operations.py` - Registry CRUD operations
-   `src/erenshor/registry/item_classifier.py` - Item type classification

**Unity Export**:

-   `src/Assets/Editor/ExportBatch.cs` - Batch export entry point
-   `src/Assets/Editor/ExportSystem/AssetScanner.cs` - Asset scanner
-   `src/Assets/Editor/ExportSystem/AssetScanner/Listener/*.cs` - Entity listeners (30+ listeners)
-   `src/Assets/Editor/Database/*.cs` - SQLite record models (40+ tables)

**Configuration**:

-   `config.toml` - Main configuration (tracked in git)
-   `.erenshor/config.local.toml` - User overrides (NOT tracked)
-   `registry.db` - Entity-to-page mapping database
-   `pyproject.toml` - Python dependencies and console script entry point

## Quick Reference

```bash
# System commands
uv run erenshor version                 # Show version
uv run erenshor status                  # Show status
uv run erenshor doctor                  # Health check
uv run erenshor config show             # View configuration

# Extraction pipeline
uv run erenshor extract full            # Complete pipeline
uv run erenshor extract download        # Download from Steam
uv run erenshor extract rip             # Extract Unity project
uv run erenshor extract export          # Export to SQLite

# Wiki and Sheets
uv run erenshor wiki fetch              # Fetch wiki pages
uv run erenshor wiki generate           # Generate wiki pages locally
uv run erenshor wiki deploy             # Deploy wiki pages
uv run erenshor sheets list             # List available sheets
uv run erenshor sheets deploy --all-sheets  # Deploy to Google Sheets

# Interactive Maps
uv run erenshor maps dev                # Start dev server
uv run erenshor maps preview            # Preview built site
uv run erenshor maps build              # Build for production
uv run erenshor maps deploy             # Deploy to Cloudflare static hosting

# Testing
uv run pytest                           # Run all tests
uv run pytest --cov                     # With coverage
uv run erenshor test                    # Run tests via CLI

# Backup & Documentation
uv run erenshor backup list             # List backups
uv run erenshor docs                    # Generate documentation
```

## Notes

For AI assistance: The project is pure Python using Typer for the CLI. All orchestration, system operations, and business logic are in Python. The legacy bash CLI has been moved to `legacy/cli/` and is not used. Always respect the "only modify src/" constraint.
