# Phase 1: Foundation - Detailed Task Breakdown

**Status**: Ready to Execute
**Estimated Duration**: 2-3 weeks
**Last Updated**: 2025-10-16

---

## Overview

Phase 1 establishes the foundation for the complete rewrite. This phase focuses on:
1. Archiving the old system
2. Creating new Python package structure
3. Implementing two-layer TOML configuration
4. Setting up Loguru logging
5. Creating CLI skeleton with Typer
6. Merging erenshor-maps into monorepo
7. Setting up pytest infrastructure
8. Laying foundation for resource-name-based registry

**Key Principle**: Each task is atomic, independently committable, and builds on previous tasks.

---

## Task Dependencies

```
Task 1 (Archive) → Task 2 (Directory Structure)
                ↓
Task 3 (Pre-commit) ← Task 2
                ↓
Task 4 (pyproject.toml) → Task 5 (Basic Config)
                       ↓
Task 6 (Config Loader) → Task 7 (Path Resolution)
                       ↓
Task 8 (Config Tests) ← Task 7
                       ↓
Task 9 (Logging Setup) → Task 10 (Logging Utilities)
                       ↓
Task 11 (Logging Tests) ← Task 10
                       ↓
Task 12 (CLI Entry) → Task 13 (Command Groups)
                    ↓
Task 14 (Placeholder Commands) → Task 15 (Basic Commands)
                               ↓
Task 16 (Registry Foundation) → Task 17 (Resource Names)
                              ↓
Task 18 (Registry Operations) → Task 19 (Registry Tests)
                              ↓
Task 20 (Pytest Config) → Task 21 (Test Fixtures)
                        ↓
Task 22 (Maps Integration) → Task 23 (Maps Config)
                           ↓
Task 24 (Maps CLI) → Task 25 (Final Integration)
```

---

## Tasks (Ordered by Dependencies)

### Task 1: Archive Old System

**Goal**: Move current implementation to `legacy/` to preserve history while starting fresh.

**Actions**:
- Create `legacy/` directory
- Move the following to `legacy/`:
  - `cli/` (entire Bash CLI)
  - `src/erenshor/` (old Python package)
  - `src/export.sh` (Unity export wrapper)
  - `config.toml` → `legacy/config.toml.old`
  - `pyproject.toml` → `legacy/pyproject.toml.old`
  - `.pre-commit-config.yaml` → `legacy/pre-commit-config.yaml.old`
- Keep in place (not archived):
  - `src/Assets/` (Unity Editor scripts - will be updated later)
  - `variants/` (working directories)
  - `tests/` (will be rewritten)
  - `.erenshor/` (state directory)
  - `docs/` (documentation)
  - Git files (`.git/`, `.gitignore`, `.gitattributes`)
  - Python environment (`.venv/`, `.python-version`)
  - IDE files (`.idea/`, `__pycache__/`)
- Update `.gitignore` if needed

**Files Created/Modified**:
- `legacy/` (directory created)
- `legacy/cli/`
- `legacy/src/erenshor/`
- `legacy/export.sh`
- `legacy/config.toml.old`
- `legacy/pyproject.toml.old`
- `legacy/pre-commit-config.yaml.old`
- `.gitignore` (if updated)

**Dependencies**: None

**Success Criteria**:
- `legacy/` directory exists with archived code
- `src/erenshor/` no longer exists (moved to legacy)
- `cli/` no longer exists (moved to legacy)
- `src/Assets/` still exists (not archived)
- All other important files preserved
- Git history intact

**Commit Message**: "refactor: archive old system to legacy/"

**Estimated Time**: 15 minutes

---

### Task 2: Create New Directory Structure

**Goal**: Establish the new project structure with proper package layout.

**Actions**:
- Create new directory structure (matches approved plan section 1.2):
  ```
  src/
    erenshor/
      __init__.py
      application/
        __init__.py
        formatters/
          __init__.py
          sheets/
            __init__.py
            queries/
        generators/
          __init__.py
        services/
          __init__.py
      cli/
        __init__.py
        commands/
          __init__.py
      domain/
        __init__.py
        entities/
          __init__.py
      infrastructure/
        __init__.py
        database/
          __init__.py
        publishers/
          __init__.py
        storage/
          __init__.py
      outputs/
        __init__.py
        wiki/
          __init__.py
        sheets/
          __init__.py
        maps/
          __init__.py
      registry/
        __init__.py
  tests/
    __init__.py
    unit/
      __init__.py
    integration/
      __init__.py
  ```
- Add docstrings to key `__init__.py` files explaining module purpose

**Note**: `infrastructure/config/` is NOT created in this task - it will be created in Task 5 when implementing the config system.

**Files Created/Modified**:
- All directory structure and `__init__.py` files listed above

