# Current Feature Checklist

**Document Status**: TO DO - Requires Audit
**Date**: 2025-10-16
**Purpose**: Ensure no functionality is lost during big bang rewrite

---

## Overview

This document tracks all current features that must be preserved in the new system. Per Risk 4 mitigation: "We definitely need to do a check for any missing functionality before we get started."

**Goal**: Create comprehensive inventory of current capabilities to ensure nothing is lost.

**Approach**:
1. Audit current system (Bash CLI + Python CLI)
2. List all features, commands, and capabilities
3. Check each feature against new implementation plan
4. Flag any gaps

---

## 1. Extraction Features

### 1.1 SteamCMD Integration
- [ ] Download game files for all variants (main, playtest, demo)
- [ ] Validate Steam credentials
- [ ] Handle Steam Guard / 2FA
- [ ] Check for game updates before downloading
- [ ] Resume interrupted downloads
- [ ] Verify downloaded files (checksums?)

### 1.2 AssetRipper Integration
- [ ] Extract Unity project from game files
- [ ] Handle all supported asset types
- [ ] Preserve asset relationships
- [ ] Generate readable C# scripts from IL
- [ ] Handle custom Unity version (2021.3.45f2)

### 1.3 Unity Export
- [ ] Run Unity in batch mode (headless)
- [ ] Execute export scripts (ExportBatch.cs)
- [ ] Export all entity types:
  - [ ] Items
  - [ ] Characters
  - [ ] Spells
  - [ ] Skills
  - [ ] Quests (if implemented)
  - [ ] Zones
  - [ ] Factions
  - [ ] Loot tables
  - [ ] Spawn points
  - [ ] Vendor inventories
  - [ ] Dialogs
  - [ ] ... (check ExportBatch.cs for full list)
- [ ] Create SQLite database with correct schema
- [ ] Handle junction tables (many-to-many relationships)
- [ ] Validate exported data
- [ ] Handle export errors gracefully

### 1.4 Backup Management
- [ ] Create backups on game version change
- [ ] Store backups per variant
- [ ] Backup includes:
  - [ ] SQLite database
  - [ ] Unity Editor scripts (ZIP archive)
  - [ ] Config file snapshot
- [ ] Show backup information (count, size, dates)
- [ ] No automatic deletion (manual cleanup only)

### 1.5 Variant Support
- [ ] Support multiple variants (main, playtest, demo)
- [ ] Separate working directories per variant
- [ ] Separate databases per variant
- [ ] Separate logs per variant
- [ ] Variant-specific configuration
- [ ] Switch between variants via CLI flag

---

## 2. Registry Features

### 2.1 Entity Tracking
- [ ] Track all entities across game versions
- [ ] Assign stable UIDs to entities
- [ ] Detect new entities
- [ ] Detect deleted entities
- [ ] Detect renamed entities
- [ ] Track entity metadata

### 2.2 Manual Mappings
- [ ] Override page titles manually
- [ ] Override display names manually
- [ ] Override image names manually
- [ ] Store mappings persistently (currently: mapping.json)
- [ ] Support per-entity mappings
- [ ] Support wildcard/pattern mappings (if exists)

### 2.3 Page Title Resolution
- [ ] Resolve entity → page title
- [ ] Handle disambiguation (suffix with entity type)
- [ ] Respect manual overrides
- [ ] Handle multi-entity pages
- [ ] Generate URLs from titles

### 2.4 Link Generation
- [ ] Generate wiki links [[Page Title]]
- [ ] Generate external links
- [ ] Generate faction links
- [ ] Generate zone links
- [ ] Generate item links
- [ ] Generate character links
- [ ] Generate spell links
- [ ] Generate skill links

---

## 3. Wiki Features

### 3.1 Page Fetching
- [ ] Fetch pages from MediaWiki API
- [ ] Support incremental fetching (recentchanges API)
- [ ] Parse fetched wikitext
- [ ] Store fetched pages for comparison
- [ ] Handle API rate limiting
- [ ] Handle authentication (bot account)
- [ ] Track last fetch timestamp per page

