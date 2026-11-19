## Publication permission

Nothing from this change goes to a shared target before Erenshor 0.8 ships on `main`. Shared targets are the wiki, Google Sheets (including the playtest spreadsheet), the map Workers, wiki pictures, Thunderstore and the Erenshor Vault. Every publication in section 7 needs explicit approval of its reviewed preview. Local verification does not authorize publication.

## Priority

0.8 has priority over every other change in progress. Do work from another change here only when 0.8 needs it, and record the dependency in that change's tasks.md.

## 1. Playtest data (design D1, D4)

- [x] 1.1 Rip the installed public playtest build (26769622) with `uv run erenshor -V playtest extract rip`. Verify: the playtest Unity project exists and the rip reports the build ID.
  - The rip itself does not print the build ID. The export backup records it as `variants/playtest/backups/build-26769622`.
- [x] 1.2 Compare the decompiled playtest scripts with `variants/main/backups/build-24405256/scripts/`. Record each changed mechanic outside the code-facts registry in this file, with the class and method. Verify: every type that the readiness audit names (`BardSong`, `Chessboard`, `GlowmereSayScript`, `Stats`, `Inventory`, `ItemInfoWindow`, `CharSelectManager`) has an entry or a note that it did not change.
  - The record is in `script-changes.md` next to this file. Every type the audit names has an entry there.
- [x] 1.3 Run `extract export`. Reconcile `src/tools/ExportSurface/field-coverage.json` with the playtest DLL, classifying the 17 native inputs and the 8 declared-only fields from the readiness audit against their serialized bindings. If the export exits 3, follow `skill://auditing-spawn-coverage`. Each classification or listener change is its own commit. Verify: export exits 0 without a bypassed gate.
  - The gate found 114 new fields. 27 are captured and the rest are classified as interface, audio, animation or runtime state. The export exits 0 with no spawn-coverage findings.
  - `NeverRain` hides the rain effect only. Logical rain and weather-dependent spawns are unchanged in those zones.
- [x] 1.4 Run `extract code-facts` and resolve each failure from the shipped method (`skill://code-facts`). Keep the main-only critical-strike facts as explicit skips. Each re-derived fact or matcher fix is its own commit. Verify: no fact fails, and the skips are the ones listed.
  - All facts bind for build 26769622. `RaidSkaldEvent` is pending under task 3.3.
- [x] 1.5 Run `extract build` and fix processor errors at their source. Verify: the clean database and its backup exist for build 26769622.
  - The build needed a zone type for Glowmere Grotto, two Ripper's Keep door records, a shifted Stowaway object key and the song scroll titles of design D8.
- [x] 1.6 Run `extract compare-variants` between main and the playtest, review every table, and run `progression show --gaps` for the playtest. Record the new zones, quests, NPCs, items, spells and classes, the renamed and removed content, and the new progression gaps in this file. Verify: each of the following has a row, or a note that it is missing from the data:
  - The record is in `data-changes.md`, and the developer's playtest notes are in `playtest-changelog.md`.
  - The Bard class and its songs, notes and chords.
  - Glowmere Grotto.
  - The Ripper's Keep entry quest.
  - The new quests and the quest giver in the Revival Plains.
  - The Vitheo's Plane raid boss.
  - The six Bard vendors.
  - The furniture item.
  - The Mind to Persuasion rename.
- [ ] 1.7 Decide which mechanics change an existing spec (design D3). Add those delta specs to this change before their code tasks. Verify: `openspec validate prepare-for-verses-of-adventure --strict` passes.
  - The encounter-tiers delta recognizes raid event boss bindings and passes strict validation. The existing character placement requirement covers the accompanist dependency.

## 2. Classes (design D2, specs/character-classes)

- [x] 2.1 `refactor: read playable classes from the clean classes table`: replace every six-class list in the export listeners, processors, wiki generators, `wiki_lua`, `semantic_validation.py`, `critical_strike_model.py`, the sheet queries and their tests with the exported classes, skipping `Default`. Keep any per-class value that the game doesn't export in one file, and make generation fail when a class has none. Verify: `uv run erenshor test ci` passes on `main` (0.7), and the playtest build lists the Bard among its seven classes.
  - Skill levels live in `skill_classes`, and the item templates take `classes` and `class_levels`. CI passes, and the playtest database lists seven classes with 19 Bard skills and 63 Bard spells. The critical-strike model keeps its named Stormcaller and Windblade profiles because no exported data classifies them.
- [x] 2.2 `feat: show the Bard in starter items, skills and spells`: run the playtest wiki, Lua and sheet generation and fix what is still missing for the Bard. Verify: the Bard's starter items, skills and spell levels appear in the generated pages, data modules and sheet previews.
  - All 3,062 articles passed semantic validation and 790 Lua modules compiled. The Bard data and its item sources, 19 skills and 58 learned spells are present. The other five Bard spell records are equipped aura effects and retain their levels without appearing in the learned ability view. All nine starter items are in the item sources, including Bread and Water. No generator fix was needed.

