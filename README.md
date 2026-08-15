# Erenshor Data Mining & Companion Tools

Tools for extracting Erenshor game data, building SQLite databases, publishing wiki and spreadsheet data, maintaining the interactive map, and shipping BepInEx companion mods.

## Links

- Erenshor on Steam: <https://store.steampowered.com/app/2382520/Erenshor/>
- Wiki: <https://erenshor.wiki.gg>
- Interactive map: <https://erenshor.compendiums.org>

## What this repository provides

- A Python CLI, `erenshor`, for extraction, publishing, map, mod, capture, and development workflows.
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

The `flake.nix` dev shell provides the whole command-line toolchain at the versions CI uses:

- Python 3.14 with the `uv.lock` environment built reproducibly by uv2nix. `uv` remains the command runner and lockfile editor.
- .NET SDK 9 and 10 for the native tools, mods, and their tests.
- Node 22 and pnpm 10 for the map frontend workspace.
- AssetRipper for `extract rip`.
- `sqlite3` for ad-hoc database inspection.

```bash
nix develop           # or `direnv allow` once, with nix-direnv
```

Every `erenshor ...` command in this README assumes that shell.

Three things the dev shell cannot supply, because they are licensed, interactive, or platform-specific:

- Unity `2021.3.45f2`, installed through Unity Hub and activated with a Unity account. `extract export` refuses to run against any other version.
- SteamCMD and a Steam account that owns Erenshor, for `extract download`. Not needed if `game_files` points at a copy of the game you already have installed.
- CrossOver or another Windows runtime, for launching the game and its companion mods on macOS.

Local config supplies machine-specific paths and credentials. Do not commit local credentials.

## Configuration

Configuration is layered:

1. `config.toml` — project defaults, tracked in git.
2. `.erenshor/config.local.toml` — local overrides, gitignored.

Create the local config file before running workflows that need tool paths or credentials:

```bash
mkdir -p .erenshor
cp config.local.toml.example .erenshor/config.local.toml
```

Common local values:

```toml
[global.steam]
username = "your_steam_username"

[global.mediawiki]
bot_username = "YourUsername@BotName"
bot_password = "your_bot_password"

[variants.main]
# Rip an installation you already have instead of downloading a second copy.
game_files = "$HOME/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/Erenshor"
```

AssetRipper needs no entry: the tracked config resolves it from PATH, which the dev shell populates.

The default variant is `main`. Use `--variant` or `-V` to target another variant:

```bash
erenshor --variant playtest status
```

Configured variants:

| Variant | Steam app ID | Purpose |
| --- | --- | --- |
| `main` | `2382520` | Production release. |
| `playtest` | `3090030` | Beta testing. |
| `demo` | `2522260` | Free demo. |

## Quick start

Install the locked JavaScript dependencies and .NET tools explicitly. The Python
environment is built from `uv.lock` when Nix realizes the development shell. The
bootstrap app works outside an active dev shell and fails rather than rewriting a
stale lockfile:

```bash
nix run .#bootstrap
```

Then enter the development shell and run the data pipeline. Unity editor packages
remain an extraction-specific setup step because they require the external Unity
installation:

```bash
nix develop
erenshor status
erenshor extract download     # skip when game_files points at an existing install
erenshor extract packages     # Editor NuGet dependencies, once per checkout
erenshor extract rip
erenshor extract export
erenshor extract code-facts
erenshor extract build
```

The clean database for the default variant is written to:

```text
variants/main/erenshor-main.sqlite
```

Run `erenshor --help` and `erenshor <group> --help` for the current command surface.

## Dependency maintenance

Renovate owns routine updates for Python, pnpm, NuGet, .NET tools, and GitHub
Actions. A separate GitHub Actions workflow owns Nix flake updates because each
Nix update must also synchronize the pnpm version supplied by the dev shell.
These owners are exclusive. Do not enable Renovate's Nix manager or add another
scheduled dependency updater.

| Dependency graph | Version manifest | Authoritative lock or pin | Automated owner |
| --- | --- | --- | --- |
| Nix | `flake.nix` inputs | `flake.lock` | `update-nix-dependencies.yml` |
| Python | `pyproject.toml` | `uv.lock` | Renovate |
| pnpm workspace | Root and workspace `package.json` files | `pnpm-lock.yaml` | Renovate |
| NuGet | `src/Directory.Packages.props` and project `PackageReference` items | Maintained `packages.lock.json` files | Renovate |
| .NET tools | `.config/dotnet-tools.json` | Exact versions in the manifest | Renovate |
| GitHub Actions | `.github/workflows/*.yml` | Full commit SHA with a release comment | Renovate |

Use the root manifest for each graph. Do not add nested JavaScript lockfiles,
inline NuGet versions, or a second copy of a package version. `src/Directory.Packages.props`
owns NuGet versions. Each maintained .NET project owns its generated lockfile.
Mod projects own one lockfile for each loader graph.