### 3.2 Content Generation
- [ ] Generate pages for all entity types:
  - [ ] Items (all subtypes: weapons, armor, consumables, etc.)
  - [ ] Characters (NPCs, enemies, bosses, rare enemies)
  - [ ] Spells
  - [ ] Skills
  - [ ] Fishing spots (if implemented)
  - [ ] Zones (if implemented)
  - [ ] Factions (if implemented)
  - [ ] Quests (if implemented)
- [ ] Render infoboxes (templates)
- [ ] Render loot tables
- [ ] Render spawn location tables
- [ ] Render vendor inventories
- [ ] Format stats correctly
- [ ] Format durations correctly (seconds to human-readable)
- [ ] Handle special cases (unique stats, special abilities, etc.)

### 3.3 Content Merging
- [ ] Preserve manual wiki edits
- [ ] Update only managed templates/sections
- [ ] Detect changes between old and new content
- [ ] Handle conflicts gracefully
- [ ] Never overwrite manual sections

### 3.4 Uploading
- [ ] Upload pages to MediaWiki
- [ ] Handle upload failures gracefully
- [ ] Retry failed uploads
- [ ] Rate limiting (respect wiki API limits)
- [ ] Batch uploads
- [ ] Skip unchanged pages (optimization)
- [ ] Show upload progress
- [ ] Log upload results

### 3.5 Image Handling
- [ ] Extract images from Unity assets
- [ ] Find images that need upload
- [ ] Detect changed images (via recentchanges)
- [ ] Bulk upload images
- [ ] Correct naming (match entity names)
- [ ] Organize images (categories, etc.)

### 3.6 Special Cases
- [ ] Handle multi-entity pages (multiple entities → one page)
- [ ] Handle disambiguation pages
- [ ] Handle redirect pages
- [ ] Handle category pages
- [ ] Handle special wiki syntax (tables, lists, etc.)
- [ ] Handle nested templates
- [ ] Escape special characters
- [ ] Handle wikitext edge cases (see existing implementation for known issues)

---

## 4. Google Sheets Features

