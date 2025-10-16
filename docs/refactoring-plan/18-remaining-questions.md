# Remaining Questions

**Document Status**: FOR USER REVIEW
**Date**: 2025-10-16
**Purpose**: Track any outstanding questions before Phase 1 begins

---

## Executive Summary

**Critical Blockers**: None (all research complete)

**Important Questions**: 2 questions to answer early in implementation

**Minor Questions**: 3 questions that can be deferred

**Overall Status**: Ready to start Phase 1 with minimal outstanding questions

---

## Critical Questions (Must Answer Before Phase 1)

**None remaining** - All research tasks completed:
- ✅ Stable entity IDs - Strategy finalized
- ✅ Template inventory - Complete audit done
- ✅ Cargo integration - Decision document created
- ✅ Test database - Strategy finalized

---

## Important Questions (Should Answer Early)

### Q1: Cargo Integration Timing

**Question**: Should Cargo be implemented NOW (6-week phased rollout) or HIGH-PRIORITY BACKLOG (first item after rewrite)?

**Context**:
- User requirement: Cargo is MUST HAVE (not optional)
- Research finding: Adding later requires regenerating/re-uploading ALL pages
- Recommendation: Implement NOW (see 17-cargo-decision.md)

**Impact**: Timeline (6-week difference), architecture (design decisions), user experience (when structured data becomes available)

**Decision Required**: User must choose Option A (NOW) or Option B (BACKLOG) in 17-cargo-decision.md

**Urgency**: High - Affects Phase 1 planning and template architecture

---

### Q2: Database Deployment Strategy for Maps

**Question**: How should the database be deployed to maps static assets without moving it from variants directory?

**Context**:
- Maps need database in `src/maps/static/data/erenshor.sqlite` for Cloudflare deployment
- Database lives in `variants/main/erenshor-main.sqlite` (gitignored)
- Don't want to move DB out of variants directory (per user comment: "We don't really want to move it out of the variants directory")

**Options**:

**Option A: Copy during build**
```bash
erenshor maps build
# Copies variants/main/erenshor-main.sqlite → src/maps/static/data/erenshor.sqlite
# Build artifact includes database
```
- ✅ Clean separation (variants/ stays gitignored)
- ✅ Build artifact is self-contained
- ❌ Stale database if build isn't re-run

**Option B: Symlink during dev**
```bash
erenshor maps dev
# Symlinks variants/main/erenshor-main.sqlite → src/maps/static/data/erenshor.sqlite
# Live updates during development
```
- ✅ Live updates (no rebuild needed)
- ✅ Always fresh data
- ❌ Symlink management complexity
- ❌ Doesn't work for production build

**Option C: Copy on dev/build, delete after**
```bash
erenshor maps dev     # Copy DB, start dev server
erenshor maps build   # Copy DB, build, remove from build artifact
```
- ✅ Flexible for both dev and build
- ❌ More complex cleanup logic

**Recommendation**: **Hybrid approach**
- `erenshor maps dev`: Symlink for live updates (delete symlink on exit)
- `erenshor maps build`: Copy for production build
- Add `.gitignore` entry for `src/maps/static/data/*.sqlite`

**Decision Required**: Confirm approach or suggest alternative

**Urgency**: Medium - Can be decided during Phase 6 (Outputs), but affects `src/erenshor/outputs/maps` module design

---

## Minor Questions (Can Defer)

### Q3: Maps Performance Optimization Timing

**Question**: Should maps performance optimization (compression, IndexedDB caching) be part of initial rewrite or backlog?

**Context**:
- Current performance: ~5 seconds initial load (acceptable per user)
- Optimizations: gzip compression (~70% size reduction), IndexedDB caching (~100ms subsequent loads)
- User feedback: "That's good enough for a first throw"

**Options**:
- **Initial rewrite**: Include basic optimizations (gzip compression)
- **Backlog**: Defer all optimizations, revisit if load times become problematic

