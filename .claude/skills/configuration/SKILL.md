---
name: configuration
description: Understand and modify project configuration. Use when working with config.toml, settings, variants, paths, or environment setup.
---

# Configuration System

Two-layer TOML configuration with NO environment variables.

## Files

| File | Purpose | Tracked |
|------|---------|---------|
| `config.toml` | Project defaults | Yes |
| `.erenshor/config.local.toml` | User overrides | No |

Local config merges over project config. User-specific paths and credentials
go in local config.

## Structure

```toml
[global.unity]
path = "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity"
version = "2021.3.45f2"

[global.google_sheets]
credentials_file = "$HOME/.config/erenshor/google-credentials.json"
batch_size = 1000

[variants.main]
app_id = 2382520
database = "$REPO_ROOT/variants/main/erenshor-main.sqlite"

[variants.main.google_sheets]
spreadsheet_id = "1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E"

[variants.playtest]
app_id = 3090030
database = "$REPO_ROOT/variants/playtest/erenshor-playtest.sqlite"

[variants.demo]
app_id = 2522260
database = "$REPO_ROOT/variants/demo/erenshor-demo.sqlite"
```

## Variable Expansion

- `$HOME` or `~` - User's home directory
- `$REPO_ROOT` - Repository root directory

## Variants

Three game variants with completely separate:
- Game downloads (`variants/{variant}/game/`)
- Unity projects (`variants/{variant}/unity/`)
- Databases (`variants/{variant}/erenshor-{variant}.sqlite`)
- Wiki caches (`variants/{variant}/wiki/`)
- Logs (`variants/{variant}/logs/`)
- Google Sheets spreadsheets

## Commands

```bash
uv run erenshor config show              # View merged config
uv run erenshor --variant playtest ...   # Use specific variant
```

## Loading Config in Code

```python
from pathlib import Path
from erenshor.infrastructure.config import load_config

config = load_config()
repo_root = Path("/path/to/repo")

# Raw config values (unexpanded)
raw_db = config.variants["main"].database  # "$REPO_ROOT/variants/main/..."

# Resolved paths (use resolved_* methods)
db_path = config.variants["main"].resolved_database(repo_root)  # Path object
unity_path = config.global_.unity.resolved_path(repo_root)
credentials = config.global_.google_sheets.resolved_credentials_file(repo_root)
```

## Google Sheets Setup

1. Create service account in Google Cloud Console
2. Download JSON credentials to `~/.config/erenshor/google-credentials.json`
3. Share spreadsheet with service account email (Editor access)
4. Add spreadsheet_id to config.toml
