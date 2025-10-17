# Erenshor Refactoring - Phase Overview

**Last Updated**: 2025-10-17

---

## Phase Timeline

```
Phase 1 (COMPLETE)     Phase 2 (COMPLETE)     Phase 3 (PLANNED)
Foundation             Infrastructure         Orchestration
2-3 weeks              ~3 weeks               3-4 weeks
```

---

## What Each Phase Delivered

### Phase 1: Foundation (COMPLETE)
**Status**: ✅ Merged to main (a29bacfa)

**Built**:
- Project structure and monorepo
- Two-layer TOML config system
- Loguru logging infrastructure
- CLI skeleton with Typer
- Registry system
- Testing infrastructure (pytest, fixtures)
- Maps merged into monorepo

**Deliverables**:
- Working CLI framework
- Config system loading from TOML files
- Logging to files and console
- 469 tests passing (Phase 1 foundation)

**Key Files**:
- `src/erenshor/infrastructure/config/` (config system)
- `src/erenshor/infrastructure/logging/` (logging)
- `src/erenshor/registry/` (entity registry)
- `src/erenshor/cli/main.py` (CLI entry point)

---

### Phase 2: Infrastructure (COMPLETE)
**Status**: ✅ Merged to main (c0b2cfe8)

**Built**:
- Domain entity models (11 entities)
- Database repositories (minimal skeletons)
- Extraction wrappers (SteamCMD, AssetRipper, Unity)
- MediaWiki API client (623 lines)
- Wiki template parser (mwparserfromhell)
- Google Sheets publisher (961 lines)
- Google Sheets formatter with 21 SQL queries

**Deliverables**:
- All infrastructure components ready
- CLI commands stubbed (orchestration deferred)
- 469 tests passing (infrastructure tested)

**Key Files**:
- `src/erenshor/domain/entities/` (11 entity models)
- `src/erenshor/infrastructure/database/repositories/` (11 repositories)
- `src/erenshor/infrastructure/steam/steamcmd.py` (330 lines)
- `src/erenshor/infrastructure/assetripper/wrapper.py` (317 lines)
- `src/erenshor/infrastructure/unity/batch_mode.py` (517 lines)
- `src/erenshor/infrastructure/wiki/client.py` (623 lines)
- `src/erenshor/infrastructure/wiki/template_parser.py` (418 lines)
- `src/erenshor/infrastructure/publishers/sheets.py` (961 lines)
- `src/erenshor/application/formatters/sheets/queries/*.sql` (21 queries)

**What Was Deferred**:
- CLI command implementations → Phase 3
- Service orchestration layer → Phase 3
- Wiki page generation → Phase 3
- Integration testing → Phase 3

---

### Phase 3: Orchestration (THIS PHASE)
**Status**: ⏭️ Ready to Start

**Will Build**:
- CLI command implementations (extract, wiki, sheets)
- Service orchestration layer (WikiService, SheetsDeployService, etc.)
- Wiki page generation (templates, merging, conflict detection)
- Repository query methods (add as needed)
- Integration testing (end-to-end workflows)
- Documentation updates

**Will Deliver**:
- Working extraction pipeline (`erenshor extract full`)
- Working wiki generation (`erenshor wiki update`)
- Working sheets deployment (`erenshor sheets deploy --all-sheets`)
- >80% test coverage with integration tests
- Complete user documentation

**Key Files (To Be Created)**:
- `src/erenshor/application/services/wiki_service.py`
- `src/erenshor/application/services/sheets_deploy_service.py`
- `src/erenshor/application/services/backup.py`
- `src/erenshor/application/services/change_detector.py`
- `src/erenshor/application/generators/page_generator.py`
- `src/erenshor/application/generators/content_merger.py`
- `templates/wiki/*.j2` (Jinja2 templates)
- `tests/integration/cli/` (CLI workflow tests)
- `tests/integration/services/` (service tests)
- `tests/regression/` (edge case tests)

---

## Architecture Evolution

