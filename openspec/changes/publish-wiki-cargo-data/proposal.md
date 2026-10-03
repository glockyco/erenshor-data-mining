## Why

The wiki runs Cargo, but no table exists, so editors cannot query game data. What they need sits in tables that editors keep by hand, and those tables fall behind the game. 54 NPC pages carry hand-copied vendor tables, and on 2026-07-16 the vendor-table tool found 37 of them stale or missing. On 2026-09-09 an editor had to add a missing summon spell to the Druid ability table. The `Quests` overview shows `?` for The Tragedy at Goodsoil, for which the export records no experience, gold, or item. Zone pages carry hand-written enemy lists, and the `Ability Books`, `Auras`, and `Zones` overviews repeat data the export already has. Only the maintainer can run the export pipeline, and editors who know a fact the export misses have no way to add it as queryable data.

The current design stores Cargo rows from converted articles. No article is converted, so every table would stay incomplete until all of them are. Table creation needs the `recreatecargodata` right, and neither configured bot session holds it today (checked 2026-10-03).

## What Changes

- One Python schema defines each table: its columns, their types and meaning, and how rows derive from the clean database. The declarations, the rows, and the column documentation are generated from it.
- Bot-owned storage pages under `Erenshor Wiki:Cargo/` hold the generated rows, one template call per row, at most 1,000 rows per page. Saving a storage page stores its rows. Every table is complete without any article change.
- The first schema covers entities, items (stats per quality, classes, effects), characters, spawns, character abilities, faction effects of kills, spells, skills, stances, class abilities by level, item sources in both directions (drops, world drops, vendors with quest unlocks, quest rewards, crafting, gathering, starting gear), item uses, zones with connections and hostile level ranges, quests (givers with their keywords, turn-ins, required items, rewards, prerequisites, faction effects), and factions.
- `erenshor wiki cargo generate`, `deploy`, `verify`, and `create-tables` build the pages, deploy them with the guarded and drift-checked path, compare every live table with the expected rows, and create tables through the interface-admin session.
- `{{ItemSource}}` and `{{SpawnPoint}}` let editors store their own rows, marked as community rows, in the same tables.
- Documented query templates render zone rosters, class abilities by level, vendor stock, item sources, character drops, zone drops, quest data, faction effects, and sortable item, zone, quest, and boss lists. A hub page documents the tables, the templates, and the rules.
- **BREAKING**: Cargo leaves the article path. The Cargo declarations and store calls in the `lua=1` branches of the entity templates, the store and query templates, the Lua Cargo row builders and store entry points, the Cargo parts of `Template:Spell` and `Template:Skill`, `Module:Erenshor/Cargo`, and the Cargo storage probe are removed. The local harness checks the storage pages instead.

## Capabilities

### New Capabilities

- `wiki-cargo-data`: What the wiki's Cargo tables hold, how generated and community rows reach them, and how editors query them.

### Modified Capabilities

None. Item sources keep listing special world drops, as `special-world-drops` requires.

## Impact

- New: `src/erenshor/application/wiki_cargo/`, the `wiki cargo` commands, generated pages under `variants/<variant>/wiki/cargo/`, `Module:Erenshor/Query`, the query and community templates, and the hub page `Erenshor Wiki:Cargo`.
- Removed: `wiki/templates/` store, declare, and query templates of the article path, the Cargo parts of `wiki/modules/Erenshor/`, `src/erenshor/tools/wiki_cargo_probe/`, and `wiki-dev` fixtures for the old tables.
- Live wiki: about 25 table templates, 50 to 60 storage pages, 15 query and community templates, and the hub page. Table creation is one privileged step per table.
- Prerequisite: the maintainer enables the `cargoadmin` grant ("Create and delete data through the Cargo extension") for the `WoWMuch@InterfaceDeploy` bot password at Special:BotPasswords.
- Depends on `refresh-wiki-articles`, which provides the guarded deploy, the drift check, and entity templates whose Lua branch needs exact `lua=1`.
- Non-goals: replacing the hand-maintained tables on pages (the next change uses these templates for that), data-backed article templates and article conversion, the size of the article data modules, the quest article strategy (#288), and Special:Drilldown, which the wiki does not install.
