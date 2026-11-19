# Design

## Context

See proposal.md for the reasons and the scope.

- The playtest variant (`-V playtest`, app 3090030) has its own paths in `config.toml`. Before this change it had no Unity project, no clean database and no backup.
- The installed playtest build is 26769622 from the public branch. `skill://refreshing-game-data` is the procedure for one variant, from rip to approved publication.
- `variants/playtest/audits/update-readiness.json` (17 Oct, build 25971160) compared the decompiled assemblies without exporting assets. It found these gaps:
  - 21 code-facts failures.
  - 17 native inputs that need a classification and 8 fields that are declared but never read.
  - Starter items and skill levels written for six classes.
  - Item harmony and dissonance.
  - The Bard aura.
  - The seven-way chessboard.
  - The Glowmere wall passage.
- The clean `classes` table already comes from class assets. `ClassDisplayNameService` reads display names from it. The six-class assumptions sit in the consumers, such as `wiki_lua/skills.py`, `generators/sections/skill.py` and `item.py`, `overview_base.py`, `semantic_validation.py`, `critical_strike_model.py` and the sheet query tests.
- `extract compare-variants` compares the clean databases of two variants. `extract changes` compares a variant with its earlier backed-up builds.

## Goals / Non-Goals

Goals:

- On 1 Dec, the work between the 0.8 build landing on `main` and approval of each consumer's publication is a short, known runbook. It is not development.
- Each code change for 0.8 is tested against the playtest data and keeps the 0.7 data on `main` working.

Non-goals:

- New consumer features that 0.8 does not need.
- Fixing the playtest build's own bugs.

## Decisions

### D1. Prepare on the playtest variant, cut over by refreshing `main`

All extraction and generation for 0.8 runs with `-V playtest` against `variants/playtest/`. On release day, `main` is refreshed from the shipped build with the same pipeline. `extract compare-variants` then compares main with the playtest, and every difference gets a review before publication.

Alternative: copy the playtest outputs to `main`'s targets. Rejected because the shipped build can differ from the last playtest build, and publication must come from the build that players have.

### D2. Generic classes, not a seventh entry

Each consumer that lists classes reads them from the clean `classes` table, skipping the non-playable `Default`, and from class junction tables. Skill levels live in `skill_classes`, derived by matching each playable raw class asset to its `Skills` level field. Missing or unmatched fields fail the clean build. Adding `Bard` to each list would leave the next class with the same problem, and `specs/character-classes` forbids closed lists. Where a consumer needs a value per class that the game doesn't export, it keeps that value in one file, and generation fails when a class has none.

Item tooltips accept comma-separated class display names in `classes` and display-name/level pairs in `class_levels`, such as `Arcanist: 5, Druid: 7`, instead of one parameter per class. Generation resolves labels through `classes`. The templates render those plain values through shared Lua formatters, preserving the existing spans and level rows without coupling article parameters to tooltip markup.

### D3. Each new mechanic comes from its source of truth

Each 0.8 mechanic that a consumer presents comes from exported data or a code fact, never from patch-note text. This covers songs, notes and chords, harmony and dissonance, the Bard aura, the chessboard, the Glowmere passage, the entry quest for Ripper's Keep, the Persuasion rename and the charisma and wand rebalance. The code-facts failures get re-derived from the shipped methods and never re-pinned blindly (`skill://code-facts`). When a mechanic changes a requirement in `runtime-item-mechanics`, `progression-requirements`, `encounter-tiers` or `quest-routes`, this change adds the delta spec before the code change.

### D4. Every playtest build re-runs the same pipeline

When a newer playtest build ships before release, the playtest variant is ripped and extracted again. `extract changes --since <previous-build>` lists the differences, which then get a review. A newer build therefore costs one pipeline run, not new work for each consumer.

### D5. Map tiles: new zones plus changed scenes

Tiles are shared across variants. Each new 0.8 zone needs bounds, tiles and an overview position. Changed scenes come from comparing the scene assets of the playtest rip with `main`'s rip. Each zone whose geometry changed gets a recapture, including Ripper's Keep and the zones with new vendor buildings. MapTileCapture turns off fog and replaces the ambient light in indoor zones, but outdoor zones keep the game's sun. 0.8 changes that lighting. One outdoor zone gets captured as a test and compared with its current tiles before deciding whether every outdoor zone needs a recapture. MapTileCapture itself has to run in 0.8 before any capture. New tiles stay local until release day, because publishing them would show 0.8 terrain to 0.7 players.

### D6. Mods are checked in the running playtest

Each mod in scope (AdventureGuide, Interactive Map Companion, JusticeForF7, Sprint) gets built against the playtest assemblies and run in the playtest game with a dedicated save. A mod passes when its user interface opens, works with the new game interface and reads no removed game member. A fix must keep the mod working with 0.7 until the release, or it waits for release day as a tested branch.

### D7. Publication is all at once and gated

Nothing goes to a shared target before 0.8 ships on `main`. On release day the runbook runs, in order: the `main` refresh, the variant comparison, consumer previews, approval, and publication through the existing gated commands with their rollback manifests (`wiki deploy-repo-pages`, `sheets deploy`, `images publish`, `maps deploy`, mod releases).

## Risks / Trade-offs

- [The shipped build differs from the last playtest build] → Every consumer gets regenerated from `main` on release day. The variant comparison shows the differences, and they get a review before approval.
- [Playtest builds keep arriving, 3 to 5 a week] → D4 keeps a new build to one pipeline run. Builds get re-extracted when they change data that a consumer uses, and in any case before each review point.
- [Work paused in other changes conflicts with 0.8 edits] → 0.8 has priority. Paused changes rebase onto 0.8 work afterwards, and their tasks.md files record the pause.
- [The new user interface breaks mods on day one] → D6 tests the mods before release. Releases needing 0.8-only APIs are prepared as tested builds and published on release day.
- [Recapturing tiles takes a long time] → Captures start with the new zone and the zones whose geometry changed, and run in the weekend sessions of 21 and 28 Nov.

## Migration Plan

1. Extract the playtest and review its data.
2. Land the code changes, each keeping `main` (0.7) green under `uv run erenshor test ci`.
3. Prepare every consumer locally with `-V playtest` and review its previews.
4. Release day: run the runbook in tasks.md section 7.

Rollback per consumer uses the existing manifests and `--revert` options. A failed consumer publication stops that consumer only and leaves the others unchanged.

## Open Questions

- Which zones besides Glowmere Grotto and Ripper's Keep changed geometry. The scene comparison in task 5.1 answers this.
- Whether Glowmere Grotto has more than one scene or floor. The rip answers this.
