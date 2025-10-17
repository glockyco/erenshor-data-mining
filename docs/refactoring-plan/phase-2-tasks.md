# Phase 2: Data Extraction Pipeline - Detailed Task Breakdown

**Status**: Ready to Execute
**Estimated Duration**: 4-6 weeks
**Last Updated**: 2025-10-17

---

## Overview

Phase 2 implements the complete data extraction pipeline and output systems. This phase focuses on:
1. Database layer with repository pattern
2. Data extraction pipeline (SteamCMD, AssetRipper, Unity export)
3. Wiki operations (template system, MediaWiki client, page generation)
4. Google Sheets deployment
5. Integration testing with real database

**Key Principle**: Each task is atomic, independently committable, and builds on Phase 1 foundation.

---

## Task Dependencies

```
Task 1 (Domain Models) → Task 2 (Database Repository Base)
                       ↓
Task 3 (Entity Repositories) → Task 4 (Query Builders)
                             ↓
Task 5 (Repo Tests) ← Task 4
                             ↓
Task 6 (SteamCMD Wrapper) → Task 7 (AssetRipper Wrapper)
                          ↓
Task 8 (Unity Wrapper) → Task 9 (Extract Commands)
                       ↓
Task 10 (Backup System) → Task 11 (Change Detection)
                        ↓
Task 12 (Extract Tests) ← Task 11
                        ↓
Task 13 (MediaWiki Client) → Task 14 (Wiki Fetcher)
                           ↓
Task 15 (Template Parser) → Task 16 (Template Context)
                          ↓
Task 17 (Page Generator) → Task 18 (Content Merger)
                         ↓
Task 19 (Wiki Publisher) → Task 20 (Wiki Tests)
                         ↓
Task 21 (Sheets Formatter) → Task 22 (Sheets Publisher)
                           ↓
Task 23 (Sheets Deploy) → Task 24 (Sheets Tests)
                        ↓
Task 25 (Integration Tests) → Task 26 (End-to-End Tests)
                            ↓
Task 27 (Documentation) → Task 28 (Final Integration)
```

---

## Tasks (Ordered by Dependencies)

### Task 1: Create Domain Entity Models

**Goal**: Define domain models for game entities matching Unity export schema.

**Actions**:
- Create `src/erenshor/domain/entities/base.py`:
  - `BaseEntity` - Base class for all entities
  - Common fields (id, created_at, updated_at)
  - Type hints and validation
- Create entity models:
  - `src/erenshor/domain/entities/item.py` - Item model
  - `src/erenshor/domain/entities/spell.py` - Spell model
  - `src/erenshor/domain/entities/skill.py` - Skill model
  - `src/erenshor/domain/entities/character.py` - Character/NPC model
  - `src/erenshor/domain/entities/quest.py` - Quest model
  - `src/erenshor/domain/entities/faction.py` - Faction model
  - `src/erenshor/domain/entities/zone.py` - Zone model
  - `src/erenshor/domain/entities/loot_table.py` - LootTable model
  - `src/erenshor/domain/entities/spawn_point.py` - SpawnPoint model
- Use Pydantic for validation
- Match existing database schema exactly
- Add resource_name extraction methods
- Add stable_key properties (resource-name-based)

**Files Created/Modified**:
- `src/erenshor/domain/entities/base.py`
- `src/erenshor/domain/entities/item.py`
- `src/erenshor/domain/entities/spell.py`
- `src/erenshor/domain/entities/skill.py`
- `src/erenshor/domain/entities/character.py`
- `src/erenshor/domain/entities/quest.py`
- `src/erenshor/domain/entities/faction.py`
- `src/erenshor/domain/entities/zone.py`
- `src/erenshor/domain/entities/loot_table.py`
- `src/erenshor/domain/entities/spawn_point.py`

**Dependencies**: None (builds on Phase 1 structure)

**Success Criteria**:
- All major entity types have models
- Models match database schema
- Resource name extraction works
- Stable key generation works
- Type hints complete
- Can instantiate models programmatically

**Commit Message**: "feat(domain): add entity models for game data"

**Estimated Time**: 90 minutes

---

### Task 2: Implement Database Repository Base

**Goal**: Create base repository pattern for database access.

**Actions**:
- Create `src/erenshor/infrastructure/database/connection.py`:
  - `DatabaseConnection` class
  - SQLite connection pooling
  - Context manager support
  - Transaction handling
  - Read-only mode support
- Create `src/erenshor/infrastructure/database/repository.py`:
  - `BaseRepository[T]` generic base class
  - CRUD operations (create, read, update, delete)
  - Bulk operations (insert_many, update_many)
  - Query builder integration
  - Type-safe query results
- Add connection string configuration
- Support variant-specific databases
- Error handling and logging

**Files Created/Modified**:
- `src/erenshor/infrastructure/database/connection.py`
- `src/erenshor/infrastructure/database/repository.py`

**Dependencies**: Task 1 (Domain Models)

