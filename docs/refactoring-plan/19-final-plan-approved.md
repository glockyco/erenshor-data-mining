# Final Approved Implementation Plan

**Document Status**: APPROVED - Ready to Start Phase 1
**Date**: 2025-10-16
**Purpose**: Definitive implementation plan with all user decisions finalized

---

## Executive Summary

Complete rewrite of Erenshor data mining project approved and ready to begin. All research completed, all decisions finalized, zero remaining blockers.

### User Approval Status

✅ All major architectural decisions approved
✅ All research tasks completed
✅ All open questions answered
✅ Ready to start Phase 1 immediately

### Major Decisions (FINAL)

1. **Cargo Integration**: HIGH-PRIORITY BACKLOG (first item after rewrite stabilizes)
2. **Stable IDs**: Keep resource names (ID columns NOT reliable - duplicate IDs observed)
3. **Templates**: Simplified (no inheritance), fix auras as item subtype, skip low-priority types
4. **Test Database**: Keep hybrid approach (unit + integration + optional production)
5. **Database Deployment**: Hybrid (symlink dev, copy build)
6. **Monorepo**: Merge erenshor-maps into main repository
7. **Python-only CLI**: Eliminate Bash layer entirely
8. **Two-layer TOML config**: No environment variables

### Key Insights from User Feedback

**Cargo Decision**: User overruled research recommendation
- Research said: Add NOW to avoid double wiki updates
- User said: "Wiki update overhead is irrelevant, that's what we have auto updates for"
- **Deferring avoids huge manual validation requirements**
- Future effort is same as current effort (validation is the real cost, not wiki updates)
- **Outcome**: Cargo → HIGH-PRIORITY BACKLOG

**Stable IDs Decision**: User corrected research recommendation
- Research said: Use Unity ID columns (Id, Guid fields)
- User said: "Can't really use ID columns... NOT always guaranteed to be unique"
- **We've already had cases of duplicate IDs**
- **Outcome**: Keep resource names (current implementation), add quest DBName + faction REFNAME

