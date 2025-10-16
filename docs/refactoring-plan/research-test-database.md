# Test Database Strategy Research

## Executive Summary

For the Erenshor project, a **hybrid approach** is recommended:
- **Unit tests**: Continue using in-memory SQLite with programmatic fixtures (current approach works well)
- **Integration tests**: Use a minimal SQL fixture file (already implemented at 28KB)
- **Full data tests**: Copy production database when needed for specific edge cases

**Verdict**: The current implementation is already following best practices. The 28KB SQL fixture is the sweet spot for this project.

---

## Best Practices Summary

### Industry Standards for Python/SQLite Testing

**1. Test Pyramid Principle**
- Unit tests (70%): In-memory database with minimal data
- Integration tests (20%): File-based SQLite with representative data
- End-to-end tests (10%): Production-like database copy

**2. Fast Feedback Loop**
- Tests should run in < 5 seconds for rapid iteration
- In-memory SQLite is 10-100x faster than disk-based
- Session-scoped fixtures amortize setup cost

**3. Test Data Independence**
- Each test should be isolated and reproducible
- Avoid shared state between tests
- Prefer factories over large static datasets

**4. Production Parity vs Speed Trade-off**
- Unit tests: Speed > Parity (in-memory is fine)
- Integration tests: Balance both (small file-based DB)
- Acceptance tests: Parity > Speed (real DB copy)

**5. Version Control Strategy**
- Small fixtures (<100KB): Commit directly to git
- Medium fixtures (100KB-10MB): Use git-lfs or separate repo
- Large databases (>10MB): Generate on-demand, never commit

### Factory Pattern vs Static Fixtures

**Factory Pattern (factory_boy, pytest-factory)**
- Best for: Unit tests with varying data permutations
- Pros: Flexible, expressive, reduces duplication
- Cons: Requires maintenance, can drift from reality

**Static Fixtures (SQL dumps)**
- Best for: Integration tests with complex relationships
- Pros: Represents real data structure, easier to reason about
- Cons: Can become stale, requires regeneration

### Git-LFS Considerations

**When to use Git-LFS:**
- Files > 100KB that change frequently
- Binary files (images, compiled assets)
- Multiple large database snapshots

**When NOT to use Git-LFS:**
- Text files < 100KB (SQL fixtures)
- Files that rarely change
- Single developer projects (minimal benefit)

**Git-LFS limitations:**
- GitHub: 1GB free storage, then $5/month per 50GB
- No fine-grained diffs (treats as binary)
- Cannot revert to previous versions easily
- Additional CI/CD setup complexity

---

## Approach Comparison

| Approach | Pros | Cons | Maintenance | Fit for Project |
|----------|------|------|-------------|-----------------|
| **Option A: Copy Production DB** | Real data, comprehensive coverage, catches edge cases | Large file (5.5MB), slow tests, storage challenges | Low (automated copy script) | **Good for occasional full tests** |
| **Option B: Fixture Generation (factory_boy)** | Flexible, programmatic, no storage cost, fast | Manual setup, can drift from reality, complex relationships hard to model | High (must update with schema changes) | **Poor - too much maintenance** |
| **Option C: In-Memory SQLite** | Extremely fast, isolated, no cleanup needed | Limited data, not comprehensive | Medium (programmatic setup) | **Excellent for unit tests (current)** |
| **Option D: Minimal SQL Fixture** | Representative data, fast enough, easy to understand, committed to git | Requires regeneration if schema changes, not comprehensive | Medium (regenerate when schema changes) | **Excellent for integration tests (current)** |
| **Option E: Hybrid (C + D + A)** | Best of all worlds, right tool for right job | Slightly more complex setup | Medium (but distributed across strategies) | **RECOMMENDED - already implemented** |

---

## Current Implementation Analysis

### Strengths of Current Approach

Your test infrastructure at `/Users/joaichberger/Projects/Erenshor/tests/conftest.py` already implements a **well-designed hybrid strategy**:

1. **Minimal SQL Fixture (28KB)** - `/Users/joaichberger/Projects/Erenshor/tests/fixtures/test_erenshor.sql`
   - 20 items, 10 characters, 11 abilities, 3 fishing zones
   - Covers all entity types with representative relationships
   - Session-scoped fixture (created once per test run)
   - Fast enough for integration tests

2. **Unit Tests with In-Memory DB** - `/Users/joaichberger/Projects/Erenshor/tests/unit/test_item_obtainability.py`
   - Programmatic setup via `create_engine("sqlite:///:memory:")`
   - Each test creates exactly the data it needs
   - Tests complete in milliseconds

3. **Integration Tests with Real Database** - `/Users/joaichberger/Projects/Erenshor/tests/integration/test_item_obtainability_real_db.py`
   - Uses session-scoped test database fixture
   - Tests work with realistic data relationships
   - Graceful handling when test data doesn't have specific cases

### What's Working Well

- **28KB SQL fixture** is the perfect size (small enough for git, large enough for testing)
- **Session-scoped engine** reduces test execution time
- **Temporary directory cleanup** prevents test pollution
- **Programmatic unit tests** provide fast feedback
- **Integration tests** verify real-world behavior

### Gap: Production Database Testing

**When you need the full production database (5.5MB):**

Currently there's no mechanism to test against the full production database. This would be valuable for:
- Validating complex queries across 10,000+ entities
- Catching edge cases not in minimal fixture
- Performance testing with realistic data volumes
- Regression testing of data transformations

**Recommendation**: Add a third test category for production-data tests.

---

## Recommended Approach

### Strategy: Tri-Level Testing

```
Unit Tests (70%)              Integration Tests (20%)       Production Tests (10%)
┌─────────────────┐          ┌──────────────────────┐     ┌─────────────────────┐
│ In-Memory SQLite│          │ Minimal SQL Fixture  │     │ Production DB Copy  │
│ Programmatic    │          │ (28KB, committed)    │     │ (5.5MB, generated)  │
│ Fast (<100ms)   │  →       │ Representative       │  →  │ Comprehensive       │
│ Isolated        │          │ Fast enough          │     │ Occasional          │
└─────────────────┘          └──────────────────────┘     └─────────────────────┘
```

**Keep existing implementation** for unit and integration tests. Add production database testing as follows.

---

## Implementation Guide

### 1. Add Production Database Test Support

Create a new pytest marker and fixture for full database tests:

**File: `/Users/joaichberger/Projects/Erenshor/tests/conftest.py`** (add to existing file)

```python
import os
import shutil
from pathlib import Path

@pytest.fixture(scope="session")
def production_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path | None:
    """Copy production database for comprehensive testing.

    This fixture is only used when explicitly requested with @pytest.mark.production.
    The database is copied from the production location and is session-scoped
    to avoid recreating it for every test.

    Returns None if production database doesn't exist (tests will be skipped).
    """
    # Path to production database
    repo_root = Path(__file__).parent.parent
    prod_db_path = repo_root / "variants" / "main" / "erenshor-main.sqlite"

    if not prod_db_path.exists():
        return None

    # Copy to temp directory
    test_db_path = tmp_path_factory.mktemp("prod_db") / "erenshor-production.sqlite"
    shutil.copy2(prod_db_path, test_db_path)

    return test_db_path


@pytest.fixture(scope="session")
def production_engine(production_db_path: Path | None) -> Engine | None:
    """Create SQLAlchemy engine for production database copy.

    Returns None if production database doesn't exist.
    """
    if production_db_path is None:
        return None

    engine = create_engine(f"sqlite:///{production_db_path}")
    yield engine
    engine.dispose()
```

**File: `/Users/joaichberger/Projects/Erenshor/pyproject.toml`** (update markers)

```toml
[tool.pytest.ini_options]
markers = [
    "integration: integration tests with real database and file I/O",
    "slow: tests that take more than a few seconds",
    "production: tests that require full production database (skipped if not available)",
]
```

### 2. Create Production Database Tests

**File: `/Users/joaichberger/Projects/Erenshor/tests/integration/test_production_data.py`** (new file)