**Dependencies**: Task 1 (Archive)

**Success Criteria**:
- All directories exist
- All `__init__.py` files present
- Clean package structure
- Ready for code

**Commit Message**: "refactor: create new package structure"

**Estimated Time**: 20 minutes

---

### Task 3: Set Up Pre-commit Hooks

**Goal**: Configure code quality tools early to maintain standards from the start.

**Actions**:
- Create `.pre-commit-config.yaml`:
  ```yaml
  repos:
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.8.4
      hooks:
        - id: ruff
          args: [--fix]
        - id: ruff-format
    - repo: https://github.com/pre-commit/mirrors-mypy
      rev: v1.13.0
      hooks:
        - id: mypy
          additional_dependencies: [types-all]
          args: [--strict]
  ```
- Install pre-commit hooks: `uv run pre-commit install`
- Test hooks on empty files

**Files Created/Modified**:
- `.pre-commit-config.yaml`

**Dependencies**: Task 2 (Directory Structure)

**Success Criteria**:
- Pre-commit hooks installed
- Hooks run successfully on commit
- Ruff and mypy configured
- No errors on empty project

**Commit Message**: "build: configure pre-commit hooks with ruff and mypy"

**Estimated Time**: 15 minutes

---

### Task 4: Create pyproject.toml

**Goal**: Define project metadata, dependencies, and tool configurations.

**Actions**:
- Create `pyproject.toml` with:
  - Project metadata (name: "erenshor", description, version: "2.0.0-alpha.1")
  - Python version requirement: `>=3.13`
  - Dependencies:
    - typer[all]>=0.12.0 (CLI framework)
    - loguru>=0.7.0 (logging)
    - pydantic>=2.0.0 (data validation)
    - pydantic-settings>=2.0.0 (settings management)
    - tomli>=2.0.0 (TOML parsing for Python <3.11)
    - httpx>=0.27.0 (HTTP client)
    - sqlmodel>=0.0.24 (ORM)
    - jinja2>=3.1.0 (templates)
    - mwparserfromhell>=0.6.0 (wiki parsing)
    - pillow>=11.0.0 (image processing)
    - google-auth>=2.0.0 (Google API)
    - google-api-python-client>=2.0.0 (Google Sheets)
    - platformdirs>=4.0.0 (cross-platform paths)
    - rich>=13.0.0 (terminal formatting)
  - Dev dependencies:
    - pytest>=8.0.0
    - pytest-cov>=7.0.0
    - mypy>=1.17.0
    - ruff>=0.8.0
    - pre-commit>=4.0.0
    - types-* (for mypy type stubs)
  - Tool configurations:
    - [tool.ruff] - linting rules
    - [tool.ruff.format] - formatting
    - [tool.mypy] - strict type checking
    - [tool.pytest.ini_options] - test configuration
    - [tool.coverage.run] - coverage settings
  - Entry point: `erenshor = "erenshor.cli.main:app"`
  - Build system: hatchling

**Files Created/Modified**:
- `pyproject.toml`

**Dependencies**: Task 2 (Directory Structure), Task 3 (Pre-commit)

**Success Criteria**:
- `pyproject.toml` is valid
- `uv sync` installs all dependencies
- Entry point defined
- All tools configured
- Can run `uv run python -m erenshor.cli.main --help` (will fail, but package loads)

**Commit Message**: "build: add pyproject.toml with dependencies and tool config"

**Estimated Time**: 30 minutes

---

### Task 5: Create Basic Config Schema

**Goal**: Define the configuration file structure with Pydantic models.

**Actions**:
- Create `src/erenshor/infrastructure/config/__init__.py`
- Create `src/erenshor/infrastructure/config/schema.py`:
  - `GlobalConfig` - Global settings
  - `PathsConfig` - Path settings
  - `SteamConfig` - Steam settings
  - `UnityConfig` - Unity settings
  - `AssetRipperConfig` - AssetRipper settings
  - `DatabaseConfig` - Database settings
  - `MediaWikiConfig` - MediaWiki settings
  - `GoogleSheetsConfig` - Google Sheets settings
  - `BehaviorConfig` - Behavior settings
  - `LoggingConfig` - Logging settings
  - `VariantConfig` - Variant-specific config
  - `Config` - Root config model with variants dict
- Use Pydantic `BaseModel` with validation
- Add docstrings explaining each field
- No loading logic yet, just schema

**Files Created/Modified**:
- `src/erenshor/infrastructure/config/__init__.py`
- `src/erenshor/infrastructure/config/schema.py`

**Dependencies**: Task 4 (pyproject.toml)

**Success Criteria**:
- All config models defined
- Type hints complete
- Validation rules specified
- Models can be instantiated programmatically
- No runtime errors when importing

