# Final Implementation Plan

**Document Status**: FINAL - Ready for Phase 1
**Date**: 2025-10-16
**Purpose**: Definitive refactoring plan with all research completed and decisions finalized

---

## Executive Summary

Complete rewrite of Erenshor data mining project with clean separation from legacy system. All major architectural decisions are finalized, all research tasks completed, and implementation can begin immediately.

### Research Completed

- **Stable Entity IDs**: Strategy finalized (use Unity Id/Guid fields)
- **Template Inventory**: Complete audit done (20 templates, 4 categories)
- **Cargo Integration**: Decision made (implement NOW with phased rollout)
- **Test Database**: Strategy finalized (keep current hybrid approach)

### Major Decisions Finalized

- Big bang rewrite - Clean break from old system
- Monorepo - Merge erenshor-maps into main repository
- Python-only CLI - Eliminate Bash layer entirely
- Two-layer TOML config - No environment variables
- Full SQLite for maps - Database accessible via Cloudflare static assets
- Cargo integration - Implement now (6-week phased rollout)
- Keep all backups - No retention policy
- Test Python only - Skip C# testing

---

## 1. Architecture Updates from Latest Feedback

### 1.1 Maps Architecture Refinement

**Output directory structure**:
```
erenshor/
├── src/
│   ├── erenshor/
│   │   ├── outputs/
│   │   │   ├── wiki/          # MediaWiki operations
│   │   │   ├── sheets/        # Google Sheets deployment
│   │   │   └── maps/          # Maps data preparation (MAY NOT BE NEEDED)
│   └── maps/                  # TypeScript/Svelte frontend
│       └── static/
│           └── data/          # Database deployed here (Cloudflare serves as static asset)
```

**Key update from feedback**: Maps access database directly, may not need `src/erenshor/outputs/maps` module. Keep structure flexible for now, can remove if unnecessary.

**Database deployment**: Need to figure out how to get DB from `variants/main/erenshor-main.sqlite` to `src/maps/static/data/` for Cloudflare deployment without moving it out of variants directory.

**Options**:
1. Copy database during build: `erenshor maps build` copies DB to static/data/
2. Symlink during development: `erenshor maps dev` symlinks for live updates
3. Build artifact: Database is a build output, not source

### 1.2 CLI Commands (Complete)

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

**Note**: `erenshor maps dev` vs `erenshor maps preview` - dev is development server, preview is built site preview.

### 1.3 Testing Architecture

**Test organization**:
```
tests/
├── conftest.py                     # Shared fixtures
├── unit/                           # Fast, isolated tests
│   ├── test_item_obtainability.py
│   └── formatters/
│       └── test_sheets_formatter.py
├── integration/                    # Real components
│   ├── test_item_obtainability_real_db.py
│   ├── test_character_updates.py
│   └── test_idempotency.py
└── maps/                           # Maps tests (TypeScript/Jest)
    ├── unit/
    └── integration/
```

**Important**: Don't forget maps tests (TypeScript tests in maps/ directory).

### 1.4 Template Architecture (From Research)

**Current inventory** (20 templates across 4 categories):

**Items** (8 subtypes):
- General items: `items/item.j2` → `{{Item}}`
- Weapons: `items/fancy_weapon_*.j2` → `{{Fancy-weapon}}`
- Armor: `items/fancy_armor_*.j2` → `{{Fancy-armor}}`
- Charms: `items/fancy_charm.j2` → `{{Fancy-charm}}`
- Auras: Uses `{{Item}}` template
- Ability Books: `items/ability_book.j2` → `{{Ability Books}}`
- Molds: `items/mold.j2` → `{{Mold}}`
- Consumables: Uses `{{Item}}` template

**Abilities** (shared template):
- Spells & Skills: `abilities/ability.j2` → `{{Ability}}`

**Characters** (unified template):
- NPCs & Enemies: `characters/enemy.j2` → `{{Enemy}}`