```python
"""Production database tests - comprehensive validation with real data.

These tests use a copy of the production database (5.5MB) to validate:
- Complex queries across all entities
- Edge cases not covered in minimal fixtures
- Performance with realistic data volumes

Tests are marked with @pytest.mark.production and skipped if database unavailable.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from erenshor.domain.services import is_item_obtainable


@pytest.mark.production
def test_all_spell_scrolls_obtainability(production_engine: Engine | None) -> None:
    """Validate obtainability logic for all spell scrolls in production database.

    This test catches edge cases not present in the minimal test fixture.
    """
    if production_engine is None:
        pytest.skip("Production database not available")

    with production_engine.connect() as conn:
        spell_scrolls = conn.execute(
            text(
                "SELECT Id, ItemName FROM Items "
                "WHERE TeachSpell IS NOT NULL AND TeachSpell <> ''"
            )
        ).fetchall()

    # Track results for debugging
    obtainable = []
    unobtainable = []

    for item_id, item_name in spell_scrolls:
        if is_item_obtainable(production_engine, item_id, item_name):
            obtainable.append(item_name)
        else:
            unobtainable.append(item_name)

    # Log results for visibility
    print(f"\nObtainable spell scrolls: {len(obtainable)}/{len(spell_scrolls)}")
    if unobtainable:
        print(f"Unobtainable scrolls ({len(unobtainable)}):")
        for name in unobtainable[:10]:  # Show first 10
            print(f"  - {name}")

    # All scrolls should be classified
    assert len(obtainable) + len(unobtainable) == len(spell_scrolls)


@pytest.mark.production
@pytest.mark.slow
def test_database_statistics(production_engine: Engine | None) -> None:
    """Validate production database has expected data volumes."""
    if production_engine is None:
        pytest.skip("Production database not available")

    with production_engine.connect() as conn:
        # Get table counts
        tables = {
            "Items": conn.execute(text("SELECT COUNT(*) FROM Items")).scalar(),
            "Characters": conn.execute(text("SELECT COUNT(*) FROM Characters")).scalar(),
            "Spells": conn.execute(text("SELECT COUNT(*) FROM Spells")).scalar(),
            "Skills": conn.execute(text("SELECT COUNT(*) FROM Skills")).scalar(),
            "LootDrops": conn.execute(text("SELECT COUNT(*) FROM LootDrops")).scalar(),
        }

    print("\nProduction database statistics:")
    for table, count in tables.items():
        print(f"  {table}: {count}")

    # Sanity checks - adjust based on actual game content
    assert tables["Items"] > 100, "Should have substantial item count"
    assert tables["Characters"] > 50, "Should have many characters"
    assert tables["LootDrops"] > 100, "Should have many loot drops"


@pytest.mark.production
def test_junction_table_integrity(production_engine: Engine | None) -> None:
    """Validate junction tables have valid foreign key relationships."""
    if production_engine is None:
        pytest.skip("Production database not available")

    with production_engine.connect() as conn:
        # Test CharacterVendorItems references valid characters
        orphaned_vendors = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM CharacterVendorItems cvi
                LEFT JOIN Characters c ON cvi.CharacterId = c.Id
                WHERE c.Id IS NULL
                """
            )
        ).scalar()

        assert orphaned_vendors == 0, "All vendor items should reference valid characters"

        # Test LootDrops references valid items
        orphaned_drops = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM LootDrops ld
                LEFT JOIN Items i ON ld.ItemId = i.Id
                WHERE i.Id IS NULL
                """
            )
        ).scalar()

        assert orphaned_drops == 0, "All loot drops should reference valid items"
```

### 3. Run Tests with Different Strategies

```bash
# Fast unit tests only (in-memory)
uv run pytest tests/unit/ -v

# Integration tests with minimal fixture
uv run pytest tests/integration/ -v -m "not production"

# All tests including production database
uv run pytest -v

# Only production database tests
uv run pytest -v -m production

# Skip slow production tests
uv run pytest -v -m "not slow"
```

### 4. CI/CD Integration

