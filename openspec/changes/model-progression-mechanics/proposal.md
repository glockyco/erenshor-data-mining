## Why

The clean database records most gates, but several kinds of game logic reach consumers only through the Adventure Guide's hand-written overrides in `quest_guides/graph_overrides.toml`, or not at all:

- A controller's effects ignore whether its host is active. `QuestSpawnListener` enables `PlanningDesk` after Claiming the Reliquary, and `PlanningDesk` hosts the `PlanningTable` that opens the Reliquary portals. The clean build drops effects on plain objects, 104 of the 150 exported quest-listener effects, and never applies a host's activation to the controllers it hosts or to the characters they spawn. The last phase of the Fallen Fernalla fight, which drops the Inert Rune of Fernalla, is available without the quest that starts the fight.
- The clean build ignores that a spawn point starts disabled. 118 spawn points start disabled, 26 by their component and 92 by an inactive object or ancestor, among them the Azynthian Keeper's, which `StowawayPortal` enables after the four Shadows die.
- Spawns that follow deaths have no trigger. `AstraListener` spawns Astra, Rogue of the Stars after every Stardust dies, and the Freed Spirit of Raval after Raval dies, but the export records both spawns without a condition.
- Barriers other than keyed doors have no record of what they guard: the angel statue that `ShiveringAngel` turns after Stand, Angel!, the wall in Jaws of Sivakaya that `SivTorchLight` removes after She Sees You, and the six Wards of Piety, level 99 and impossible to damage, that `PietyTrigger` calls when a player enters without A Pious Guest.
- Travel, world state, and faction standing that only code expresses: the Dimensional Rift between the two Azynthi's Garden scenes, rain, which `WeatherTrend` keeps from starting in Braxonian Desert and Invoke Storm forces, and faction standing, which decides whether an NPC talks. The Arcane Headmaster gives the Loss Stone only while the Pupil's Pin is equipped, because `Inventory` sets his faction below zero otherwise.
- Nothing fails when a script that gates progression is not classified. `JawsStatueStartup` enables the gaze statue after The Guardian Awakens, and `BellsieWineTrigger` takes an item and enables objects on Bellwain Island. Neither is exported, and every build passes.

The overrides approximate these mechanisms. They gate the Jaws entrance instead of the wall inside, and they state A Pious Guest as a spawn condition of Vessel Siraethe. Any game update can add another such script without a failing check.

## What Changes

- Behaviour coverage: the code-facts run lists every script type that reads quest, item, account, weather, spawn death, or faction state, or that changes scenes, quests, invulnerability, weather, or faction standing. Each type is classified by the component that models it, excluded with a reason, or pending with the task that will model it. An unclassified type fails the run.
- Hierarchy activity: an object's activation applies to everything under it, to every controller it hosts, and to the characters those controllers spawn. This replaces the separate export of UI item access, and gives each placement that starts inactive, a spawn point or a placed copy, the activation that enables it or a gate that never holds.
- Death triggers: the spawns and activations that follow deaths need a defeat of each character whose death triggers them.
- Released spawns: the Vitheo arena's fighters need the coin of their round, its award chests also need a defeat of the round's fighters, and a character that another character summons needs its summoner.
- Barriers: each object that blocks access gets its opening condition from its mechanism, and `barriers.toml` records what each barrier guards, with a reason and an in-game check. Keyed doors become one kind of barrier. Gates keep the barrier's identity.
- Travel: zone lines, teleport items, and scene switches by spell become one set of travel facts with their conditions.
- World state: each scene's weather limits and the spells that change the weather become facts, and a gate can need a world state.
- Item actions preserve their class restrictions and record spell learning levels as need attributes, so a teaching scroll is not an unrestricted substitute for a click effect.
- Faction standing: the rules by which a world faction's standing blocks an NPC's dialog become code facts, and a dialog can need a standing with a faction.
- Hand-coded literals, such as `"STANDANGEL"`, `"JAWSSEEN"`, and spell names, come from code facts that extract them, so a changed literal fails the run instead of drifting.
- The rule-specific branches of `gates.py` that these rules cover go, with their literal quest keys.
- Way ranks: each way keeps the tier and depth that the build already computes and the clean facts that produced it, so that a consumer choosing among ways it cannot use yet follows the build's order and never loops.
- The open producer tasks of `model-guide-gates` move here after a handoff: inactive placements (its task group 4), unusable zone lines (5), and removed barriers (6.1), with the guide's pending producer proposals and evidence as inputs.
- The guide's overrides lose their gates in a guide change once the clean database holds them.

Non-goals: the Chessboard offering workflow beyond classifying its scripts, evaluating a player's save, and guide navigation.

Migration boundary: each mechanism lands with its consumers unchanged. The requirement graph of `derive-progression-requirements` shows its effect, and the guide removes an override only after the clean database covers it.

## Capabilities

### New Capabilities

- `progression-mechanics`: how the export, code facts, reviewed facts, and the clean build record what makes a zone, placement, source, or route available: hierarchy activity, barriers, travel, world state, and the coverage check that keeps them complete.

### Modified Capabilities

- `progression-requirements`: ways carry their rank and the clean facts that produced them.

The requirements of `guide-gate-data` that describe shared clean-build data move into `progression-mechanics` when `model-guide-gates` archives (task 9.1).

## Impact

- Export: the listeners and catalogs under `src/Assets/Editor/ExportSystem/`, the subject records under `src/Assets/Editor/Database/`, and `src/tools/ExportSurface/field-coverage.json`.
- Code facts: an inventory mode and new facts in `src/tools/CodeFacts/`.
- Clean build: `src/erenshor/application/processor/` (`gates.py` and new modules), the schema in `writer.py`, `barriers.toml`, and `mapping.json`.
- Readers of zone line usability: the map query in `src/maps/src/lib/database.base.ts` and the wiki zone connections.
- Guide: the gates of `quest_guides/graph_overrides.toml`, removed in a guide change, and the way rank that the guide export carries to its sources.
- Documentation: the README's Gates concept and the `unity-export-system`, `code-facts`, and `refreshing-game-data` skills.
- Shared resources: Unity exports, code-facts runs, clean builds, and game sessions for the in-game checks, all run from the main checkout.