**Fishing**:
- Fishing canonical: `fishing/canonical.j2` → Full page content

**Future templates needed** (high priority):
- Quests: Complex relationships (items, NPCs, prerequisites, rewards)
- Factions: Simple structure
- Zones: Aggregate many entities

**Key correction from feedback**: "Items have quite a few 'subtypes', some of which use their own specialized templates (e.g., weapons, armor)." Also: "spells and skills share an ability template."

---

## 2. Stable Entity ID Strategy (From Research)

### 2.1 Recommended Primary Keys

| Entity Type | Primary Stable Key | Fallback Key | Risk Level |
|-------------|-------------------|--------------|------------|
| **Items** | `item:{Id}` | `item:{ResourceName}` | Low |
| **Spells** | `spell:{Id}` | `spell:{ResourceName}` | Low |
| **Skills** | `skill:{Id}` | `skill:{ResourceName}` | Low |
| **Characters (Prefab)** | `character:{Guid}` | `character:{ObjectName}` | Medium |
| **Characters (Scene)** | `character:{ObjectName}|{Scene}|{X}|{Y}|{Z}` | Manual mapping required | High |
| **Quests** | `quest:{DBName}` | `quest:{ResourceName}` | Very Low |
| **Factions** | `faction:{REFNAME}` | None needed | Very Low |

### 2.2 Implementation Strategy

**Change stable_key generation** (backward compatible):
```python
@property
def stable_key(self) -> str:
    """Key for tracking entities across versions (prefers db_id)."""
    # Prefer db_id for stability (Id for Items/Spells/Skills, Guid for Characters, etc.)
    if self.db_id is not None:
        return f"{self.entity_type.value}:{self.db_id}"
    # Fallback to resource_name
    if self.resource_name:
        return f"{self.entity_type.value}:{self.resource_name}"
    # Last resort: display name
    return f"{self.entity_type.value}:{self.db_name}"
```

**Update EntityRef.from_* methods**:
- Items/Spells/Skills: Use `Id` field as db_id
- Character prefabs: Use `Guid` field as db_id
- Character scene instances: Use coordinate-based key, accept manual mapping
- Quests: Use `DBName` field as db_id
- Factions: Use `REFNAME` as resource_name

**Migration**:
1. Update stable_key property to prefer db_id (Phase 3)
2. Migrate existing registry.json (automatic conversion)
3. Migrate mapping.json to registry database

**Special handling**:
- Scene-placed characters inherently unstable (Unity limitation)
- Rely on manual mapping for important NPCs
- Use coordinate proximity matching as fallback

---

## 3. Cargo Integration Strategy (From Research)

### 3.1 Decision: Implement NOW

**Rationale**:
1. User requirement: Cargo is **MUST HAVE** (not optional)
2. Adding later requires regenerating/re-uploading ALL pages
3. Minimal overhead now vs significant rework later
4. User is wiki team representative (no long feedback cycles)

### 3.2 Architecture Integration

**Cargo fits cleanly into existing architecture**:
```
Database (SQLite)
    ↓
Generator (Python)
    ↓
Template Context (Pydantic) [UNCHANGED]
    ↓
Jinja2 Template [MODIFIED: Add #cargo_store calls]
    ↓
WikiText Output [MODIFIED: Includes Cargo storage]
    ↓
MediaWiki API Upload
    ↓
Cargo Database [NEW: MediaWiki extension stores data]
```

**Template changes**:
- Add `#cargo_declare` to `<noinclude>` section
- Add `#cargo_store` to `<includeonly>` section
- No Python code changes required

### 3.3 Phased Rollout (6 weeks)

**Phase 1 (Week 1)**: Foundation
- Install Cargo extension on wiki
- Design core table schemas (map Pydantic models to Cargo)
- Create Cargo template module (Python helper functions)
- Integrate into one template (Enemy) and test

