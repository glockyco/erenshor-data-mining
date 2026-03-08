---
name: debugging
description: Debug and troubleshoot issues in the Erenshor project. Use when encountering errors, investigating failures, or diagnosing problems with exports, CLI, or deployments.
---

# Debugging Guide

## Export Issues

**Check logs first**:
```bash
# Variant-specific logs
ls variants/{variant}/logs/export_*.log

# Global logs
ls .erenshor/logs/
```

**Common problems**:

1. **Unity version mismatch**: Must use exactly Unity 2021.3.45f2
   ```bash
   uv run erenshor config show  # Check configured Unity path
   ```

2. **Missing ScriptableObject references**: Run Unity in GUI mode to see
   console errors. Assets may have broken references after game updates.

3. **Database locked**: Close any SQLite viewers before running export.

4. **Symlink issues**: Verify Editor symlink exists:
   ```bash
   ls -la variants/main/unity/Assets/Editor
   ```

## CLI Issues

**Health check**:
```bash
uv run erenshor status    # Current status
uv run erenshor config show  # View configuration
```

**Verbose mode**:
```bash
uv run erenshor --verbose <command>
```

**Common problems**:

1. **Command not found**: Run `uv sync --dev` to install dependencies
2. **Import errors**: Check Python path and virtual environment
3. **Config not loading**: Verify config.toml exists and is valid TOML

## Google Sheets Issues

**Authentication**:
```bash
# Check credentials file exists
ls ~/.config/erenshor/google-credentials.json
```

**Permissions**: Service account needs **Editor** access to the spreadsheet,
not just Viewer.

**Test without writing**:
```bash
uv run erenshor sheets deploy --dry-run
```

**Common problems**:

1. **403 Forbidden**: Service account lacks Editor permission
2. **Spreadsheet not found**: Check spreadsheet_id in config.toml
3. **Rate limiting**: Reduce batch_size in config or add delays

## Wiki Issues

**Test locally first**:
```bash
uv run erenshor wiki generate  # Generate without deploying
ls variants/main/wiki/generated/  # Check output
```

**Common problems**:

1. **Template errors**: Check Jinja2 templates in generators/
2. **Missing pages**: Verify entity exists in database
3. **Auth failures**: Check wiki credentials in config

## Database Issues

**Inspect database**:
```bash
sqlite3 variants/main/erenshor-main.sqlite
.tables  # List all tables
.schema Items  # Show table schema
SELECT COUNT(*) FROM Items;  # Check row counts
```

**Common problems**:

1. **Empty tables**: Export may have failed silently
2. **Missing columns**: Schema changed, re-run export
3. **Duplicate keys**: Check StableKey generation logic
