## Context

See `proposal.md`. The facts that shape the approach, checked on 2026-10-11 against build 24405256 and the live wiki:

- The treasure guardian view is live and is the pattern for every view: `wiki generate-lua` writes `Module:Erenshor/Data/TreasureGuardians` from the clean database, `Module:Erenshor/TreasureGuardian` loads it with `mw.loadData` and renders by stable key, and `{{TreasureGuardianStats}}` places it on a page. A key without data renders a visible message and the tracking category `Pages with missing Erenshor treasure guardian data`.
- `Module:Erenshor/Data/Links` (1.6 MB) holds every entity's name, page, image, kind, and subtype, indexed by key (`byKey`) and by page (`byPage`). `Module:Erenshor/Link` renders names, icons, and hover cards from it. Pages that already link entities load it. On live, Breena Carpenter uses 7.9 MiB of Lua memory and 0.11 s, Ability Books 10.4 MiB and 0.50 s, and Quests 10.4 MiB and 0.26 s. The limits are 50 MiB and 15 s.
- The 54 vendors that have a page are the 54 pages with a `Store inventory` table: item, type, price, and unlock condition. Breena Carpenter sells 7 items and 14 more after quests. A vendor sells at `round(ItemValue)` (`GameData.CurSellVal`) and adds the `UnlockItemForVendor` item of each completed quest in `QuestRewardsForSale`, which the clean database holds as `character_vendor_quest_unlocks` and `quest_variants.unlock_item_for_vendor_stable_key`.
- Zone rosters group by encounter tier, which `characters.encounter_tier` holds: Abyssal Lake's table lists the 9 enemies and 6 bosses that the clean database places there. Port Azure groups its NPCs by the sub-areas Outskirts, Slums, and Undercity Tunnels, which no exported table records.
- Players learn spells and skills only by using an item that teaches them (`ItemIcon.KnownSpells.Add` and `KnownSkills.Add`). 63 class-flagged spells have no teaching item, among them aura and consumable effects and spells without a required level. Each of the six Druid summon spells has a teaching scroll.
- Quests reach the player by dialog keyword (79), by quest chain (24), by reading an item (12), by partial turn-in (4), by script (3), and by entering a zone (1), as `quest_acquisition_sources` records. Alyssia Fearnon gives A Skeleton Eye for Alyssia Fearnon on the keyword "favor" for 155 experience and the Bonestudded Belt. Secure Port Azure follows Sivakayan Intel for Kilkay (1) or Sivakayan Intel for Ripper and is turned in to Captain Kilkay. The Tragedy at Goodsoil gives no experience, gold, or item.
- Every kill of a character with a loot table also rolls the special world drops (`LootTable.InitLootTable`), which `special_world_drops` holds as one row per item and roll: 38 items in 10 rolls on build 24405256, with each chance per kill at the default loot rate and each roll's level gate. The Global Drops section of the Enemies page lists 8 of the rolls in two hand-written tables. Five of them give a wrong chance, Sivakrux also a wrong level, and Essence of Amarion and Crystallized Balance are missing. The mask roll is on in build 24405256 (`GameManager.DropMasks`). The 16 masks have pages that editors wrote, but `mapping.json` has given them no page since 2026-01-30, without a recorded reason, so the link catalog lacks them.

## Goals / Non-Goals

**Goals:**

- Every table that design D3 of `adopt-data-backed-wiki` lists for step 3 renders from generated data through a documented view.
- A new view is a builder, a module, and a template, following the treasure guardian view.
- A dedicated editor can write a module against any view's data from the module's own text and the data guide.

**Non-Goals:** see `proposal.md`.

## Decisions

### D1. One data module for each view, keyed by the page's entity

Each view has one bot-owned data module under `Module:Erenshor/Data/`, keyed by the stable key of the entity whose page shows the view: `VendorStock` by vendor, `ZoneRosters` by zone, `ClassAbilities` by class, and `Quests` by quest. An overview reads the module of its kind: the quest overview reads `Quests`, the zone overview reads `Zones`, which holds each zone's type, level range, and connections, and the world drop view reads `WorldDrops`, keyed by item. Rows hold stable keys and plain values. Names, pages, and icons stay in `Data/Links`, so a renamed page changes one module.

