# Agent Instructions

## Project Overview

Data mining project for Erenshor (single-player simulated MMORPG). Extracts
game data via AssetRipper + Unity Editor scripts, exports to SQLite, deploys
to MediaWiki, Google Sheets, interactive maps, and in-game companion mods.
Solo developer. Hobby project.

**Maintained implementation code lives in** `src/Assets/Editor/`, `src/erenshor/`,
`src/mods/`, `src/maps/`, and `src/tools/`. Regression tests under `tests/` MAY be
added or changed when they defend the requested behavior. Wiki templates and
other repository-owned content MAY be changed when the task explicitly requires
it. `AGENTS.md`, plans, and other process documents MAY be changed when the
user explicitly requests an instruction or planning update.

**Never modify shipped-game reference files or installed game files.** In
particular, treat these as read-only:

- `variants/{variant}/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/`
  (decompiled `Assembly-CSharp` game scripts used as reference)
- `variants/{variant}/unity/ExportedProject/Assets/Scenes/` and other
  AssetRipper/decompiled game assets
- `variants/{variant}/game/` and any Steam/CrossOver installation files
- any original game files outside the maintained implementation paths above

Do not hand-edit generated or deployment outputs. Regenerate them through the
canonical CLI commands instead. This includes variant SQLite databases,
`quest_guides/guide.json`, map build/static artifacts, captured tiles, generated
wiki output, and generated mod metadata. Do not update shared golden baselines
or deploy shared wiki/map targets unless the user explicitly authorizes that
cutover or deployment.

## Directory Map

