## Context

See `proposal.md`. The facts that shape the approach, checked on 2026-10-03:

- The live wiki runs LIBRARIAN 4.21.0 (wiki.gg's Cargo fork). `Special:CargoTables` lists only two empty legacy tables. Special:CargoQuery and Special:CargoExport exist. Special:Drilldown does not.
- An anonymous TemplateSandbox parse showed that `mw.ext.cargo.query` and `#cargo_query` work from Lua on the live wiki. The anonymous `cargoquery` API works too.
- `#cargo_store` is reached from Lua only through `frame:callParserFunction`, because wiki.gg disables the native Lua store. The 2026-07 live probe stored rows from `User:` pages through nested storage templates, removed stale rows on edit, kept two entities on one page apart by key, and kept a replacement table queryable until an administrator switched it in at Special:CargoTables, a step with no API.
- The WoWMuch account holds `recreatecargodata`, but neither BotPassword session does. The live grant list offers `cargoadmin` (create and delete Cargo data) and `cargobasic` (queries).
- Players learn spells and skills only by using an item that teaches them (`ItemIcon.KnownSpells.Add` and `KnownSkills.Add`). 63 class-flagged spells have no teaching item. They include aura and consumable effects and spells without a required level.
- A vendor sells at `round(ItemValue)` (`GameData.CurSellVal`) and adds the `UnlockItemForVendor` item of each completed quest in `QuestRewardsForSale`, which the export holds as `character_vendor_quest_unlocks` and `quest_variants.unlock_item_for_vendor_stable_key`. Selling with the sell button pays `round(ItemValue × 0.65) + 1` gold but logs the amount without the extra 1. Selling a stack pays `round(ItemValue × 0.65)` per item.
- `loot_drops` holds 345 rows for the placeholder `A Common World Drop`, which is not an item. Three event spawns of `FernallaPortalEvent` have no zone. `RareNPCChance` above 100 means the rare spawn always wins, and the clean `spawn_chance` already accounts for it.

## Goals / Non-Goals

**Goals:** complete, exact, documented tables that editors can query and extend, filled and refreshed without touching articles.

**Non-Goals:** see `proposal.md`. This design also does not move article rendering to Cargo. Articles keep rendering their own facts from their parameters and the Lua data modules.

## Decisions

### D1. A Python schema is the single source

`src/erenshor/application/wiki_cargo/schema.py` defines each table: name, columns (name, Cargo type, meaning, whether generated rows, community rows, or both fill it), the row identity, and the builder that derives rows from the clean database. Generation produces the declaration template, the storage pages, and the column documentation from it. Generation fails on a column name that MySQL 8 or Cargo reserves, on a column that no builder or community template fills, on a value with markup, and on a `*Key` value that has no `Entities` row.

### D2. Storage pages hold the rows as template calls

Each row is one call of its table template on a storage page, for example `{{Cargo/Spawns|CharacterKey=character:a beaktooth|ZoneKey=zone:stowaway|…}}`. Saving the page stores its rows, so the text of a storage page always matches what it stores, and its history shows every data change as a readable diff. A refresh edits only the pages whose rows changed.

Alternatives:

- Lua row modules that a storage page reads. Rejected: the modules and the stored rows can disagree until each storage page is reparsed, and the refresh then needs purges and job polling.
- Rows stored by the articles, as the old design planned. Rejected: tables stay incomplete until every article converts, and each recreation reparses hundreds of articles.

Values pass through one escaper: `|` becomes `{{!}}`. Generation fails on `{{`, `}}`, `[[`, `]]`, `<`, `>`, and line breaks, so an unexpected value stops the build instead of corrupting a page.

### D3. Pages, templates, and shards

- `Template:Cargo/<Table>` declares the table, documents its columns, stores one row per call, and renders nothing.
- `Erenshor Wiki:Cargo/<Table>/<NN>` holds the rows of shard `NN`. A stable hash of the row's owner key picks the shard, so new rows change one page. Each table has a fixed shard count with room to grow, and rows are sorted by key within a page. A page starts with a notice that it is generated, the build number, a link to the hub, `__NOINDEX__`, and a hidden category.
- `{{ItemSource}}` and `{{SpawnPoint}}` attach to `ItemSources` and `Spawns` and store community rows. They resolve the entity key through `Entities` with a Cargo query. An unresolved key stores nothing and adds the page to a tracking category.
- The hub `Erenshor Wiki:Cargo` (repository source `wiki/content/Erenshor Wiki/Cargo.wiki`) lists the tables, the query and community templates with examples, and the rules: do not edit storage pages, report wrong data, keys and their kinds, and the build the data comes from.

### D4. The first schema

Columns that hold an entity's stable key end in `Key`. Chances are percentages from 0 to 100. Times are seconds. Booleans are `yes` or `no`.

| Table | One row per | Main columns | Source |
|---|---|---|---|
| `Entities` | item, character, spell, skill, stance, zone, quest, faction, or class | StableKey, Kind, Name, Page, Image | the clean entity tables, with the link catalog's naming rules |
| `Items` | item | ItemType, Slot, WeaponType, Level, BuyValue, SellValue, flags | `items` |
| `ItemStats` | item and quality | Quality, damage, delay, armor, attributes, resists | `item_stats` |
| `ItemClasses` | item and class | ItemKey, ClassKey | `item_classes` |
| `ItemEffects` | item and effect role | EffectType (teaches, proc, worn, click, aura, wand, bow, skill), AbilityKey, Chance | `items` |
| `Characters` | character | Tier, Level, FactionKey, IsVendor, health, mana, armor, resists | `characters` |
| `Spawns` | wiki-visible placement or possible treasure location | CharacterKey, ZoneKey, X, Y, Z, SpawnChance, IsRare, NightOnly, QuestGateKey, SpawnType, Origin | `wiki_character_spawns`, `treasure_chest_possible_spawns` |
| `CharacterAbilities` | character, ability, and use | CharacterKey, AbilityKey, AbilityUse | the `character_*_spells` and `character_attack_skills` tables |
| `CharacterFactionEffects` | character and faction | CharacterKey, FactionKey, StandingChange | `character_faction_modifiers` |
| `Spells`, `Skills`, `Stances` | ability | the queryable scalar columns of each type | `spells`, `skills`, `stances` |
| `AbilityClasses` | ability and class | AbilityKey, ClassKey, RequiredLevel | `spell_classes` and the per-class skill levels |
| `ItemSources` | item and source | ItemKey, SourceType, SourceKey, ZoneKey, Chance, IsGuaranteed, Quantity, MinLevel, QuestGateKey, drop condition flags, Origin, SourceText | loot, special world drops, vendor stock and quest unlocks, quest rewards, crafting, item drops, mining, fishing, item bags, starting gear |
| `ItemUses` | item and use | ItemKey, UseType, TargetKey, Quantity | `crafting_recipes`, `quest_required_items`, the smithing code facts |
| `Zones` | zone | ZoneType, hostile level minimum, median, and maximum, flags | `zones` and hostile spawns |
| `ZoneConnections` | zone line | ZoneKey, DestinationKey, QuestGateKey | `zone_lines`, `zone_line_quest_unlocks` |
| `Quests` | quest | XP, Gold, Repeatable, flags | `quests`, `quest_variants` |
| `QuestRoles` | quest, character, and role | QuestKey, CharacterKey, QuestRole (gives, completes, takes items), Keyword | `quest_character_roles`, `character_dialogs` |
| `QuestPrerequisites` | quest and required quest | QuestKey, RequiredQuestKey | `character_dialogs`, `quest_complete_other_quests` |
| `QuestFactionEffects` | quest and faction | QuestKey, FactionKey, StandingChange | `quest_faction_affects` |
| `Factions` | faction | the faction's scalar columns | `factions` |

Rules from the export audit:

- Loot chances are the pipeline's chance per kill at the default loot rate. The drop flags carry the game's conditions: guaranteed drops, unique items that do not drop while the player holds one, and worn items. The `A Common World Drop` placeholder rows are not items. The hub describes the common world drop instead.
- `SellValue` states the gold for selling one item. Its exact rule follows the in-game check of task 2.4.
- A class abilities list shows only abilities that an item teaches, because players learn abilities no other way. `AbilityClasses` still holds every class flag of the game.
- The three event spawns without a zone are resolved in the clean build or published without a zone, never dropped.

### D5. Query templates are Lua over Cargo

`Module:Erenshor/Query` implements every query template with `mw.ext.cargo.query`, and renders links through `Module:Erenshor/Link` so that names, icons, and hover cards match the rest of the wiki. A template resolves its argument through `Entities` by key or by page. A page that holds several entities of the requested kind produces an error that lists their keys. Each template has a documentation subpage with TemplateData and an example with its output. Proposed names: `Zone roster`, `Class abilities`, `Vendor stock`, `Item sources`, `Character drops`, `Zone drops`, `Quest data`, `Faction effects`, `Item list`, `Zone list`, `Quest list`, and `Boss list`. Task 6.1 checks that the names are free on the wiki.

### D6. Commands

- `wiki cargo generate` writes the table templates and storage pages under `variants/<variant>/wiki/cargo/` and fails on any D1 violation.
- `wiki cargo deploy` deploys the table templates, stops if a table does not exist, deploys the changed storage pages, runs `verify`, and purges the pages that use query templates. It uses the guarded write and the drift check of `refresh-wiki-articles`, with new manifest stages for table templates and storage pages.
- `wiki cargo verify` reads every table through the anonymous `cargoquery` API, normalizes each value by its type, and compares the rows whose `Origin` is not `community` with the expected rows.
- `wiki cargo create-tables` logs in as the interface-admin session, requires `recreatecargodata`, and runs `cargorecreatetables` for each table that does not exist. For a table whose declaration changed, it creates a replacement table, fills it, and stops with the switch-in instructions. The next run verifies the switched table.

### D7. Cargo leaves the article path

The article templates no longer declare or store tables after `refresh-wiki-articles`. This change removes what remains: the store, declare, and query templates of the old design, `ArmorTable` and `WeaponTable`, the Cargo parts of `Template:Spell` and `Template:Skill`, the Lua row builders and `cargoStore` entry points, `Module:Erenshor/Cargo`, the Cargo storage probe, and the old fixtures. The deploy reports the live copies of removed pages for an administrator to delete, because the bot cannot delete.

## Risks / Trade-offs

- [Cargo might not store from the project namespace] → The first slice (task 5) stores `Entities` and `Spawns` on live before the other tables exist.
- [A large storage page might parse slowly] → The 1,000-row limit applies, and the first slice measures the parse time of the largest page through TemplateSandbox before any table exists.
- [A schema change needs a sysop and a manual switch-in, and renaming a column breaks editors' queries] → The schema is reviewed before the first creation. New needs get new tables or new columns. Existing columns keep their names.
- [Query results are cached in page HTML] → `deploy` purges the pages that use query templates.
- [361 character keys contain coordinates and can change when a game update moves a character] → Community rows that use such a key join the tracking category after an update. The hub explains how to update them.
- [Editors edit a storage page] → The drift check stops the next deploy and names the page.

## Migration Plan

1. The maintainer enables the `cargoadmin` grant. `create-tables` checks it before its first change.
2. Build the schema code and the `Entities` and `Spawns` slice, test it in the local harness, and deploy it to live with `generate`, `deploy`, `create-tables`, `deploy`, and `verify`.
3. Add the remaining tables the same way, then the community and query templates, the hub, and the removals.

Rollback: storage pages and templates roll back through their manifests. A table stays empty or keeps old rows until its pages are saved again. An administrator deletes a table at Special:CargoTables.

## Open Questions

None.
