# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Project Overview

Data mining project for Erenshor, a single-player simulated MMORPG. Extracts
game data via AssetRipper, exports to SQLite via Unity Editor scripts, deploys
to MediaWiki and Google Sheets.

**CRITICAL**: Only modify code in `src/Assets/Editor/` and `src/erenshor/`.
All other files are from the original game and MUST NOT be changed.

## Project Context

- **Solo Developer**: Hobby project, single maintainer
- **Zero Cost**: Free tools only (SteamCMD, AssetRipper, Unity Personal)
- **Multi-Variant**: Handles main, playtest, and demo game versions
- **Unity Constraints**: Non-Editor code belongs to game developer

## Architecture

```
Python CLI (Typer) → Unity batch mode → SQLite → Wiki/Sheets
```

**Entry point**: `uv run erenshor`

Three game variants with separate pipelines:
- **main** (App ID 2382520): Production release
- **playtest** (App ID 3090030): Beta testing
- **demo** (App ID 2522260): Free demo

## Essential Commands

```bash
uv run erenshor extract download    # Download game files from Steam
uv run erenshor extract rip         # Extract Unity project via AssetRipper
uv run erenshor extract export      # Export data to SQLite via Unity
uv run erenshor sheets deploy       # Deploy to Google Sheets
uv run erenshor wiki deploy         # Deploy to MediaWiki
uv run erenshor --variant playtest extract download  # Use different variant
uv run pytest                       # Run tests
uv run pre-commit run --all-files   # Run linters
```

## Development Guidelines

1. Only modify `src/Assets/Editor/` and `src/erenshor/`
2. Use `uv` for Python dependencies
3. Maintain Unity 2021.3.45f2 compatibility
4. Test changes across all variants
5. Type hints required for Python code
6. Run pre-commit hooks before committing

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
