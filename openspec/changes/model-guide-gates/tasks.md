# Tasks

## 0. Remove the unused dense guide

- [x] 0.1 `refactor(guide): stop generating guide.json`: confirm that no code, CI job, map file, or document reads `quest_guides/guide.json`, then remove `guide compile`, `json_writer.py`, their tests, and the file, and update the README, the AdventureGuide README, and `skill://refreshing-game-data`. Verify: a repository search for `guide.json` finds only `quest-guide.json`, and `uv run erenshor test unit` passes.
  - Done in 6c28bd251. The compiler stages that only `guide.json` serialized went too. `quest-guide.json` was byte-identical before and after. The only remaining mention is a historical note in `adopt-data-backed-wiki`.

## 1. Condition model and keyed doors

- [x] 1.1 Measure the baseline of design D10 on the mod built from the current commit (BepInEx, main variant, test character with twelve tracked quests, one navigated) in Stowaway's Step and Shivering Step. Verify: the averages, minimums, and maximums are recorded under this task, and `pgrep -f Erenshor.exe` prints nothing afterwards.
  - Done on 2026-10-16 with the mod of 6c28bd251 on the test character Gatetest (slot 11). Times are synchronous calls in the running game through HotRepl: the runtime tick (`TickActive`, without drawing) as a direct delegate, the guide's half of an event (the patch handler, then one tick), and the runtime's scene-load handler plus one tick. A synchronous loop of ticks skips the 0.25 s source re-pick, which runs in real frames only.

    | Measurement | Stowaway's Step | Shivering Step |
    | --- | --- | --- |
    | Tick, 600 calls | avg 0.04, min 0.03, max 0.28 ms | avg 0.02, min 0.01, max 0.28 ms |
    | Managed allocation per tick (`GC.GetTotalMemory` over 600 ticks) | 0 B | 0 B |
    | Inventory change, 10 events | avg 2.0, min 1.2, max 4.8 ms | avg 1.8, min 1.3, max 3.9 ms |
    | Quest completion, 10 events | avg 3.2, min 1.4, max 6.7 ms | avg 2.8, min 1.4, max 10.2 ms |
    | Scene load, 5 repeats after a warm-up | avg 15.9, min 12.5, max 23.4 ms | avg 16.9, min 13.3, max 22.2 ms |

    The slowest quest completion (10.2 ms) already exceeds the absolute 8 ms the spec named, so the event budget is now relative to the baseline. These first numbers are not comparable with the slice 1 results under 1.4: the navigated quest and the tracked set were not fixed, and `GC.GetAllocatedBytesForCurrentThread` always returns 0 under the game's Mono runtime.
- [x] 1.2 `feat(pipeline): record gates as conditions in the clean database`: add `gate_conditions` to `writer.py` and derive it from the existing quest unlocks of zone lines and characters, quest-started and quest-stopped spawn points, Reliquary furnishings, vendor stock unlocks, item bag unlocks, and keyed doors through `barriers.toml`. Add `barriers.toml` with an entry for every keyed door, moving the door and item edges out of `graph_overrides.toml`, and fail the build on a missing or stale entry. Drop `zone_line_quest_unlocks` and `character_quest_unlocks`. Document `barriers.toml` in the README's concepts. Add unit tests for each atom source and both completeness failures. Verify: the tests pass, and after a clean build (announced in the status) the slice 1 scenarios of `guide-gate-data` hold in SQL.
  - Done, with `[[entries]]` added in `feat(pipeline): record targets that only some entrances reach`. `barriers.toml` has 29 entries for the 40 keyed doors of the main build. Each was reviewed in the game: a NavMesh obstacle carved into the door, paths from the scene entry compared before and after, and plan renders, perspective renders, and the wiki for what the NavMesh does not reach. The five Bellwain house doors guard nothing in the data, because the house has no NavMesh. On a clean build from the current raw export the slice 1 scenarios hold in SQL: no quest-only unlock tables, Ghost of Wyland Sercher's spawn point and the Stowaway's Step lighthouse zone line carry the matching key atoms, and every Reliquary room placement carries its furnishing atom.
- [x] 1.3 `feat(guide): compile and ship typed gate conditions`: build unlock edges from `gate_conditions`, extend `_compile_unlock_predicates` to the atom kinds, add the size limit and the acyclicity check, and write `quest-guide.json` version 7 as design D4 describes. In the mod, load the conditions, add `GateConditions` with the keyring check of design D6, remove `FurnishingStatus` and the separate furnishing checks, and migrate every consumer of the old gate fields. Add compiler tests for each atom kind and a cycle, the database-to-JSON contract test, and `GateConditions` tests on the real data, moving the existing furnishing tests onto the atom. Update the AdventureGuide README's data section. Verify: Python and C# tests pass, `uv run erenshor mod build --mod adventure-guide --loader all` succeeds, and the regenerated `quest-guide.json` holds the door gates of the spec scenarios.
  - Done. The regenerated `quest-guide.json` gives Founder the Dockhouse Key, Ghost of Wyland Sercher the Ghostly Key, and the Duskenlight Coast line to the Jaws of Sivakaya a candle group and a She Sees You group. The contract test passes.
