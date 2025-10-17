# Precondition System Design Questions

**Date**: 2025-10-17
**Status**: Design Decisions Documented
**Purpose**: Document design decisions made during precondition system implementation

---

## Questions & Answers

### 1. How should CLI context be passed to checks?

**Decision**: Use decorator pattern with automatic context extraction from Typer's CLIContext.

**Rationale**:
- The CLI already has a `CLIContext` dataclass with config, variant, repo_root
- Decorator can automatically extract needed info from ctx.obj
- Check functions receive a simple dict with only what they need
- No coupling between checks and CLI framework

**Implementation**:
```python
# Decorator extracts from CLIContext and builds simple dict
context = {
    "variant": cli_ctx.variant,
    "database_path": variant_config.resolved_database(cli_ctx.repo_root),
    "unity_project": variant_config.resolved_unity_project(cli_ctx.repo_root),
    "game_dir": variant_config.resolved_game_files(cli_ctx.repo_root),
    "repo_root": cli_ctx.repo_root,
}
```

### 2. Should checks be async or sync?

**Decision**: Sync only for now.

**Rationale**:
- All current checks are fast (file existence, simple queries)
- No network I/O in precondition checks (that's for commands)
- Simpler implementation and testing
- Can add async support later if needed (YAGNI)

### 3. How to handle checks that need configuration?

**Decision**: Configuration passed via context dict.

**Rationale**:
- Checks receive context dict with all needed info
- No direct config dependency in check functions
- Easy to test with mock contexts
- Check functions stay pure and reusable

**Example**:
```python
def database_exists(context: dict) -> PreconditionResult:
    db_path = Path(context["database_path"])  # From config
    if not db_path.exists():
        return PreconditionResult(...)
```

### 4. Should we support check dependencies (check A before check B)?

**Decision**: No automatic dependency management. Manual ordering in decorator.

**Rationale**:
- Simple and explicit (decorator lists checks in order)
- No magic or hidden behavior
- Most checks are independent anyway
- If ordering matters, developer can see it in decorator
- YAGNI - don't build dependency graph until needed

**Example**:
```python
# Want database_exists before database_valid
@require_preconditions(
    database_exists,      # Run first
    database_valid,       # Run second (assumes DB exists)
    database_has_items,   # Run third (assumes DB valid)
)
```

### 5. How verbose should error messages be?

**Decision**: Two-level messages - short message + optional detail.

**Rationale**:
- Short message for summary view
- Detail field for actionable hints
- Follows Rich console patterns
- Similar to existing doctor command output

**Example**:
```python
PreconditionResult(
    passed=False,
    check_name="database_exists",
    message="Database not found",  # Short
    detail=f"Missing: {db_path}\nRun 'erenshor export' to create"  # Detailed
)
```

### 6. Should we show all failing checks or stop at first failure?

**Decision**: Run all checks, show all failures.

**Rationale**:
- Better UX - see all problems at once, not one at a time
- Faster iteration - fix multiple issues before re-running
- Consistent with existing doctor command behavior
- Decorator collects all results before failing

**Example output**:
```
Precondition checks failed:

  ✓ Unity project exists
  ✗ Database not found
    Missing: /path/to/db.sqlite
    Run 'erenshor export' to create
  ✗ Database is empty
    No items found in database

Abort: Fix issues before running command
```

---

## Design Principles Applied

1. **Simple over Complex**: Dict context, no dependency graph, sync only
2. **Explicit over Implicit**: Decorator shows checks, manual ordering
3. **Good DX**: Clear messages, show all failures, easy to add checks
4. **Fail Fast**: All checks before command runs, clear exit on failure
5. **YAGNI**: No features we don't need yet (async, dependencies, etc.)

---

## Future Considerations

**NOT implementing now** (add if genuinely needed):
- Async check support (no network checks needed yet)
- Automatic dependency resolution (manual ordering sufficient)
- Check caching (checks are fast enough)
- Conditional checks (every check runs, simple enough)
- Custom check discovery (explicit imports clearer)
- Check timeout handling (checks are instant)

---

## Integration Notes

### With Existing Doctor Command

The Bash doctor command (`legacy/cli/commands/doctor.sh`) performs comprehensive system health checks. We'll reuse the same logical checks in Python:

**Mapping**:
- `check_dependency()` bash function → Python check functions
- File existence checks → `filesystem.py` checks
- Unity checks → `unity.py` checks
- Database checks → `database.py` checks

**Difference**:
- Doctor: comprehensive diagnostics (all checks, warnings + errors)
- Preconditions: fail-fast before command (critical checks only)

### With CLI Commands

Commands use decorator pattern for zero-boilerplate enforcement:

```python
@require_preconditions(
    database_exists,
    database_valid,
)
def wiki_update(ctx: typer.Context):
    # Command automatically fails if checks fail
    # No manual checking needed
```

---

## Testing Strategy

1. **Unit tests**: Each check function individually
2. **Decorator tests**: Enforcement behavior, context extraction
3. **Integration tests**: Real commands with checks
4. **Mock contexts**: Easy to test without real files

---

**Status**: All design questions resolved. Ready for implementation.
