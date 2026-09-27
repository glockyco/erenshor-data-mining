## Why

Each variant can resolve to game files in two places. `game_files` names a download destination, defaulting to a directory inside the repository, and `game_install` optionally names a runnable installation, otherwise discovered inside the CrossOver bottle by application id. On this workstation the tracked default and the working arrangement disagree: `config.toml` points main at `variants/main/game`, and a gitignored override points it at the bottle with the note that it exists to avoid downloading a second copy.

Two locations invite two builds. An extraction can then be taken from files that are not the files the mods are deployed into, and nothing reports the difference.

The download that creates the second location cannot be pointed at the first. `extract download` passes `game_files` to SteamCMD as `+force_install_dir`, and that flag produces a self-contained install root with its own nested `steamapps` manifest. Aimed at the bottle's library directory it would nest a second manifest inside the installation and leave the client's record stale. Aimed anywhere else it produces the second copy. There is no argument to that command that yields one installation.

The Steam client inside the bottle already installs and updates every application there, and the bottle already hosts a game together with its demo. It can host all three variants.

## Goals

- One location for the game files of each variant: the installation the Steam client maintains.
- One way to find it: the application id recorded in the Steam application manifest.
- Configuration that describes the arrangement in use, with no path that has to be corrected per machine.
- Absent, ambiguous, or unusable installations reported loudly, naming the application id.

## Non-Goals

- The three-variant design. Each variant keeps its own application id, its own extracted database, and its own outputs. Variants are the reason discovery keys on the application id rather than on a name.
- Where derived output goes. The Unity project, databases, images, wiki, logs, and backups already live under `variants/{variant}` outside the bottle, and they stay there.
- Supporting a machine without CrossOver. That case is not handled, and the tooling says so rather than offering a path that has never been exercised.
- Failure reporting elsewhere in the pipeline, which `fail-loudly-on-partial-work` covers.
- Adding an update command. The Steam client performs updates, and no workflow here needs to trigger one programmatically.

## Migration Boundary

A machine whose variant already resolves to the bottle installation sees no change in what is extracted. A variant that is not installed in the bottle stops being downloadable and must be installed through the Steam client, which is how it reaches the bottle in the first place. Derived output paths are untouched.

## What Changes

- **BREAKING** Remove `extract download` and the SteamCMD wrapper it is the sole consumer of. The Steam client installs and updates game files.
- **BREAKING** Resolve the game files of a variant by discovering its application id inside the CrossOver bottle. Remove `game_files` and `game_install` as configured paths, along with the local override that exists to reconcile them.
- **BREAKING** Remove the `[steam]` configuration section and the credential precondition that served only the download.
- Report an installation that is absent, ambiguous, or missing its managed assemblies by naming the application id and the variant.
- Remove the self-contained install layout handling from manifest lookup. Only the Steam library layout remains, because only Steam writes these files.
- Record in the tracked configuration that the Steam client owns installation, so a reader learns the arrangement from the file rather than from a gitignored override.

## Capabilities

### New Capabilities

- `game-installation`: where the game files of a variant live, what puts them there, how the tooling finds them, and what it does when it cannot.

### Modified Capabilities

None. `dependency-management` and `development-environment` govern the toolchain rather than game files.

## Impact

- **Removed:** `src/erenshor/infrastructure/steam/steamcmd.py` and its exports, `tests/unit/infrastructure/steam/test_steamcmd.py`, the `download` command in `src/erenshor/cli/commands/extract.py`, `SteamConfig` in `src/erenshor/infrastructure/config/schema.py`, the credential precondition in `src/erenshor/cli/preconditions/checks/steam.py`, and `_find_app_manifest`'s self-contained branch.
- **Changed:** `VariantConfig` loses `game_files` and `game_install`. `get_game_path` resolves through discovery alone. `setup_mods` no longer needs `allow_extracted`.
- **Configuration:** `config.toml` loses two path keys per variant and the `[steam]` section. `.erenshor/config.local.toml` loses its reason to exist for the main variant.
- **Retained:** `src/erenshor/infrastructure/steam/build_feed.py`, which reads published build metadata and does not depend on the removed wrapper.
- **Dependencies:** SteamCMD is no longer required by this repository.
- **Lost capability:** SteamCMD can fetch a specific build id and the Steam client cannot. Nothing here passes a build id.
- **Unaffected:** extraction, ripping, the maps site, the mods, the wiki, and every derived output path.
