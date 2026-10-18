## Shared resources

Each Unity export, code-facts run, and clean build of the main variant runs in an owned worktree with its own database clones. A game session starts only after the Adventure Guide tab hands over the runtime slot, keeps sound off, uses a dedicated character slot, leaves the player's saves unchanged, and ends through the normal shutdown with no game process left.

## 0. Handoff (design D8)

- [ ] 0.1 Confirm the handoff with the maintainer and the Adventure Guide tab: tasks 4.1, 4.2, 5.1, 5.2, and 6.1 of `model-guide-gates` move here, and the guide tab's audit, inventory, scene proofs, proposals, and door reviews are its inputs. Record below the handed-over files and the commit at which the guide's consumer branch landed. Verify: both changes name one owner for each moved task.

## 1. Behaviour coverage (design D1)

- [ ] 1.1 `feat(tools): list the scripts that read or change progression state`: add the inventory mode and the catalog format to `src/tools/CodeFacts/`, failing on an unlisted type, a stale entry, and a changed set of state APIs. Add tests with fixture types for each failure. Verify: the tests pass, and the run on build 24405256 lists the 60 types.
- [ ] 1.2 `feat(tools): classify every progression script`: add a catalog entry for each listed type with the component that models it or a reason. Record below each type that still needs an adapter or a rule, with the task that adds it. Verify: `uv run erenshor extract code-facts` passes, and deleting any entry makes it fail.

## 2. Hierarchy activity (design D2 and D3)

- [ ] 2.1 `feat(export): record the object hierarchy of subjects and controllers`: add `ObjectHierarchy` and the object of each subject record. Verify: after an owned export, every subject names its object, every ancestor is recorded, and `PlanningDesk` is the host of `PlanningTable`.
- [ ] 2.2 `feat(pipeline): apply an object's activation to what it contains and hosts`: add the rule of D3, and remove `UiItemAccessActivations` with its listener path and processor reader. Add unit tests for inheritance through ancestors, a hosted controller, a disable, and a starting-inactive subject. Verify: the tests pass, the 40 planning-slot zone lines need Claiming the Reliquary, the Box of Portals keeps its condition, and `extract changes` against the previous build shows no other changed gate.
- [ ] 2.3 `fix(pipeline): keep inactive placements unavailable without an activator`: export the wards of `FernallaPortalBoss`, the Bellwains of `AngelScript`, and the portal identities of `PlanningTable`, and give each audited inactive copy its activation or a gate that never holds. Verify: each of the audited copies has the condition that its audit entry names, and the unit tests pass.
- [ ] 2.4 Check hierarchy activity in the game on a quest-enabled object outside account state, such as the Duskenlight ritual portal before and after The Duskenlight Ritual. Verify: the object and its zone line become active exactly when the gate says, and the evidence is recorded below.

## 3. Barriers (design D4)

- [ ] 3.1 `feat(pipeline): record barriers beyond keyed doors`: give `barriers.toml` the barrier form with kind, targets, reason, and check, move the keyed door entries into it, and add the build checks. Verify: `extract changes` shows no changed door gate, and the unit tests show each check failing on its case.
- [ ] 3.2 `feat(export): export the barrier mechanisms`: export `BreakWall` of `SivTorchLight` with the enable of `JawsStatueStartup`, the host of `ShiveringAngel`, the guardians of `PietyTrigger`, the `SpawnIfAlive` objects of `NPCAliveListener`, and the removals of the quest listeners. Extract `STANDANGEL` and `JAWSSEEN` with code facts, and drop the literal from the `shivering_angel` branch. Verify: each barrier has its opening condition, the code-facts run passes, and the unit tests pass.
- [ ] 3.3 Check the containment of each barrier in the game with NavMesh paths from each entrance landing, and record each barrier in `barriers.toml` with its targets, reason, and check, including the Blooming Sepulcher barriers and the Vitheo's Rest doors of task 6.1 of `model-guide-gates`. Verify: `extract build` passes, and `erenshor progression show character:siraethe` shows the gaze wall and the Wards of Piety, and the zone line into Shivering Tomb (2) shows the angel statue.

## 4. Travel (design D5)

- [ ] 4.1 `feat(pipeline): record travel between zones`: add `travel_routes` from zone lines and teleports, and from a code fact that extracts the scene switches of `SpellVessel`'s spell switch. Add unit tests. Verify: the Dimensional Rift has a route in each direction that needs the spell, and the Reliquary Hall saved-return exit has no fixed destination.
- [ ] 4.2 `fix(pipeline): mark zone lines that players cannot use`: check each candidate of issue #298 in the game, derive `is_usable` and `unusable_reason`, add the reviewed `zoneline:` rules to `mapping.json`, and exclude unusable lines in the map query and the wiki zone connections. Verify: each candidate's result is recorded below, the map tests pass against the fixture database, and the wiki zone page tests pass.
- [ ] 4.3 Check the Dimensional Rift in the game by using the Azynthian Riftstone in each scene. Verify: the scene switches both ways, and the evidence is recorded below.

## 5. World state (design D6)

- [ ] 5.1 `feat(export): record the weather limits of scenes`: export each `WeatherTrend` with its scene and limits, and pin the rain rules of `AtmosphereColors` and `WeatherTrend` and the weather spells of `SpellVessel` as code facts. Verify: the four capped scenes and their limits appear in the clean database, and the code-facts run passes.
- [ ] 5.2 `feat(pipeline): let gates need a world state`: add the `world_state` atom, derive where natural rain can start, record the weather spells as producers, and map the `raining` release to rain in its scene. Add unit tests. Verify: `erenshor progression show "item:key -  ancient braxonian key"` shows Evadne the Corrupted needing rain in Braxonian Desert, and the rain needing Invoke Storm, which Tempestalia, Ring of Storms casts and Spell Scroll: Invoke Storm teaches.
- [ ] 5.3 Check in the game that Invoke Storm from Tempestalia, Ring of Storms starts rain in Braxonian Desert and that Evadne the Corrupted can then be damaged. Verify: the evidence is recorded below, and the game exits normally.

## 6. Cleanup

- [ ] 6.1 `refactor(pipeline): retire the gate branches that general rules cover`: remove each branch of D7 that a landed rule covers. Verify: `extract changes` against the previous build shows no unintended gate change, and the processor tests pass.
- [ ] 6.2 Give the Adventure Guide tab the overrides that the clean database now covers, each with its clean gate: the Jaws entrance, Vessel Siraethe, Shivering Tomb (2), and the planning desk. Verify: after the guide change lands, `quest_guides/graph_overrides.toml` holds no gate.
- [ ] 6.3 `docs: describe progression mechanics`: update the README's Gates concept and the `unity-export-system`, `code-facts`, and `refreshing-game-data` skills with hierarchy activity, barriers, travel, world state, and how to classify a new script after a game update. Verify: `uv run pytest tests/contract/test_document_paths.py` passes.

## 7. Integration

- [ ] 7.1 After `model-guide-gates` archives, move the shared requirements of `guide-gate-data` into `progression-mechanics` with a delta that removes them there and adds them here. Verify: `openspec validate --specs` passes.
- [ ] 7.2 Run `uv run erenshor test ci`. Verify: it passes.
- [ ] 7.3 Archive with `openspec archive model-progression-mechanics --yes`. Verify: `openspec/specs/progression-mechanics/spec.md` exists.
