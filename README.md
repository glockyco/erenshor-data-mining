# Erenshor Data Mining & Wiki Publishing Pipeline

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Unity](https://img.shields.io/badge/unity-2021.3.45f2-black.svg)](https://unity.com/)

Data mining pipeline for Erenshor (single-player MMORPG). Downloads game files from Steam, extracts Unity assets, exports to SQLite, and publishes to MediaWiki and Google Sheets.

**Pipeline**: Steam → Game Files → Unity Project → SQLite Database → Wiki/Sheets

---

## Table of Contents

-   [Quick Start](#quick-start)
-   [Architecture](#architecture)
-   [Usage](#usage)
-   [Configuration](#configuration)
-   [Development](#development)
-   [Reference](#reference)

---

## Quick Start

### Prerequisites

-   **Unity 2021.3.45f2** (exact version required)
-   **Python 3.13+**
-   **SteamCMD**
-   **AssetRipper**
-   **uv** (Python package manager)
-   **Steam Account** with Erenshor ownership
-   **8GB+ RAM** and **20GB+ disk space** per variant

### Installation

```bash
# Clone repository
git clone https://github.com/glockyco/erenshor-data-mining.git
cd erenshor-data-mining

# Install dependencies
uv sync --dev

# Configure tools and credentials
cp config.toml .erenshor/config.local.toml
# Edit .erenshor/config.local.toml with your tool paths

# Verify installation
uv run erenshor doctor
```

### First Run

```bash
# Run full extraction pipeline
uv run erenshor extract full

# Expected output: variants/main/erenshor-main.sqlite (50MB+ database)

# Deploy to Google Sheets (optional)
uv run erenshor sheets deploy --all-sheets
```

---

## Architecture

### Pipeline

**Steam** → **SteamCMD** → **Game Files** → **AssetRipper** → **Unity Project** → **Unity Editor Scripts (C#)** → **SQLite** → **Python Formatters** → **MediaWiki / Google Sheets**

Python CLI (`uv run erenshor`) built with Typer handles pipeline automation, data formatting, and publishing.

### Data Flow

**Export Layer** (Unity C# → SQLite)

-   Unity Editor scripts extract game data from ScriptableObjects
-   Custom listeners for each entity type (items, characters, quests, etc.)
-   Location: `src/Assets/Editor/`

**Format Layer** (SQLite → Content)

-   Python generators stream entities from database
-   Jinja2 templates render MediaWiki markup
-   Custom formatters for Google Sheets
-   Location: `src/erenshor/application/`

**Deploy Layer** (Content → Destinations)

-   MediaWiki API client for wiki uploads
-   Google Sheets API v4 for spreadsheet publishing
-   Location: `src/erenshor/infrastructure/`

### Multi-Variant Support

Three game variants with separate pipelines:

| Variant      | App ID  | Description                |
| ------------ | ------- | -------------------------- |
| **main**     | 2382520 | Production release         |
| **playtest** | 3090030 | Private beta/alpha testing |
| **demo**     | 2522260 | Free demo version          |

Each variant maintains separate game downloads, Unity projects, databases, spreadsheets, and logs.

---

## Usage

### Common Workflows

**Full Pipeline Update (After Game Patch)**

```bash
# Run complete extraction pipeline
uv run erenshor extract full

# Update wiki content
uv run erenshor wiki update

# Deploy to Google Sheets
uv run erenshor sheets deploy --all-sheets
```

**Individual Extraction Steps**

```bash
uv run erenshor extract download    # Download from Steam
uv run erenshor extract rip         # Extract Unity project
uv run erenshor extract export      # Export to SQLite
```

**Managing Multiple Variants**

```bash
# Update playtest variant
uv run erenshor extract full --variant playtest

# Check status
uv run erenshor status
```

**Google Sheets Deployment**

```bash
# List available sheets
uv run erenshor sheets list

# Deploy all sheets
uv run erenshor sheets deploy --all-sheets

# Deploy specific sheets
uv run erenshor sheets deploy --sheets items characters

# Preview without uploading
uv run erenshor sheets deploy --all-sheets --dry-run
```

**Available Sheets**: achievement-triggers, ascensions, books, character-dialogs, characters, classes, drop-chances, factions, fishing, item-bags, items, mining-nodes, quests, secret-passages, skills, spawn-points, spells, teleports, treasure-locations, wishing-wells, zones

### CLI Commands

```bash
# System
uv run erenshor version             # Show version
uv run erenshor status              # Show status
uv run erenshor doctor              # Health check
uv run erenshor config show         # View configuration

# Extraction (download → rip → export)
uv run erenshor extract full        # Complete pipeline
uv run erenshor extract download    # Download from Steam
uv run erenshor extract rip         # Extract Unity project
uv run erenshor extract export      # Export to SQLite

# Publishing
uv run erenshor wiki update         # Update wiki pages
uv run erenshor sheets deploy       # Deploy to Google Sheets

# Maps
uv run erenshor maps dev            # Start dev server
uv run erenshor maps build          # Build for production
uv run erenshor maps deploy         # Deploy to Cloudflare

# Testing
uv run erenshor test                # Run all tests
```

See **[CLAUDE.md](CLAUDE.md)** for detailed documentation.

---

## Configuration

Two-layer TOML configuration system:

1. `config.toml` - Project defaults (tracked in git)
2. `.erenshor/config.local.toml` - Local overrides (NOT tracked)

**Example `config.toml`:**

```toml
[global.unity]
path = "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity"
version = "2021.3.45f2"

[global.mediawiki]
api_url = "https://erenshor.wiki.gg/api.php"

[global.google_sheets]
credentials_file = "$HOME/.config/erenshor/google-credentials.json"

[variants.main]
app_id = "2382520"
database = "$REPO_ROOT/variants/main/erenshor-main.sqlite"
```

**Example `.erenshor/config.local.toml`:**

```toml
[global.steam]
username = "your_steam_username"

[global.mediawiki]
bot_username = "YourUsername@BotName"
bot_password = "your_bot_password"

[variants.playtest]
enabled = true  # Enable playtest variant
```

**Setting Up Credentials:**

**MediaWiki Bot Credentials:**

1. Log in to wiki account
2. Go to `Special:BotPasswords`
3. Create bot password with "Edit existing pages" grant
4. Add to `.erenshor/config.local.toml`

**Google Sheets Credentials:**

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project and enable Google Sheets API
3. Create service account with "Editor" role
4. Download JSON key file to `~/.config/erenshor/google-credentials.json`
5. Share spreadsheets with service account email

---

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/glockyco/erenshor-data-mining.git
cd erenshor-data-mining

# Install dependencies
uv sync --dev

# Install pre-commit hooks
uv run pre-commit install

# Verify setup
uv run pytest
```

### Testing

```bash
# Run all tests
uv run pytest

# With coverage
uv run pytest --cov

# Integration tests only
uv run pytest -m integration

# Watch mode
uv run pytest-watch

# Specific test
uv run pytest tests/test_wiki_generator.py::test_item_generation
```

Pre-commit hooks run linting and type checking only (no tests). Full test suite runs in CI on every push and PR.

### Code Quality

```bash
# Format code
uv run ruff format src/ tests/

# Lint code
uv run ruff check src/ tests/

# Type checking
uv run mypy src/

# Run all pre-commit hooks
uv run pre-commit run --all-files
```

### Adding New Content Types

**1. Unity Export (if new entity type)**

Create listener in `src/Assets/Editor/ExportSystem/AssetScanner/Listener/`:

```csharp
public class MyEntityListener : IAssetListener
{
    public void OnAsset(Object asset, Repository repository)
    {
        if (asset is MyScriptableObject myEntity)
        {
            var record = new MyEntityRecord { Id = myEntity.Id, Name = myEntity.Name };
            repository.Insert(record);
        }
    }
}
```

Register in `ExportBatch.cs`:

```csharp
scanner.RegisterListener(new MyEntityListener());
```

**2. Python Wiki Generation**

Create generator in `src/erenshor/application/generators/`:

```python
class MyEntityGenerator(WikiGenerator):
    def generate(self) -> Iterator[WikiPage]:
        entities = self.repository.get_all_my_entities()
        for entity in entities:
            content = self.render_template("my_entity.jinja2", entity=entity)
            yield WikiPage(title=entity.name, content=content)
```

**3. Wire Up CLI Command**

Add command in `src/erenshor/cli/commands/wiki.py`:

```python
@app.command()
def update_my_entities():
    """Update MyEntity wiki pages."""
    generator = MyEntityGenerator(...)
    for page in generator.generate():
        save_page(page)
```

### Continuous Integration

GitHub Actions runs on every push and PR:

-   Ruff linting and formatting
-   MyPy type checking
-   Gitleaks secret scanning
-   Full pytest suite with coverage

View results: [GitHub Actions](https://github.com/glockyco/erenshor-data-mining/actions)

### Git Workflow

Use [conventional commits](https://www.conventionalcommits.org/):

```bash
git checkout -b feature/my-new-feature
git add .
git commit -m "feat: add new content type"
git push origin feature/my-new-feature
```

Commit types: `feat:`, `fix:`, `docs:`, `style:`, `refactor:`, `perf:`, `test:`, `build:`, `ci:`, `chore:`, `revert:`

---

## Reference

### Project Structure

```
erenshor/
├── src/
│   ├── erenshor/           # Python package (CLI, services, formatters)
│   │   ├── cli/            # Typer CLI implementation
│   │   ├── application/    # Business services
│   │   ├── infrastructure/ # External integrations (Steam, Unity, AssetRipper)
│   │   ├── domain/         # Domain models
│   │   └── registry/       # Entity registries
│   └── Assets/Editor/      # Unity C# export scripts
├── variants/               # Working directories (NOT tracked)
│   ├── main/               # Main game files, Unity project, database
│   ├── playtest/           # Playtest variant
│   └── demo/               # Demo variant
├── tests/                  # Python test suite
├── docs/                   # Documentation
├── config.toml             # Project configuration
├── pyproject.toml          # Python dependencies
└── .erenshor/              # Local state and overrides (NOT tracked)
```

### Key Files

| File                                 | Purpose                           |
| ------------------------------------ | --------------------------------- |
| `config.toml`                        | Project configuration             |
| `.erenshor/config.local.toml`        | Local overrides                   |
| `variants/main/erenshor-main.sqlite` | Main database                     |
| `src/Assets/Editor/`                 | Unity export scripts              |
| `src/erenshor/`                      | Python package                    |
| `pyproject.toml`                     | Python dependencies and CLI entry |

### Troubleshooting

**Quick Diagnostics:**

```bash
uv run erenshor doctor       # System health check
uv run erenshor status       # Pipeline status
```

**Common Issues:**

-   Unity export failures → Check Unity version, symlinks, logs in `variants/{variant}/logs/`
-   Wiki upload errors → Verify credentials, test API access
-   Google Sheets permissions → Ensure service account has Editor access
-   Database missing → Re-run export, check backups
-   SteamCMD auth fails → Verify Steam credentials and game ownership
-   Python import errors → Run `uv sync --dev` to reinstall dependencies

See **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** for detailed solutions.
