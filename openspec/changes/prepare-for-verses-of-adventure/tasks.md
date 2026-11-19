## Publication permission

Nothing from this change goes to a shared target before Erenshor 0.8 ships on `main`. Shared targets are the wiki, Google Sheets (including the playtest spreadsheet), the map Workers, wiki pictures, Thunderstore and the Erenshor Vault. Every publication in section 7 needs explicit approval of its reviewed preview. Local verification does not authorize publication.

## Priority

0.8 has priority over every other change in progress. Do work from another change here only when 0.8 needs it, and record the dependency in that change's tasks.md.

## 1. Playtest data (design D1, D4)

- [ ] 1.1 Rip the installed public playtest build (26769622) with `uv run erenshor -V playtest extract rip`. Verify: the playtest Unity project exists and the rip reports the build ID.
- [ ] 1.2 Compare the decompiled playtest scripts with `variants/main/backups/build-24405256/scripts/`. Record each changed mechanic outside the code-facts registry in this file, with the class and method. Verify: every type that the readiness audit names (`BardSong`, `Chessboard`, `GlowmereSayScript`, `Stats`, `Inventory`, `ItemInfoWindow`, `CharSelectManager`) has an entry or a note that it did not change.
- [ ] 1.3 Run `extract export`. Reconcile `src/tools/ExportSurface/field-coverage.json` with the playtest DLL, classifying the 17 native inputs and the 8 declared-only fields from the readiness audit against their serialized bindings. If the export exits 3, follow `skill://auditing-spawn-coverage`. Each classification or listener change is its own commit. Verify: export exits 0 without a bypassed gate.
- [ ] 1.4 Run `extract code-facts` and resolve each failure from the shipped method (`skill://code-facts`). Keep the main-only critical-strike facts as explicit skips. Each re-derived fact or matcher fix is its own commit. Verify: no fact fails, and the skips are the ones listed.
- [ ] 1.5 Run `extract build` and fix processor errors at their source. Verify: the clean database and its backup exist for build 26769622.
- [ ] 1.6 Run `extract compare-variants` between main and the playtest, review every table, and run `progression show --gaps` for the playtest. Record the new zones, quests, NPCs, items, spells and classes, the renamed and removed content, and the new progression gaps in this file. Verify: each of the following has a row, or a note that it is missing from the data:
  - The Bard class and its songs, notes and chords.
  - Glowmere Grotto.
  - The Ripper's Keep entry quest.
  - The new quests and the quest giver in the Revival Plains.
  - The Vitheo's Plane raid boss.
  - The six Bard vendors.
  - The furniture item.
  - The Mind to Persuasion rename.
- [ ] 1.7 Decide which mechanics change an existing spec (design D3). Add those delta specs to this change before their code tasks. Verify: `openspec validate prepare-for-verses-of-adventure --strict` passes.

## 2. Classes (design D2, specs/character-classes)

- [ ] 2.1 `refactor: read playable classes from the clean classes table`: replace every six-class list in the export listeners, processors, wiki generators, `wiki_lua`, `semantic_validation.py`, `critical_strike_model.py`, the sheet queries and their tests with the exported classes, skipping `Default`. Keep any per-class value that the game doesn't export in one file, and make generation fail when a class has none. Verify: `uv run erenshor test ci` passes on `main` (0.7), and the playtest build lists the Bard among its seven classes.
- [ ] 2.2 `feat: show the Bard in starter items, skills and spells`: run the playtest wiki, Lua and sheet generation and fix what is still missing for the Bard. Verify: the Bard's starter items, skills and spell levels appear in the generated pages, data modules and sheet previews.

## 3. New mechanics (design D3)

Each task below adds the data at its source (export, code fact or reviewed file), and then presents it in the consumers that already show that kind of fact. Fill in the exact scope from the findings of 1.2 and 1.6.