**Success Criteria**:
- Connection pooling works
- Transactions commit/rollback correctly
- Base repository provides type-safe CRUD
- Can query database with type hints
- Proper error handling
- Context managers work

**Commit Message**: "feat(database): implement repository pattern with connection pooling"

**Estimated Time**: 60 minutes

---

### Task 3: Create Entity Repositories

**Goal**: Implement concrete repositories for each entity type.

**Actions**:
- Create `src/erenshor/infrastructure/database/repositories/__init__.py`
- Create repository classes:
  - `src/erenshor/infrastructure/database/repositories/items.py` - ItemRepository
  - `src/erenshor/infrastructure/database/repositories/spells.py` - SpellRepository
  - `src/erenshor/infrastructure/database/repositories/skills.py` - SkillRepository
  - `src/erenshor/infrastructure/database/repositories/characters.py` - CharacterRepository
  - `src/erenshor/infrastructure/database/repositories/quests.py` - QuestRepository
  - `src/erenshor/infrastructure/database/repositories/factions.py` - FactionRepository
  - `src/erenshor/infrastructure/database/repositories/zones.py` - ZoneRepository
  - `src/erenshor/infrastructure/database/repositories/loot_tables.py` - LootTableRepository
  - `src/erenshor/infrastructure/database/repositories/spawn_points.py` - SpawnPointRepository
- Each repository:
  - Inherits from BaseRepository[EntityType]
  - Implements entity-specific queries
  - Maps database rows to domain models
  - Handles relationships (junction tables)
- Add bulk operations for performance
- Include common filters (by resource name, by type, etc.)

**Files Created/Modified**:
- `src/erenshor/infrastructure/database/repositories/__init__.py`
- `src/erenshor/infrastructure/database/repositories/items.py`
- `src/erenshor/infrastructure/database/repositories/spells.py`
- `src/erenshor/infrastructure/database/repositories/skills.py`
- `src/erenshor/infrastructure/database/repositories/characters.py`
- `src/erenshor/infrastructure/database/repositories/quests.py`
- `src/erenshor/infrastructure/database/repositories/factions.py`
- `src/erenshor/infrastructure/database/repositories/zones.py`
- `src/erenshor/infrastructure/database/repositories/loot_tables.py`
- `src/erenshor/infrastructure/database/repositories/spawn_points.py`

**Dependencies**: Task 2 (Repository Base)

**Success Criteria**:
- All entity repositories implemented
- Type-safe entity queries work
- Relationship loading works (lazy/eager)
- Bulk operations performant
- Common filters implemented
- No N+1 query issues

**Commit Message**: "feat(database): add entity-specific repositories"

**Estimated Time**: 90 minutes

---

### Task 4: Add Query Builders

**Goal**: Provide fluent query builders for complex queries.

**Actions**:
- Create `src/erenshor/infrastructure/database/queries.py`:
  - `QueryBuilder` class for fluent queries
  - Support WHERE, JOIN, ORDER BY, LIMIT
  - Type-safe column references
  - Query composition (AND, OR conditions)
  - Parameterized queries (SQL injection prevention)
- Create common query patterns:
  - `get_items_by_slot(slot: str)`
  - `get_characters_in_zone(zone: str)`
  - `get_spells_by_class(class_name: str)`
  - `get_quest_requirements(quest_id: int)`
- Add query caching for repeated queries
- Include query logging (DEBUG level)

**Files Created/Modified**:
- `src/erenshor/infrastructure/database/queries.py`

**Dependencies**: Task 3 (Entity Repositories)

**Success Criteria**:
- Fluent API works intuitively
- Type safety maintained
- SQL injection prevented
- Common queries implemented
- Query logging functional
- Performance acceptable

**Commit Message**: "feat(database): add fluent query builders"

**Estimated Time**: 60 minutes

---

### Task 5: Add Database Tests

**Goal**: Test database layer with comprehensive coverage.

**Actions**:
- Create `tests/unit/infrastructure/database/__init__.py`
- Create `tests/unit/infrastructure/database/test_connection.py`:
  - Test connection pooling
  - Test transactions
  - Test context managers
  - Test error handling
- Create `tests/unit/infrastructure/database/test_repository.py`:
  - Test CRUD operations
  - Test bulk operations
  - Test query building
  - Test type safety
- Create `tests/integration/database/test_repositories.py`:
  - Test with 28KB fixture database
  - Test entity queries
  - Test relationship loading
  - Test complex joins
- Use in-memory SQLite for unit tests
- Use 28KB fixture for integration tests

**Files Created/Modified**:
- `tests/unit/infrastructure/database/__init__.py`
- `tests/unit/infrastructure/database/test_connection.py`
- `tests/unit/infrastructure/database/test_repository.py`
- `tests/integration/database/__init__.py`
- `tests/integration/database/test_repositories.py`

**Dependencies**: Task 4 (Query Builders)

**Success Criteria**:
- All tests pass
- >80% coverage for database module
- Unit tests fast (<100ms)
- Integration tests with real data
- Edge cases covered

