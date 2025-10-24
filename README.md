# Erenshor Data Mining & Wiki Publishing Pipeline

> **A complete automated pipeline for extracting game data from Erenshor and publishing to wikis, spreadsheets, and structured data formats.**

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Unity](https://img.shields.io/badge/unity-2021.3.45f2-black.svg)](https://unity.com/)
[![CI](https://github.com/glockyco/erenshor-wiki/actions/workflows/ci.yml/badge.svg)](https://github.com/glockyco/erenshor-wiki/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-766+%20passing-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## What is This?

**Erenshor** is a single-player RPG that captures the soul of classic MMOs - built for players who miss the journey.

**This project** automates the entire data mining workflow from Steam download to wiki publication:

```
Steam → Game Files → Unity Project → SQLite Database → Wiki/Sheets
```

It handles downloading game files, extracting Unity assets, exporting structured data, and publishing formatted content to MediaWiki, Google Sheets, JSON, and CSV.

### Key Features

- 🎮 **Full Pipeline Automation** - One command from download to deployment
- 🔄 **Multi-Variant Support** - Handle main game, playtest, and demo separately
- 📊 **Multiple Output Formats** - MediaWiki, Google Sheets, JSON, CSV
- 🐍 **Pure Python CLI** - Built with Typer for type-safe command handling
- 🧪 **Comprehensive Testing** - 766+ unit and integration tests
- 📝 **29 Junction Tables** - Fully normalized database schema
- 🚀 **Streaming Architecture** - Memory-efficient processing of thousands of entities
- 🎨 **Rich Terminal UI** - Real-time progress tracking

---

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Development](#development)
- [Documentation](#documentation)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Quick Start

### Prerequisites

Before you begin, ensure you have:

- **Unity 2021.3.45f2** (exact version required for game compatibility)
- **Python 3.13+** (for wiki generation and data processing)
- **SteamCMD** (for automated game downloads)
- **AssetRipper** (for Unity asset extraction)
- **uv** (Python package manager - recommended)
- **Steam Account** with Erenshor ownership
- **8GB+ RAM** and **20GB+ disk space** per variant

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/erenshor.git
cd erenshor

# 2. Install Python dependencies (using uv - recommended)
uv sync --dev

# Alternative: using pip
pip install -e ".[dev]"

# 3. Set up local configuration
cp config.toml .erenshor/config.local.toml
# Edit .erenshor/config.local.toml with your Unity, SteamCMD, and AssetRipper paths

# 4. Set up credentials (for wiki/sheets publishing)
cp .env.example .env
# Edit .env with your bot credentials (see instructions in file)

# 5. Verify installation
uv run erenshor doctor
```

### Your First Export

```bash
uv run erenshor --help              # Show all commands
uv run erenshor version             # Show version
uv run erenshor status              # Check system status
uv run erenshor doctor              # Validate configuration

# Wiki operations
uv run erenshor wiki fetch --all    # Fetch wiki pages
uv run erenshor wiki update         # Update content

# Google Sheets deployment
uv run erenshor sheets deploy --all-sheets

# Maps development
uv run erenshor maps dev            # Start dev server
uv run erenshor maps build          # Build for production
```

Expected output: `variants/main/erenshor-main.sqlite` (50MB+ database) and generated wiki pages in `wiki_updated/`.

---

## Architecture

### Complete Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     ERENSHOR DATA PIPELINE                      │
└─────────────────────────────────────────────────────────────────┘

  Steam (Game Files)
       ↓
  [SteamCMD - Bash CLI]
       ↓
  Game Directory (variants/{variant}/game/)
       ↓
  [AssetRipper - Bash CLI]
       ↓
  Unity Project (variants/{variant}/unity/)
       ↓
  [Unity Editor Scripts - C#]
       ↓
  SQLite Database (erenshor-{variant}.sqlite)
       ↓
  [Python Formatters & Publishers]
       ↓
  ┌──────────┬──────────┬──────────┬──────────┐
  │ MediaWiki│  Sheets  │   JSON   │   CSV    │
  └──────────┴──────────┴──────────┴──────────┘
```

### Pure Python CLI Architecture

The project uses a **pure Python CLI** built with Typer:

```
┌─────────────────────────────────────────┐
│      Python CLI (Typer Framework)      │
│  • Pipeline automation                  │
│  • System operations                    │
│  • Unity/Steam/AssetRipper integration  │
│  • Database operations                  │
│  • Wiki generation & publishing         │
│  • Google Sheets deployment             │
│  • Data formatting & transformation     │
└─────────────────────────────────────────┘
```

**Entry Point**: `uv run erenshor` (console script defined in pyproject.toml)

### Three-Layer Data Flow

1. **Export Layer** (Unity C# → SQLite)
   - Unity Editor scripts extract game data from ScriptableObjects
   - Custom listeners for each entity type (items, characters, quests, etc.)
   - 29 junction tables for normalized many-to-many relationships
   - Location: `src/Assets/Editor/`

2. **Format Layer** (SQLite → Content)
   - Python generators stream entities from database
   - Jinja2 templates render MediaWiki markup
   - Custom formatters for Google Sheets, JSON, and CSV
   - Location: `src/erenshor/application/`

3. **Deploy Layer** (Content → Destinations)
   - MediaWiki API client for wiki uploads
   - Google Sheets API v4 for spreadsheet publishing
   - File system writers for local JSON/CSV output
   - Location: `src/erenshor/infrastructure/`

### Multi-Variant Support

The project handles **three game variants** independently:

| Variant   | App ID  | Description                    | Use Case                          |
|-----------|---------|--------------------------------|-----------------------------------|
| **main**  | 2382520 | Production release             | Public wiki content               |
| **playtest** | 3090030 | Private beta/alpha testing  | Preview upcoming changes          |
| **demo**  | 2522260 | Free demo version              | Demo-specific documentation       |

Each variant maintains:
- Separate game downloads (`variants/{variant}/game/`)
- Separate Unity projects (`variants/{variant}/unity/`)
- Separate databases (`erenshor-{variant}.sqlite`)
- Separate Google Sheets spreadsheets
- Separate logs and backups

---

## Features

### Python CLI Commands

Complete pipeline automation from game download to deployment:

```bash
# System commands
uv run erenshor version             # Show version
uv run erenshor status              # Show status
uv run erenshor doctor              # Health check

# Extraction pipeline (download → rip → export)
uv run erenshor extract download    # Download from Steam
uv run erenshor extract rip         # Extract Unity project
uv run erenshor extract export      # Export to SQLite
uv run erenshor extract full        # Complete pipeline

# Configuration
uv run erenshor config show         # View configuration
uv run erenshor config validate     # Validate configuration
```

### Wiki Generation

Sophisticated wiki content generation and publishing:

```bash
# Update wiki pages
uv run erenshor wiki update         # Update all wiki content

# Use global options for control
uv run erenshor wiki update --dry-run    # Preview only
uv run erenshor wiki update --verbose    # Detailed output
```

### Google Sheets Deployment

Deploy formatted data to Google Sheets spreadsheets:

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

**Available Sheets**:
- items, item-stats, armor, weapons, consumables
- characters, character-vendor-items
- spells, skills, abilities, attack-spells, buff-spells
- quests, quest-rewards, quest-required-items
- loot-tables, drop-chances
- spawn-points, patrol-points
- crafting-recipes, gathering-nodes

### Content Types

Automatic generation for:

- **Items** - Weapons, armor, consumables, ability books, auras (3,000+ items)
- **Characters** - NPCs, bosses, rare spawns with stats and loot tables (1,500+ characters)
- **Abilities** - Spells and skills with detailed mechanics (800+ abilities)
- **Quests** - Quest chains, rewards, and requirements (500+ quests)
- **Fishing** - Fishing zones and catchable items
- **Overviews** - Category summaries and item lists

### Advanced Features

- **Streaming Architecture** - Memory-efficient processing of thousands of entities
- **Parser-Driven Updates** - AST-based transformations (no regex), deterministic output
- **Real-Time Progress** - Rich terminal UI with live progress bars and metrics
- **Event-Driven Reporting** - Structured JSONL logs with detailed metrics
- **Validation System** - Structure checks before upload prevent malformed content
- **Registry System** - Resolves naming conflicts, maps entities to wiki pages
- **Dry-Run Mode** - Preview all changes without publishing
- **Diff Tool** - Compare database vs. wiki content side-by-side

---

## Installation

### System Requirements

- **Unity 2021.3.45f2** (exact version - must match game's Unity version)
- **Python 3.13+**
- **macOS, Linux, or Windows** (with WSL for Bash scripts)
- **8GB+ RAM**
- **20GB+ disk space** per game variant

### Required Software

#### 1. Unity 2021.3.45f2

Download Unity Hub and install the exact version:
- [Unity Hub Download](https://unity.com/download)
- Install Unity 2021.3.45f2 from the Archive section

#### 2. SteamCMD

Install SteamCMD for automated game downloads:

**macOS (using Homebrew)**:
```bash
brew install steamcmd
```

**Linux (Ubuntu/Debian)**:
```bash
sudo apt-get install steamcmd
```

**Manual Installation**:
- [SteamCMD Documentation](https://developer.valvesoftware.com/wiki/SteamCMD)

#### 3. AssetRipper

Download and install AssetRipper for Unity asset extraction:
- [AssetRipper Releases](https://github.com/AssetRipper/AssetRipper/releases)
- Download the appropriate version for your OS
- Extract to a permanent location (e.g., `~/Applications/AssetRipper/`)

#### 4. Python 3.13+ and uv

**Using uv (recommended)**:
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv
```

**Using system Python**:
```bash
# Ensure Python 3.13+ is installed
python3 --version

# Install pip if needed
python3 -m ensurepip
```

### Project Setup

#### 1. Clone Repository

```bash
git clone https://github.com/yourusername/erenshor.git
cd erenshor
```

#### 2. Install Python Dependencies

**With uv (recommended)**:
```bash
uv sync --dev
```

**With pip**:
```bash
pip install -e ".[dev]"
```

#### 3. Configure Tools

Create local configuration file:

```bash
cp config.toml .erenshor/config.local.toml
```

Edit `.erenshor/config.local.toml` with your tool paths:

```toml
[global.unity]
path = "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity"
version = "2021.3.45f2"

[global.steam]
username = "your_steam_username"

[global.assetripper]
path = "/path/to/AssetRipper/AssetRipper.ConsoleApp"
```

#### 4. Configure Credentials (Optional)

For MediaWiki and Google Sheets publishing:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# MediaWiki bot credentials (from Special:BotPasswords)
ERENSHOR_BOT_USERNAME=YourUsername@BotName
ERENSHOR_BOT_PASSWORD=your_bot_password

# Google Sheets (path to service account JSON)
ERENSHOR_GOOGLE_SHEETS_CREDENTIALS_FILE=$HOME/.config/erenshor/google-credentials.json
```

**Getting MediaWiki Bot Credentials**:
1. Log in to your wiki account
2. Go to `Special:BotPasswords`
3. Create a new bot password with "Edit existing pages" grant
4. Copy username (format: `YourUsername@BotName`) and password to `.env`

**Getting Google Sheets Credentials**:
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable Google Sheets API
4. Create a service account with "Editor" role
5. Download the JSON key file
6. Save to `~/.config/erenshor/google-credentials.json`
7. Share your spreadsheets with the service account email

#### 5. Verify Installation

```bash
uv run erenshor doctor
```

This checks:
- ✅ Unity installation and version
- ✅ Python environment
- ✅ SteamCMD availability
- ✅ AssetRipper installation
- ✅ Configuration validity
- ✅ Required dependencies

---

## Usage

### Common Workflows

#### Full Pipeline Update (After Game Patch)

```bash
# 1. Run complete extraction pipeline (download → rip → export)
uv run erenshor extract full

# 2. Update wiki content
uv run erenshor wiki update

# 3. Deploy to Google Sheets
uv run erenshor sheets deploy --all-sheets

# Or run individual extraction steps:
uv run erenshor extract download    # Download from Steam
uv run erenshor extract rip          # Extract Unity project
uv run erenshor extract export       # Export to SQLite
```

#### Managing Multiple Variants

```bash
# Update playtest variant
uv run erenshor extract full --variant playtest

# Compare databases between variants
sqlite3 variants/main/erenshor-main.sqlite "SELECT COUNT(*) FROM Items"
sqlite3 variants/playtest/erenshor-playtest.sqlite "SELECT COUNT(*) FROM Items"

# Check status
uv run erenshor status
```

#### Google Sheets Workflow

```bash
# 1. Preview deployment (dry-run)
uv run erenshor sheets deploy --all-sheets --dry-run

# 2. Deploy to spreadsheet
uv run erenshor sheets deploy --all-sheets

# Deploy specific sheets only
uv run erenshor sheets deploy --sheets items characters quests
```

### CLI Commands

For complete command reference:
```bash
uv run erenshor --help              # Show all commands
uv run erenshor <command> --help    # Command-specific help
```

See **[CLAUDE.md](CLAUDE.md)** for detailed command documentation and usage examples.

---

## Configuration

### Configuration Files

The project uses a layered configuration system:

```
Priority (highest to lowest):
1. Environment variables (ERENSHOR_*)
2. .env file (gitignored, for secrets)
3. .erenshor/config.local.toml (gitignored, for local overrides)
4. config.toml (tracked, project defaults)
```

### Main Configuration (`config.toml`)

Project-wide settings:

```toml
version = "3.0"
default_variant = "main"

[global.unity]
path = "/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity"
version = "2021.3.45f2"
timeout = 1800  # 30 minutes

[global.assetripper]
path = "$HOME/Projects/AssetRipper/AssetRipper.GUI.Free"
port = 8080
timeout = 3600  # 60 minutes

[global.database]
validate = true

[global.mediawiki]
api_url = "https://erenshor.wiki.gg/api.php"
api_batch_size = 25
upload_batch_size = 10
upload_delay = 1.0

[global.google_sheets]
credentials_file = "$HOME/.config/erenshor/google-credentials.json"
batch_size = 1000
max_retries = 3

[variants.main]
enabled = true
app_id = "2382520"
database = "$REPO_ROOT/variants/main/erenshor-main.sqlite"

[variants.main.google_sheets]
spreadsheet_id = "1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E"
```

### Local Overrides (`.erenshor/config.local.toml`)

Machine-specific settings (NOT tracked in git):

```toml
[global.steam]
username = "your_steam_username"

[global.unity]
path = "/custom/path/to/Unity"

[variants.playtest]
enabled = true  # Enable playtest variant
```

### Environment Variables (`.env`)

Secrets and runtime overrides (NOT tracked in git):

```bash
# Steam credentials
ERENSHOR_STEAM_USERNAME=your_username

# MediaWiki bot credentials
ERENSHOR_BOT_USERNAME=YourBot@WikiJob
ERENSHOR_BOT_PASSWORD=your_bot_password

# Google Sheets
ERENSHOR_GOOGLE_SHEETS_CREDENTIALS_FILE=/path/to/credentials.json

# Path overrides
ERENSHOR_DB_PATH=/custom/path/erenshor.sqlite
```

### Variable Expansion

Configuration supports path expansion:

- `$REPO_ROOT` - Repository root (auto-detected from git)
- `$HOME` - User's home directory
- `~` - User's home directory (in paths)

---

## Project Structure

```
erenshor/
├── src/
│   ├── erenshor/           # Python package (CLI, services, formatters)
│   │   ├── cli/            # Typer CLI implementation
│   │   ├── application/    # Business services
│   │   ├── infrastructure/ # External integrations (Steam, Unity, AssetRipper)
│   │   ├── domain/         # Domain models
│   │   └── registry/       # Entity registries
│   └── Assets/Editor/      # Unity C# export scripts (symlinked to Unity projects)
├── variants/               # Working directories (NOT tracked in git)
│   ├── main/               # Main game: game files, Unity project, database
│   ├── playtest/           # Playtest variant
│   └── demo/               # Demo variant
├── legacy/                 # Legacy bash CLI (archived, not used)
│   └── cli/                # Old bash implementation
├── docs/                   # Documentation (architecture, troubleshooting, guides)
├── tests/                  # Python test suite (766+ tests)
├── config.toml             # Main configuration
├── pyproject.toml          # Python dependencies and console script entry point
└── .erenshor/              # Local state and overrides (NOT tracked)
```

**Key Directories**:
- `src/erenshor/` - Python package (CLI, services, infrastructure)
- `src/Assets/Editor/` - Unity C# export scripts
- `variants/` - Per-variant game files and databases
- `tests/` - Comprehensive test suite
- `docs/` - Architecture and troubleshooting
- `legacy/cli/` - Old bash CLI (archived)

See **[CLAUDE.md](CLAUDE.md)** for complete directory structure with all subdirectories.

---

## Development

### Prerequisites for Development

- All installation requirements (Unity, Python, etc.)
- Git for version control
- Code editor (VS Code, PyCharm, or similar)
- SQLite browser for database inspection

### Setting Up Development Environment

```bash
# 1. Clone and set up project
git clone https://github.com/yourusername/erenshor.git
cd erenshor

# 2. Install development dependencies
uv sync --dev

# 3. Install pre-commit hooks
uv run pre-commit install

# 4. Run tests to verify setup
uv run pytest
```

### Running Tests

```bash
# Run all tests locally
uv run pytest

# Run with coverage report
uv run pytest --cov

# Run integration tests only
uv run pytest -m integration

# Run tests in watch mode (re-run on file changes)
uv run pytest-watch

# Run specific test file
uv run pytest tests/test_wiki_generator.py

# Run specific test
uv run pytest tests/test_wiki_generator.py::test_item_generation
```

**Note**: Tests are NOT run in pre-commit hooks (too slow). Pre-commit only runs fast linting and type checking. Full test suite runs automatically in CI on every push and PR.

### Code Quality

```bash
# Format code (Ruff formatter)
uv run ruff format src/ tests/

# Lint code (Ruff linter)
uv run ruff check src/ tests/

# Type checking (mypy)
uv run mypy src/

# Run all pre-commit hooks (fast checks only, no tests)
uv run pre-commit run --all-files
```

### Continuous Integration

GitHub Actions automatically runs on every push and pull request:

- **Linting**: Ruff code style and formatting checks
- **Type Checking**: MyPy static type validation
- **Security**: Gitleaks secret scanning
- **Testing**: Full pytest suite (766+ tests) with coverage reporting

View CI results: [GitHub Actions](https://github.com/glockyco/erenshor-wiki/actions)

### Adding New Content Types

#### 1. Unity Export (if new entity type)

Create Unity C# listener in `src/Assets/Editor/ExportSystem/AssetScanner/Listener/`:

```csharp
public class MyEntityListener : IAssetListener
{
    public void OnAsset(Object asset, Repository repository)
    {
        if (asset is MyScriptableObject myEntity)
        {
            var record = new MyEntityRecord
            {
                Id = myEntity.Id,
                Name = myEntity.Name,
                // ... map fields
            };
            repository.Insert(record);
        }
    }
}
```

Register in `ExportBatch.cs`:
```csharp
scanner.RegisterListener(new MyEntityListener());
```

#### 2. Python Wiki Generation

Create generator in `src/erenshor/application/generators/`:

```python
class MyEntityGenerator(WikiGenerator):
    def generate(self) -> Iterator[WikiPage]:
        entities = self.repository.get_all_my_entities()
        for entity in entities:
            content = self.render_template("my_entity.jinja2", entity=entity)
            yield WikiPage(title=entity.name, content=content)
```

Create template in `src/erenshor/templates/`:

```jinja2
{# my_entity.jinja2 #}
{{Infobox My Entity
|name = {{ entity.name }}
|description = {{ entity.description }}
}}

{{ entity.description }}

== Details ==
...
```

#### 3. Wire Up CLI Command

Add command in `src/erenshor/presentation/cli/commands/wiki.py`:

```python
@app.command()
def update_my_entities():
    """Update MyEntity wiki pages."""
    generator = MyEntityGenerator(...)
    for page in generator.generate():
        save_page(page)
```

### Code Style Guidelines

**Python**:
- Follow PEP 8
- Use type hints for all function signatures
- Docstrings for public functions (Google style)
- Max line length: 100 characters
- Use domain-driven design patterns

**C#**:
- Follow C# naming conventions (PascalCase for methods, camelCase for fields)
- Use explicit types (avoid `var` unless obvious)
- XML documentation comments for public APIs
- Keep Unity Editor scripts in `src/Assets/Editor/` only

**Bash**:
- Use `set -euo pipefail` at script start
- Quote all variable expansions
- Use functions for reusable code
- Prefix functions with `command_` for commands

### Testing Guidelines

- Write tests for all new features
- Maintain >95% test coverage
- Use pytest fixtures for common setup
- Mock external dependencies (database, API calls)
- Integration tests marked with `@pytest.mark.integration`

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/my-new-feature

# Make changes and commit
git add .
git commit -m "feat: add new content type"

# Push and create PR
git push origin feature/my-new-feature
```

Use [conventional commits](https://www.conventionalcommits.org/):
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test changes
- `refactor:` - Code refactoring

---

## Documentation

### Primary Documentation

- **[README.md](README.md)** (this file) - Project overview and getting started
- **[CLAUDE.md](CLAUDE.md)** - Detailed AI context: architecture, CLI commands, Python integration
- **[README_WIKI.md](README_WIKI.md)** - Python wiki system: generators, transformers, publishers

### Architecture Documentation

- **[docs/ARCHITECTURE_MERGE.md](docs/ARCHITECTURE_MERGE.md)** - Detailed architecture and design decisions
- **[docs/PYTHON_INTEGRATION.md](docs/PYTHON_INTEGRATION.md)** - Bash ↔ Python integration guide
- **[docs/GOOGLE_SHEETS_DEPLOYMENT.md](docs/GOOGLE_SHEETS_DEPLOYMENT.md)** - Google Sheets deployment guide
- **[docs/PHASE3_COMPLETION_REPORT.md](docs/PHASE3_COMPLETION_REPORT.md)** - Phase 3 completion report

### Developer Guides

- **[AGENTS.md](AGENTS.md)** - AI agent collaboration guidelines
- **[GEMINI.md](GEMINI.md)** - Google Gemini integration guide
- **[.env.example](.env.example)** - Environment variable documentation

### External Resources

- [Erenshor on Steam](https://store.steampowered.com/app/2382520/Erenshor/)
- [Erenshor Wiki](https://erenshor.wiki.gg)
- [Unity Documentation](https://docs.unity3d.com/2021.3/Documentation/Manual/)
- [AssetRipper Documentation](https://github.com/AssetRipper/AssetRipper/wiki)
- [MediaWiki API Documentation](https://www.mediawiki.org/wiki/API:Main_page)
- [Google Sheets API Documentation](https://developers.google.com/sheets/api)

---

## Troubleshooting

For detailed troubleshooting guides, see **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)**.

**Quick Diagnostics**:
```bash
uv run erenshor doctor       # System health check
uv run erenshor status       # Pipeline status
```

**Common Issues**:
- Unity export failures → Check Unity version, symlinks, logs
- Wiki upload errors → Verify credentials, test API access
- Google Sheets permissions → Ensure service account has Editor access
- Database missing → Re-run export, check backups
- SteamCMD auth fails → Verify Steam credentials and game ownership
- Python import errors → Check environment, reinstall dependencies

See the [full troubleshooting guide](docs/TROUBLESHOOTING.md) for detailed solutions and error reference table.
---

## Contributing

Contributions are welcome! Whether you're fixing bugs, adding features, improving documentation, or helping with testing.

### How to Contribute

1. **Fork the Repository**
   ```bash
   # Fork on GitHub, then:
   git clone https://github.com/YOUR_USERNAME/erenshor.git
   cd erenshor
   ```

2. **Create a Feature Branch**
   ```bash
   git checkout -b feature/my-awesome-feature
   ```

3. **Make Your Changes**
   - Follow code style guidelines
   - Add tests for new features
   - Update documentation

4. **Run Tests and Quality Checks**
   ```bash
   uv run pytest                    # Run tests
   uv run ruff format src/ tests/   # Format code
   uv run ruff check src/ tests/    # Lint code
   uv run mypy src/                 # Type check
   ```

5. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "feat: add awesome feature"
   ```
   Use [conventional commits](https://www.conventionalcommits.org/):
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation
   - `test:` - Tests
   - `refactor:` - Code refactoring
   - `chore:` - Maintenance

6. **Push and Create Pull Request**
   ```bash
   git push origin feature/my-awesome-feature
   ```
   Then create a PR on GitHub.

### Contribution Guidelines

- **Code Quality**: Maintain high code quality and test coverage
- **Documentation**: Update docs for any user-facing changes
- **Tests**: Add tests for new features and bug fixes
- **Commit Messages**: Use conventional commits format
- **No Secrets**: Never commit credentials, API keys, or `.env` files
- **Only Modify `src/`**: Never change original game files outside `src/`

### Areas for Contribution

- 🐛 **Bug Fixes** - Fix issues and edge cases
- ✨ **New Features** - Add new content types, formatters, or publishers
- 📚 **Documentation** - Improve guides, add examples, fix typos
- 🧪 **Tests** - Improve test coverage and add integration tests
- 🎨 **Templates** - Enhance Jinja2 templates for wiki pages
- 🚀 **Performance** - Optimize database queries and streaming
- 🔧 **Tooling** - Improve CLI, add validation, enhance error messages

### Questions?

- Open a GitHub issue for bugs or feature requests
- Join the [Erenshor Discord](https://discord.gg/erenshor) for community discussion
- Check existing documentation for common questions

---

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### Third-Party Licenses

This project uses several open-source tools:

- **Erenshor** - Game content owned by Burgee Media
- **Unity** - Unity Technologies (Personal license)
- **AssetRipper** - MIT License
- **SteamCMD** - Valve Corporation
- **Python Libraries** - Various open-source licenses (see `pyproject.toml`)

---

## Acknowledgments

### Credits

Created for the Erenshor community by the wiki team.

**Special Thanks To**:

- **Burgee Media** - For creating Erenshor, an amazing single-player MMO experience
- **Erenshor Wiki Community** - Contributors, editors, and players who make the wiki valuable
- **AssetRipper Developers** - For the excellent Unity asset extraction tool
- **All Contributors** - Everyone who has contributed code, documentation, or bug reports

### Related Projects

- [Erenshor on Steam](https://store.steampowered.com/app/2382520/Erenshor/)
- [Erenshor Wiki](https://erenshor.wiki.gg)
- [AssetRipper](https://github.com/AssetRipper/AssetRipper)
- [SteamCMD](https://developer.valvesoftware.com/wiki/SteamCMD)

### Community

- **Discord**: [Join Erenshor Community](https://discord.gg/erenshor)
- **Reddit**: [r/Erenshor](https://reddit.com/r/Erenshor)
- **Wiki**: [erenshor.wiki.gg](https://erenshor.wiki.gg)

---

## Quick Reference

### Essential Commands

```bash
uv run erenshor version             # Show version
uv run erenshor status              # Show status
uv run erenshor doctor              # Health check
uv run erenshor config show         # View configuration
uv run erenshor test                # Run all tests
uv run erenshor test unit           # Run unit tests only

# Maps commands
uv run erenshor maps dev            # Start dev server
uv run erenshor maps build          # Build for production
uv run erenshor maps deploy         # Deploy to Cloudflare

# Direct pytest (alternative)
uv run pytest                       # All tests
uv run pytest -m unit               # Unit tests only
uv run pytest --cov                 # With coverage
```

### Important Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Python dependencies and console script entry point |
| `config.toml` | Project configuration |
| `.erenshor/config.local.toml` | Local overrides |
| `.env` | Secrets and credentials |
| `variants/main/erenshor-main.sqlite` | Main database |
| `src/Assets/Editor/` | Unity export scripts |
| `src/erenshor/` | Python package (CLI, services, infrastructure) |
| `docs/` | Architecture documentation |

### Key Concepts

- **Variants**: Separate pipelines for main, playtest, and demo
- **Pure Python CLI**: Built with Typer for type-safe command handling
- **Three-Layer Data Flow**: Export (Unity) → Format (Python) → Deploy (API)
- **Symlinks**: `src/Assets/Editor/` linked into Unity projects
- **Streaming**: Memory-efficient processing of large datasets
- **Dry-Run**: Preview changes before publishing

---

**Happy data mining! 🎮⛏️**