- [ ] 3.1 Bard songs, notes and chords: what each one does, how it is learned and where it drops. Verify: the generated pages for Simple Song and Elrehon's Crescendo match the game tooltips.
- [ ] 3.2 Item harmony and dissonance, and the Bard aura from charisma, as the readiness audit describes them. Verify: an item with harmony shows the same value as its in-game tooltip.
- [ ] 3.3 The seven-piece chessboard (FacelessBard) and the Glowmere wall passage, through their existing producers. Verify: `progression show` explains each, and the Glowmere route reaches the dungeon.
- [ ] 3.4 The quest turn-in that Ripper's Keep requires, the change to Flicker of Souls and the new quests. Verify: `progression show` for Ripper's Keep shows the quest gate, and the guide data holds each new quest.
- [ ] 3.5 The Persuasion rename and the charisma and Arcanist wand rebalance. Verify: no generated page or sheet says "Mind" for the stat, and every damage claim on the wiki matches the new code facts.
- [ ] 3.6 Check the barriers of each zone where placements moved (refresh skill, review step 3). Verify: each barrier check in `barriers.toml` passes in the playtest game.

## 4. Wiki and Sheets (prepared locally)

- [ ] 4.1 Run `-V playtest wiki generate` and `wiki generate-lua`, review the output for the new and changed content, and fix generation at its source. Verify: generation passes semantic validation, and a local stack renders the Bard, Glowmere Grotto, Ripper's Keep and a Bard song page without script errors.
- [ ] 4.2 Run the retired-page review for renamed and removed content (`wiki-content-lifecycle`), against the playtest data. Record the notices and redirects that release day must apply. Verify: every title that 0.8 renames or removes has a reviewed action.
- [ ] 4.3 Run `-V playtest --dry-run sheets deploy --all-sheets` and review the Bard and the new content. Verify: no query fails and no class column is missing.

## 5. Map, tiles and pictures (design D5)

- [ ] 5.1 Compare the scene assets of the playtest rip with `main`'s rip. List the zones whose geometry changed. Verify: the list covers Glowmere Grotto and Ripper's Keep and records each other changed zone.
- [ ] 5.2 Check that MapTileCapture runs in 0.8, and fix it if it doesn't. Then capture one outdoor zone and compare it with its current tiles to decide whether the new lighting needs a full recapture. Record the decision here.
- [ ] 5.3 Add the capture bounds and overview position for Glowmere Grotto, and capture it and every zone from 5.1 (`skill://tile-capture`, `skill://interactive-map`). Verify: `-V playtest maps preview` shows each zone with markers and no failure on `/map`.
- [ ] 5.4 Run `images manifest` and `images items manifest`, capture the new and changed subjects in the playtest game, review the captures, then run `-V playtest --dry-run images publish`. Verify: the Bard armor and weapon, the new NPCs and the furniture item have reviewed pictures, and the dry run lists no unexplained conflict.

## 6. Mods (design D6)

- [ ] 6.1 Build the AdventureGuide, Interactive Map Companion, JusticeForF7 and Sprint against the playtest assemblies, then fix compile errors without breaking the 0.7 build. Verify: the mods build for both variants.
- [ ] 6.2 Run each mod in the playtest game with a dedicated save. Verify: the guide opens, tracks a new quest and shows a 0.8 zone; the map companion shares the live position on the map preview; JusticeForF7 and Sprint work as described in their READMEs.
- [ ] 6.3 Run `-V playtest guide export-mod` and check that the guide shows the Bard quest and the Ripper's Keep entry quest with their requirements. Do not commit the playtest guide data. Release day regenerates it from `main`.
- [ ] 6.4 Prepare a release build and changelog for each mod that changed, without publishing them.

## 7. Release day runbook (design D7)

- [ ] 7.1 Once 0.8 is live, update `main` in Steam and run the refresh skill end to end for `-V main`. Verify: the clean database records the 0.8 build ID.
- [ ] 7.2 Run `extract compare-variants` between main and the playtest, and review each difference from the last prepared playtest build.
- [ ] 7.3 Regenerate every consumer from `main` and review the previews: wiki pages and Lua, the lifecycle actions from 4.2, Sheets, map with tiles, pictures, and guide data.
- [ ] 7.4 Ask for approval, then publish wiki, Sheets, pictures, map and mods. Keep each rollback manifest. Verify: a live parse of the Bard and Glowmere Grotto pages shows no script error, the map shows Glowmere Grotto, and the mod listings show the new versions.
- [ ] 7.5 Update the README for any changed workflow, record the outcome in the project note and archive this change.
