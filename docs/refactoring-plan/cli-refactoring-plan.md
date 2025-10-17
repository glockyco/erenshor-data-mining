# CLI Refactoring Plan

## Current State

The `src/erenshor/cli/main.py` file has grown to **845 lines** and contains multiple concerns:

### Current Structure

```
src/erenshor/cli/main.py (845 lines)
├── Main app setup (40 lines)
│   ├── Imports
│   ├── Console initialization
│   ├── Typer app creation
│   └── Command group registration
│
├── Global callback (50 lines)
│   ├── Config loading
│   ├── Logging setup
│   ├── CLI context creation
│   └── Error handling
│
├── Status command (120 lines)
│   ├── Variant iteration logic
│   ├── Configuration display
│   ├── Database info
│   ├── Path validation
│   └── Tools verification
│
├── Doctor command (145 lines)
│   ├── Health checks for config
│   ├── Log directory checks
│   ├── Unity verification
│   ├── AssetRipper verification
│   ├── Database checks
│   └── Credentials validation
│
├── Config command group (180 lines)
│   ├── Config app creation
│   ├── Helper functions (_get_nested_value, _format_config_tree, _add_tree_node)
│   └── config_show command
│
├── Backup command group (85 lines)
│   ├── Backup app creation
│   └── backup_info command
│
├── Test command group (100 lines)
│   ├── Test app creation
│   ├── test_callback (run all tests)
│   ├── test_unit command
│   └── test_integration command
│
├── Docs command group (25 lines)
│   ├── Docs app creation
│   └── docs_generate command (stub)
│
└── cli_main entry point (15 lines)
```

### Issues

1. **Too many responsibilities**: Single file handles app setup, global options, status display, health checks, config display, backup info, test running, and docs generation
2. **Large command implementations**: `status` (120 lines) and `doctor` (145 lines) have complex logic
3. **Helper functions mixed with commands**: Config tree formatting helpers in same file
4. **Hard to test**: Tightly coupled code makes unit testing difficult
5. **Hard to navigate**: Developers must scroll through 845 lines to find specific functionality

## Refactoring Goals

1. **Separate concerns** - Each command group should be in its own module
2. **Improve testability** - Extract logic into testable functions
3. **Reduce file size** - Break into logical modules of 100-200 lines each
4. **Maintain consistency** - Follow same patterns as existing command modules (wiki, sheets, extract, maps)
5. **Keep it simple** - Don't over-engineer, just organize logically

## Proposed Structure

```
src/erenshor/cli/
├── __init__.py
├── main.py                 # ~100 lines - app setup, global options, entry point
├── context.py              # Existing - CLIContext class
├── commands/
│   ├── __init__.py
│   ├── extract.py          # Existing
│   ├── wiki.py             # Existing
│   ├── sheets.py           # Existing
│   ├── maps.py             # Existing
│   ├── info.py             # NEW - status, doctor commands
│   ├── config.py           # NEW - config command group
│   ├── backup.py           # NEW - backup command group
│   ├── test.py             # NEW - test command group
│   └── docs.py             # NEW - docs command group
```

### Detailed Breakdown

#### `main.py` (~100 lines)
**Responsibility**: App setup, global options, entry point

```python
"""Main CLI entry point with global options and app setup."""

# Imports
from erenshor.cli.commands import backup, config, docs, extract, info, maps, sheets, test, wiki

# Create app
app = typer.Typer(...)

# Register command groups
app.add_typer(extract.app, name="extract")
app.add_typer(wiki.app, name="wiki")
app.add_typer(sheets.app, name="sheets")
app.add_typer(maps.app, name="maps")
app.add_typer(info.app, name="info")  # NEW: status, doctor
app.add_typer(config.app, name="config")
app.add_typer(backup.app, name="backup")
app.add_typer(test.app, name="test")
app.add_typer(docs.app, name="docs")

# Global callback (--variant, --dry-run, --verbose, --quiet)
@app.callback()
def main(...): ...

# Version command (keep here - it's simple and top-level)
@app.command()
def version(): ...

# Entry point
def cli_main(): ...
```

#### `commands/info.py` (~200 lines)
**Responsibility**: System information and health checks

```python
"""System information and health check commands."""

app = typer.Typer(name="info", help="System information and health checks")

@app.command("status")
def status(...):
    """Show system status."""
    # Current status command implementation
    ...

@app.command("doctor")
def doctor(...):
    """Run system health check."""
    # Current doctor command implementation
    ...

# Helper functions for these commands
def _check_database_status(...): ...
def _check_unity_installation(...): ...
def _check_credentials(...): ...
```

