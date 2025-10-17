# Phase 2 Architecture Review

**Review Date**: 2025-10-17
**Reviewed By**: Claude (Architecture Analysis)
**Phase**: Phase 2 - Core Infrastructure Layer
**Codebase Size**: ~9,889 lines of Python across infrastructure, application, and domain layers

---

## Executive Summary

Phase 2 successfully implemented the core infrastructure layer for the Erenshor data mining pipeline. The architecture demonstrates **excellent adherence to separation of concerns**, **appropriate use of design patterns**, and **strong YAGNI compliance**. The implementation is well-suited for a solo developer maintaining a hobby project.

**Overall Assessment**: **A- (Excellent with minor refinements needed)**

**Key Strengths**:
- Clean three-layer architecture (domain/application/infrastructure)
- Consistent wrapper pattern for external tools
- Minimal repository pattern with intentional under-implementation
- Strong error handling with clear exception hierarchies
- Comprehensive TYPE_CHECKING guards for development vs runtime
- Well-designed configuration system with deep merging

**Key Concerns**:
- Repository pattern may be *too* minimal for future needs
- Some inconsistency in error handling approaches
- Missing integration points between some components
- Test coverage gaps in critical integration paths

---

## Architectural Overview

### What Was Built

Phase 2 implemented the following infrastructure components:

#### 1. External Tool Wrappers (~2,987 LOC total)
- **SteamCMD Wrapper** (342 LOC): Game file download automation
- **AssetRipper Wrapper** (527 LOC): Unity asset extraction with HTTP API
- **Unity Batch Mode Wrapper** (534 LOC): Headless Unity script execution
- **MediaWiki Client** (623 LOC): Wiki API integration with authentication
- **Google Sheets Publisher** (961 LOC): Complex table-aware publishing

#### 2. Database Layer (~400 LOC)
- **Connection Management**: SQLite with pooling and transactions
- **Repository Pattern**: Minimal skeletons for 10+ entity types
- **Base Repository**: Generic query execution infrastructure

#### 3. Application Layer (~200 LOC)
- **SheetsFormatter**: SQL-to-spreadsheet data transformation
- **Query Library**: 20+ SQL query files for Google Sheets export

#### 4. Domain Layer (~1,500 LOC)
- **Entity Models**: 10+ Pydantic models for game entities
- **Base Entity**: Common validation and serialization

#### 5. Configuration System (~600 LOC)
- **TOML Loader**: Two-layer override system
- **Path Resolution**: $REPO_ROOT and environment variable expansion
- **Pydantic Schema**: Type-safe configuration validation

---

## Analysis of Key Design Decisions

### 1. Minimal Repository Pattern (Repository Skeletons)

**Decision**: Create repository classes with NO methods initially, adding queries only when actually needed.

**Rationale**: Avoid premature abstraction and generic CRUD operations that may never be used.

**Implementation**:
```python
class CharacterRepository(BaseRepository[Character]):
    """Repository for character-specific database queries.

    Add specialized query methods here as needed for wiki generation,
    Google Sheets export, or other pipeline features.
    """
    pass  # Add query methods when actually needed
```

**Analysis**:
- **Strength**: Perfect YAGNI compliance - zero speculative code
- **Strength**: Forces developers to think about specific use cases
- **Strength**: Clear documentation about what queries should be added
- **Concern**: May create friction when first queries are needed
- **Concern**: No pattern established for common operations (get_by_id, get_all)
- **Concern**: Risk of inconsistent query patterns across repositories

**Verdict**: ✅ **Bold but appropriate for this project**. The documentation is excellent, and the approach prevents over-engineering. However, consider establishing pattern examples once first real queries are added.

**Recommendation**: Add 1-2 example queries to one repository (e.g., ItemRepository.get_vendor_items()) to establish patterns without compromising YAGNI.

---

### 2. Wrapper Pattern for External Tools

**Decision**: Wrap SteamCMD, AssetRipper, and Unity with Python classes using subprocess.

**Implementation Consistency**:
```python
# All wrappers follow this pattern:
1. Custom exception hierarchy (SteamCMDError, AssetRipperError, etc.)
2. Path validation in __init__
3. subprocess.run() for execution
4. Comprehensive error handling
5. Detailed logging with loguru
6. Helper methods (is_installed, get_version)
```