**Commit Message**: "test(database): add comprehensive database layer tests"

**Estimated Time**: 75 minutes

---

### Task 6: Implement SteamCMD Wrapper

**Goal**: Python wrapper for downloading game files via SteamCMD.

**Actions**:
- Create `src/erenshor/infrastructure/extraction/__init__.py`
- Create `src/erenshor/infrastructure/extraction/steamcmd.py`:
  - `SteamCMDWrapper` class
  - Download game by app ID
  - Verify download integrity
  - Check for updates
  - Handle Steam authentication
  - Progress reporting
  - Timeout handling
- Support all variants (main, playtest, demo)
- Detect SteamCMD installation
- Provide clear error messages
- Log all operations

**Files Created/Modified**:
- `src/erenshor/infrastructure/extraction/__init__.py`
- `src/erenshor/infrastructure/extraction/steamcmd.py`

**Dependencies**: Task 5 (Database Tests) - establishes infrastructure layer works

**Success Criteria**:
- Can download game files
- Detects existing installations
- Reports download progress
- Handles authentication
- Verifies file integrity
- Works for all variants
- Clear error messages

**Commit Message**: "feat(extraction): add SteamCMD wrapper for game downloads"

**Estimated Time**: 60 minutes

---

### Task 7: Implement AssetRipper Wrapper

**Goal**: Python wrapper for extracting Unity project via AssetRipper.

**Actions**:
- Create `src/erenshor/infrastructure/extraction/assetripper.py`:
  - `AssetRipperWrapper` class
  - Extract Unity project from game files
  - Configure export settings
  - Verify extraction success
  - Progress reporting
  - Handle AssetRipper errors
- Detect AssetRipper installation
- Validate output directory structure
- Check Unity version compatibility
- Log extraction process

**Files Created/Modified**:
- `src/erenshor/infrastructure/extraction/assetripper.py`

**Dependencies**: Task 6 (SteamCMD Wrapper)

**Success Criteria**:
- Can extract Unity project
- Detects AssetRipper installation
- Reports extraction progress
- Validates output structure
- Handles errors gracefully
- Unity version check works
- Clear logging

**Commit Message**: "feat(extraction): add AssetRipper wrapper for Unity extraction"

**Estimated Time**: 50 minutes

---

### Task 8: Implement Unity Batch Mode Wrapper

**Goal**: Python wrapper for running Unity Editor in batch mode.

**Actions**:
- Create `src/erenshor/infrastructure/extraction/unity.py`:
  - `UnityWrapper` class
  - Run Unity in batch mode
  - Execute ExportBatch.cs script
  - Parse Unity log output
  - Detect export completion
  - Handle Unity crashes
  - Progress extraction from logs
- Verify Unity installation and version
- Validate export database
- Check for export errors
- Clean log parsing

**Files Created/Modified**:
- `src/erenshor/infrastructure/extraction/unity.py`

**Dependencies**: Task 7 (AssetRipper Wrapper)

**Success Criteria**:
- Can run Unity batch mode
- Executes ExportBatch.cs correctly
- Parses logs for progress
- Detects export completion
- Handles crashes gracefully
- Validates output database
- Clear error reporting

**Commit Message**: "feat(extraction): add Unity batch mode wrapper"

**Estimated Time**: 60 minutes

---

### Task 9: Implement Extract Commands

**Goal**: Wire up extraction commands in CLI.

**Actions**:
- Update `src/erenshor/cli/commands/extract.py`:
  - Implement `extract download` - Download via SteamCMD
  - Implement `extract rip` - Extract via AssetRipper
  - Implement `extract export` - Export via Unity batch mode
  - Implement `extract full` - Run complete pipeline
- Add progress indicators with Rich
- Add dry-run support
- Add resume support (skip completed steps)
- Integrate with logging system
- Handle interruptions (Ctrl+C)
- Report pipeline status
- Show next steps after completion

**Files Created/Modified**:
- `src/erenshor/cli/commands/extract.py` (updated from stub)

**Dependencies**: Task 8 (Unity Wrapper)

**Success Criteria**:
- All extract commands work
- Full pipeline runs successfully
- Progress reporting clear
- Dry-run mode works
- Resume from interruption works
- Error handling robust
- Next steps helpful

**Commit Message**: "feat(cli): implement extract commands for full pipeline"

**Estimated Time**: 75 minutes

---

### Task 10: Implement Backup System

**Goal**: Automatic backups on database changes.

**Actions**:
- Create `src/erenshor/infrastructure/storage/backup.py`:
  - `BackupManager` class
  - Create backup on database version change
  - Store metadata (timestamp, version, entity counts)
  - Compression (gzip)
  - Backup verification
  - List available backups
  - Restore from backup (with confirmation)
- Integrate with extract pipeline
- Add `erenshor backup info` command updates
- Add `erenshor backup list` command
- Add `erenshor backup restore <backup_id>` command
- Store backups in `.erenshor/backups/`

