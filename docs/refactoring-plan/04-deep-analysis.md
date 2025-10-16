# Deep Analysis: Erenshor Data Pipeline Refactoring

**Document Status**: Planning Phase - No Implementation Yet
**Date**: 2025-10-16
**Purpose**: Comprehensive analysis of current system, pain points, and design options for refactoring

---

## Table of Contents

1. [Current Pain Points Analysis](#1-current-pain-points-analysis)
2. [Architecture Proposals](#2-architecture-proposals)
3. [Technology Choices](#3-technology-choices)
4. [Wiki Workflow Deep Dive](#4-wiki-workflow-deep-dive)
5. [Registry System Rethinking](#5-registry-system-rethinking)
6. [Maps Integration Strategy](#6-maps-integration-strategy)
7. [Configuration System Design](#7-configuration-system-design)
8. [Migration Strategy](#8-migration-strategy)
9. [Testing Strategy](#9-testing-strategy)
10. [Backup System](#10-backup-system)
11. [Change Detection System](#11-change-detection-system)
12. [Developer Experience Improvements](#12-developer-experience-improvements)
13. [Open Questions & Discussion Points](#13-open-questions--discussion-points)

---

## 1. Current Pain Points Analysis

### 1.1 Bash + Python Split

**The Problem**: Dual CLI system creates cognitive overhead and maintenance burden.

**Concrete Issues**:
- Two separate command structures (`cli/commands/*.sh` vs `src/erenshor/cli/commands/*.py`)
- Python integration module (`cli/lib/modules/python.sh`) adds indirection
- Parameter passing between layers is error-prone (variant handling, config overrides)
- Testing requires testing both layers
- Documentation must cover both systems
- New developers must learn both Bash and Python CLI patterns

**Evidence from Codebase**:
```bash
# Bash wrapper that just delegates to Python
python_exec wiki update "$@"

# Config override complexity
python_exec_with_config db.path "/custom/path" db stats

# Variant context passing
python_exec_variant "$variant" sheets deploy
```

**Why It Exists**: Originally, Bash handled system operations (SteamCMD, AssetRipper, Unity) while Python handled data processing. This made sense for orchestration but now creates unnecessary complexity.

### 1.2 Configuration Cascade Complexity

**The Problem**: Multi-layer configuration system is hard to debug and understand.

**Current System** (from `config.toml` and `settings.py`):
1. Environment variables (`ERENSHOR_*`)
2. `.env` file (gitignored)
3. `.erenshor/config.local.toml` (local overrides)
4. `config.toml` (project defaults)
5. Field defaults in Pydantic models
6. PathResolver dynamic defaults

**Concrete Issues**:
- Hard to know which config value is being used
- Path resolution happens in multiple places (Bash, Python, PathResolver)
- Variant-specific config requires careful navigation
- Three languages need to read same config (C#, Python, TypeScript)
- `$REPO_ROOT` variable expansion happens differently in Bash vs Python
- Config validation scattered across modules

**Real Pain Point**: Looking at `settings.py`, config loading is complex:
```python
# Load TOML, then override Field defaults, then let pydantic read env vars
toml_config = load_config(resolver.root)
mediawiki_config = toml_config.get_global_config("mediawiki")
for field_name, toml_key in field_mappings:
    toml_value = mediawiki_config.get(toml_key)
    if toml_value is not None:
        WikiSettings.model_fields[field_name].default = toml_value
settings = WikiSettings()  # Now reads env vars
```

### 1.3 Wiki Update System Issues

**The Problem**: Current wiki system is "amateurish" (user's words) with multiple fundamental issues.

**Issue 1: Not Using MediaWiki APIs Properly**

Current approach:
- Fetch ALL pages in namespace
- Hash everything locally
- Compare hashes to detect changes
- No use of `recentchanges` API

Proper approach:
- Use `recentchanges` API with continuation to get only changed pages since last fetch
- Use `revisions` with timestamp filters
- Only fetch pages that actually changed
- Dramatically reduces API calls

**Issue 2: Registry/Disambiguation System Brittleness**

Current system (`registry/core.py`):
- Manual mappings in `mapping.json` (`entity.stable_key -> page_title`)
- Display name overrides
- Image name overrides
- Page ID generation system
- Complex entity reference tracking

Problems:
- Manual mapping maintenance is error-prone
- Stable keys can break on game updates
- No clear rules for when to use multi-entity pages vs single-entity pages
- Registry can get out of sync with reality
- Version 2.0 format breaks old data

**Issue 3: Local Diffing Not Useful**

Current features:
- `wiki diff` command shows local vs cached content
- Hash tracking for original vs updated content
- Timestamp tracking (last_fetched, last_updated, last_pushed)

User feedback: "Local diffing doesn't provide actionable information"

The real need: Know what changed in the GAME (schema changes, new entities) not what changed locally.

**Issue 4: Manual Content Preservation Unclear**

Current approach:
- Fetch wiki page
- Generate new content from database
- ???
- Push to wiki

Missing: How to preserve manually-added content that's not in templates?

Examples:
- Strategy tips
- Lore notes
- Community discoveries
- Dialog text (currently in main body, not templated)

**Issue 5: Multi-Entity Pages Half-Supported**

Current state:
- Spells and skills: Multi-entity pages work (e.g., "Fire Spells" page)
- Characters: Single-entity only
- Items: Single-entity only

Why the inconsistency? How to handle "Goblin Warrior" variants (different levels, same base character)?

### 1.4 Internal Representations Bloat

**The Problem**: Too many intermediate data structures.

**Example Path**: Item data transformations
1. Unity ScriptableObject (C#)
2. SQLite table record (C# Database class)
3. SQLAlchemy model (Python `domain/entities/item.py`)
4. ItemKind classifier output (Python domain service)
5. Wiki template parameters (Python generator)
6. Google Sheets row (Python formatter)
7. Maps JSON (TypeScript - in separate project)

**Question**: Which of these are actually necessary? Can we reduce 7 representations to 3-4?

**Necessary**:
- Unity ScriptableObject (source of truth)
- SQLite (intermediate storage, queryable)
- Output formats (wiki wikitext, sheets rows, maps JSON)

**Maybe Unnecessary**:
- Heavy domain entities in Python (do we need full ORM models?)
- Separate classifier services (could be SQL queries)
- Multiple storage abstractions

### 1.5 Logging System Issues

**Current System**:
- Bash: Uses `log_*` functions to `stderr` and log files
- Python: Uses stdlib logging (via structlog in some places)
- Log files scattered: `.erenshor/logs/`, `variants/{variant}/logs/`
- No clear retention policy
- Hard to find relevant logs for specific operations

**Problems**:
- Two logging systems (Bash and Python)
- Log rotation not standardized
- No connection between CLI output and detailed logs
- Debug logs buried in verbose output
- No log viewer or search tool

### 1.6 Multi-Variant Path Confusion

**The Problem**: Easy to accidentally use wrong variant's database or paths.

**Current Protection**: PathResolver, variant validation, environment variables

**Still Possible Errors**:
- Forgetting to specify variant in CLI command
- Using main database when playtest is intended
- Mixing paths from different variants in scripts
- Hard-coded paths in C# scripts

**Recent Evidence**: User mentioned "Issues due to improper use of variant-specific paths have caused so many issues already"

---

## 2. Architecture Proposals

### 2.1 Core Concept: Multi-Output Data Pipeline

**Mental Model Shift**: NOT a "wiki project" - it's a **data pipeline** with 4 outputs.

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA EXTRACTION                         │
│                                                               │
│  Steam Download → AssetRipper → Unity Export → SQLite DB    │
│                                                               │
│              (Multi-variant: main, playtest, demo)           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
              ┌──────────────────────┐
              │   SQLite Database    │
              │  (Single Source of   │
              │       Truth)         │
              └──────────┬───────────┘
                         │
          ┌──────────────┼──────────────┬──────────────┐
          ↓              ↓              ↓              ↓
    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────────┐
    │  Wiki   │    │ Sheets  │    │  Maps   │    │Compendium│
    │(Fetch,  │    │(Deploy) │    │(JSON    │    │  (Mod)   │
    │Generate,│    │         │    │Export)  │    │ (Future) │
    │ Push)   │    │         │    │         │    │          │
    └─────────┘    └─────────┘    └─────────┘    └──────────┘
       ↕                                ↕
   MediaWiki                      Cloudflare
     API                            Pages
```

**Key Principles**:
1. **No direct dependencies between outputs** (wiki doesn't know about sheets, etc.)
2. **Shared data source** (all outputs query same SQLite DB)
3. **Cross-linking via configuration** (URLs configured, not hard-coded)
4. **Independent deployment** (can update sheets without touching wiki)

### 2.2 Option A: Monorepo with Independent Output Modules

**Structure**:
```
erenshor/
├── cli/                      # Python CLI (consolidate everything)
├── src/
│   ├── erenshor/
│   │   ├── extraction/       # Unity/Steam/AssetRipper orchestration
│   │   ├── database/         # SQLite schema and queries
│   │   ├── outputs/          # Output modules (no interdependencies)
│   │   │   ├── wiki/         # Wiki fetch/generate/push
│   │   │   ├── sheets/       # Google Sheets deploy
│   │   │   ├── maps/         # Maps JSON export
│   │   │   └── compendium/   # Future: mod data export
│   │   └── shared/           # Truly shared utilities (config, logging)
│   ├── maps/                 # TypeScript/Svelte frontend
│   │   ├── src/
│   │   ├── static/
│   │   └── package.json
│   └── Assets/Editor/        # C# Unity scripts
├── variants/                 # Working directories (gitignored)
├── config.toml
└── pyproject.toml
```

**Pros**:
- Single source of truth
- Unified versioning and releases
- Shared tooling (CI/CD, linting, formatting)
- Easy cross-referencing (maps can import erenshor package for types)
- Clear separation via directory structure

**Cons**:
- Large repository size
- Mixed language tooling (Python + TypeScript)
- Need to coordinate dependency updates across languages

### 2.3 Option B: Monorepo with Fully Independent Subprojects

**Structure**:
```
erenshor/
├── core/                     # Data extraction + database
│   ├── cli/bin/erenshor
│   ├── src/erenshor/extraction/
│   └── pyproject.toml
├── wiki/                     # Wiki operations
│   ├── src/erenshor_wiki/
│   └── pyproject.toml
├── sheets/                   # Sheets operations
│   ├── src/erenshor_sheets/
│   └── pyproject.toml
├── maps/                     # TypeScript frontend
│   ├── src/
│   └── package.json
└── config.toml              # Shared config
```

**Pros**:
- True independence (can use different Python versions, dependencies)
- Clear boundaries
- Can develop/test each subproject in isolation

**Cons**:
- More complex (multiple packages to install)
- Dependency coordination harder
- More CI/CD complexity
- Overkill for single-dev project

**Recommendation**: **Option A** - Monorepo with independent modules. Simpler, easier to maintain, clearer boundaries.

### 2.4 Output Module Independence

**Design Rule**: Output modules MUST NOT import from each other.

```python
# BAD - Creates coupling
from erenshor.outputs.wiki import WikiPage
from erenshor.outputs.sheets import format_for_sheets

# GOOD - Each output queries database independently
from erenshor.database import execute_query

def generate_wiki_page():
    return execute_query("SELECT * FROM items WHERE id = ?")

def generate_sheet_row():
    return execute_query("SELECT * FROM items WHERE id = ?")
```

**Cross-Linking Mechanism**:

Option 1: URL Configuration
```toml
[outputs.wiki]
base_url = "https://erenshor.wiki.gg/wiki/"

[outputs.maps]
base_url = "https://maps.erenshor.wiki"

[outputs.sheets]
spreadsheet_id = "..."
```

Each output module reads config and generates appropriate links.

Option 2: Shared URL Builder
```python
# erenshor/shared/urls.py
def item_wiki_url(item_name: str) -> str:
    return f"{config.wiki.base_url}{item_name}"

def spawn_point_map_url(zone: str, x: float, y: float) -> str:
    return f"{config.maps.base_url}/{zone}?x={x}&y={y}"
```

**Recommendation**: Option 2 (shared URL builder) - DRY, centralized, easy to update.

### 2.5 Pipeline Orchestration Options

**Option A: Simple Sequential Python**
```python
def update_pipeline(variant: str):
    download_game(variant)
    extract_unity_project(variant)
    export_to_database(variant)

    # Outputs can run in parallel or sequentially
    update_wiki(variant)
    deploy_sheets(variant)
    export_maps_data(variant)
```

**Pros**: Simple, easy to understand, no dependencies
**Cons**: No parallelization, no dependency tracking, no retry logic

**Option B: Use Task Library (Luigi, Prefect, Dagster)**

Example with Luigi:
```python
class DownloadGame(luigi.Task):
    variant = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(f"variants/{variant}/game/.complete")

    def run(self):
        download_game(self.variant)

class ExportDatabase(luigi.Task):
    variant = luigi.Parameter()

    def requires(self):
        return [DownloadGame(self.variant), ExtractUnityProject(self.variant)]

    def run(self):
        export_to_database(self.variant)
```

**Pros**: Dependency tracking, parallelization, retries, task state management
**Cons**: Adds dependency, learning curve, possible overkill

**Recommendation**: **Start with Option A** (simple sequential). Add task library ONLY if you need:
- Partial pipeline runs (resume from failure)
- Parallel output generation (wiki + sheets + maps simultaneously)
- Complex dependency graphs

For a solo dev, simplicity wins. YAGNI.

---

## 3. Technology Choices

### 3.1 CLI Framework

**Candidates**:

| Framework | Pros | Cons | Fit |
|-----------|------|------|-----|
| **Typer** (current) | Rich integration, automatic help, type hints, modern | Relatively new, less docs than Click | ✅ Keep |
| **Click** | Mature, widely used, extensive docs | More verbose, no automatic type validation | ❌ No benefit |
| **argparse** | Stdlib, no deps | Very verbose, less ergonomic | ❌ Too basic |
| **Rich-Click** | Click + Rich UI | Adds wrapper complexity | ❌ Typer already has Rich |

**Recommendation**: **Keep Typer** - Already in use, good fit, no reason to change.

**Command Structure Proposal**:
```bash
erenshor extract [--variant main]              # Data extraction
erenshor wiki fetch                            # Wiki operations
erenshor wiki update
erenshor wiki push
erenshor sheets deploy --all-sheets            # Sheets operations
erenshor maps export                           # Maps data export
erenshor status [--all-variants]               # Status/info commands
erenshor config show
```

### 3.2 Progress Reporting

**Current**: Rich library (Live, Progress, Spinner)

**Alternatives**:
- `tqdm`: Simple progress bars, less rich features
- `progressbar2`: Similar to tqdm
- `alive-progress`: Animated, fun but less informative
- `rich` (current): Most feature-complete, best for complex UIs

**Recommendation**: **Keep Rich** - Already using, excellent for complex progress with Live displays.

**Enhancement**: Add structured progress events
```python
@dataclass
class ProgressEvent:
    operation: str
    current: int
    total: int
    message: str
    metadata: dict[str, Any]

def upload_pages() -> Iterator[ProgressEvent]:
    for i, page in enumerate(pages):
        yield ProgressEvent("upload", i+1, len(pages), page.title, {"size": len(content)})
```

### 3.3 Configuration Format

**Candidates**:

| Format | Pros | Cons | Multi-Language |
|--------|------|------|----------------|
| **TOML** (current) | Human-readable, good for config, Python support, C# support | No native TypeScript support | ⚠️ Need parser |
| **JSON** | Universal support, simple | Not human-friendly, no comments | ✅ Native everywhere |
| **YAML** | Very readable, comments | Significant whitespace, parsing inconsistencies | ⚠️ Need parser |
| **JSON5** | JSON + comments | Less standardized | ⚠️ Need parser |

**Current State**: TOML is working, has good Python support (tomllib, pydantic-settings)

**Multi-Language Support**:
- Python: ✅ Native tomllib (3.11+)
- C#: ✅ [Tomlyn](https://github.com/xoofx/Tomlyn) library
- TypeScript: ⚠️ Need [smol-toml](https://github.com/squirrelchat/smol-toml)

**Recommendation**: **Keep TOML** - It's working, human-readable, has support in all three languages.

**Improvement**: Simplify cascade to 3 layers:
1. Environment variables (highest priority)
2. `config.local.toml` (local overrides, gitignored)
3. `config.toml` (defaults)

Remove: `.env` file support (use env vars or config.local.toml instead)

### 3.4 Logging System

**Candidates**:

| Library | Pros | Cons | Fit |
|---------|------|------|-----|
| **stdlib logging** | No deps, universal | Verbose, outdated API | ❌ Clunky |
| **loguru** | Simple API, automatic rotation, colorization | Another dependency | ✅✅ Best DX |
| **structlog** (current?) | Structured logging, good for analysis | More complex setup | ⚠️ Maybe overkill |
| **rich.logging** | Integrates with Rich, pretty output | Less feature-complete | ⚠️ Backup option |

**Recommendation**: **Loguru** - Best developer experience, simple, powerful.

```python
from loguru import logger

logger.add("erenshor.log", rotation="10 MB", retention="7 days", level="DEBUG")
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")

logger.info("Starting extraction")
logger.debug("Processing item {item_id}", item_id=123)
```

**Log Organization**:
```
.erenshor/logs/
├── erenshor.log            # Current log (rotated at 10MB)
├── erenshor.2025-10-15.log # Rotated logs (kept 7 days)
└── erenshor.2025-10-14.log
```

**Retention Policy**: 7 days of logs, max 100MB total. Old logs auto-deleted.

### 3.5 Wiki Integration - MediaWiki API Strategy

**Current Issues**:
- Fetches all pages unnecessarily
- Uses hash comparison instead of MediaWiki timestamps
- Doesn't use `recentchanges` API

**Proper MediaWiki API Usage**:

1. **Initial Fetch** (first time):
```python
# Get all pages in namespace
pages = api.list_pages(namespace=0)  # Main namespace

# Fetch content in batches
for batch in chunks(pages, 50):
    content = api.fetch_batch(batch)
```

2. **Incremental Updates** (subsequent runs):
```python
# Use recentchanges API to get only changed pages since last fetch
last_fetch_timestamp = registry.get_last_fetch_timestamp()

changes = api.query_recent_changes(
    namespace=0,
    start=last_fetch_timestamp,
    end="now",
    type="edit|new"
)

changed_titles = [change["title"] for change in changes]

# Only fetch changed pages
content = api.fetch_batch(changed_titles)
```

**Key API Endpoints**:
- `action=query&list=recentchanges` - Get recently changed pages
- `action=query&list=allpages` - Get all pages in namespace (initial fetch)
- `action=query&prop=revisions` - Get page content with timestamps
- `action=edit` - Upload pages
- `action=upload` - Upload files

**Rate Limiting Strategy**:
- Respect `Retry-After` header (already implemented in `client.py`)
- Use `maxlag` parameter (already implemented)
- Batch requests (50 pages per request)
- Add delays between batches (configurable, default 1 second)

### 3.6 Testing Frameworks

**Python Testing**:

Current: pytest (good choice, keep it)

**Additions**:
- `pytest-mock` - For mocking external services
- `pytest-httpx` - Mock HTTP requests (wiki API)
- `pytest-sqlite` - In-memory SQLite for tests
- `pytest-timeout` - Prevent hanging tests

**TypeScript Testing** (for maps):

Current: vitest (good choice, modern, fast)

**Unity Testing**:

Challenge: Unity batch mode is slow, testing is hard.

**Strategy**:
- Unit test C# listeners independently (mock AssetScanner)
- Integration test full export (slow, run less frequently)
- Validate database schema after export
- Compare against known-good baseline

**Test Organization**:
```
tests/
├── unit/                 # Fast, isolated tests
│   ├── test_wiki/
│   ├── test_sheets/
│   └── test_database/
├── integration/          # Slower, with real DB/files
│   ├── test_wiki_e2e/
│   └── test_sheets_e2e/
└── fixtures/             # Test data
    ├── sample.sqlite
    └── sample_pages/
```

**Mock Wiki API for Testing**:
```python
import pytest
from pytest_httpx import HTTPXMock

def test_fetch_page(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://erenshor.wiki.gg/api.php",
        json={"query": {"pages": [{"title": "Test", "revisions": [...]}]}}
    )

    client = WikiAPIClient(api_url="https://erenshor.wiki.gg/api.php")
    content = client.fetch_page("Test")
    assert content is not None
```

---

## 4. Wiki Workflow Deep Dive

### 4.1 What SHOULD Wiki Updates Look Like?

**Ideal Workflow**:
```bash
# 1. Fetch latest wiki pages (only changed since last fetch)
erenshor wiki fetch

# 2. Generate updated pages from database
erenshor wiki update

# 3. Review changes (optional)
erenshor wiki status              # Shows pages needing upload
erenshor wiki diff "Sword"        # Shows local changes

# 4. Push to wiki (with safety checks)
erenshor wiki push --dry-run      # Preview
erenshor wiki push --all          # Upload all modified pages
```

**Key Features**:
1. **Smart Fetching**: Only fetch pages changed since last run
2. **Merge Logic**: Preserve manually-added content outside templates
3. **Safety**: Dry-run mode, batch limits, confirmation prompts
4. **Progress**: Real-time feedback on operations
5. **Recovery**: Can resume after failures

### 4.2 Minimal Feature Set for Wiki Maintenance

**Must Have**:
1. Fetch wiki pages (initial + incremental)
2. Generate page content from database
3. Upload pages with edit summaries
4. Preserve manual content (via template boundaries)
5. Handle rate limits gracefully
6. Track upload status (needs upload vs up-to-date)

**Nice to Have**:
- Diff viewing (for debugging)
- Batch operations (upload multiple pages)
- Conflict detection (local vs remote changes)
- Image upload automation

**Don't Need** (YAGNI):
- Local content hashing (trust MediaWiki timestamps)
- Complex diff tools (just use git for local tracking)
- Page history tracking (MediaWiki does this)
- Offline mode (always need API access)

### 4.3 Disambiguation / Name Conflicts

**The Problem**: Multiple entities can have same name (e.g., "Sword" item vs "Sword" skill)

**Current Solution**: Manual mapping in `mapping.json`
```json
{
  "item/sword": "Sword (item)",
  "skill/sword": "Sword (skill)"
}
```

**Issues**:
- Manual maintenance
- Brittle stable keys
- Hard to predict conflicts before they happen

**Better Solution**: Automatic disambiguation with override

```python
class DisambiguationStrategy(Enum):
    SUFFIX = "suffix"           # "Sword (item)", "Sword (skill)"
    PREFIX = "prefix"           # "Item: Sword", "Skill: Sword"
    MULTI_ENTITY = "multi"      # One page "Sword" with both entities
    MANUAL = "manual"           # Use manual mapping

def resolve_page_title(entity: EntityRef, strategy: DisambiguationStrategy) -> str:
    # Check manual mappings first
    if manual_title := get_manual_mapping(entity.stable_key):
        return manual_title

    # Detect conflicts
    conflicts = find_entities_with_same_name(entity.db_name)
    if len(conflicts) <= 1:
        return entity.db_name  # No conflict, use plain name

    # Apply strategy
    if strategy == DisambiguationStrategy.SUFFIX:
        return f"{entity.db_name} ({entity.entity_type.value})"
    elif strategy == DisambiguationStrategy.MULTI_ENTITY:
        return entity.db_name  # Multiple entities on one page
    # ... etc
```

**Configuration**:
```toml
[wiki.disambiguation]
default_strategy = "suffix"
multi_entity_types = ["spell", "skill"]  # These can share pages

[wiki.disambiguation.overrides]
"item/old_sword" = "Rusty Sword"        # Manual override
"character/goblin_warrior_1" = "Goblin Warrior"  # Merge variants
```

### 4.4 Multi-Entity Pages

**Current State**:
- Spells/Skills: ✅ Multi-entity pages work
- Characters: ❌ Single-entity only
- Items: ❌ Single-entity only

**Use Cases**:
1. **Spell Ranks**: "Fireball I", "Fireball II", "Fireball III" → One "Fireball" page
2. **Character Variants**: "Goblin Warrior (Level 5)", "Goblin Warrior (Level 10)" → One "Goblin Warrior" page
3. **Item Sets**: Collect related items on one page

**Design**:

```python
@dataclass
class WikiPage:
    title: str
    entities: list[EntityRef]  # Multiple entities per page
    template: PageTemplate      # How to render multiple entities

    def is_multi_entity(self) -> bool:
        return len(self.entities) > 1

class PageTemplate(Enum):
    SINGLE_INFOBOX = "single"           # One entity, one infobox
    MULTI_INFOBOX = "multi"             # Multiple entities, multiple infoboxes
    TABBED_INFOBOX = "tabbed"           # Multiple entities, tabbed display
    COMPARISON_TABLE = "comparison"     # Multiple entities, comparison table
```

**Template Example**:
```wikitext
{{Spell Infobox
|name=Fireball
|ranks=3
}}

== Ranks ==

{{Spell Rank
|rank=I
|level=1
|damage=10
|mana=5
}}

{{Spell Rank
|rank=II
|level=10
|damage=25
|mana=10
}}

{{Spell Rank
|rank=III
|level=20
|damage=50
|mana=20
}}
```

### 4.5 Manual Content Preservation

**The Challenge**: How to preserve content that's not auto-generated?

**Examples of Manual Content**:
- Strategy tips
- Lore notes
- Community discoveries
- Quest walkthroughs
- Location guides

**Solution: Template Boundaries**

```wikitext
{{Character Infobox
<!-- AUTO-GENERATED - DO NOT EDIT BETWEEN THESE COMMENTS -->
|name=Goblin Warrior
|level=5
|health=100
<!-- END AUTO-GENERATED -->
}}

== Description ==
<!-- AUTO-GENERATED -->
A fierce goblin warrior found in the northern forests.
<!-- END AUTO-GENERATED -->

== Strategy ==
<!-- This section is manually maintained -->
Best fought with fire spells. Weak against magic but strong melee attacks.
Watch out for his charge ability!

== Loot ==
<!-- AUTO-GENERATED -->
{{Loot Table
|item1=Rusty Sword
|chance1=25%
}}
<!-- END AUTO-GENERATED -->
```

**Merge Logic**:
```python
def merge_page_content(original: str, generated: str) -> str:
    """Merge generated content into original, preserving manual sections."""

    # Parse both pages
    original_sections = parse_sections(original)
    generated_sections = parse_sections(generated)

    # For each section:
    # - If marked AUTO-GENERATED: Replace with generated version
    # - If not marked: Keep original content
    # - If new in generated: Add to page

    merged = {}
    for section_name, section_content in original_sections.items():
        if is_auto_generated(section_content):
            # Replace with generated version if available
            merged[section_name] = generated_sections.get(section_name, section_content)
        else:
            # Keep original manual content
            merged[section_name] = section_content

    # Add new auto-generated sections
    for section_name, section_content in generated_sections.items():
        if section_name not in merged:
            merged[section_name] = section_content

    return render_page(merged)
```

**Recommendation**: Use MediaWiki templates with clearly marked auto-generated sections. Anything outside those sections is preserved.

### 4.6 Missing Entity Types (Quests, Zones, Factions)

**Current Support**:
- ✅ Items
- ✅ Characters
- ✅ Spells
- ✅ Skills
- ⚠️ Quests (partial - database exists, no wiki pages yet)
- ⚠️ Zones (partial)
- ⚠️ Factions (partial)
- ❌ Achievements
- ❌ Crafting recipes

**Architecture Requirement**: Must support adding new entity types WITHOUT major refactoring.

**Plugin-Style Design**:
```python
# Registry of entity handlers
@dataclass
class EntityHandler:
    entity_type: EntityType
    page_generator: Callable[[EntityRef], str]
    disambiguation_strategy: DisambiguationStrategy
    supports_multi_entity: bool

handlers: dict[EntityType, EntityHandler] = {}

def register_entity_handler(handler: EntityHandler):
    handlers[handler.entity_type] = handler

# Register handlers
register_entity_handler(EntityHandler(
    entity_type=EntityType.ITEM,
    page_generator=generate_item_page,
    disambiguation_strategy=DisambiguationStrategy.SUFFIX,
    supports_multi_entity=False,
))

register_entity_handler(EntityHandler(
    entity_type=EntityType.SPELL,
    page_generator=generate_spell_page,
    disambiguation_strategy=DisambiguationStrategy.MULTI_ENTITY,
    supports_multi_entity=True,
))

# Add new entity type easily
register_entity_handler(EntityHandler(
    entity_type=EntityType.QUEST,
    page_generator=generate_quest_page,
    disambiguation_strategy=DisambiguationStrategy.SUFFIX,
    supports_multi_entity=False,
))
```

**Name Conflict Resolution Across All Types**:

Even if quest pages aren't fully implemented, registry must track ALL entity names to detect conflicts.

```python
def build_registry(db_path: Path) -> WikiRegistry:
    registry = WikiRegistry()

    # Load ALL entities from database (even if no page generator yet)
    items = load_items(db_path)
    characters = load_characters(db_path)
    spells = load_spells(db_path)
    quests = load_quests(db_path)  # Even if no wiki pages generated yet

    # Register all for conflict detection
    for item in items:
        registry.register_entity(EntityRef(EntityType.ITEM, item.id, item.name))
    for quest in quests:
        registry.register_entity(EntityRef(EntityType.QUEST, quest.id, quest.name))

    # Detect conflicts
    conflicts = registry.find_name_conflicts()
    for conflict in conflicts:
        logger.warning(f"Name conflict: {conflict.name} ({conflict.types})")

    return registry
```

---

## 5. Registry System Rethinking

### 5.1 What Problem Does Registry Solve?

**Problems It Addresses**:
1. **Name conflicts**: Multiple entities with same name need unique page titles
2. **Tracking**: Which entities have wiki pages? Which need updates?
3. **Cross-references**: Link from sheets/maps back to wiki pages
4. **Metadata**: Last fetch, last update, last push timestamps
5. **Manual overrides**: Display name, image name, page title overrides

**Current Registry** (`registry/core.py`):
- Pages: `dict[str, WikiPage]` (title → page)
- Entities: `dict[str, WikiPage]` (entity.uid → page)
- Manual mappings: `dict[str, str]` (stable_key → title)
- Display names: `dict[str, str]` (stable_key → display_name)
- Image names: `dict[str, str]` (stable_key → image_name)
- Stored as JSON in `.erenshor/registry/registry.json`

### 5.2 Is It Too Complex?

**Concerns**:
1. Stable keys are brittle (`entity_type/db_id`)
2. Manual mapping maintenance is tedious
3. Registry can get out of sync with reality
4. Version 2.0 format breaks old data

**Alternative: Simpler Registry**

**Option 1: No Registry (Query Database Each Time)**
```python
def get_wiki_page_title(entity: EntityRef) -> str:
    # Query database for conflicts
    conflicts = query_db(f"SELECT * FROM entities WHERE name = '{entity.name}'")
    if len(conflicts) > 1:
        return f"{entity.name} ({entity.type})"
    return entity.name
```

**Pros**: No state to manage, always correct
**Cons**: Slower (database queries), no upload tracking

**Option 2: Lightweight Registry (Metadata Only)**
```python
@dataclass
class PageMetadata:
    title: str
    last_fetched: datetime | None
    last_pushed: datetime | None

registry: dict[str, PageMetadata] = {}  # title → metadata
```

**Pros**: Simple, just tracks timestamps
**Cons**: No entity tracking, no disambiguation

**Option 3: Current System (Enhanced)**

Keep current registry but fix issues:
- Use content-addressable keys instead of brittle stable_keys
- Auto-detect conflicts instead of manual mappings
- Provide migration tool for version upgrades

**Recommendation**: **Option 3** (keep and enhance) - Registry provides value, just needs refinement.

### 5.3 Improved Registry Design

**Key Changes**:
1. **Robust Entity IDs**: Use content-hash or database primary key
2. **Auto-disambiguation**: Detect conflicts automatically
3. **Lazy Loading**: Don't load entire registry in memory
4. **Versioned Format**: Support migration between versions

```python
@dataclass
class EntityRef:
    entity_type: EntityType
    db_id: str                    # Primary key from database (stable)
    db_name: str                  # Display name
    resource_name: str | None     # Unity resource name

    @property
    def uid(self) -> str:
        # Use database ID (stable across renames)
        return f"{self.entity_type.value}/{self.db_id}"

@dataclass
class WikiPage:
    title: str
    page_id: str
    entities: list[EntityRef]
    last_fetched: datetime | None
    last_pushed: datetime | None
    content_hash: str | None      # Current wiki content hash

class WikiRegistry:
    def resolve_page_title(self, entity: EntityRef) -> str:
        # 1. Check manual overrides
        if override := self.manual_mappings.get(entity.uid):
            return override

        # 2. Check if entity already has a page
        if page := self.by_entity.get(entity.uid):
            return page.title

        # 3. Auto-disambiguate based on conflicts
        return self.auto_disambiguate(entity)

    def auto_disambiguate(self, entity: EntityRef) -> str:
        # Find all entities with same name
        conflicts = [e for e in self.all_entities if e.db_name == entity.db_name]

        if len(conflicts) <= 1:
            return entity.db_name  # No conflict

        # Apply disambiguation strategy
        strategy = self.get_strategy(entity.entity_type)
        return strategy.apply(entity, conflicts)
```

### 5.4 Registry Storage

**Current**: JSON file (`.erenshor/registry/registry.json`)

**Issues**:
- Large file (10,000+ entities)
- Full load/save every operation
- Manual editing is error-prone

**Alternative: SQLite Database**

```sql
CREATE TABLE pages (
    page_id TEXT PRIMARY KEY,
    title TEXT UNIQUE NOT NULL,
    last_fetched INTEGER,  -- Unix timestamp
    last_pushed INTEGER,
    content_hash TEXT
);

CREATE TABLE entities (
    uid TEXT PRIMARY KEY,  -- entity_type/db_id
    entity_type TEXT NOT NULL,
    db_id TEXT NOT NULL,
    db_name TEXT NOT NULL,
    page_id TEXT REFERENCES pages(page_id)
);

CREATE TABLE manual_mappings (
    entity_uid TEXT PRIMARY KEY,
    page_title TEXT NOT NULL
);

CREATE INDEX idx_entities_name ON entities(db_name);
CREATE INDEX idx_entities_page ON entities(page_id);
```

**Pros**:
- Efficient queries
- Incremental updates
- Easy to inspect with SQLite tools
- Concurrent access (if needed)

**Cons**:
- Yet another database
- More complex than JSON

**Recommendation**: **Keep JSON for now**, optimize with lazy loading and incremental saves. Switch to SQLite if performance becomes an issue.

### 5.5 Entity Renames Across Game Versions

**Problem**: Game update renames "Sword" → "Iron Sword"

**Current System**: Breaks (stable_key changes, registry out of sync)

**Better Approach**: Track by database ID, not by name

```python
# Database ID is stable (Unity's GUID or auto-increment ID)
entity = EntityRef(
    entity_type=EntityType.ITEM,
    db_id="abc123",         # Stable across renames
    db_name="Iron Sword",   # Can change
)

# Registry uses db_id, not name
registry.by_entity[entity.uid] = page  # uid = "item/abc123"
```

**When Name Changes**:
1. Detect rename (same db_id, different db_name)
2. Log warning for review
3. Option to rename wiki page or keep old title
4. Update registry with new name

```python
def detect_renames(old_entities, new_entities):
    for entity_id, old_entity in old_entities.items():
        if entity_id in new_entities:
            new_entity = new_entities[entity_id]
            if old_entity.db_name != new_entity.db_name:
                yield Rename(
                    entity_id=entity_id,
                    old_name=old_entity.db_name,
                    new_name=new_entity.db_name,
                )
```

---

## 6. Maps Integration Strategy

### 6.1 Maps Project Overview

**Current State**: Separate repository at `/Users/joaichberger/Projects/erenshor-maps`

**Stack**:
- SvelteKit 2.0 (frontend framework)
- TypeScript (language)
- Leaflet (map library)
- sql.js (SQLite in browser)
- Cloudflare Pages (hosting)
- Vite (build tool)

**Data Flow**:
```
SQLite DB → JSON Export → Static Files → Browser → sql.js in WASM
```

### 6.2 Where Should Maps Live?

**Option A: Merge into Monorepo**

```
erenshor/
├── src/
│   ├── erenshor/          # Python package
│   └── maps/              # TypeScript/Svelte frontend
│       ├── src/
│       ├── static/
│       └── package.json
├── config.toml
└── pyproject.toml
```

**Pros**:
- Single source of truth
- Shared configuration
- Unified versioning
- Easy to coordinate updates
- Better CI/CD (one pipeline)

**Cons**:
- Large repository
- Mixed tooling (Python + TypeScript)
- More complex build process

**Option B: Keep Separate, Share Data via Export**

```
erenshor/              # Data extraction + outputs
└── variants/main/
    └── maps_data.json  # Exported for maps

erenshor-maps/         # Frontend
└── static/
    └── data.json      # Copied from main repo
```

**Pros**:
- Clean separation
- Independent development
- Simpler build

**Cons**:
- Manual data sync
- Harder to coordinate
- Two repositories to manage

**Recommendation**: **Option A (merge into monorepo)** - Better for long-term maintenance, simpler coordination.

**Migration Path**:
1. Copy `erenshor-maps/` to `src/maps/`
2. Update import paths
3. Add maps build to CI/CD
4. Archive old repository

### 6.3 Data Export Format

**Current**: Maps project loads full SQLite database in browser (sql.js)

**Issue**: Database is large (10+ MB), slow to load

**Better Approach**: Pre-process and export only needed data as JSON

```json
{
  "version": "1.0",
  "generated_at": "2025-10-16T12:00:00Z",
  "maps": [
    {
      "id": "northernforest",
      "name": "Northern Forest",
      "bounds": [[0, 0], [1000, 1000]],
      "markers": [
        {
          "type": "spawn_point",
          "id": "spawn_001",
          "name": "Goblin Warrior",
          "position": [500, 500],
          "level": 5,
          "wiki_url": "https://erenshor.wiki.gg/wiki/Goblin_Warrior"
        },
        {
          "type": "treasure",
          "id": "treasure_001",
          "position": [750, 250],
          "loot": ["Gold Coin", "Health Potion"]
        }
      ]
    }
  ]
}
```

**Generator**:
```python
# src/erenshor/outputs/maps/exporter.py

def export_maps_data(db_path: Path, output_path: Path):
    """Export map data from database to JSON for frontend."""

    data = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "maps": []
    }

    zones = query_zones(db_path)
    for zone in zones:
        map_data = {
            "id": zone.id,
            "name": zone.name,
            "bounds": [[zone.min_x, zone.min_y], [zone.max_x, zone.max_y]],
            "markers": []
        }

        # Add spawn points
        spawns = query_spawn_points(db_path, zone_id=zone.id)
        for spawn in spawns:
            map_data["markers"].append({
                "type": "spawn_point",
                "id": spawn.id,
                "name": spawn.character_name,
                "position": [spawn.x, spawn.y],
                "level": spawn.level,
                "wiki_url": get_wiki_url(spawn.character_name),
            })

        # Add treasures, etc.
        treasures = query_treasures(db_path, zone_id=zone.id)
        for treasure in treasures:
            map_data["markers"].append({
                "type": "treasure",
                "id": treasure.id,
                "position": [treasure.x, treasure.y],
                "loot": treasure.loot_items,
            })

        data["maps"].append(map_data)

    output_path.write_text(json.dumps(data, indent=2))
```

**CLI Command**:
```bash
erenshor maps export [--variant main] [--output maps_data.json]
```

### 6.4 URL Coordination

**Challenge**: Maps, wiki, and sheets need to link to each other.

**Solution: Shared URL Configuration**

```toml
# config.toml
[outputs.wiki]
base_url = "https://erenshor.wiki.gg/wiki/"

[outputs.sheets]
spreadsheet_id = "1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E"

[outputs.maps]
base_url = "https://maps.erenshor.wiki"

# Or local dev
# base_url = "http://localhost:5173"
```

**Usage in Python**:
```python
from erenshor.shared.urls import get_wiki_url, get_map_url

# Generate URLs
wiki_url = get_wiki_url("Goblin Warrior")  # https://erenshor.wiki.gg/wiki/Goblin_Warrior
map_url = get_map_url("northernforest", x=500, y=500)  # https://maps.erenshor.wiki/northernforest?x=500&y=500
```

**Usage in TypeScript**:
```typescript
// Load config from JSON (generated by Python)
import config from './config.json';

function getWikiUrl(entityName: string): string {
  return `${config.outputs.wiki.base_url}${entityName}`;
}
```

### 6.5 Maps Build and Deployment

**Current**: Manual `npm run build && wrangler deploy`

**After Monorepo Merge**:

```bash
# Development
erenshor maps dev            # Start Vite dev server

# Build
erenshor maps build          # Build for production

# Deploy
erenshor maps deploy         # Deploy to Cloudflare Pages
```

**Implementation**:
```python
# src/erenshor/cli/commands/maps.py

def dev():
    """Start maps development server."""
    subprocess.run(["npm", "run", "dev"], cwd="src/maps")

def build():
    """Build maps for production."""
    subprocess.run(["npm", "run", "build"], cwd="src/maps")

def deploy():
    """Deploy maps to Cloudflare Pages."""
    subprocess.run(["npm", "run", "deploy"], cwd="src/maps")
```

---

## 7. Configuration System Design

### 7.1 Simplified Configuration Cascade

**Current**: 6 layers (too many)

**Proposed**: 3 layers
1. **Environment variables** (highest priority) - For secrets and overrides
2. **config.local.toml** (local overrides) - User-specific, gitignored
3. **config.toml** (defaults) - Project defaults, tracked in git

**Remove**:
- `.env` file (use env vars or config.local.toml)
- PathResolver dynamic defaults (explicit paths in config)
- Multiple fallback layers

### 7.2 Configuration Structure

```toml
# config.toml
version = "0.4"
default_variant = "main"

# ============================================================================
# GLOBAL SETTINGS (shared across all components)
# ============================================================================

[paths]
repo_root = "."                    # Auto-detected, can override
variants_dir = "variants"
backups_dir = "backups"

[extraction]
steam_username = ""                # Set in config.local.toml or env var
steam_platform = "windows"
unity_version = "2021.3.45f2"
unity_path = "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity"
assetripper_path = "$HOME/Projects/AssetRipper/AssetRipper.GUI.Free"

[logging]
level = "info"                     # debug, info, warn, error
retention_days = 7
max_size_mb = 100

# ============================================================================
# OUTPUT CONFIGURATIONS
# ============================================================================

[outputs.wiki]
enabled = true
api_url = "https://erenshor.wiki.gg/api.php"
base_url = "https://erenshor.wiki.gg/wiki/"
batch_size = 25
rate_limit_delay = 1.0
bot_username = ""                  # Set in env var: ERENSHOR_WIKI_BOT_USERNAME
bot_password = ""                  # Set in env var: ERENSHOR_WIKI_BOT_PASSWORD

[outputs.sheets]
enabled = true
credentials_file = "$HOME/.config/erenshor/google-credentials.json"
batch_size = 1000
rate_limit_delay = 5.0

[outputs.maps]
enabled = true
base_url = "https://maps.erenshor.wiki"
export_format = "json"
output_file = "maps_data.json"

[outputs.compendium]
enabled = false                    # Future: BepInEx mod

# ============================================================================
# VARIANT CONFIGURATIONS
# ============================================================================

[variants.main]
enabled = true
app_id = "2382520"
name = "Main Game"

# Paths (relative to variants_dir)
game_files = "main/game"
unity_project = "main/unity"
database = "main/erenshor-main.sqlite"
logs = "main/logs"
backups = "main/backups"
images = "main/images"
maps_data = "main/maps_data.json"

# Output-specific overrides
sheets_spreadsheet_id = "1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E"

[variants.playtest]
enabled = false
app_id = "3090030"
name = "Playtest"
# ... same structure as main

[variants.demo]
enabled = false
app_id = "2522260"
name = "Demo"
# ... same structure as main
```

### 7.3 Path Resolution

**Problem**: Variant-specific paths are error-prone

**Solution**: Encapsulate all path logic in config system

```python
@dataclass
class VariantPaths:
    """All paths for a specific variant (absolute, resolved)."""
    variant: str
    game_files: Path
    unity_project: Path
    database: Path
    logs: Path
    backups: Path
    images: Path
    maps_data: Path

    @classmethod
    def from_config(cls, config: Config, variant: str) -> VariantPaths:
        base = config.paths.variants_dir / variant
        variant_config = config.variants[variant]

        return cls(
            variant=variant,
            game_files=base / variant_config.game_files,
            unity_project=base / variant_config.unity_project,
            database=base / variant_config.database,
            logs=base / variant_config.logs,
            backups=base / variant_config.backups,
            images=base / variant_config.images,
            maps_data=base / variant_config.maps_data,
        )

# Usage
paths = VariantPaths.from_config(config, "main")
db = sqlite3.connect(paths.database)  # Always correct path
```

**CLI Usage**:
```python
@app.command()
def export(variant: str = "main"):
    config = load_config()
    paths = VariantPaths.from_config(config, variant)

    # No way to use wrong path
    run_unity_export(paths.unity_project, paths.database)
```

### 7.4 Multi-Language Config Access

**Python**: Use Pydantic for validation
```python
from pydantic_settings import BaseSettings
import tomllib

class Config(BaseSettings):
    version: str
    paths: PathsConfig
    outputs: OutputsConfig
    variants: dict[str, VariantConfig]

    @classmethod
    def load(cls) -> Config:
        with open("config.toml", "rb") as f:
            data = tomllib.load(f)

        # Override with config.local.toml if exists
        if Path("config.local.toml").exists():
            with open("config.local.toml", "rb") as f:
                local = tomllib.load(f)
            data = deep_merge(data, local)

        return cls(**data)
```

**C#**: Use Tomlyn library
```csharp
using Tomlyn;

var config = Toml.ToModel<Config>(File.ReadAllText("config.toml"));
var databasePath = config.Variants["main"].Database;
```

**TypeScript**: Use smol-toml
```typescript
import { parse } from 'smol-toml';
import { readFileSync } from 'fs';

const config = parse(readFileSync('config.toml', 'utf-8'));
const wikiUrl = config.outputs.wiki.base_url;
```

### 7.5 Environment Variable Overrides

**Convention**: `ERENSHOR_<SECTION>_<KEY>`

Examples:
```bash
# Override wiki credentials
export ERENSHOR_OUTPUTS_WIKI_BOT_USERNAME="mybot"
export ERENSHOR_OUTPUTS_WIKI_BOT_PASSWORD="secret"

# Override variant database path
export ERENSHOR_VARIANTS_MAIN_DATABASE="/custom/path/db.sqlite"

# Override logging level
export ERENSHOR_LOGGING_LEVEL="debug"
```

**Python Implementation**:
```python
class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ERENSHOR_",
        env_nested_delimiter="_",
    )
```

---

## 8. Migration Strategy

### 8.1 Big Bang vs Incremental

**Option A: Big Bang Rewrite**
- Stop development
- Rewrite everything
- Switch when done

**Pros**: Clean slate, no compromises
**Cons**: Risky, long without working system, hard to validate

**Option B: Incremental Migration**
- Migrate one component at a time
- Keep old system working
- Validate each step

**Pros**: Less risky, continuous validation, can stop if problems
**Cons**: More complex, dual system maintenance

**Recommendation**: **Incremental** - Lower risk, easier to validate

### 8.2 Migration Phases

**Phase 1: Consolidate CLI (Python Only)**
- Move Bash command logic to Python
- Keep Bash as thin wrapper (temporary)
- Test: All commands work identically

**Phase 2: Simplify Configuration**
- Implement new config structure
- Add migration script for old config
- Test: All paths and settings work

**Phase 3: Refactor Wiki System**
- Implement proper MediaWiki API usage
- Add incremental fetch
- Add manual content preservation
- Test: Wiki updates work correctly

**Phase 4: Integrate Maps**
- Move maps project to monorepo
- Implement maps data export
- Update URLs
- Test: Maps work with exported data

**Phase 5: Enhance Registry**
- Improve entity tracking
- Add auto-disambiguation
- Test: All entity pages resolve correctly

**Phase 6: Add Backup System**
- Implement build-tagged backups
- Add retention policy
- Test: Backups created and cleaned up

**Phase 7: Add Change Detection**
- Implement schema change detection
- Add entity change notifications
- Test: Changes detected correctly

**Phase 8: Polish and Documentation**
- Improve CLI UX
- Add comprehensive docs
- Add tutorials

### 8.3 Validation Strategy

**For Each Phase**:

1. **Unit Tests**: Test new code in isolation
2. **Integration Tests**: Test with real database/files
3. **Comparison Tests**: Compare output with old system
4. **Manual Testing**: Run full pipeline and verify results

**Comparison Testing Example**:
```python
# Generate pages with old system
old_pages = old_system.generate_all_pages(db)

# Generate pages with new system
new_pages = new_system.generate_all_pages(db)

# Compare
for title, old_content in old_pages.items():
    new_content = new_pages.get(title)
    if new_content != old_content:
        diff = difflib.unified_diff(old_content, new_content)
        print(f"Difference in {title}:")
        print('\n'.join(diff))
```

### 8.4 Rollback Plan

**For Each Phase**:
- Keep old code path active
- Add feature flag for new code
- Can switch back if issues

```python
# Feature flag
USE_NEW_WIKI_SYSTEM = os.getenv("ERENSHOR_USE_NEW_WIKI", "false") == "true"

if USE_NEW_WIKI_SYSTEM:
    from erenshor.outputs.wiki.new_system import update_wiki
else:
    from erenshor.outputs.wiki.old_system import update_wiki
```

**Remove old code only after**:
- New code is stable (1+ months)
- All tests pass
- Manual validation complete
- No reported issues

### 8.5 Can Old and New Coexist?

**Yes, with careful design**:

1. **Separate CLI commands**: `erenshor wiki update` (old) vs `erenshor wiki2 update` (new)
2. **Separate directories**: `wiki_cache/` vs `wiki_cache_new/`
3. **Separate registries**: `registry.json` vs `registry_v2.json`
4. **Feature flags**: Control which system is used

**Eventually**: Remove old system when confident in new one

---

## 9. Testing Strategy

### 9.1 What Needs Testing?

**Critical Paths** (must test):
1. Database export (Unity → SQLite)
2. Wiki page generation (SQLite → wikitext)
3. Wiki upload (wikitext → MediaWiki)
4. Sheets deployment (SQLite → Google Sheets)
5. Maps data export (SQLite → JSON)
6. Configuration loading (TOML → Python/C#/TypeScript)

**Less Critical** (nice to test):
- CLI argument parsing
- Error handling
- Progress reporting
- Logging

**Don't Over-Test**:
- Simple getters/setters
- Data classes with no logic
- External API wrappers (mock instead)

### 9.2 Test Pyramid

```
        ┌──────────────┐
        │  E2E Tests   │  <-- Few, slow, high-level
        │   (10%)      │
        └──────┬───────┘
              / \
        ┌─────────────┐
        │Integration  │  <-- Some, medium speed, with real DB
        │    Tests    │
        │    (30%)    │
        └──────┬──────┘
              / \
        ┌─────────────┐
        │    Unit     │  <-- Many, fast, isolated
        │    Tests    │
        │    (60%)    │
        └─────────────┘
```

**Unit Tests** (fast, isolated):
```python
def test_item_classifier():
    assert classify_item_kind(required_slot="MainHand", ...) == "weapon"
    assert classify_item_kind(required_slot="Chest", ...) == "armor"

def test_url_builder():
    assert get_wiki_url("Sword") == "https://erenshor.wiki.gg/wiki/Sword"
    assert get_map_url("zone", 100, 200) == "https://maps.erenshor.wiki/zone?x=100&y=200"
```

**Integration Tests** (medium, with real database):
```python
@pytest.fixture
def test_db():
    # Create temporary SQLite database with test data
    db = sqlite3.connect(":memory:")
    load_schema(db)
    load_test_data(db)
    yield db
    db.close()

def test_generate_item_page(test_db):
    page = generate_item_page(test_db, item_id="sword_001")
    assert "{{Item Infobox" in page
    assert "name=Iron Sword" in page
```

**E2E Tests** (slow, full pipeline):
```python
def test_full_wiki_update(tmp_path):
    # Setup test environment
    config = create_test_config(tmp_path)

    # Run full pipeline
    export_database(config)
    update_wiki_pages(config)

    # Verify outputs
    assert (tmp_path / "wiki_updated" / "Sword.txt").exists()
    content = (tmp_path / "wiki_updated" / "Sword.txt").read_text()
    assert "{{Item Infobox" in content
```

### 9.3 Mocking External Services

**Wiki API**:
```python
@pytest.fixture
def mock_wiki_api(httpx_mock):
    httpx_mock.add_response(
        url="https://erenshor.wiki.gg/api.php",
        json={"query": {"pages": [{"title": "Test", "revisions": [...]}]}}
    )
    return httpx_mock

def test_fetch_page(mock_wiki_api):
    client = WikiAPIClient(api_url="https://erenshor.wiki.gg/api.php")
    content = client.fetch_page("Test")
    assert content is not None
```

**Google Sheets**:
```python
@pytest.fixture
def mock_sheets_api(mocker):
    mock = mocker.patch("googleapiclient.discovery.build")
    mock.return_value.spreadsheets().values().update.return_value.execute.return_value = {"updatedCells": 100}
    return mock

def test_deploy_sheet(mock_sheets_api):
    deploy_sheet("items", [[1, "Sword", 10]])
    assert mock_sheets_api.called
```

### 9.4 Unity Testing Strategy

**Challenge**: Unity batch mode is slow (minutes per run)

**Strategy**:

1. **Unit test C# listeners** (fast):
```csharp
[Test]
public void TestItemListener_ProcessesItemCorrectly() {
    var listener = new ItemListener();
    var item = CreateTestItem("Sword", ItemSlot.MainHand);

    var record = listener.Process(item);

    Assert.AreEqual("Sword", record.Name);
    Assert.AreEqual("Weapon", record.Category);
}
```

2. **Integration test with small Unity project** (medium):
- Create minimal Unity project with test assets
- Run export on test project
- Validate database output

3. **Validate production exports** (slow):
- Run full export on real game data
- Compare schema against expected
- Flag unexpected changes

### 9.5 Fast Feedback Loops

**Pytest Watch**: Run tests on file changes
```bash
uv run ptw -- -x  # Stop on first failure
```

**Test Markers**: Run subset of tests
```bash
uv run pytest -m "not slow"        # Skip slow tests
uv run pytest -m "unit"            # Only unit tests
uv run pytest -m "integration"    # Only integration tests
```

**Fixtures for Speed**:
```python
@pytest.fixture(scope="session")
def test_db():
    # Create once per test session
    db = create_test_database()
    yield db
    db.close()
```

---

## 10. Backup System

### 10.1 What to Back Up

1. **C# Editor Scripts** (`src/Assets/Editor/`)
   - Reason: Track how data is extracted over time
   - Frequency: Per game build

2. **SQLite Databases** (`variants/{variant}/erenshor-{variant}.sqlite`)
   - Reason: Preserve extracted data
   - Frequency: Per game build (latest export only)

3. **Configuration** (`config.toml`)
   - Reason: Track pipeline config changes
   - Frequency: On significant changes

**Don't Back Up**:
- Game files (can re-download)
- Unity projects (can re-extract)
- Wiki pages (MediaWiki has history)
- Logs (temporary debugging only)

### 10.2 Backup Naming and Tagging

**Naming Convention**: `{component}-{build_id}-{date}.{ext}`

Examples:
```
backups/
├── scripts/
│   ├── editor-scripts-v1.0.5.2-2025-10-16.zip
│   └── editor-scripts-v1.0.5.3-2025-10-20.zip
├── databases/
│   ├── main/
│   │   ├── erenshor-main-v1.0.5.2-2025-10-16.sqlite
│   │   └── erenshor-main-v1.0.5.3-2025-10-20.sqlite
│   └── playtest/
│       └── erenshor-playtest-v1.0.6.0-2025-10-18.sqlite
└── config/
    └── config-2025-10-16.toml
```

**Build ID**: Game version (from Unity or Steam manifest)

**Date**: ISO date (YYYY-MM-DD)

### 10.3 Backup Triggers

**Automatic** (on pipeline run):
```python
def export_database(variant: str):
    # Before export, check if game version changed
    current_build = get_game_build_id(variant)
    last_build = get_last_backed_up_build(variant)

    if current_build != last_build:
        # New build detected - backup old database
        backup_database(variant, last_build)
        backup_editor_scripts(current_build)

    # Run export
    run_unity_export(variant)
```

**Manual** (CLI command):
```bash
erenshor backup create [--variant main] [--comment "Before major refactor"]
erenshor backup list [--variant main]
erenshor backup restore v1.0.5.2
```

### 10.4 Retention Policy

**Rules**:
1. Keep latest 5 backups per variant (unlimited time)
2. Keep one backup per month for last 6 months
3. Delete older backups

**Rationale**: Recent backups most useful, but want some historical data

**Implementation**:
```python
def cleanup_backups(variant: str):
    backups = list_backups(variant)
    backups.sort(key=lambda b: b.date, reverse=True)

    # Keep latest 5
    keep = backups[:5]

    # Keep one per month for 6 months
    now = datetime.now()
    for i in range(6):
        month_start = now - timedelta(days=30*i)
        month_backups = [b for b in backups if b.date.month == month_start.month]
        if month_backups:
            keep.append(month_backups[0])

    # Delete others
    to_delete = [b for b in backups if b not in keep]
    for backup in to_delete:
        backup.delete()
```

### 10.5 Backup Storage Location

**Option A: Local** (current approach)
```
erenshor/
└── backups/
    ├── scripts/
    ├── databases/
    └── config/
```

**Pros**: Simple, fast, no external dependencies
**Cons**: No off-site protection, can grow large

**Option B: Git LFS**
- Track backup files in git with Large File Storage
- Pushed to GitHub

**Pros**: Versioned, off-site, easy to share
**Cons**: GitHub LFS has cost/limits, slower

**Option C: Cloud Storage** (S3, Google Drive)
- Upload backups to cloud automatically

**Pros**: Off-site, unlimited storage (with cost)
**Cons**: Adds complexity, dependencies, cost

**Recommendation**: **Option A (local)** - Simple, sufficient for solo dev. Add cloud later if needed.

**Space Estimate**:
- C# scripts: ~5 MB per backup
- SQLite DB: ~20 MB per backup
- 5 recent + 6 monthly = ~11 backups per variant
- Total: ~275 MB per variant
- 3 variants = ~825 MB total

Reasonable size, no need for cloud yet.

---

## 11. Change Detection System

### 11.1 What Changes to Detect

**Game Data Changes**:
1. **New entities**: New items, characters, spells added
2. **Removed entities**: Entities deleted (rare but possible)
3. **Renamed entities**: Same ID, different name
4. **Modified stats**: Health, damage, etc. changed
5. **New mechanics**: New fields in ScriptableObjects

**Schema Changes**:
1. **New tables**: New entity types
2. **New columns**: New fields in existing tables
3. **Removed columns**: Fields deprecated
4. **Type changes**: Field type modified

### 11.2 Detection Mechanisms

**Entity Changes** (database diff):
```python
def detect_entity_changes(old_db: Path, new_db: Path) -> ChangeReport:
    old_entities = load_entities(old_db)
    new_entities = load_entities(new_db)

    # New entities
    added = [e for e in new_entities if e.id not in old_entities]

    # Removed entities
    removed = [e for e in old_entities if e.id not in new_entities]

    # Renamed entities
    renamed = []
    for e in new_entities:
        if e.id in old_entities:
            old_name = old_entities[e.id].name
            if e.name != old_name:
                renamed.append((e.id, old_name, e.name))

    # Modified stats (check specific fields)
    modified = []
    for e in new_entities:
        if e.id in old_entities:
            if has_stat_changes(old_entities[e.id], e):
                modified.append(e.id)

    return ChangeReport(added, removed, renamed, modified)
```

**Schema Changes** (SQLite schema diff):
```python
def detect_schema_changes(old_db: Path, new_db: Path) -> SchemaChanges:
    old_schema = get_schema(old_db)
    new_schema = get_schema(new_db)

    # Compare tables
    new_tables = [t for t in new_schema if t not in old_schema]
    removed_tables = [t for t in old_schema if t not in new_schema]

    # Compare columns in common tables
    column_changes = {}
    for table in new_schema:
        if table in old_schema:
            old_cols = old_schema[table].columns
            new_cols = new_schema[table].columns

            added_cols = [c for c in new_cols if c not in old_cols]
            removed_cols = [c for c in old_cols if c not in new_cols]

            if added_cols or removed_cols:
                column_changes[table] = (added_cols, removed_cols)

    return SchemaChanges(new_tables, removed_tables, column_changes)
```

### 11.3 Notification System

**After Export**:
```python
def export_with_change_detection(variant: str):
    # Find previous database
    old_db = find_previous_database(variant)

    # Run export
    run_unity_export(variant)
    new_db = get_current_database(variant)

    # Detect changes
    if old_db:
        entity_changes = detect_entity_changes(old_db, new_db)
        schema_changes = detect_schema_changes(old_db, new_db)

        # Report changes
        print_change_report(entity_changes, schema_changes)

        # Save to file for review
        save_change_report(entity_changes, schema_changes, "changes.json")

        # Email notification (optional)
        if config.notifications.enabled:
            send_email_notification(entity_changes, schema_changes)
```

**Change Report Format**:
```json
{
  "timestamp": "2025-10-16T12:00:00Z",
  "variant": "main",
  "old_build": "v1.0.5.2",
  "new_build": "v1.0.5.3",
  "entity_changes": {
    "added": [
      {"type": "item", "id": "new_sword_123", "name": "Legendary Sword"}
    ],
    "removed": [],
    "renamed": [
      {"id": "old_sword_456", "old_name": "Sword", "new_name": "Iron Sword"}
    ],
    "modified": [
      {"id": "goblin_001", "changes": {"health": {"old": 100, "new": 120}}}
    ]
  },
  "schema_changes": {
    "new_tables": ["CraftingRecipes"],
    "removed_tables": [],
    "column_changes": {
      "Items": {
        "added": ["CraftingTime"],
        "removed": []
      }
    }
  }
}
```

### 11.4 Actionable Insights

**For Developer**:
- New items → Need wiki pages
- Renamed entities → Update registry manual mappings
- New table → Need new C# listener? New wiki template?
- New column → Update existing listeners

**CLI Display**:
```
Erenshor Export Complete

Changes Detected (v1.0.5.2 → v1.0.5.3):

Entities:
  + 5 new items
  + 2 new characters
  ↻ 1 renamed: "Sword" → "Iron Sword"
  ✎ 3 modified stats

Schema:
  + New table: CraftingRecipes
  + New column: Items.CraftingTime

Action Required:
  • Create wiki pages for 5 new items
  • Update registry mapping for renamed entity
  • Consider adding CraftingRecipes listener
  • Update Item wiki template for new field

Full report: variants/main/logs/changes-2025-10-16.json
```

### 11.5 Integration with CI/CD

**GitHub Actions** (if using):
```yaml
- name: Run export
  run: erenshor extract --variant main

- name: Check for changes
  run: |
    if erenshor changes detect --variant main; then
      echo "Changes detected - review required"
      exit 1  # Fail workflow to draw attention
    fi
```

**Local Development**:
```bash
# After export
erenshor changes detect [--variant main]

# Review changes
cat variants/main/logs/changes-2025-10-16.json

# Acknowledge changes (mark as reviewed)
erenshor changes ack
```

---

## 12. Developer Experience Improvements

### 12.1 Command Discoverability

**Current Issue**: Hard to know what commands exist

**Solution 1: Better Help**
```bash
$ erenshor --help

Erenshor Data Pipeline

Commands:
  extract     Download, extract, and export game data to SQLite
  wiki        Manage wiki pages (fetch, update, push)
  sheets      Deploy data to Google Sheets
  maps        Export and manage map data
  config      View and validate configuration
  status      Show pipeline status and health
  backup      Manage backups of databases and scripts

Run 'erenshor COMMAND --help' for command-specific help
```

**Solution 2: Smart Suggestions**
```bash
$ erenshor wik fetch
Error: Unknown command 'wik'

Did you mean: wiki fetch
```

**Solution 3: Completion Scripts**
```bash
# Generate shell completion
erenshor completion bash > ~/.bash_completion.d/erenshor
erenshor completion zsh > ~/.zsh/completions/_erenshor

# Now tab completion works
$ erenshor w<TAB>
wiki

$ erenshor wiki <TAB>
fetch  update  push  status
```

### 12.2 Progress Reporting

**Current**: Some commands have progress, others don't

**Standardize**:

Every long-running operation should show:
1. What it's doing
2. Progress (X/Y items)
3. Time elapsed
4. Estimated time remaining
5. Current item being processed

```
Extracting Game Data
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 75% 0:02:30 / 0:03:20

[✓] Downloaded game files (5.2 GB)
[✓] Extracted Unity project (1,234 assets)
[⟳] Exporting to database... (1,850 / 2,500 items)
    └─ Processing: Legendary Sword
[ ] Validating database schema
[ ] Creating backup
```

**Implementation** (using Rich):
```python
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn

with Progress(
    SpinnerColumn(),
    *Progress.get_default_columns(),
    TimeElapsedColumn(),
) as progress:
    task = progress.add_task("Exporting items...", total=len(items))
    for item in items:
        process_item(item)
        progress.update(task, advance=1, description=f"Exporting: {item.name}")
```

### 12.3 Clear Next Steps

**After Each Command**: Tell user what to do next

```bash
$ erenshor extract --variant main

✓ Extraction complete!

Database: variants/main/erenshor-main.sqlite
Entities: 2,500 items, 350 characters, 180 spells

Next steps:
  • Update wiki pages:     erenshor wiki update
  • Deploy to sheets:      erenshor sheets deploy --all-sheets
  • Export maps data:      erenshor maps export

Or run full pipeline:     erenshor pipeline run
```

### 12.4 Logs in Right Place

**Problem**: Logs scattered, hard to find

**Solution**: Consistent log paths + clear indication

```
.erenshor/logs/
├── erenshor.log                 # Current session
├── erenshor.2025-10-16.log      # Rotated logs
└── commands/                     # Command-specific logs
    ├── extract-2025-10-16.log
    ├── wiki-update-2025-10-16.log
    └── sheets-deploy-2025-10-16.log
```

**Show Log Path**:
```bash
$ erenshor extract --variant main

[Running extraction...]

✓ Complete! (took 3m 45s)

Logs: .erenshor/logs/commands/extract-2025-10-16.log
```

**Quick Log Access**:
```bash
# View latest log
erenshor logs show

# View specific command log
erenshor logs show extract

# Tail logs in real-time
erenshor logs tail
```

### 12.5 Better Error Messages

**Current**: Sometimes cryptic Python stack traces

**Better**:

```bash
$ erenshor wiki push --all

Error: Bot credentials not configured

Fix:
  1. Get bot password from https://erenshor.wiki.gg/wiki/Special:BotPasswords
  2. Set environment variables:
     export ERENSHOR_WIKI_BOT_USERNAME="YourBot@YourPassword"
     export ERENSHOR_WIKI_BOT_PASSWORD="..."
  3. Or add to config.local.toml:
     [outputs.wiki]
     bot_username = "YourBot@YourPassword"
     bot_password = "..."

For help: erenshor wiki auth --help
```

**Implementation**:
```python
class BotCredentialsError(Exception):
    def __init__(self):
        super().__init__("Bot credentials not configured")

    def help_text(self) -> str:
        return """
Fix:
  1. Get bot password from https://erenshor.wiki.gg/wiki/Special:BotPasswords
  2. Set environment variables:
     export ERENSHOR_WIKI_BOT_USERNAME="YourBot@YourPassword"
     export ERENSHOR_WIKI_BOT_PASSWORD="..."
  ...
"""

# In CLI
try:
    push_to_wiki()
except BotCredentialsError as e:
    console.print(f"[red]Error:[/red] {e}")
    console.print(e.help_text())
    raise typer.Exit(1)
```

### 12.6 Dry-Run Mode Everywhere

**Every destructive operation should have --dry-run**

Current: Wiki push has it ✓

Add to:
- Database export (show what would be exported)
- Backup creation (show what would be backed up)
- Cleanup operations (show what would be deleted)

```bash
# See what would be uploaded without uploading
erenshor wiki push --all --dry-run

# See what backups would be deleted
erenshor backup cleanup --dry-run

# See what would be exported
erenshor maps export --dry-run
```

### 12.7 Validation Commands

**Check system health**:
```bash
$ erenshor doctor

Checking system health...

✓ Python 3.13 installed
✓ Unity 2021.3.45f2 found
✓ Database schema valid
✓ Configuration valid
✗ Wiki bot credentials missing
⚠ AssetRipper not in PATH (required for extract)

Overall: 4 checks passed, 1 failed, 1 warning
```

**Validate before operations**:
```bash
$ erenshor wiki validate

Validating wiki configuration...

✓ API URL reachable (https://erenshor.wiki.gg/api.php)
✓ Bot credentials configured
✓ Authentication successful
✓ Bot has edit permissions
✓ 150 pages ready to update

Ready to push pages!
```

### 12.8 Interactive Mode for Dangerous Operations

**Push with confirmation**:
```bash
$ erenshor wiki push --all

Found 150 pages to upload.

Preview:
  • Sword
  • Goblin Warrior
  • Fireball
  ... and 147 more

Continue? [y/N]: y

Uploading pages...
[progress bar]
```

**Batch operations**:
```bash
$ erenshor backup cleanup

Found 23 old backups to delete:
  • erenshor-main-v1.0.4.5-2025-08-01.sqlite (75 days old, 18 MB)
  • erenshor-main-v1.0.4.4-2025-07-15.sqlite (90 days old, 17 MB)
  ...

Total space to free: 450 MB

Delete these backups? [y/N]:
```

---

## 13. Open Questions & Discussion Points

### 13.1 Pipeline Orchestration

**Question**: Do we need a task library (Luigi, Prefect, Dagster)?

**Options**:
1. Simple sequential Python (current approach)
2. Task library with dependency tracking
3. Custom lightweight orchestrator

**Trade-offs**:
- Task library: More powerful, learning curve, dependency
- Simple: Easy to understand, less features
- Custom: Tailored to needs, maintenance burden

**Discussion**: Start simple, add task library ONLY if you hit limits (want parallelization, retry logic, etc.)

### 13.2 Wiki Multi-Entity Pages

**Question**: How to decide when to use multi-entity pages vs single-entity?

**Options**:
1. **Explicit configuration**: List in config which entities should share pages
2. **Name-based heuristic**: "Fireball I", "Fireball II" → group by prefix
3. **Manual annotation**: Add tags in database to group entities

**Discussion**: Probably combination - config for known cases, heuristic for new cases, manual for edge cases.

### 13.3 Maps Data Format

**Question**: Export full SQLite or pre-processed JSON?

**Current**: Maps loads full SQLite in browser (sql.js)

**Options**:
1. Keep SQLite (flexible, ad-hoc queries possible)
2. Switch to JSON (smaller, faster, pre-processed)
3. Hybrid (JSON for common data, SQLite for advanced queries)

**Trade-offs**:
- SQLite: Large download, slower initial load, very flexible
- JSON: Smaller, faster, less flexible, requires backend changes for new queries

**Discussion**: Lean toward JSON for production (faster UX), SQLite for development (easier testing)

### 13.4 Registry Storage

**Question**: Keep JSON or switch to SQLite?

**Current**: JSON file (`registry.json`)

**Pros of JSON**: Simple, human-readable, easy to edit, git-diffable
**Cons of JSON**: Large file, slow for 10,000+ entities, full load/save

**Pros of SQLite**: Fast queries, incremental updates, indexed lookups
**Cons of SQLite**: Yet another database, not human-editable

**Discussion**: JSON is fine for now (< 5,000 entities). Switch to SQLite if performance becomes issue.

### 13.5 C# Configuration

**Question**: How should C# editor scripts read configuration?

**Options**:
1. Parse TOML directly (Tomlyn library)
2. JSON export of config (Python generates JSON from TOML)
3. Environment variables only

**Discussion**: TOML parsing (Option 1) keeps single source of truth. JSON export (Option 2) adds layer but might be simpler.

### 13.6 Compendium (Future Mod)

**Question**: What data format for BepInEx mod?

**Options**:
1. Embedded SQLite database
2. JSON files
3. Custom binary format

**Discussion**: Too early to decide - wait until starting mod development. Likely JSON or SQLite for ease of access.

### 13.7 Testing Unity Exports

**Question**: How to test Unity batch mode exports without running Unity every time?

**Options**:
1. Mock AssetScanner in C# unit tests
2. Small test Unity project with known data
3. Snapshot testing (compare against baseline)

**Discussion**: Combination - unit tests for listeners, small test project for integration, snapshot for validation.

### 13.8 Image Upload Automation

**Question**: Should image uploads be automatic or manual?

**Current**: Semi-manual (extract images, upload via CLI)

**Options**:
1. Fully automatic (upload all images after extraction)
2. Semi-automatic (detect new/changed images, prompt)
3. Manual (current - user decides what to upload)

**Trade-offs**:
- Automatic: Less work, might upload unwanted images
- Manual: More control, more work

**Discussion**: Semi-automatic seems best - detect new/changed, show preview, let user approve batch.

### 13.9 Rate Limiting Strategy

**Question**: How aggressive should rate limiting be?

**Current**: 1 second delay between uploads, maxlag parameter

**Options**:
1. Conservative (2-3 second delays)
2. Current (1 second delays)
3. Aggressive (no delays, rely on API rate limits)

**Discussion**: Current is fine. Can make configurable. Add exponential backoff on 429 errors (already implemented).

### 13.10 Variant Management

**Question**: Support more than 3 variants?

**Current**: main, playtest, demo

**Future**: Custom variants? Test variants?

**Discussion**: Config supports unlimited variants. Just enable when needed. No special handling required.

### 13.11 TypeScript/Python Type Sharing

**Question**: How to share types between Python and TypeScript?

**Examples**:
- Maps JSON format
- Config structure

**Options**:
1. Manual duplication (maintain separately)
2. JSON Schema (generate types from schema)
3. Code generation (Python → TypeScript types)

**Discussion**: Manual is simple but error-prone. JSON Schema adds tooling but ensures consistency. Probably worth it.

### 13.12 Documentation Strategy

**Question**: Where should documentation live?

**Options**:
1. Markdown files in `docs/`
2. Wiki on GitHub
3. Dedicated docs site (MkDocs, Docusaurus)
4. Inline in code (docstrings + generated)

**Discussion**: Markdown in `docs/` is fine for now. Can generate site later with MkDocs if needed.

### 13.13 Local Development Setup

**Question**: How to make onboarding easier?

**Ideas**:
- Setup script (`erenshor setup`)
- Docker container (full environment)
- Documentation improvements
- Video tutorial

**Discussion**: Setup script + good docs probably sufficient. Docker might be overkill for solo dev.

### 13.14 Notification System

**Question**: How to notify about changes/errors?

**Options**:
1. CLI output only
2. Email notifications
3. Discord/Slack webhook
4. Desktop notifications

**Discussion**: Start with CLI output. Email for critical errors? Probably overkill for solo dev.

### 13.15 Performance Benchmarking

**Question**: Should we track pipeline performance over time?

**Metrics**:
- Extract time
- Database size
- Wiki update time
- Number of entities

**Discussion**: Nice to have but not critical. Could log metrics to file for analysis.

---

## Summary and Recommendations

### Priority 1 (Must Do):
1. ✅ **Consolidate CLI to Python** - Eliminate Bash/Python split
2. ✅ **Simplify Configuration** - 3-layer cascade, clear path resolution
3. ✅ **Fix Wiki API Usage** - Use `recentchanges`, proper incremental updates
4. ✅ **Improve Registry** - Auto-disambiguation, stable entity IDs

### Priority 2 (Should Do):
5. ✅ **Integrate Maps** - Move to monorepo, export JSON data
6. ✅ **Add Backup System** - Build-tagged backups with retention policy
7. ✅ **Add Change Detection** - Notify about game updates
8. ✅ **Improve DX** - Better CLI UX, progress reporting, error messages

### Priority 3 (Nice to Have):
9. ⚠️ **Enhanced Testing** - More integration tests, mock services
10. ⚠️ **Manual Content Preservation** - Template boundary system
11. ⚠️ **Multi-Entity Pages** - Better support for grouped entities
12. ⚠️ **Logging Improvements** - Switch to loguru, better organization

### Not Now (YAGNI):
- ❌ Task orchestration library (too complex for solo dev)
- ❌ SQLite registry (JSON is fine for now)
- ❌ Cloud backups (local sufficient)
- ❌ Notification system (CLI output sufficient)
- ❌ Separate Python packages (monorepo with modules is simpler)

### Migration Approach:
**Incremental** - One phase at a time, validate each step, keep old system working until confident.

### Key Architecture Decisions:
- **Monorepo** with independent output modules
- **Python-only CLI** (eliminate Bash)
- **TOML configuration** (multi-language support)
- **Loguru logging** (best DX)
- **Typer CLI** (keep current)
- **Rich progress UI** (keep current)
- **Local backups** (simple, sufficient)
- **JSON for maps** (faster than SQLite in browser)

### Next Steps:
1. Review this document with user
2. Discuss open questions
3. Finalize architecture decisions
4. Create detailed implementation plan for Phase 1
5. Begin implementation

---

**End of Document**