| Path | Contents |
|------|----------|
| `src/erenshor/` | Python CLI tool (Typer), pipeline logic, domain entities |
| `src/Assets/Editor/` | C# Unity export scripts (listeners, records, scanner) |
| `src/mods/` | Native BepInEx and Lunaris companion mods (C#) |
| `src/maps/` | Interactive map website (SvelteKit) |
| `variants/{variant}/` | Per-variant game files, Unity projects, databases (gitignored) |
| `variants/{variant}/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/` | Decompiled game C# scripts (read-only reference) |
| `wiki/`, `wiki-templates/` | Wiki source files and templates |
| `quest_guides/` | Quest guide JSON (auto-generated + manual curation) |
| `.agent/skills/` | Agent skill files (domain-specific knowledge) |
| `docs/` | Design documents, PRDs, architecture analysis |

## Databases

Two SQLite databases per variant, both gitignored:

| File | Produced by | Contents |
|------|-------------|----------|
| `variants/{variant}/erenshor-{variant}-raw.sqlite` | `extract export` (Unity batch mode) | Raw tables mirroring Unity assets |
| `variants/{variant}/erenshor-{variant}.sqlite` | `extract build` (Python processor) | Clean tables consumed by wiki, maps, sheets, quest guides |

The map website symlinks the clean DB: `src/maps/static/db/erenshor.sqlite` → `variants/main/erenshor-main.sqlite`.

```bash
# List tables in the clean DB (main variant)
sqlite3 variants/main/erenshor-main.sqlite ".tables"
```

## Essential Commands

```bash
uv run erenshor --help                          # All command groups
uv run erenshor extract export                  # Unity -> raw SQLite
uv run erenshor extract code-facts              # Shipped DLL -> raw code_facts (between export and build)
uv run erenshor guide compile                   # Compile entity graph to guide.json
uv run erenshor mod setup                                  # Provision both loaders' build references
uv run erenshor mod build --mod <id> --loader all          # Build both native targets
uv run erenshor mod status                                 # Inspect installed/active loaders
uv run erenshor mod deploy --mod <id> --loader bepinex     # Build, deploy, and activate BepInEx
uv run erenshor mod deploy --mod <id> --loader lunaris     # Build, deploy, and activate Lunaris
uv run erenshor mod deploy --mod <id> --loader bepinex --scripts # BepInEx hot reload
uv run erenshor mod thunderstore --dry-run                 # Validate all public BepInEx packages
uv run erenshor maps build                    # Verify, build, and stamp maps site
uv run erenshor maps deploy                   # Deploy existing fresh maps build
uv run pytest                                   # Run all tests
uv run erenshor golden capture                # Regenerate data-pipeline golden baselines
```

Drive every subsystem through `uv run erenshor ...`; never call `pnpm build`,
`wrangler deploy`, or `dotnet build` directly for project workflows.

### Command Map

| Stage | Canonical command |
|---|---|
| Acquire/build game data | `uv run erenshor extract export` → `uv run erenshor extract code-facts` → `uv run erenshor extract build` |
| Build mods | `uv run erenshor mod build --mod <id> --loader all` |
| Develop maps | `uv run erenshor maps dev` |
| Publish maps externally | `uv run erenshor maps build` → `uv run erenshor maps deploy` |
| Verify Python pipeline | `uv run pytest` |
| Verify data baselines | `uv run erenshor golden capture` |

## Runtime Inspection

Use HotRepl (`erenshor eval`) to inspect live game state, check field
values, and prototype fixes without a build cycle. Use the decompiled
game scripts as reference for available fields and methods. See the
`runtime-eval` and `mod-development` skills for full details.

Use Unity MCP (`unity` server in `.omp/mcp.json`) to inspect scene
hierarchy, read component values, and query GameObjects directly from
the Unity Editor. Requires the Unity Editor open with the MCP server
started via **Window > MCP for Unity > Start Server** (HTTP on port 8080).
Package: `com.coplaydev.unity-mcp` (in `Packages/manifest.json`).

## Working Principles

- **Take a holistic view.** Every change considers the overall project architecture. Avoid tunnel vision: a compiling build or a passing test is not the same as a correct, complete solution. Always ask what else is affected by a change.
- Be proactive. If you notice something that can be improved, bring it up and fix it.
- Plan before implementing. List planned commits before writing code.
- Suggest larger architectural changes if they make for a cleaner solution.
- Read the relevant skill before touching a subsystem (see Skill Directory below).
- If you change a workflow documented in a skill, update the skill in the same commit.
- Do not use semicolons in prose. Rewrite with a full stop, comma, colon, or parentheses. Semicolons remain valid where required by code or syntax.
- No shortcuts. No hacks. Always strive to leave the project in a better state than you found it.

## Work Decomposition

Before starting multi-file work, list planned commits. Each commit is one
logical change. Implement and commit sequentially. A commit that requires
"and" to describe is two commits. Planning docs follow the global convention (`skill://planning-files`); implement plans **inline in the main working tree** — do not create git worktrees unless explicitly requested.

## Commit Standards

Conventional commits: `type(scope): description`
- Types: feat, fix, refactor, style, docs, test, chore
- Scopes: any short noun matching the changed subsystem (e.g. mod, map, cli, export, wiki, sheets, pipeline, guide, config, plans, skills)
- Body: prose paragraphs, not bullet lists. Explain why, not what.
- Imperative mood. 80-char line wrap. No period on summary.
- Full guidelines: read the `commit-guidelines` skill.

## Code Quality

1. **Fail fast**: no fallback functionality that hides errors.
2. **No backward compatibility**: clean breaks when changing behavior.
3. **Clean cuts**: remove old code entirely when refactoring.
4. **Atomic commits**: one concept per commit.
5. **Fix all errors**: fix every test failure, linter error, and type error you encounter — including ones that predate your change. "Pre-existing" is not an exemption. If CI is broken when you arrive, fix it before committing anything else.
6. **Verify every claim**: search the codebase, read files, confirm.

## Critical Constraints

- **Unity version**: must be exactly 2021.3.45f2
- **Config layering**: `config.toml` (tracked) + `.erenshor/config.local.toml` (gitignored)
- **Three variants**: main, playtest, demo -- separate databases, Unity projects, game files
- **Use `resolved_*` methods** for config paths, not raw values (`$REPO_ROOT` unexpanded)
- **Editor symlink**: exports require `variants/{variant}/unity/Assets/Editor` symlink
- **Non-interactive shell**: always use `cp -f`, `mv -f`, `rm -rf` (aliases may prompt)

## Testing

```bash
uv run pytest                       # All Python tests (1900+)
uv run pytest -m integration        # Integration tests only
uv run erenshor golden capture      # Regenerate golden baselines after data changes
```

Always run `golden capture` before deploying data changes and review diffs.
Golden files in `tests/golden/` detect unintended data-pipeline changes; they
are not a frontend-only maps redeploy gate.

### Matching CI locally

`uv run pytest` is **not** what CI runs, and passing it is not evidence CI will
pass. CI gates on four static checks plus four verification leaves, none of
which `pytest` invokes:

```bash
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
uv run mypy src/
uv run erenshor test ci             # unit, contract, maps, mods leaves
```

CI additionally runs `dotnet csharpier --check .` from the repository root,
which does not reproduce there locally: the CSharpier tool manifests live per
mod under `src/mods/*/.config/`, so a root-level `dotnet tool restore` finds
nothing. Check C# formatting from inside the mod you touched instead.

Run that block before pushing. The `maps` leaf matters most and is the easiest
to miss: it prerenders the site against the hermetic fixture in
`src/maps/tests/fixtures/map-database.sql`, whereas `erenshor maps build`
prerenders against the real clean DB from `variants/`. The two databases have
different schemas, so a query touching a table the fixture lacks passes locally
and fails in CI every time. `tests/contract/test_maps_fixture_schema.py` catches
column drift between them, but a table the fixture never had is only caught by
running the leaf.

## Skill Directory

Read the relevant skill before working in its domain. Skills are in `.agent/skills/<name>/SKILL.md`.

| Working on... | Read first | Path |
|---|---|---|
| Unity export code (`src/Assets/Editor/`) | unity-export-system | `.agent/skills/unity-export-system/SKILL.md` |
| Refreshing data after a new game version | refreshing-game-data | `.agent/skills/refreshing-game-data/SKILL.md` |
| Code-facts analyzer / hardcoded constants | code-facts | `.agent/skills/code-facts/SKILL.md` |
| Companion mods (`src/mods/`) | mod-development | `.agent/skills/mod-development/SKILL.md` |
| Mod build/deploy/publish | mod-pipeline | `.agent/skills/mod-pipeline/SKILL.md` |
| Interactive map (`src/maps/`) | interactive-map | `.agent/skills/interactive-map/SKILL.md` |
| Map tile capture | tile-capture | `.agent/skills/tile-capture/SKILL.md` |
| Runtime eval / HotRepl | runtime-eval | `.agent/skills/runtime-eval/SKILL.md` |
| Combat mechanics and formula validation | combat-evaluation | `.agent/skills/combat-evaluation/SKILL.md` |
| In-game runtime profiling | in-game-performance-profiling | `.agent/skills/in-game-performance-profiling/SKILL.md` |
| Wiki templates | wiki-templates | `.agent/skills/wiki-templates/SKILL.md` |
| Google Sheets queries | sheets-queries | `.agent/skills/sheets-queries/SKILL.md` |
| CLI commands (`src/erenshor/cli/`) | cli-commands | `.agent/skills/cli-commands/SKILL.md` |
| Writing commit messages | commit-guidelines | `.agent/skills/commit-guidelines/SKILL.md` |

## Session Completion

If this session created or used a `docs/plans/` artifact for work that is now
complete, run `omp-plans complete <slug>` before the final response so the
implemented doc is archived and removed from the active planning index.