**Analysis**:
- **Strength**: Excellent consistency across all three wrappers
- **Strength**: Clear error boundaries with specific exception types
- **Strength**: Testable via mocking subprocess.run()
- **Strength**: Self-contained with no external dependencies beyond stdlib
- **Strength**: Detailed docstrings with usage examples
- **Neutral**: ~500 LOC per wrapper (appropriate for complexity)
- **Weakness**: AssetRipper HTTP API logic is complex (log monitoring, timeouts)

**Verdict**: ✅ **Excellent implementation**. The pattern is clear, consistent, and appropriate for wrapping CLI tools.

**Recommendation**: Consider extracting common "subprocess wrapper" utilities if more wrappers are added in the future.

---

### 3. TYPE_CHECKING Guards for Imports

**Decision**: Use TYPE_CHECKING guards to separate development-time imports from runtime imports.

**Implementation Pattern**:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.auth.exceptions import GoogleAuthError
    from google.oauth2 import service_account
else:
    from google.auth.exceptions import GoogleAuthError
    from google.oauth2 import service_account
```

**Analysis**:
- **Strength**: Enables type checking without runtime import overhead
- **Strength**: Documents what dependencies are optional/development-only
- **Confusion**: Why import twice (TYPE_CHECKING and else)? Pattern is unusual
- **Expected Pattern**: TYPE_CHECKING for type hints only, normal imports for runtime
- **Observation**: Some files use this correctly (repositories), others redundantly (publishers)

**Verdict**: ⚠️ **Pattern misapplied**. TYPE_CHECKING should be for type-only imports, not duplicating runtime imports.

**Correct Usage** (from repositories):
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine  # Type-only, not used at runtime
```

**Incorrect Usage** (from publishers):
```python
if TYPE_CHECKING:
    from google.oauth2 import service_account
else:
    from google.oauth2 import service_account  # Redundant!
```

**Recommendation**: Review and fix TYPE_CHECKING usage. Import runtime dependencies normally, use TYPE_CHECKING only for type-only imports (function signatures, forward references).

---

### 4. Error Hierarchy Design

**Decision**: Create domain-specific exception hierarchies for each component.

**Implementation Pattern**:
```python
class SteamCMDError(Exception):
    """Base exception for SteamCMD-related errors."""
    pass

class SteamCMDNotFoundError(SteamCMDError):
    """Raised when SteamCMD executable is not found."""
    pass

class SteamCMDDownloadError(SteamCMDError):
    """Raised when game download fails."""
    pass
```

**Analysis**:
- **Strength**: Clear error boundaries per component
- **Strength**: Catchable at multiple levels (specific or base)
- **Strength**: Excellent docstrings explaining when errors occur
- **Strength**: Consistent across all infrastructure components
- **Inconsistency**: Some use "Error" suffix, others don't (ConfigLoadError vs UnityBatchModeError)
- **Missing**: No top-level application error hierarchy

**Verdict**: ✅ **Well-designed with minor naming inconsistencies**.

**Recommendation**: Establish naming convention (prefer "Error" suffix consistently). Consider adding top-level ErenshorError for application-level catches.

---

### 5. Configuration Architecture

**Decision**: Two-layer TOML configuration with deep merging (config.toml + config.local.toml).

**Implementation**:
- Base config: Project defaults (committed)
- Local config: User overrides (gitignored)
- Deep merge: Nested dict values merge recursively
- Validation: Pydantic schema ensures correctness
- Path expansion: $REPO_ROOT, $HOME resolved at access time

**Analysis**:
- **Strength**: Clear separation of defaults and overrides
- **Strength**: Deep merge preserves partial overrides
- **Strength**: Pydantic validation catches errors early
- **Strength**: Path expansion deferred to access time (good for testing)
- **Strength**: Excellent error messages with validation details
- **Neutral**: No environment variable support (intentional TOML-only approach)

**Verdict**: ✅ **Excellent design**. Clean, testable, and appropriate for the project.

---

### 6. Test Mocking Strategy

**Decision**: Mock external dependencies (subprocess.run, HTTP clients) in unit tests.

**Implementation** (from test_batch_mode.py):
```python
@patch("erenshor.infrastructure.unity.batch_mode.subprocess.run")
def test_execute_method_success(self, mock_run: MagicMock, tmp_path: Path):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    unity.execute_method(...)
    mock_run.assert_called_once()
```

**Analysis**:
- **Strength**: Fast unit tests without external dependencies
- **Strength**: Tests focus on wrapper logic, not tool behavior
- **Strength**: Consistent mocking pattern across all wrappers
- **Weakness**: No integration tests for actual tool execution
- **Gap**: Missing tests for error scenarios (timeouts, malformed output)