## 3. New mechanics (design D3)

Each task below adds the data at its source (export, code fact or reviewed file), and then presents it in the consumers that already show that kind of fact. Fill in the exact scope from the findings of 1.2 and 1.6.

- [ ] 3.1 Bard songs, notes and chords: what each one does, how it is learned and where it drops. Songs are ordered compositions of chords with capacity from `SkillPower`, and their damage applies the Bard charisma curve twice (`script-changes.md`, Spells, skills and songs). Include Hum, Caesura and the Songwriting book. Verify: the generated pages for Simple Song and Elrehon's Crescendo match the game tooltips.
- [ ] 3.2 Item harmony and dissonance, and the Bard aura from the caster's charisma, as `script-changes.md` describes them. Verify: an item with harmony shows the same value as its in-game tooltip.
- [ ] 3.3 The seven-piece chessboard (FacelessBard), the Glowmere wall that the spoken word `respite` opens, and The Skald in Plane of Vitheo, whose four accompanist spawn points are active only while he lives. Export the wall reference and the accompanist dependency from their serialized bindings and model them through the existing producers. Verify: `progression show` explains each, the Glowmere route reaches the dungeon, and the map shows the accompanists as dependent on The Skald.
  - The Glowmere trigger exports its bounds and moved wall. The keyword comes from shipped code. Scene geometry places the Pirate's Ledger behind the wall, pending the in-game check in 3.6. Both exterior entrances are usable in the clean database and do not require `respite`.
  - The Skald's controller exports the boss and accompanist spawn points. Processor tests cover boss classification and the live spawn dependency in progression ways. Playtest re-export and map presentation are still open.
- [ ] 3.4 Ripper's Keep: the gate door needs Ripper's Gate Key from the guard's quest `RIPPERKEY`, the ritual portal opens after `TheRipperRitual`, and the Ripper spell moves its destination. Model the three as separate routes. Also cover Flicker of Souls dying on quest turn-in and the new quests. Verify: `progression show` for Ripper's Keep shows the key gate and the ritual route, and the guide data holds each new quest.
- [ ] 3.5 The Persuasion label, the wand damage roll in `[0.1, 1]`, threat now using the attacker's stance without low-health multipliers, damage amplification, status resist and duration changes, and the new cooldown and haste-cap modifiers. Verify: no generated page or sheet says "Mind" for the stat, and every combat claim on the wiki matches the new code and code facts.
- [ ] 3.6 Check the barriers of each zone where placements moved (refresh skill, review step 3). Verify: each barrier check in `barriers.toml` passes in the playtest game.

## 4. Wiki and Sheets (prepared locally)

- [ ] 4.1 Run `-V playtest wiki generate` and `wiki generate-lua`, review the output for the new and changed content, and fix generation at its source. Verify: generation passes semantic validation, and a local stack renders the Bard, Glowmere Grotto, Ripper's Keep and a Bard song page without script errors.
- [x] 4.2 Run the retired-page review for renamed and removed content (`wiki-content-lifecycle`), against the playtest data. Record the notices and redirects that release day must apply. Verify: every title that 0.8 renames or removes has a reviewed action.
  - On release day after approval, move `A Faerie Drone` to `Faerie Drone`, `Lifeflame Brazier` to `Life Flame Brazier`, and `Creeping Waistband` to `Observer's Waistband`, leaving redirects and retaining article history. The waistband keeps item ID `42273351` but changes its stable key from `item:belt - 42 - creeping waistband` to `item:belt - 44 - creeping waistband`. Update the moved root to the new key before fetching and regenerating it. No new Historical Content notices are needed.
  - The live review checked 816 bot-created titles. It flagged the brazier and waistband without dispositions and did not enumerate the non-bot drone article. The three old articles exist and none of the new titles is live, so the existing redirect command cannot preview those moves. Its dry run failed closed. Record the redirects in `content-lifecycle.json` only once `main` generates the new titles, then repeat the audit after the approved moves.
- [x] 4.3 Run `-V playtest --dry-run sheets deploy --all-sheets` and review the Bard and the new content. Verify: no query fails and no class column is missing.
  - All 24 tabs previewed 34,934 rows. The class queries include the Bard and skill and spell levels. Item sources list the full Bard starter inventory, and the zone and character tabs include Glowmere Grotto, Ripper's Keep and The Skald. No query fix was needed.
- [ ] 4.4 Capture every in-game tooltip and window kind in the playtest (weapon, armor, charm, instrument, spell scroll, skill book, song scroll, spell, skill, chord and note, the song composer, the Bard class description, the character window with Persuasion) and compare each with the wiki's tooltip templates. Propose the wiki presentation for each in Plannotator with `skill://compare-options`, then restyle the templates, Lua modules and `wiki/gadgets/erenshor.css`. Verify: a local stack renders each kind next to its in-game capture, and the tooltip parity check of `capture-wiki-tooltip-parity` reports no unexplained text difference.
  - Implemented D9 in the maintained tooltip templates, Lua renderers and gadget styles. The playtest review has desktop and 390 px captures of the eight item kinds, spell, skill, chord, note and Simple Song. The standalone in-game note capture and the full-build comparison in `capture-wiki-tooltip-parity` remain open.

