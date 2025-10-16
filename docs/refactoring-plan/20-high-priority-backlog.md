# High-Priority Backlog (Post-Rewrite)

**Document Status**: APPROVED
**Date**: 2025-10-16
**Purpose**: Clear plan for features to implement AFTER the rewrite is complete and stable

---

## Executive Summary

This document outlines the high-priority features to implement immediately after the main rewrite is complete. These features were intentionally deferred to avoid validation overhead during the rewrite, but are critical for the long-term success of the project.

**Timeline**: These items should be tackled in order after Phase 8 (Polish) is complete and the new system has been validated.

**Total Estimated Effort**: 9 weeks (6 + 2 + 1)

---

## Immediate Post-Rewrite (High Priority)

### Item 1: Cargo Integration (6 weeks)

**Priority**: HIGHEST - First item after rewrite stabilizes

**Why Deferred**: Avoid huge manual validation requirements during rewrite. Validation cost >> wiki update automation cost.

**User Rationale**: "Wiki update overhead is irrelevant, that's what we have auto updates for, but deferring Cargo for now avoids huge manual validation requirements beyond what we already need to do as part of the refactoring/rewrite. The future effort is the same as the current one."

**Why It's Critical**:
- User requirement: Cargo is **MUST HAVE** (not optional)
- Enables structured data queries across wiki pages
- Makes manual wiki editing much easier
- Modern gaming wikis require structured data
- Foundation for many future features (dynamic lists, statistics, search)

**Implementation Reference**: See `15-research-cargo-integration.md` for detailed architecture and rollout plan.

#### Phase 1 (Week 1): Foundation

**Tasks**:
1. Install Cargo extension on MediaWiki instance
2. Design core table schemas (map Pydantic models to Cargo types)
3. Create Cargo template module (Python helper functions)
4. Integrate into one template (Enemy) and test
5. Validate Cargo storage and retrieval

**Deliverables**:
- Cargo extension installed and configured
- Schema design document (Pydantic → Cargo mapping)
- Python helper module for generating `#cargo_declare` and `#cargo_store` calls
- One working template with Cargo integration
- Test report confirming data storage and retrieval

**Success Criteria**:
- Enemy template stores data in Cargo
- Can query Cargo database via Special:CargoTables
- Data matches source database (SQLite)

#### Phase 2 (Week 2): Core Entities

**Tasks**:
1. Add Cargo to Items template (all 8 subtypes)
2. Add Cargo to Abilities template (spells + skills)
3. Add Cargo to Factions template
4. Add Cargo to Zones template
5. Regenerate and upload all core entity pages
6. Run "Recreate data" to populate Cargo tables
7. Validate all core tables

**Deliverables**:
- All core entity templates include Cargo storage
- Core Cargo tables populated:
  - `Enemies`
  - `Items`
  - `Abilities`
  - `Factions`
  - `Zones`
- Test report for each entity type

**Success Criteria**:
- All core entities stored in Cargo
- Row counts match SQLite database
- Field values match source data

#### Phase 3 (Week 3): Relationship Tables

**Tasks**:
1. Design junction table schemas:
   - `EnemyDrops` (enemy → item drops)
   - `EnemySpawns` (enemy → spawn locations)
   - `EnemyAbilities` (enemy → abilities)
   - `EnemyFactions` (enemy → factions)
   - `ItemSources` (item → acquisition methods)
   - `ItemClasses` (item → class restrictions)
   - `ItemComponents` (item → crafting recipes)
   - `AbilityClasses` (ability → class restrictions)
   - `VendorItems` (vendor → items sold)
2. Add relationship storage to templates
3. Regenerate and upload all pages
4. Run "Recreate data"
5. Validate all junction tables

**Deliverables**:
- All junction tables created
- Relationship data stored in Cargo
- Cross-page queries working

**Success Criteria**:
- Can query which enemies drop specific items
- Can query where items are obtained
- Can query which abilities enemies use
- Row counts match SQLite junction tables

#### Phase 4 (Week 4): Dynamic Queries

**Tasks**:
1. Add dynamic enemy lists to zone pages (via Cargo query)
2. Add dynamic "Dropped By" sections to item pages (via Cargo query)
3. Add dynamic "Used By" sections to ability pages (via Cargo query)
4. Add dynamic item lists to vendor pages (via Cargo query)
5. Create statistics pages (enemy counts by zone, item counts by type, etc.)
6. Test all queries for performance and correctness