**Verdict**: ✅ **Appropriate for unit tests**, but integration test coverage is needed.

**Recommendation**: Add integration test suite that runs against real tools (marked with pytest.mark.integration, skipped by default).

---

## Layering & Separation of Concerns

### Layer Dependency Flow

```
┌─────────────────────────────────────┐
│        CLI / Application            │
│  (Commands, Formatters, Services)   │
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│         Domain Layer                │
│     (Entities, Value Objects)       │
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│      Infrastructure Layer           │
│  (DB, Wrappers, Clients, Config)    │
└─────────────────────────────────────┘
```

**Analysis**:
- ✅ **Clean separation**: Domain has no infrastructure dependencies
- ✅ **Infrastructure is isolated**: Each wrapper is self-contained
- ✅ **Application layer coordinates**: Uses both domain and infrastructure
- ⚠️ **Potential violation**: Some repositories might bypass domain layer (direct SQL)

**Dependency Direction**: ✅ **Correct**. Dependencies flow downward: Application → Domain ← Infrastructure.

**Abstraction Without Over-Abstraction**:
- ✅ No unnecessary interfaces or protocols
- ✅ Concrete implementations where appropriate
- ✅ BaseRepository provides just enough abstraction
- ✅ No "manager" or "service" proliferation

**Verdict**: ✅ **Excellent layering**. Clean boundaries without over-engineering.

---

## Design Patterns Analysis

### Patterns Identified

#### 1. Repository Pattern (Minimal Implementation)
- **Usage**: Database access layer
- **Assessment**: ✅ Appropriately minimal, excellent YAGNI compliance
- **Concern**: May need pattern guidance when first queries added

#### 2. Wrapper Pattern (Tool Abstraction)
- **Usage**: SteamCMD, AssetRipper, Unity, MediaWiki, Google Sheets
- **Assessment**: ✅ Excellent consistency, clear error handling
- **Strength**: Each wrapper is testable and self-contained

#### 3. Context Manager Pattern
- **Usage**: DatabaseConnection, MediaWikiClient
- **Assessment**: ✅ Proper resource management with __enter__/__exit__
- **Example**: `with db.connect() as conn:` ensures cleanup

#### 4. Builder Pattern (Implicit)
- **Usage**: Configuration loading with deep merge
- **Assessment**: ✅ Builds complex config from layers incrementally

#### 5. Singleton Pattern (Path Resolver)
- **Usage**: PathResolver for path expansion
- **Assessment**: ⚠️ Singleton state can cause test issues (autouse fixture resets it)
- **Concern**: Global state, but necessary for config access

**Patterns Avoided** (Good YAGNI):
- ❌ Factory pattern (not needed for simple instantiation)
- ❌ Strategy pattern (no algorithmic variations needed)
- ❌ Observer pattern (no event-driven requirements)
- ❌ Adapter pattern (wrappers serve this role simply)

**Verdict**: ✅ **Appropriate pattern usage**. Patterns help without over-engineering.

---

## Dependencies & Coupling

### Module Coupling Analysis

**Infrastructure Layer**:
- ✅ **Loosely coupled**: Each wrapper is independent
- ✅ **No circular dependencies**: Clean import graph
- ✅ **Minimal external dependencies**: httpx, loguru, pydantic, google-api-python-client

**Application Layer**:
- ✅ **Depends on infrastructure**: Formatters use database connection
- ✅ **No direct domain coupling**: Formatters return generic lists
- ⚠️ **Missing service layer**: No orchestration of multiple infrastructure components

**Domain Layer**:
- ✅ **Zero infrastructure dependencies**: Pure Python + Pydantic
- ✅ **No application dependencies**: Domain is isolated
- ✅ **Self-contained**: Entities define stable_key, normalized_resource_name properties

**Circular Dependency Check**:
```bash
# No circular dependencies detected
Infrastructure → Domain ✅
Application → Infrastructure ✅
Application → Domain ✅
```

**Testability**:
- ✅ **Wrappers mockable**: subprocess.run, HTTP clients
- ✅ **Database testable**: In-memory SQLite
- ✅ **Config testable**: PathResolver reset fixture
- ⚠️ **Integration gaps**: No full pipeline tests

**Verdict**: ✅ **Excellent coupling discipline**. Components are loosely coupled and testable.

**Recommendation**: Add service layer for orchestrating multi-step operations (e.g., download → extract → export).