**Phase 2 (Week 2)**: Core entities
- Items, Abilities, Factions, Zones templates
- All core Cargo tables created
- Test report for each entity type

**Phase 3 (Week 3)**: Relationship tables
- EnemyDrops, EnemySpawns, EnemyAbilities
- ItemSources, ItemComponents
- Cross-page queries working

**Phase 4 (Week 4)**: Dynamic queries
- Zone pages with enemy lists
- Item pages with drop sources
- Statistics pages

**Phase 5 (Week 5)**: Testing & documentation
- Integration testing
- Performance testing
- User documentation
- Maintainer guide

**Phase 6 (Week 6)**: Production deployment
- Upload all templates
- Run "Recreate data"
- Full pipeline with Cargo
- Monitoring

### 3.4 Cargo Table Schema

**Core entity tables**:
- `Enemies` - Character/NPC base stats
- `Items` - Item base stats
- `Abilities` - Spell/Skill base stats
- `Factions` - Faction information
- `Zones` - Zone/area information

**Relationship tables** (junction):
- `EnemySpawns` - Enemy spawn locations
- `EnemyDrops` - Enemy loot tables
- `EnemyAbilities` - Enemy abilities
- `EnemyFactions` - Enemy faction relationships
- `ItemSources` - Item acquisition methods
- `ItemClasses` - Item class restrictions
- `ItemComponents` - Crafting recipes
- `AbilityClasses` - Ability class restrictions
- `VendorItems` - Vendor inventories

---

## 4. Test Database Strategy (From Research)

### 4.1 Current Approach: Already Optimal

**Keep existing hybrid approach**:
- **Unit tests (70%)**: In-memory SQLite with programmatic fixtures
- **Integration tests (20%)**: Minimal 28KB SQL fixture (committed to git)
- **Production tests (10%)**: Optional full database copy (5.5MB, generated on demand)

**Current implementation is already following best practices**. No changes needed.

### 4.2 Production Database Testing (Optional Enhancement)

**Add `@pytest.mark.production` tests**:
- Copy production database for comprehensive validation
- Test complex queries across all entities
- Catch edge cases not in minimal fixture
- Skip if database unavailable

**Implementation**:
```python
@pytest.fixture(scope="session")
def production_db_path(tmp_path_factory) -> Path | None:
    """Copy production database for comprehensive testing."""
    prod_db_path = repo_root / "variants/main/erenshor-main.sqlite"
    if not prod_db_path.exists():
        return None
    test_db_path = tmp_path_factory.mktemp("prod_db") / "erenshor-production.sqlite"
    shutil.copy2(prod_db_path, test_db_path)
    return test_db_path
```

**Git strategy**:
- 28KB SQL fixture: Committed to git
- Binary .sqlite files: Delete, generate from SQL
- 5.5MB production DB: Never commit, copy on demand

**NO Git-LFS**: Not worth cost for solo dev hobby project.

---

## 5. Implementation Phases (Updated)

### Phase 0: Preparation (COMPLETE)

**All research tasks completed**:
- ✅ Stable entity IDs (use Unity Id/Guid fields)
- ✅ Template inventory (20 templates, 4 categories)
- ✅ Cargo integration (implement NOW with 6-week rollout)
- ✅ Test database (keep current hybrid approach)

**Ready to start Phase 1**.

### Phase 1: Foundation (2-3 weeks)

**Goal**: Set up new project structure and core systems.

**Tasks**:
1. Archive old system to `legacy/`
2. Create new Python package structure
3. Implement two-layer TOML config system
4. Implement Loguru logging (verbose INFO level by default)
5. Implement path resolution (strongly-typed config classes)
6. Set up pytest infrastructure (keep current fixtures)
7. Create CLI skeleton with Typer
8. Implement basic commands (status, config show, doctor, test)

**Success Criteria**:
- CLI runs and shows help
- Config loads from config.toml + config.local.toml
- Logging works with INFO level
- Tests run (pytest unit + integration)
- No Bash dependencies

