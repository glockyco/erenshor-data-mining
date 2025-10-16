# Final Implementation Plan

**Document Status**: APPROVED - Ready for Implementation
**Date**: 2025-10-16
**Purpose**: Definitive refactoring plan with all decisions finalized

---

## Executive Summary

Complete rewrite of Erenshor data mining project with clean separation from legacy system. All major architectural decisions are finalized, Priority 1 blockers have been addressed, and implementation can begin immediately after research tasks are completed.

### Approved Changes
- **Big bang rewrite** - Clean break from old system
- **Monorepo** - Merge erenshor-maps into main repository
- **Python-only CLI** - Eliminate Bash layer entirely
- **Two-layer TOML config** - No environment variables
- **Full SQLite for maps** - Not JSON
- **Keep all backups** - No retention policy
- **Test Python only** - Skip C# testing
- **Real DB for integration tests** - Copy of production database

---

## 1. Finalized Architectural Decisions

### 1.1 Migration Strategy: Big Bang Rewrite

**Decision**: Complete rewrite with zero code reuse from legacy system.

**Implementation**:
- Archive entire old system to `legacy/` folder
- Start new implementation from scratch
- Use old system only for comparison testing
- Delete `legacy/` after validation

**Rationale**: User strongly prefers clean break, "maintenance nightmare" with dual paths.

### 1.2 Repository Structure: Monorepo

```
erenshor/
├── src/
│   ├── erenshor/              # Python package
│   │   ├── extraction/        # Unity/Steam/AssetRipper orchestration
│   │   ├── database/          # SQLite schema and queries
│   │   ├── registry/          # Entity tracking, conflict detection
│   │   ├── outputs/           # Output modules (independent)
│   │   │   ├── wiki/          # MediaWiki operations
│   │   │   ├── sheets/        # Google Sheets deployment
│   │   │   └── maps/          # Maps data preparation
│   │   └── shared/            # Config, logging, utils
│   ├── maps/                  # TypeScript/Svelte frontend (merged from erenshor-maps)
│   └── Assets/Editor/         # C# Unity scripts (existing, unchanged)
├── variants/                  # Working directories (gitignored)
│   ├── main/
│   ├── playtest/
│   └── demo/
├── backups/                   # All backups, never deleted
├── tests/
│   ├── unit/                  # Minimal test data
│   ├── integration/           # Real database copy
│   └── fixtures/
├── legacy/                    # Old system (deleted after validation)
├── config.toml                # Project defaults
└── pyproject.toml             # Python dependencies
```

### 1.3 CLI Architecture: Python-Only

**Command Structure**:
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
erenshor maps preview               # Local preview server
erenshor maps build                 # Production build
erenshor maps deploy                # Deploy to Cloudflare

# Status/Info
erenshor status                     # Pipeline status
erenshor config show                # Show configuration
erenshor doctor                     # System health check
erenshor backup info                # Backup information

# Documentation
erenshor docs generate              # Generate CLI docs (Markdown)

# Global options
--variant <name>                    # Specify variant (default: main)
--dry-run                           # Preview without changes
--resume                            # Resume from failure (explicit flag)
```

**No Bash** - All orchestration in Python.

### 1.4 Configuration System: Two-Layer TOML

**Layers** (in priority order):
1. `config.local.toml` (gitignored, local overrides) - **Higher priority**
2. `config.toml` (tracked, defaults) - Lower priority

**NO**:
- Environment variables (user explicitly against them)
- .env files
- Dynamic defaults
- Multiple fallback layers

**Example**:
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
level = "info"  # User prefers verbose (INFO level)

[outputs.wiki]
api_url = "https://erenshor.wiki.gg/api.php"
base_url = "https://erenshor.wiki.gg/wiki/"
bot_username = ""  # Set in config.local.toml
bot_password = ""  # Set in config.local.toml

[variants.main]
enabled = true
app_id = "2382520"
database = "main/erenshor-main.sqlite"
sheets_spreadsheet_id = "1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E"
```

### 1.5 Data Formats

**SQLite for everything**:
- Game data database (existing)
- Registry database (new - replaces mapping.json)
- Metrics tracking (if implemented)

