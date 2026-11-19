# Proposal

## Why

Erenshor 0.8 "Verses of Adventure" ships on 1 Dec 2026. It adds a seventh class (Bard), a new dungeon (Glowmere Grotto), a rebuilt Ripper's Keep, new quests, a raid boss, a vendor network, renamed and rebalanced stats, and a new user interface. The public playtest branch already carries this content (build 26769622 on 19 Nov). Every consumer of this repository reads the game data and assumes six classes, the old zones and the old interface. On release day, the wiki, Sheets, map, pictures and companion mods would show stale or wrong data unless they are prepared against the playtest first.

## What Changes

- Extract the playtest variant end to end from the public playtest branch: rip, export, code facts, clean build and change report. Repeat this for each playtest build that ships before release.
- Treat every class that the game exports as a class. Replace the lists hard-coded to six classes in the export listeners, processors, wiki generators, Lua modules, sheet queries and tests with data from the exported classes.
- Model the new mechanics that consumers present, each from shipped code or exported data:
  - Bard songs, notes and chords, item harmony and dissonance, and the Bard aura.
  - The seven-piece chessboard and the Glowmere wall passage.
  - The quest that Ripper's Keep requires to enter.
  - The renamed and rebalanced stats.
- Resolve the code-facts failures, the native fields that have no classification yet and the spawn-coverage findings that the 0.8 build raises. Do not loosen any gate.
- Prepare each consumer locally against the playtest data:
  - Wiki pages and data modules, including the content-lifecycle handling for renamed or removed content.
  - Google Sheets.
  - Interactive map, with tiles, bounds and overview positions for Glowmere Grotto and for every zone whose scene changed.
  - Wiki pictures for new and changed models.
  - AdventureGuide data.
  - The AdventureGuide, Interactive Map Companion, JusticeForF7 and Sprint mods, checked against the new interface in the running playtest.
- Write a release-day runbook that refreshes `main` from the shipped 0.8 build and compares it with the prepared playtest data. It publishes every consumer only after approval.
- Nothing is published to a shared target before 0.8 ships on `main`.

## Non-goals

- Erenshor Logs support for the Bard class.
- The open work from other changes, unless 0.8 depends on it. `unify-item-provenance` and the wiki changes in progress ship with the 0.8 release only if they are ready by then. Otherwise they stay paused.
- Publishing playtest data anywhere, including the playtest spreadsheet.

## Migration boundary

Code changes land on `main` while `main`'s database still holds 0.7 data, so each change keeps 0.7 working: a generic class set covers six classes as well as seven. The cutover happens on release day, when `main` is extracted from the 0.8 build and published. Until then, playtest output stays in `variants/playtest/` and in local previews.

## Capabilities

### New Capabilities

- `character-classes`: the set of playable classes comes from the exported class assets. Every consumer covers each exported class, and none of them keeps a closed list of classes.

### Modified Capabilities

None known yet. The data review in task group 2 decides whether the new mechanics change `runtime-item-mechanics`, `progression-requirements`, `encounter-tiers` or `quest-routes`. If one does, this change adds its delta spec before the code changes.

## Impact

- The Unity export listeners under `src/Assets/Editor/ExportSystem/`, `field-coverage.json` and `dynamic-spawn-catalog.toml`.
- The code-facts registry.
- The processors under `src/erenshor/application/processor/`.
- The wiki generators and `wiki_lua`.
- The sheet queries.
- `quest_guides/`.
- `mapping.json`, `barriers.toml`, the map capture config and zone positions, and the tiles.
- The mods under `src/mods/`.
- The playtest variant's working files under `variants/playtest/`, which are not committed.
