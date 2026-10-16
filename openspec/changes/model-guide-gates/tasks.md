# Tasks

## 0. Remove the unused dense guide

- [ ] 0.1 `refactor(guide): stop generating guide.json`: confirm that no code, CI job, map file, or document reads `quest_guides/guide.json`, then remove `guide compile`, `json_writer.py`, their tests, and the file, and update the README, the AdventureGuide README, and `skill://refreshing-game-data`. Verify: a repository search for `guide.json` finds only `quest-guide.json`, and `uv run erenshor test unit` passes.

## 1. Condition model and keyed doors

- [ ] 1.1 Measure the baseline of design D10 on the mod built from the current commit (BepInEx, main variant, test character with twelve tracked quests, one navigated) in Stowaway's Step and Shivering Step. Verify: the averages, minimums, and maximums are recorded under this task, and `pgrep -f Erenshor.exe` prints nothing afterwards.
- [ ] 1.2 `feat(pipeline): record gates as conditions in the clean database`: add `gate_conditions` to `writer.py` and derive it from the existing quest unlocks of zone lines and characters, quest-started and quest-stopped spawn points, Reliquary furnishings, vendor stock unlocks, item bag unlocks, and keyed doors through `barriers.toml`. Add `barriers.toml` with an entry for every keyed door, moving the door and item edges out of `graph_overrides.toml`, and fail the build on a missing or stale entry. Drop `zone_line_quest_unlocks` and `character_quest_unlocks`. Document `barriers.toml` in the README's concepts. Add unit tests for each atom source and both completeness failures. Verify: the tests pass, and after a clean build (announced in the status) the slice 1 scenarios of `guide-gate-data` hold in SQL.
- [ ] 1.3 `feat(guide): compile and ship typed gate conditions`: build unlock edges from `gate_conditions`, extend `_compile_unlock_predicates` to the atom kinds, add the size limit and the acyclicity check, and write `quest-guide.json` version 7 as design D4 describes. In the mod, load the conditions, add `GateConditions` with the keyring check of design D6, remove `FurnishingStatus` and the separate furnishing checks, and migrate every consumer of the old gate fields. Add compiler tests for each atom kind and a cycle, the database-to-JSON contract test, and `GateConditions` tests on the real data, moving the existing furnishing tests onto the atom. Update the AdventureGuide README's data section. Verify: Python and C# tests pass, `uv run erenshor mod build --mod adventure-guide --loader all` succeeds, and the regenerated `quest-guide.json` holds the door gates of the spec scenarios.
- [ ] 1.4 `feat(adventure-guide): lead navigation to what unlocks a gate`: add requirement selection and chains (design D7) to navigation, the navigation display, the detail panel, and the tracker, and `DumpGate` with the chain in `DumpNav`. Update `skill://runtime-eval`. Add tests on the real data for the lighthouse key, the Jaws alternatives, and a chain of two requirements. Verify: tests pass, the slice 1 checks of design D12 pass in the game with screenshots, and the budgets hold.

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