**For GitHub Actions / CI:**

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync --dev

      # Fast tests for every commit
      - name: Run unit and integration tests
        run: uv run pytest -v -m "not production"

      # Production tests only on main branch or weekly schedule
      - name: Setup production database
        if: github.ref == 'refs/heads/main'
        run: |
          # Download/generate production database
          # Or use cached artifact

      - name: Run production tests
        if: github.ref == 'refs/heads/main'
        run: uv run pytest -v -m production
```

---

## Storage Strategy

### Current Files (Keep in Git)

```
tests/fixtures/
├── test_erenshor.sql     # 28KB - KEEP in git ✓
├── test_erenshor.sqlite  # 12KB - REMOVE (generated from SQL)
├── test_erenshor.db      # 12KB - REMOVE (duplicate)
└── test.db               # 12KB - REMOVE (duplicate)
```

**Action items:**
1. Delete binary `.sqlite` and `.db` files
2. Update `.gitignore` to exclude `tests/fixtures/*.{sqlite,db}`
3. Generate SQLite files from SQL during test setup

### Production Database (Never Commit)

```
variants/main/erenshor-main.sqlite  # 5.5MB - already in .gitignore ✓
```

**Strategy:** Copy on demand for production tests. Already excluded from git.

### Git-LFS: NOT RECOMMENDED

Reasons to avoid Git-LFS:
1. **Cost**: Project is free, LFS is $5/month after 1GB
2. **Solo dev**: No benefit from LFS's main feature (team collaboration on large files)
3. **Size**: 5.5MB is manageable without LFS
4. **Text format available**: The 28KB SQL fixture is sufficient
5. **Generated artifact**: Database is generated from game files, not source of truth

---

## Maintenance Guidelines

### When to Update Test Fixtures

**Minimal SQL fixture (`test_erenshor.sql`)**:
- Schema changes (new columns, tables, indices)
- New entity types added to game
- Breaking changes to relationships
- Every major game version update

**How to regenerate:**
1. Export fresh data from production database
2. Trim to minimal representative set
3. Validate tests still pass
4. Commit updated SQL file

**Unit test factories**:
- When schema changes affect tested functionality
- When new acquisition methods added
- When edge cases discovered

### Schema Evolution

When Unity export schema changes:

1. **Update SQL fixture first**
   ```bash
   # Export minimal subset from production
   sqlite3 variants/main/erenshor-main.sqlite <<EOF
   .output tests/fixtures/test_erenshor_new.sql
   .dump Items Characters Spells Skills
   -- Add WHERE clauses to limit data
   EOF
   ```

2. **Run tests to identify failures**
   ```bash
   uv run pytest tests/ -v
   ```

3. **Update fixtures incrementally**
   - Fix test_erenshor.sql for integration tests
   - Fix unit test factories as needed

4. **Validate with production database**
   ```bash
   uv run pytest -m production
   ```

---

## Example Code: Complete Setup

### Pytest Configuration

**File: `/Users/joaichberger/Projects/Erenshor/pyproject.toml`**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--strict-markers",
    "--tb=short",
    "--cov=src/erenshor",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-branch",
]
markers = [
    "integration: integration tests with real database and file I/O",
    "slow: tests that take more than a few seconds",
    "production: tests requiring full production database (5.5MB)",
]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning",
]
```

### Fixture Best Practices

**File: `/Users/joaichberger/Projects/Erenshor/tests/conftest.py`** (key patterns)

```python
# Pattern 1: Session-scoped database (amortize setup cost)
@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create once, use for all tests."""
    db_path = tmp_path_factory.mktemp("db") / "test.sqlite"
    # Setup database
    return db_path

# Pattern 2: Function-scoped connection (isolated tests)
@pytest.fixture
def test_connection(test_engine: Engine) -> Generator[Connection, None, None]:
    """Each test gets fresh connection with transaction rollback."""
    with test_engine.connect() as conn:
        trans = conn.begin()
        yield conn
        trans.rollback()  # Undo changes after test

# Pattern 3: Auto-cleanup (no manual teardown)
@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Temporary directory automatically cleaned up."""
    dirpath = Path(tempfile.mkdtemp())
    yield dirpath
    shutil.rmtree(dirpath, ignore_errors=True)

# Pattern 4: Conditional skip (graceful degradation)
@pytest.fixture
def production_db(prod_db_path: Path | None):
    """Skip tests if production database unavailable."""
    if prod_db_path is None:
        pytest.skip("Production database not available")
    return prod_db_path
```

### Test Organization

```
tests/
├── conftest.py                          # Shared fixtures
├── unit/                                # Fast, isolated tests
│   ├── test_item_obtainability.py      # In-memory database
│   ├── test_junction_enricher.py       # Pure logic tests
│   └── formatters/
│       └── test_sheets_formatter.py    # Mock dependencies
├── integration/                         # Real components
│   ├── test_item_obtainability_real_db.py   # Minimal fixture
│   ├── test_character_updates.py            # Full pipeline
│   └── test_idempotency.py                  # End-to-end
└── production/                          # NEW: Full database tests
    ├── test_comprehensive_obtainability.py  # All items
    ├── test_data_integrity.py               # Validation
    └── test_performance.py                  # Query performance
```

---

## Performance Benchmarks

Expected test execution times on typical development machine:

| Test Type | Count | Database | Time | Why |
|-----------|-------|----------|------|-----|
| Unit tests | ~20 | In-memory | <1s | Minimal data, isolated |
| Integration tests | ~10 | File (28KB) | 2-5s | Session-scoped setup |
| Production tests | ~5 | File (5.5MB) | 5-10s | Larger dataset, complex queries |
| **Total** | **~35** | **Mixed** | **<15s** | **Fast enough for TDD** |

---

## Conclusion

### Current State: Already Excellent

Your test infrastructure is **already following best practices**:
- ✅ Unit tests use in-memory SQLite
- ✅ Integration tests use minimal 28KB SQL fixture
- ✅ Session-scoped fixtures for performance
- ✅ Proper cleanup and isolation
- ✅ Clear test organization

### Recommended Enhancement

Add **production database testing** for comprehensive validation:
- Copy 5.5MB database for occasional full tests
- Mark with `@pytest.mark.production`
- Skip if database unavailable (CI flexibility)
- Run weekly or before releases

### No Git-LFS Needed

- 28KB SQL fixture: Commit directly to git ✓
- 5.5MB production DB: Generate on-demand, exclude from git ✓
- Binary SQLite files: Delete duplicates, generate from SQL ✓

### Maintenance Effort

- **Low**: SQL fixture only needs updates on schema changes
- **Automated**: Production database copied by pytest fixtures
- **Flexible**: Tests gracefully skip when data unavailable

---

## Additional Resources

**Python Testing with Databases:**
- [Pytest with Eric - Database Testing](https://pytest-with-eric.com/database-testing/pytest-sql-database-testing/)
- [SQLModel Testing Guide](https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/)

**Factory Pattern:**
- [pytest-factoryboy Documentation](https://pytest-factoryboy.readthedocs.io/)
- [Factory Boy Guide](https://factoryboy.readthedocs.io/)

**Test Data Management:**
- [Fun with Fixtures for Database Applications](https://medium.com/@geoffreykoh/fun-with-fixtures-for-database-applications-8253eaf1a6d)

**Git-LFS:**
- [Git LFS Tutorial](https://git-lfs.github.com/)
- [GitHub Storage Pricing](https://docs.github.com/en/billing/managing-billing-for-git-large-file-storage)

---

## Decision Matrix

Should you copy the production database for tests?

| If... | Then... |
|-------|---------|
| Testing specific edge cases not in fixtures | ✅ Add production test with `@pytest.mark.production` |
| General functionality testing | ❌ Use existing minimal fixture (faster) |
| Unit testing isolated logic | ❌ Use in-memory database (fastest) |
| Validating data integrity | ✅ Use production database |
| Testing query performance | ✅ Use production database |
| Running on CI for every commit | ❌ Too slow (5-10s extra) |
| Running before release | ✅ Comprehensive validation |
| Developing new feature | ❌ Use minimal fixture first |

---

**Final Recommendation**: Keep current implementation, add production database testing as optional enhancement for comprehensive validation. No Git-LFS needed.