**Full SQLite for maps** - User requirement for future search functionality.

**TOML for configuration** - User approved.

### 1.6 Manual Mappings: Required

**Decision**: Manual mappings cannot be avoided due to legacy wiki content.

**Support**:
- Page title overrides
- Display name overrides
- Image name overrides

**Storage**: Registry SQLite database (table: `manual_mappings`).

**Auto-disambiguation**: Only for NEW entities, always respect manual overrides. Use postfix only ("... (Item)", "... (Spell)", etc.).

### 1.7 Backup Policy: Keep Everything

**Decision**: Keep ALL backups (one per game version), no automatic deletion.

**Cleanup**: Manual/on-demand only via separate command.

**Display**: Show backup count and space usage for awareness.

### 1.8 Testing Strategy

**Focus**: Python code (wiki generation, data transformations).

**Skip**: C# Unity scripts (stable, not changing in near/medium-term).

**Approach**: Hybrid - real database for integration tests, minimal database for unit tests.

**Test Database**: Copy of production database, not tracked in git (regenerate on demand).

### 1.9 Technology Stack

**Python**:
- Python 3.13+
- Typer (CLI framework)
- Rich (progress UI)
- **Loguru (logging)** - New addition
- Pydantic (config validation)
- httpx (async HTTP for wiki API)
- pytest + pytest-httpx + pytest-mock

**TypeScript (Maps)**:
- SvelteKit 2.0
- Vite
- Leaflet
- sql.js (WASM SQLite)

**C#**:
- Unity 2021.3.45f2
- Tomlyn (TOML parser)

---

## 2. Critical Decisions Based on Feedback

### 2.1 Wiki Content Preservation

**Problem**: Cannot use special markers in wiki pages (wiki team independence).

**Solution**: Template-based and table-based updates.

**Supported Update Types** (now and future):
1. **Infoboxes** (current) - `{{Item Infobox}}`, `{{Character Infobox}}`, `{{Spell Infobox}}`, etc.
2. **Tables** (current) - Loot tables, spawn locations, etc.
3. **Plain text sections** (future) - "Description", "Strategy", etc.

**Implementation**:
- Parse wikitext to identify managed templates/tables
- Update only those structures
- Preserve all other content (manual sections, notes, tips)
- NO special markers

**Status**: Need to identify all currently managed templates (see Research Tasks).

### 2.2 Name Conflict Detection

**Approach**: Track ALL wiki pages (managed + manual) and detect conflicts proactively.

**Scanning**: Run on `extract` and `wiki fetch` (as early as possible).

**Auto-Resolution**: Yes, if no conflict exists, use appropriate name field (Items.ItemName, Spells.SpellName, etc.).

**Resolution Strategies**: Postfix disambiguation only ("... (Item)", "... (Spell)", etc.). No prefix disambiguation.

**Manual Resolution**: Required when conflicts exist. Interactive command `erenshor wiki resolve-conflict <id>`.

**Reporting**: Automatic alerts at end of relevant commands + dedicated `erenshor wiki conflicts` command.

### 2.3 Resume from Failure

**Behavior**: ONLY resume if `--resume` flag provided. No timeout-based expiration.

**State Storage**: SQLite database (not JSON files).

**User Experience**: On failure, suggest flagged command for discoverability:
```
✗ Pipeline failed at: wiki_push

To resume:
  erenshor update --resume
```

**State Tracking**: Store enough state to avoid unnecessary updates when resuming (per user question Q2.4).

### 2.4 Change Detection

**Defer to backlog**: Full diff command and most change detection features.

**Implement basic version**: Simple entity count changes and new entity type detection.