A module that would pass the page size limit is split into shards when it gets there, as the item shards are. No view module is near the limit: the largest, `ZoneRosters`, folds the 8,997 wiki-visible spawn rows into 1,181 rows, one for each character and zone.

Alternatives considered:

- Entity modules that embed relationships, such as one `Data/Characters` with drops, spawns, and stock. Rejected: a change to one vendor's stock would re-render every character page, and the July `Data/Characters` reached 5.1 MB.
- Tables shaped like the Cargo schema with a query module over them. Rejected: the clean database and Python already answer queries. A second query layer on the wiki would need its own documentation, tests, and limits, and a view needs only a builder and a module.

### D2. Python builds and checks the rows

A builder in `src/erenshor/application/wiki_lua/` derives each view's rows from the clean database, next to the existing writers, and `wiki generate-lua` writes them. Each view declares its fields once: name, type, and meaning. The writer renders that declaration as the comment that opens the module, so the description cannot drift from the rows.

Generation fails, naming the module, the row, and the field, when:

- a key does not resolve in the link catalog;
- a value holds wiki markup (`[[`, `]]`, `{{`, `}}`, `<`, `>`) or a line break;
- a value has another type than its declaration. A field holds one type, as WARFRAME's database guidelines also ask, so modules never test types at run time;
- a row lacks a field that the view does not declare optional, or holds a field that the view does not declare.

The existing size check applies to every module.

### D3. View modules and templates

Each view is a repository module `Module:Erenshor/<View>` with `p.render(args)` and a frame entry point, and a template `Template:<View name>` that invokes it, with documentation and an example in `<noinclude>`. Before a slice adds a template, it checks that the name is free on the wiki. The proposed names are `Vendor stock`, `World drops`, `Zone roster`, `Class abilities`, `Quest data`, `Zone list`, and `Quest list`.

A view resolves its entity from `stablekey`. Without it, the view takes the entity of its kind whose page is the current page, through a public `Link.pageKeys(kind, page)` over the existing `byPage` index. When several entities of the kind share the page, the view shows an error that lists their keys. When the entity has no rows, the view shows that the data is missing and adds the page to `Pages with missing Erenshor <view> data`. Entities render through `Module:Erenshor/Link`.

Each view has Scribunto testcases and structural rows in `wiki-dev/fixtures/smoke.tsv`. The render check of `adopt-data-backed-wiki` D7 covers each view module and template at its deploy.

### D4. Columns that editors write

A replaced table can hold a column that only people know, such as the notes column of the Zones overview. Such a view takes one parameter for each row, named by the row's page title: `{{Zone list|Port Azure=Starting city}}`. It renders the value in the column and adds the page to a tracking category when a parameter names no row. Only the overview slice uses this, because only the overviews have such a column.

### D5. Replacing a table on a page that people own

People own the pages with the hand-maintained tables (`adopt-data-backed-wiki` D2). For each slice:

1. Announce the replacement on Discord `#wiki-chat` and on the talk page of `Erenshor Wiki:Game Data`.
2. Render the view on each page through TemplateSandbox and compare its rows with the hand table. Each difference is either a stale row of the table, which the view corrects, or a gap in the pipeline, which is fixed before the replacement.
3. Review each page with WoWMuch. The edit replaces only the table and keeps every other text. Groupings that the data lacks, such as Port Azure's sub-areas, are decided per page: the editors' text stays next to the view, or the view replaces it.
4. Write one guarded edit per page against the reviewed revision, with a rollback manifest.

### D6. Deploy and refresh

Data modules deploy with the other generated data through `wiki deploy-repo-pages`, and view modules and templates with the repository modules and templates. The dependency check, the render check, and the drift check apply as for every repository page. After a data deploy, MediaWiki's job queue re-renders the pages that use a changed module. `wiki refresh-embedded` forces it when a check must see the new render at once. Nothing purges pages by hand.

### D7. Modules that editors write

The data guide lists the view data modules and links each module, whose opening comment describes its fields. It shows how a module loads data with `mw.loadData` and renders links with `Module:Erenshor/Link`, with the view modules as examples. A module that an editor writes is owned by people. Generated modules change only by adding fields. A changed structure is published under a new title, and the readers move before the old module goes (`adopt-data-backed-wiki` D1).

### D8. The vendor script

`src/tools/update_vendor_inventory_tables.py` and `src/tools/generate_vendor_inventory_tables.py` with `src/erenshor/tools/vendor_inventory_tables.py` write and check vendor tables from outside the pipeline. The vendor slice deletes them and their tests once no vendor page holds a `Store inventory` table.

