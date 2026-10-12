## Why

Editors keep the lists that span entities by hand, and those lists fall behind the game. 54 NPC pages carry store inventory tables that a script outside the pipeline rewrites, and on 2026-07-16 it found 37 of them stale or missing. On 2026-09-09 an editor had to add a missing summon spell to the Druid ability table. Zone pages carry hand-written rosters, and the Quests overview shows `?` for The Tragedy at Goodsoil, for which the export records no experience, gold, or item. The Global Drops table of the Enemies page gives a wrong chance for five of its eight rolls and lacks two rolls of build 24405256.

`publish-wiki-cargo-data` planned to fill Cargo tables from bot-owned storage pages and to render these lists with query templates. wiki.gg does not allow that use of Cargo ([Cargo](https://support.wiki.gg/wiki/Cargo), "Do NOT use Cargo if"), its query results stay cached until each page is purged, WoWBot may purge 30 pages a minute, and a schema change needs a replacement table that an administrator switches in by hand. Comparable wikis keep exported data in Lua modules (WARFRAME's `/data` modules, Terraria's `Module:Iteminfo/data`) and use Cargo or a similar store only for facts that people write on articles (Terraria, Path of Exile, Weird Gloop's Bucket). This wiki already renders one list this way: `{{TreasureGuardianStats}}` reads the generated `Module:Erenshor/Data/TreasureGuardians` through `Module:Erenshor/TreasureGuardian`.

## What Changes

- Each list that spans entities becomes a view: a bot-owned data module that Python generates from the clean database, keyed by the stable key of the page that shows it, and a repository-owned module and template that render it. Names, pages, and icons come from the link catalog `Module:Erenshor/Data/Links` at render time.
- This change adds seven views: vendor stock, world drops, zone rosters, class abilities, the quest panel, the zone and quest overviews, and the bosses of the Braxonian Game Board.
- Each data module begins with a generated description of its fields, so that a dedicated editor can write a module against it without reading the pipeline.
- The change lands in slices. Each slice publishes one view, checks it on live, and replaces the hand-maintained tables that the view covers, after an announcement and a review of each page.
- The vendor slice deletes the vendor table script, its module, and its tests.
- The data guide `Erenshor Wiki:Game Data` explains the views and the data modules.
- `publish-wiki-cargo-data` is withdrawn. The wiki stores no Cargo data.

Non-goals: Cargo, a query language on the wiki, the item sources and character drops of item and character pages (they come with the data-backed templates of step 4 of `adopt-data-backed-wiki`), sub-areas of zones that the export does not record, and the conversion of articles.

## Capabilities

### New Capabilities

- `wiki-data-views`: how lists that span entities reach wiki pages from generated data, what each view shows, and how editors use and extend them.

### Modified Capabilities

- `special-world-drops`: the item outputs that show world drops name the wiki's Lua item data, which no longer has a Cargo counterpart.

## Impact

- New: view builders in `src/erenshor/application/wiki_lua/`, the data modules `Module:Erenshor/Data/VendorStock`, `WorldDrops`, `ZoneRosters`, `ClassAbilities`, `Quests`, `Zones`, and `GameBoard`, the export of the piece that summons each Game Board boss, the view modules under `wiki/modules/Erenshor/` with testcases, the view templates under `wiki/templates/`, and a section of `wiki/content/Erenshor Wiki/Game Data.wiki`.
- Removed: `src/tools/update_vendor_inventory_tables.py`, `src/tools/generate_vendor_inventory_tables.py`, `src/erenshor/tools/vendor_inventory_tables.py`, and their tests.
- Changed: `mapping.json` links the 16 masks to the pages that editors wrote for them, so that the link catalog and the world drop view know them.
- Live wiki: the data modules, view modules, and templates deploy through `wiki generate-lua` and `wiki deploy-repo-pages` with the existing dependency, render, and drift checks. Each replaced table is one reviewed guarded edit with a rollback manifest.
- Migration boundary: a slice replaces a table only after its view renders on that page through TemplateSandbox with every fact of the table, or after each difference is explained. The vendor script goes when the last vendor table is gone.