**Files Created/Modified**:
- `src/erenshor/infrastructure/storage/backup.py`
- `src/erenshor/cli/commands/info.py` (update backup info)

**Dependencies**: Task 9 (Extract Commands)

**Success Criteria**:
- Backups created automatically
- Metadata stored correctly
- Compression works
- Backup verification works
- Can list backups
- Can restore from backup
- Backup info command accurate

**Commit Message**: "feat(storage): add automatic backup system"

**Estimated Time**: 60 minutes

---

### Task 11: Implement Change Detection

**Goal**: Detect and report changes between database versions.

**Actions**:
- Create `src/erenshor/application/services/change_detector.py`:
  - `ChangeDetector` class
  - Compare entity counts (before/after)
  - Detect new entities
  - Detect removed entities
  - Detect modified entities (field-level)
  - Generate change report
  - Format changes with Rich tables
- Add to extract pipeline output
- Show summary after extraction
- Highlight significant changes
- Log detailed changes

**Files Created/Modified**:
- `src/erenshor/application/services/change_detector.py`

**Dependencies**: Task 10 (Backup System)

**Success Criteria**:
- Detects all entity changes
- Field-level change detection works
- Change reports clear and useful
- Performance acceptable (< 5 seconds)
- Highlights important changes
- Integrates with extract pipeline

**Commit Message**: "feat(services): add database change detection"

**Estimated Time**: 50 minutes

---

### Task 12: Add Extraction Tests

**Goal**: Test extraction pipeline with mocks and integration tests.

**Actions**:
- Create `tests/unit/infrastructure/extraction/__init__.py`
- Create `tests/unit/infrastructure/extraction/test_steamcmd.py`:
  - Mock SteamCMD execution
  - Test download logic
  - Test error handling
- Create `tests/unit/infrastructure/extraction/test_assetripper.py`:
  - Mock AssetRipper execution
  - Test extraction logic
  - Test validation
- Create `tests/unit/infrastructure/extraction/test_unity.py`:
  - Mock Unity batch mode
  - Test log parsing
  - Test completion detection
- Create `tests/integration/extraction/test_pipeline.py`:
  - Test with existing game files (skip download)
  - Test database validation
  - Test change detection
- Use pytest mocks for external processes

**Files Created/Modified**:
- `tests/unit/infrastructure/extraction/__init__.py`
- `tests/unit/infrastructure/extraction/test_steamcmd.py`
- `tests/unit/infrastructure/extraction/test_assetripper.py`
- `tests/unit/infrastructure/extraction/test_unity.py`
- `tests/integration/extraction/__init__.py`
- `tests/integration/extraction/test_pipeline.py`

**Dependencies**: Task 11 (Change Detection)

**Success Criteria**:
- All tests pass
- >80% coverage for extraction module
- Mocks realistic behavior
- Integration tests validate pipeline
- Error conditions tested

**Commit Message**: "test(extraction): add extraction pipeline tests"

**Estimated Time**: 60 minutes

---

### Task 13: Implement MediaWiki Client

**Goal**: Low-level MediaWiki API client with proper API usage.

**Actions**:
- Create `src/erenshor/infrastructure/wiki/client.py`:
  - `MediaWikiClient` class
  - API authentication
  - Page fetching (by title, by recent changes)
  - Page uploading (with edit summary)
  - Query continuation (for large result sets)
  - Rate limiting (respect API limits)
  - Error handling (API errors, network errors)
  - Retry logic with exponential backoff
- Use httpx for async requests
- Respect robots.txt and API guidelines
- Log all API interactions
- Support dry-run mode (no uploads)

**Files Created/Modified**:
- `src/erenshor/infrastructure/wiki/client.py`

**Dependencies**: Task 12 (Extraction Tests) - establishes extraction layer complete

**Success Criteria**:
- Can authenticate with MediaWiki
- Can fetch pages correctly
- Can upload pages correctly
- Rate limiting works
- Retry logic robust
- Dry-run mode prevents uploads
- Clear API error messages

**Commit Message**: "feat(wiki): implement MediaWiki API client"

**Estimated Time**: 60 minutes

---

### Task 14: Implement Wiki Fetcher

**Goal**: Fetch and cache wiki pages with incremental updates.

**Actions**:
- Create `src/erenshor/outputs/wiki/fetcher.py`:
  - `WikiFetcher` class
  - Fetch all pages in category
  - Use recentchanges API for incremental updates
  - Cache fetched pages locally
  - Store page metadata (last modified, revision ID)
  - Detect manual pages (not managed by pipeline)
  - Track image changes
- Create `src/erenshor/outputs/wiki/storage.py`:
  - Local page storage (filesystem)
  - Metadata database (SQLite)
  - Query cached pages
- Add `erenshor wiki fetch` command implementation
- Show fetch progress with Rich

**Files Created/Modified**:
- `src/erenshor/outputs/wiki/fetcher.py`
- `src/erenshor/outputs/wiki/storage.py`
- `src/erenshor/cli/commands/wiki.py` (update fetch command)

**Dependencies**: Task 13 (MediaWiki Client)