**Note**: The `info` command group is new but contains existing `status` and `doctor` commands. This groups related information/diagnostic commands together.

#### `commands/config.py` (~200 lines)
**Responsibility**: Configuration viewing and management

```python
"""Configuration viewing and management commands."""

app = typer.Typer(name="config", help="View and manage configuration")

@app.command("show")
def config_show(...):
    """Show configuration."""
    # Current config_show implementation
    ...

# Helper functions
def _get_nested_value(...): ...
def _format_config_tree(...): ...
def _add_tree_node(...): ...
```

#### `commands/backup.py` (~100 lines)
**Responsibility**: Database backup management

```python
"""Database backup management commands."""

app = typer.Typer(name="backup", help="Manage database backups")

@app.command("info")
def backup_info(...):
    """Show backup information."""
    # Current backup_info implementation
    ...

# Future commands could include:
# @app.command("create")
# def backup_create(...): ...
#
# @app.command("restore")
# def backup_restore(...): ...
```

#### `commands/test.py` (~120 lines)
**Responsibility**: Test execution

```python
"""Test execution commands."""

app = typer.Typer(name="test", help="Run tests and validation")

@app.callback(invoke_without_command=True)
def test_callback(...):
    """Run all tests."""
    # Current test_callback implementation
    ...

@app.command("unit")
def test_unit(...):
    """Run unit tests only."""
    ...

@app.command("integration")
def test_integration(...):
    """Run integration tests only."""
    ...
```

#### `commands/docs.py` (~50 lines)
**Responsibility**: Documentation generation

```python
"""Documentation generation commands."""

app = typer.Typer(name="docs", help="Generate documentation")

@app.command("generate")
def docs_generate(...):
    """Generate documentation."""
    # Stub implementation or future expansion
    ...
```

## Migration Strategy

### Phase 1: Extract Command Groups (Low Risk)
**Goal**: Move command groups to separate files without changing behavior

1. **Extract `config.py`**
   - Create `src/erenshor/cli/commands/config.py`
   - Move `config_app`, `config_show`, and helpers
   - Update `main.py` to import from `commands.config`
   - Test: `uv run pytest tests/unit/ -k config`

2. **Extract `backup.py`**
   - Create `src/erenshor/cli/commands/backup.py`
   - Move `backup_app` and `backup_info`
   - Update `main.py` imports
   - Test: Manual testing (no backup tests yet)

3. **Extract `test.py`**
   - Create `src/erenshor/cli/commands/test.py`
   - Move `test_app`, `test_callback`, `test_unit`, `test_integration`
   - Update `main.py` imports
   - Test: `uv run pytest tests/unit/`

4. **Extract `docs.py`**
   - Create `src/erenshor/cli/commands/docs.py`
   - Move `docs_app` and `docs_generate`
   - Update `main.py` imports
   - Test: Manual testing (stub command)

### Phase 2: Create Info Module (Medium Risk)
**Goal**: Group status and doctor commands under new `info` namespace

1. **Create `info.py`**
   - Create `src/erenshor/cli/commands/info.py`
   - Move `status` and `doctor` commands
   - Create `info` app with these as subcommands
   - Update `main.py` to register `info` app

2. **Update command invocation**
   - Old: `erenshor status`, `erenshor doctor`
   - New: `erenshor info status`, `erenshor info doctor`
   - Consider: Add aliases to maintain backward compatibility?

3. **Test thoroughly**
   - Test: `erenshor info status`
   - Test: `erenshor info doctor`
   - Update any documentation or scripts that reference old commands

### Phase 3: Clean Up Main (Low Risk)
**Goal**: Simplify main.py to just app setup and global options

1. **Review `main.py`**
   - Should only contain: imports, app creation, command registration, global callback, version command, entry point
   - Target: ~100 lines
   - Remove any helper functions that should be in other modules

2. **Add module docstrings**
   - Ensure each new module has clear docstring explaining its purpose
   - Add "See Also" references between related modules

3. **Update CLAUDE.md**
   - Document new structure
   - Update examples to use new command paths
   - Add migration notes

## Testing Strategy

### Unit Tests
No new unit tests required - existing tests should continue to work if imports are updated correctly.

### Integration Tests
1. **Command invocation tests**
   - Test each command can be invoked from CLI
   - Test help text displays correctly
   - Test command groups are registered