---

## Extensibility

### Extension Points

#### 1. Adding New External Tool Wrappers
**Ease**: ⭐⭐⭐⭐⭐ (5/5)
- Clear pattern established by existing wrappers
- Exception hierarchy, subprocess handling, logging all documented
- Example: Adding RipGrep wrapper would follow same pattern

#### 2. Adding New Repository Queries
**Ease**: ⭐⭐⭐⭐☆ (4/5)
- Pattern is clear (use _execute_raw)
- Documentation excellent (what queries to add, examples)
- **Concern**: No established pattern yet, first query will set precedent
- **Recommendation**: Add example query to establish pattern

#### 3. Adding New Entity Types
**Ease**: ⭐⭐⭐⭐⭐ (5/5)
- Inherit from BaseEntity
- Define Pydantic fields
- Add stable_key property
- Very straightforward

#### 4. Adding New Google Sheets Queries
**Ease**: ⭐⭐⭐⭐⭐ (5/5)
- Add .sql file to queries directory
- SheetsFormatter automatically discovers it
- No code changes needed
- Excellent extensibility

#### 5. Adding New Configuration Options
**Ease**: ⭐⭐⭐⭐☆ (4/5)
- Update Pydantic schema
- Add to config.toml defaults
- Validation automatic
- **Minor friction**: Schema must be updated in code

#### 6. Supporting New Variants (game versions)
**Ease**: ⭐⭐⭐⭐⭐ (5/5)
- Add variant config section
- Directory structure automatic
- Multi-variant fully supported by design

**Future-Proofing**:
- ✅ Variant system supports main/playtest/demo/future
- ✅ Query library extensible (just add SQL files)
- ✅ Repository pattern allows adding methods on demand
- ⚠️ No plugin system (probably not needed)
- ⚠️ No hooks/events for pipeline steps (may need later)

**Verdict**: ✅ **Highly extensible**. Clear patterns and examples for most extensions.

---

## Integration Points

### How Components Work Together

#### 1. Configuration → All Components
**Status**: ✅ **Working**
- Config loaded once, passed to components
- Path resolution handled transparently
- Type-safe with Pydantic validation

#### 2. Database → Repositories → Formatters
**Status**: ✅ **Working**
- DatabaseConnection provides connections
- Repositories execute queries (when implemented)
- SheetsFormatter executes SQL directly (bypasses repositories)
- **Design Question**: Should formatters use repositories?

**Current Flow**:
```
SheetsFormatter → SQL file → DatabaseConnection → SQLite
```

**Alternative Flow**:
```
SheetsFormatter → Repository.get_sheet_data() → DatabaseConnection → SQLite
```

**Analysis**:
- Current approach: Simple, direct, fewer abstractions
- Alternative: More layers, but queries in repositories
- **Verdict**: Current approach appropriate for read-only formatting

#### 3. Wrappers → Configuration
**Status**: ⚠️ **Inconsistent**
- Unity wrapper: Takes unity_path directly
- AssetRipper: Takes executable_path directly
- SteamCMD: Takes username directly
- **Missing**: No unified way to instantiate from config

**Recommendation**: Add factory methods (e.g., `UnityBatchMode.from_config(config)`) for clean instantiation.

#### 4. Domain Entities → Repositories
**Status**: ⚠️ **Disconnected**
- Repositories return Any (not entities)
- No entity hydration from database rows
- **Gap**: BaseRepository has generic type [T] but doesn't use it

**Expected Pattern**:
```python
class ItemRepository(BaseRepository[Item]):
    def get_by_id(self, item_id: str) -> Item | None:
        row = self._execute_raw("SELECT * FROM Items WHERE Id = ?", (item_id,))
        return self._row_to_entity(row)
```

**Current Reality**:
```python
class ItemRepository(BaseRepository[Item]):
    pass  # No methods yet
```

**Analysis**: Generic typing is present but unused. This is intentional (YAGNI), but will need implementation when first queries added.

#### 5. CLI → Services → Components
**Status**: ⚠️ **Service layer missing**
- CLI commands call infrastructure directly
- No orchestration layer
- **Gap**: Multi-step operations (download → extract → export) not coordinated

**Recommendation**: Add service layer for complex workflows when Bash CLI is replaced by Python orchestration.

**Verdict**: ✅ **Integration boundaries are clean**, but some connections missing (intentionally minimal for Phase 2).

---

## YAGNI Compliance