**Commit Message**: "feat(config): define configuration schema with Pydantic models"

**Estimated Time**: 45 minutes

---

### Task 6: Implement Config Loader

**Goal**: Load configuration from TOML files with two-layer override system.

**Actions**:
- Create `src/erenshor/infrastructure/config/loader.py`:
  - `load_config()` - Main loading function
  - Load `config.toml` (project defaults)
  - Load `config.local.toml` (user overrides) if exists
  - Merge configs (local overrides defaults)
  - Parse with `tomli` (Python 3.10 compat) or `tomllib` (3.11+)
  - Validate with Pydantic schema
  - Return `Config` instance
- Handle missing files gracefully
- Provide clear error messages for invalid TOML
- No environment variable support (per requirements)

**Files Created/Modified**:
- `src/erenshor/infrastructure/config/loader.py`

**Dependencies**: Task 5 (Config Schema)

**Success Criteria**:
- `load_config()` loads config.toml successfully
- Local overrides work correctly
- Returns validated Config instance
- Errors are clear and actionable
- Can be imported and called

**Commit Message**: "feat(config): implement two-layer TOML config loader"

**Estimated Time**: 40 minutes

---

### Task 7: Implement Path Resolution

**Goal**: Resolve special path variables ($REPO_ROOT, $HOME, ~) to absolute paths.

**Actions**:
- Create `src/erenshor/infrastructure/config/paths.py`:
  - `resolve_path(path: str, repo_root: Path) -> Path`
  - Support `$REPO_ROOT` expansion
  - Support `$HOME` and `~` expansion
  - Convert to absolute paths
  - Validate paths exist (optional flag)
  - Return `Path` objects (not strings)
- Add path resolution to config loader
- Create strongly-typed path accessors on Config models
- Add validation for critical paths (Unity, database, etc.)

**Files Created/Modified**:
- `src/erenshor/infrastructure/config/paths.py`
- `src/erenshor/infrastructure/config/loader.py` (updated)

**Dependencies**: Task 6 (Config Loader)

**Success Criteria**:
- All path variables expand correctly
- Absolute paths returned
- Path validation works
- Config objects have typed path properties
- No string path manipulation in business logic

**Commit Message**: "feat(config): add path resolution with variable expansion"

**Estimated Time**: 35 minutes

---

### Task 8: Add Config Tests

**Goal**: Ensure configuration system works correctly with comprehensive tests.

**Actions**:
- Create `tests/unit/infrastructure/config/test_schema.py`:
  - Test model validation
  - Test invalid data rejection
  - Test default values
- Create `tests/unit/infrastructure/config/test_loader.py`:
  - Test loading valid TOML
  - Test two-layer override
  - Test missing files
  - Test invalid TOML
  - Test merge behavior
- Create `tests/unit/infrastructure/config/test_paths.py`:
  - Test path resolution
  - Test $REPO_ROOT expansion
  - Test $HOME and ~ expansion
  - Test absolute path conversion
  - Test path validation
- Create test fixtures (sample TOML files)

**Files Created/Modified**:
- `tests/unit/infrastructure/__init__.py`
- `tests/unit/infrastructure/config/__init__.py`
- `tests/unit/infrastructure/config/test_schema.py`
- `tests/unit/infrastructure/config/test_loader.py`
- `tests/unit/infrastructure/config/test_paths.py`
- `tests/fixtures/config/` (test TOML files)

**Dependencies**: Task 7 (Path Resolution)

**Success Criteria**:
- All tests pass
- >80% coverage for config module
- Edge cases handled
- Clear test names and assertions

**Commit Message**: "test(config): add comprehensive config system tests"

**Estimated Time**: 50 minutes

---

### Task 9: Set Up Loguru Logging

**Goal**: Configure Loguru as the logging backend with appropriate defaults.

**Actions**:
- Create `src/erenshor/infrastructure/logging/__init__.py`
- Create `src/erenshor/infrastructure/logging/setup.py`:
  - `setup_logging(level: str = "INFO", verbose: bool = True)`
  - Configure Loguru with:
    - INFO level by default (verbose mode)
    - Colorized output
    - Structured format: `{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}`
    - Rotation: 10 MB per file
    - Retention: 7 days
    - Compression: gzip
  - Write logs to variant-specific log files
  - Also log to stderr for console output
  - Support DEBUG level via config
- Integrate with config system (read log level from config)

**Files Created/Modified**:
- `src/erenshor/infrastructure/logging/__init__.py`
- `src/erenshor/infrastructure/logging/setup.py`

**Dependencies**: Task 7 (Path Resolution)

**Success Criteria**:
- Loguru configured correctly
- Logs written to files
- Console output formatted nicely
- Log rotation works
- Can change level via config

