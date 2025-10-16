# Cargo Integration Decision

**Document Status**: REQUIRES USER DECISION
**Date**: 2025-10-16
**Purpose**: Finalize Cargo implementation timing

---

## Executive Summary

**User Requirement**: Cargo is **MUST HAVE** (not optional)

**Key Finding**: Research shows adding Cargo later requires regenerating/re-uploading ALL wiki pages. The overhead of deferring is greater than implementing now.

**Recommendation**: **Implement Cargo NOW** as part of initial rewrite (6-week phased rollout parallel with Phase 4/6).

**User Decision Needed**: Confirm NOW vs HIGH-PRIORITY-BACKLOG

---

## What is MediaWiki Cargo?

**Cargo** is a MediaWiki extension that stores template data in database tables, enabling:

- **Structured queries** across wiki pages (SQL-like queries)
- **Dynamic lists and tables** that auto-update when data changes
- **Complex relationships** (items dropped by enemies, quests requiring items, etc.)
- **Data aggregation** (statistics, counts, summaries)
- **Cross-page references** without manual maintenance

**Example use case**: On an item page, automatically show which enemies drop it by querying the Cargo database. When a new enemy is added that drops the item, the list updates automatically.

---

## Research Summary

### Key Findings from research-cargo-integration.md

1. **Minimal Overhead to Add Now**: Our generator-based architecture already produces all necessary data. Adding Cargo requires only template updates (Jinja2 changes), no Python code changes.

2. **Significant Rework if Added Later**:
   - Requires modifying every template to include `#cargo_declare` and `#cargo_store` calls
   - Requires regenerating ALL wiki pages
   - Requires re-uploading ALL pages
   - Requires testing all templates
   - Requires validating all Cargo schemas

3. **Schema Design is Upfront Work**: Cargo table schemas (field names, types, relationships) must be designed before templates are deployed. Changing schemas later requires:
   - Recreating Cargo tables (data loss)
   - Updating all template calls
   - Regenerating and re-uploading all pages

4. **Wiki Maintainer Benefit**: Cargo makes manual editing easier:
   - Adding a new enemy drop? Just add one `{{#cargo_store}}` call
   - Item page's "Dropped By" section updates automatically
   - No need to manually update both enemy and item pages

5. **User Expectation**: Modern gaming wikis use structured data (Cargo or Semantic MediaWiki). Without Cargo, the Erenshor wiki feels outdated.

### Architectural Integration

Cargo fits cleanly into our existing architecture with minimal changes:

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

**What changes**:
- Add `#cargo_declare` to template `<noinclude>` section (one-time per template)
- Add `#cargo_store` to Jinja2 templates (mirrors existing template parameters)

**What doesn't change**:
- Python generators (no changes)
- Pydantic context models (no changes)
- Database schema (no changes)
- Upload logic (no changes)

---

## Implementation Comparison: NOW vs BACKLOG

### Option A: Implement NOW (6-week phased rollout)

**Phase 1 (Week 1)**: Foundation
- Install Cargo extension on wiki
- Design core table schemas (map Pydantic models to Cargo types)
- Create Cargo template module (Python helper functions)
- Test with one template (Enemy)

**Phase 2 (Week 2)**: Core entities
- Items, Abilities, Factions, Zones templates
- All core Cargo tables created and populated

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

**Phase 6 (Week 6)**: Production deployment
- Upload all templates
- Run "Recreate data"
- Full pipeline with Cargo

**Effort**: 6 weeks (can run parallel with Phase 4/6 of main rewrite)

**Risk**: Low (Cargo is mature, well-supported extension)

**Benefits**:
- ✅ No rework later (templates designed with Cargo from start)
- ✅ Wiki maintainers get structured data immediately
- ✅ Dynamic cross-references work from day one
- ✅ Clean architecture (no half-Cargo state)
- ✅ User is wiki team representative (no feedback cycles)

**Drawbacks**:
- ❌ 6 weeks additional effort in initial rewrite
- ❌ Need to install Cargo extension (one-time setup)
- ❌ More complex templates (but only slightly)

### Option B: HIGH-PRIORITY BACKLOG (implement after initial rewrite)

**When**: First backlog item after initial rewrite is stable

**Effort**: 2-3 weeks (faster because rewrite is done, but still requires full regeneration)

**Process**:
1. Design Cargo schemas (map existing templates to Cargo tables)
2. Update all templates to include Cargo calls
3. Install Cargo extension on wiki
4. Regenerate ALL wiki pages with new templates
5. Re-upload ALL pages to wiki
6. Run "Recreate data" to populate Cargo tables
7. Validate all Cargo queries
8. Fix any issues

**Benefits**:
- ✅ Defers 6 weeks of work to after initial rewrite
- ✅ Can validate base system before adding Cargo
- ✅ Allows time to observe wiki team's needs

**Drawbacks**:
- ❌ Requires regenerating/re-uploading ALL pages (hundreds of pages)
- ❌ Risk of breaking existing pages during migration
- ❌ Manual wiki edits during rewrite → backlog period may conflict
- ❌ Users won't have structured data benefits during initial rollout
- ❌ Two rounds of "big wiki updates" instead of one
- ❌ Template changes after deployment = more risky