- [x] 1.4 `feat(adventure-guide): lead navigation to what unlocks a gate`: add requirement selection and chains (design D7) to navigation, the navigation display, the detail panel, and the tracker, and `DumpGate` with the chain in `DumpNav`. Update `skill://runtime-eval`. Add tests on the real data for the lighthouse key, the Jaws alternatives, and a chain of two requirements. Verify: tests pass, the slice 1 checks of design D12 pass in the game with screenshots, and the budgets hold.
  - Done. Requirement chains, entrance routing for placements with `entries`, door zones in key requirements, and a keyring event that re-resolves navigation. The slice 1 checks of design D12 pass in the game on Gatetest: Whispers of Wyland without the Ghostly Key names the key and stops, because the key is crafted, and with the key on the keyring it navigates to the ghost. Occuphage from Blacksalt Strand routes through Stowaway's Step to the lighthouse line, and without the key the chain leads to Garrey Ambrose. The Shivering Step crypt from Stowaway's Step leads to the Crypt Keeper. A Reliquary vendor appears when its room holds the set, and Bassle Wavebreak is available after The Angler's Ring. The Lunaris build loads, navigates Occuphage with the same chain, and quits after the save.
  - Budgets, both builds measured the same way in one session: twelve fixed tracked quests, Alice Hewer's Necklace navigated, one untimed warm-up event, then ten timed events of a patch handler plus one tick. Allocation is `GC.GetTotalMemory` over 600 ticks.

    | Measurement | Stowaway's Step, main / this change | Shivering Step, main / this change |
    | --- | --- | --- |
    | Tick avg | 0.027 / 0.022 to 0.024 ms | 0.012 / 0.009 to 0.010 ms |
    | Allocation per tick | 0 / 0 B | 0 / 0 B |
    | Inventory change avg, max | 1.15, 1.47 / 1.14 to 1.43, 1.43 to 1.66 ms | 1.09, 1.48 / 1.30 to 1.34, 1.75 to 2.66 ms |
    | Keyring change avg | 0.07 / 0.85 to 1.01 ms | 0.06 / 0.90 to 0.95 ms |
    | Quest completion avg, max | 1.09, 1.33 / 1.29 to 1.32, 1.69 to 2.51 ms | 1.06, 1.32 / 1.18 to 1.19, 1.42 to 1.63 ms |
    | Scene load avg | 11.5 / 9.6 to 10.4 ms | 8.0 / 7.3 to 7.8 ms |

    An inventory event allocates about 25 KB on this change against 1 to 2.5 KB on main. Navigating cross-zone to Ghost of Wyland Sercher from Stowaway's Step, an inventory event costs 1.3 ms against 5.7 ms on main, because a state change that leaves the route and its zone lines unchanged keeps the waypoint instead of recomputing NavMesh paths to every line.
- [x] 1.5 `fix(guide): list the common world item swap as one world-drop source`: after the clean build of `adopt-data-backed-wiki` task 5.44, a `loot_drops` row with `is_common_world_item = 1` and no other drop flag comes only from the swap of `GameManager.CommonWorldItems`. Turn those rows into one background source per item, like the special world drops, instead of a drop edge from every character, and keep rows that also carry their own drop flag as character drops. Add unit tests for both kinds of row. Verify: tests pass, and the regenerated `quest-guide.json` lists Bread, Water, Brackfruit Juice, Luminstone, Citrine Stone, and Star Stone with one swap source each and no swap-only character drops. This lands before the first regeneration of `quest-guide.json` from that build.
  - Done. Each of the six items has one `common_world_item` source, "Any enemy with common drops", with the chance range over placed characters (Bread 0.92-8.12%). Bread drops from 334 sources to 42 droppers that have their own flag plus that one source.

## 2. Export for slices 2 to 6