### Phase 1 Architecture
```
┌─────────────────────────────┐
│   CLI Framework (Typer)     │
│   • main.py                 │
│   • Command groups          │
│   • Help text               │
└──────────┬──────────────────┘
           │
┌──────────▼──────────────────┐
│   Infrastructure            │
│   • Config (TOML)           │
│   • Logging (Loguru)        │
│   • Registry                │
└─────────────────────────────┘
```

### Phase 2 Architecture (Added Infrastructure)
```
┌─────────────────────────────┐
│   CLI Commands (STUBBED)    │
│   • extract (stub)          │
│   • wiki (stub)             │
│   • sheets (stub)           │
└──────────┬──────────────────┘
           │
┌──────────▼──────────────────┐
│   Infrastructure (NEW)      │
│   • SteamCMDWrapper         │
│   • AssetRipperWrapper      │
│   • UnityBatchMode          │
│   • MediaWikiClient         │
│   • GoogleSheetsPublisher   │
│   • Repositories            │
└─────────────────────────────┘
```

### Phase 3 Architecture (Adding Orchestration)
```
┌─────────────────────────────────┐
│   CLI Commands (IMPLEMENTED)    │
│   • extract full               │
│   • wiki fetch/update/push     │
│   • sheets list/deploy         │
└──────────┬──────────────────────┘
           │
┌──────────▼──────────────────────┐
│   Application Services (NEW)    │
│   • WikiService                 │
│   • SheetsDeployService         │
│   • BackupService               │
│   • ChangeDetectionService      │
└──────────┬──────────────────────┘
           │
┌──────────▼──────────────────────┐
│   Infrastructure (Phase 2)      │
│   • MediaWikiClient             │
│   • GoogleSheetsPublisher       │
│   • SteamCMDWrapper             │
│   • AssetRipperWrapper          │
│   • UnityBatchMode              │
│   • Repositories                │
└─────────────────────────────────┘
```

---

## What Changed Between Phases

### Phase 1 → Phase 2
**Change**: Added all infrastructure components
**Deferred**: CLI orchestration, service layer

**Why**: Build infrastructure first, wire it up later
**Result**: Phase 2 has all components but they're not connected

### Phase 2 → Phase 3
**Change**: Wire infrastructure into working features
**Focus**: Orchestration, not infrastructure

**Why**: Infrastructure is complete, now make it usable
**Result**: Phase 3 delivers working CLI commands

---

## Testing Strategy Evolution

### Phase 1 Testing
- Unit tests for config, logging, registry
- 28KB fixture database
- Testing infrastructure set up
- **Coverage**: 48.63% (expected - many stubs)

### Phase 2 Testing
- Infrastructure unit tests (wrappers, clients)
- Domain entity tests
- Repository tests (skeletons)
- **Coverage**: 48.63% (many CLI stubs)

### Phase 3 Testing (Planned)
- CLI integration tests (end-to-end)
- Service orchestration tests
- Repository query tests (real database)
- Regression tests (edge cases)
- **Target Coverage**: >80%

---

## Code Metrics

### Phase 1
- **Files Created**: ~30
- **Tests**: 469 passing
- **Coverage**: 48.63%
- **Duration**: 2-3 weeks

### Phase 2
- **Files Created**: ~50
- **Lines of Code**: 
  - MediaWikiClient: 623 lines
  - GoogleSheetsPublisher: 961 lines
  - UnityBatchMode: 517 lines
  - AssetRipperWrapper: 317 lines
  - SteamCMDWrapper: 330 lines
  - TemplateParser: 418 lines
- **Tests**: 469 passing (infrastructure tests)
- **Coverage**: 48.63% (stubbed orchestration not counted)
- **Duration**: ~3 weeks

### Phase 3 (Estimated)
- **Files to Create**: ~25
- **Lines of Code Estimate**: 2,500-3,000
- **Tests Expected**: 550+ (80+ integration tests)
- **Coverage Target**: >80%
- **Duration**: 3-4 weeks

---

## Key Learnings

