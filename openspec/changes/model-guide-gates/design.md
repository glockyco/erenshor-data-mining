# Design

## Context

See proposal.md for the gaps and their ranking. The current state that shapes the design:

- The export records doors with their key (`doors.key_item_stable_key`, 247 doors, 40 keyed placements, 26 keys), zone lines and placements with `is_enabled`, and the positive effects of the three quest listeners (`QuestActivationListener`, which skips item conditions and every removal).
- The guide graph has `DOOR` nodes, `UNLOCKS_DOOR` edges, and curated door and item edges in `quest_guides/graph_overrides.toml`. `compiler._compile_unlock_predicates` resolves a door to its key item. `mod_writer` ignores those predicates and rebuilds quest-only groups, so the mod never sees a door or item gate. `guide compile` writes a dense `quest_guides/guide.json` that no code, CI job, or the map reads.
- The mod has no shared gate evaluation. `ZoneGraph`, `NavigationController`, `WorldMarkerSystem`, `QuestDetailPanel`, `StepSceneResolver`, and `TrackerSorter` each read `required_quest_groups`, `_character_quest_unlocks`, or `required_quest_db_names` themselves, and `FurnishingPolicy` is a second availability mechanism beside them. Nothing reads `GameData.Keyring`.
- The runtime updates every frame, re-picks among a step's sources every 0.25 s, recomputes cross-zone waypoints after 10 m of movement, and rebuilds markers on a state version that quest and inventory patches increment.
- The removed rewrite (`fb9ce883b`) failed through per-frame resolution, cloned dependency trees, global cache clears followed by synchronous cold resolution of every pin (2.6 s), exponential feasibility walks, and caches whose keys missed a dependency. The current runtime family is the stable one restored by `299a51855`.
- The dynamic spawn catalog already classifies the character and object fields of the scripted activators, as denied spawn sources (`ShiverEvent`, `MemorySphere`, `QuestSpawnListener`, `MultiQuestListener`, and others). The export fails on an unclassified field.
- `mapping.json` holds reviewed corrections of exported rows, each with a reason, and already overrides spawn point flags.
- Zone lines are read by the guide, the map's zone line layer (`database.base.ts`), and the wiki zone page generator (`zones.py`).

## Goals / Non-Goals

**Goals:**

- One condition model from the export to the runtime, with one derivation in the compiler and one evaluation in the mod, and no second representation.
- Every gate either derived from game data or held in one reviewed home that fails the build when the game changes.
- No new runtime cache. Conditions are evaluated on demand from state the mod already mirrors.
- Each gate kind lands as a verified slice, checked in the running game on a test character.

**Non-Goals:**

- Navigating several quests at once. A separate change follows.
- A general travel graph for teleports, portals, and the Riftstone. Routing stays a zone line graph.
- Spatial reachability analysis. Which targets a door guards is reviewed data.
- Showing gates on the map or the wiki. Both only stop showing unusable zone lines.

## Decisions

### D1. Conditions are flat OR groups of typed atoms

A condition is a list of groups, and a group is a list of atoms. A subject without a condition is always available, and a condition without groups never holds. Observable atoms: `quest_done`, `quest_not_done`, `item_held`, `key_held`, `room_furnished`. Advisory atom: `encounter_won`. This matches the game's listeners: alternative listeners are separate groups, `MultiQuestListener` is one group with two atoms, and a door adds one `key_held` atom to each group of its target. `quest_not_done` expresses removal effects and quest-stopped spawn points. `room_furnished` names a Reliquary room slot and a furniture set and replaces the separate furnishing mechanism. `encounter_won` names the characters whose deaths reveal, unlock, or open the subject.

Encounters are advisory because the mod cannot observe them reliably: a kill before the mod loaded, a fight script that resets on respawn, and a death outside the player's view all leave no trace it can read. An advisory atom never makes a subject unavailable. It becomes guidance on the step.

A general boolean tree was rejected. Combinations such as two alternative listeners in front of a keyed door distribute into this form with a few groups, and the compiler fails when a condition exceeds a fixed size. A flat form is cheap to evaluate, to serialize, to diff in a contract test, and to explain to the player.

