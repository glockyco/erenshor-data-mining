# Erenshor Data Mining & Companion Tools

Tools for extracting Erenshor game data, building SQLite databases, publishing wiki and spreadsheet data, maintaining the interactive map, and shipping BepInEx companion mods.

## Links

- Erenshor on Steam: <https://store.steampowered.com/app/2382520/Erenshor/>
- Wiki: <https://erenshor.wiki.gg>
- Interactive map: <https://erenshor.compendiums.org>

## What this repository provides

- A Python CLI, `uv run erenshor`, for extraction, publishing, map, mod, capture, and development workflows.
- A game-data pipeline from Steam download to AssetRipper output, Unity batch export, raw SQLite, and clean SQLite.
- MediaWiki and Google Sheets publishing from the clean database.
- A SvelteKit/deck.gl interactive map deployed with Wrangler to Cloudflare Workers.
- BepInEx companion mods for live map integration, quest guidance, sprinting, screenshot cleanup, and map tile capture.

Core data pipeline:

```text
SteamCMD game files
  → AssetRipper Unity project
  → Unity batch export
      → raw SQLite database
      → exported images
  → clean SQLite database
      → MediaWiki pages
      → Google Sheets
      → interactive map data
```

Map and live integrations:

```text
clean SQLite database
  → interactive map data

MapTileCapture
  → map screenshots
  → map tiles
  → interactive map data

InteractiveMapCompanion
  → WebSocket live state
  → interactive map data
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `src/erenshor/` | Python CLI and pipeline implementation. |
| `src/Assets/Editor/` | Unity editor export scripts run during batch export. |
| `src/maps/` | SvelteKit interactive map website. |
| `src/mods/` | Native BepInEx/Lunaris companion mods and build/publish metadata. |
| `quest_guides/` | Generated and curated quest-guide data consumed by AdventureGuide. |
| `variants/` | Per-game-variant outputs: game files, Unity projects, databases, logs, backups, images, wiki output, and map data. |
| `.erenshor/` | Local state, logs, and config overrides. Gitignored. |
| `docs/` | Project notes, plans, and design docs. |

## Requirements

- Python 3.13 or newer.
- `uv` for Python dependency and tool management.
- Unity `2021.3.45f2`.
- AssetRipper.
- SteamCMD.
- A Steam account that owns Erenshor for download workflows.
- pnpm for the map frontend workspace.
- .NET SDK for native mod build/test workflows.

Local config supplies machine-specific paths and credentials. Do not commit local credentials.

## Configuration

Configuration is layered:

1. `config.toml` — project defaults, tracked in git.
2. `.erenshor/config.local.toml` — local overrides, gitignored.

Create the local config file before running workflows that need tool paths or credentials:

```bash
mkdir -p .erenshor
cp config.toml .erenshor/config.local.toml
```

Common local values:

```toml
[global.steam]
username = "your_steam_username"

[global.assetripper]
path = "/path/to/AssetRipper"