### 4.1 Sheet Generation
- [ ] Generate all current sheets:
  - [ ] Items sheet
  - [ ] Characters sheet
  - [ ] Spells sheet
  - [ ] Skills sheet
  - [ ] Drop chances sheet
  - [ ] Spawn points sheet
  - [ ] ... (check sheets/queries/*.sql for full list)
- [ ] Execute SQL queries from .sql files
- [ ] Format data as spreadsheet rows (header + data)
- [ ] Handle large datasets (batching)

### 4.2 Deployment
- [ ] Authenticate with Google Sheets API (service account)
- [ ] Create/update sheets
- [ ] Clear existing data before update
- [ ] Batch writes (for performance)
- [ ] Handle API rate limiting
- [ ] Handle API errors gracefully
- [ ] Show deployment progress
- [ ] Validate credentials
- [ ] List available sheets

### 4.3 Configuration
- [ ] Per-variant spreadsheet IDs
- [ ] Credentials file path configuration
- [ ] Batch size configuration
- [ ] Deployment options (--all-sheets, --sheets <name>, --dry-run)

---

## 5. Maps Features

### 5.1 Data Preparation
- [ ] Export full SQLite database for maps
- [ ] Optimize database for browser loading (if any optimizations exist)
- [ ] Include all necessary data (spawn points, coordinates, zone info, etc.)

### 5.2 Frontend (erenshor-maps)
- [ ] SvelteKit application
- [ ] Leaflet map rendering
- [ ] Load SQLite via sql.js (WASM)
- [ ] Display spawn points on map
- [ ] Interactive markers (click for details)
- [ ] Search functionality (if implemented)
- [ ] Zone filtering
- [ ] Entity type filtering
- [ ] Responsive design (mobile support)

### 5.3 Deployment
- [ ] Build static site
- [ ] Deploy to Cloudflare Pages (or current hosting)
- [ ] Configure custom domain (if used)
- [ ] Handle build errors

---

## 6. Configuration Features

### 6.1 Config Management
- [ ] Load configuration from TOML files
- [ ] Support two-layer config (config.toml + config.local.toml)
- [ ] Support environment variable overrides (CURRENT SYSTEM - to be removed)
- [ ] Validate configuration
- [ ] Show current configuration (`erenshor config get`)
- [ ] Per-variant configuration sections

### 6.2 Path Resolution
- [ ] Resolve paths from config
- [ ] Support environment variable expansion (e.g., $HOME, $REPO_ROOT)
- [ ] Absolute path resolution
- [ ] Variant-specific paths
- [ ] Working directory handling

### 6.3 Secrets Management
- [ ] Bot credentials (username, password)
- [ ] Google Sheets credentials (service account JSON)
- [ ] Steam credentials (username, password)
- [ ] Store secrets in config.local.toml (gitignored)

---

## 7. CLI Features

### 7.1 Bash CLI Commands (Current - to be replaced)
- [ ] `erenshor update` - Full pipeline
- [ ] `erenshor download` - Download game files
- [ ] `erenshor extract` - Extract Unity project
- [ ] `erenshor export` - Export to SQLite
- [ ] `erenshor deploy` - Deploy to wiki/sheets
- [ ] `erenshor status` - Show system status
- [ ] `erenshor config get` - View configuration
- [ ] `erenshor symlink check|create|status` - Manage symlinks
- [ ] `erenshor doctor` - System health check
- [ ] `erenshor test-python` - Test Python integration

### 7.2 Python CLI Commands (Current)
- [ ] `db stats` - Database statistics
- [ ] `db validate` - Validate schema
- [ ] `wiki fetch` - Fetch wiki templates
- [ ] `wiki update` - Update wiki pages
- [ ] `sheets list` - List available sheets
- [ ] `sheets validate` - Validate credentials
- [ ] `sheets deploy` - Deploy all sheets
- [ ] `check-paths` - Show path configuration

### 7.3 Global Options
- [ ] `--variant <name>` - Specify variant
- [ ] `--verbose` - Verbose output
- [ ] `--quiet` - Minimal output
- [ ] `--dry-run` - Preview without changes (if implemented)
- [ ] `--help` - Show help
- [ ] `--version` - Show version

### 7.4 Output & Progress
- [ ] Rich progress bars (current: Rich library)
- [ ] Colored terminal output
- [ ] Clear error messages
- [ ] Success/failure indicators
- [ ] Detailed logging to files
- [ ] Console output separate from log files

---

## 8. Logging Features

### 8.1 Log Files
- [ ] Per-variant log directories
- [ ] Timestamped log files
- [ ] Log rotation (if implemented)
- [ ] Different log levels (DEBUG, INFO, WARNING, ERROR)
- [ ] Configurable log level
- [ ] Console logging
- [ ] File logging

### 8.2 Log Content
- [ ] Timestamp per log line
- [ ] Log level indicator
- [ ] Source module/function
- [ ] Detailed error traces (stack traces)
- [ ] Progress tracking in logs
- [ ] Structured logging (if implemented)

---

## 9. Testing Features (Current)

### 9.1 Test Coverage
- [ ] Unit tests for Python code
- [ ] Integration tests (if exist)
- [ ] Test fixtures
- [ ] Test database (if used)
- [ ] Mock external APIs (MediaWiki, Google Sheets)

### 9.2 Test Commands
- [ ] Run all tests (`pytest`)
- [ ] Run specific tests
- [ ] Coverage reporting
- [ ] CI/CD integration (if exists)

---

## 10. Developer Experience

### 10.1 Documentation
- [ ] CLAUDE.md (comprehensive project guide)
- [ ] README.md (project overview)
- [ ] Inline code documentation (docstrings)
- [ ] Architecture diagrams (if exist)
- [ ] Setup instructions

### 10.2 Development Tools
- [ ] uv for Python dependency management (current)
- [ ] Fallback to pip/system Python
- [ ] Environment detection (uv vs system Python)
- [ ] Code formatting (if configured)
- [ ] Linting (if configured)

---

## 11. Special Features / Edge Cases

### 11.1 Known Special Cases (from current implementation)
- [ ] Multi-entity pages (multiple entities → one page)
- [ ] Disambiguation (items vs spells with same name)
- [ ] Special character handling (escaping wikitext)
- [ ] Duration conversion (game ticks → human-readable)
- [ ] Stat calculations (effective stats, ranges, etc.)
- [ ] Drop chance calculations (per loot table, guaranteed vs regular)
- [ ] Faction handling (Generic Good/Evil, world factions, etc.)
- [ ] SimPlayers filtering (exclude from character exports)
- [ ] Obtainability checks (filter unobtainable items/spells)
- [ ] Class restrictions (item/spell classes)
- [ ] Spell/skill procs and effects
- [ ] Pet summoning
- [ ] Status effects
- [ ] Reap and Renew mechanics
- [ ] Unstable durations
- [ ] Fishing mechanics (if implemented)

### 11.2 Platform-Specific
- [ ] macOS support (current development platform)
- [ ] Linux support (Unity headless on Linux)
- [ ] Windows support (if tested)
- [ ] Cross-platform path handling

---

## 12. Performance Optimizations (Current)

### 12.1 Existing Optimizations
- [ ] Incremental wiki fetching (recentchanges API)
- [ ] Skip unchanged pages (don't re-upload)
- [ ] Batch operations (sheets deployment, wiki uploads)
- [ ] Database indexing
- [ ] Lazy loading (if implemented)
- [ ] Caching (if implemented)

---

## 13. Audit Checklist

**To complete this checklist**:

1. **Review current Bash CLI**
   - Read all `cli/commands/*.sh` files
   - Document every command and option
   - Check for hidden features

2. **Review current Python CLI**
   - Read all `src/erenshor/cli/commands/*.py` files
   - Document all commands and options
   - Check for undocumented features

3. **Review current implementation**
   - Read all generator files (`src/erenshor/application/generators/*.py`)
   - Read all transformer files
   - Read all service files
   - Document special logic and edge cases

4. **Review Unity export scripts**
   - Read `src/Assets/Editor/ExportBatch.cs`
   - List all exported entity types
   - Document export logic

5. **Review configuration**
   - Read `config.toml`
   - Document all config options
   - Check for variant-specific settings

6. **Review tests**
   - Check what is currently tested
   - Document test fixtures
   - Identify test gaps

7. **Cross-check with new plan**
   - For each current feature, verify it's in Phase 1-8 plan
   - Flag any features missing from new plan
   - Add missing features to appropriate phase

---

## 14. Known Issues (Current System)

### 14.1 Known Bugs/Limitations
- [ ] Manual wiki fixes overwritten by auto-updates (MAJOR - to be fixed in new system)
- [ ] Registry system brittle (entity ID stability issues)
- [ ] Bash/Python split complexity (to be eliminated)
- [ ] Config system too many layers (to be simplified)
- [ ] Wiki content preservation inadequate (to be improved)
- [ ] Conflict detection incomplete (to be enhanced)
- [ ] No change detection (to be added)
- [ ] No resume from failure (to be added)
- [ ] ... (check GitHub issues, TODO comments, etc.)

### 14.2 Known Workarounds
- [ ] Document any workarounds in current system
- [ ] These workarounds may need to be preserved or have proper fixes in new system

---

## 15. Validation Criteria

After implementation, validate each feature:

**For each checked item above**:
- [ ] Feature works identically in new system
- [ ] OR feature intentionally improved (document improvement)
- [ ] OR feature intentionally removed (document why and get user approval)

**No feature should be accidentally lost.**

---

## Status

**Current Status**: NOT STARTED

**Next Steps**:
1. Assign someone to complete audit (AI or user)
2. Review all current code systematically
3. Check every box above
4. Flag any gaps in new plan
5. Update phases 1-8 if missing features found

**Deadline**: Before Phase 1 implementation begins

---

**End of Feature Checklist**