### From Phase 1
- Two-layer TOML config works great
- Loguru is excellent for logging
- Registry system handles entity tracking well
- Testing infrastructure solid

### From Phase 2
- Minimal repository skeletons work (YAGNI)
- Infrastructure before orchestration is right approach
- Stubbing CLI commands was good decision
- MediaWiki/Sheets infrastructure is production-ready

### For Phase 3
- Keep services thin (coordinators, not implementations)
- Add repository queries only when needed
- Start with simple templates, defer complex ones
- Focus on MVP for each feature
- YAGNI discipline is critical

---

## Decision Log

### Why Phase 2 Deferred Orchestration
**Decision**: Build infrastructure, stub CLI commands
**Rationale**: 
- Infrastructure is complex, needs focus
- Orchestration depends on infrastructure being complete
- Easier to test infrastructure in isolation
- Allows iteration on infrastructure without CLI changes

**Result**: Phase 2 delivered excellent infrastructure, Phase 3 wires it up

### Why Phase 3 Adds Service Layer
**Decision**: Create thin service layer for orchestration
**Rationale**:
- CLI commands shouldn't call infrastructure directly
- Services coordinate multiple infrastructure components
- Services handle business workflows
- Easier to test services than CLI commands

**Result**: Clean separation between user interface (CLI) and business logic (services)

---

## Success Criteria Comparison

### Phase 1 Success Criteria
✅ CLI runs and shows help
✅ Config loads from TOML files
✅ Logging works
✅ Tests run and pass
✅ No Bash dependencies
✅ Maps merged

### Phase 2 Success Criteria
✅ Domain models complete
✅ Repositories implemented (minimal)
✅ Extraction wrappers working
✅ MediaWiki client functional
✅ Template parser working
✅ Sheets publisher complete
⚠️ CLI commands stubbed (deferred)
⚠️ Service layer stubbed (deferred)

### Phase 3 Success Criteria (Planned)
🎯 All CLI commands work
🎯 Service orchestration complete
🎯 Wiki generation working
🎯 Sheets deployment working
🎯 Integration tests passing
🎯 Documentation updated

---

## File Organization

```
erenshor/
├── src/erenshor/
│   ├── cli/                    # Phase 1 (skeleton) → Phase 3 (implement)
│   │   ├── main.py            # Phase 1
│   │   └── commands/          # Phase 1 (stubs) → Phase 3 (implement)
│   ├── infrastructure/        # Phase 1 (config/logging) → Phase 2 (wrappers/clients)
│   │   ├── config/            # Phase 1
│   │   ├── logging/           # Phase 1
│   │   ├── database/          # Phase 2
│   │   ├── steam/             # Phase 2
│   │   ├── assetripper/       # Phase 2
│   │   ├── unity/             # Phase 2
│   │   ├── wiki/              # Phase 2
│   │   └── publishers/        # Phase 2
│   ├── application/           # Phase 2 (formatters) → Phase 3 (services/generators)
│   │   ├── formatters/        # Phase 2
│   │   ├── services/          # Phase 3 (NEW)
│   │   └── generators/        # Phase 3 (NEW)
│   ├── domain/                # Phase 2
│   │   └── entities/          # Phase 2
│   └── registry/              # Phase 1
├── templates/                 # Phase 3 (NEW)
│   └── wiki/                  # Phase 3
├── tests/
│   ├── unit/                  # Phase 1 + Phase 2
│   ├── integration/           # Phase 3 (NEW)
│   └── regression/            # Phase 3 (NEW)
└── docs/
    ├── guides/                # Phase 3 (NEW)
    └── refactoring-plan/      # All phases
```

---

## Next Phase Preview

### Phase 4: Backlog Items (TBD)
**High Priority**:
1. Cargo integration (6 weeks)
2. Advanced change detection (2 weeks)
3. Diff command (1 week)

**Medium Priority**:
4. Quest/Faction/Zone templates
5. Image upload automation
6. Performance optimization

**Low Priority**:
7. Shell completion scripts
8. Performance metrics
9. VCR.py integration

---

**End of Phase Overview**