## 5. Map, tiles and pictures (design D5)

- [x] 5.1 Compare the scene assets of the playtest rip with `main`'s rip. List the zones whose geometry changed. Verify: the list covers Glowmere Grotto, Ripper's Keep and Faerie's Brake, and records each other changed zone.
  - [Scene comparison](scene-changes.md) records nine zones that need tiles, including new bounds for Glowmere Grotto and Faerie's Brake. Loomingwood Forest and Vitheo's Plane of Valor need placement updates, not new tiles.
- [ ] 5.2 Check that MapTileCapture runs in 0.8, and fix it if it doesn't. Then capture one outdoor zone and compare it with its current tiles to decide whether the new lighting needs a full recapture. Record the decision here.
- [ ] 5.3 Add the capture bounds and overview position for Glowmere Grotto, and capture it and every zone from 5.1 (`skill://tile-capture`, `skill://interactive-map`). Verify: `-V playtest maps preview` shows each zone with markers and no failure on `/map`.
- [ ] 5.4 Run `images manifest` and `images items manifest`, capture the new and changed subjects in the playtest game, review the captures, then run `-V playtest --dry-run images publish`. Verify: the Bard armor and weapon, the new NPCs and the furniture item have reviewed pictures, and the dry run lists no unexplained conflict.

## 6. Mods (design D6)

- [x] 6.1 Build the AdventureGuide, Interactive Map Companion, JusticeForF7 and Sprint against the playtest assemblies, then fix compile errors without breaking the 0.7 build. Verify: the mods build for both variants.
  - All five mods, including MapTileCapture, build and pass artifact verification for BepInEx and Lunaris on main (24405256) and playtest (26769622). No compile fixes were needed. All 1,066 mod tests passed.
  - In-game checks still needed: guide inventory and quest updates, journal replacement and focus with the new windows and hotbars, map overlay and Bard SimPlayers across zones, F7 nameplate subtext and cast bars, and Sprint with Bard movement effects and Shift bindings. For capture, check the start-choice screen, outdoor light, and instrument portraits.
- [ ] 6.2 Run each mod in the playtest game with a dedicated save. Verify: the guide opens, tracks a new quest and shows a 0.8 zone; the map companion shares the live position on the map preview; JusticeForF7 and Sprint work as described in their READMEs.
  - All four mods load under BepInEx with a Bard in Ripper's Keep, Glowmere Grotto and Willowwatch. The guide window draws over the new interface, reads Glowmere Grotto as the current zone, and after "A Key to Ripper's Keep" was assigned its tracker shows the quest beside the game's own quest tracker. Sprint raises run speed from 9.25 to 13.875, keeps it through `CalcStats` and restores it on release. The game's F7 toggle hides and restores the guide and tracker windows with the rest of the interface. The map companion's WebSocket and overlay connected to the live map. Still open: the map companion on a playtest map preview (with task 5.3) and the keyboard focus and UI scale checks of the 6.1 risk list, which need real key presses.
- [x] 6.3 Run `-V playtest guide export-mod` and check that the guide shows the Bard quest and the Ripper's Keep entry quest with their requirements. Do not commit the playtest guide data. Release day regenerates it from `main`.
  - The export holds 195 quests. "Old Bonepits Songbook" (Brandon Uree, say "tale", one Old Song Book) and "A Key to Ripper's Keep" (Ripper Gate Guard, say "killed", one Sivakayan Ore) show their steps and rewards. The committed guide data was restored afterwards.
- [ ] 6.4 Prepare a release build and changelog for each mod that changed, without publishing them.

## 7. Release day runbook (design D7)

- [ ] 7.1 Once 0.8 is live, update `main` in Steam and run the refresh skill end to end for `-V main`. Verify: the clean database records the 0.8 build ID.
- [ ] 7.2 Run `extract compare-variants` between main and the playtest, and review each difference from the last prepared playtest build.
- [ ] 7.3 Regenerate every consumer from `main` and review the previews: wiki pages and Lua, the lifecycle actions from 4.2, Sheets, map with tiles, pictures, and guide data.
- [ ] 7.4 Ask for approval, then publish wiki, Sheets, pictures, map and mods. Keep each rollback manifest. The item templates take generic `classes` and `class_levels` parameters instead of one parameter per class, so deploy the templates, their Lua modules and the regenerated item pages in one run. Verify: a live parse of the Bard and Glowmere Grotto pages shows no script error, the map shows Glowmere Grotto, the mod listings show the new versions, and an item page shows its classes.
- [ ] 7.5 Update the README for any changed workflow, record the outcome in the project note and archive this change.