For a manual update, change the owning manifest and regenerate only its
corresponding lock state:

```bash
uv lock
pnpm install --lockfile-only

dotnet restore path/to/Project.csproj --force-evaluate
# Mod projects have two independent restore graphs.
dotnet restore src/mods/<Mod>/<Mod>.csproj -p:ModLoader=bepinex --force-evaluate
dotnet restore src/mods/<Mod>/<Mod>.csproj -p:ModLoader=lunaris --force-evaluate

nix flake update
nix run .#sync-pnpm-version
```

Then run the locked dependency gate and the complete local CI contract:

```bash
erenshor test dependency-state
erenshor test ci
```

Renovate groups compatible patch and minor updates by ecosystem. Major updates
remain blocked until they are approved in the Dependency Dashboard. Security
updates bypass the normal schedule and release-age delay, but they still require
human review, a current branch, and a passing `CI Success` check. Automerge is
disabled for every group.

The private [`glockyco/dependency-automation`](https://github.com/glockyco/dependency-automation)
control plane runs Nix updates for every managed repository. It mints one
short-lived `glockyco-dependency-updater` GitHub App token scoped to this
repository, regenerates `flake.lock` and the matching pnpm assertion, then opens
one review-only pull request. Normal pull-request CI starts automatically, and
the token is revoked when the job ends. This repository does not store the App
private key or run a competing Nix scheduler.

If an updater produces stale or conflicting lock state, do not edit the lockfile
by hand. Run the matching command above, commit the complete regenerated lock
state to the same updater branch, and rerun CI. Close a superseded Renovate pull
request so Renovate can recreate it from the current base. For Nix failures,
rerun the dedicated Nix workflow or run both Nix commands locally. Do not run a
second Nix updater against the same branch.

## Common workflows

### Inspect local setup

```bash
erenshor status
erenshor config show
```

### Extract and build game data

```bash
erenshor extract download
erenshor extract rip
erenshor extract export
erenshor extract build
```

### Publish wiki output

```bash
erenshor wiki fetch
erenshor wiki generate
erenshor wiki deploy
```

### Publish Google Sheets

```bash
erenshor sheets list
erenshor sheets deploy
```

### Process and upload images

```bash
erenshor images process
erenshor images compare
erenshor images report
erenshor images upload
```

### Run and deploy the interactive map

```bash
erenshor maps dev
erenshor maps build
erenshor maps preview
erenshor maps deploy
erenshor maps thumbnails
```

The CLI owns map development, verification, builds, and deployment. Use these
commands instead of invoking workspace package scripts directly.

### Build and deploy companion mods

Every maintained mod has native BepInEx and Lunaris targets. Both loaders may
remain installed in one game installation. Deployment activates exactly one by
switching the root `winhttp.dll` proxy. Select the game variant with `-V`:

```bash
erenshor -V playtest mod setup
erenshor -V playtest mod build --loader all
erenshor -V playtest mod status
erenshor -V playtest mod deploy --loader lunaris
erenshor -V playtest mod deploy --loader bepinex
erenshor mod thunderstore --dry-run
```

Use `mod deploy --mod <id> --loader <bepinex|lunaris>` for one mod and
`mod activate --loader <bepinex|lunaris>` to switch an installed loader without
rebuilding. Standard CrossOver installs are resolved from `-V main`,
`-V playtest`, or `-V demo`; non-standard installs use
`[variants.<name>] game_install` in `.erenshor/config.local.toml`. See the
`mod-pipeline` skill for package publication and proxy safety details.

### Capture map tiles

```bash
erenshor capture status
erenshor capture budget
erenshor capture run
erenshor capture tile
```

### Compile AdventureGuide data

```bash
erenshor guide compile
```

The AdventureGuide mod embeds the compiled guide graph from `quest_guides/guide.json`.

### Runtime C# REPL / HotRepl workflows

HotRepl runs under BepInEx. With the game closed, select that loader and launch
the default `main` variant through Steam. HotRepl remains installed between
sessions, so it is not redeployed for each launch.

```bash
erenshor mod activate --loader bepinex
erenshor mod launch
erenshor eval ping
erenshor eval run 'SceneManager.GetActiveScene().name'
erenshor eval watch 'GameData.PlayerControl.transform.position'
erenshor eval complete 'Camera.main.'
erenshor eval reset
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

### Internal mods

| Mod | Purpose |
| --- | --- |
| `MapTileCapture` | Internal capture tool for rendering orthographic map screenshots used by the tile pipeline. |

## Interactive map

The map website lives in `src/maps/` and is packaged as `erenshor-maps` in the pnpm workspace. It uses SvelteKit, deck.gl, Tailwind, bits-ui, and SQLite data loaded through sql.js in the browser, with prerendered route data for static builds.

Live mode connects to `InteractiveMapCompanion` over WebSocket. The default local endpoint is:

```text
ws://localhost:18585
```

Tracked live entity types include the player, SimPlayers, pets, friendly NPCs, and enemies.

## Development

Install the mutable JavaScript and .NET dependencies, then enter the dev shell:

```bash
nix run .#bootstrap
nix develop           # or `direnv allow` once, with nix-direnv
```

The dev shell builds the locked Python environment and pins the same toolchain
versions CI uses. Update the flake and workflow together so local verification
continues to predict CI.

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

Hook jobs that need project tooling run through `scripts/with-dev-env.sh`, which
enters the dev shell when the calling process is not already inside it. Git
clients that are not shells — Fork, IDE integrations — invoke hooks with the
bare session PATH, where `uv` does not exist and every job would fail with exit
127. Add the wrapper to any new job that calls a dev-shell tool.

Gitleaks ships in the dev shell, so the pre-commit secret scan always runs
rather than skipping itself; CI runs the same scan over the repository.

Run independent static checks for the area you changed:

```bash
# Python
uv run ruff format src/ tests/
uv run ruff check src/ tests/
uv run mypy src/

# Lua modules
pnpm exec stylua --check wiki/modules

# C# formatting used by hooks
bash src/mods/run-csharpier.sh
```

Run behavioral verification through the canonical task leaves:

```bash
erenshor test unit
erenshor test unit --coverage
erenshor test contract
erenshor test maps
erenshor test mods
erenshor test wiki --warm
erenshor -V main test data
```

Use the composites for the same disjoint leaves in parallel:

```bash
erenshor test ci
erenshor -V main test release
```

`test ci` runs unit, contract, maps, and mods. `test release` adds the main data
leaf, clean wiki parity, a real main-data map build, dual-loader mod builds, and
Thunderstore package validation. Run clean wiki parity directly with
`erenshor test wiki --clean-parity` when that isolated Docker gate is the
only target. Every leaf checks its own prerequisites, rejects zero collected
tests, and writes a structured report under `artifacts/test-reports/`.

### Verification acceptance baseline

Measured on 2026-07-24 on an Apple M2 macOS workstation. Fast-gate timings are
the median of three runs after one warm-up. Environment-bound gates were run
once. Every command writes machine-readable diagnostics under
`artifacts/test-reports/`.

| Gate | Canonical command | Required environment | Observed result | Duration | Report |
| --- | --- | --- | --- | ---: | --- |
| Unit | `erenshor test unit` | uv and `tests/unit/` | 1,672 passed | 24.14 s | `unit.json` |
| Contract | `erenshor test contract` | uv, .NET 9, and the native analyzer projects | 3 pytest, 13 CodeFacts, and 14 ExportSurface tests passed | 21.20 s | `contract.json` and `native/contract/*.trx` |
| Warm wiki | `erenshor test wiki --warm` | running local MediaWiki, its API, and Playwright Chromium | 189 managed pages plus API and browser acceptance passed | 38.11 s | `wiki.json` |
| Local CI | `erenshor test ci` | unit, contract, maps, and mods prerequisites | all four disjoint leaves passed | 111.25 s | `ci.json` |
| Clean wiki parity | `erenshor test wiki --clean-parity` | Docker, uv, curl, and Playwright Chromium | isolated 189-page import, Cargo, API, and browser parity passed | 334.02 s | `wiki.json` and `wiki-clean-parity.json` |
| Main data | `erenshor -V main test data` | main raw and clean databases plus shipped `Assembly-CSharp.dll` | 142 passed | 172.45 s | `data.json` |
| Main release | `erenshor -V main test release` | every leaf prerequisite plus provisioned dual-loader mod references | six leaves and three release actions passed | 537.36 s | `release.json` |

The contract gate includes the production CodeFacts and ExportSurface analyzer
projects. The data gate includes the dynamic-spawn and full-export database
contracts. A new Unity batch export remains a separate post-update operation
because it mutates the raw database and requires the configured Unity project.

CI runs independent static-check jobs plus the unit leaf with XML coverage, the
contract leaf, the hermetic maps leaf, and all maintained native mod tests. Main
data, clean wiki parity, real release builds, package validation, and Unity
exports remain explicit environment-bound gates.

## Troubleshooting

### Check setup first

```bash
erenshor status
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
erenshor status
```

### Map live mode does not connect

Confirm the game is running with `InteractiveMapCompanion` installed, then check that the map is connecting to:

```text
ws://localhost:18585
```

The legacy per-zone maps continue to accept player-position updates from retired
`InteractiveMapsCompanion` installations on port `18584`. The current world map
and `InteractiveMapCompanion` use port `18585`.

## License

MIT. See [LICENSE](LICENSE).