**Current Plan**: Backlog (per feedback)

**Decision Required**: Confirm or change priority

**Urgency**: Low - Can decide during Phase 6 (Outputs)

---

### Q4: CLI Shell Completion

**Question**: Should CLI auto-completion (Bash/Zsh/Fish) be included in initial rewrite or backlog?

**Context**:
- Typer has built-in completion support (very easy to add)
- Implementation: `erenshor --install-completion` or `eval "$(_ERENSHOR_COMPLETE=source_bash erenshor)"`
- Effort: Low (1 day - mostly documentation)

**Options**:
- **Initial rewrite**: Add during Phase 9 (Polish)
- **Backlog**: Defer as nice-to-have feature

**Current Plan**: Backlog (not critical)

**Decision Required**: Confirm or change priority

**Urgency**: Low - Can decide during Phase 9 (Polish)

---

### Q5: `src/erenshor/outputs/maps` Module Necessity

**Question**: Do we actually need a `src/erenshor/outputs/maps` Python module?

**Context**: User feedback: "Not sure we will need src/erenshor/outputs/maps. After all, maps will directly access DB data."

**Analysis**:
- Maps CLI commands (dev, preview, build, deploy) are mostly npm script wrappers
- Database copying/symlinking can be handled in CLI command directly
- May not need a full output module like wiki/sheets

**Options**:
- **Keep module**: Consistent structure with wiki/sheets outputs
- **Simplify**: Just CLI commands, no output module
- **Defer decision**: Implement during Phase 6, see what's actually needed

**Recommendation**: **Defer decision** to Phase 6 - Implement what's actually needed, don't over-engineer

**Decision Required**: None (defer to implementation)

**Urgency**: Low - Will become clear during Phase 6 implementation

---

## Questions from Feature Checklist Review

**Note**: The feature checklist (14-current-feature-checklist.md) is quite thorough. User asked "What do you need from me here?"

**Response**: The checklist is just a reference to ensure nothing is lost. Main thing needed is to confirm high-level features to preserve/improve/remove.

**Outstanding**:
- User to review checklist and flag any features that should be explicitly removed (legacy baggage)
- User to confirm all entity types are documented correctly
- User to validate special cases section (items 11.1)

**Urgency**: Medium - Should review before Phase 4 (Wiki) to ensure all templates are planned

**Action**: User to scan checklist and flag any concerns/corrections

---

## Summary by Urgency

### Critical (Must answer before Phase 1)
- None remaining ✅

### Important (Should answer early in Phase 1-3)
1. **Q1: Cargo timing** - Requires decision now (affects architecture)
2. **Q2: Database deployment for maps** - Can defer to Phase 6 but affects design

### Minor (Can answer during implementation)
3. **Q3: Maps performance optimization** - Decide during Phase 6
4. **Q4: CLI shell completion** - Decide during Phase 9
5. **Q5: Maps output module necessity** - Defer to Phase 6 implementation

### For User Review (Non-blocking)
- Feature checklist review (flag legacy baggage to remove)

---

## Next Steps

1. **User reviews 17-cargo-decision.md** - Choose Option A (NOW) or Option B (BACKLOG)
2. **User reviews Q2** - Confirm database deployment approach for maps
3. **User scans feature checklist** - Flag anything to explicitly remove
4. **Start Phase 1** - Foundation work begins

**Blockers**: Only Q1 (Cargo timing) needs decision before starting Phase 1. All other questions can be answered during implementation.

---

## Approval

**Status**: READY FOR USER REVIEW

**User Actions**:
1. ✅ Review 17-cargo-decision.md and choose Cargo timing
2. ✅ Confirm database deployment approach (Q2) or defer to Phase 6
3. ⏸️ Review feature checklist (non-blocking, can do during Phase 1-3)
4. ⏸️ Minor questions (Q3-Q5) can be answered during implementation

**Once Cargo decision is made**: Ready to begin Phase 1 immediately.

---

**End of Remaining Questions**
