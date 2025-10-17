# Phase 3 Implementation Plan - Executive Summary

**Status**: Ready to Execute  
**Duration**: 3-4 weeks part-time (35-40 hours)  
**Date**: 2025-10-17

---

## What Phase 3 Delivers

**In One Sentence**: Wire up all Phase 2 infrastructure into working CLI commands that users can actually use.

**Phase 2 Built**: Database, extraction wrappers, wiki client, sheets publisher  
**Phase 3 Builds**: CLI commands, service orchestration, wiki generation, integration tests

---

## Key Milestones

### Week 1: CLI Orchestration (6-7 hours)
- Extract commands (full, download, rip, export)
- Backup service (automatic backups on export)
- Change detection (show what changed)

**Deliverable**: Working extraction pipeline with `erenshor extract full`

### Week 2: Wiki Generation (12-14 hours)
- Repository queries for wiki data
- Page generator with Jinja2 templates
- Content merger (preserve manual edits)
- Wiki service (orchestrate workflow)
- Wiki commands (fetch, update, push)

**Deliverable**: Working wiki generation with `erenshor wiki update`

### Week 3 (First Half): Sheets Deployment (4-5 hours)
- Sheets deploy service
- Sheets commands (list, deploy)

**Deliverable**: Working sheets deployment with `erenshor sheets deploy --all-sheets`

### Week 3-4: Integration Testing (9-10 hours)
- CLI workflow tests
- Service orchestration tests
- Repository query tests
- Regression tests

**Deliverable**: >80% test coverage, 469+ tests passing

### Week 4: Documentation (4-5 hours)
- Update CLAUDE.md
- Create user guides
- Phase 3 completion report

**Deliverable**: Complete documentation for all Phase 3 features

---

## Architecture

```
CLI Commands (Typer)
    ↓
Application Services (NEW - Phase 3)
    ├── WikiService (fetch → generate → merge → publish)
    ├── SheetsDeployService (query → format → publish)
    ├── BackupService (create backups automatically)
    └── ChangeDetectionService (detect database changes)
    ↓
Infrastructure (Phase 2)
    ├── MediaWikiClient
    ├── GoogleSheetsPublisher
    ├── SteamCMDWrapper
    ├── AssetRipperWrapper
    ├── UnityBatchMode
    └── Repositories
```

**Key Principle**: Services are thin coordinators, not feature implementations.

---

## Task Overview

### 16 Tasks Total

**Milestone 1: CLI Orchestration** (3 tasks)
1. Extract commands (2h)
2. Backup service (1.5h)
3. Change detection service (1.5h)

**Milestone 2: Wiki Generation** (5 tasks)
4. Repository queries (2h)
5. Page generator (3h)
6. Content merger (2.5h)
7. Wiki service (2.5h)
8. Wiki commands (2h)

**Milestone 3: Sheets Deployment** (2 tasks)
9. Sheets deploy service (2h)
10. Sheets commands (1.5h)

**Milestone 4: Integration Testing** (4 tasks)
11. CLI integration tests (2.5h)
12. Service integration tests (2h)
13. Repository integration tests (1.5h)
14. Regression tests (2h)

**Milestone 5: Documentation** (3 tasks)
15. Update CLAUDE.md (1.5h)
16. Create user guides (2h)
17. Completion report (1h)

---

## What's Different from Phase 2?

**Phase 2 Focus**: Build infrastructure (wrappers, clients, publishers)  
**Phase 3 Focus**: Wire infrastructure together into working features

**Phase 2 Deferred**:
- CLI command orchestration → Phase 3 Task 1.1, 2.5, 3.2
- Service layer → Phase 3 Tasks 1.2, 1.3, 2.4, 3.1
- Wiki page generation → Phase 3 Tasks 2.2, 2.3
- Integration testing → Phase 3 Milestone 4

**Phase 2 Approach**: "Build infrastructure, stub orchestration"  
**Phase 3 Approach**: "Connect infrastructure, implement orchestration"

---

## YAGNI Principles for Phase 3

**DO Add**:
- Repository query methods when needed for features
- Service methods when needed for orchestration
- Templates for entity types we actually use

**DON'T Add**:
- Speculative query methods ("might be useful")
- Complex features not in plan (interactive conflict resolution)
- Template inheritance (keep simple)
- Performance optimizations unless needed

---

## Success Criteria

Phase 3 is complete when:

1. ✅ All CLI commands work (extract, wiki, sheets)
2. ✅ Wiki generation preserves manual content
3. ✅ Sheets deployment works for all 21 queries
4. ✅ Integration tests pass (>80% coverage)
5. ✅ Documentation updated (CLAUDE.md + guides)
6. ✅ Quality gates pass (mypy, ruff, pytest)

---

## Key Risks

1. **Template Complexity**: Wiki templates might be harder than expected
   - Mitigation: Start simple, defer complex ones

2. **Content Merging Edge Cases**: Manual edits might conflict unexpectedly
   - Mitigation: Comprehensive tests, dry-run mode, backups

3. **Scope Creep**: Temptation to add "nice to have" features
   - Mitigation: Strict YAGNI, defer to backlog, user approval for changes

---

## Implementation Order

**Sequential (must follow order)**:
1. Milestone 1 → Milestone 4 (testing needs commands)
2. Within Milestone 2: Tasks 2.1 → 2.2 → 2.3 → 2.4 → 2.5

**Parallel (can do simultaneously)**:
- Milestones 1, 2, 3 (independent features)
- Tasks 4.1, 4.2, 4.3, 4.4 (after dependencies met)
- Tasks 5.1, 5.2 (documentation)

**Recommended Approach**: Do milestones 1, 2, 3 sequentially, then testing, then docs.

---

## Quick Reference

**See Full Plan**: `docs/refactoring-plan/phase-3-tasks.md`

**Key Commands After Phase 3**:
```bash
# Extraction
erenshor extract full

# Wiki
erenshor wiki fetch
erenshor wiki update
erenshor wiki push

# Sheets
erenshor sheets list
erenshor sheets deploy --all-sheets

# Status
erenshor status
```

**Testing**:
```bash
uv run pytest                    # All tests
uv run pytest tests/integration  # Integration only
uv run pytest tests/regression   # Regression only
uv run pytest --cov              # With coverage
```

---

## Next Steps

1. **Read full plan**: `docs/refactoring-plan/phase-3-tasks.md`
2. **Start with Milestone 1**: CLI orchestration (Week 1)
3. **Commit after each task**: Atomic commits
4. **Run tests frequently**: `uv run pytest`
5. **Ask questions early**: Clarify before implementing

---

**End of Summary**
