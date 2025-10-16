# Architecture Decisions Record

**Document Status**: Planning Phase - Incorporates User Feedback
**Date**: 2025-10-16
**Purpose**: Final architectural decisions based on deep analysis and user feedback

---

## Table of Contents

1. [Overview](#1-overview)
2. [Major Decisions](#2-major-decisions)
3. [Migration Strategy](#3-migration-strategy)
4. [Technology Stack](#4-technology-stack)
5. [Configuration System](#5-configuration-system)
6. [CLI Structure](#6-cli-structure)
7. [Data Formats](#7-data-formats)
8. [Testing Approach](#8-testing-approach)

---

## 1. Overview

This document records all major architectural decisions made based on the deep analysis and user feedback. These decisions are final and should guide implementation.

### Key Principles

1. **Big Bang Rewrite** - Clean break from old system, no legacy code paths
2. **KISS** - Keep it simple, avoid over-engineering
3. **YAGNI** - Don't add features until needed
4. **Clear Separation** - Old and new systems completely separated during transition
5. **Solo Dev Focus** - Optimized for single developer, not team complexity

---

## 2. Major Decisions

### 2.1 Migration Approach: Big Bang Rewrite

**Decision**: Complete rewrite with clean separation from old system.

**Rationale** (from user feedback):
- "I'd really rather do the Big Bang Rewrite"
- "If we go for the move, we should do it properly"
- "Everything else is just a maintenance nightmare with yet another half-finished solution"
- "Just NO. As discussed, that's just a maintenance nightmare. Clearly separate the two systems (old vs. new). NO shared files. NO shared code paths."

**Implementation**:
- Move old system to `legacy/` folder (archived, reference only)
- Start new implementation from scratch in main codebase
- Use old system for comparison testing during development
- Zero shared code between old and new
- Once new system validated, delete legacy folder entirely

### 2.2 Repository Structure: Monorepo with Independent Output Modules

**Decision**: Merge erenshor-maps into main repository as independent module.

**Rationale** (from user feedback):
- "I think I prefer the monorepo with independent output modules"
- "Large repo size should not be too much of an issue"
- "keeping things in sync across fully independent projects is probably trickier"
- "As discussed, let's go with the merged monorepo solution"

**Structure**:
```
erenshor/
├── src/
│   ├── erenshor/          # Python package
│   │   ├── extraction/    # Unity/Steam/AssetRipper orchestration
│   │   ├── database/      # SQLite schema and queries
│   │   ├── outputs/       # Output modules (no interdependencies)
│   │   │   ├── wiki/
│   │   │   ├── sheets/
│   │   │   └── maps/
│   │   └── shared/        # Config, logging, URLs
│   ├── maps/              # TypeScript/Svelte frontend
│   └── Assets/Editor/     # C# Unity scripts
├── variants/              # Working directories (gitignored)
├── backups/               # All backups, no retention policy
├── legacy/                # Old system (reference only, deleted after validation)
├── config.toml            # Project defaults
└── pyproject.toml         # Python dependencies
```

### 2.3 CLI: Python-Only (Eliminate Bash)

**Decision**: Consolidate all CLI logic into Python, remove Bash layer.

**Rationale**:
- Bash/Python split adds unnecessary complexity
- Python can handle all orchestration needs
- Simpler to test, document, and maintain
- User agreed with consolidation

**Command Structure**:
```bash
erenshor extract [--variant main]         # Data extraction
erenshor wiki fetch                       # Wiki operations
erenshor wiki update
erenshor wiki push
erenshor sheets deploy --all-sheets       # Sheets operations
erenshor maps export                      # Maps data export
erenshor maps dev                         # Maps development server
erenshor status [--all-variants]          # Status/info
erenshor config show
erenshor backup info                      # Backup info
erenshor doctor                           # System health
```

### 2.4 Configuration: Simplified Two-Layer System

**Decision**: Remove environment variables, use only TOML files.

**Rationale** (from user feedback):
- "I'm somewhat hesitant about keeping environment variables. What are the benefits of that over just the two-layer config.local.toml + config.toml?"
- "Seems like that adds a lot of potential for problems with, at best, marginal benefits?"
- "As discussed, I'm not really a fan of environment variables. Why's that 'better' than, e.g., .env? Or the config.local.toml?"

**Configuration Layers**:
1. **config.local.toml** (local overrides, gitignored) - Higher priority
2. **config.toml** (defaults, tracked in git) - Lower priority

**NO**:
- Environment variables
- .env files
- Dynamic defaults
- Multiple fallback layers

### 2.5 Maps Data: Full SQLite Database (Not JSON)

**Decision**: Keep full SQLite database for maps, not JSON export.

**Rationale** (from user feedback):
- "Hmmm, I'm not sure where you're getting 'maps JSON' from? The maps use the SQLite DB for the data, as far as I remember."
- "we want to extend the maps in the future to also offer search for items, characters, etc. so we can't really trim things down at all. All data will be needed in some form eventually."
- "the maps really need the full DB. So JSON is not a solution."

**Implementation**: Maps frontend loads full SQLite database via sql.js in browser.

**Open Question**: How to address long load times? (See section 7 in critical issues document)

### 2.6 Manual Mappings: Required and Cannot Be Avoided

**Decision**: Manual mappings in registry are necessary and will remain.

**Rationale** (from user feedback):
- "Regarding the manual mapping: I'm afraid there's just no way around this."
- "We have quite a lot of legacy data in the wiki that we can't reasonably migrate to use auto-generated mapping / conflict resolutions."
- "we're not only mapping page names, but also display names, image names, and potentially other overrides down the line."
- "it's not really possible to use an automated disambiguation strategy at the moment - at least not for legacy content. We MUST preserve names of wiki pages as they currently are."

**Implementation**: Support manual overrides for:
- Page titles
- Display names
- Image names
- Future overrides as needed

**Enhancement**: Auto-disambiguation for NEW entities only, always respecting manual overrides.

### 2.7 Backup Policy: Keep Everything, No Retention

**Decision**: Keep ALL backups (one per game version), no automatic deletion.

**Rationale** (from user feedback):
- "As discussed, I'd like to keep ALL backups (i.e., 1 for every build / version of the game that we ever ran through our pipeline). No need for any retention policies or anything like that."
- "If the data ever becomes too much, I'll just delete some stuff manually."

**Implementation**:
- One backup per game version (automatic on version change)
- Manual deletion only (no auto-cleanup)
- Show space usage in CLI output for awareness

### 2.8 Testing: Focus on Python, Skip C# for Now

**Decision**: No automated testing for C# Unity scripts.

**Rationale** (from user feedback):
- "I wouldn't worry about C# testing for now at all. Things 'just work' there, and we don't really plan to change anything about the C# code in the near to medium-term future."
- "Don't test C# code for now."
- "As mentioned: no automated testing for C# scripts please."

**Focus**: Python testing for wiki page generation, data transformations, and outputs.

### 2.9 TOML vs YAML: Stick with TOML

**Decision**: Keep TOML for configuration.

**Rationale** (from user feedback):
- "I'm somewhat on the fence about TOML vs. YAML. Admittedly, I think TOML looks 'cleaner'"
- "we don't really have THAT many config settings to get all too much benefit from YAML's nesting."

User asked for justification but ultimately accepted TOML as "fine" and "cleaner".

**Note**: TOML has good multi-language support (Python, C#, TypeScript) which we need.

---

## 3. Migration Strategy

### 3.1 Big Bang Approach

**Phase 1: Archive Old System**
- Move current `src/erenshor/` to `legacy/erenshor/`
- Move current `cli/` to `legacy/cli/`
- Keep for comparison testing only
- No modifications to legacy code

**Phase 2: Implement New System**
- Build new architecture from scratch in `src/erenshor/`
- Implement Python-only CLI
- No code reuse from legacy (clean slate)

**Phase 3: Validation**
- Compare outputs (wiki pages, sheets data, etc.)
- Run integration tests
- Manual validation of key workflows

**Phase 4: Cutover**
- Switch to new system
- Delete `legacy/` folder entirely
- Update documentation

**Phase 5: Polish**
- Add missing features discovered during use
- Improve error messages and DX
- Add more tests

### 3.2 No Feature Flags, No Dual Paths

From user feedback:
- "Just NO. As discussed, that's just a maintenance nightmare. Clearly separate the two systems (old vs. new). NO shared files. NO shared code paths."
- "Too much effort. Clear cut!"

**Principle**: Old system is for reference/comparison only. New system is the only implementation.

---

## 4. Technology Stack

### 4.1 Python

**Version**: Python 3.13+
**Package Manager**: uv (preferred) or pip

**Core Libraries**:
- **CLI**: Typer (keep current)
- **Progress**: Rich (keep current)
- **Logging**: Loguru (new - better DX than stdlib)
- **Config**: tomllib (stdlib) + Pydantic
- **Database**: sqlite3 (stdlib)
- **Wiki API**: httpx (async HTTP client)
- **Testing**: pytest + pytest-httpx + pytest-mock

### 4.2 TypeScript (Maps)

**Framework**: SvelteKit 2.0 (keep current)
**Build**: Vite
**Map Library**: Leaflet
**SQLite**: sql.js (WASM)
**Hosting**: Cloudflare Pages

### 4.3 C#

**Unity Version**: 2021.3.45f2 (MUST match game)
**Config Parser**: Tomlyn (TOML parser for C#)

### 4.4 Configuration Format

**Format**: TOML
**Why**: Human-readable, multi-language support, user preference

### 4.5 Logging

**Library**: Loguru
**Why**: Simple API, auto-rotation, colorization, better than stdlib

---

## 5. Configuration System

### 5.1 Two-Layer Cascade

**Layers** (in priority order):
1. `config.local.toml` (gitignored, local overrides)
2. `config.toml` (tracked, defaults)

**Loading Logic**:
```python
def load_config() -> Config:
    # Load defaults
    with open("config.toml", "rb") as f:
        data = tomllib.load(f)

    # Override with local config if exists
    if Path("config.local.toml").exists():
        with open("config.local.toml", "rb") as f:
            local = tomllib.load(f)
        data = deep_merge(data, local)

    return Config(**data)
```

### 5.2 Structure

```toml
version = "0.5"
default_variant = "main"

[paths]
repo_root = "."
variants_dir = "variants"
backups_dir = "backups"

[extraction]
unity_version = "2021.3.45f2"
unity_path = "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app"

[logging]
level = "info"

[outputs.wiki]
api_url = "https://erenshor.wiki.gg/api.php"
base_url = "https://erenshor.wiki.gg/wiki/"
bot_username = ""  # Set in config.local.toml
bot_password = ""  # Set in config.local.toml

[outputs.sheets]
credentials_file = "$HOME/.config/erenshor/google-credentials.json"

[outputs.maps]
base_url = "https://erenshor-maps.wowmuch1.workers.dev"

[variants.main]
enabled = true
app_id = "2382520"
database = "main/erenshor-main.sqlite"
sheets_spreadsheet_id = "1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E"
```

### 5.3 Path Resolution

**Approach**: Encapsulate all path logic in config system, provide strongly-typed access.

```python
@dataclass
class VariantPaths:
    """All paths for a variant (absolute, resolved)."""
    variant: str
    game_files: Path
    unity_project: Path
    database: Path
    logs: Path
    backups: Path
    images: Path

# Usage - no way to use wrong path
paths = config.get_variant_paths("main")
db = sqlite3.connect(paths.database)
```

---

## 6. CLI Structure

### 6.1 High-Level Commands

**Extraction**:
- `erenshor extract` - Full pipeline (download → extract → export)
- `erenshor extract download` - Download game files
- `erenshor extract rip` - Run AssetRipper
- `erenshor extract export` - Export to SQLite

**Wiki**:
- `erenshor wiki fetch` - Fetch pages from MediaWiki
- `erenshor wiki update` - Generate updated content
- `erenshor wiki push` - Upload to MediaWiki
- `erenshor wiki status` - Show update status

**Sheets**:
- `erenshor sheets list` - List available sheets
- `erenshor sheets deploy` - Deploy to Google Sheets

**Maps**:
- `erenshor maps dev` - Development server
- `erenshor maps build` - Production build
- `erenshor maps deploy` - Deploy to Cloudflare

**Status/Info**:
- `erenshor status` - Pipeline status
- `erenshor config show` - Show configuration
- `erenshor doctor` - System health check
- `erenshor backup info` - Backup information

### 6.2 Global Options

```bash
--variant <name>    # Specify variant (default: main)
--dry-run          # Preview without changes
--verbose          # Verbose output
--quiet            # Minimal output
```

### 6.3 CLI Documentation

**Requirement** (from user feedback):
- "how difficult would it be to generate CLI docs automatically?"
- "If there was some 'online'/browser-based single-page documentation that of the full CLI surface"
- "As mentioned somewhere earlier, some 'online' / browser-based documentation might be a nice addition as well. Any way to automate this?"

**Solution**: Auto-generate single-page HTML documentation from Typer CLI.

**Implementation**: Use Typer's introspection + Jinja2 template → HTML file.

---

## 7. Data Formats

### 7.1 SQLite Database

**Primary data format** for all extracted game data.

**Schema**: Defined by C# Unity scripts, exported directly.

**Access**:
- Python: stdlib sqlite3
- TypeScript/Maps: sql.js (WASM)
- C#: SQLite-net

### 7.2 Registry Storage

**Format**: SQLite database (not JSON)

**Rationale** (from user feedback):
- "I don't mind switching to SQLite. Not really a fan of the huge JSON file, to be honest."
- "Having it queryable might make conflict detection easier? Especially if we also create some sort of index of fetched wiki pages in the DB?"
- "As discussed earlier, I'd prefer SQLite storage for the registry."

**Schema**:
```sql
CREATE TABLE pages (
    page_id TEXT PRIMARY KEY,
    title TEXT UNIQUE NOT NULL,
    last_fetched INTEGER,
    last_pushed INTEGER
);

CREATE TABLE entities (
    uid TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    db_id TEXT NOT NULL,
    db_name TEXT NOT NULL,
    page_id TEXT REFERENCES pages(page_id)
);

CREATE TABLE manual_mappings (
    entity_uid TEXT PRIMARY KEY,
    page_title TEXT,
    display_name TEXT,
    image_name TEXT
);

CREATE TABLE all_wiki_pages (
    title TEXT PRIMARY KEY,
    is_managed BOOLEAN NOT NULL,
    last_seen INTEGER
);
```

### 7.3 Backup Format

**Editor Scripts**: ZIP archive of Unity project C# scripts
**Databases**: Direct copy of SQLite file
**Config**: Copy of config.toml

---

## 8. Testing Approach

### 8.1 Scope

**Focus**: Python code, especially wiki page generation.

**Skip**: C# Unity scripts (stable, not changing).

### 8.2 Test Levels

**Unit Tests** (60%):
- Fast, isolated
- Individual functions and classes
- Mock external dependencies

**Integration Tests** (30%):
- Real database (copy of current production DB)
- Test full workflows
- Validate outputs

**Comparison Tests** (10%):
- Compare new system output with old system
- Ensure parity during transition

**Rationale for using real DB** (from user feedback):
- "Beware that constructing a test DB is hard work and often produces cases that don't quite match real-world scenarios due to some subtle differences."
- "An option might be to just copy the current, most recent DB and use that for implementation of integration tests going forward."

### 8.3 Mocking Strategy

From user feedback:
- "Please avoid overly heavy mocking. Advocates often go quite a bit overboard with it"
- "Just to be clear: I'm NOT saying we should NEVER use mocking, but we should really think about where it makes sense"

**Use Mocking For**:
- External API calls (MediaWiki, Google Sheets)
- Network requests
- File system operations in unit tests

**Don't Mock**:
- Database access (use real SQLite)
- Internal application logic
- Data transformations

### 8.4 Regression Prevention

**Approach**: Keep library of problematic wiki pages/snippets.

From user feedback:
- "keeping a 'library' of wiki pages / snippets that caused issues in the past sure is a good idea to avoid regressions even if those wiki pages don't exist in their problematic form anymore."

**Implementation**:
```
tests/fixtures/wiki_pages/
├── problematic_cases/
│   ├── case_001_special_chars.txt
│   ├── case_002_multiline_template.txt
│   └── ...
└── regression_tests.py
```

---

## Summary

These architectural decisions are **final** and based on extensive user feedback. Key takeaways:

1. **Big bang rewrite** - Clean break, no legacy code paths
2. **Monorepo** - Merge maps into main repository
3. **Python-only CLI** - Eliminate Bash layer
4. **Two-layer TOML config** - No env vars
5. **Full SQLite for maps** - Not JSON
6. **Manual mappings required** - No way around it
7. **Keep all backups** - No retention policy
8. **Skip C# testing** - Focus on Python
9. **Real DB for tests** - Use copy of production data
10. **Minimal mocking** - Use real systems where possible

**Next Steps**: Create detailed documents for critical issues and open questions.