---

## Recommendation: Implement NOW

### Rationale

1. **Avoid Rework**: Adding Cargo later requires the same template design work PLUS regenerating all pages. Doing it now means one round of page generation instead of two.

2. **Research Finding**: "Adding Cargo later requires regenerating/re-uploading all pages" - This is the critical finding. The cost of deferral is high.

3. **User Requirement**: User said Cargo is "MUST HAVE" and "the wiki team has long wanted to introduce Cargo." This isn't a nice-to-have feature.

4. **No Feedback Cycles**: User is the wiki team representative, so we can design Cargo architecture directly without waiting for external feedback.

5. **Clean Architecture**: Designing templates with Cargo from the start is cleaner than retrofitting later. We avoid "half-Cargo" state.

6. **Parallel Work**: Cargo rollout (6 weeks) can run in parallel with Phase 4 (Wiki) and Phase 6 (Outputs) of main rewrite, minimizing timeline impact.

7. **Future-Proofing**: Many planned wiki improvements depend on Cargo:
   - Dynamic enemy lists by zone
   - Dynamic item sources
   - Statistics pages
   - Search and filtering
   - Without Cargo, these require manual maintenance or complex bots

### Design Decisions to Make NOW (Prevents Rework Later)

Even if we defer Cargo to backlog, we MUST make these decisions now:

1. **Template Parameter Names**: Must match Cargo field names (can't change later without regenerating pages)
2. **Pydantic Context Models**: Must map cleanly to Cargo types (no nested structures)
3. **Relationship Data**: Must be separate blocks (not inline in infobox)
4. **Template Structure**: Must use `<noinclude>`/`<includeonly>` sections (reserve space for Cargo)

**Conclusion**: If we have to design for Cargo anyway, we might as well implement it now.

---

## Timeline Impact

### If Implemented NOW

**Total Rewrite Timeline**: 20-26 weeks (including 6-week Cargo rollout)

**Cargo Phases**: Run parallel with Phase 4 (Wiki) and Phase 6 (Outputs)
- Week 1: During Phase 4 (Wiki foundation)
- Week 2-3: During Phase 4 (template implementation)
- Week 4-5: During Phase 6 (outputs)
- Week 6: During Phase 7 (testing)

**Impact**: Minimal (Cargo work happens during other phases, slight complexity increase)

### If Deferred to BACKLOG

**Initial Rewrite Timeline**: 14-20 weeks (no Cargo)

**Cargo Implementation Later**: 2-3 weeks AFTER rewrite is stable

**Total Timeline**: 16-23 weeks (similar to NOW option, but split into two phases)

**Risk**: Higher (two rounds of major wiki updates instead of one)

---

## User Decision Required

**Question**: Should we implement Cargo integration NOW (6-week rollout) or defer to HIGH-PRIORITY BACKLOG (first item after rewrite)?

### Option A: NOW (RECOMMENDED)
- 6-week phased rollout parallel with Phase 4/6
- One round of wiki page generation
- Clean architecture from start
- Users get structured data immediately

### Option B: HIGH-PRIORITY BACKLOG
- Saves 6 weeks in initial rewrite
- But requires 2-3 weeks later PLUS regenerating all pages
- Two rounds of major wiki updates
- Delays structured data benefits

**My Recommendation**: **Option A (NOW)**

**Reasoning**: The cost of regenerating all pages later outweighs the benefit of deferring 6 weeks. Since Cargo is MUST HAVE, we should build it in from the start.

---

## If User Chooses NOW: Next Steps

1. **Approve this decision** - Confirm Cargo integration in initial rewrite
2. **Verify Cargo availability** - Confirm Cargo extension is available on wiki
3. **Begin Phase 1** - Start foundation work
4. **Start Cargo design during Phase 4** - Map Pydantic models to Cargo schemas
5. **Test Cargo with one template** - Validate integration before rolling out to all templates

---

## If User Chooses BACKLOG: Requirements

If deferring Cargo, we MUST do the following NOW to avoid rework:

1. **Design templates with Cargo in mind**: Use `<noinclude>`/`<includeonly>` sections
2. **Use Cargo-compatible field names**: Lowercase with underscores (e.g., `drop_chance` not `dropChance`)
3. **Document all template fields**: Create schema mappings for future Cargo design
4. **Keep relationship data separate**: Don't inline junction table data in infoboxes
5. **Use simple Pydantic types**: Avoid nested structures (Cargo doesn't support nested objects)

**Preconditions for adding Cargo later**:
- Backup all pages (full export)
- Test on staging wiki
- Freeze content during migration
- Regenerate all pages
- Re-upload all pages
- Recreate Cargo tables
- Validate all queries

---

## Approval

**Status**: AWAITING USER DECISION

**Please choose**:
- [ ] **Option A: Implement NOW** (6-week phased rollout, one round of wiki updates)
- [ ] **Option B: HIGH-PRIORITY BACKLOG** (defer 6 weeks, requires design decisions now + full regeneration later)

**Once decided**: Update 16-final-implementation-plan.md with choice and proceed to Phase 1.

---

**End of Cargo Decision Document**