**Commit Message**: "feat(logging): configure Loguru with file rotation and console output"

**Estimated Time**: 35 minutes

---

### Task 10: Create Logging Utilities

**Goal**: Provide logging helpers for common patterns.

**Actions**:
- Create `src/erenshor/infrastructure/logging/utils.py`:
  - `log_command_start(command: str, **context)` - Log command execution start
  - `log_command_end(command: str, duration: float)` - Log command completion
  - `log_error(error: Exception, context: dict)` - Log errors with context
  - `log_progress(message: str, current: int, total: int)` - Log progress
  - Context manager for operation logging
  - Decorators for function logging (optional, if useful)
- Add typing for all functions
- Include examples in docstrings

**Files Created/Modified**:
- `src/erenshor/infrastructure/logging/utils.py`

**Dependencies**: Task 9 (Logging Setup)

**Success Criteria**:
- All utility functions work
- Clean, reusable API
- Well-documented
- Type hints complete

**Commit Message**: "feat(logging): add logging utility functions and helpers"

**Estimated Time**: 30 minutes

---

### Task 11: Add Logging Tests

**Goal**: Test logging configuration and utilities.

**Actions**:
- Create `tests/unit/infrastructure/logging/__init__.py`
- Create `tests/unit/infrastructure/logging/test_setup.py`:
  - Test logging setup
  - Test log level configuration
  - Test file output
  - Test console output
  - Test log rotation (basic check)
- Create `tests/unit/infrastructure/logging/test_utils.py`:
  - Test command logging
  - Test error logging
  - Test progress logging
  - Test context managers
- Use `caplog` fixture for log capture

**Files Created/Modified**:
- `tests/unit/infrastructure/logging/__init__.py`
- `tests/unit/infrastructure/logging/test_setup.py`
- `tests/unit/infrastructure/logging/test_utils.py`

**Dependencies**: Task 10 (Logging Utilities)

**Success Criteria**:
- All tests pass
- Logging behavior verified
- Edge cases covered
- >80% coverage

**Commit Message**: "test(logging): add logging system tests"

**Estimated Time**: 40 minutes

---

### Task 12: Create CLI Entry Point

**Goal**: Set up Typer CLI framework with main entry point.

**Actions**:
- Create `src/erenshor/cli/main.py`:
  - Create Typer `app` instance
  - Add `--version` callback
  - Add `--variant` global option (default: "main")
  - Add `--dry-run` global option (default: False)
  - Add `--verbose` / `--quiet` log level options
  - Initialize logging on startup
  - Load config on startup
  - Handle global exceptions gracefully
  - Show helpful error messages
- Create `src/erenshor/cli/context.py`:
  - `CLIContext` class to hold config, variant, dry_run state
  - Pass context through commands
- Update entry point in pyproject.toml

**Files Created/Modified**:
- `src/erenshor/cli/main.py`
- `src/erenshor/cli/context.py`
- `pyproject.toml` (verify entry point)

**Dependencies**: Task 10 (Logging Utilities)

**Success Criteria**:
- `erenshor --help` shows help
- `erenshor --version` shows version
- Global options work
- Config loads on startup
- Logging initializes correctly
- Clean error handling

**Commit Message**: "feat(cli): create Typer CLI entry point with global options"

**Estimated Time**: 45 minutes

---

### Task 13: Add Command Groups

**Goal**: Organize CLI commands into logical groups.

**Actions**:
- Create command group modules:
  - `src/erenshor/cli/commands/extract.py` - Extraction commands
  - `src/erenshor/cli/commands/wiki.py` - Wiki commands
  - `src/erenshor/cli/commands/sheets.py` - Google Sheets commands
  - `src/erenshor/cli/commands/maps.py` - Maps commands
  - `src/erenshor/cli/commands/info.py` - Status/info commands
  - `src/erenshor/cli/commands/test.py` - Testing commands
- Create Typer sub-apps for each group
- Register sub-apps in main.py:
  ```python
  app.add_typer(extract.app, name="extract")
  app.add_typer(wiki.app, name="wiki")
  app.add_typer(sheets.app, name="sheets")
  app.add_typer(maps.app, name="maps")
  # info commands added directly to main app
  # test commands added directly to main app
  ```
- Add docstrings to each command group

**Files Created/Modified**:
- `src/erenshor/cli/commands/extract.py`
- `src/erenshor/cli/commands/wiki.py`
- `src/erenshor/cli/commands/sheets.py`
- `src/erenshor/cli/commands/maps.py`
- `src/erenshor/cli/commands/info.py`
- `src/erenshor/cli/commands/test.py`
- `src/erenshor/cli/main.py` (updated)

**Dependencies**: Task 12 (CLI Entry Point)

