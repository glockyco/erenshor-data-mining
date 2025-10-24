# Troubleshooting Guide

Comprehensive guide for diagnosing and resolving common issues in the Erenshor data mining pipeline.

## Quick Diagnostics

Run these commands first to identify issues:

```bash
erenshor doctor                  # System health check
erenshor status                  # Pipeline status
erenshor status --all-variants   # Multi-variant status
```

**Log Locations**:

-   Global logs: `.erenshor/logs/`
-   Variant logs: `variants/{variant}/logs/`
-   Unity export logs: `variants/{variant}/logs/export_*.log`

## Common Issues

### Unity Export Fails

**Problem**: Unity batch mode export crashes or hangs

**Solutions**:

```bash
# 1. Check Unity version matches exactly
erenshor config show global.unity.version
# Should output: 2021.3.45f2

# 2. Verify Unity installation path
erenshor config show global.unity.path

# 3. Check export logs
cat variants/main/logs/export_*.log

# 4. Check symlinks are valid
ls -la variants/main/unity/Assets/Editor

# 5. Increase timeout if needed
# Edit .erenshor/config.local.toml:
# [global.unity]
# timeout = 3600  # 1 hour
```

### Wiki Upload Issues

**Problem**: Wiki uploads fail or credentials rejected

**Solutions**:

```bash
# 1. Verify credentials are set in config
erenshor config show global.mediawiki

# 2. Test wiki access
erenshor wiki update --dry-run

# 3. Check MediaWiki API is accessible
curl https://erenshor.wiki.gg/api.php?action=query&meta=siteinfo
```

### Google Sheets Permission Denied

**Problem**: Google Sheets API returns 403 Forbidden

**Solutions**:

```bash
# 1. Validate credentials file exists
ls -la ~/.config/erenshor/google-credentials.json

# 2. Test with dry-run
erenshor sheets deploy --sheets items --dry-run

# 3. Verify service account has Editor access
# Open spreadsheet → Share → Add service account email with "Editor" role

# 4. Check spreadsheet ID in config
erenshor config show variants.main.google_sheets.spreadsheet_id

# 5. Enable Google Sheets API in Google Cloud Console
# https://console.cloud.google.com/apis/library/sheets.googleapis.com
```

### Database Not Found

**Problem**: SQLite database missing or corrupt

**Solutions**:

```bash
# 1. Check database location
ls -la variants/main/erenshor-main.sqlite

# 2. Re-export if missing
erenshor extract export --variant main

# 3. Verify variant configuration
erenshor config show variants.main.database

# 4. Check Unity export completed successfully
erenshor status
```

### SteamCMD Authentication Fails

**Problem**: SteamCMD can't download game

**Solutions**:

```bash
# 1. Verify Steam username is set
erenshor config show global.steam.username

# 2. Check Steam credentials
# SteamCMD stores credentials in ~/.steam/

# 3. Verify game ownership
# Log in to Steam and check library

# 4. Try manual SteamCMD login
steamcmd +login your_username +quit

# 5. Check SteamCMD installation
which steamcmd
steamcmd +version
```

### Python Import Errors

**Problem**: Python modules not found

**Solutions**:

```bash
# 1. Verify Python environment
uv run python --version
# Should be 3.13+

# 2. Reinstall dependencies
uv sync --dev

# 3. Check package is installed
uv run pip list | grep erenshor

# 4. Verify PYTHONPATH (for development)
echo $PYTHONPATH

# 5. Install in editable mode
uv pip install -e ".[dev]"
```

## Error Reference Table

| Error                               | Cause                                  | Solution                                                  |
| ----------------------------------- | -------------------------------------- | --------------------------------------------------------- |
| `Unity version mismatch`            | Wrong Unity version installed          | Install Unity 2021.3.45f2 exactly                         |
| `Database schema mismatch`          | Old database format                    | Re-run `erenshor extract export`                          |
| `Symlink broken`                    | Editor scripts not linked              | Check symlink: `ls -la variants/main/unity/Assets/Editor` |
| `SteamCMD authentication failed`    | Invalid Steam credentials              | Check Steam username and password                         |
| `AssetRipper timeout`               | Extraction taking too long             | Increase timeout in config                                |
| `Wiki page validation failed`       | Malformed wiki markup                  | Check logs in `.erenshor/logs/`                           |
| `Service account permission denied` | Sheets not shared with service account | Share spreadsheet with service account email              |

## Advanced Debugging

### Log Analysis

**Global Logs** (`.erenshor/logs/`):

-   `erenshor.log` - Main pipeline log
-   `operations/` - Per-operation logs with timestamps

**Variant Logs** (`variants/{variant}/logs/`):

-   `export_*.log` - Unity batch mode output
-   `unity_*.log` - Unity editor logs
-   `extraction_*.log` - AssetRipper extraction logs

**Unity Logs** (system-specific):

-   macOS: `~/Library/Logs/Unity/Editor.log`
-   Linux: `~/.config/unity3d/Editor.log`
-   Windows: `%APPDATA%\Unity\Editor.log`

### Environment Validation

**Unity Version Check**:

```bash
# Check configured version and path
erenshor config show global.unity

# Check installed version (copy path from config show)
/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity -version
```

**Python Environment**:

```bash
# Check Python version
python3 --version

# Check uv installation
uv --version

# List installed packages
uv run pip list
```

**Symlink Validation**:

```bash
# Verify symlink for each variant
ls -la variants/main/unity/Assets/Editor
ls -la variants/playtest/unity/Assets/Editor
ls -la variants/demo/unity/Assets/Editor
# Should point to: ../../../../src/Assets/Editor
```

**Permission Checks**:

```bash
# Check file permissions
ls -la variants/main/erenshor-main.sqlite

# Check directory permissions
ls -ld variants/main/
```

### Stack Traces

**Python Stack Traces**:

```bash
# Enable verbose mode
erenshor --verbose <command>

# Enable Python debugging
export PYTHONWARNINGS=default
erenshor <command>
```

**Unity Stack Traces**:
Check Unity editor logs for C# exceptions. Stack traces include:

-   Exception type
-   File path and line number
-   Call stack

## Getting Help

If you're still stuck:

### 1. Check Logs

```bash
# Global logs
ls -la .erenshor/logs/

# Variant-specific logs
ls -la variants/main/logs/
```

### 2. Run Doctor

```bash
erenshor doctor
```

### 3. Check Status

```bash
erenshor status --all-variants
```

### 4. Enable Debug Logging

```bash
erenshor --verbose extract export
```