**Maps integration**: Merge erenshor-maps repo into monorepo structure.

### Phase 2: Data Extraction (2-3 weeks)

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
1. Implement stable UID system (use Id/Guid fields per research)
2. Create registry SQLite database schema
3. Implement entity registration
4. Migrate manual mappings from mapping.json to registry database
5. Implement ALL wiki pages tracking (managed + manual)
6. Implement conflict detection
7. Implement conflict resolution UI (`erenshor wiki conflicts`, `resolve-conflict`)
8. Integrate with extraction pipeline

**Stable ID implementation**:
- Update EntityRef.stable_key to prefer db_id
- Migrate existing mapping.json to new format
- Support both formats during transition

**Success Criteria**:
- Registry tracks all entities with stable UIDs (Id/Guid-based)
- Manual mappings migrated to database
- Conflict detection catches all conflicts
- Interactive conflict resolution works

### Phase 4: Wiki System (3-4 weeks)

**Goal**: Re-implement wiki operations with proper content preservation.

**Tasks**:
1. MediaWiki API client (proper usage of recentchanges API)
2. Wiki page fetching (incremental, respects recentchanges)
3. Template-based content parsing (all 20 templates identified)
4. Page generation from database (all entity types, all subtypes)
5. Content merging (preserve manual sections, update managed templates/tables)
6. Upload with rate limiting
7. Conflict detection integration
8. Image change detection (use recentchanges to find updated images)

**Template handling**:
- Support all 8 item subtypes (weapons, armor, charms, auras, books, molds, consumables, general)
- Support shared ability template (spells + skills)
- Support character template (NPCs + enemies)
- Plan ahead for quest templates

**Success Criteria**:
- `erenshor wiki fetch` works correctly
- `erenshor wiki update` generates pages preserving manual content
- All 20 templates supported
- `erenshor wiki push` uploads without overwriting manual changes
- Image change detection works

### Phase 5: Cargo Integration (6 weeks) - PARALLEL with Phase 4/6

**See detailed rollout plan in Section 3.3**.

**Can run in parallel with other phases** after Phase 4 foundation is complete.

**Deliverable**: All wiki pages include Cargo storage, all Cargo tables populated, dynamic queries working.

### Phase 6: Output Modules (2-3 weeks)

**Goal**: Implement sheets and maps outputs.

**Tasks**:
1. Refactor Google Sheets deployment (keep current approach, clean up if needed)
2. Maps data preparation (copy database to static/data/ for Cloudflare)
3. Maps CLI commands (dev, preview, build, deploy)
4. URL coordination (wiki URLs in sheets, maps URLs in wiki, etc.)
5. Database deployment strategy (copy vs symlink for dev/build)

**Maps implementation**:
- `erenshor maps dev` - Start dev server (npm run dev), symlink DB for live updates
- `erenshor maps preview` - Preview built site (npm run preview)
- `erenshor maps build` - Production build, copy DB to static/data/
- `erenshor maps deploy` - Deploy to Cloudflare

**Success Criteria**:
- `erenshor sheets deploy` works identically to old system
- Maps have full database access via static assets
- Maps dev/preview/build/deploy all work
- Database accessible at runtime without moving from variants/

### Phase 7: Testing & Validation (2-3 weeks)

**Goal**: Ensure new system works correctly.

**Tasks**:
1. Unit tests (60% target coverage) - in-memory DB
2. Integration tests (30% target coverage) - 28KB SQL fixture
3. Optional production tests (10%) - 5.5MB database copy
4. Maps tests (TypeScript/Jest) - don't forget!
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
- Maps tests pass
- No critical bugs

### Phase 8: Migration & Cutover (1 week)

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

### Phase 9: Polish (1-2 weeks)

**Goal**: Improve developer experience and add finishing touches.

