# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Project Overview

Data mining project for Erenshor, a single-player simulated MMORPG. Extracts
game data via AssetRipper, exports to SQLite via Unity Editor scripts, deploys
to MediaWiki, Google Sheets, and an interactive map website.

**CRITICAL**: Only modify code in `src/Assets/Editor/`, `src/erenshor/`,
`src/mods/`, and `src/maps/`. All other files are from the original game and
MUST NOT be changed.

## Project Context

- **Solo Developer**: Hobby project, single maintainer
- **Multi-Variant**: Handles main, playtest, and demo game versions
- **Unity Constraints**: Non-Editor code belongs to game developer

**Variant directories** (`variants/{variant}/`) are .gitignored but essential
for data mining work:
- `variants/{variant}/game/` — downloaded game installation
- `variants/{variant}/unity/ExportedProject/Assets/Scripts/` — decompiled
  C# game scripts (critical for understanding game mechanics, writing
  export scripts, and verifying data mining correctness)
- `variants/{variant}/unity/ExportedProject/Assets/` — all AssetRipper
  exported game assets (prefabs, scenes, scriptable objects, etc.)

These directories must be read frequently even though they are not tracked
in git. Run `extract download` and `extract rip` to populate them.

## Essential Commands

```bash
uv run erenshor --help              # All command groups
uv run erenshor <group> --help      # Subcommands for any group
uv run erenshor --variant playtest <command>  # Use different variant
uv run pytest                       # Run tests
uv run pre-commit run --all-files   # Run linters
```

### Common Workflows

**New game version** (full pipeline):
`extract download` → `extract rip` → `extract export` → `extract build`
→ `wiki fetch` → `wiki generate` → `golden capture` → review diffs →
`sheets deploy --all-sheets` → `maps build --force` → `maps deploy` → `wiki deploy`

**Rebuild after changing build logic** (fast, no re-export needed):
`extract build` re-reads the raw DB without re-exporting, then follow
the deploy steps above from `wiki generate` onwards.

**Wiki update**:
`wiki fetch` → `wiki generate` → `golden capture` → review diffs →
`wiki deploy`

Always run `golden capture` before deploying and review every diff.
Golden files in `tests/golden/` are the source of truth for detecting
unintended data changes. Commit the updated goldens after review.

**Image update**:
`images process` → `images compare` → `images report` → `images upload`

**Maps deployment**:
`maps build --force` → `maps deploy`

**Mod development**: See `mod-build-pipeline` skill.
`mod setup` (copy game DLLs, needed once) → `mod build` → `mod deploy` (local)
or `mod publish` (stage for website) or `mod thunderstore` (Thunderstore)

## Collaboration Expectations

Prioritize accuracy over agreement. Avoid sycophantic behavior.

- **Challenge when appropriate**: If a request seems wrong, say so directly.
  Propose alternatives instead of just complying.
- **Flag concerns proactively**: Outdated patterns, inconsistencies, potential
  bugs, architectural issues - raise them without being asked.
- **Verify before stating**: Don't write docs or make claims without checking
  actual code. Grep, read files, confirm.
- **Ask instead of assuming**: When details are unclear, ask. Don't fill gaps
  with guesses that might be wrong.
- **Maintain positions when correct**: If pushback is based on misunderstanding,
  explain clearly rather than immediately yielding.

## Code Quality Principles

1. **Validate Every Claim**: Never make claims without checking actual code.
   Search the codebase, read files, verify implementations.

2. **Fail Fast**: No fallback functionality that hides errors. Fail immediately
   with clear messages.

3. **No Backward Compatibility**: Clean breaks when changing behavior. No
   legacy code paths "just in case".

4. **Keep It Simple**: No extra config options or features. Suggest improvements
   but only implement after discussion.

5. **Clean Cuts Only**: Remove old code entirely when refactoring. Less code
   means less maintenance.

6. **Minimal Comments**: Don't comment obvious code. Comments explain why,
   not what.

7. **Atomic Commits**: One concept per commit. Conventional commits format.
   Prose descriptions, not bullet lists. 80 char line limit.

8. **Fix All Errors**: Don't ignore errors. Fix bugs discovered during testing.

## Important Constraints

1. **Unity Version**: Must use Unity 2021.3.45f2 exactly
2. **Steam Credentials**: Requires valid Steam account with game ownership
3. **Symlinks**: C# files symlinked, DLLs copied (Unity limitation)
4. **Batch Mode**: Unity exports run headless via CLI
5. **Service Account**: Google Sheets requires Editor access

## Testing

```bash
uv run pytest                    # All tests
uv run pytest --cov              # With coverage
uv run pytest -m integration     # Integration tests only
```

CI runs on all pushes: linting (Ruff), type checking (MyPy), secret scanning
(Gitleaks), and full test suite.

## Database Files

Two databases per variant (both gitignored):
- **Raw** (`erenshor-{variant}-raw.sqlite`): direct Unity export. Do not query.
- **Clean** (`erenshor-{variant}.sqlite`): built by `extract build`. Query this one.

Paths: `variants/main/erenshor-main.sqlite`, `variants/playtest/erenshor-playtest.sqlite`,
`variants/demo/erenshor-demo.sqlite`

## Wiki Content

`wiki/` at project root holds version-controlled wiki source files (not
auto-generated, not variant-specific):
- `wiki/Zones.txt` — zone index page (deploy via `wiki deploy --from-dir wiki/`)
- `wiki/zones/` — generated individual zone pages (deploy via `wiki deploy --from-dir wiki/zones/`)
- `wiki/templates/` — wiki template source files (deploy via `wiki deploy --from-dir wiki/templates/`)