**Detail Level**: Keep it simple initially (don't overcomplicate).

### 2.5 Maps Performance

**Defer to backlog**: Full performance optimization.

**Accept current approach**: ~5 seconds initial load is acceptable for now.

### 2.6 CLI Documentation

**Format**: Markdown (not HTML).

**Content**: Simple, clear, concise list of commands, parameters, etc.

**Generation**: Via introspection of Typer CLI.

**Update Strategy**: Manual trigger + pre-commit hook (per-commit hook somewhat expensive but best stop-gap).

### 2.7 Docker

**Decision**: Put on backlog for now.

**Rationale**: Infrequent setup, Unity blocker, YAGNI for solo dev hobby project.

**Future**: Consider if project needs to be handed over.

### 2.8 Logging

**Verbosity**: User prefers verbose (INFO level by default).

**Next Steps**: Show verbose next steps hints after command completion.

**Level**: WARNING for conflict warnings and similar alerts.

### 2.9 Dry-Run Mode

**Behavior**: Show exactly what would happen (same progress outputs as non-dry-run command).

**Don't Overcomplicate**: Strive for identical output, accept limitations where not possible.

### 2.10 Confirmation Prompts

**Decision**: No confirmation prompts. Use dry-run mode instead.

### 2.11 Performance Metrics

**Storage**: SQL (in registry database or separate metrics table).

**Metrics to Track**: Whatever is actionable and useful/interesting (see Research Tasks for recommendations).

### 2.12 Test Database

**Storage**: NOT in git (see Research Tasks for best practice recommendation).

**Update Frequency**: Manual/on-demand only.

**Edge Cases**: Track as encountered, build regression test library over time.

---

## 3. Implementation Phases

### Phase 0: Research & Preparation

**Duration**: 1-2 weeks

**Tasks**:
1. Research stable entity IDs (analyze user-provided database backups) - **BLOCKER**
2. Identify all currently managed wiki templates - **BLOCKER**
3. Answer Cargo integration question - **BLOCKER**
4. Create current feature checklist (ensure nothing lost)
5. Recommend test database best practices
6. Recommend actionable performance metrics
7. Recommend log command UX (logs tail, logs show)
8. Design JSON Schema type sharing approach (if worth it)

**Deliverables**:
- Stable entity ID strategy
- Complete list of managed templates
- Cargo integration plan
- Feature preservation checklist
- Test DB recommendation
- Metrics recommendations
- Log command design
- Type sharing recommendation

**Blockers**: Cannot start Phase 1 without completing research tasks.

### Phase 1: Foundation

**Duration**: 2-3 weeks

**Goal**: Set up new project structure and core systems.

**Tasks**:
1. Archive old system to `legacy/`
2. Create new Python package structure
3. Implement two-layer TOML config system
4. Implement Loguru logging
5. Implement path resolution (strongly-typed config classes)
6. Set up pytest infrastructure (fixtures, conftest.py)
7. Create CLI skeleton with Typer
8. Implement basic commands (status, config show, doctor)

**Success Criteria**:
- CLI runs and shows help
- Config loads from config.toml + config.local.toml
- Logging works with configurable levels
- Tests run (even if mostly empty)
- No Bash dependencies

**Deliverable**: Working CLI skeleton with no functionality yet.

### Phase 2: Data Extraction

**Duration**: 2-3 weeks

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

**Deliverable**: Extraction pipeline works end-to-end.

### Phase 3: Registry System

**Duration**: 2-3 weeks

**Goal**: Implement robust entity tracking and conflict detection.

**Tasks**:
1. Design stable entity UID system (based on research from Phase 0)
2. Create registry SQLite database schema
3. Implement entity registration
4. Implement manual mappings system
5. Implement ALL wiki pages tracking (managed + manual)
6. Implement conflict detection
7. Implement conflict resolution UI (`erenshor wiki conflicts`, `resolve-conflict`)
8. Integrate with extraction pipeline

**Success Criteria**:
- Registry tracks all entities with stable UIDs
- Manual mappings work (page title, display name, image name overrides)
- Conflict detection catches all conflicts (managed + manual pages)
- Interactive conflict resolution works
- Proactive conflict alerts work

**Deliverable**: Registry system fully operational.

### Phase 4: Wiki System

**Duration**: 3-4 weeks

**Goal**: Re-implement wiki operations with proper content preservation.

**Tasks**:
1. MediaWiki API client (proper usage of recentchanges API)
2. Wiki page fetching (incremental, respects recentchanges)
3. Template-based content parsing (identify managed templates)
4. Page generation from database (all entity types)
5. Content merging (preserve manual sections, update managed templates/tables)
6. Upload with rate limiting
7. Conflict detection integration
8. Image change detection (use recentchanges to find updated images)

**Success Criteria**:
- `erenshor wiki fetch` works correctly
- `erenshor wiki update` generates pages preserving manual content
- `erenshor wiki push` uploads without overwriting manual changes
- Template-based updates work for all entity types
- Image change detection works

**Deliverable**: Wiki operations fully functional with proper content preservation.

### Phase 5: Output Modules

**Duration**: 2-3 weeks

**Goal**: Implement sheets and maps outputs.

**Tasks**:
1. Refactor Google Sheets deployment (keep current approach, clean up if needed)
2. Maps data preparation (full SQLite, optimize if easy wins available)
3. Merge erenshor-maps repository into monorepo
4. URL coordination (wiki URLs in sheets, maps URLs in wiki, etc.)
5. Maps preview command (local dev server)

**Success Criteria**:
- `erenshor sheets deploy` works identically to old system
- Maps have full database access
- Maps preview works locally
- URL coordination works across outputs

**Deliverable**: All outputs working.

### Phase 6: Testing & Validation

**Duration**: 2-3 weeks

**Goal**: Ensure new system works correctly.

**Tasks**:
1. Unit tests (60% target coverage) - minimal test data
2. Integration tests (30% target coverage) - real database
3. Comparison tests (10%) - old vs. new system outputs
4. Create test database (copy of production)
5. Set up regression test library (problematic wiki pages)
6. Manual validation (run full pipeline on all variants)
7. Fix bugs and issues

**Success Criteria**:
- Test suite passes
- New system output matches old system (or differences are intentional improvements)
- Manual validation successful on all variants
- No critical bugs

**Deliverable**: Validated, tested system.

### Phase 7: Migration & Cutover

**Duration**: 1 week

**Goal**: Switch to new system permanently.

**Tasks**:
1. Final validation run
2. Full backup of current state
3. Delete `legacy/` folder
4. Update CLAUDE.md documentation
5. Generate CLI documentation
6. Commit and push

**Success Criteria**:
- Old system removed
- Documentation updated
- New system is only system

**Deliverable**: Clean codebase with new system only.

### Phase 8: Polish

**Duration**: 1-2 weeks

**Goal**: Improve developer experience and add finishing touches.

**Tasks**:
1. Better error messages
2. Progress reporting enhancements
3. Dry-run mode for all operations
4. Shell completion scripts (if easy)
5. CLI documentation refinement
6. Performance profiling (identify obvious bottlenecks)

**Success Criteria**:
- Errors are clear and actionable
- Progress reporting is informative
- Dry-run works for all commands
- Documentation is complete

**Deliverable**: Polished, production-ready system.

---

## 4. Out of Scope (Backlog)

The following items are explicitly deferred to backlog:

1. **Diff command** (Q1.5, Q2.5) - Show diffs between wiki and generated content
2. **Maps performance optimization** (Q2.6, Q2.7, Issue 2) - Compression, IndexedDB caching, offline support
3. **Advanced change detection** (Q3.7, Issue 6) - C# script diffing, field-level detection, actionable reports
4. **Docker support** (Q2.11, Q2.12, Q2.13, Issue 9) - Containerization for Unity and other tools
5. **Full documentation site** (Q3.13) - MkDocs or similar (beyond CLI docs)
6. **Pre-defined section structures** (Issue 1 follow-up) - Standard section templates for different page types
7. **Auto-generated listener code** (Q2.5) - Generate boilerplate for new fields/types
8. **Backup cleanup automation** (manual is sufficient)
9. **Image upload automation** (semi-automatic is sufficient for now, full automation is goal)
10. **Advanced logging features** (logs tail, logs show - see Research Tasks for recommendations)
11. **Performance metrics dashboard** (basic SQL queries are sufficient for now)
12. **Resume for individual stages** (Q2.4) - Full pipeline resume is sufficient
13. **CLI auto-completion** (nice to have)
14. **Progress ETAs** (Q3.8) - Inaccurate estimates not worth it

See **12-backlog.md** for details on each item.

---

## 5. Success Criteria

The refactoring is successful when:

1. ✅ **Feature Parity**: All current functionality preserved
2. ✅ **Output Equivalence**: New system generates identical (or intentionally improved) outputs
3. ✅ **Simpler Architecture**: Code is easier to understand and maintain
4. ✅ **Better DX**: Improved error messages, clearer CLI, helpful hints
5. ✅ **Robust**: Handles edge cases, doesn't break on game updates
6. ✅ **Tested**: Good test coverage (60% unit, 30% integration, 10% comparison)
7. ✅ **Documented**: Updated CLAUDE.md, auto-generated CLI docs
8. ✅ **Content Preservation**: Manual wiki edits never overwritten
9. ✅ **Conflict Detection**: All name conflicts caught proactively
10. ✅ **No Bash**: Pure Python CLI

---

## 6. Risks & Mitigation

### Risk 1: Scope Creep
**Mitigation**: Strict adherence to phases. Features beyond current scope go to backlog.

### Risk 2: Underestimated Complexity
**Mitigation**: Focus on MVP, defer non-critical features, ask for help when stuck.

### Risk 3: Breaking Changes to Data
**Mitigation**: Extensive comparison testing, gradual rollout, backup everything.

### Risk 4: Lost Functionality
**Mitigation**: Complete feature checklist before starting (see **14-current-feature-checklist.md**).

### Risk 5: Burnout
**Mitigation**: Clear milestones, celebrate wins, take breaks. User is hyped!

---

## 7. Dependencies & Blockers

### Current Blockers

**Before Phase 1 can start**:
1. Complete research tasks (Phase 0) - **See 13-research-tasks.md**
2. User provides 2-3 database backups for stable ID analysis

**External Dependencies**:
- Unity 2021.3.45f2 (must match game version)
- SteamCMD (existing)
- AssetRipper (existing)
- MediaWiki API (existing)
- Google Sheets API (existing)

**No New Dependencies**: All tools already in use.

---

## 8. Communication Plan

### Status Updates
- **Weekly**: What was done, what's next, any blockers
- **Milestones**: Detailed update when phases complete
- **Blockers**: Immediate notification if stuck

### Decision Points
- **Architecture changes**: Consult before making significant changes
- **Scope additions**: Request approval for new features
- **Trade-offs**: Present options when decisions needed

### Documentation
- Keep planning docs updated
- Document key decisions and rationale
- Update CLAUDE.md as architecture evolves

---

## 9. Timeline

**Total Estimated Time**: 16-20 weeks

**Breakdown**:
- Phase 0 (Research): 1-2 weeks
- Phase 1 (Foundation): 2-3 weeks
- Phase 2 (Extraction): 2-3 weeks
- Phase 3 (Registry): 2-3 weeks
- Phase 4 (Wiki): 3-4 weeks
- Phase 5 (Outputs): 2-3 weeks
- Phase 6 (Testing): 2-3 weeks
- Phase 7 (Migration): 1 week
- Phase 8 (Polish): 1-2 weeks

**Note**: User explicitly stated "no timeline estimates needed" - solo dev hobby project, done whenever there's time.

**Reality Check**: Part-time solo dev work, expect delays and unknowns. These are rough estimates only.

---

## 10. What's Next

### Immediate Actions

1. **Review this plan** - User approval
2. **Complete research tasks** - See **13-research-tasks.md**
3. **User provides database backups** - Critical for entity ID analysis
4. **Start Phase 1** - Once research complete

### Documents to Review

- **11-final-plan.md** (this document) - Overall plan
- **12-backlog.md** - Deferred features
- **13-research-tasks.md** - What AI needs to investigate
- **14-current-feature-checklist.md** - Features to preserve

---

## Approval

**Status**: AWAITING APPROVAL

**User Actions Required**:
1. Review and approve this plan
2. Review research tasks document
3. Provide database backups for analysis
4. Confirm ready to proceed

**Once Approved**: Begin Phase 0 (Research & Preparation).

---

**End of Final Plan**
