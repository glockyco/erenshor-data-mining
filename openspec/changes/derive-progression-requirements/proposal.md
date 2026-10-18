## Why

The clean database records the facts of progression in separate places: gates in `gate_conditions`, item sources and uses in the item provenance contract, placements and damage releases in the character tables, and quest sources in `quest_acquisition_sources` and `quest_completion_sources`. The quest source tables hold only a method and a source, without the source copy, the resource variant, or the conditions of a route. So each reader adds its own rules: the quest panel's repository decides which routes run and what they grant, the Adventure Guide's edge builder derives quest edges again, and `gates.py` reads the same tables for the Shivering Step event. Three derivations of one relation drift apart, as item sources did before `unify-item-provenance`.

No output says what a zone, quest, item, or character copy needs as a whole. A game update that changes a requirement shows up in `extract changes` only as scattered rows of several tables, and a reviewer cannot see that a raid chain changed.

## What Changes

- The clean build derives each quest's routes once. A start route is a dialog with its keyword, a read item, the completion of another quest, a zone entry, a partial turn-in, or a script. A completion route is a turn-in, a talk, a read, a death, a zone entry, a shout, a chain, or a script. Each route keeps its exact source copy, its resource variant, and its conditions. The quest panel reads these routes instead of deriving its own.
- The clean build derives one requirement graph from the canonical facts. Its nodes are zones, quests, items, character copies, barriers, game mechanisms, and world or account states. Each node lists alternative ways, and every need of a way is required.
- The clean build gives each node a playthrough tier: the number of progression steps on the earliest route from a new character in Stowaway's Step, with the way that achieves it.
- The build fails on a fact that the graph cannot represent and names it.
- `erenshor progression show` prints a node's ways and the milestone chain of a target, for review.
- The graph lives in clean tables, so `extract changes` reports changed requirements and tiers between game builds without new code.

Non-goals: rendering (`publish-wiki-progression-graph`), evaluating a player's save, mechanisms that the clean database does not record yet (`model-progression-mechanics`), and moving the Adventure Guide onto the canonical routes or the graph, which is a guide change.

Migration boundary: the quest panel switches to the canonical routes with byte-identical output. The Adventure Guide keeps reading the source tables until its own change adopts the routes.

## Capabilities

### New Capabilities

- `quest-routes`: how the clean database records how each quest starts and finishes.
- `progression-requirements`: the requirement graph, its playthrough tiers, and the checks that keep it complete.

### Modified Capabilities

None.

## Impact

- Clean build: new processor stages for quest routes and the requirement graph, their tables in `src/erenshor/application/processor/writer.py`, and repositories under `src/erenshor/infrastructure/database/repositories/`.
- Wiki: `QuestRepository.get_quest_panel_rows` reads the canonical routes.
- CLI: a `progression` command group with `show`.
- Tests: unit tests for each route method and relation family, data tests on the main build.
- Documentation: the README's Concepts section and the `refreshing-game-data` skill.