**Success Criteria**:
- Can fetch all wiki pages
- Incremental updates work correctly
- Caching reduces API calls
- Manual pages detected
- Image changes tracked
- Fetch command functional
- Progress reporting clear

**Commit Message**: "feat(wiki): add page fetcher with incremental updates"

**Estimated Time**: 65 minutes

---

### Task 15: Implement Template Parser

**Goal**: Parse wiki templates from existing pages.

**Actions**:
- Create `src/erenshor/outputs/wiki/parser.py`:
  - `TemplateParser` class
  - Parse wikitext with mwparserfromhell
  - Extract template calls ({{Template|param=value}})
  - Extract template parameters
  - Handle nested templates
  - Preserve template order
  - Extract manual content sections
- Support all template types:
  - Item templates ({{Item}}, {{Fancy-weapon}}, etc.)
  - Ability templates ({{Ability}})
  - Character templates ({{Enemy}})
  - Future: Quest, Faction, Zone templates
- Handle template variations (spacing, parameter order)
- Parse infobox-style templates

**Files Created/Modified**:
- `src/erenshor/outputs/wiki/parser.py`

**Dependencies**: Task 14 (Wiki Fetcher)

**Success Criteria**:
- Can parse all template types
- Handles nested templates
- Parameter extraction accurate
- Preserves template structure
- Edge cases handled (malformed templates)
- Fast parsing (<1 second per page)

**Commit Message**: "feat(wiki): add template parser for wikitext"

**Estimated Time**: 55 minutes

---

### Task 16: Create Template Context Models

**Goal**: Define Pydantic models for template rendering context.

**Actions**:
- Create `src/erenshor/application/generators/context.py`:
  - `ItemContext` - Context for item templates
  - `AbilityContext` - Context for ability templates
  - `CharacterContext` - Context for character templates
  - `QuestContext` - Context for quest templates (stub)
  - `FactionContext` - Context for faction templates (stub)
  - `ZoneContext` - Context for zone templates (stub)
- Each context:
  - Maps database fields to template parameters
  - Handles data transformations (e.g., stat formatting)
  - Includes relationships (e.g., item components)
  - Validates required fields
- Use Pydantic for validation
- Add helper methods for formatting
- Include URL generation for wiki links

**Files Created/Modified**:
- `src/erenshor/application/generators/context.py`

**Dependencies**: Task 15 (Template Parser)

**Success Criteria**:
- All context models defined
- Database-to-template mapping complete
- Validation works correctly
- Helper methods useful
- Type hints complete
- URL generation works

**Commit Message**: "feat(generators): add template context models"

**Estimated Time**: 60 minutes

---

### Task 17: Implement Page Generator

**Goal**: Generate wiki pages from database using Jinja2 templates.

**Actions**:
- Create `src/erenshor/application/generators/page_generator.py`:
  - `PageGenerator` class
  - Load Jinja2 templates
  - Generate page content from context
  - Support all entity types
  - Handle template selection (item subtypes, etc.)
  - Generate infoboxes and data tables
  - Format numbers, percentages, durations
- Create Jinja2 templates:
  - `templates/wiki/item.j2` - General item template
  - `templates/wiki/ability.j2` - Ability template
  - `templates/wiki/character.j2` - Character template
  - (Quest, Faction, Zone as stubs)
- Add template filters and globals
- Include page metadata (categories, etc.)

**Files Created/Modified**:
- `src/erenshor/application/generators/page_generator.py`
- `templates/wiki/item.j2`
- `templates/wiki/ability.j2`
- `templates/wiki/character.j2`
- `templates/wiki/quest.j2` (stub)
- `templates/wiki/faction.j2` (stub)
- `templates/wiki/zone.j2` (stub)

**Dependencies**: Task 16 (Template Context)

**Success Criteria**:
- Can generate pages for all entity types
- Templates produce correct wikitext
- Data formatting correct
- Template selection works (subtypes)
- Generated pages validate
- Performance acceptable

**Commit Message**: "feat(generators): add page generator with Jinja2 templates"

**Estimated Time**: 75 minutes

---

### Task 18: Implement Content Merger

**Goal**: Merge generated content with existing manual content.

**Actions**:
- Create `src/erenshor/outputs/wiki/merger.py`:
  - `ContentMerger` class
  - Identify managed sections (templates, tables)
  - Identify manual sections (prose, notes)
  - Replace managed content
  - Preserve manual content
  - Maintain section order
  - Handle edge cases (missing sections, etc.)
- Create merge strategy:
  - Replace templates completely
  - Replace managed tables (marked with HTML comments)
  - Keep everything else untouched
  - Preserve section headers
- Add conflict detection (manual edits to managed sections)
- Generate merge report

**Files Created/Modified**:
- `src/erenshor/outputs/wiki/merger.py`

**Dependencies**: Task 17 (Page Generator)

**Success Criteria**:
- Managed content replaced correctly
- Manual content preserved
- Section order maintained
- Conflicts detected
- Merge report clear
- No data loss
- Safe for all page types