**Template Simplifications**:
- Fishing is currently broken (note for fixing)
- Auras should be item subtype (currently separate - fix this)
- Skip templates for: classes, mining nodes, achievements, teleports, doors, books
- Molds ARE crafting recipes (don't need separate crafting recipe template)
- **Avoid template inheritance** - keep simple, readability over maintainability

---

## 1. Architecture Overview

### 1.1 Core Principles

- **Clean Break**: Archive old system to `legacy/`, build new from scratch
- **Python-Only**: No Bash layer, pure Python CLI with Typer
- **Monorepo**: Merge erenshor-maps into main repository
- **Two-Layer Config**: TOML files only, no environment variables
- **Resource Names**: Primary stable keys (Unity IDs unreliable)
- **Simplicity**: No unnecessary abstractions or premature optimization

### 1.2 Directory Structure

```
erenshor/
├── legacy/                     # Old system (archived after Phase 1)
├── src/
│   ├── erenshor/               # Python package
│   │   ├── application/        # Application services
│   │   │   ├── formatters/     # Data formatters
│   │   │   │   └── sheets/     # Google Sheets formatters
│   │   │   │       └── queries/  # SQL query files
│   │   │   ├── generators/     # Wiki page generators
│   │   │   └── services/       # Business services
│   │   ├── cli/                # Python CLI implementation
│   │   │   └── commands/       # CLI command implementations
│   │   ├── domain/             # Domain models
│   │   │   └── entities/       # Entity models (Resource names)
│   │   ├── infrastructure/     # Infrastructure layer
│   │   │   ├── database/       # SQLite repositories
│   │   │   ├── publishers/     # Google Sheets, MediaWiki
│   │   │   └── storage/        # File storage
│   │   ├── outputs/            # Output modules
│   │   │   ├── wiki/           # MediaWiki operations
│   │   │   ├── sheets/         # Google Sheets deployment
│   │   │   └── maps/           # Maps data (MAY NOT BE NEEDED)
│   │   └── registry/           # Entity registries (Resource name based)
│   ├── maps/                   # TypeScript/Svelte frontend
│   │   └── static/
│   │       └── data/           # Database deployed here
│   └── Assets/
│       ├── Editor/             # Unity export scripts (symlinked to Unity)
│       │   ├── ExportBatch.cs  # Batch mode export entry
│       │   ├── Database/       # SQLite table records
│       │   └── ExportSystem/   # Asset scanning system
│       └── Packages/           # NuGet packages (copied to Unity)
├── variants/                   # Working directories (NOT in git)
│   ├── main/                   # Main game (App ID 2382520)
│   │   ├── game/               # Downloaded from Steam
│   │   ├── unity/              # Unity project from AssetRipper
│   │   └── erenshor-main.sqlite
│   ├── playtest/               # Playtest (App ID 3090030)
│   └── demo/                   # Demo (App ID 2522260)
├── tests/
│   ├── unit/                   # Fast, isolated tests
│   ├── integration/            # Real components (28KB SQL fixture)
│   └── maps/                   # TypeScript/Jest tests
├── config.toml                 # Main config
├── config.local.toml           # User overrides (gitignored)
└── pyproject.toml              # Python dependencies
```

---

## 2. Stable Entity ID Strategy (CORRECTED)

### 2.1 User Correction: Unity IDs Are Unreliable

**Research Recommendation**: Use Unity ID columns (Id, Guid fields)

**User Feedback**: "Can't really use ID columns. Even though they come from ScriptableObject ID fields, they are NOT always guaranteed to be unique. We've already had cases of duplicate IDs."

**Approved Strategy**: Keep resource names (current implementation)

### 2.2 Primary Stable Keys (Resource Name Based)

| Entity Type | Primary Stable Key | Notes |
|-------------|-------------------|-------|
| **Items** | `item:{ResourceName}` | Keep current approach |
| **Spells** | `spell:{ResourceName}` | Keep current approach |
| **Skills** | `skill:{ResourceName}` | Keep current approach |
| **Characters** | `character:{ObjectName}` | Keep current approach |
| **Quests** | `quest:{DBName}` | NEW - Add DBName support |
| **Factions** | `faction:{REFNAME}` | NEW - Add REFNAME support |

### 2.3 Implementation

**EntityRef stable_key (UNCHANGED)**:
```python
@property
def stable_key(self) -> str:
    """Key for tracking entities across versions (uses resource names)."""
    if self.resource_name:
        return f"{self.entity_type.value}:{self.resource_name}"
    # Fallback to display name
    return f"{self.entity_type.value}:{self.db_name}"
```

**Update EntityRef.from_* methods**:
- Items/Spells/Skills: Use ResourceName (keep current)
- Characters: Use ObjectName (keep current)
- Quests: Use DBName field as resource_name (NEW)
- Factions: Use REFNAME as resource_name (NEW)

**No migration required**: Current system already uses resource names.

---

## 3. Template Architecture (SIMPLIFIED)

### 3.1 Current Templates (Keep)

**Items** (8 subtypes):
- General items: `items/item.j2` → `{{Item}}`
- Weapons: `items/fancy_weapon_*.j2` → `{{Fancy-weapon}}`
- Armor: `items/fancy_armor_*.j2` → `{{Fancy-armor}}`
- Charms: `items/fancy_charm.j2` → `{{Fancy-charm}}`
- **Auras**: FIX - Should use item template with subtype (currently broken)
- Ability Books: `items/ability_book.j2` → `{{Ability Books}}`
- Molds: `items/mold.j2` → `{{Mold}}` (these ARE crafting recipes)
- Consumables: Uses `{{Item}}` template

**Abilities** (shared template):
- Spells & Skills: `abilities/ability.j2` → `{{Ability}}`

**Characters** (unified template):
- NPCs & Enemies: `characters/enemy.j2` → `{{Enemy}}`

**Fishing**:
- Fishing canonical: `fishing/canonical.j2` → Full page content (CURRENTLY BROKEN)

### 3.2 New Templates (High Priority)

- **Quests**: Complex relationships (items, NPCs, prerequisites, rewards)
- **Factions**: Simple structure
- **Zones**: Aggregate many entities

### 3.3 Templates NOT Needed (Skip)

User explicitly said these are NOT needed:
- Classes (too simple)
- Mining nodes (too simple)
- Achievements (too simple)
- Teleports (too simple)
- Doors (too simple)
- Books (too simple)

### 3.4 Design Principles

**User guidance**: "Please avoid template inheritance shenanigans. Just keep things simple. Those are not files we are touching / modifying on a regular basis, so readability trumps maintainability."

- No template inheritance
- No complex abstractions
- Readability over maintainability
- Keep templates straightforward
- Copy-paste over DRY if it improves clarity

### 3.5 Fixes Required

1. **Auras**: Make auras an item subtype (currently separate)
2. **Fishing**: Fix broken fishing template
3. **Molds**: Keep as-is (they ARE crafting recipes, no separate template needed)

---

## 4. Cargo Integration (HIGH-PRIORITY BACKLOG)

### 4.1 Decision Rationale

**User overruled research recommendation**:
- Research: Add NOW to avoid double wiki updates
- User: "Wiki update overhead is irrelevant, that's what we have auto updates for"

**Key insight**: **Validation cost >> wiki update automation cost**

**User rationale**: "Deferring Cargo for now avoids huge manual validation requirements beyond what we already need to do as part of the refactoring/rewrite. The future effort is the same as the current one."

### 4.2 Backlog Priority

**Status**: HIGH-PRIORITY BACKLOG
**When**: First major feature after rewrite stabilizes
**Estimated Effort**: 6 weeks (same as implementing NOW, but with stable foundation)

### 4.3 Design During Rewrite

Even though Cargo is deferred, we will:
- Design templates with Cargo in mind (use proper sections)
- Keep field names Cargo-compatible (lowercase_with_underscores)
- Document template schemas for future Cargo mapping
- Keep relationship data separate (not inline)
- Use simple Pydantic types (avoid nested structures)

**This minimizes rework when Cargo is implemented later**.

### 4.4 Why Deferring Is OK

1. **Validation is the real cost**: Manual verification of Cargo data tables takes time
2. **Auto updates make wiki regen cheap**: We already have automation for updating pages
3. **Stable foundation first**: Better to add Cargo to stable system than debug both at once
4. **Same future effort**: Adding Cargo later requires same 6-week effort, just with less pressure

---

## 5. Test Database Strategy (APPROVED)

### 5.1 Hybrid Approach (Keep Current)

User approved keeping current hybrid approach:

**Unit tests (70%)**: In-memory SQLite with programmatic fixtures
- Fast, isolated
- No git dependencies
- Generate data programmatically

**Integration tests (20%)**: Minimal 28KB SQL fixture (committed to git)
- Real database with real data
- Small enough to commit
- Covers common entity types

**Production tests (10%)**: Optional full database copy (5.5MB, generated on demand)
- Comprehensive validation
- Test complex queries
- Skip if database unavailable
- Never commit to git

### 5.2 Git Strategy

- Commit: 28KB SQL fixture
- Delete: Binary .sqlite test files (generate from SQL)
- Never commit: 5.5MB production database (copy on demand)
- No Git-LFS: Not worth cost for solo dev hobby project

---

## 6. Maps Architecture (APPROVED)

### 6.1 Database Deployment Strategy

**User approved hybrid approach**:

**Development** (`erenshor maps dev`):
- Symlink `variants/main/erenshor-main.sqlite` → `src/maps/static/data/erenshor.sqlite`
- Live updates during development
- Delete symlink on exit

**Production** (`erenshor maps build`):
- Copy `variants/main/erenshor-main.sqlite` → `src/maps/static/data/erenshor.sqlite`
- Build artifact includes database
- Cloudflare serves as static asset

**Add to .gitignore**: `src/maps/static/data/*.sqlite`

### 6.2 Maps Output Module

**User feedback**: "Not sure we will need src/erenshor/outputs/maps. After all, maps will directly access DB data."

**Decision**: DEFER to Phase 6 implementation - only create if actually needed. Maps CLI commands might just be npm script wrappers.

### 6.3 Performance Optimization

**User feedback**: "That's good enough for a first throw"

**Decision**: BACKLOG - Current ~5 second load time is acceptable. Defer optimizations (gzip, IndexedDB) to post-rewrite.

---

## 7. CLI Commands (Complete)

```bash
# Extraction
erenshor extract                    # Full pipeline
erenshor extract download           # Download only
erenshor extract rip                # AssetRipper only
erenshor extract export             # Unity export only

# Wiki operations
erenshor wiki fetch                 # Fetch pages from MediaWiki
erenshor wiki update                # Generate updated content
erenshor wiki push                  # Upload to MediaWiki
erenshor wiki conflicts             # Show name conflicts
erenshor wiki resolve-conflict <id> # Resolve specific conflict

# Sheets
erenshor sheets list                # List available sheets
erenshor sheets deploy              # Deploy to Google Sheets

# Maps
erenshor maps dev                   # Local dev server (npm run dev)
erenshor maps preview               # Preview build (npm run preview)
erenshor maps build                 # Production build
erenshor maps deploy                # Deploy to Cloudflare

# Status/Info
erenshor status                     # Pipeline status
erenshor config show                # Show configuration
erenshor doctor                     # System health check
erenshor backup info                # Backup information

# Documentation
erenshor docs generate              # Generate CLI docs (Markdown)

# Testing
erenshor test                       # Run Python test suite
erenshor test unit                  # Unit tests only
erenshor test integration           # Integration tests only

# Global options
--variant <name>                    # Specify variant (default: main)
--dry-run                           # Preview without changes
--resume                            # Resume from failure (explicit flag)
```

---

## 8. Implementation Phases (FINAL)

### Phase 0: Preparation (COMPLETE)

✅ All research tasks completed
✅ All decisions finalized
✅ User approval received
✅ Ready to start Phase 1

### Phase 1: Foundation (2-3 weeks)

**Goal**: Set up new project structure and core systems.

**Tasks**:
1. Archive old system to `legacy/`
2. Create new Python package structure
3. Merge erenshor-maps into monorepo
4. Implement two-layer TOML config system
5. Implement Loguru logging (verbose INFO level by default)
6. Implement path resolution (strongly-typed config classes)
7. Set up pytest infrastructure (keep current hybrid fixtures)
8. Create CLI skeleton with Typer
9. Implement basic commands (status, config show, doctor, test)

**Success Criteria**:
- CLI runs and shows help
- Config loads from config.toml + config.local.toml
- Logging works with INFO level
- Tests run (pytest unit + integration)
- No Bash dependencies
- Maps merged into monorepo

**Deliverables**:
- Working CLI skeleton
- Two-layer TOML config
- Loguru logging
- pytest infrastructure
- Foundation for resource-name-based registry

### Phase 2: Data Extraction (2 weeks)

**Goal**: Re-implement extraction pipeline in Python.

**Tasks**:
1. Python wrappers for SteamCMD
2. Python wrappers for AssetRipper
3. Python wrappers for Unity batch mode
4. Database validation (schema checks, row counts)
5. Backup system (create on version change)
6. Basic change detection (entity count differences)

**Success Criteria**:
- `erenshor extract` command fully functional
- Produces identical database to old system
- Creates backups automatically
- Reports entity count changes

### Phase 3: Registry System (2-3 weeks)

**Goal**: Implement robust entity tracking and conflict detection.

**Tasks**:
1. Implement stable UID system (resource names, NOT Unity IDs)
2. Add quest DBName and faction REFNAME support
3. Create registry SQLite database schema
4. Implement entity registration
5. Migrate manual mappings from mapping.json to registry database
6. Implement ALL wiki pages tracking (managed + manual)
7. Implement conflict detection
8. Implement conflict resolution UI (`erenshor wiki conflicts`, `resolve-conflict`)
9. Integrate with extraction pipeline

**Stable ID implementation**:
- Use resource names (current approach)
- Add quest DBName support
- Add faction REFNAME support
- NO Unity ID columns (duplicate IDs observed)

**Success Criteria**:
- Registry tracks all entities with stable UIDs (resource name based)
- Quest DBName and faction REFNAME work correctly
- Manual mappings migrated to database
- Conflict detection catches all conflicts
- Interactive conflict resolution works

### Phase 4: Wiki System (4-5 weeks)

**Goal**: Re-implement wiki operations with proper content preservation.

**Tasks**:
1. MediaWiki API client (proper usage of recentchanges API)
2. Wiki page fetching (incremental, respects recentchanges)
3. Template-based content parsing (all 20 templates)
4. Page generation from database (all entity types, all subtypes)
5. Content merging (preserve manual sections, update managed templates/tables)
6. Upload with rate limiting
7. Conflict detection integration
8. Image change detection (use recentchanges)
9. **Fix auras** (make item subtype, not separate)
10. **Fix fishing** (currently broken)

**Template handling**:
- Support all 8 item subtypes (weapons, armor, charms, auras, books, molds, consumables, general)
- Support shared ability template (spells + skills)
- Support character template (NPCs + enemies)
- Add quest, faction, zone templates (high priority)
- Skip: classes, mining, achievements, teleports, doors, books (per user)
- NO template inheritance (keep simple)

**Success Criteria**:
- `erenshor wiki fetch` works correctly
- `erenshor wiki update` generates pages preserving manual content
- All required templates supported
- Auras fixed (item subtype)
- Fishing fixed
- `erenshor wiki push` uploads without overwriting manual changes
- Image change detection works

### Phase 5: Output Modules (3 weeks)

**Goal**: Implement sheets and maps outputs.

**Tasks**:
1. Refactor Google Sheets deployment (keep current approach, clean up if needed)
2. Maps database deployment (hybrid: symlink dev, copy build)
3. Maps CLI commands (dev, preview, build, deploy)
4. URL coordination (wiki URLs in sheets, maps URLs in wiki, etc.)
5. Add .gitignore entry for `src/maps/static/data/*.sqlite`
6. Only create maps output module if actually needed (DEFER decision)

**Maps implementation**:
- `erenshor maps dev` - Start dev server, symlink DB for live updates
- `erenshor maps preview` - Preview built site
- `erenshor maps build` - Production build, copy DB to static/data/
- `erenshor maps deploy` - Deploy to Cloudflare

**Success Criteria**:
- `erenshor sheets deploy` works identically to old system
- Maps have full database access via static assets
- Maps dev/preview/build/deploy all work
- Database accessible at runtime without moving from variants/
- Symlink created/destroyed correctly

### Phase 6: Testing & Validation (2-3 weeks)

**Goal**: Ensure new system works correctly.

**Tasks**:
1. Unit tests (60% target coverage) - in-memory DB
2. Integration tests (30% target coverage) - 28KB SQL fixture
3. Optional production tests (10%) - 5.5MB database copy
4. **Maps tests (TypeScript/Jest)** - don't forget!
5. Comparison tests - old vs. new system outputs
6. Set up regression test library (problematic wiki pages)
7. Manual validation (run full pipeline on all variants)
8. Fix bugs and issues

**Test database strategy**:
- Keep current 28KB SQL fixture (committed to git)
- Delete binary .sqlite duplicates
- Add optional production DB tests (@pytest.mark.production)

**Success Criteria**:
- Test suite passes
- New system output matches old system (or differences are intentional improvements)
- Manual validation successful on all variants
- **Maps tests pass** (TypeScript)
- No critical bugs

### Phase 7: Migration & Cutover (1-2 weeks)

**Goal**: Switch to new system permanently.

**Tasks**:
1. Final validation run
2. Full backup of current state
3. Delete `legacy/` folder
4. Update CLAUDE.md documentation
5. Generate CLI documentation (Markdown)
6. Commit and push

**Success Criteria**:
- Old system removed
- Documentation updated
- New system is only system

### Phase 8: Polish (1-2 weeks)

**Goal**: Improve developer experience and add finishing touches.

**Tasks**:
1. Better error messages
2. Progress reporting enhancements (Rich library)
3. Dry-run mode for all operations
4. CLI documentation refinement
5. Performance profiling (identify obvious bottlenecks)
6. Next steps hints after command completion

**Deferred to backlog**:
- Shell completion scripts (backlog)
- Performance metrics (backlog)
- Log commands (backlog - BUT keep "logs at..." messages)

**Success Criteria**:
- Errors are clear and actionable
- Progress reporting is informative
- Dry-run works for all commands
- Documentation is complete
- Helpful next steps hints shown

---

## 9. Timeline (WITHOUT CARGO)

**Total Estimated Time**: 17-21 weeks

**Breakdown**:
- Phase 0 (Research): ✅ COMPLETE
- Phase 1 (Foundation): 2-3 weeks
- Phase 2 (Extraction): 2 weeks
- Phase 3 (Registry): 2-3 weeks
- Phase 4 (Wiki): 4-5 weeks
- Phase 5 (Outputs): 3 weeks
- Phase 6 (Testing): 2-3 weeks
- Phase 7 (Migration): 1-2 weeks
- Phase 8 (Polish): 1-2 weeks

**Savings from deferring Cargo**: 3-5 weeks

**Note**: Timeline is estimates only. Solo dev hobby project, done whenever there's time.

---

## 10. Out of Scope (Backlog)

### High Priority (Do Next)

**See 20-high-priority-backlog.md for detailed plan**.

1. **Cargo Integration** (6 weeks) - First item after rewrite stabilizes
2. **Advanced Change Detection** (2 weeks) - Schema changes, new mechanics, C# script diffs
3. **Diff Command** (1 week) - Show local vs wiki changes before push

### Medium Priority

- Maps performance optimization (gzip, IndexedDB caching)
- Pre-defined section structures (wiki templates)
- Plain text section updates (preserve formatting)
- Image upload automation refinements

### Low Priority

- Docker support
- Shell completion scripts
- Performance metrics tracking
- Full documentation site
- Log commands (tail, show) - Keep "logs at..." messages in output
- JSON Schema type sharing (do manually instead)

---

## 11. Success Criteria

The refactoring is successful when:

1. ✅ **Feature Parity**: All current functionality preserved
2. ✅ **Output Equivalence**: New system generates identical outputs (or intentional improvements)
3. ✅ **Simpler Architecture**: Code is easier to understand and maintain
4. ✅ **Better DX**: Improved error messages, clearer CLI, helpful hints
5. ✅ **Robust**: Handles edge cases, doesn't break on game updates
6. ✅ **Tested**: Good test coverage (60% unit, 30% integration, 10% optional production)
7. ✅ **Documented**: Updated CLAUDE.md, auto-generated CLI docs
8. ✅ **Content Preservation**: Manual wiki edits never overwritten
9. ✅ **Conflict Detection**: All name conflicts caught proactively
10. ✅ **No Bash**: Pure Python CLI
11. ✅ **Stable Entity IDs**: Entities tracked reliably with resource names
12. ✅ **Simple Templates**: No inheritance, readable over maintainable
13. ✅ **Cargo-Ready**: Templates designed for easy Cargo addition later

---

## 12. Key Corrections from User Feedback

### 12.1 Unity IDs Are Unreliable

**Research said**: Use Unity ID columns for stability
**User corrected**: "Can't really use ID columns... NOT always guaranteed to be unique. We've already had cases of duplicate IDs."

**Action**: Keep resource names as primary stable keys (current approach).

### 12.2 Cargo Validation Cost

**Research said**: Add Cargo NOW to avoid double wiki updates
**User corrected**: "Wiki update overhead is irrelevant, that's what we have auto updates for"

**Key insight**: Validation cost >> wiki update automation cost

**Action**: Defer Cargo to HIGH-PRIORITY BACKLOG.

### 12.3 Template Simplifications

**User guidance**:
- Fishing is broken (fix it)
- Auras should be item subtype (currently separate - fix this)
- Molds ARE crafting recipes (don't separate)
- Skip: classes, mining, achievements, teleports, doors, books
- No template inheritance (keep simple)

**Action**: Simplify template architecture per user guidance.

### 12.4 Feature Scope

**User said**: "Things that we didn't explicitly discuss the scope of can most likely just stay as they are (e.g., C# listeners, AssetRipper stuff, ...). Of course, don't just copy things blindly 1:1 - make sure to implement any necessary changes to fit things to the new architecture (as needed)."

**Action**: Keep existing features unless explicitly removing. Adapt for new architecture, don't blindly copy.

---

## 13. Approval Status

**Status**: ✅ APPROVED - Ready to Start Phase 1

**User confirmed**:
- ✅ Cargo → HIGH-PRIORITY BACKLOG
- ✅ Stable IDs → Keep resource names
- ✅ Templates → Simplified, no inheritance
- ✅ Test DB → Hybrid approach approved
- ✅ DB deployment → Hybrid (symlink dev, copy build)
- ✅ Maps optimization → BACKLOG
- ✅ Shell completion → BACKLOG
- ✅ Feature scope → Stick to new plan

**Blockers**: NONE

**Next Action**: Begin Phase 1 (Foundation)

---

## 14. What's Next

### Immediate Actions

1. **Start Phase 1** - Begin foundation work
2. **Archive old system** to `legacy/`
3. **Create new structure** - Python package + merged maps
4. **Implement two-layer TOML config**
5. **Set up pytest** with hybrid fixtures
6. **Create CLI skeleton** with Typer

### First Milestone

**Phase 1 Complete** (2-3 weeks):
- Working CLI with basic commands
- Two-layer TOML config loading
- Loguru logging functioning
- pytest infrastructure ready
- No Bash dependencies
- Maps merged into monorepo

---

**End of Final Approved Implementation Plan**
