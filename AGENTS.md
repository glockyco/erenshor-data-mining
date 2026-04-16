# Agent Instructions

## Project Overview

Data mining project for Erenshor (single-player simulated MMORPG). Extracts
game data via AssetRipper + Unity Editor scripts, exports to SQLite, deploys
to MediaWiki, Google Sheets, interactive maps, and in-game companion mods.
Solo developer. Hobby project.

**Only modify code in `src/Assets/Editor/`, `src/erenshor/`, `src/mods/`, and
`src/maps/`.** All other files are from the original game and must not be changed.

## Directory Map

| Path | Contents |
|------|----------|
| `src/erenshor/` | Python CLI tool (Typer), pipeline logic, domain entities |
| `src/Assets/Editor/` | C# Unity export scripts (listeners, records, scanner) |
| `src/mods/` | BepInEx companion mods (C#) |
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
uv run erenshor extract build                   # Raw SQLite -> clean SQLite
uv run erenshor guide generate                  # Generate quest guide JSON
uv run erenshor mod setup                       # Copy game DLLs (first time)
uv run erenshor mod dev-setup                   # Install ScriptEngine + ConfigManager (first time)
uv run erenshor mod build --mod <id>            # Build a mod
uv run erenshor mod deploy --mod <id> --scripts # Hot reload deploy (F6 in game)
uv run erenshor mod deploy --mod <id>           # Production deploy (restart game)
uv run pytest                                   # Run all tests
uv run erenshor golden capture                  # Regenerate golden baselines after data changes
```

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

- Take a holistic view. Every change considers the overall project architecture.
- Be proactive. If you notice something that can be improved, bring it up and fix it.
- Plan before implementing. List planned commits before writing code.
- Suggest larger architectural changes if they make for a cleaner solution.
- Read the relevant skill before touching a subsystem (see Skill Directory below).
- If you change a workflow documented in a skill, update the skill in the same commit.
- No shortcuts. No hacks. Always strive to leave the project in a better state than you found it.

## Work Decomposition

Before starting multi-file work, list planned commits. Each commit is one
logical change. Implement and commit sequentially. A commit that requires
"and" to describe is two commits. Write plans to `docs/plans/{YYYY-MM-DD}-{plan-name}.md`.

## Commit Standards

Conventional commits: `type(scope): description`
- Types: feat, fix, refactor, style, docs, test, chore
- Scopes: mod, map, cli, export, wiki, sheets, pipeline, guide, config
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
uv run pytest                       # All tests (744+)
uv run pytest -m integration        # Integration tests only
uv run erenshor golden capture      # Regenerate golden baselines after data changes
```

Always run `golden capture` before deploying and review diffs. Golden files
in `tests/golden/` detect unintended data changes.

## Skill Directory

Read the relevant skill before working in its domain. Skills are in `.agent/skills/<name>/SKILL.md`.

| Working on... | Read first | Path |
|---|---|---|
| Unity export code (`src/Assets/Editor/`) | unity-export-system | `.agent/skills/unity-export-system/SKILL.md` |
| Companion mods (`src/mods/`) | mod-development | `.agent/skills/mod-development/SKILL.md` |
| Mod build/deploy/publish | mod-pipeline | `.agent/skills/mod-pipeline/SKILL.md` |
| Interactive map (`src/maps/`) | interactive-map | `.agent/skills/interactive-map/SKILL.md` |
| Map tile capture | tile-capture | `.agent/skills/tile-capture/SKILL.md` |
| Runtime eval / HotRepl | runtime-eval | `.agent/skills/runtime-eval/SKILL.md` |
| In-game runtime profiling | in-game-performance-profiling | `.agent/skills/in-game-performance-profiling/SKILL.md` |
| Wiki templates | wiki-templates | `.agent/skills/wiki-templates/SKILL.md` |
| Google Sheets queries | sheets-queries | `.agent/skills/sheets-queries/SKILL.md` |
| CLI commands (`src/erenshor/cli/`) | cli-commands | `.agent/skills/cli-commands/SKILL.md` |
| Writing commit messages | commit-guidelines | `.agent/skills/commit-guidelines/SKILL.md` |
| Creating/updating skills | writing-skills | `.agent/skills/writing-skills/SKILL.md` |

## Issue Tracking (bd)

This project uses **bd** (beads) for issue tracking. No markdown TODOs or task lists.

```bash
bd ready                            # Find available work
bd show <id>                        # View issue details
bd update <id> --claim              # Claim work
bd close <id> --reason "Done"       # Complete work
bd create "Title" --description="..." -t task -p 2  # Create issue
bd dolt push                        # Push beads data to remote
```

Link discovered work: `bd create "Found bug" -p 1 --deps discovered-from:<parent-id>`

## Session Completion

Close finished issues. Create issues for remaining work.