**Commit Message**: "feat(wiki): add content merger preserving manual edits"

**Estimated Time**: 60 minutes

---

### Task 19: Implement Wiki Publisher

**Goal**: Upload generated pages to MediaWiki with conflict handling.

**Actions**:
- Create `src/erenshor/outputs/wiki/publisher.py`:
  - `WikiPublisher` class
  - Upload pages with edit summaries
  - Rate limiting (respect API limits)
  - Dry-run mode (preview changes)
  - Conflict resolution (detect concurrent edits)
  - Batch uploads with progress
  - Error handling and retry
- Create `src/erenshor/application/services/wiki_service.py`:
  - Orchestrate fetch → generate → merge → publish
  - Track upload progress
  - Generate upload report
  - Handle partial failures
- Update `erenshor wiki update` command
- Update `erenshor wiki push` command
- Add upload confirmation prompt

**Files Created/Modified**:
- `src/erenshor/outputs/wiki/publisher.py`
- `src/erenshor/application/services/wiki_service.py`
- `src/erenshor/cli/commands/wiki.py` (update commands)

**Dependencies**: Task 18 (Content Merger)

**Success Criteria**:
- Can upload pages to MediaWiki
- Rate limiting works
- Dry-run mode accurate
- Concurrent edit detection works
- Batch uploads efficient
- Error recovery robust
- Commands functional

**Commit Message**: "feat(wiki): add page publisher with conflict handling"

**Estimated Time**: 70 minutes

---

### Task 20: Add Wiki Tests

**Goal**: Test wiki operations comprehensively.

**Actions**:
- Create `tests/unit/outputs/wiki/__init__.py`
- Create `tests/unit/outputs/wiki/test_parser.py`:
  - Test template parsing
  - Test parameter extraction
  - Test edge cases
- Create `tests/unit/outputs/wiki/test_generator.py`:
  - Test page generation
  - Test template rendering
  - Test data formatting
- Create `tests/unit/outputs/wiki/test_merger.py`:
  - Test content merging
  - Test manual content preservation
  - Test conflict detection
- Create `tests/integration/wiki/test_wiki_service.py`:
  - Test full workflow (fetch → generate → merge)
  - Use mock MediaWiki API
  - Test with real templates
- Use fixtures for sample wiki pages

**Files Created/Modified**:
- `tests/unit/outputs/wiki/__init__.py`
- `tests/unit/outputs/wiki/test_parser.py`
- `tests/unit/outputs/wiki/test_generator.py`
- `tests/unit/outputs/wiki/test_merger.py`
- `tests/integration/wiki/__init__.py`
- `tests/integration/wiki/test_wiki_service.py`
- `tests/fixtures/wiki/` (sample pages)

**Dependencies**: Task 19 (Wiki Publisher)

**Success Criteria**:
- All tests pass
- >80% coverage for wiki module
- Edge cases covered
- Integration tests realistic
- Sample pages representative

**Commit Message**: "test(wiki): add comprehensive wiki tests"

**Estimated Time**: 70 minutes

---

### Task 21: Implement Sheets Formatter

**Goal**: Format database data for Google Sheets deployment.

**Actions**:
- Create `src/erenshor/application/formatters/sheets/formatter.py`:
  - `SheetsFormatter` class
  - Execute SQL queries from query files
  - Format results as spreadsheet rows
  - Include header row
  - Handle data types (numbers, dates, URLs)
  - Format hyperlinks (wiki links, map links)
  - Handle NULL values
- Load SQL queries from `src/erenshor/application/formatters/sheets/queries/`:
  - Read `.sql` files
  - Execute with parameters
  - Return formatted data
- Add query validation
- Log query execution

**Files Created/Modified**:
- `src/erenshor/application/formatters/sheets/formatter.py`

**Dependencies**: Task 20 (Wiki Tests) - establishes wiki layer complete

**Success Criteria**:
- Can load and execute SQL queries
- Data formatted correctly for sheets
- Hyperlinks formatted correctly
- NULL handling works
- Query validation catches errors
- Performance acceptable

**Commit Message**: "feat(formatters): add Google Sheets data formatter"

**Estimated Time**: 50 minutes

---

### Task 22: Implement Sheets Publisher

**Goal**: Publish formatted data to Google Sheets via API.

**Actions**:
- Create `src/erenshor/infrastructure/publishers/sheets.py`:
  - `GoogleSheetsPublisher` class
  - Authenticate with service account
  - Clear sheet ranges
  - Write data in batches
  - Format cells (headers, hyperlinks, numbers)
  - Handle large datasets (chunking)
  - Rate limiting
  - Error handling and retry
- Validate credentials
- Support dry-run mode
- Add progress reporting
- Log all API operations

**Files Created/Modified**:
- `src/erenshor/infrastructure/publishers/sheets.py`

**Dependencies**: Task 21 (Sheets Formatter)