**Success Criteria**:
- All command groups registered
- `erenshor extract --help` shows extract commands
- `erenshor wiki --help` shows wiki commands
- `erenshor sheets --help` shows sheets commands
- `erenshor maps --help` shows maps commands
- Help text clear and organized

**Commit Message**: "feat(cli): add command groups for extract, wiki, sheets, and maps"

**Estimated Time**: 35 minutes

---

### Task 14: Add Placeholder Commands

**Goal**: Create all command stubs to establish CLI structure.

**Actions**:
- Add commands to each group (stubs only, no implementation):
  - **Extract**: `full`, `download`, `rip`, `export`
  - **Wiki**: `fetch`, `update`, `push`, `conflicts`, `resolve-conflict`
  - **Sheets**: `list`, `deploy`
  - **Maps**: `dev`, `preview`, `build`, `deploy`
  - **Info** (main app): `status`, `config show`, `doctor`, `backup info`
  - **Test** (main app): `test`, `test unit`, `test integration`
  - **Docs** (main app): `docs generate`
- Each command:
  - Accepts appropriate options/arguments
  - Prints "Not yet implemented: [command]"
  - Returns exit code 0
  - Has docstring describing what it will do

**Files Created/Modified**:
- All command files created in Task 13 (updated with stubs)

**Dependencies**: Task 13 (Command Groups)

**Success Criteria**:
- All commands appear in `--help`
- All commands execute without error
- Clear "not implemented" messages
- Command signatures correct (args, options)
- Docstrings present

**Commit Message**: "feat(cli): add placeholder commands for all CLI operations"

**Estimated Time**: 50 minutes

---

### Task 15: Implement Basic Commands

**Goal**: Implement simple informational commands that don't require full pipeline.

**Actions**:
- Implement `status` command:
  - Show config file locations
  - Show variant configuration
  - Show database existence
  - Show log file locations
  - Show Unity/Steam/AssetRipper paths
- Implement `config show` command:
  - Pretty-print config with Rich
  - Support filtering by key
  - Show resolved paths
  - Highlight local overrides
- Implement `doctor` command:
  - Check Unity installation
  - Check database existence
  - Check config validity
  - Check log directory access
  - Report health status
- Implement `backup info` command:
  - List available backups
  - Show backup metadata
  - Show backup sizes
- Implement `test` command:
  - Run pytest with appropriate options
  - Support unit/integration filtering
  - Show coverage report

**Files Created/Modified**:
- `src/erenshor/cli/commands/info.py` (updated)
- `src/erenshor/cli/commands/test.py` (updated)

**Dependencies**: Task 14 (Placeholder Commands)

**Success Criteria**:
- All commands work correctly
- Output is clear and formatted nicely
- Errors handled gracefully
- Commands useful for debugging

**Commit Message**: "feat(cli): implement status, config, doctor, backup, and test commands"

**Estimated Time**: 60 minutes

---

### Task 16: Create Registry Data Structures

**Goal**: Define the registry database schema and models.

**Actions**:
- Create `src/erenshor/registry/schema.py`:
  - `EntityType` enum (item, spell, skill, character, quest, faction, etc.)
  - `EntityRecord` table:
    - id (primary key)
    - entity_type (EntityType)
    - resource_name (stable key)
    - display_name
    - wiki_page_title (nullable)
    - first_seen (timestamp)
    - last_seen (timestamp)
    - is_manual (boolean - manually created page)
  - `MigrationRecord` table (from mapping.json):
    - id
    - old_key
    - new_key
    - migration_date
  - `ConflictRecord` table:
    - id
    - entity_ids (list of conflicting entity IDs)
    - conflict_type (name_collision, ambiguous_reference)
    - resolved (boolean)
    - resolution (nullable - chosen entity)
- Use SQLModel for ORM
- Add indexes for performance

**Files Created/Modified**:
- `src/erenshor/registry/schema.py`

**Dependencies**: Task 15 (Basic Commands) - establishes project is functional

**Success Criteria**:
- All models defined
- Relationships clear
- Indexes specified
- Type hints complete
- Can create tables in SQLite

**Commit Message**: "feat(registry): define registry database schema"

**Estimated Time**: 40 minutes

---

### Task 17: Implement Resource Name Handling

**Goal**: Add utilities for working with resource names as stable identifiers.

**Actions**:
- Create `src/erenshor/registry/resource_names.py`:
  - `build_stable_key(entity_type: EntityType, resource_name: str) -> str`
    - Format: `{entity_type}:{resource_name}`
  - `parse_stable_key(key: str) -> tuple[EntityType, str]`
  - `extract_resource_name(entity_data: dict) -> str`
    - Items/Spells/Skills: Use ResourceName field
    - Characters: Use ObjectName field
    - Quests: Use DBName field (NEW)
    - Factions: Use REFNAME field (NEW)
  - Validation functions
  - Normalization functions (handle case, whitespace)
