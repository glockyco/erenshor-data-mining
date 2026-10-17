# Erenshor Data Mining

Game data for the single-player MMORPG [Erenshor](https://store.steampowered.com/app/2382520/Erenshor/), extracted from the shipped build and published as a wiki, spreadsheets, an interactive map, and in-game companion mods.

[Wiki](https://erenshor.wiki.gg) · [Interactive map](https://erenshor.compendiums.org)

## What it publishes

- **Wiki** (`erenshor.wiki.gg`). Generated item, character, ability, stance, and zone articles, Lua data modules for links and tooltips, and repository-owned modules and templates. Editors write the prose. The pipeline owns the generated data. The OpenSpec change [`adopt-data-backed-wiki`](openspec/changes/adopt-data-backed-wiki/) holds the plan: bot-owned data modules, view templates that render lists such as vendor stock and zone rosters from them, data-backed templates, and articles that hold only what people write.
- **Google Sheets.** One tab per query in `src/erenshor/application/sheets/queries/`.
- **Interactive map** (`erenshor.compendiums.org`). A SvelteKit and deck.gl site with every spawn, resource, and location, plus live positions from the companion mod.
- **Companion mods.** AdventureGuide (quest guide and navigation), InteractiveMapCompanion (live map data), Sprint, and JusticeForF7. MapTileCapture is an internal tool. Each mod builds for BepInEx and Lunaris.

Every published fact comes from the clean database of the current shipping build.

## How it works

```mermaid
flowchart LR
  steam["Steam install<br/>(CrossOver bottle)"] -->|extract rip| unity["AssetRipper<br/>Unity project"]
  unity -->|extract export| raw[("raw SQLite")]
  dll["Assembly-CSharp.dll"] -->|extract code-facts| raw
  raw -->|extract build| clean[("clean SQLite")]
  clean --> wiki["Wiki"]
  clean --> sheets["Sheets"]
  clean --> maps["Map"]
  clean --> guide["Quest guide"] --> mods["Mods"]
```

1. **Rip and export.** `extract rip` turns the installed game into a Unity project with AssetRipper. `extract export` runs the editor scripts in `src/Assets/Editor/` in Unity batch mode. They write tables that mirror the Unity assets into `variants/<variant>/erenshor-<variant>-raw.sqlite`, without merging or filtering.
2. **Code facts.** `extract code-facts` reads constants that the game hardcodes (drop chances, level gates, formulas) from the shipped assembly into the raw database. The clean build fails without them.
3. **Clean build.** `extract build` applies `mapping.json` (display names, exclusions, overrides with a reason), deduplicates characters, derives columns, and writes `variants/<variant>/erenshor-<variant>.sqlite`. The schema lives in `src/erenshor/application/processor/writer.py`.
4. **Consumers.** The wiki generators, the sheet queries, the map build, and the quest guide compiler read only the clean database.

### Concepts worth knowing

- **Stable keys.** Every entity has a `stable_key` such as `item:head - 7 - arcanist cap`. Names and pages are not unique and never join data. Characters placed in a scene with a duplicate name get coordinates in their key.
- **Variants.** `main` (Steam app 2382520), `playtest` (3090030), and `demo` (2522260) have separate installs, Unity projects, and databases. Select one with `-V`. The wiki publishes only the current shipping build.
- **Encounter tiers.** Each character is `npc`, `enemy`, `elite`, or `boss`, derived in the clean build from faction, boss XP, and spawn placements. `mapping.json` can override a tier with a reason.
- **Drop sources.** `loot_drops` holds each character's own table, `item_drops` holds items that yield items, and `special_world_drops` holds the rolls that every kill makes at the default loot rate.
- **Spawn coverage.** Some spawns are scripted at run time. The dynamic-spawn catalog in `src/Assets/Editor/ExportSystem/AssetScanner/` classifies every spawning script, and the export fails when a new one is unclassified.
- **Gates.** `gate_conditions` records what makes a zone line, placement, vendor item, or item bag available: quests done or not done, items or keys held, a furnished Reliquary room, or an encounter won (advisory). The clean build derives them from the export and `barriers.toml`, and the guide adds the reviewed gates in `quest_guides/graph_overrides.toml`. `barriers.toml` lists every keyed door with the targets it guards and a reason. Its `[[entries]]` name targets that only some zone lines into their scene reach, such as Occuphage's ledge in the Island Tomb, and navigation enters through those lines. The build fails when a keyed door is missing or an entry names a door, zone line, or target the build lacks. Review a new door in game: block it with a carved NavMesh obstacle and compare paths from the scene entry, and confirm unclear cases with renders or the wiki.
- **Generated and written content.** On the wiki, the bot owns the data modules. Prose, notes, and strategy belong to editors and survive every refresh. A fact the export misses goes into code facts or `mapping.json`, so every consumer sees it, not into one article's parameters.

## Repository layout

| Path | What it holds |
| --- | --- |
| `src/erenshor` | The `erenshor` CLI: extraction, clean build, wiki, sheets, maps, mods, tests. |
| `src/Assets/Editor` | Unity editor scripts for the raw export. |
| `src/tools` | Native analyzers (CodeFacts, ExportSurface) and maintenance scripts. |
| `src/maps` | The interactive map site. |
| `src/mods` | The companion mods and their packaging. |
| `wiki` | Repository-owned wiki pages: Lua modules, templates, content pages, and gadgets. |
| `wiki-dev` | A local MediaWiki stack for testing wiki changes. |
| `quest_guides` | Generated and curated quest guide data for AdventureGuide. |
| `tests` | Unit, contract, system, and data tests. |
| `openspec` | Requirements (`specs/`) and the reasoning behind each change (`changes/`). |
| `.agent/skills` | Step-by-step procedures for recurring work. |

`variants/` (game files, Unity projects, databases, generated output) and `.erenshor/` (local configuration and logs) are not tracked.

## Getting started

The Nix flake's dev shell provides Python and uv, the .NET SDKs, Node and pnpm, AssetRipper, and `sqlite3`. With nix-direnv it loads in the working tree. Otherwise run `nix develop`. Every command below assumes the dev shell.

```sh
nix run .#bootstrap                  # locked JavaScript packages and .NET tools
pnpm exec lefthook install --reset-hooks-path
erenshor status                      # tool paths, installs, and database state
```

The shell never compiles a toolchain from source. If entering it starts a compiler, stop it and check `nix build --dry-run 'path:.#devShells.aarch64-darwin.default'`: the plan must not contain `swift`, `dotnet-vmr`, or `dotnet-stage0`.

Three things the shell cannot provide:

- **Unity 2021.3.45f2**, installed through Unity Hub. `extract export` refuses any other version.
- **CrossOver with a Steam bottle** that has each variant installed. The CLI finds an install by its Steam app ID. Set `CROSSOVER_BOTTLE` when there are several bottles.
- **Credentials.** Copy `config.local.toml.example` to `.erenshor/config.local.toml` and fill in the wiki bot and interface logins. The Google service account key path is set there too. The Thunderstore token goes into `.env` (see `.env.example`). `config.toml` holds the tracked defaults, and an unknown key is an error.

### Git worktrees

Enter the dev shell and run the existing bootstrap command in each new worktree. The editable Python installation selects the checkout containing the current directory at interpreter startup. This also applies to `python`, `erenshor`, and `uv run` inherited from another checkout's dev shell. No `PYTHONPATH` override is needed.

After a dev-shell update, enter `nix develop` again or reload direnv. An inherited immutable environment may still import a different checkout. The CLI rejects that mismatch before loading configuration or creating logs.

```sh
python -c 'import erenshor; from erenshor.infrastructure.config import get_repo_root; print(erenshor.__file__); print(get_repo_root())'
```

Resolve variant paths from `config.toml` and any local overrides before copying data. Give each worktree its own raw and clean SQLite files. On macOS, `/bin/cp -c` creates owned APFS clones without duplicating their unchanged data blocks. Use `/bin/cp` because the dev shell's GNU `cp` does not support APFS cloning. Do not symlink the SQLite files or their writable parent directory to another checkout, because a clean build replaces the published database.

Unity, images, wiki, and backups may remain symlinks when used only as read inputs. A clean build also writes its image catalog, profiles, and clean-database backup. For builds on macOS, clone the image and backup directories into owned locations with `/bin/cp -cR`, then point the selected variant's `images_output` and `backups` local overrides at those clones. Keep the shared symlinks for read-only work. This preserves the existing catalog and backup contracts without changing another checkout's files.

`extract build` rejects outputs resolving into another checkout before profiling or building. Correct the named path in `.erenshor/config.local.toml` or replace its symlink with an owned clone. Explicit output paths outside Git checkouts remain supported.

## Common work

| Command | What it does |
| --- | --- |
| `erenshor extract packages` | Restores the Unity editor packages, once per checkout. |
| `erenshor extract rip` / `export` / `code-facts` / `build` | Runs the pipeline steps above. |
| `erenshor extract changes` | Compares the clean database with the previous backed-up build. Review its report after every data change. |
| `erenshor wiki fetch` / `generate` | Fetches live articles and merges regenerated data into them. |
| `erenshor wiki generate-lua` / `deploy-repo-pages` | Generates the Lua data modules and deploys repository-owned modules and templates with revision guards and rollback data. |
| `erenshor sheets deploy` | Publishes the sheet queries. |
| `erenshor maps dev` / `build` / `preview` / `deploy` | Develops, verifies, and deploys the map. |
| `erenshor publish prepare` / `apply` / `status` / `resume` | Reviews and coordinates explicitly selected wiki, map, and sheet writes with one immutable plan. |
| `erenshor mod build` / `deploy` / `thunderstore` | Builds, installs, and packages the mods. `-V` selects the game install, `--loader` the loader. |
| `erenshor guide export-mod` | Writes `quest_guides/quest-guide.json`, the quest data that AdventureGuide embeds. |
| `erenshor eval run '<C#>'` | Evaluates code in the running game through HotRepl. |
| `erenshor capture run` | Captures map tiles through MapTileCapture. |

Run every subsystem through `erenshor`, not through `pnpm`, `wrangler`, or `dotnet` directly. `erenshor <group> --help` lists the options.

### Reviewed publishing

Use `publish` for a coordinated update instead of chaining publishing commands in a shell. Its fixed selection schema is declared in `src/erenshor/application/publish/models.py`. Select exact titles, map targets, and sheet tabs. Missing dependencies are reported, never added to the live write set.

Prepare into a new directory under the selected variant's storage. Preparation inspects live bases and freezes complete payloads without publishing. Selected maps are built locally at this step. Start with the native `review-summary.json`, then open its referenced payloads and exact Sheets request-body sidecar. The summary includes every operation, destination, base, dependency, guard and recovery limit without dumping workbook cells into the terminal.

Inspect the plan with root `--dry-run` and `publish apply`. The complete `review.json` and hashed payload files retain exact wiki text and diffs, map asset hashes, and the stable Sheets preimage with typed rows and atomic request bytes. A concise summary does not replace review of those payloads or change the approval digest.

Only a human approval declaration naming that reviewed digest permits live `apply` or `resume`. Keep editor prose in a separately reviewed variant-local replacement file, not tracked wiki sources. The selection must include its exact file digest. The publisher does not invent prose changes.

The first failure stops every later operation. Keep the entire run directory and native wiki rollback manifests. `status` reports known writes and blocked or uncertain work. Explicit `resume` rechecks completed receipts and remaining bases before skipping successful operations. Changed inputs, destinations, editor revisions, or uncertain provider outcomes require reconciliation and a newly reviewed continuation.

Wiki writes check the current revision before editing and verify the saved revision, parent and source afterward. MediaWiki can merge a racing edit, so this is not atomic compare-and-set. A mismatch stops publication and retains the actual write and editor's prior text for separately reviewed recovery. Map and Sheets checks also cannot prevent a concurrent writer between inspection and mutation.

There is no automatic or cross-service rollback. Wiki rollback cannot delete new pages, and map or sheet restoration is a separate provider-specific review.

Selected tabs for one spreadsheet publish together in one native atomic batch. Google manages reference rebasing. The publisher checks owned outputs and retains the observed workbook state for resume rather than predicting formulas. Atomicity does not prevent a concurrent editor from racing the preflight check.

### Game updates

A new Steam build runs through backup, rip, export, code facts, and build, then through the checks and deploys of each consumer. The [refreshing-game-data skill](.agent/skills/refreshing-game-data/SKILL.md) gives the order and the gates.

### Rules for changes

- Never edit the decompiled game scripts under `variants/<variant>/unity/ExportedProject/Assets/Scripts/`, other ripped assets, or the installed game.
- Never edit generated output by hand: databases, `quest_guides/quest-guide.json`, map builds, captured tiles, generated wiki pages, or mod metadata. Change the generator and regenerate.
- Deploys to the wiki, the map, or the sheets need the maintainer's approval. Review each deploy with its dry run first.
- The live map keeps its legacy contract: `/map` with the `layers` and `sel` parameters on both hosts, WebSocket ports 18584 and 18585, and `/db/erenshor.sqlite`.
- The Nix dev shell must never compile a toolchain from source.
- Fix every failing check you meet, including failures that predate the change.
- Follow the relevant subsystem skill before implementing a change.
- Wiki work follows the plan in the OpenSpec change `adopt-data-backed-wiki`. Read its design before any wiki change, and track wiki work only in OpenSpec.

### Design principles

Interfaces (wiki, map, mods) put evidence before decoration: show source, identity, state, and failure plainly. Use the host platform's conventions (MediaWiki, the web, the game) instead of a new visual language. Keep safe paths obvious: preview before mutation, fail before destructive actions. Target WCAG 2.2 AA with complete keyboard use.

## Testing

```sh
erenshor test ci                     # what CI runs: static checks, unit, contract, maps, mods
erenshor test unit                   # one leaf
erenshor -V main test release        # adds main data, clean wiki parity, real builds, package checks
```

`uv run pytest` alone is not CI. The maps leaf prerenders the site against the fixture database in `src/maps/tests/fixtures/`, which has a different schema from the real one, so a query that works against the real database can fail in CI. `erenshor test wiki` needs the local MediaWiki stack described in `wiki-dev/README.md`. Each leaf writes a report under `artifacts/test-reports/`.

## Dependencies

| Graph | Versions | Lock |
| --- | --- | --- |
| Nix | `flake.nix` | `flake.lock` |
| Python | `pyproject.toml` | `uv.lock` |
| pnpm | `package.json` files | root `pnpm-lock.yaml` |
| NuGet | `src/Directory.Packages.props` | each project's `packages.lock.json` |
| .NET tools | `.config/dotnet-tools.json` | exact versions |
| GitHub Actions | workflow `uses:` | full commit SHAs |

Renovate updates everything except Nix. The private `glockyco/dependency-automation` workflow updates Nix and the pnpm version in `flake.nix`, and opens a pull request. After a manual change, regenerate the lock (`uv lock`, `pnpm install --lockfile-only`, `dotnet restore --force-evaluate` once per mod loader, or `nix flake update` and `nix run .#sync-pnpm-version`) and run `erenshor test dependency-state`.

Keep NuGet feeds and package source mappings beside the central package versions, so Renovate's generated restore configuration and project builds discover the same sources.

## Troubleshooting

- **Setup.** `erenshor status` reports tool paths, installs, and database state. Logs are in `.erenshor/logs/` and `variants/<variant>/logs/`.
- **Git hooks fail with exit 127.** Git clients without a shell call hooks without the dev shell. Hook jobs that need project tools run through `scripts/with-dev-env.sh`.
- **Live map does not connect.** The game must run InteractiveMapCompanion, which serves `ws://localhost:18585`.

## Further reading

- [`openspec/specs`](openspec/specs/) states what the pipeline and its outputs must do. Each change under [`openspec/changes`](openspec/changes/) records why it was made.
- [`.agent/skills`](.agent/skills/) holds the procedures for game updates, exports, code facts, wiki, sheets, map, tile capture, mods, and runtime inspection.
- Commit messages explain why each change exists.

## License

MIT. See [LICENSE](LICENSE).

Erenshor Data Mining is an unofficial fan project and is not affiliated with the developer of Erenshor.
