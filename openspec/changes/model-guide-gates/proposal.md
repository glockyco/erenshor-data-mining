# Proposal

## Why

AdventureGuide sends players to places they cannot reach yet and to characters that are not there. The guide's entity graph already knows several of these gates, but the writer of the shipped `quest-guide.json` keeps only quest sources (`mod_writer._unlock_groups`), so every door and item gate is lost before the mod sees it. Other gates were never exported: the Shivering Step event, quest scripts that remove objects, disabled zone line components, and encounters that must be won first. Earlier runtime attempts at door gates were removed because they were unreliable and stalled the game, so this change also sets reliability and performance budgets for the runtime.

The gate kinds, highest player impact first:

1. Keyed doors in front of quest targets and zone lines. Examples: the Island Tomb lighthouse entrance and Occuphage (Stowaway's Step Lighthouse Key), the Shivering Step entrance (Shivering Key), Ghost of Wyland Sercher who starts Whispers of Wyland (Ghostly Key), Founder (Dockhouse Key), Lighthouse Flame (Shivering Step Lighthouse Key), Warded Shadow (Shadowed Key), Fallen Braxonia (Ancient Braxonian Key), Sablehart (Sableheart's Key). The game opens a keyed door when the key is on the keyring or in the inventory (`Door.OpenOrShut`). The guide ignores both.
2. The Shivering Step event (`ShiverEvent`). It assigns Meet Shivering Step on zone entry and finishes it when the four keeper quests are done, swaps the two Kio copies, removes the keepers, darkens the island and activates The Hider and ten spawn triggers after The Shivering Torch, and removes Kio after Changing the Lighthouse. The guide models the keeper quests as prerequisites of Meet Shivering Step and shows The Hider and the second Kio before they exist.
3. Placements that are inactive when a scene starts. `_character_spawns` drops `is_enabled`, so the guide presents inactive placements as ordinary ones. Outside the Reliquary rooms, whose furniture condition the guide already handles, 34 placed characters are inactive at scene start and have no exported activator, among them The Hider, the restored planar gods, and the disabled copies of Lucian Revald and Revan Gavault.
4. Zone lines that players cannot use (issue #298). Disabled `Zoneline` components and non-trigger colliders are exported as usable, and copies of the Island Tomb exits in the Shivering scenes are unreachable. A quest can still mark a disabled component as unlocked (Shivering Step to Hidden Hills after A Way To Erenshor). The map and the wiki's zone connections show these lines too.
5. Quest scripts that remove barriers, and the dungeon locks behind them: the staged barriers of Blooming Sepulcher (A Dying Wish), the Vitheo's Rest key doors, and the removal lists of `QuestSpawnListener`, `MultiQuestListener`, and `DynamicContentManager`, which the export ignores.
6. Encounters that must be won first: restored planar gods appear after their boss dies, Warded Shadow and the Reliquary Fiend are invulnerable until their wards die, A Strange Hermit answers only after Eldoth Molorai dies, and boss barriers in the planes open when their boss dies.

## What Changes

- Record every gate as a condition: OR groups of AND-ed atoms. Observable atoms are quest completed, quest not completed, item held, key held (keyring or inventory), and Reliquary room furnished. The advisory atom is encounter won. The mod evaluates observable atoms. It never hides a target because of an advisory atom, and shows that atom as guidance instead.
- Replace the quest-only unlock representation entirely. The existing quest unlocks of zone lines and characters, quest-started and quest-stopped spawn points, Reliquary furnishings, vendor stock unlocks, and item bag unlocks become conditions, and no path runs beside the new one. **BREAKING** for the database: `gate_conditions` replaces `zone_line_quest_unlocks` and `character_quest_unlocks`. **BREAKING** for the embedded format: `quest-guide.json` version 7 replaces `required_quest_groups`, `_character_quest_unlocks`, `required_quest_db_names`, and `spawn_upon_quest_complete_stable_key` with a condition table and condition references.
- Export every activation effect of the quest listeners in both directions with its trigger (quest, active quest, held item), the usability of each zone line component, and the serialized targets of the scripted activators. Pin the hand-encoded rules of those scripts and the door key rule as code facts.
- Give each reviewed fact one home. Corrections of exported rows, such as zone lines that players cannot reach, go into `mapping.json` with a reason. Which targets a keyed door or a removable barrier guards goes into a new reviewed file, `barriers.toml`, that the clean build reads and checks for completeness. The door and item curation of `quest_guides/graph_overrides.toml` moves to its proper home, and the Shivering Step overrides give way to the event rule.
- Model the Shivering Step event from its rules. Meet Shivering Step is acquired on zone entry and completed by the four keeper quests.
- Evaluate conditions in AdventureGuide in one place and migrate every gate consumer to it. When a target or a route hop is gated, explain the gate and navigate to what satisfies it.
- Mark unusable zone lines in the clean database and exclude them in every reader: the guide, the map, and the wiki's zone connections. This closes issue #298.
- Stop generating `quest_guides/guide.json`, which nothing reads, and remove its writer and command.
- Land each gate kind as its own verified slice, in the order above.

Non-goals, each recorded as an issue in the format of issue #282:

- Navigating several quests at once. It becomes its own OpenSpec change after this one lands, with budgets measured on the current navigation first.
- Travel that is not a zone line: teleport items and spells, the Azynthian Riftstone, the Reliquary rune portals and their movable endpoints, and the Box of Portals return.
- The Bellwain Isle puzzle, the Chessboard offering workflow, secret passages, and forced travel. The zone-wide spectre spawner keeps issue #282.
- Weather as a condition. Evadne keeps a plain explanation of the rain requirement.

## Capabilities

### New Capabilities

- `guide-gate-data`: how the export, code facts, reviewed facts, and the clean build record the conditions under which zone lines, placements, and sources are available, and how the guide compiler and `quest-guide.json` carry them.
- `guide-gated-navigation`: how AdventureGuide evaluates those conditions, explains unmet gates, navigates to what satisfies them, and which reliability and performance budgets it meets.

### Modified Capabilities

None.

## Impact

- Unity export: `QuestActivationListener`, a new scripted-activator listener, `ZoneLineListener`, `dynamic-spawn-catalog.toml`, `src/tools/ExportSurface/field-coverage.json`, and the records under `src/Assets/Editor/Database/`.
- Code facts: `src/tools/CodeFacts/specs/erenshor-facts.json`.
- Clean build: `src/erenshor/application/processor/`, the schema in `writer.py`, `mapping.json`, and the new `barriers.toml`.
- Guide: `src/erenshor/application/guide/`, the `guide` CLI commands, `quest_guides/graph_overrides.toml`, the regenerated `quest_guides/quest-guide.json`, and the removal of `quest_guides/guide.json` and `json_writer.py`.
- Readers of zone line usability: the map's zone line query (`src/maps/src/lib/database.base.ts`) and the wiki zone page generator (`src/erenshor/application/wiki/generators/pages/zones.py`).
- AdventureGuide: `Data/`, `State/`, `Navigation/`, `UI/`, `Diagnostics/DebugAPI.cs`, the test project, the README, and both changelogs.
- Documentation: the README, the AdventureGuide README, and the `refreshing-game-data`, `unity-export-system`, and `runtime-eval` skills.
- Shared resources: Unity exports, code-facts runs, and clean builds of the main variant, each announced before it starts.
- Unreleased guide fixes e1d2c587f, 141ce9ad1, and 5773f7ab0 ship with the mod release that follows this change.