- Add docstrings with examples
- Add type hints

**Files Created/Modified**:
- `src/erenshor/registry/resource_names.py`

**Dependencies**: Task 16 (Registry Data Structures)

**Success Criteria**:
- All functions work correctly
- Resource name extraction handles all entity types
- Quest DBName support works
- Faction REFNAME support works
- Validation catches invalid keys
- Well-documented

**Commit Message**: "feat(registry): implement resource name utilities for stable IDs"

**Estimated Time**: 40 minutes

---

### Task 18: Implement Registry Operations

**Goal**: Add core registry operations (create, read, update, conflict detection).

**Actions**:
- Create `src/erenshor/registry/operations.py`:
  - `initialize_registry(db_path: Path)` - Create registry database
  - `register_entity(...)` - Add/update entity
  - `get_entity(stable_key: str)` - Retrieve entity
  - `find_conflicts()` - Detect name conflicts
  - `resolve_conflict(conflict_id: int, chosen_entity_id: int)` - Resolve conflict
  - `migrate_from_mapping_json(mapping_path: Path)` - Import old mappings
  - `list_entities(entity_type: EntityType = None)` - Query entities
- Use SQLModel for database access
- Add proper error handling
- Log operations

**Files Created/Modified**:
- `src/erenshor/registry/operations.py`

**Dependencies**: Task 17 (Resource Name Handling)

**Success Criteria**:
- All operations work
- Database transactions handled correctly
- Conflicts detected properly
- mapping.json migration works
- Operations logged
- Type-safe API

**Commit Message**: "feat(registry): implement core registry operations"

**Estimated Time**: 60 minutes

---

### Task 19: Add Registry Tests

**Goal**: Test registry functionality comprehensively.

**Actions**:
- Create `tests/unit/registry/__init__.py`
- Create `tests/unit/registry/test_schema.py`:
  - Test model creation
  - Test relationships
  - Test constraints
- Create `tests/unit/registry/test_resource_names.py`:
  - Test stable key building
  - Test stable key parsing
  - Test resource name extraction (all entity types)
  - Test quest DBName extraction
  - Test faction REFNAME extraction
  - Test validation
- Create `tests/unit/registry/test_operations.py`:
  - Test registry initialization
  - Test entity registration
  - Test entity retrieval
  - Test conflict detection
  - Test conflict resolution
  - Test mapping.json migration
- Use in-memory SQLite for tests
- Create test fixtures

**Files Created/Modified**:
- `tests/unit/registry/__init__.py`
- `tests/unit/registry/test_schema.py`
- `tests/unit/registry/test_resource_names.py`
- `tests/unit/registry/test_operations.py`

**Dependencies**: Task 18 (Registry Operations)

**Success Criteria**:
- All tests pass
- >80% coverage for registry module
- Edge cases covered
- Quest and faction handling tested

**Commit Message**: "test(registry): add comprehensive registry tests"

**Estimated Time**: 55 minutes

---

### Task 20: Configure Pytest Infrastructure

**Goal**: Set up pytest with proper configuration and markers.

**Actions**:
- Update `pyproject.toml` [tool.pytest.ini_options]:
  - testpaths = ["tests"]
  - python_files = ["test_*.py"]
  - python_classes = ["Test*"]
  - python_functions = ["test_*"]
  - addopts for coverage, verbosity, markers
  - Markers:
    - unit: Fast, isolated unit tests
    - integration: Tests with real database (28KB fixture)
    - production: Optional tests with full database (skip if unavailable)
    - slow: Tests that take >5 seconds
- Update `pyproject.toml` [tool.coverage.run]:
  - source = ["src/erenshor"]
  - omit test files
- Update `pyproject.toml` [tool.coverage.report]:
  - Set minimum coverage target
  - exclude_lines for pragmas

**Files Created/Modified**:
- `pyproject.toml` (updated)

**Dependencies**: Task 19 (Registry Tests) - validates test setup works

**Success Criteria**:
- `uv run pytest` runs all tests
- `uv run pytest -m unit` runs only unit tests
- `uv run pytest -m integration` runs integration tests
- Coverage reports generated
- Markers work correctly

**Commit Message**: "test: configure pytest with coverage and markers"

**Estimated Time**: 25 minutes

---

### Task 21: Create Test Database Fixtures

**Goal**: Set up hybrid test database approach with fixtures.

**Actions**:
- Create `tests/fixtures/database/schema.sql`:
  - Minimal schema for integration tests
  - Key tables only (Items, Spells, Characters, etc.)