**Success Criteria**:
- Can authenticate with Google Sheets API
- Can write data to sheets
- Batch operations work
- Cell formatting correct
- Rate limiting works
- Dry-run mode accurate
- Error handling robust

**Commit Message**: "feat(publishers): add Google Sheets publisher"

**Estimated Time**: 60 minutes

---

### Task 23: Implement Sheets Deploy Service

**Goal**: Orchestrate Google Sheets deployment workflow.

**Actions**:
- Create `src/erenshor/application/services/sheets_service.py`:
  - `SheetsDeployService` class
  - List available sheets (query files)
  - Load queries
  - Format data
  - Publish to sheets
  - Track deployment progress
  - Generate deployment report
- Update `erenshor sheets list` command
- Update `erenshor sheets deploy` command:
  - Deploy specific sheets
  - Deploy all sheets
  - Dry-run mode
  - Progress reporting
- Add sheet validation
- Show deployment summary

**Files Created/Modified**:
- `src/erenshor/application/services/sheets_service.py`
- `src/erenshor/cli/commands/sheets.py` (update commands)

**Dependencies**: Task 22 (Sheets Publisher)

**Success Criteria**:
- Can list available sheets
- Can deploy individual sheets
- Can deploy all sheets
- Dry-run mode works
- Progress reporting clear
- Deployment report useful
- Commands functional

**Commit Message**: "feat(services): add Google Sheets deployment service"

**Estimated Time**: 55 minutes

---

### Task 24: Add Sheets Tests

**Goal**: Test Google Sheets deployment with mocks.

**Actions**:
- Create `tests/unit/application/formatters/test_sheets_formatter.py`:
  - Test query loading
  - Test SQL execution
  - Test data formatting
  - Test hyperlink formatting
- Create `tests/unit/infrastructure/publishers/test_sheets_publisher.py`:
  - Mock Google Sheets API
  - Test authentication
  - Test data writing
  - Test batching
  - Test error handling
- Create `tests/integration/sheets/test_sheets_service.py`:
  - Test full deployment workflow
  - Use mock API
  - Test with real queries
- Use fixtures for sample query results

**Files Created/Modified**:
- `tests/unit/application/formatters/test_sheets_formatter.py` (update existing stub)
- `tests/unit/infrastructure/publishers/__init__.py`
- `tests/unit/infrastructure/publishers/test_sheets_publisher.py`
- `tests/integration/sheets/__init__.py`
- `tests/integration/sheets/test_sheets_service.py`

**Dependencies**: Task 23 (Sheets Deploy Service)

**Success Criteria**:
- All tests pass
- >80% coverage for sheets module
- Mocks realistic behavior
- Integration tests comprehensive
- Edge cases covered

**Commit Message**: "test(sheets): add Google Sheets deployment tests"

**Estimated Time**: 60 minutes

---

### Task 25: Add Integration Tests

**Goal**: Test complete workflows with real database.

**Actions**:
- Create `tests/integration/test_full_pipeline.py`:
  - Test extraction → wiki → sheets workflow
  - Use 28KB fixture database
  - Mock external services (Steam, MediaWiki, Google)
  - Verify data flow between components
  - Test error propagation
  - Test recovery from failures
- Create `tests/integration/test_idempotency.py`:
  - Test running pipeline multiple times
  - Verify no data corruption
  - Test change detection accuracy
  - Test backup creation
- Add performance benchmarks:
  - Measure extraction time
  - Measure wiki generation time
  - Measure sheets deployment time
- Use pytest markers for slow tests

**Files Created/Modified**:
- `tests/integration/test_full_pipeline.py`
- `tests/integration/test_idempotency.py`
- `tests/integration/test_performance.py`

**Dependencies**: Task 24 (Sheets Tests)

**Success Criteria**:
- End-to-end workflows pass
- Idempotency verified
- Performance benchmarks baseline
- Error handling tested
- Recovery mechanisms work
- Tests run in <30 seconds

**Commit Message**: "test(integration): add end-to-end pipeline tests"

**Estimated Time**: 65 minutes

---

### Task 26: Add End-to-End Validation

**Goal**: Manual validation checklist and regression tests.

**Actions**:
- Create `tests/regression/test_wiki_pages.py`:
  - Known problematic pages as test cases
  - Test template rendering edge cases
  - Test content merging edge cases
  - Test conflict detection
- Create `docs/testing/validation-checklist.md`:
  - Pre-deployment checklist
  - Manual testing steps
  - Known issues to check
  - Regression test cases
- Create test data sets:
  - Problematic items (edge cases)
  - Complex characters (many abilities)
  - Long quest chains
- Add regression fixtures
- Document expected outputs

**Files Created/Modified**:
- `tests/regression/__init__.py`
- `tests/regression/test_wiki_pages.py`
- `tests/regression/test_edge_cases.py`
- `docs/testing/validation-checklist.md`
- `tests/fixtures/regression/` (test data)

**Dependencies**: Task 25 (Integration Tests)

**Success Criteria**:
- Regression tests capture known issues
- Validation checklist comprehensive
- Test data represents edge cases
- Documentation clear
- Tests prevent regressions
- Manual validation streamlined

