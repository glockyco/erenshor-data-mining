# Phase 3 Implementation Plan

**Status**: Ready to Execute
**Estimated Duration**: ~17 hours (simplified from 35-40 hours)
**Last Updated**: 2025-10-17

---

## Overview

Phase 3 builds on the solid infrastructure from Phase 2 to create the **actual application features and orchestration**. Phase 2 delivered all the core infrastructure components (database repositories, extraction wrappers, wiki client, sheets publisher), but left the orchestration and business logic as stubs. Phase 3 connects these components into working features.

**What Phase 2 Delivered**:
- ✅ Domain entity models (11 entities)
- ✅ Minimal database repository skeletons (ready for queries)
- ✅ SteamCMD wrapper (330 lines)
- ✅ AssetRipper wrapper (317 lines)
- ✅ Unity batch mode wrapper (517 lines)
- ✅ MediaWiki API client (623 lines)
- ✅ Wiki template parser with mwparserfromhell (418 lines)
- ✅ Google Sheets publisher (961 lines)
- ✅ Google Sheets formatter with 21 SQL queries
- ✅ 469 passing tests (Phase 1 + Phase 2 infrastructure)

**What Phase 3 Delivers**:
- 🎯 CLI command implementations (connect infrastructure to user)
- 🎯 Service orchestration layer (coordinate infrastructure)
- 🎯 Wiki generation and content merging (page generator, merger)
- 🎯 Precondition check system (fail fast before destructive operations)
- 🎯 Repository query methods (add as needed for features)
- 🎯 Integration testing (end-to-end workflows)

---

## Goals

1. **Complete CLI Commands**: Implement all stubbed commands (extract, wiki, sheets)
2. **Service Orchestration**: Build service layer to coordinate infrastructure
3. **Wiki Generation**: Generate wiki pages from database, preserve manual content
4. **Field Preservation**: Simple system for preserving user-curated content
5. **Manual Edit Notifications**: Push-style warnings in command output
6. **Google Sheets Deployment**: Wire up sheets deployment service
7. **Integration Testing**: Verify end-to-end workflows work correctly

---

## Scope

### In Scope

**CLI Command Implementations**:
- Extract commands (full, download, rip, export)
- Wiki commands (fetch, update, push)
- Sheets commands (list, deploy)

**Service Layer**:
- WikiService (orchestrate fetch → generate → merge → publish)
- SheetsService (orchestrate query → format → publish)
- BackupService (create backups per game build ID)

