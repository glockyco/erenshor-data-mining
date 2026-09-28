## Why

When an enemy dies, `LootTable.InitLootTable` rolls its own loot table and then a fixed set of special world drops that do not depend on the table: Sivak, a random world drop mold, a random map, Essence of Amarion, an XP potion, Inert Diamond, Planar Shard, a random mask or the Molorai Mask, Crystallized Balance, and Planar. The pipeline models only the table rolls. The wiki item pages, the sheets, and the map item search therefore show no source for these drops, or only a secondary source. Crystallized Balance, for example, shows only its Braxonian Fossil source. GitHub issue #274 tracks the gap.

Most of the rules are already extracted: code facts `loot.world_drop.*` hold the chance and level gate of each roll, but no consumer reads them. The items in each roll are not in the data at all. They come from the `GameManager` and `Misc` components in `LoadScene`, which the export does not read.

## What Changes

- The Unity export reads the special-drop item pools and flags from the `GameManager` and `Misc` components in `LoadScene` and writes them to the raw database.
- Code facts gain the Essence of Amarion roll and the ordinary-mask and Molorai Mask split. The existing `loot.world_drop.masks` and `loot.world_drop.molorai_mask` facts give only the chance of the outer mask roll, not the 98% and 2% shares.
- The clean build combines the pools with the code facts into one row per item and roll: the chance per kill at the default loot rate, and the level that the killed enemy must exceed. Pools that a game flag disables (the demo-only roll, masks when `DropMasks` is off) produce no rows.
- The wiki item pages, the drop-chances sheet, the map item search, and the Lua/Cargo item data show these rows as a world drop source.
- The GitHub issue text is corrected: the Molorai Mask gets 2% of the mask roll, not 1%.

## Capabilities

### New Capabilities

- `special-world-drops`: What the pipeline records about the special world drops, and how the item-facing outputs present them.

### Modified Capabilities

None.

## Impact

- Unity export: a new listener and record under `src/Assets/Editor/`, and the raw database schema.
- Code facts: `src/tools/CodeFacts/` (a scoped matcher for the mask split) and `specs/erenshor-facts.json`.
- Clean build: `src/erenshor/application/processor/` and the clean schema in `writer.py`.
- Consumers: the wiki item source section and templates, `src/erenshor/application/wiki_lua/`, the Cargo source-type registration, `src/erenshor/application/sheets/queries/drop-chances.sql`, and the map item search (`getItemSources` and the item popup).
- Golden baselines change, which needs approval at capture.
- Deploys: maps and sheets after verification. The wiki deploy stays a separate decision and needs Category:Elites first.
- Non-goals: per-character loot tables, the "A Common World Drop" row, the Adventure Guide (its item sources are quest-directed and a world drop gives no location to go to), and loot-rate or guild bonuses beyond the default.
