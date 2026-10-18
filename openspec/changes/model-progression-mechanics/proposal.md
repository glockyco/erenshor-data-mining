## Why

The clean database records most gates, but four kinds of game logic reach consumers only through the Adventure Guide's hand-written overrides in `quest_guides/graph_overrides.toml`, or not at all:

- A controller's effects ignore whether its host is active. `QuestSpawnListener` enables `PlanningDesk` after Claiming the Reliquary, and `PlanningDesk` hosts the `PlanningTable` that opens the Reliquary portals. The clean build drops effects on plain objects, 104 of the 150 exported quest-listener effects, and never applies a host's activation to the controllers it hosts.
- Barriers other than keyed doors have no record of what they guard: the angel statue that `ShiveringAngel` turns after Stand, Angel!, the wall in Jaws of Sivakaya that `SivTorchLight` removes after She Sees You, and the six Wards of Piety, level 99 and impossible to damage, that `PietyTrigger` calls when a player enters without A Pious Guest.
- Travel and world state that only code expresses: the Dimensional Rift between the two Azynthi's Garden scenes, and rain, which `WeatherTrend` keeps from starting in Braxonian Desert and Invoke Storm forces.
- Nothing fails when a script that gates progression is not classified. `JawsStatueStartup` enables the gaze statue after The Guardian Awakens, and `BellsieWineTrigger` takes an item and enables objects on Bellwain Island. Neither is exported, and every build passes.

The overrides approximate these mechanisms. They gate the Jaws entrance instead of the wall inside, and they state A Pious Guest as a spawn condition of Vessel Siraethe. Any game update can add another such script without a failing check.

## What Changes

- Behaviour coverage: the code-facts run lists every script type that reads quest, item, account, or weather state, or that changes scenes, quests, invulnerability, or weather. Each type is classified by the component that models it, or excluded with a reason. An unclassified type fails the run.
- Hierarchy activity: an object's activation applies to everything under it and to every controller it hosts. This replaces the separate export of UI item access, and gives each inactive placement the activation that enables it or none.
- Barriers: each object that blocks access gets its opening condition from its mechanism, and `barriers.toml` records what each barrier guards, with a reason and an in-game check. Keyed doors become one kind of barrier. Gates keep the barrier's identity.
- Travel: zone lines, teleport items, and scene switches by spell become one set of travel facts with their conditions.
- World state: each scene's weather limits and the spells that change the weather become facts, and a gate can need a world state.
- Hand-coded literals, such as `"STANDANGEL"`, `"JAWSSEEN"`, and spell names, come from code facts that extract them, so a changed literal fails the run instead of drifting.
- The rule-specific branches of `gates.py` that these rules cover go, with their literal quest keys.
- The open producer tasks of `model-guide-gates` move here after a handoff: inactive placements (its task group 4), unusable zone lines (5), and removed barriers (6.1), with the guide's pending producer proposals and evidence as inputs.
- The guide's overrides lose their gates in a guide change once the clean database holds them.

Non-goals: solving the Bellwain Isle puzzle or the Chessboard offering workflow beyond classifying their scripts, evaluating a player's save, and guide navigation.

Migration boundary: each mechanism lands with its consumers unchanged. The requirement graph of `derive-progression-requirements` shows its effect, and the guide removes an override only after the clean database covers it.

## Capabilities

### New Capabilities

- `progression-mechanics`: how the export, code facts, reviewed facts, and the clean build record what makes a zone, placement, source, or route available: hierarchy activity, barriers, travel, world state, and the coverage check that keeps them complete.

### Modified Capabilities

None. The requirements of `guide-gate-data` that describe shared clean-build data move into `progression-mechanics` when `model-guide-gates` archives (task 7.1).

## Impact

- Export: the listeners and catalogs under `src/Assets/Editor/ExportSystem/`, the subject records under `src/Assets/Editor/Database/`, and `src/tools/ExportSurface/field-coverage.json`.
- Code facts: an inventory mode and new facts in `src/tools/CodeFacts/`.
- Clean build: `src/erenshor/application/processor/` (`gates.py` and new modules), the schema in `writer.py`, `barriers.toml`, and `mapping.json`.
- Readers of zone line usability: the map query in `src/maps/src/lib/database.base.ts` and the wiki zone connections.
- Guide: the gates of `quest_guides/graph_overrides.toml`, removed in a guide change.
- Documentation: the README's Gates concept and the `unity-export-system`, `code-facts`, and `refreshing-game-data` skills.
- Shared resources: Unity exports, code-facts runs, clean builds, and game sessions for the in-game checks, each coordinated with the Adventure Guide tab.
