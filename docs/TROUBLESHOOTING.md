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
- Global logs: `.erenshor/logs/`
- Variant logs: `variants/{variant}/logs/`
- Unity export logs: `variants/{variant}/logs/export_*.log`

## Common Issues

### Unity Export Fails

**Problem**: Unity batch mode export crashes or hangs

**Solutions**:
```bash
# 1. Check Unity version matches exactly
erenshor config get unity.version
# Should output: 2021.3.45f2

# 2. Verify Unity installation path
ls -la "$(erenshor config get unity.path)"

# 3. Check export logs
cat variants/main/logs/export_*.log

# 4. Check symlinks are valid
erenshor symlink check

# 5. Increase timeout if needed
# Edit .erenshor/config.local.toml:
# [global.unity]
# timeout = 3600  # 1 hour
```

### Wiki Upload Issues

**Problem**: Wiki uploads fail or credentials rejected

**Solutions**:
```bash
# 1. Verify credentials are set
cat .env | grep ERENSHOR_BOT

# 2. Test credentials
uv run python -m erenshor.cli.main wiki fetch "Main Page"

# 3. Validate content before upload
uv run python -m erenshor.cli.main wiki validate-items

# 4. Use dry-run to preview
uv run python -m erenshor.cli.main wiki push --all --dry-run

# 5. Check MediaWiki API is accessible
curl https://erenshor.wiki.gg/api.php?action=query&meta=siteinfo
```

### Google Sheets Permission Denied

**Problem**: Google Sheets API returns 403 Forbidden

**Solutions**:
```bash
# 1. Validate credentials file exists
ls -la ~/.config/erenshor/google-credentials.json

# 2. Test credentials
uv run python -m erenshor.cli.main sheets validate

# 3. Verify service account has Editor access
# Open spreadsheet → Share → Add service account email with "Editor" role

# 4. Check spreadsheet ID in config
erenshor config get variants.main.google_sheets.spreadsheet_id

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
erenshor export --variant main

# 3. Check for backups
ls -la variants/main/backups/

# 4. Verify variant configuration
erenshor config get variants.main.database

# 5. Check Unity export completed successfully
erenshor status
```

### SteamCMD Authentication Fails

**Problem**: SteamCMD can't download game

**Solutions**:
```bash
# 1. Verify Steam username is set
erenshor config get global.steam.username

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
uv run pip list | grep erenshor-wiki

# 4. Verify PYTHONPATH (for development)
echo $PYTHONPATH

# 5. Install in editable mode
uv pip install -e ".[dev]"
```

## Error Reference Table

| Error | Cause | Solution |
|-------|-------|----------|
| `Unity version mismatch` | Wrong Unity version installed | Install Unity 2021.3.45f2 exactly |
| `Database schema mismatch` | Old database format | Re-run `erenshor export` |
| `Symlink broken` | Editor scripts not linked | Run `erenshor symlink create` |
| `SteamCMD authentication failed` | Invalid Steam credentials | Check Steam username and password |
| `AssetRipper timeout` | Extraction taking too long | Increase timeout in config |
| `Wiki page validation failed` | Malformed wiki markup | Check generated content in `wiki_updated/` |
| `Service account permission denied` | Sheets not shared with service account | Share spreadsheet with service account email |

## Advanced Debugging

### Log Analysis

**Global Logs** (`.erenshor/logs/`):
- `erenshor.log` - Main pipeline log
- `operations/` - Per-operation logs with timestamps

**Variant Logs** (`variants/{variant}/logs/`):
- `export_*.log` - Unity batch mode output
- `unity_*.log` - Unity editor logs
- `extraction_*.log` - AssetRipper extraction logs

**Unity Logs** (system-specific):
- macOS: `~/Library/Logs/Unity/Editor.log`
- Linux: `~/.config/unity3d/Editor.log`
- Windows: `%APPDATA%\Unity\Editor.log`

### Environment Validation

**Unity Version Check**:
```bash
# Check configured version
erenshor config get unity.version

# Check installed version
"$(erenshor config get unity.path)" -version
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
# Check all symlinks
erenshor symlink status

# Verify specific symlink
ls -la variants/main/unity/Assets/Editor
# Should point to: ../../../../src/Assets/Editor
```

**Permission Checks**:
```bash
# Check file permissions
ls -la variants/main/erenshor-main.sqlite

# Check directory permissions
ls -ld variants/main/

# Check script execute permissions
ls -la cli/bin/erenshor
```

### Stack Traces

**Python Stack Traces**:
```bash
# Enable verbose mode
uv run python -m erenshor.cli.main --verbose <command>

# Enable Python debugging
export PYTHONWARNINGS=default
uv run python -m erenshor.cli.main <command>
```

**Unity Stack Traces**:
Check Unity editor logs for C# exceptions. Stack traces include:
- Exception type
- File path and line number
- Call stack

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
export LOG_LEVEL=DEBUG
erenshor export
```

### 5. File an Issue

When reporting issues, include:
- Error messages and relevant log excerpts
- Operating system and versions (Unity, Python, SteamCMD)
- Steps to reproduce the problem
- Configuration (sanitize credentials!)
- Check existing issues first

**Where to Report**:
- GitHub Issues: Check repository for issue tracker
- Documentation: Review CLAUDE.md and README.md first