[global.mediawiki]
bot_username = "YourUsername@BotName"
bot_password = "your_bot_password"
```

The default variant is `main`. Use `--variant` or `-V` to target another variant:

```bash
uv run erenshor --variant playtest status
```

Configured variants:

| Variant | Steam app ID | Purpose |
| --- | --- | --- |
| `main` | `2382520` | Production release. |
| `playtest` | `3090030` | Beta testing. |
| `demo` | `2522260` | Free demo. |

## Quick start

```bash
uv sync --dev
uv run erenshor status
uv run erenshor extract download
uv run erenshor extract rip
uv run erenshor extract export
uv run erenshor extract build
```

The clean database for the default variant is written to:

```text
variants/main/erenshor-main.sqlite
```

Run `uv run erenshor --help` and `uv run erenshor <group> --help` for the current command surface.

## Common workflows

### Inspect local setup

```bash
uv run erenshor status
uv run erenshor config show
```

### Extract and build game data

```bash
uv run erenshor extract download
uv run erenshor extract rip
uv run erenshor extract export
uv run erenshor extract build
```

### Publish wiki output

```bash
uv run erenshor wiki fetch
uv run erenshor wiki generate
uv run erenshor wiki deploy
```

### Publish Google Sheets

```bash
uv run erenshor sheets list
uv run erenshor sheets deploy
```

### Process and upload images

```bash
uv run erenshor images process
uv run erenshor images compare
uv run erenshor images report
uv run erenshor images upload
```

### Run and deploy the interactive map

```bash
uv run erenshor maps dev
uv run erenshor maps build
uv run erenshor maps preview
uv run erenshor maps deploy
uv run erenshor maps thumbnails
```

The map can also be run through the pnpm workspace scripts from the repository root:

```bash
pnpm dev
pnpm build
pnpm preview
pnpm check
pnpm lint
```

### Build and deploy companion mods

Every maintained mod has native BepInEx and Lunaris targets. Both loaders may
remain installed in one game installation. Deployment activates exactly one by
switching the root `winhttp.dll` proxy. Select the game variant with `-V`:

```bash
uv run erenshor -V playtest mod setup
uv run erenshor -V playtest mod build --loader all
uv run erenshor -V playtest mod status
uv run erenshor -V playtest mod deploy --loader lunaris
uv run erenshor -V playtest mod deploy --loader bepinex
uv run erenshor mod thunderstore --dry-run
```

Use `mod deploy --mod <id> --loader <bepinex|lunaris>` for one mod and
`mod activate --loader <bepinex|lunaris>` to switch an installed loader without
rebuilding. Standard CrossOver installs are resolved from `-V main`,
`-V playtest`, or `-V demo`; non-standard installs use
`[variants.<name>] game_install` in `.erenshor/config.local.toml`. See the
`mod-pipeline` skill for package publication and proxy safety details.

### Capture map tiles

```bash
uv run erenshor capture status
uv run erenshor capture budget
uv run erenshor capture run
uv run erenshor capture tile
```

### Compile AdventureGuide data

```bash
uv run erenshor guide compile
```

The AdventureGuide mod embeds the compiled guide graph from `quest_guides/guide.json`.

### Runtime C# REPL / HotRepl workflows

HotRepl runs under BepInEx. With the game closed, select that loader and launch
the default `main` variant through Steam. HotRepl remains installed between
sessions, so it is not redeployed for each launch.

```bash
uv run erenshor mod activate --loader bepinex
uv run erenshor mod launch
uv run erenshor eval ping
uv run erenshor eval run 'SceneManager.GetActiveScene().name'
uv run erenshor eval watch 'GameData.PlayerControl.transform.position'
uv run erenshor eval complete 'Camera.main.'
uv run erenshor eval reset
```

The `runtime-eval` skill documents current multi-assembly host installation,
loader selection, runtime inspection, and ScriptEngine reloads.

## Companion mods

### Player-facing mods

| Mod | Purpose |
| --- | --- |
| `AdventureGuide` | In-game quest guide, tracker overlay, navigation arrow, optional ground path, world markers, and per-character tracking state. |
| `InteractiveMapCompanion` | Live entity tracking for the interactive map. Runs a local WebSocket server on port `18585` by default and can render the map as an in-game overlay. |
| `Sprint` | Configurable sprint key, hold/toggle modes, and configurable speed multiplier. |
| `JusticeForF7` | Extends the game’s F7 hide-UI mode to hide world-space UI such as nameplates, damage numbers, target rings, XP orbs, cast bars, and loot prompts. |

### Legacy and internal mods

| Mod | Purpose |
| --- | --- |
| `InteractiveMapsCompanion` | Legacy player-position broadcast mod on port `18584`. Kept separate from the current `InteractiveMapCompanion`. |
| `MapTileCapture` | Internal capture tool for rendering orthographic map screenshots used by the tile pipeline. |

## Interactive map

The map website lives in `src/maps/` and is packaged as `erenshor-maps` in the pnpm workspace. It uses SvelteKit, deck.gl, Tailwind, bits-ui, and SQLite data loaded through sql.js in the browser, with prerendered route data for static builds.

Live mode connects to `InteractiveMapCompanion` over WebSocket. The default local endpoint is:

```text
ws://localhost:18585
```

Tracked live entity types include the player, SimPlayers, pets, friendly NPCs, and enemies.

## Development

Install development dependencies:

```bash
uv sync --dev
pnpm install
```

Install Git hooks:

```bash
pnpm exec lefthook install --reset-hooks-path
```

Validate hook configuration and run hook groups directly:

```bash
pnpm exec lefthook validate
pnpm exec lefthook run pre-commit
pnpm exec lefthook run pre-push
```

The pre-commit hook runs Gitleaks when `gitleaks` is installed locally; CI
always runs the repository security scan.

Run checks for the area you changed:

```bash
# Python
uv run ruff format src/ tests/
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest
uv run pytest tests/unit -q --tb=short
uv run pytest tests/integration -v

# Map frontend
pnpm check
pnpm lint
pnpm build

# Lua modules
pnpm exec stylua --check wiki/modules

# C# formatting used by hooks
bash src/mods/run-csharpier.sh
```

The CLI also exposes test helpers:

```bash
uv run erenshor test
uv run erenshor test unit
uv run erenshor test integration
```

CI runs on pushes and pull requests to `main`. The workflow covers Python linting, formatting checks, type checking, pytest, Gitleaks scanning, mod metadata validation, and targeted C# formatting/tests for `InteractiveMapCompanion`.

## Troubleshooting

### Check setup first

```bash
uv run erenshor status
```

This reports configured tool paths and database state.

### Local logs

```text
.erenshor/logs/
variants/{variant}/logs/
variants/{variant}/logs/export_*.log
```

### AssetRipper or Unity paths are wrong

Update `.erenshor/config.local.toml`, then rerun:

```bash
uv run erenshor status
```

### Map live mode does not connect

Confirm the game is running with `InteractiveMapCompanion` installed, then check that the map is connecting to:

```text
ws://localhost:18585
```

The legacy `InteractiveMapsCompanion` uses port `18584`; do not mix the two ports.

## License

MIT. See [LICENSE](LICENSE).
