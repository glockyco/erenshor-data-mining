## 1. Baseline

- [ ] 1.1 Record an extraction for the main variant against the current installation, keeping checksums of the resulting database and Unity project so later steps compare against a measurement.
- [ ] 1.2 Record which variant application ids are installed in the bottle, and the `buildid` of each.
- [ ] 1.3 Record the current `uv run erenshor test ci` result.

## 2. Remove the downloader

- [ ] 2.1 Delete the `download` command from `src/erenshor/cli/commands/extract.py` and its registration.
- [ ] 2.2 Delete `src/erenshor/infrastructure/steam/steamcmd.py` and its exports from `src/erenshor/infrastructure/steam/__init__.py`, keeping `build_feed.py`.
- [ ] 2.3 Delete `tests/unit/infrastructure/steam/test_steamcmd.py`.
- [ ] 2.4 Confirm nothing else imports the wrapper. Verify with a search that also proves the search works, rather than accepting an empty result.

## 3. Collapse resolution to discovery

- [ ] 3.1 Change `get_game_path` in `src/erenshor/application/mods/local_workflow.py` to resolve only through `discover_crossover_game_path`.
- [ ] 3.2 Delete the `game_install`, `ERENSHOR_GAME_PATH`, and `allow_extracted` resolution branches, and the `allow_extracted` parameter and its one call site in `setup_mods`.
- [ ] 3.3 Confirm extraction, mod setup, deploy, and launch all resolve through the one path.

## 4. Report the three failures apart

- [ ] 4.1 Fail with the variant and its application id when nothing matches, stating that the variant is installed through the Steam client.
- [ ] 4.2 Fail naming every candidate when more than one installation matches.
- [ ] 4.3 Fail naming the manifest when one exists but cannot be read, rather than reporting absence.
- [ ] 4.4 Reject a candidate lacking its managed assembly directory and say what was missing.
- [ ] 4.5 Add tests covering all four conditions and asserting the reports differ.

## 5. Remove the configuration

- [ ] 5.1 Delete `game_files` and `game_install` from `VariantConfig` in `src/erenshor/infrastructure/config/schema.py` and their resolver methods.
- [ ] 5.2 Delete both keys from all three variants in `config.toml`, and delete the commented `game_install` guidance.
- [ ] 5.3 Delete `SteamConfig` and the `[steam]` section.
- [ ] 5.4 Delete the credential precondition from `src/erenshor/cli/preconditions/checks/steam.py`, and rewrite the game-files precondition so its remediation names the Steam client instead of the removed command.
- [ ] 5.5 Delete the main-variant override from `.erenshor/config.local.toml`, and confirm the variant still resolves.
- [ ] 5.6 Record in `config.toml` that the Steam client owns installation and that discovery uses the application id.

## 6. Remove the second layout

- [ ] 6.1 Delete the self-contained branch from `_find_app_manifest`, leaving the Steam library layout.
- [ ] 6.2 Confirm `_read_manifest_fields` and `_read_build_id` still resolve for an installed variant.

## 7. Verification

- [ ] 7.1 Confirm each installed variant resolves to the installation recorded in its manifest, and that an uninstalled variant fails with a report naming it and its application id.
- [ ] 7.2 Run an extraction for the main variant and compare against the task 1.1 checksums.
- [ ] 7.3 Confirm exactly one copy of the game files exists for each variant, and that no nested `steamapps` directory exists inside any installation.
- [ ] 7.4 Confirm the installation is unchanged by a full pipeline run, comparing its `buildid` and file count against task 1.2.
- [ ] 7.5 Run `uv run erenshor test ci` and compare against task 1.3.
- [ ] 7.6 Run `openspec validate single-game-installation --strict`.
- [ ] 7.7 Search for remaining references to the removed keys, the removed command, and SteamCMD, and remove what is found.