### D2. Each kind of gate fact has one home

1. The export, for facts that game data states: the quest listeners in both directions with item conditions, zone line component and collider state, and the scene objects referenced by the scripted activators. `QuestActivationListener` owns listener effects and writes them to a raw `QuestActivationEffects` table that replaces `ZoneLineQuestUnlocks` and `CharacterQuestUnlocks`. A new listener exports the serialized targets of the scripted activators, driven by a new `[[activation]]` class in `dynamic-spawn-catalog.toml`: each entry names a script, its fields, and a rule ID. The scripted acquisition and completion notes in `CharacterListener` that describe the Shivering Step keepers as kills are corrected with the event rule.
2. Rules in the pipeline, for logic that lives in game code: the Shivering Step event, the angel statue, the ward listeners, the planar fight reveals, the essential spawn that blocks A Strange Hermit, the boss barriers, `MemorySphere`, `SivTorchLight`, and the door key rule. A rule maps each field of its script to a condition template. Each rule carries `code-fact` tags, and `assert` facts in `erenshor-facts.json` pin the quests, comparisons, and calls the rule encodes.
3. `mapping.json`, for reviewed corrections of exported rows: a `zoneline:` rule with `is_usable: 0` and a reason marks a zone line that players cannot reach (issue #298). This follows the existing spawn point rules.
4. `barriers.toml`, a new reviewed file beside `mapping.json`, for the one fact no existing file can hold: which targets each keyed door and each removed object guards. Each entry has a reason. The clean build fails on a keyed door or removed object without an entry, and on an entry whose object no longer exists. The door and item edges of `graph_overrides.toml` move here or to the rule that owns them (the candle to `MemorySphere` and the listener export, the Tempestalia ring to Evadne's weather note). The Shivering Step edges give way to the event rule. `graph_overrides.toml` keeps only guide-only content, such as the Reliquary planning table node.

A per-placement review list for inactive placements was rejected. The dynamic spawn catalog already fails the export on an unclassified activator field, so an inactive placement without an exported activator is never available, and the one-time audit of the 34 current ones is a task, not a stored fact. Automatic door containment by NavMesh analysis was rejected as the source of truth, because a wrong guess silently misleads. The in-game NavMesh check reviews `barriers.toml` instead.

### D3. The clean database owns gates and every reader follows

The clean build writes `gate_conditions` (subject kind, subject stable key, group, atom kind, atom reference) from every availability rule, and adds `is_usable` and `unusable_reason` to `zone_lines`. `zone_line_quest_unlocks` and `character_quest_unlocks` are dropped without compatibility views. Their only reader is the guide edge builder. The map's zone line query and the wiki zone page generator filter on `is_usable` in the slice that adds it. The source tables of other rules, such as `spawn_point_stop_quests`, stay, because the sheets read them.

### D4. The compiler derives conditions once and only `quest-guide.json` is written

`edge_builder` turns `gate_conditions` into typed unlock edges. `compiler._compile_unlock_predicates` grows the atom kinds and becomes the only place that combines a subject's sources into a condition. `mod_writer` serializes the compiled conditions as a `_conditions` table and adds a `condition` index to zone lines, placements, spawn points, item sources, vendor offers, and item bags. `_version` becomes 7. `_unlock_groups`, `required_quest_groups`, `_character_quest_unlocks`, `required_quest_db_names`, and `spawn_upon_quest_complete_stable_key` are deleted. Furnishing slot and set stay on placements for display. `_gate_items` lists, for every item a condition names, its game item ID (the keyring stores IDs) and its sources, built by the existing `_item_sources_with_rewards`. The module docstring stops calling the shipped format a legacy wrapper. A contract test compares the clean database's conditions with `quest-guide.json`. The acyclicity check runs in the compiler, visits each subject once, and fails with the cycle.

`guide compile`, `json_writer.py`, and `quest_guides/guide.json` are removed, with their tests and the documentation that names them. The compiled data stays as the in-memory input of `mod_writer`.

### D5. The Shivering Step event is a rule, not overrides

The event rule reads the exported targets of each `ShiverEvent` field and assigns conditions: `FirstKio` while the four keeper quests are not all complete, `Kio` once they are and while Changing the Lighthouse is not, `WelcomeCrew` while not all four are complete, `Hider` from The Shivering Torch until Warming the Isle, `SpawnTriggers` from The Shivering Torch, `Phantom` from Seeing the Truth. Meet Shivering Step gets a zone-entry acquisition and the four keeper quests as its completion. The ten seconds of darkness before The Hider and the triggers appear become a step note. The rule's code facts pin each `CompletedQuests.Contains`, `AssignQuest`, `FinishQuest`, and `SetActive` call of `ShiverEvent.Update` and `ShiverEvent.InitAll`.

Re-entry hides the keepers as soon as all four quests are complete, while the live sequence keeps them until darkness. The condition follows re-entry, because the keepers have no purpose after their quests.

### D6. The mod evaluates conditions on demand, without a cache

`GateConditions` (new, in `State/`) holds the conditions as arrays of atoms whose references are resolved to indices at load. `IsAvailable(condition)` treats advisory atoms as holding. `Explain(condition)` lists unmet observable atoms and every advisory atom. Both read the existing mirrors: the completed quest set of `QuestStateTracker`, the inventory counts, and the furniture slots that `FurnishingPolicy` reads. They read `GameData.Keyring` directly, so no copy of it can go stale. `FurnishingStatus` and the per-consumer furnishing checks are removed, and the furnishing requirement text becomes the explanation of the `room_furnished` atom.

Consumers rebuild on the existing state version. `QuestStateTracker.Update` already polls furnishings and treasure hunts each frame, and it also compares `GameData.Keyring.Count` with the last value and increments the version on a change. During play only `Door.OpenOrShut` changes the keyring, and it only adds a key. A character load replaces the keyring before the gameplay scene loads, and the scene load already refreshes all guide state.

Evaluating a condition costs a few set lookups, and the data has a few hundred gated subjects. Caching results per state version was rejected: it adds a key that must cover every fact, which is the defect class that sank the rewrite, for no measurable gain. If a budget fails, the fix goes to the consumer that evaluates too often.

All consumers call `GateConditions`. No consumer reads atoms itself.

### D7. Requirement guidance is resolved where the target is resolved

When `NavigationController` resolves a target, as it does today on a NAV click, a state version change, a scene load, or the 0.25 s source re-pick, it checks the target's condition and the conditions of the hops of its route. For an unmet observable condition it picks the group with the fewest unmet atoms, then the first unmet atom, and builds a requirement step: the sources of the item from `_gate_items`, the current step of the quest, or the planning table for a furnishing. It resolves that step with the same code as a quest step and repeats for a gated requirement, with a visited set. The compiler's acyclicity check guarantees termination, and the visited set turns a data defect into an explanation instead of a hang. Advisory atoms add a requirement line with a NAV link to the named characters and do not change the target. The chain is a short list of value objects that the display, the detail panel, and the tracker render. Nothing is cloned or stored beyond the current navigation.

### D8. Routing drops unusable zone lines and asks the condition

`ZoneGraph` leaves unusable zone lines out of the graph. The accessible-first search asks `GateConditions` about each zone line. The locked fallback route stays, and requirement guidance applies to its first gated hop.

### D9. Slices follow player impact

Each slice ends with its gate kind working in the game. The first slice carries the cutover, because the quest-only representation cannot run beside the new one.

| Slice | Content | Needs an export |
| --- | --- | --- |
| 0 | Remove `guide.json` generation. | No |
| 1 | The condition model end to end: `gate_conditions`, `quest-guide.json` version 7, `GateConditions`, requirement guidance, diagnostics, `barriers.toml`. All existing gates migrate, and keyed doors are added. | No |
| 2 | The Shivering Step event. | Yes |
| 3 | Inactive placements. | Yes, for the activator targets |
| 4 | Unusable zone lines, with the map and wiki readers. | Yes |
| 5 | Quest listener removals and the barriers behind them. | Yes |
| 6 | Encounter prerequisites. | Yes |

The export changes of slices 2 to 6 land as separate commits and run as one export, announced in the status before it starts, so that slices 2 to 6 do not wait for one export each.

### D10. Budgets are measured against the mod before this change

Before the first runtime change, the baseline is measured on the mod built from the commit before it, with the method of `in-game-performance-profiling`, in Stowaway's Step and Shivering Step with twelve tracked quests and one navigated: the per-frame update, managed allocation over 600 frames, the frame of a quest completion, an inventory change, and a scene load. The values go into tasks.md. The same measurement after each runtime slice must meet the budgets in the `guide-gated-navigation` spec. A failed budget blocks the slice.

### D11. Testing follows the layer that owns the logic

- Export: the export run and SQL checks against the scenarios of the `guide-gate-data` spec. Unity listeners have no unit tests in this repository.
- Clean build and compiler: unit tests for each atom source, the completeness failures of `barriers.toml`, the contradictory listener, the Shivering Step rule, and the cycle check. A contract test compares database conditions with `quest-guide.json`.
- Mod: `GateConditions` and requirement selection are pure classes that take state through small interfaces, compiled into `AdventureGuide.Tests` like the existing policies. Their scenario tests load the real `quest-guide.json` and assert the spec scenarios.
- Game: the verification plan below.

### D12. In-game verification uses a test character and the diagnostics

`DebugAPI` gains `DumpGate(subject)` and the requirement chain in `DumpNav()`. Each scenario runs on a dedicated test character through HotRepl: change state with game calls (`GameData.AssignQuest`, `GameData.FinishQuest`, `PlayerInv.AddItemToInv`, `GameData.Keyring`), read the dumps, and take a screenshot with `ScreenCapture.CaptureScreenshot` to see the arrow, markers, and panels. Every session ends through the game's quit path, and `pgrep -f Erenshor.exe` confirms that the game exited.

| Slice | In-game check |
| --- | --- |
| 1 | Whispers of Wyland without and with the Ghostly Key, the key moved to the keyring, Occuphage through the lighthouse entrance, the Shivering Step entrance, a Reliquary vendor with and without its room set, Bassle Wavebreak after Angler's Ring. |
| 2 | Each phase in order: keepers, both Kio copies, The Hider after darkness, trigger spawns, Kio leaving, Founder and Warded Shadow behind their doors. |
| 3 | The restored gods' placements before their condition, the disabled Lucian Revald and Revan Gavault copies, and The Hider before the torch get no markers. |
| 4 | Routes out of Shivering Step and both Shivering Tomb scenes avoid the unusable lines. A NavMesh path from the scene entry checks each `barriers.toml` entry. |
| 5 | A Dying Wish parts one to three route to the barrier's quest before the deeper section. |
| 6 | Restored Fernalla, Warded Shadow, and A Strange Hermit show their encounter requirement and stay navigable. |
| All | The BepInEx build runs every check. The Lunaris build loads, navigates a gated quest, and quits cleanly. |

## Risks / Trade-offs

- A `barriers.toml` entry misclassifies what a door guards. Each entry is checked with a NavMesh path in the game, and the requirement explanation names the door, so a wrong entry is visible to players and reportable.
- A rule drifts from a game update. The code facts fail extraction, and the export fails on a new unclassified field.
- Encounter requirements are always shown, even after the player won the encounter. This is the cost of never hiding a target on a fact the mod cannot observe.
- Slice 1 is large, because the cutover cannot be split without a second path. Its pipeline and mod halves are separate commits, and the mod half is verified in the game before the next slice starts.
- The scope is large. The non-goals become issues, so nothing found by the audit is lost.

## Migration Plan

1. Slices 0 and 1 use the current raw export and one clean build, announced before it starts.
2. The export changes of slices 2 to 6, one export run, then slices 2 to 6 in order.
3. One mod release for both loaders after approval, which also ships the unreleased guide fixes.

Rollback is a revert of a slice's commits and a regenerated `quest-guide.json`. The clean database is rebuilt from the raw export.