**Deliverables**:
- Zone pages auto-populate enemy lists
- Item pages auto-populate drop sources
- Ability pages auto-populate enemy usage
- Statistics pages working

**Success Criteria**:
- Dynamic queries update when data changes
- No manual maintenance required for cross-references
- Query performance is acceptable (<2 seconds per page)

#### Phase 5 (Week 5): Testing & Documentation

**Tasks**:
1. Integration testing (full pipeline with Cargo)
2. Performance testing (query times, page load times)
3. Edge case testing (missing data, null values, empty results)
4. User documentation (how to use Cargo queries)
5. Maintainer guide (how to add new Cargo tables)
6. Schema documentation (all table definitions)

**Deliverables**:
- Integration test suite for Cargo
- Performance test results
- User documentation for Cargo queries
- Maintainer guide for schema changes
- Complete schema documentation

**Success Criteria**:
- All tests pass
- Performance is acceptable
- Documentation is clear and complete

#### Phase 6 (Week 6): Production Deployment

**Tasks**:
1. Final validation on staging wiki
2. Upload all templates to production wiki
3. Run full pipeline to regenerate all pages
4. Upload all pages to production wiki
5. Run "Recreate data" on production
6. Validate all Cargo tables on production
7. Monitor for issues
8. Fix any problems that arise

**Deliverables**:
- All production wiki pages include Cargo data
- All Cargo tables populated on production
- Monitoring dashboard (query counts, errors, performance)
- Post-deployment report

**Success Criteria**:
- All pages uploaded successfully
- All Cargo tables populated correctly
- No errors in MediaWiki logs
- Dynamic queries working on production
- Users can use Cargo queries

**Estimated Effort**: 6 weeks total

**Dependencies**: Requires stable rewrite (Phase 8 complete)

**Risks**:
- Cargo extension version compatibility
- Schema design mistakes (requires regenerating all pages)
- Performance issues with large queries
- Manual validation is time-consuming

**Mitigation**:
- Test on staging wiki first
- Design schemas carefully upfront
- Use indexes for common queries
- Batch validation with automated tests

---

### Item 2: Advanced Change Detection (2 weeks)

**Priority**: HIGH - Alerts developer to important game changes

**Why Deferred**: Not critical for initial rewrite functionality, but important for maintenance.

**Current State**: Basic change detection exists (entity count differences).

**Goal**: Detect schema changes, new game mechanics, and C# script modifications.

#### Week 1: Schema & Mechanic Detection

**Tasks**:
1. Detect new database columns (schema changes)
2. Detect new entity types (new ScriptableObject types)
3. Detect new game mechanics (new fields on existing entities)
4. Alert developer with clear messages
5. Suggest appropriate actions (add to listener, update template, etc.)

**Deliverables**:
- Schema change detection module
- New entity type detection
- New mechanic detection
- Alert system with actionable messages

**Example Alerts**:
```
[SCHEMA CHANGE DETECTED]
New column: Items.SpiritBound (Boolean)
Suggestion: Add SpiritBound to ItemListener.cs and update item template

[NEW ENTITY TYPE DETECTED]
New ScriptableObject type: PetCompanion
Suggestion: Create PetListener.cs and pet template

[NEW MECHANIC DETECTED]
New field: Character.MountSpeed (Float)
Suggestion: Review CharacterListener.cs for mount-related fields
```

#### Week 2: C# Script Diff Detection

**Tasks**:
1. Track C# script changes in Unity project (game scripts, not Editor scripts)
2. Diff game scripts between versions
3. Identify new game mechanics from script changes
4. Alert developer to review significant changes
5. Integrate with extraction pipeline

**Deliverables**:
- C# script tracking module
- Diff generation for game scripts
- Mechanic detection from script changes
- Integration with `erenshor extract` command

**Example Alerts**:
```
[GAME SCRIPT CHANGED]
File: CharacterController.cs
Changes: Added mount system (50 lines added)
Suggestion: Review mount-related data extraction

[NEW GAME SYSTEM DETECTED]
New scripts: PetSystem.cs, PetCompanion.cs, PetInventory.cs
Suggestion: Create data extraction for pet system
```