2. **Import tests**
   - Verify all commands are importable
   - Verify no circular dependencies

### Manual Testing Checklist
- [ ] `erenshor --help` shows all command groups
- [ ] `erenshor version` works
- [ ] `erenshor info status` works
- [ ] `erenshor info doctor` works
- [ ] `erenshor config show` works
- [ ] `erenshor backup info` works
- [ ] `erenshor test` works
- [ ] `erenshor test unit` works
- [ ] `erenshor docs generate` works (stub)

## Backward Compatibility

### Breaking Changes
**Phase 2 introduces breaking changes**:
- `erenshor status` → `erenshor info status`
- `erenshor doctor` → `erenshor info doctor`

### Mitigation Options

#### Option 1: Aliases (Recommended)
Keep old commands as aliases for transition period:

```python
# In main.py
@app.command(name="status", hidden=True)
def status_alias(ctx: typer.Context):
    """Deprecated: Use 'erenshor info status' instead."""
    typer.echo("Warning: 'erenshor status' is deprecated. Use 'erenshor info status'", err=True)
    # Invoke new command
    from .commands import info
    ctx.invoke(info.status, ctx=ctx)

@app.command(name="doctor", hidden=True)
def doctor_alias(ctx: typer.Context):
    """Deprecated: Use 'erenshor info doctor' instead."""
    typer.echo("Warning: 'erenshor doctor' is deprecated. Use 'erenshor info doctor'", err=True)
    # Invoke new command
    from .commands import info
    ctx.invoke(info.doctor, ctx=ctx)
```

#### Option 2: Keep Commands at Top Level
Alternative: Keep `status` and `doctor` at top level instead of grouping under `info`.

This avoids breaking changes but doesn't achieve the "grouping related commands" goal.

#### Option 3: Document Migration Path
Simplest option: Document the change, update all internal scripts/docs, announce to users.

Since this is a hobby project with likely few users, this may be sufficient.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking CLI interface | High | Use aliases or keep commands at top level |
| Import errors | Medium | Thorough testing, update all imports |
| Circular dependencies | Low | Keep imports in main.py, not in command modules |
| Regression in commands | Medium | Run full test suite after each phase |
| Documentation out of sync | Low | Update CLAUDE.md, README in same PR |

## Success Criteria

1. ✅ `main.py` reduced to ~100 lines
2. ✅ Each command group in separate file (100-200 lines each)
3. ✅ All existing tests pass without modification (except import updates)
4. ✅ All commands still work from CLI
5. ✅ No circular dependencies
6. ✅ Documentation updated
7. ✅ Code quality checks pass (mypy, ruff)

## Timeline and Effort

### Estimated Effort
- **Phase 1**: 2-3 hours (extract command groups)
- **Phase 2**: 1-2 hours (create info module, handle breaking changes)
- **Phase 3**: 1 hour (clean up, documentation)
- **Total**: 4-6 hours

### Implementation Order
1. Start with Phase 1 - low risk, immediate benefit
2. Get feedback before Phase 2 (breaking changes)
3. Complete Phase 3 after Phase 2

## Alternative Approaches Considered

### 1. Keep Everything in One File
**Pros**: Simpler, no imports to manage
**Cons**: Already at 845 lines, will continue to grow
**Verdict**: ❌ Not sustainable

### 2. Split by Functionality Type
Structure by command category (info, management, deployment):
```
commands/
├── info/           # status, doctor, version
├── management/     # config, backup, test
└── deployment/     # wiki, sheets, maps, extract
```

**Pros**: Clear separation of concerns
**Cons**: More complex, over-engineered for current needs
**Verdict**: ❌ Too complex

### 3. Flat Structure (Current + New Files)
Keep current structure, just move each command group to its own file (recommended approach).

**Pros**: Simple, follows existing patterns, easy to understand
**Cons**: None significant
**Verdict**: ✅ Recommended

## References

- **Typer Best Practices**: https://typer.tiangolo.com/tutorial/subcommands/
- **Click Modular Applications**: https://click.palletsprojects.com/en/8.1.x/complex/
- **Project CLAUDE.md**: /Users/joaichberger/Projects/Erenshor/CLAUDE.md

## Notes

- This plan follows the "Keep It Simple" principle from project guidelines
- Each phase is independently testable and can be committed separately
- Breaking changes are isolated to Phase 2 and can be deferred
- The structure mirrors existing command modules (wiki, sheets, extract, maps)