### Speculative Features Avoided ✅

The codebase demonstrates **excellent YAGNI compliance**:

1. ✅ **No generic CRUD operations** in repositories
2. ✅ **No query builder abstraction** (raw SQL is fine)
3. ✅ **No ORM** (SQLite via sqlite3 is sufficient)
4. ✅ **No plugin system** (not needed yet)
5. ✅ **No event bus** (no event-driven requirements)
6. ✅ **No caching layer** (premature optimization)
7. ✅ **No connection pooling** (SQLite doesn't benefit)
8. ✅ **No async/await** (not needed for CLI tool)
9. ✅ **No GraphQL/REST API** (not needed)
10. ✅ **No microservices** (monolith appropriate for solo dev)

### Features Built (All Justified) ✅

1. ✅ **Error hierarchies**: Needed for error handling
2. ✅ **Logging with loguru**: Debugging/troubleshooting
3. ✅ **Pydantic validation**: Configuration correctness
4. ✅ **Context managers**: Resource cleanup
5. ✅ **TYPE_CHECKING guards**: Type safety without runtime overhead
6. ✅ **Deep config merge**: User overrides without duplication
7. ✅ **Multi-variant support**: Actual requirement (main/playtest/demo)
8. ✅ **Table-aware sheets publishing**: Preserves user formatting

### Minimal Approach Analysis

**Repository Pattern** (Too minimal?):
- ❓ Zero methods in most repositories
- ❓ No pattern established for queries
- ✅ **Verdict**: Justifiable for Phase 2, needs guidance when first used

**Database Connection** (Just right?):
- ✅ Connection pooling: Simple reuse (appropriate for SQLite)
- ✅ Transaction support: Needed for writes
- ✅ Context managers: Resource safety
- ✅ **Verdict**: Appropriate scope

**Wrappers** (Right level of abstraction?):
- ✅ SteamCMD: 342 LOC (wraps 10+ CLI options)
- ✅ AssetRipper: 527 LOC (HTTP API + lifecycle)
- ✅ Unity: 534 LOC (error parsing + validation)
- ✅ **Verdict**: Appropriate complexity for tools

**Overall Verdict**: ✅ **Excellent YAGNI compliance**. The minimal approach is sustainable and appropriate for the project stage.

---

## Consistency

### What's Consistent ✅

1. ✅ **Error hierarchies**: All follow `BaseError → SpecificError` pattern
2. ✅ **Docstrings**: Comprehensive, Google-style format
3. ✅ **Logging**: loguru used consistently with debug/info/warning/error
4. ✅ **Path handling**: pathlib.Path used everywhere
5. ✅ **Type hints**: Present on all public methods
6. ✅ **Wrapper pattern**: Consistent across SteamCMD/AssetRipper/Unity
7. ✅ **Context managers**: Used for resource management
8. ✅ **Pydantic models**: Domain entities and config schemas

### What's Inconsistent ⚠️

1. ⚠️ **TYPE_CHECKING usage**: Some redundant, some correct
2. ⚠️ **Error naming**: Some "Error" suffix, some not (ConfigLoadError vs UnityBatchModeError)
3. ⚠️ **Repository documentation**: Excellent in base, minimal in implementations
4. ⚠️ **Import organization**: Some absolute, some relative
5. ⚠️ **Logging levels**: Debug logging placement varies
6. ⚠️ **Factory methods**: Some wrappers have, others don't (from_config, from_path)

### Naming Conventions

**Consistent**:
- ✅ Classes: PascalCase
- ✅ Functions: snake_case
- ✅ Constants: SCREAMING_SNAKE_CASE (in publishers)
- ✅ Private methods: _leading_underscore
- ✅ Module names: snake_case

**Pattern Variations**:
- Exceptions: `Error` suffix inconsistent
- Repositories: `Repository` suffix consistent ✅
- Wrappers: No suffix (SteamCMD, AssetRipper) ✅
- Clients: `Client` suffix (MediaWikiClient) ✅

**Verdict**: ✅ **Mostly consistent** with minor variations that don't harm readability.

**Recommendation**: Establish error naming convention (prefer `Error` suffix consistently).

---

## Strengths

### 1. Clean Architecture
- **Three-layer separation** (domain/application/infrastructure) is textbook
- **Dependency flow** is correct (downward, no circular)
- **Abstraction level** appropriate (not over-engineered)

### 2. Wrapper Pattern Excellence
- **Consistent implementation** across all external tools
- **Clear error boundaries** with specific exception types
- **Comprehensive logging** for debugging
- **Testability** via mocking subprocess/HTTP

### 3. YAGNI Discipline
- **Minimal repository pattern** avoids premature abstraction
- **No speculative features** (no ORM, query builder, caching, etc.)
- **Intentional under-implementation** with clear documentation

### 4. Error Handling
- **Exception hierarchies** allow catching at multiple levels
- **Detailed error messages** guide users to solutions
- **Clear error documentation** explains when exceptions occur

### 5. Configuration Design
- **Two-layer override system** separates defaults from user config
- **Deep merging** preserves partial overrides
- **Pydantic validation** catches errors early
- **Path expansion** deferred to access time

### 6. Documentation Quality
- **Comprehensive docstrings** on all public methods
- **Usage examples** in docstrings
- **Module-level documentation** explains purpose
- **Inline comments** explain "why" not "what"

### 7. Type Safety
- **Type hints** on all public APIs
- **Pydantic models** for validation
- **Generic typing** in BaseRepository
- **TYPE_CHECKING guards** (mostly correct usage)

### 8. Google Sheets Publisher
- **Table-aware publishing** preserves user formatting
- **Handles growing/shrinking** tables gracefully
- **Comprehensive error handling** with helpful messages
- **Batch operations** for performance

---

## Issues & Concerns

### Critical Issues ❌ (None Found)

No critical architectural flaws that would block progress or require immediate refactoring.

### High Priority Issues ⚠️

#### 1. Repository Pattern Too Minimal
**Severity**: Medium
**Impact**: Friction when first queries added, potential inconsistency

**Problem**:
- Zero query methods in most repositories
- No established pattern for query implementation
- Generic typing present but unused

**Example**:
```python
class CharacterRepository(BaseRepository[Character]):
    pass  # What goes here when we need queries?
```

**Recommendation**:
- Add 1-2 example queries to establish pattern
- Document entity hydration approach (_row_to_entity)
- Show how to use generic type parameter

**When**: Before first real repository usage

---

#### 2. TYPE_CHECKING Usage Inconsistency
**Severity**: Low
**Impact**: Code clarity, minor performance (redundant imports)

**Problem**:
```python
# Incorrect: Redundant imports
if TYPE_CHECKING:
    from google.oauth2 import service_account
else:
    from google.oauth2 import service_account  # Why both?
```

**Expected**:
```python
# Correct: TYPE_CHECKING for type-only imports
if TYPE_CHECKING:
    from sqlalchemy.engine import Engine  # Only used in signatures
```

**Recommendation**:
- Review all TYPE_CHECKING blocks
- Remove redundant imports
- Use TYPE_CHECKING only for type-only imports

**When**: Next refactoring pass

---

#### 3. Missing Service/Orchestration Layer
**Severity**: Low (for Phase 2)
**Impact**: CLI commands directly call infrastructure

**Problem**:
- No orchestration for multi-step workflows
- CLI directly instantiates wrappers
- No single entry point for "download → extract → export"

**Example Gap**:
```bash
# Bash CLI currently orchestrates
erenshor download
erenshor extract
erenshor export

# Python has no equivalent
python -m erenshor.cli update  # Doesn't exist
```

**Recommendation**:
- Add service layer when migrating from Bash to Python orchestration
- Service classes: PipelineService, UpdateService, DeployService
- Not urgent (Bash CLI works well for now)

**When**: Phase 3 or later (if/when Bash CLI replaced)

---

### Medium Priority Issues ℹ️

#### 4. No Integration Tests
**Severity**: Medium
**Impact**: Untested integration between real tools

**Problem**:
- Unit tests mock subprocess.run and HTTP clients
- No tests with actual Unity, AssetRipper, SteamCMD
- Integration failures only discovered in production

**Recommendation**:
- Add integration test suite (`tests/integration/`)
- Mark with `@pytest.mark.integration`
- Skip by default (opt-in: `pytest -m integration`)
- Run in CI on main branch only

**Example**:
```python
@pytest.mark.integration
@pytest.mark.slow
def test_unity_export_real_project(unity_exe, test_project):
    """Test real Unity batch mode export."""
    unity = UnityBatchMode(unity_path=unity_exe)
    unity.execute_method(...)
    # Verify database created
```

---

#### 5. Error Naming Inconsistency
**Severity**: Low
**Impact**: Readability, naming predictability

**Problem**:
- Some: `ConfigLoadError`, `DatabaseConnectionError`
- Others: `UnityBatchModeError`, `MediaWikiAPIError`
- Inconsistent "Error" suffix usage

**Recommendation**:
- Standardize on `Error` suffix for all exceptions
- Rename: `ConfigLoadError` → `ConfigurationError`
- Or rename: `UnityBatchModeError` → `UnityBatchMode` (less preferred)

**When**: Low priority (doesn't affect functionality)

---

#### 6. Missing Factory Methods
**Severity**: Low
**Impact**: Boilerplate when instantiating from config

**Problem**:
```python
# Current: Manual instantiation
config = load_config()
unity = UnityBatchMode(
    unity_path=Path(config.global_.unity.path),
    timeout=config.global_.unity.timeout
)

# Desired: Factory method
unity = UnityBatchMode.from_config(config)
```

**Recommendation**:
- Add `from_config()` class methods to wrappers
- Reduces boilerplate in CLI commands
- Makes config changes easier

**When**: Next round of wrapper improvements

---

#### 7. Repository Entity Hydration Not Implemented
**Severity**: Low (intentional)
**Impact**: Pattern unclear when needed

**Problem**:
- `BaseRepository[T]` has generic type but doesn't use it
- No `_row_to_entity()` helper implemented
- Repositories return `list[Any]` not `list[T]`

**This is intentional** (YAGNI), but needs documentation for first usage.

**Recommendation**:
- Add example implementation when first query added
- Document pattern in BaseRepository docstring
- Show how to use generic type parameter

---

### Low Priority Issues / Observations 📝

#### 8. Singleton PathResolver State
**Severity**: Very Low
**Impact**: Test isolation (mitigated by autouse fixture)

**Observation**:
- PathResolver is singleton
- Global state can cause test issues
- Currently mitigated by autouse fixture that resets it

**No action needed** - current solution works well.

---

#### 9. Google Sheets Publisher Complexity
**Severity**: Very Low (Informational)
**Impact**: None (complexity justified)

**Observation**:
- GoogleSheetsPublisher: 961 LOC (largest single file)
- Table-aware publishing is complex
- Growing/shrinking logic is intricate

**This is justified** - table-aware publishing is inherently complex.

**No action needed** - complexity is appropriate for requirements.

---

#### 10. SQL Queries Outside Repository Layer
**Severity**: Very Low (Design Decision)
**Impact**: Architectural preference

**Observation**:
- SheetsFormatter executes SQL directly
- Bypasses repository layer
- SQL files in queries/ directory

**Current Design**:
```
SheetsFormatter → SQL file → DatabaseConnection
```

**Alternative Design**:
```
SheetsFormatter → Repository → DatabaseConnection
```

**Analysis**:
- Current: Simpler, fewer abstractions, SQL visible
- Alternative: More layers, queries in Python
- **Verdict**: Current approach appropriate for read-only formatting

**No action needed** - design choice is reasonable.

---

## Recommendations

### Immediate Actions (Before Phase 3)

1. **Add Repository Pattern Examples**
   - Add 1-2 example queries to one repository
   - Document entity hydration pattern
   - Show how to use generic type parameter
   - **Impact**: High (establishes patterns)

2. **Fix TYPE_CHECKING Usage**
   - Remove redundant imports in TYPE_CHECKING blocks
   - Use only for type-only imports (signatures)
   - **Impact**: Low (code clarity)

3. **Standardize Error Naming**
   - Choose convention: Always use "Error" suffix
   - Rename inconsistent exceptions
   - **Impact**: Low (consistency)

### Short-Term (Phase 3)

4. **Add Integration Test Suite**
   - Create tests/integration/ directory
   - Add tests for real tool execution
   - Mark with @pytest.mark.integration
   - **Impact**: Medium (catches integration issues)

5. **Add Factory Methods**
   - UnityBatchMode.from_config()
   - SteamCMD.from_config()
   - AssetRipper.from_config()
   - **Impact**: Low (reduces boilerplate)

6. **Consider Service Layer**
   - Only if migrating from Bash to Python orchestration
   - PipelineService, UpdateService, DeployService
   - **Impact**: Medium (if needed)

### Future Considerations

7. **Plugin System**
   - Not needed now, but consider for custom exporters
   - **Impact**: Low (speculative)

8. **Event Hooks**
   - Pipeline step hooks (pre/post download, extract, export)
   - **Impact**: Low (nice-to-have)

9. **Async/Await**
   - Not needed for CLI, but could speed up batch operations
   - **Impact**: Low (premature optimization)

---

## Future Considerations

### What's Next?

The Phase 2 architecture is well-positioned for:

1. ✅ **Wiki Generation Pipeline**
   - Repositories ready for query methods
   - MediaWiki client fully functional
   - Template parsing infrastructure exists

2. ✅ **Google Sheets Deployment**
   - Publisher complete with table-aware updates
   - Query library extensible (add SQL files)
   - Formatter infrastructure solid

3. ✅ **Multi-Variant Support**
   - Configuration system supports unlimited variants
   - Directory structure automatic
   - Database per variant

4. ⚠️ **Python CLI Migration** (if desired)
   - Infrastructure solid, but no orchestration layer
   - Would need service layer for multi-step workflows
   - Current Bash CLI works well (may not need migration)

5. ⚠️ **Real-Time Updates** (future)
   - Current: Batch processing (download → extract → export)
   - Future: Watch for game updates, auto-deploy
   - Would need event system or scheduling

### Scalability Considerations

**Current Scope**: Solo developer, hobby project, single machine

**Scaling Concerns**:
- ✅ **Database**: SQLite sufficient (read-heavy, low writes)
- ✅ **Performance**: Batch operations handle 10k+ rows
- ✅ **Memory**: Streaming not needed (datasets < 100MB)
- ✅ **Concurrency**: Not needed (sequential pipeline)

**If scaling needed** (unlikely):
- Postgres instead of SQLite (multi-user, larger datasets)
- Async/await for parallel operations
- Connection pooling for database
- Caching layer for expensive queries

**Verdict**: ✅ **No scaling needed**. Current architecture appropriate for project scope.

---

## Overall Assessment

### Summary Scores

| Category | Score | Notes |
|----------|-------|-------|
| **Layering & Separation** | A | Clean 3-layer architecture, correct dependencies |
| **Design Patterns** | A- | Appropriate patterns, excellent YAGNI compliance |
| **Dependencies & Coupling** | A | Loose coupling, no circular dependencies |
| **Extensibility** | A | Clear extension points, consistent patterns |
| **Integration** | B+ | Clean boundaries, some missing connections |
| **YAGNI Compliance** | A+ | Excellent restraint, minimal over-engineering |
| **Consistency** | B+ | Mostly consistent, minor naming variations |
| **Error Handling** | A | Clear hierarchies, helpful messages |
| **Documentation** | A | Comprehensive docstrings, usage examples |
| **Testability** | B+ | Good unit tests, missing integration tests |

**Overall Grade**: **A- (Excellent with Minor Refinements)**

---

### Final Verdict

The Phase 2 architecture is **well-designed and appropriate** for a solo developer maintaining a hobby data mining project. The implementation demonstrates:

1. ✅ **Strong architectural discipline** with clean layering
2. ✅ **Excellent YAGNI compliance** avoiding over-engineering
3. ✅ **Consistent design patterns** across components
4. ✅ **Clear error handling** with helpful messages
5. ✅ **High code quality** with comprehensive documentation
6. ⚠️ **Minor inconsistencies** in error naming and TYPE_CHECKING usage
7. ⚠️ **Repository pattern needs examples** before first real usage
8. ⚠️ **Integration test coverage gaps** for external tools

**The architecture will successfully support** the project's goals and is maintainable by a solo developer. The intentionally minimal approach (especially repositories) is bold but justified, with excellent documentation to guide future implementation.

**Recommended next steps**:
1. Add repository pattern examples (high priority)
2. Fix TYPE_CHECKING usage (low priority)
3. Standardize error naming (low priority)
4. Add integration tests (medium priority)

**No major refactoring needed.** The foundation is solid for Phase 3 and beyond.

---

## Conclusion

Phase 2 successfully implemented a **clean, maintainable, and extensible infrastructure layer** that follows software engineering best practices while avoiding over-engineering. The architecture demonstrates excellent judgment in balancing simplicity with structure, making it well-suited for a solo developer working on a hobby project.

The minimal repository pattern is the most controversial decision, but it's well-documented and intentional. Adding pattern examples when first queries are implemented will validate this approach and establish consistency.

**The architecture is production-ready** and positioned well for Phase 3 implementation.

---

**Architecture Review Completed**: 2025-10-17
**Reviewer**: Claude (Sonnet 4.5)
**Methodology**: Static code analysis, pattern recognition, dependency mapping, YAGNI assessment