**Success Criteria**:
- Detects all schema changes automatically
- Identifies new entity types
- Diffs game scripts between versions
- Provides actionable suggestions to developer
- Alerts are clear and non-spammy

**Estimated Effort**: 2 weeks

**Dependencies**: Requires extraction pipeline (Phase 2 complete)

**Benefits**:
- Developer aware of all game changes
- Reduces risk of missing new data
- Clear guidance on what to update
- Easier to keep up with game updates

---

### Item 3: Diff Command (1 week)

**Priority**: HIGH - Debugging and validation tool

**Why Deferred**: Nice-to-have for initial rewrite, but very useful for ongoing maintenance.

**Goal**: Show differences between local changes and wiki content before pushing.

#### Implementation

**Tasks**:
1. Fetch current wiki page content
2. Generate new page content locally
3. Diff the two versions (text diff)
4. Show differences in CLI (colored output)
5. Optionally show only template/table diffs (ignore manual sections)
6. Support filtering by entity type or specific pages

**Deliverables**:
- `erenshor wiki diff` command
- `erenshor wiki diff --entity-type items` (filter by type)
- `erenshor wiki diff --page "Sword of Power"` (specific page)
- `erenshor wiki diff --managed-only` (ignore manual sections)
- Colored diff output (green = added, red = removed, yellow = changed)

**Example Usage**:
```bash
# Show all differences
erenshor wiki diff

# Show only item page differences
erenshor wiki diff --entity-type items

# Show specific page diff
erenshor wiki diff --page "Ancient Sword"

# Show only managed section diffs (ignore manual changes)
erenshor wiki diff --managed-only

# Show summary only (counts)
erenshor wiki diff --summary
```

**Example Output**:
```
[DIFF] Ancient Sword
  ├─ Managed sections: 3 changes
  │  ├─ Template (Fancy-weapon): 1 field changed
  │  │  └─ attack_speed: 2.5 → 2.8 (+0.3)
  │  ├─ Drops table: 1 row added
  │  │  └─ + Dropped by: Ancient Guardian (10%)
  │  └─ Stats table: 2 values changed
  │     ├─ Attack: 150 → 160 (+10)
  │     └─ Critical: 5% → 8% (+3%)
  └─ Manual sections: No changes detected
```

**Success Criteria**:
- Shows all differences between local and wiki
- Filters work correctly (entity type, specific pages, managed-only)
- Colored output is readable
- Helps developer understand what will change before pushing
- Summary mode shows counts (X pages with changes, Y total changes)

**Estimated Effort**: 1 week

**Dependencies**: Requires wiki system (Phase 4 complete)

**Benefits**:
- Debugging tool (see what changed)
- Validation before pushing (catch mistakes)
- Confidence that manual edits won't be overwritten
- Understand impact of database changes

---

## Medium Priority Backlog

These items are valuable but not urgent. Tackle after high-priority items are complete.

### Maps Performance Optimization (2-3 weeks)

**Current State**: ~5 second initial load (acceptable per user: "That's good enough for a first throw")

**Optimizations**:
1. **gzip compression** (~70% size reduction)
   - Compress SQLite database for web delivery
   - Decompress in browser using pako.js
   - Estimated load time: ~2 seconds
2. **IndexedDB caching** (~100ms subsequent loads)
   - Cache decompressed database in browser
   - Check for updates via ETag or version hash
   - Instant loads after first visit