**Commit Message**: "test(regression): add regression tests and validation checklist"

**Estimated Time**: 55 minutes

---

### Task 27: Update Documentation

**Goal**: Document Phase 2 implementation and usage.

**Actions**:
- Update `CLAUDE.md`:
  - Document new CLI commands
  - Document extraction pipeline
  - Document wiki workflow
  - Document sheets deployment
  - Update architecture diagrams
  - Add troubleshooting section
- Create `docs/guides/extraction-pipeline.md`:
  - Step-by-step extraction guide
  - Common issues and solutions
  - Performance tips
- Create `docs/guides/wiki-operations.md`:
  - Wiki workflow overview
  - Template management
  - Content preservation
  - Conflict resolution
- Create `docs/guides/sheets-deployment.md`:
  - Sheets setup guide
  - Query development
  - Deployment workflow
- Update `README.md`:
  - Add Phase 2 completion notes
  - Update feature list
  - Update examples

**Files Created/Modified**:
- `CLAUDE.md` (updated)
- `docs/guides/extraction-pipeline.md`
- `docs/guides/wiki-operations.md`
- `docs/guides/sheets-deployment.md`
- `README.md` (updated)

**Dependencies**: Task 26 (End-to-End Validation)

**Success Criteria**:
- All documentation updated
- Guides clear and accurate
- Examples working
- Troubleshooting helpful
- Architecture current
- README reflects Phase 2 completion

**Commit Message**: "docs: update documentation for Phase 2 completion"

**Estimated Time**: 60 minutes

---

### Task 28: Final Integration and Phase 2 Completion

**Goal**: Verify everything works together and document completion.

**Actions**:
- Run full test suite: `uv run pytest`
- Run type checker: `uv run mypy src/`
- Run linter: `uv run ruff check src/`
- Test all CLI commands:
  - `erenshor extract full` (with mock services)
  - `erenshor wiki fetch`
  - `erenshor wiki update`
  - `erenshor wiki push --dry-run`
  - `erenshor sheets list`
  - `erenshor sheets deploy --dry-run`
- Verify test coverage >80%
- Run integration tests with 28KB fixture
- Run performance benchmarks
- Create `docs/refactoring-plan/phase-2-completion.md`:
  - List completed tasks
  - Note any deviations from plan
  - Document known issues
  - Next steps for Phase 3
- Update backlog with discovered issues
- Clean up TODOs in code

**Files Created/Modified**:
- `docs/refactoring-plan/phase-2-completion.md`
- Any final cleanup files

**Dependencies**: Task 27 (Documentation)

**Success Criteria**:
- All tests pass (>280 total)
- Type checking passes
- Linting passes
- Test coverage >80%
- All commands functional
- Performance acceptable
- Documentation complete
- Completion report written
- Ready for Phase 3

**Commit Message**: "docs: complete Phase 2 data extraction pipeline - ready for Phase 3"

**Estimated Time**: 45 minutes

---

## Summary

**Total Tasks**: 28
**Total Estimated Time**: ~28 hours (4-6 weeks part-time)

**Key Milestones**:
1. **Tasks 1-5**: Database layer (6h 15min)
2. **Tasks 6-12**: Extraction pipeline (6h 55min)
3. **Tasks 13-20**: Wiki operations (8h 5min)
4. **Tasks 21-24**: Google Sheets (3h 45min)
5. **Tasks 25-28**: Testing & validation (3h 45min)

**Phase 2 Deliverables**:
- ✅ Database repository layer with type-safe queries
- ✅ Complete extraction pipeline (SteamCMD → AssetRipper → Unity → Database)
- ✅ Automatic backup system with change detection
- ✅ Wiki operations (fetch, generate, merge, publish)
- ✅ Google Sheets deployment
- ✅ Comprehensive test coverage (>80%)
- ✅ Integration tests with 28KB fixture
- ✅ Complete documentation

**Ready for Phase 3**: Registry system improvements and advanced wiki features.

---

## Notes

- **Atomic Commits**: Each task is independently committable
- **Sequential Dependencies**: Tasks build on previous work
- **Test Coverage**: Tests added throughout (not just at end)
- **Realistic Estimates**: Based on Phase 1 actual timing
- **Clear Success Criteria**: Each task has measurable completion markers
- **Incremental Value**: Each milestone provides working functionality

**Implementation Tips**:
1. Commit after each task completion
2. Run tests frequently (`uv run pytest`)
3. Use type checking to catch issues early (`uv run mypy src/`)
4. Keep commits focused and atomic
5. Update this document if deviations occur
6. Document unexpected issues or decisions
7. Test with 28KB fixture regularly
8. Verify commands work as expected

**Quality Gates**:
- Each task must pass type checking
- Each task must pass linting
- Each task must include tests
- Each task must update documentation if needed
- Integration tests must use 28KB fixture
- No task should take >90 minutes

---

**End of Phase 2 Task Breakdown**