- [ ] 2.1 `feat(export): export both directions of quest listener effects`: replace `ZoneLineQuestUnlocks` and `CharacterQuestUnlocks` with `QuestActivationEffects`, recording enable and disable effects of `QuestSpawnListener`, `MultiQuestListener`, and `DynamicContentManager` for every scene object, with the quest, active quest, or held item that triggers them. Switch the clean build to the new table in the same commit, so the existing conditions stay unchanged. Update `field-coverage.json`. Verify after 2.5: the conditions of slice 1 are unchanged, and rows exist for the item condition in Stowaway's Step, the A Dying Wish removals, and both effects of Meet the Fisherman.
- [ ] 2.2 `feat(export): export zone line component and collider state`: add the enabled state of the `Zoneline` component and whether its collider is a trigger to the zone line record. Verify after 2.5: the six components of the gating audit read disabled or non-trigger, and every other zone line reads usable.
- [ ] 2.3 `feat(export): export the targets of scripted activators`: add the `[[activation]]` class with a rule ID to `dynamic-spawn-catalog.toml`, move the fields of `ShiverEvent`, `ShiveringAngel`, `ShiveringPhantomWardListener`, `MemorySphere`, `SivTorchLight`, the planar fight reveals, and the boss barriers into it, and add a listener that records each referenced scene object with its script, field, and stable key. Update `skill://unity-export-system`. Verify after 2.5: the export lists `Kio the Lightkeeper (1)` for `FirstKio`, `Kio the Lightkeeper` for `Kio`, the four keepers for `WelcomeCrew`, The Hider, the ten spawn triggers, and the four restored gods.
- [ ] 2.4 `feat(tools): pin the gate rules of the scripted activators`: add `assert` facts for the `Door.OpenOrShut` key rule, each quest check, assignment, finish, and activation of `ShiverEvent.Update` and `ShiverEvent.InitAll`, the `STANDANGEL` check of `ShiveringAngel`, the ward rules, the reveal and reset of each planar fight script, the essential-spawn block of `NPCShoutListener`, the boss barriers, `MemorySphere`, and the gaze rule of `SivTorchLight`. Follow `skill://code-facts`. Verify: `uv run erenshor extract code-facts` binds every new fact, and a changed literal in a test fixture fails it.
- [ ] 2.5 Announce the export in the status, then run the export, code facts, and clean build of the main variant. Verify: the checks of 2.1 to 2.4 hold.

## 3. The Shivering Step event

- [ ] 3.1 `fix(guide): model the Shivering Step event from its rules`: add the event rule of design D5 to the clean build, give Meet Shivering Step its zone-entry acquisition and keeper completion, correct the keeper notes of `CharacterListener`, and remove the Shivering Step edges of `graph_overrides.toml`. Add unit tests for each phase. Verify: tests pass, the Shivering Step scenarios of both specs hold, and the slice 2 check of design D12 passes in the game.

## 4. Inactive placements

- [ ] 4.1 Audit the 34 inactive placements without an exported activator against the game code. Verify: each is recorded under this task as unused or as activated by a named script, and every activating script is classified in the catalog.
- [ ] 4.2 `fix(guide): keep inactive placements unavailable without an activator`: give each inactive placement the condition of its activation effects, or a never-holding condition without one, and carry it to the mod. Add unit tests. Verify: tests pass and the slice 3 check of design D12 passes in the game.

## 5. Unusable zone lines

- [ ] 5.1 Check each candidate zone line of issue #298 in the game. Verify: the result for each line is recorded under this task.
- [ ] 5.2 `fix(pipeline): mark zone lines that players cannot use`: derive `is_usable` and `unusable_reason` from the component and collider state and from `zoneline:` rules in `mapping.json`, add those rules with reasons, exclude unusable lines in the guide, the map's zone line query, and the wiki zone page generator. Add unit tests. Verify: tests pass, the zone line scenarios of both specs hold, the map preview and the generated zone pages omit the lines, and the slice 4 check of design D12 passes in the game, including the NavMesh check of every `barriers.toml` entry.

## 6. Removed barriers

- [ ] 6.1 `feat(pipeline): gate targets behind objects that quest scripts remove`: derive conditions from the disable effects of the quest listeners and `barriers.toml` entries for every removed object, including the Blooming Sepulcher barriers and the Vitheo's Rest key doors. Add unit tests. Verify: tests pass and the slice 5 check of design D12 passes in the game.

## 7. Encounter prerequisites

- [ ] 7.1 `feat(adventure-guide): show encounter prerequisites as guidance`: derive encounter atoms from the planar fight reveals, the ward rules, the essential-spawn block, and the boss barriers, carry them to the mod, and show them as requirements with NAV links. Add unit tests for the derivation and for the guidance never hiding a target. Verify: tests pass and the slice 6 check of design D12 passes in the game.

## 8. Close-out

- [ ] 8.1 Run the Lunaris smoke check of design D12. Verify: the result is recorded under this task and the game has exited.
- [ ] 8.2 `docs(mod): describe gated navigation in the release notes`: add player-facing entries to both changelogs, including the unreleased guide data fixes. Verify: `uv run erenshor --dry-run mod thunderstore --mod adventure-guide` passes.
- [ ] 8.3 Open an issue in the format of issue #282 for each non-goal except multi-quest navigation, after checking it against the current code, and close issue #298 with the commit that fixes it. Verify: each issue link is recorded under this task.
- [ ] 8.4 Run `uv run erenshor test ci`, sync the specs, and archive the change. Propose the multi-quest navigation change afterwards. Verify: CI passes and both specs exist under `openspec/specs/`.