3. **Lazy loading** (load what's needed)
   - Load only necessary tables on startup
   - Fetch additional data as needed
   - Reduces initial payload

**Effort**: 2-3 weeks (including testing and validation)

### Pre-defined Section Structures (1-2 weeks)

**Goal**: Define expected sections for each entity type to guide wiki maintainers.

**Example for items**:
```
== Obtaining ==
[Auto-generated from database]

== Uses ==
[Manual section - preserve]

== Notes ==
[Manual section - preserve]

== Gallery ==
[Manual section - preserve]
```

**Benefits**:
- Consistent page structure
- Clear guidance for maintainers
- Easier to detect manual sections

### Plain Text Section Updates (2-3 weeks)

**Goal**: Update plain text sections (description, notes, etc.) without overwriting manual formatting.

**Approach**:
- Detect if content has changed significantly (fuzzy match)
- Preserve manual formatting (line breaks, bold, italics, links)
- Only update if content is clearly outdated

**Benefits**:
- Keep descriptions up to date
- Preserve manual improvements
- Less manual review needed

### Image Upload Automation Refinements (1-2 weeks)

**Current State**: Image change detection works via recentchanges API.

**Improvements**:
1. Automatically upload new images (not just detect changes)
2. Compare image hashes to detect visual changes (not just uploads)
3. Support bulk image uploads (new game version with many new items)
4. Better error handling for upload failures

**Benefits**:
- Fully automated image pipeline
- Detect actual visual changes (not just metadata)
- Handle bulk imports efficiently

---

## Low Priority Backlog

These items are nice-to-have but not critical. Consider for future improvements.

### Docker Support (1-2 weeks)

**Goal**: Containerize pipeline for easier setup and consistency.

**Benefits**:
- No local Unity installation needed (Unity in Docker)
- Reproducible environment
- Easier for contributors
- Consistent behavior across machines

**Challenges**:
- Unity licensing in Docker
- Large Docker images
- Performance overhead

### Shell Completion (1 day)

**Goal**: Tab completion for CLI commands.

**Implementation**: Typer has built-in completion support.

**Commands**:
- `erenshor --install-completion` (install for current shell)
- `eval "$(_ERENSHOR_COMPLETE=source_bash erenshor)"` (load completion)

**Effort**: 1 day (mostly documentation)

### Performance Metrics Tracking (1-2 weeks)

**Goal**: Track pipeline performance over time.

**Metrics**:
- Extraction time (download, rip, export)
- Database size (total, per table)
- Wiki upload time (per page, total)
- Sheets deployment time
- Memory usage
- CPU usage

**Benefits**:
- Identify performance regressions
- Optimize bottlenecks
- Understand resource usage

### Full Documentation Site (2-3 weeks)

**Goal**: Comprehensive documentation site with guides, architecture diagrams, API docs, etc.

**Content**:
- User guide (how to run pipeline)
- Developer guide (how to add new features)
- Architecture overview (diagrams, flow charts)
- API documentation (auto-generated from code)
- Troubleshooting guide
- FAQ

**Tools**: MkDocs, Sphinx, or similar

**Benefits**:
- Easier onboarding for contributors
- Better project documentation
- Professional appearance

### Log Commands (1 day)

**Current State**: User manually opens log files.

**Enhancement**: Add CLI commands for viewing logs:
- `erenshor logs tail` (tail current log)
- `erenshor logs show <log-file>` (show specific log)
- `erenshor logs list` (list all logs)

**Keep**: "Logs at..." messages in command outputs (already good UX)

**Effort**: 1 day

### JSON Schema Type Sharing (REJECTED)

**User decision**: "Do manually instead, not worth generation complexity"

**Rationale**: Manual type definitions are simpler and more maintainable than generation scripts.

**Action**: REMOVE from backlog.

---

## Summary

### High Priority (Total: 9 weeks)

1. **Cargo Integration** (6 weeks) - MUST HAVE, first after rewrite
2. **Advanced Change Detection** (2 weeks) - Important for maintenance
3. **Diff Command** (1 week) - Debugging and validation tool

### Medium Priority (Total: 8-11 weeks)

4. Maps performance optimization (2-3 weeks)
5. Pre-defined section structures (1-2 weeks)
6. Plain text section updates (2-3 weeks)
7. Image upload automation refinements (1-2 weeks)

### Low Priority (Total: 6-10 weeks)

8. Docker support (1-2 weeks)
9. Shell completion (1 day)
10. Performance metrics tracking (1-2 weeks)
11. Full documentation site (2-3 weeks)
12. Log commands (1 day)

### Total Estimated Backlog Effort: 23-30 weeks

**Note**: These are estimates for solo development. Actual time will vary based on complexity discovered during implementation.

---

## Recommended Order

1. **Complete Phase 8 of rewrite** (1-2 weeks)
2. **Stabilize new system** (1-2 weeks of production use)
3. **Cargo Integration** (6 weeks) - HIGHEST PRIORITY
4. **Advanced Change Detection** (2 weeks)
5. **Diff Command** (1 week)
6. Reassess priorities based on user needs
7. Tackle medium/low priority items as needed

---

**End of High-Priority Backlog**
