## Why

The repository makes statements about its own environment that the code does not honour. `.env.example` documents a four-level configuration precedence led by environment variables and advertises four variables. The loader implements two levels, and the whole package reads four environment variables, none of which are the advertised ones. `README.md` offers "CrossOver or another Windows runtime" while the launcher invokes CrossOver's `cxstart` and nothing else. `docs/architecture-analysis.md` directs the reader to three paths that do not exist. The CrossOver bottle root and launcher path are defined twice, once in the application layer and once in the CLI, although the application layer already exports both.

A contributor cannot tell which statement to trust, and an agent reading the repository is misled in the same way with less ability to notice. The cost is paid on every task that starts by reading these files.

## Goals

- Every statement about how the project is configured and run matches what the code does.
- One definition for each machine-specific value.
- Documents name only files, commands, and configuration keys that exist.
- Prerequisite tools state how this environment supplies them.

## Non-Goals

- Changing runtime behaviour. Where a document and the code disagree, the code is correct unless stated otherwise in this proposal.
- The three-variant design. `game_files` and `game_install` are separate keys for separate purposes and both remain.
- Failure reporting, which `fail-loudly-on-partial-work` covers.
- Removing the legacy per-zone map socket or the old-format handling it exists for. That surface is supported and kept indefinitely. Only the unreachable branch beside it goes.
- Where game files live and what installs them. `single-game-installation` owns that, and this change follows it.

## Migration Boundary

Documentation, comments, and duplicate constant definitions change. One code path changes: the duplicated constants collapse to an import. No command changes its behaviour, its output, or its exit status.

## What Changes

- Rewrite the `.env.example` precedence section to the two levels the loader implements, and remove variables the package never reads.
- Correct the macOS launch prerequisite in `README.md` to CrossOver, matching the launcher.
- Remove the SteamCMD prerequisite and state that game files come from the Steam client inside the bottle, matching `single-game-installation`.
- Correct or remove the three nonexistent paths named in `docs/architecture-analysis.md`, and remove its historical narrative.
- Import the CrossOver bottle root and launcher path in the CLI from the application layer, which already exports them, instead of redefining them.
- Document the legacy player-position socket where a reader meets it, and record that it is kept indefinitely. The port serves players still running the previous companion mod, and that reason currently exists only in a commit message.
- Remove the branch in that same handler which discards messages carrying a `type` field. The only client that serves the port never sends one, and the branch dates from a two-day window when two mods shared the port, before either had a release path.
- Remove historical framing from active documents. They describe current behaviour only, with the stated exception that a supported compatibility surface may name what it is compatible with, because that is a current fact about what the code accepts.

## Capabilities

### New Capabilities

- `environment-description`: what the repository states about where things are, how it is configured, and how it is run, and the requirement that those statements agree with the code and with each other.

### Modified Capabilities

None. `development-environment` governs the Nix development shell, which this change does not alter.

## Impact

- **Documents:** `README.md`, `.env.example`, `docs/architecture-analysis.md`, comments in `config.toml`.
- **Code:** `src/erenshor/cli/commands/mod.py` imports two constants instead of defining them. `src/maps/src/routes/maps/[mapName]/+page.svelte` loses one unreachable branch and gains the reason its socket exists.
- **Documented, not removed:** the legacy player-position socket on port `18584` in `src/maps/src/routes/maps/[mapName]/+page.svelte`. Nothing in this repository serves that port. Players running the previous companion mod do, and the socket exists for them. The code site gains the reason, and the README gains it alongside the behaviour it already describes.
- **Depends on:** `single-game-installation`, whose removals this change describes. It lands first.
- **Unaffected:** every command, the three variants, generated data, and deployment outputs.