**Tasks**:
1. Better error messages
2. Progress reporting enhancements (Rich library)
3. Dry-run mode for all operations
4. Shell completion scripts (if easy)
5. CLI documentation refinement
6. Performance profiling (identify obvious bottlenecks)
7. Next steps hints after command completion

**Success Criteria**:
- Errors are clear and actionable
- Progress reporting is informative
- Dry-run works for all commands
- Documentation is complete
- Helpful next steps hints shown

---

## 6. Updated Backlog (From Feedback)

**Moved to backlog**:
1. **Performance metrics** (Task 5) - Not critical for initial implementation
2. **Log commands** (Task 6) - Manual log access sufficient, BUT keep "logs at..." messages in command outputs
3. **JSON Schema type sharing** (Task 7) - Do manually instead, not worth generation complexity

**Cargo**: **NOT on backlog** - Implement NOW per decision in Section 3.

**High priority backlog** (after initial rewrite):
1. Diff command (show wiki changes before push)
2. Advanced change detection (C# script diffing, field-level detection)
3. Image upload automation (full automation of changed images)

---

## 7. Success Criteria

The refactoring is successful when:

1. ✅ **Feature Parity**: All current functionality preserved (per feature checklist)
2. ✅ **Output Equivalence**: New system generates identical outputs (or intentional improvements)
3. ✅ **Simpler Architecture**: Code is easier to understand and maintain
4. ✅ **Better DX**: Improved error messages, clearer CLI, helpful hints
5. ✅ **Robust**: Handles edge cases, doesn't break on game updates
6. ✅ **Tested**: Good test coverage (60% unit, 30% integration, 10% optional production)
7. ✅ **Documented**: Updated CLAUDE.md, auto-generated CLI docs
8. ✅ **Content Preservation**: Manual wiki edits never overwritten
9. ✅ **Conflict Detection**: All name conflicts caught proactively
10. ✅ **No Bash**: Pure Python CLI
11. ✅ **Cargo Integration**: Wiki has structured data storage and dynamic queries
12. ✅ **Stable Entity IDs**: Entities tracked reliably across game versions (Id/Guid-based)

---

## 8. Remaining Questions

**See 18-remaining-questions.md** for detailed list.

**Critical questions** (must answer before Phase 1):
- None remaining (all research complete)

**Important questions** (should answer early):
- Database deployment strategy for maps (copy vs symlink)
- Cargo rollout timing (parallel with Phase 4/6 or after?)

**Minor questions** (can defer):
- Maps performance optimization timing (backlog or initial?)
- CLI shell completion (nice-to-have or initial?)

---

## 9. What's Next

### Immediate Actions

1. **Review Cargo decision document** (17-cargo-decision.md) - Confirm NOW vs HIGH-PRIORITY-BACKLOG
2. **Review remaining questions** (18-remaining-questions.md) - Address any blockers
3. **Start Phase 1** - Begin foundation work

### Timeline

**Total Estimated Time**: 20-26 weeks (including 6-week Cargo rollout)

**Breakdown**:
- Phase 0 (Research): ✅ COMPLETE
- Phase 1 (Foundation): 2-3 weeks
- Phase 2 (Extraction): 2-3 weeks
- Phase 3 (Registry): 2-3 weeks
- Phase 4 (Wiki): 3-4 weeks
- Phase 5 (Cargo): 6 weeks (parallel with Phase 4/6)
- Phase 6 (Outputs): 2-3 weeks
- Phase 7 (Testing): 2-3 weeks
- Phase 8 (Migration): 1 week
- Phase 9 (Polish): 1-2 weeks

**Note**: User explicitly stated "no timeline estimates needed" - solo dev hobby project, done whenever there's time.

---

## Approval

**Status**: READY FOR APPROVAL

**User Actions Required**:
1. Review and approve Cargo decision (17-cargo-decision.md)
2. Review remaining questions (18-remaining-questions.md)
3. Confirm ready to proceed with Phase 1

**Once Approved**: Begin Phase 1 (Foundation).

---

**End of Final Implementation Plan**
