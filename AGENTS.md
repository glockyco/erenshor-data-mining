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
| `wiki/`, `wiki-templates/` | Wiki source files and templates |
| `quest_guides/` | Quest guide JSON (auto-generated + manual curation) |
| `.agent/skills/` | Agent skill files (domain-specific knowledge) |
| `docs/` | Design documents, PRDs, architecture analysis |

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

## Working Principles

- Take a holistic view. Every change considers the overall project architecture.
- Be proactive. If you notice something that can be improved, bring it up and fix it.
- Plan before implementing. List planned commits before writing code.
- Read the relevant skill before touching a subsystem (see Skill Directory below).
- If you change a workflow documented in a skill, update the skill in the same commit.
- Verify with tests, not assumptions.

## Work Decomposition

Before starting multi-file work, list planned commits. Each commit is one
logical change. Implement and commit sequentially. A commit that requires
"and" to describe is two commits.

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
5. **Fix all errors**: don't ignore bugs discovered during work.
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

Work is NOT complete until `git push` succeeds.

```bash
git pull --rebase
bd dolt push
git push
git status    # Must show "up to date with origin"
```

Close finished issues, create issues for remaining work, push everything.