**Precondition System**:
- Per-command precondition checks (decorator pattern)
- Structural enforcement (can't bypass)
- Reuse doctor command logic

**Wiki Operations**:
- Page generation from database (use Jinja2 templates)
- Content merging (preserve manual sections, update managed templates)
- Category tag generation (programmatic, not template-based)
- Legacy template removal (10 templates → 4 active templates)

**Field Preservation**:
- Default: override with generated value
- Built-in handlers: preserve_if_blank, merge_sources, preserve_boss_type
- Template-specific configuration
- Custom handlers for special cases

**Manual Edit Notifications**:
- Push-style warnings in wiki update output
- Visual hierarchy with Rich
- Summary section at end of command
- Details file for drill-down

**Repository Queries**:
- Add query methods as needed for wiki generation
- Add query methods as needed for validation
- Use raw SQL (no query builders)

**Integration Tests**:
- End-to-end CLI workflows
- Service orchestration
- Wiki generation and merging
- Sheets deployment

### Out of Scope (Deferred to Later)

**NOT in Phase 3**:
- ❌ Advanced change detection (schema changes, C# diffs) - BACKLOG
- ❌ Cargo integration - HIGH-PRIORITY BACKLOG (post-rewrite)
- ❌ Performance optimization - BACKLOG
- ❌ Pre-defined section structures - BACKLOG
- ❌ Image upload automation - BACKLOG
- ❌ Backup restoration UI - Add when needed
- ❌ Performance metrics - BACKLOG
- ❌ Automatic vandalism detection - Removed (feature creep)
- ❌ Complex merge strategies - Removed (too complex)
- ❌ Concurrent edit detection - Removed (rate limiting)
- ❌ Multiple preservation modes - Removed (use custom handlers)

**Keep Using Bash/Existing**:
- ✅ Extraction pipeline (keep existing Bash CLI - it works!)
- ✅ Symlink management (Phase 1 implementation sufficient)
- ✅ Database validation (existing Unity C# scripts sufficient)

---

## Architecture Changes

### Service Layer Pattern

Phase 3 introduces a **thin service layer** to orchestrate infrastructure:

```
┌─────────────────────────────────────────┐
│         CLI Commands (Typer)            │
│  • User-facing commands                 │
│  • Argument parsing                     │
│  • Progress reporting                   │
│  • Error display                        │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│      Application Services (NEW)         │
│  • WikiService                          │
│  • SheetsService                  │
│  • BackupService                        │
│  • PreconditionChecker                  │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│         Infrastructure (Phase 2)        │
│  • MediaWikiClient                      │
│  • GoogleSheetsPublisher                │
│  • SteamCMDWrapper                      │
│  • AssetRipperWrapper                   │
│  • UnityBatchMode                       │
│  • Repositories                         │
└─────────────────────────────────────────┘
```

**Key Principle**: Services are **coordinators**, not feature implementations.
- Services call infrastructure, not the other way around
- Services handle business workflows, not low-level operations
- Keep services thin - complex logic goes in infrastructure or domain

### Repository Query Strategy

**YAGNI Approach**: Add query methods **only when needed** for specific features.

```python
# BAD (speculative)
class ItemRepository:
    def get_by_id(self, item_id: int) -> Item:  # Not needed yet
        ...
    def get_all(self) -> list[Item]:  # Not needed yet
        ...

# GOOD (on-demand)
class ItemRepository:
    def get_items_for_wiki_generation(self) -> list[Item]:
        """Get all items that need wiki pages (called from WikiService)."""
        sql = "SELECT * FROM Items WHERE ..."
        return self._execute_raw(sql, ())
```

**When to add a query method**:
1. CLI command needs it → Add query method
2. Service needs it → Add query method
3. Test needs it → Use existing methods or add if gap is real
4. "Might be useful" → DON'T add it (YAGNI)

---

## Task Breakdown

### Milestone 1: Foundation (Week 1)

**Goal**: Build core systems for fail-fast operations and safe backups.

#### Task 1.1: Implement Precondition Check System
**Estimated Time**: 3 hours

**Goal**: Structural enforcement of preconditions using decorator pattern.

**Actions**:
1. Create precondition system architecture:
   - `base.py` - PreconditionResult dataclass
   - `decorator.py` - @require_preconditions decorator
   - `checks/` directory - Per-check files
   - `checks/database.py` - Database checks (exists, valid, has_items)
   - `checks/filesystem.py` - File/directory checks
   - `checks/unity.py` - Unity project checks
   - `checks/steam.py` - Steam/game checks

2. Implement decorator pattern:
   ```python
   @require_preconditions(
       database_exists,
       database_valid,
       database_has_items,
   )
   def deploy_command(variant: str):
       # Command logic here
       pass
   ```

3. Integrate with commands:
   - Add decorator to extract, export, deploy commands
   - Commands fail fast if preconditions not met
   - Clear error messages with actionable hints

4. Reuse doctor command logic:
   - Extract health check functions
   - Share between doctor and preconditions
   - One source of truth for checks

**Files Created/Modified**:
- `src/erenshor/application/preconditions/base.py`
- `src/erenshor/application/preconditions/decorator.py`
- `src/erenshor/application/preconditions/checks/database.py`
- `src/erenshor/application/preconditions/checks/filesystem.py`
- `src/erenshor/application/preconditions/checks/unity.py`
- `src/erenshor/application/preconditions/checks/steam.py`
- `src/erenshor/cli/commands/extract.py` (add decorator)
- `src/erenshor/cli/commands/export.py` (add decorator)
- `src/erenshor/cli/commands/deploy.py` (add decorator)

**Tests**:
- Test precondition checks individually
- Test decorator enforcement
- Test error messages
- Test with all commands

**Dependencies**: None (foundation task)

**Success Criteria**:
- Decorator enforces preconditions structurally
- Can't bypass checks accidentally
- Minimal boilerplate (1 line per command)
- Clear error messages
- Reuses doctor command logic

**Implementation Notes**:
- See v3 analysis lines 421-578 for complete decorator implementation
- Context automatically built from command arguments
- Rich output for visual hierarchy
- Exit code 1 if any check fails

**Commit Message**: "feat(preconditions): add decorator-based precondition system"

---

#### Task 1.2: Implement Backup Service (Simplified)
**Estimated Time**: 2 hours

**Goal**: Automatic backups per game build ID, uncompressed for easy diffs.

**Actions**:
1. Create `BackupService` class:
   - Backup per game build ID (not DB version)
   - Uncompressed directory structure
   - Atomic operations (temp dir + rename)
   - Show disk usage when creating

2. Backup structure:
   ```
   .erenshor/backups/
   ├── main/
   │   ├── build-20370413/
   │   │   ├── metadata.json
   │   │   ├── database.sqlite       # Uncompressed
   │   │   ├── game-scripts/         # Uncompressed
   │   │   └── config.toml
   │   └── latest -> build-20456789/
   ```

3. Backup strategy:
   - Re-running on same build → overwrite old backup
   - New build → create new backup
   - Keep backups indefinitely
   - Show space usage on create

4. Integrate with export command:
   - Create backup after export completes
   - Use preconditions to check database exists

**Files Created/Modified**:
- `src/erenshor/application/services/backup.py`
- `src/erenshor/application/services/__init__.py`
- `src/erenshor/cli/commands/export.py` (integrate backup)

**Tests**:
- Test backup creation
- Test metadata stored correctly
- Test overwrite on same build
- Test new backup on new build
- Test space reporting

**Dependencies**: Task 1.1 (Precondition System)

**Success Criteria**:
- Backups created automatically per build ID
- Uncompressed for easy diffs
- Atomic operations (no partial backups)
- Space usage shown clearly
- Old backups overwritten on same build
- All backups kept indefinitely

**Implementation Notes**:
- See v3 analysis for uncompressed backup rationale
- No compression needed (disk space cheap)
- Primary use: running diffs across versions
- Show file counts and sizes

**Commit Message**: "feat(services): add backup service with build-based versioning"

---

#### Task 1.3: Implement Category Tag Generation
**Estimated Time**: 1 hour

**Goal**: Generate category tags programmatically, not via templates.

**Actions**:
1. Create category tag generation logic:
   ```python
   def _generate_category_tags(item: Item, kind: ItemKind) -> list[str]:
       """Generate category tags for item."""
       categories = []

       # Primary category from item kind
       primary = kind_to_category.get(kind, "Items")
       categories.append(primary)

       # Secondary categories from properties
       if item.is_quest_item:
           categories.append("Quest Items")
       if item.is_craftable:
           categories.append("Craftable")
       if item.rarity == "Legendary":
           categories.append("Legendary Items")

       return categories
   ```

2. Add to page generation:
   - Generate tags at end of page
   - Format as `[[Category:...]]`
   - Allow multi-category items

3. Update content merger:
   - Preserve manual category additions
   - Replace generated categories
   - Don't remove manual categories

**Files Created/Modified**:
- `src/erenshor/application/generators/page_generator.py`
- `src/erenshor/application/generators/content_merger.py`

**Tests**:
- Test category generation logic
- Test multi-category support
- Test preservation of manual categories

**Dependencies**: None (independent task)

**Success Criteria**:
- Categories generated programmatically
- Multi-category support works
- Manual categories preserved
- No template-based category encoding

**Implementation Notes**:
- See v3 analysis lines 88-198 for complete implementation
- Templates should NOT auto-add categories
- Generator decides categories based on item data

**Commit Message**: "feat(generators): add programmatic category tag generation"

---

### Milestone 2: Wiki Generation (Week 2)

**Goal**: Generate wiki pages with simplified template architecture.

#### Task 2.1: Add Repository Query Methods for Wiki Generation
**Estimated Time**: 2 hours

**Goal**: Add minimal query methods needed for wiki page generation.

**Actions**:
1. Identify required queries by examining wiki templates:
   - Items: Get all items with stats, classes, components
   - Spells/Skills: Get abilities with effects, classes, requirements
   - Characters: Get NPCs/enemies with abilities, loot, spawn points
   - Quests: DEFER (complex)
   - Factions: DEFER (low priority)

2. Add query methods to repositories:
   - `ItemRepository.get_items_for_wiki() -> list[Item]`
   - `SpellRepository.get_spells_for_wiki() -> list[Spell]`
   - `SkillRepository.get_skills_for_wiki() -> list[Skill]`
   - `CharacterRepository.get_characters_for_wiki() -> list[Character]`

3. Use raw SQL with explicit JOINs for relationships

4. Return domain entities (not raw dictionaries)

**Files Created/Modified**:
- `src/erenshor/infrastructure/database/repositories/items.py`
- `src/erenshor/infrastructure/database/repositories/spells.py`
- `src/erenshor/infrastructure/database/repositories/skills.py`
- `src/erenshor/infrastructure/database/repositories/characters.py`

**Tests**:
- Test queries return correct data
- Test relationships loaded correctly
- Test with 28KB fixture database
- Mock database for unit tests

**Dependencies**: None (repositories ready from Phase 2)

**Success Criteria**:
- Queries return all data needed for wiki templates
- Relationships loaded (items → components, characters → abilities)
- Performance acceptable (< 10 seconds for all entities)
- Type-safe (return domain entities)
- Tests verify correctness

**Commit Message**: "feat(database): add repository queries for wiki generation"

---

#### Task 2.2: Implement Simplified Page Generator
**Estimated Time**: 2.5 hours

**Goal**: Generate wiki pages using composition-based templates.

**Actions**:
1. Create template architecture:
   ```
   templates/wiki/
   ├── item.j2                    # {{Item}} template
   ├── fancy_weapon_table.j2      # {{Fancy-weapon}} tables
   ├── fancy_armor_table.j2       # {{Fancy-armor}} tables
   ├── fancy_charm.j2             # {{Fancy-charm}} template
   ├── enemy.j2                   # {{Enemy}} template
   └── shared/
       ├── sources.j2             # Reusable source fields
       ├── stats.j2               # Reusable stat fields
       └── effects.j2             # Reusable effect fields
   ```

2. Active templates (4 total):
   - `{{Item}}` - All items (base infobox)
   - `{{Fancy-weapon}}` - Weapon stat tables (3 per page)
   - `{{Fancy-armor}}` - Armor stat tables (3 per page)
   - `{{Fancy-charm}}` - Charm stat tables

3. Shared components using Jinja2 includes:
   ```jinja2
   {% include 'shared/sources.j2' %}
   ```

4. Add template filters:
   - `format_number` - Format large numbers (1000 → 1,000)
   - `format_percent` - Format percentages (0.15 → 15%)
   - `format_duration` - Format durations (3600 → 1h 0m)
   - `wiki_link` - Generate wiki links ([[Item Name]])

**Files Created/Modified**:
- `src/erenshor/application/generators/page_generator.py`
- `src/erenshor/application/generators/__init__.py`
- `templates/wiki/item.j2`
- `templates/wiki/fancy_weapon_table.j2`
- `templates/wiki/fancy_armor_table.j2`
- `templates/wiki/fancy_charm.j2`
- `templates/wiki/enemy.j2`
- `templates/wiki/shared/sources.j2`
- `templates/wiki/shared/stats.j2`
- `templates/wiki/shared/effects.j2`

**Tests**:
- Test template rendering
- Test data formatting (numbers, percents, durations)
- Test wiki link generation
- Test shared component inclusion
- Use fixture entities for tests

**Dependencies**: Task 2.1 (Repository Queries)

**Success Criteria**:
- Templates generate valid wikitext
- All entity types supported
- Data formatted correctly
- Shared components work
- Composition over inheritance
- Category tags generated

**Implementation Notes**:
- See v3 analysis lines 618-677 for active template list
- Legacy templates will be removed in Task 2.4
- Use composition for reusable parts (DRY)

**Commit Message**: "feat(generators): add simplified page generator with composition"

---

#### Task 2.3: Implement Minimal Field Preservation System
**Estimated Time**: 2 hours

**Goal**: Simple field preservation with default=override + custom handlers.

**Actions**:
1. Create field handler system:
   ```python
   # Built-in handlers (4 total)
   class OverrideHandler:        # Default
   class PreserveIfBlankHandler: # Keep old if generated is blank
   class MergeSourcesHandler:    # Merge old + new sources
   class PreserveBossTypeHandler:# Special case for Boss type
   ```

2. Configuration format:
   ```toml
   [wiki.field_preservation]
   default = "override"

   [wiki.field_preservation.item]
   othersource = "merge_sources"
   imagecaption = "preserve_if_blank"
   relatedquest = "preserve_if_blank"

   [wiki.field_preservation.enemy]
   imagecaption = "preserve_if_blank"
   type = "preserve_boss_type"
   ```

3. Create FieldResolver:
   - Load handlers from config
   - Apply per template.field
   - Default to override
   - Support custom handlers

4. Integrate with content merger:
   - Use resolver for field conflicts
   - Pass context (template type, item kind)
   - Simple: keep old OR replace (no complex merging)

**Files Created/Modified**:
- `src/erenshor/application/services/field_handlers.py`
- `src/erenshor/application/services/field_resolver.py`
- `src/erenshor/application/generators/content_merger.py`
- `config.toml` (add field preservation config)

**Tests**:
- Test each handler individually
- Test resolver logic
- Test config loading
- Test with fixture templates

**Dependencies**: Task 2.2 (Page Generator)

**Success Criteria**:
- Default behavior is override
- 4 built-in handlers work correctly
- Template-specific config works
- Easy to add custom handlers
- No complex merge strategies

**Implementation Notes**:
- See v3 analysis lines 806-1067 for complete implementation
- Based on actual old code usage (only 4 fields preserved)
- Everything else can be custom handlers
- Even "preserve" is just a built-in handler

**Commit Message**: "feat(services): add minimal field preservation system"

---

#### Task 2.4: Implement Legacy Template Remover
**Estimated Time**: 1 hour

**Goal**: Remove 10 discontinued templates, keep 4 active templates.

**Actions**:
1. Create LegacyTemplateRemover:
   ```python
   # Item templates → {{Item}}
   "Weapon": "Item",
   "Armor": "Item",
   "Consumable": "Item",
   "Mold": "Item",
   "Ability Books": "Item",
   "Ability_Books": "Item",
   "Auras": "Item",

   # Character templates → {{Enemy}}
   "Character": "Enemy",
   "Pet": "Enemy",

   # Templates to remove entirely
   "Enemy Stats"
   ```

2. Integrate with content merger:
   - Run remover BEFORE merging
   - Replace template names
   - Keep {{Fancy-weapon}}, {{Fancy-armor}}, {{Fancy-charm}} tables

3. Test with real wiki pages

**Files Created/Modified**:
- `src/erenshor/application/services/legacy_template_remover.py`
- `src/erenshor/application/generators/content_merger.py` (integrate)

**Tests**:
- Test each legacy template replacement
- Test with sample wiki pages
- Test preservation of Fancy tables

**Dependencies**: Task 2.3 (Field Preservation)

**Success Criteria**:
- All 10 legacy templates replaced
- Active templates preserved
- Fancy tables untouched
- Works with real pages

**Implementation Notes**:
- See v3 analysis lines 618-777 for complete mapping
- Old code had these replacements scattered
- Centralize in one service

**Commit Message**: "feat(services): add legacy template removal system"

---

#### Task 2.5: Implement Wiki Service and Commands
**Estimated Time**: 2.5 hours

**Goal**: Orchestrate fetch → generate → merge → publish workflow with push-style notifications.

**Actions**:
1. Create `WikiService` class:
   - Orchestrate complete wiki workflow
   - `fetch_pages()` - Download current wiki pages
   - `generate_pages()` - Generate updated pages from database
   - `merge_pages()` - Merge with field preservation
   - `publish_pages()` - Upload merged pages to wiki
   - Track progress with Rich progress bars
   - Support dry-run mode

2. Add manual edit detection:
   - Query recentchanges API (notification only)
   - List pages with manual edits
   - NO automatic preservation
   - Show in command output (push-style)

3. Push-style UX with Rich:
   ```python
   # Summary at end of command
   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ ⚠ Manual Edits Detected (3 pages) ┃
   ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
     Iron Sword: field 'othersource' by WikiUser123
     Health Potion: field 'imagecaption' by Editor456

   Review: .erenshor/wiki/manual-edits.txt
   ```

4. Implement wiki commands:
   - `wiki fetch` - Fetch pages from wiki
   - `wiki update` - Generate + merge locally
   - `wiki push` - Upload to wiki

**Files Created/Modified**:
- `src/erenshor/application/services/wiki_service.py`
- `src/erenshor/application/services/manual_edit_detector.py`
- `src/erenshor/cli/commands/wiki.py` (update from stub)

**Tests**:
- Mock WikiService
- Test command orchestration
- Test manual edit detection
- Test push-style notifications
- Test dry-run mode

**Dependencies**: Task 2.4 (Legacy Template Remover)

**Success Criteria**:
- Complete workflow works end-to-end
- Manual edits shown automatically (push-style)
- Visual hierarchy clear with Rich
- No new CLI commands needed
- Summary at end of output
- Details file for drill-down

**Implementation Notes**:
- See v3 analysis lines 1070-1378 for UX design
- Push, don't pull - show important info automatically
- Use importance levels: ✓ Green, ℹ Blue, ⚠ Yellow, ✗ Red
- Progressive disclosure: summary → file → full data

**Commit Message**: "feat(cli): implement wiki commands with push-style notifications"

---

### Milestone 3: Google Sheets Deployment (Week 3, First Half)

**Goal**: Wire up sheets deployment service (no changes from original plan).

#### Task 3.1: Implement Sheets Deploy Service
**Estimated Time**: 2 hours

**Goal**: Orchestrate query → format → publish workflow for Google Sheets.

**Actions**:
1. Create `src/erenshor/application/services/sheets_deploy_service.py`:
   - `SheetsService` class
   - List available sheets (query files in `queries/`)
   - Load SQL queries from files
   - Execute queries via database connection
   - Format results via SheetsFormatter
   - Publish to Google Sheets via GoogleSheetsPublisher
   - Track deployment progress with Rich
   - Support deploying specific sheets or all sheets
   - Support dry-run mode (show data without publishing)

2. Add sheet metadata:
   - Sheet name (from filename)
   - Description (from SQL comment)
   - Row count
   - Last deployed timestamp

3. Generate deployment report:
   - Sheets deployed
   - Rows written
   - Errors encountered
   - Duration

**Files Created/Modified**:
- `src/erenshor/application/services/sheets_deploy_service.py`
- `src/erenshor/application/services/__init__.py`

**Tests**:
- Mock database connection
- Mock SheetsFormatter and GoogleSheetsPublisher
- Test query loading
- Test deployment orchestration
- Test dry-run mode
- Test error handling

**Dependencies**: None (infrastructure ready from Phase 2)

**Success Criteria**:
- Can list available sheets
- Can deploy specific sheets
- Can deploy all sheets
- Dry-run mode works
- Progress reporting clear
- Deployment report useful

**Commit Message**: "feat(services): add Google Sheets deployment service"

---

#### Task 3.2: Implement Sheets Commands
**Estimated Time**: 1.5 hours

**Goal**: Wire up sheets CLI commands to SheetsService.

**Actions**:
1. Implement `sheets list`:
   - Call `SheetsService.list_sheets()`
   - Show sheet names, descriptions, row counts
   - Show which sheets are configured for current variant
   - Format as Rich table

2. Implement `sheets deploy`:
   - Call `SheetsService.deploy()`
   - Support --sheets flag for specific sheets (multiple)
   - Support --all-sheets flag for deploying all
   - Show deployment progress
   - Show deployment report after completion
   - Support --dry-run (show data without publishing)
   - Require Google Sheets credentials validation

**Files Created/Modified**:
- `src/erenshor/cli/commands/sheets.py` (update from stub)

**Tests**:
- Mock SheetsService
- Test command orchestration
- Test --sheets flag (multiple values)
- Test --all-sheets flag
- Test --dry-run mode
- Test credential validation
- Integration test with real SheetsService

**Dependencies**: Task 3.1 (Sheets Deploy Service)

**Success Criteria**:
- `sheets list` shows available sheets
- `sheets deploy --sheets X Y` deploys specific sheets
- `sheets deploy --all-sheets` deploys everything
- Dry-run mode works
- Progress reporting clear
- Deployment report useful
- Credential errors caught early

**Commit Message**: "feat(cli): implement sheets commands for deployment"

---

### Milestone 4: Integration Testing (Week 3, Second Half)

**Goal**: Verify end-to-end workflows work correctly.

#### Task 4.1: Add CLI Integration Tests
**Estimated Time**: 2.5 hours

**Goal**: Test complete CLI workflows with real components.

**Actions**:
1. Create `tests/integration/cli/test_extract_workflow.py`:
   - Test `extract full` with mocked external services (Steam, Unity)
   - Use 28KB fixture database
   - Verify backup creation
   - Test skip flags

2. Create `tests/integration/cli/test_wiki_workflow.py`:
   - Test `wiki fetch → update → push` workflow
   - Mock MediaWiki API
   - Use 28KB fixture database
   - Verify page generation
   - Verify content merging
   - Test dry-run mode
   - Test manual edit notifications

3. Create `tests/integration/cli/test_sheets_workflow.py`:
   - Test `sheets list` and `sheets deploy`
   - Mock Google Sheets API
   - Use 28KB fixture database
   - Verify all 21 queries work
   - Test dry-run mode

4. Use pytest fixtures for:
   - Temporary config files
   - Mock credentials
   - 28KB fixture database
   - Temporary output directories

**Files Created/Modified**:
- `tests/integration/cli/__init__.py`
- `tests/integration/cli/test_extract_workflow.py`
- `tests/integration/cli/test_wiki_workflow.py`
- `tests/integration/cli/test_sheets_workflow.py`

**Tests**: This task IS the tests (integration tests for CLI)

**Dependencies**: Tasks 1.1-3.2 (all CLI commands implemented)

**Success Criteria**:
- End-to-end workflows pass
- External services properly mocked
- 28KB fixture database used
- Tests run in < 30 seconds
- Tests are reliable (no flakiness)

**Commit Message**: "test(integration): add CLI workflow integration tests"

---

#### Task 4.2: Add Service Integration Tests
**Estimated Time**: 2 hours

**Goal**: Test service orchestration with real infrastructure.

**Actions**:
1. Create `tests/integration/services/test_wiki_service.py`:
   - Test WikiService with real MediaWikiClient (mocked API)
   - Test with real PageGenerator and ContentMerger
   - Test with real TemplateParser
   - Use 28KB fixture database
   - Verify complete fetch → generate → merge workflow
   - Test manual edit detection

2. Create `tests/integration/services/test_sheets_deploy_service.py`:
   - Test SheetsService with real GoogleSheetsPublisher (mocked API)
   - Test with real SheetsFormatter
   - Use 28KB fixture database
   - Verify complete query → format → publish workflow
   - Test all 21 query files

3. Create `tests/integration/services/test_backup_service.py`:
   - Test BackupService with real file operations
   - Test with real database files
   - Verify backup creation (uncompressed)
   - Test metadata storage
   - Test overwrite on same build
   - Test atomic operations

**Files Created/Modified**:
- `tests/integration/services/__init__.py`
- `tests/integration/services/test_wiki_service.py`
- `tests/integration/services/test_sheets_deploy_service.py`
- `tests/integration/services/test_backup_service.py`

**Tests**: This task IS the tests (integration tests for services)

**Dependencies**: Task 4.1 (CLI Integration Tests)

**Success Criteria**:
- Service orchestration tested thoroughly
- Real infrastructure components used (with mocked APIs)
- 28KB fixture database used
- Tests verify correctness of workflows
- Tests run in < 30 seconds

**Commit Message**: "test(integration): add service orchestration tests"

---

#### Task 4.3: Add Repository Integration Tests
**Estimated Time**: 1.5 hours

**Goal**: Test repository queries with real database.

**Actions**:
1. Create `tests/integration/database/test_wiki_queries.py`:
   - Test all repository methods added in Task 2.1
   - Use 28KB fixture database
   - Verify query results match expected data
   - Test relationships loaded correctly
   - Test performance (queries should be < 5 seconds)

2. Create fixtures:
   - Known entities from 28KB database
   - Expected query results
   - Relationship assertions

3. Test edge cases:
   - Empty results
   - NULL fields
   - Complex relationships (items with many components)

**Files Created/Modified**:
- `tests/integration/database/test_wiki_queries.py`
- `tests/fixtures/database/expected_entities.json` (expected results)

**Tests**: This task IS the tests (integration tests for repositories)

**Dependencies**: Task 2.1 (Repository Queries)

**Success Criteria**:
- All repository queries tested
- Real database used (28KB fixture)
- Query results verified correct
- Relationships validated
- Performance acceptable

**Commit Message**: "test(integration): add repository query integration tests"

---

## Task Dependencies

```
Milestone 1: Foundation
Task 1.1 (Preconditions) → Task 1.2 (Backup Service)
Task 1.3 (Category Tags) [independent]

Milestone 2: Wiki Generation
Task 2.1 (Repository Queries) → Task 2.2 (Page Generator) → Task 2.3 (Field Preservation)
                                                          ↓
                                Task 2.4 (Legacy Remover) → Task 2.5 (Wiki Service)

Milestone 3: Google Sheets
Task 3.1 (Sheets Deploy Service) → Task 3.2 (Sheets Commands)

Milestone 4: Integration Testing
Tasks 1.1-3.2 (All Commands) → Task 4.1 (CLI Tests)
                             ↓
                Task 4.2 (Service Tests) → Task 4.3 (Repository Tests)
```

**Parallel Opportunities**:
- Milestones 1, 2, 3 can be worked in parallel (mostly independent)
- Task 4.1-4.3 can be done in parallel (after dependencies met)

---

## Testing Strategy

### Unit Tests (70%)
**What**: Individual functions and classes in isolation
**How**: Mock dependencies, test single responsibilities
**Coverage Target**: >90% for new code

**Examples**:
- Precondition checks (all scenarios)
- Field handlers (each handler)
- Category tag generation
- Legacy template removal
- Template composition

### Integration Tests (25%)
**What**: Components working together with real infrastructure
**How**: Use 28KB fixture database, mock external APIs
**Coverage Target**: >80% for workflows

**Examples**:
- CLI workflows (extract, wiki, sheets)
- Service orchestration
- Repository queries with real database
- End-to-end data flow

### Regression Tests (5%)
**What**: Known edge cases and bugs
**How**: Fixtures from production, expected outputs
**Coverage Target**: Known issues covered

**Examples**:
- Problematic items (special characters, edge cases)
- Complex wiki pages (manual edits, nested templates)
- Multi-category items

### Test Organization
```
tests/
├── unit/                       # Fast, isolated tests
│   ├── cli/                    # CLI command tests (mocked services)
│   ├── services/               # Service tests (mocked infrastructure)
│   ├── generators/             # Generator tests (mocked database)
│   └── preconditions/          # Precondition tests
├── integration/                # Real components (28KB fixture)
│   ├── cli/                    # End-to-end CLI workflows
│   ├── services/               # Service orchestration
│   └── database/               # Repository queries
└── fixtures/                   # Test data
    ├── database/               # 28KB fixture + extras
    ├── wiki_pages/             # Sample wiki pages
    └── expected/               # Expected outputs
```

---

## Success Criteria

Phase 3 is complete when:

1. ✅ **All CLI Commands Work**:
   - Extract: full, download, rip, export
   - Wiki: fetch, update, push
   - Sheets: list, deploy

2. ✅ **Service Orchestration Complete**:
   - WikiService orchestrates fetch → generate → merge → publish
   - SheetsService orchestrates query → format → publish
   - BackupService creates backups per build ID
   - PreconditionChecker enforces fail-fast

3. ✅ **Wiki Generation Works**:
   - Pages generated from database
   - Manual content preserved via field handlers
   - Templates render correctly (4 active templates)
   - Legacy templates removed (10 templates)
   - Category tags generated programmatically
   - Manual edits shown in output (push-style)

4. ✅ **Sheets Deployment Works**:
   - All 21 query files execute correctly
   - Data formatted for spreadsheets
   - Published to Google Sheets via API

5. ✅ **Testing Complete**:
   - Integration tests pass (CLI, services, repositories)
   - Test coverage >80%
   - All 469+ tests passing

6. ✅ **Quality Gates**:
   - Type checking passes (mypy strict)
   - Linting passes (ruff)
   - Pre-commit hooks pass
   - No critical code smells

---

## Risks and Mitigations

### Risk 1: Template Complexity
**Risk**: Wiki templates might be more complex than anticipated
**Likelihood**: Low (simplified to 4 templates)
**Impact**: Medium
**Mitigation**:
- Start with simplest templates (items)
- Use composition (shared components)
- Test with real data early

### Risk 2: Field Preservation Edge Cases
**Risk**: Custom handlers might not cover all cases
**Likelihood**: Medium
**Impact**: Low (easy to add handlers)
**Mitigation**:
- Default to override (safe)
- Only 4 fields actually preserved in old code
- Easy to add custom handlers later
- Configuration-driven

### Risk 3: Performance Issues
**Risk**: Generating hundreds of wiki pages might be slow
**Likelihood**: Low
**Impact**: Low (acceptable if < 5 minutes)
**Mitigation**:
- Profile and optimize queries if needed
- Use batch operations where possible
- Add progress reporting
- Defer optimization unless needed (YAGNI)

### Risk 4: Scope Creep
**Risk**: Temptation to add features beyond Phase 3 scope
**Likelihood**: High
**Impact**: High (delays completion)
**Mitigation**:
- Strict adherence to YAGNI principle
- Defer "nice to have" features to backlog
- Focus on MVP for each feature
- Review plan before adding unplanned work
- User approval for any scope changes

---

## Estimated Timeline

**Total Estimated Time**: ~17 hours (simplified from 35-40 hours)

**Breakdown**:
- **Milestone 1 (Foundation)**: 6 hours
  - Task 1.1: 3h (Preconditions)
  - Task 1.2: 2h (Backup Service)
  - Task 1.3: 1h (Category Tags)

- **Milestone 2 (Wiki Generation)**: 10 hours
  - Task 2.1: 2h (Repository Queries)
  - Task 2.2: 2.5h (Page Generator)
  - Task 2.3: 2h (Field Preservation)
  - Task 2.4: 1h (Legacy Remover)
  - Task 2.5: 2.5h (Wiki Service)

- **Milestone 3 (Sheets Deployment)**: 3.5 hours
  - Task 3.1: 2h (Sheets Service)
  - Task 3.2: 1.5h (Sheets Commands)

- **Milestone 4 (Integration Testing)**: 6 hours
  - Task 4.1: 2.5h (CLI Tests)
  - Task 4.2: 2h (Service Tests)
  - Task 4.3: 1.5h (Repository Tests)

**Note**: Timeline assumes part-time work. Full-time work could complete in less than 1 week.

---

## Notes

### YAGNI Reminders
- Only add repository query methods when needed for features
- Don't speculatively add "useful" utility functions
- Keep services thin - complex logic goes in infrastructure
- Templates should be minimal viable versions
- No feature creep (vandalism detection, complex merging, etc.)

### Implementation Tips
1. Commit after each task completion
2. Run tests frequently (`uv run pytest`)
3. Use type checking to catch issues early (`uv run mypy src/`)
4. Keep commits focused and atomic
5. Test with 28KB fixture database regularly
6. Use dry-run mode for testing without side effects
7. Document unexpected issues or decisions

### Quality Gates
- Each task must pass type checking (mypy strict)
- Each task must pass linting (ruff)
- Each task must include tests
- Each task must update documentation if needed
- Integration tests must use 28KB fixture database
- No task should take >3 hours

### Key Simplifications from Original Plan

**Removed (saves ~18 hours)**:
- ❌ Zipped backups
- ❌ Database change detection service
- ❌ Automatic vandalism detection
- ❌ Complex merge strategies
- ❌ Concurrent edit detection
- ❌ Interactive conflict resolution
- ❌ Multiple preservation modes

**Simplified (saves ~8 hours)**:
- ✅ Backups: Per build ID, uncompressed
- ✅ Preconditions: Decorator pattern (structural)
- ✅ Templates: 4 active (not 7+)
- ✅ Field preservation: Default=override + custom handlers
- ✅ Manual edits: Push-style notifications (no new commands)

**Result**: 17 hours vs 35-40 hours (58% reduction)

---

## Out of Scope - Backlog Items

These are explicitly NOT in Phase 3 but documented for future reference:

### High Priority (Do After Phase 3)
1. **Cargo Integration** (6 weeks) - First item after rewrite stabilizes
2. **Advanced Change Detection** (2 weeks) - Schema changes, C# script diffs

### Medium Priority
3. **Quest/Faction/Zone Templates** - Complex entity templates
4. **Image Upload Automation** - Automatic image uploading to wiki
5. **Backup Restoration UI** - Interactive backup restore

### Low Priority
6. **Performance Optimization** - Only if needed
7. **Shell Completion Scripts** - Bash/Zsh completion
8. **Performance Metrics** - Tracking and reporting

---

**End of Phase 3 Implementation Plan**
