## Context

See proposal.md - Why.

The two layouts SteamCMD and the Steam client produce are different, and the difference is the whole argument.

```
steamcmd +force_install_dir X     X/Erenshor.exe
                                  X/steamapps/appmanifest_<id>.acf

Steam library                     <lib>/steamapps/common/<installdir>/Erenshor.exe
                                  <lib>/steamapps/appmanifest_<id>.acf
```

`_find_app_manifest` in `cli/commands/extract.py` already documents both, having been written to cope with each. That function is the evidence that two topologies exist and the reason the change can remove one cleanly: only its second branch survives.

The existing discovery is already correct and is the model the rest moves toward. `discover_crossover_game_path` scans bottles, reads `appmanifest_<app_id>.acf`, resolves `installdir`, and verifies the managed assembly directory. Nothing about it needs redesign. What changes is that it becomes the only path rather than one of four.

Current resolution order in `get_game_path`:

```
configured game_install  →  CrossOver discovery  →  ERENSHOR_GAME_PATH  →  game_files (only when allow_extracted)
```

Three of those four exist to support a machine that is not this one. `game_install` is documented in `config.toml` as an override "for non-standard or non-CrossOver installs". `game_files` is the download destination. The environment variable is a third way to say the same thing, and it cannot override a successful discovery anyway, so its position already makes it unreachable in the normal case.

The bottle hosts five applications on this workstation, including a game and its separate demo, which is the arrangement all three variants would use.

## Goals / Non-Goals

**Goals**

- One resolution path, so no two commands can disagree about where a variant's files are.
- Removal of the keys whose only purpose is an unsupported environment.
- Reports that distinguish absence, ambiguity, and an unreadable record.

**Non-Goals**

- Variant handling. Three variants stay, and discovery keys on the application id precisely so they can.
- Derived output locations, which are already outside the installation.
- An update command. Steam performs updates and no workflow here needs to trigger one.
- Changing extraction, ripping, or anything downstream of the resolved path.

## Decisions

**Discovery replaces configuration rather than defaulting to it.** Alternative: keep `game_install` as an optional override and default to discovery. Rejected because an override that no supported environment needs is the same aspirational surface this work exists to remove, and because an override silently beats discovery, which is how a machine ends up extracting from files the mods were never deployed into.

**`extract download` is removed rather than repointed.** There is no argument that makes it correct. Aimed at the library install directory it nests a second manifest inside the installation and leaves the client's record stale. Aimed anywhere else it creates the second copy the change exists to eliminate.

**`game_files` and `game_install` collapse together.** The scouting read of these keys as load-bearing was right while a downloaded copy could exist. Once it cannot, both name the same installation and the distinction is a difference without a case. The role distinction they encoded, extraction source against deployment target, survives as a property of the commands rather than of the configuration.

**Failure distinguishes three conditions.** Discovery currently returns `None` for no match, several matches, and an unreadable manifest, so the caller reports one thing for three problems whose remedies are install it, remove one, and repair the record.

**The self-contained manifest branch goes with the command that produced it.** Leaving it would keep the tooling able to read a layout nothing can now create, which reads as support for a topology the change forbids.

**`build_feed.py` stays.** It reads published build metadata and never touched the wrapper. Removing the whole `infrastructure/steam` package would take a working, unrelated capability with it.

## Risks / Trade-offs

**A variant not yet in the bottle becomes uninstallable from the CLI.** → It becomes installable through the Steam client, which is the only way it could reach the bottle regardless. The failure names the variant and its application id and says so.

**Playtest access is gated by an invitation, so a variant may be unavailable.** → Unchanged by this work. The download command could not obtain an unentitled application either.

**The build-id capability is lost.** → Nothing passes a build id, and both call sites request the current build only.

**Removing configuration keys breaks an existing local override.** → The override for the main variant becomes unnecessary, since discovery finds the same installation. The failure names the removed key if one is left behind.

**Discovery depends on a manifest the client writes.** → That is the point. The manifest is the record of what is installed, and reading it is what keeps the tooling and the client agreeing.

## Migration Plan

1. Remove the download command, the wrapper, and their tests. Nothing else consumes them.
2. Collapse resolution to discovery and widen its failure reporting.
3. Remove the configuration keys and the `[steam]` section, then delete the local override that reconciled them.
4. Confirm each installed variant resolves, and that an uninstalled variant fails with a report naming it.
5. Run an extraction for the main variant and compare its output against a run recorded before step 1.

Rollback is per commit. Steps 1 and 2 are independent of step 3, so the configuration removal can be reverted without restoring the downloader.