- Create `tests/fixtures/database/integration-28kb.sql`:
  - 28KB SQL fixture with real data
  - Representative entities from each type
  - Include edge cases
  - Keep minimal but realistic
- Create `tests/conftest.py`:
  - `in_memory_db` fixture - Fresh SQLite for unit tests
  - `integration_db` fixture - Load 28KB SQL fixture
  - `production_db` fixture - Optional full DB (skip if missing)
  - Database cleanup fixtures
  - Common test utilities
- Add .gitignore entry for generated test databases

**Files Created/Modified**:
- `tests/fixtures/database/schema.sql`
- `tests/fixtures/database/integration-28kb.sql`
- `tests/conftest.py`
- `.gitignore` (updated)

**Dependencies**: Task 20 (Pytest Config)

**Success Criteria**:
- Fixtures load correctly
- in_memory_db works for unit tests
- integration_db loads 28KB fixture
- production_db skips gracefully if missing
- Tests can use fixtures
- Fast test execution

**Commit Message**: "test: add hybrid database fixtures for unit and integration tests"

**Estimated Time**: 50 minutes

**Note**: The 28KB SQL fixture can initially be minimal - it will be expanded as more entities are implemented in later phases.

---

### Task 22: Merge erenshor-maps into Monorepo

**Goal**: Move erenshor-maps project into `src/maps/` within the main repository.

**Actions**:
- Copy erenshor-maps to `src/maps/`:
  - `src/maps/src/` (Svelte source)
  - `src/maps/static/` (static assets)
  - `src/maps/package.json`
  - `src/maps/package-lock.json`
  - `src/maps/svelte.config.js`
  - `src/maps/vite.config.ts`
  - `src/maps/vitest.config.ts`
  - `src/maps/tsconfig.json`
  - `src/maps/.prettierrc`
  - `src/maps/.prettierignore`
  - `src/maps/eslint.config.js`
  - `src/maps/README.md`
  - `src/maps/wrangler.jsonc`
- Do NOT copy:
  - `.git/` (leave separate for now)
  - `node_modules/`
  - `.svelte-kit/`
  - `build/`
- Update `.gitignore` to ignore:
  - `src/maps/node_modules/`
  - `src/maps/.svelte-kit/`
  - `src/maps/build/`
  - `src/maps/static/data/*.sqlite` (database files)
- Create `src/maps/.gitkeep` for empty data directory

**Files Created/Modified**:
- `src/maps/` (entire directory structure)
- `.gitignore` (updated)

**Dependencies**: Task 21 (Test Fixtures) - completes core infrastructure

**Success Criteria**:
- Maps project copied to `src/maps/`
- TypeScript/Svelte files present
- Build configuration preserved
- .gitignore updated
- No build artifacts committed
- `npm install` works in `src/maps/`

**Commit Message**: "refactor: merge erenshor-maps into monorepo at src/maps/"

**Estimated Time**: 20 minutes

---

### Task 23: Update Maps Configuration

**Goal**: Integrate maps into new configuration system.

**Actions**:
- Add to config schema (`src/erenshor/infrastructure/config/schema.py`):
  - `MapsConfig` model:
    - source_dir: Path to maps source (src/maps/)
    - data_dir: Path to maps static/data/
    - database_symlink: Path to symlink target
    - build_dir: Path to build output
    - deploy_target: Cloudflare project name
- Add to `VariantConfig`:
  - maps: MapsConfig
- Create `config.toml` entry:
  ```toml
  [variants.main.maps]
  source_dir = "$REPO_ROOT/src/maps"
  data_dir = "$REPO_ROOT/src/maps/static/data"
  build_dir = "$REPO_ROOT/src/maps/build"
  deploy_target = "erenshor-maps"
  ```
- Update config loader to handle maps config

**Files Created/Modified**:
- `src/erenshor/infrastructure/config/schema.py` (updated)
- `config.toml` (created - NEW file for refactored system)

**Dependencies**: Task 22 (Maps Integration)

**Success Criteria**:
- Maps config loads correctly
- Paths resolve properly
- Config validation works
- Can access maps config from code

**Commit Message**: "feat(config): add maps configuration to schema"

**Estimated Time**: 30 minutes

---

### Task 24: Implement Maps CLI Commands

**Goal**: Add functional maps CLI commands for dev/build/deploy workflow.

**Actions**:
- Implement `erenshor maps dev`:
  - Change to maps directory
  - Create symlink: `variants/main/erenshor-main.sqlite` → `src/maps/static/data/erenshor.sqlite`
  - Run `npm run dev`
  - Delete symlink on exit (cleanup handler)
  - Show helpful message about live database updates
- Implement `erenshor maps preview`:
  - Change to maps directory
  - Run `npm run preview`