### D9. What a vendor sells

A vendor page shows one deduplication group, as the item sources do: 11 vendor pages have several characters. Vendor items are not part of the deduplication identity, so a group can hold a copy that players never meet, such as an unplaced backup prefab, with stock that the copy in the game lacks. The clean view `vendor_offers` lists what the copies in the game sell: the copies in `characters_in_game`, which the game places or spawns, a spell summons, or a treasure hunt can dig up. Every reader of vendor stock reads `vendor_offers`: this view, the item sources, the obtainability checks, and the guide. In game on 2026-10-11, Samuel Thatcher sold the 5 items of his placed copy, and none of the 5 more that the unplaced Shopkeeper Treven prefab, which carries his name, lists.

An item that only some copies sell names the Reliquary furniture sets that place those copies: 5 of the Pocket Vendor's 11 items come only with the Stone Vendor Set. Generation stops when such an item has a seller that no furniture places, because a row cannot say which copy sells it.

A row's type is the item kind of `Data/Items`, with Furniture for the game's furniture sets. A general item is Mold when smithing upgrades with it, Crafting when a recipe uses it or it is fuel, Quest Item when a quest requires it or reading it assigns or completes a quest, and Lore when it has a book title. A finer label of a hand table, such as Potion or Cosmetic, needs a rule in the data first.

### D10. World drops

`WorldDrops` holds, for each item that a special world drop roll can yield, the roll's chance per kill at the default loot rate and the lowest level of an enemy that rolls it. `{{World drops}}` lists every item, most likely first, with its chance and the lowest enemy level, and says that the chances hold at the default loot rate. A roll that a game flag turns off has no rows (`special-world-drops` spec), so the masks appear only while a build drops them.

The masks' mapping entries name the pages that editors wrote, without the exclusion that kept them out of generation while the export could not describe them (decided with the user on 2026-10-12), so the link catalog and the view know them, and generation merges into those pages as into any other item page: it keeps the editors' prose and their Cosmetic Item type, and fills the infobox, the source, the icon, and the pictures. Their icons and renders reach the wiki through the image publication like any other item's.

The note below the Global Drops tables, which says that six common items can replace a common drop, stays editors' text. The export does not read `GameManager.CommonWorldItems`, and the loot calculator folds that swap into one `A Common World Drop` row for each character, which names no item. Task 5.44 of `adopt-data-backed-wiki` models the swap.

### Failure handling, grouping, and rollback

- Generation fails closed on the checks of D2 and on the size limit.
- A deploy stops at a new script error in the render check, at a missing dependency, and at drift, and names the page.
- A view without data says so visibly and joins its tracking category.
- A slice groups its commits: the builder and data module, the view module and template, the deploy, and the replacements. A replacement waits until its view renders on live.
- Generated modules and repository pages roll back through their deploy manifests, and replaced tables through the guarded-edit rollback manifests.

## Risks / Trade-offs

- [Editors cannot query the data ad hoc on the wiki] → The public SQLite database and the Sheets serve analysis, a new view is a builder and a module, and dedicated editors can write modules against the documented data. If editors need queries over facts that they write, Cargo stored on their own pages can be discussed with wiki.gg staff then.
- [A change to a data module re-renders every page that uses it] → One module for each view keeps a change to a vendor's stock to the vendor pages. `Data/Links` already reaches 2,726 pages.
- [The data lacks groupings that editors made] → Each page is decided in review (D5).
- [A replacement changes text that people wrote] → Announcement, a review of each page, and a rollback manifest (D5).
- [Lua limits] → Today's heaviest pages use 10.4 MiB of 50 MiB and 0.5 s of 15 s. Each slice records the cost of its heaviest page after its deploy.

## Migration Plan

1. Land the foundation: the field declarations, the checks, the module header, and `Link.pageKeys`.
2. Land the slices in order: vendor stock, world drops, zone rosters, class abilities, the quest panel, and the overviews. Vendor stock comes first, because its tables are the stalest and its slice deletes the vendor script. World drops follows, because its table gives wrong chances and its slice is small.
3. Document the views and modules in the data guide and the skill, then archive.

Rollback: see "Failure handling, grouping, and rollback".

## Open Questions

None.