- Implement `erenshor maps build`:
  - Copy database: `variants/main/erenshor-main.sqlite` → `src/maps/static/data/erenshor.sqlite`
  - Change to maps directory
  - Run `npm run build`
  - Show build output location
- Implement `erenshor maps deploy`:
  - Ensure build exists
  - Change to maps directory
  - Run `npx wrangler pages deploy build --project-name erenshor-maps`
  - Show deployment URL
- Add error handling for missing npm, node_modules
- Add validation for database existence

**Files Created/Modified**:
- `src/erenshor/cli/commands/maps.py` (updated)

**Dependencies**: Task 23 (Maps Config)

**Success Criteria**:
- `erenshor maps dev` starts dev server with symlinked DB
- `erenshor maps preview` previews built site
- `erenshor maps build` creates production build with copied DB
- `erenshor maps deploy` deploys to Cloudflare
- Symlinks cleaned up properly
- Errors handled gracefully
- Database deployment works (symlink dev, copy build)

**Commit Message**: "feat(cli): implement maps commands for dev, build, and deploy"

**Estimated Time**: 55 minutes

---

### Task 25: Final Integration and Documentation

**Goal**: Ensure everything works together and document Phase 1 completion.

**Actions**:
- Create `config.toml` (NEW root config file for refactored system):
  - Copy structure from legacy/config.toml.old
  - Update paths for new structure
  - Add maps configuration
  - Add all global settings
  - Update comments and documentation
- Create `config.local.toml.example`:
  - Example local overrides
  - Show common customizations
  - Document sensitive fields (Steam username, API keys)
- Update `.gitignore`:
  - Ensure config.local.toml is ignored
  - Ensure src/maps/static/data/*.sqlite ignored
  - Ensure test database files ignored
- Run full test suite: `uv run pytest`
- Run type checker: `uv run mypy src/`
- Run linter: `uv run ruff check src/`
- Test all basic CLI commands:
  - `erenshor --help`
  - `erenshor --version`
  - `erenshor status`
  - `erenshor config show`
  - `erenshor doctor`
  - `erenshor test`
- Update README.md:
  - Add note about Phase 1 completion
  - Update installation instructions
  - Document new CLI structure
- Create `docs/refactoring-plan/phase-1-completion.md`:
  - List completed tasks
  - Note any deviations from plan
  - Document known issues
  - Next steps for Phase 2

**Files Created/Modified**:
- `config.toml` (NEW)
- `config.local.toml.example` (NEW)
- `.gitignore` (updated)
- `README.md` (updated)
- `docs/refactoring-plan/phase-1-completion.md` (NEW)

**Dependencies**: Task 24 (Maps CLI)

**Success Criteria**:
- All tests pass
- Type checking passes
- Linting passes
- All basic commands work
- Config system functional
- Logging works
- CLI help is clear
- Documentation updated
- Ready for Phase 2

**Commit Message**: "docs: complete Phase 1 foundation - ready for Phase 2"

**Estimated Time**: 45 minutes

---

## Summary

**Total Tasks**: 25
**Total Estimated Time**: ~16.5 hours (2-3 weeks part-time)

**Key Milestones**:
1. **Tasks 1-3**: Project structure and tooling (50 min)
2. **Tasks 4-8**: Configuration system (3h 40min)
3. **Tasks 9-11**: Logging system (1h 45min)
4. **Tasks 12-15**: CLI framework (3h 10min)
5. **Tasks 16-19**: Registry foundation (3h 15min)
6. **Tasks 20-21**: Test infrastructure (1h 15min)
7. **Tasks 22-24**: Maps integration (1h 45min)
8. **Task 25**: Final integration (45 min)

**Phase 1 Deliverables**:
- ✅ Old system archived to `legacy/`
- ✅ New Python package structure
- ✅ Two-layer TOML config system
- ✅ Loguru logging (INFO level, verbose)
- ✅ CLI skeleton with Typer (all commands)
- ✅ Maps merged into monorepo
- ✅ pytest infrastructure (hybrid test DB)
- ✅ Registry foundation (resource-name-based)

**Ready for Phase 2**: Data extraction pipeline implementation.

---

## Notes

- **Atomic Commits**: Each task is independently committable
- **Sequential Dependencies**: Tasks build on previous work
- **Test Coverage**: Tests added throughout (not just at end)
- **Quality Tools**: Pre-commit hooks set up early (Task 3)
- **Realistic Estimates**: Based on actual implementation time
- **Clear Success Criteria**: Each task has measurable completion markers

**Implementation Tips**:
1. Commit after each task completion
2. Run tests frequently (`uv run pytest`)
3. Use pre-commit hooks to catch issues early
4. Keep commits focused and atomic
5. Update this document if deviations occur
6. Document unexpected issues or decisions

---

**End of Phase 1 Task Breakdown**
