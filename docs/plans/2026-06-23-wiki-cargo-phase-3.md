---
title: Wiki Cargo Phase 3 — Item Relationships, Flags & Character Junctions
type: plan
status: active
created: 2026-06-23
parent: 2026-06-04-wiki-cargo-data-architecture
---

# Wiki Cargo Phase 3 — Item Relationships, Flags & Character Junctions

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Read `skill://wiki-templates`, `skill://unity-export-system`, `skill://code-facts`, and `skill://refreshing-game-data` before starting.

**Goal:** Build the unified, item-owned `ObtainedFrom` / `UsedIn` Cargo relationship tables plus derived `IsAuctionable`, complete item-flag repository mapping, and the `CharacterAbilities` / `Spawns` junctions, then cut reverse displays over to Cargo queries — all on the local `wiki-dev` harness, with the live wiki untouched (production cutover is Phase 7).

**Architecture:** Item obtainability and usage become two unified typed tables keyed on `ItemKey`, **stored from the item page** (the only owner that already has Cargo + a dual-path gate), which collapses the Phase-5 ordering trap (Quest/Zone/Class templates have no `cargoStore` yet). Generated relationship rows are written forward via `Module:Erenshor/Cargo` and read reverse via Cargo queries; the denormalized reverse arrays are removed. Hardcoded game constants (player auction-listing gates, smithing upgrade IDs) are **consumed from the `code_facts` table**, never transcribed — derivations assert the exact extracted comparison strings and hard-fail on drift. `Drops` (character-owned) and `ContainerDrops` (item-owned) are folded into `ObtainedFrom` and deleted.

**Variant scope — clean cut to playtest.** The wiki ships from the current shipping build; playtest is the shipping build in waiting (promotes to main within ~a week). Every pipeline run, code-fact pin, and golden baseline in this plan targets the **playtest** variant — no dual-variant support. The pinned renderings are the shipping build's renderings, so they carry over unchanged at promotion and any stale non-shipping build fails fast. `ObtainedFrom` and `Spawns` declare `Origin` (`generated`|`community`) + (for `ObtainedFrom`) `SourceText` **up front**, so the Phase 4 community layer adds only rows and templates — never a production schema recreate.

**Tech Stack:** C# Unity export (`src/Assets/Editor/`), Python clean-build processor + repositories (`src/erenshor/`), Lua Scribunto modules + PortableInfobox templates (`wiki/modules/`, `wiki/templates/`), the `wiki-dev` Docker MediaWiki+Cargo harness, SQLite, pytest, golden baselines.

---

## Grounding (verified before planning)

- **Item-owned decision:** only `Item.lua` and `Character.lua` have `cargoStore` today (`wiki/modules/Erenshor/{Item,Character}.lua`). `Quest.lua`/`Zone.lua` do not and there is no Class template, so quest/zone/class-owned `ObtainedFrom` rows are impossible until Phase 5. Making `ObtainedFrom`/`UsedIn` item-owned makes Phase 3 fully harness-testable now.
- **Taxonomy is complete & deterministic.** `ObtainedFrom` SourceTypes: `drop, vendor, dialog, quest, craft, item_use, mining, fishing, item_bag, starting`. `UsedIn` UseTypes: `craft_material, quest_requirement, upgrade_material, blessing_removal_material`. Treasure hunting = the four `Lost Treasure (…)` **chest characters** carrying authored `loot_drops` (covered by `drop`, no special-casing). Wishing wells grant nothing (coordinate markers only).
- **Existing repos** already answer most reverse queries: `get_vendors_selling_item`, `get_characters_dropping_item` (`repositories/characters.py:262,311`), `get_item_drops`/`get_item_sources` (`repositories/items.py:528,568`), `get_quests_rewarding_item` (uses `quest_variants.item_on_complete_stable_key`, `repositories/quests.py:72`), `get_quests_requiring_item` (`:109`), `get_items_requiring_item` (`:233`), and Spawns reads `wiki_character_spawns` (`repositories/spawn_points.py:47`). New methods needed: dialog, craft-reward, mining, fishing, item_bag, starting, smithing special uses.
- **Code facts already extracted** (playtest `code_facts` table, values are comparison strings). Player auctionability pins are the player-facing renderings:
  - `auction.player_listing_gates` → `item_level='!= 0'`, `item_value='!= 0'`
  - `auction.player_listing_gate` → `ok='true'` (playtest-only assert for the equippable-only confirmation gate)
  - `smithing.upgrade_ids` → `strings='31377423,46289586,2298018,2265228'`
  The legacy `auction.updateah_gates` and `auction.replacebag_gates` facts remain available for SimPlayer restocking analysis, but are **not** inputs to `is_auctionable`: that flag follows the `GameData.ActivateSlotForAuction` player path and the `AuctionHouseUI.CommitItem` General-slot rejection.
- **`Item.RareItem`** reaches raw export, clean `items.rare_item`, and sheets; the `Item` domain model and Lua data map declare it, but the item repository must select it before generated Lua receives its value (Task A6). `is_auctionable` remains a derived field for Task A5. **`SellValue`** is a derived export (0.65×`ItemValue`), not a game field; the player auction gate uses `ItemValue`.
- **Storage shape — nested hidden owners (validated).** Each relationship table has one hidden store template that both declares it (in `<noinclude>`) and stores its rows (a Lua-backed `#cargo_store` in `<includeonly>`): `ItemObtainedFromStore`→`ObtainedFrom`, `ItemUsedInStore`→`UsedIn`, `CharacterSpawnsStore`→`Spawns`, `CharacterAbilitiesStore`→`CharacterAbilities`. `Item`/`Character` declare only their own detail table (`Items`/`Characters`) and *transclude* the hidden owners, so no template exceeds the wiki.gg 1-declare budget and **no attach-trick is needed**. The live `2026-07-09-wiki-cargo-storage-validation` probe confirmed this shape on wiki.gg. Data refreshes reparse pages (rows rewrite in place); only a schema change recreates a table.

## File map (created / modified)

- C# export: `src/Assets/Editor/Database/ClassStartingItemRecord.cs` (new); `src/Assets/Editor/ExportSystem/AssetScanner/Listener/ClassStartingItemsListener.cs` (new); `src/Assets/Editor/ExportBatch.cs`.
- Code facts: `src/tools/CodeFacts/specs/erenshor-facts.json` (only if a drift fix or a new `smithing`/`auction` spec is needed — see 3C2).
- Python build: `src/erenshor/application/processor/writer.py` (schemas), `processor/entities.py` (`process_classes` and `process_items`), `processor/auction.py` (new, `is_auctionable`), `domain/entities/item.py`, and the item repository mapping.
- Lua gen: `src/erenshor/application/wiki_lua/items.py`, `characters.py`, new builders; `domain/value_objects/source_info.py`.
- Lua modules: `wiki/modules/Erenshor/Item.lua`, `Character.lua`.
- Templates: `wiki/templates/Item.wiki`, `Character.wiki` (transclude the hidden owners); new hidden store owners `ItemObtainedFromStore.wiki`, `ItemUsedInStore.wiki`, `CharacterSpawnsStore.wiki`, `CharacterAbilitiesStore.wiki`; delete `Drops.wiki`, `ContainerDrops.wiki` at the end of 3E.
- Harness: `wiki-dev/smoke/cargo.py`, `wiki-dev/cargo_check.py`, `wiki-dev/fixtures/cargo_*.tsv`, `wiki-dev/fixtures/pages/*.wiki`, `wiki/modules/Erenshor/{Item,Character}/testcases.lua`.
- Freshness: `src/erenshor/application/wiki_deploy/refresh.py`.

## Verification commands (used throughout)

```bash
uv run erenshor -V playtest extract export        # Unity batch -> raw SQLite (after C# changes)
uv run erenshor -V playtest extract code-facts    # shipped DLL -> raw code_facts
uv run erenshor -V playtest extract build         # raw -> clean SQLite
uv run erenshor -V playtest wiki generate-lua     # clean DB -> local Lua data modules
uv run python wiki-dev/import_pages.py            # import modules/templates/pages into harness
uv run python wiki-dev/smoke_test.py               # action=parse render + structural checks
uv run python wiki-dev/cargo_check.py              # recreate + validate Cargo rows vs fixtures
uv run pytest tests/...                            # Python unit/integration
uv run erenshor -V playtest golden capture         # regenerate golden baselines (playtest = shipping build)
uv run python src/tools/wiki_cargo_storage_probe.py --live --candidate all  # live wiki.gg Cargo storage-shape gate (one-off, pre-Phase-3)
```

Per-module Lua assertions live in `wiki/modules/Erenshor/<Type>/testcases.lua` and are exercised by the harness render; Cargo row shape is asserted by `cargo_check.py` against `wiki-dev/fixtures/cargo_*.tsv`.

---

## Sub-phase 3A — Exports & item flags

Outcome: clean `items` already carries `rare_item`; this sub-phase adds `is_auctionable`, `class_starting_items`, complete item repository mapping, and refreshed golden baselines. No wiki changes yet.

### Task A1: Export `Item.RareItem` (complete)

- [x] `ItemRecord.RareItem` is stored from `ItemListener.CreateItemRecord`.
- [x] `RareItem` is classified as captured in `field-coverage.json`.

### Task A2: Carry `rare_item` into the clean `items` table (complete)

- [x] `writer.py` defines `items.rare_item`; `test_item_flags_flow_to_clean` verifies the raw-to-clean path.
- [x] The item sheets query includes `rare_item`; Task A6 completes the repository mapping required for the existing Lua data map to receive its value.

`is_auctionable` belongs solely to Task A5; it is not a clean-schema side effect of
the completed `rare_item` work.

### Task A3: Export `class_starting_items`

**Files:**
- Create: `src/Assets/Editor/Database/ClassStartingItemRecord.cs`
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/Listener/ClassStartingItemsListener.cs`
- Modify: `src/Assets/Editor/ExportBatch.cs` (component-listener block)
- Modify: `src/tools/ExportSurface/field-coverage.json` (classify `CharSelectManager` fields)

- [x] **Step 1:** Record class. `ClassName` + `SortOrder`, rather than item
  stable key, is the composite list-position identity: an item may legitimately
  occur more than once. Mirror the existing ordered-junction pattern with a
  unique composite `Indexed` constraint:

```csharp
#nullable enable
using SQLite;

[Table("ClassStartingItems")]
public class ClassStartingItemRecord
{
    public const string TableName = "ClassStartingItems";

    [Indexed(Name = "ClassStartingItems_Primary_IDX", Order = 1, Unique = true)]
    public string ClassName { get; set; } = string.Empty;

    [Indexed(Name = "ClassStartingItems_Primary_IDX", Order = 2, Unique = true)]
    public int SortOrder { get; set; }

    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string ItemStableKey { get; set; } = string.Empty;
}
```

- [x] **Step 2:** Listener. `CharSelectManager` is a MonoBehaviour, so use a
  component listener. Map `WarStart` to Paladin and the game-side typo
  `DueslistStart` to Duelist; the remaining field names map directly. Track
  both manager count and source configuration (`scene:<path>` or
  `prefab:<path>`), then fail from `OnScanFinished` unless each is exactly one.
  `AssetScanner` traverses every prefab and every build scene, so this catches
  a duplicated configuration rather than silently doubling exports. Reject
  null or empty class lists and null item entries; only valid 0-based,
  contiguous positions reach the database.

```csharp
public void OnAssetFound(CharSelectManager manager)
{
    _managerCount++;
    TrackSourceConfiguration(manager);
    Add("Arcanist", manager.ArcanistStart);
    Add("Paladin", manager.WarStart);
    Add("Duelist", manager.DueslistStart);
    Add("Druid", manager.DruidStart);
    Add("Stormcaller", manager.StormStart);
    Add("Reaver", manager.ReaverStart);
}
```

- [x] **Step 3:** Add `CharSelectManager` to field coverage. Mark the six
  starting-item lists as captured by `ClassStartingItemsListener`; classify
  every other public manager field as ignored because it is character-selection
  UI or runtime state, not starting-inventory data.

- [x] **Step 4:** Register in `ExportBatch.cs`, in the
  `RegisterComponentListener` block:

```csharp
["classstartingitems"] = () => scanner.RegisterComponentListener(new ClassStartingItemsListener(db)),
```

- [x] **Step 5:** Re-export and assert the single-source invariant in the
  listener plus contiguous rows in raw SQLite:

```bash
uv run erenshor -V playtest extract export
sqlite3 variants/playtest/erenshor-playtest-raw.sqlite "
WITH per_class AS (
  SELECT ClassName,
         COUNT(*) AS item_count,
         MIN(SortOrder) AS first_order,
         MAX(SortOrder) AS last_order,
         COUNT(DISTINCT SortOrder) AS distinct_orders
  FROM ClassStartingItems
  GROUP BY ClassName
)
SELECT *
FROM per_class
ORDER BY ClassName;"
```

Expected: the export succeeds only after finding one `CharSelectManager`
configuration; exactly six class rows, each with `item_count >= 1`,
`first_order = 0`, `last_order = item_count - 1`, and
`distinct_orders = item_count`.

- [x] **Step 6: Commit** — `feat(export): export per-class starting items`

### Task A4: Carry `class_starting_items` into the clean DB

**Files:**
- Modify: `src/erenshor/application/processor/writer.py` (new CREATE TABLE + `insert_class_starting_items`)
- Modify: `src/erenshor/application/processor/entities.py` (`process_class_starting_items`)
- Test: processor test asserting a known class has starting items keyed to valid item stable keys.

- [x] **Step 1: Write the failing test** asserting `class_starting_items` rows exist and `item_stable_key` ∈ valid items.
- [x] **Step 2:** Run; expect failure.
- [x] **Step 3:** Add `CREATE TABLE class_starting_items` with
  `PRIMARY KEY (class_name, sort_order)` + `insert_class_starting_items`; in the
  processor, `_rows` from raw `ClassStartingItems`, `_filter_junction` on
  `ItemStableKey` against valid item keys, `_rename_cols`, insert. Missing item
  references are filtered without renumbering surviving `sort_order` values.
- [x] **Step 4:** `extract build`; run test. Expected: PASS.
- [x] **Step 5: Commit** — `feat(pipeline): carry class starting items into the clean DB`

### Task A5: Derive `is_auctionable` from player auction rules (drift-gated)

**Files:**
- Create: `src/erenshor/application/processor/auction.py`
- Modify: `src/erenshor/application/processor/entities.py` (`process_items`)
- Modify: `src/erenshor/application/processor/writer.py` (`items.is_auctionable`)
- Modify: `src/tools/CodeFacts/specs/erenshor-facts.json`
- Test: `tests/unit/application/processor/test_auction.py`

- [x] **Step 1: Write failing tests** for the player-facing predicate and
  drift gate. The truth table covers nonzero item level/value, the
  `NoTradeNoDestroy` restriction, and the `General`-slot restriction.

- [x] **Step 2:** Run; expect import failure.

- [x] **Step 3:** Implement. `auction.player_listing_gates` extracts the exact
  `GameData.ActivateSlotForAuction` comparisons (`ItemLevel != 0`,
  `ItemValue != 0`). The playtest-only
  `auction.player_listing_gate` assert pins the
  `AuctionHouseUI.CommitItem` `RequiredSlot == General` rejection. The
  processor validates the extracted gates before writing items, then derives
  `is_auctionable` from the player listing path:
  `ItemLevel != 0`, `ItemValue != 0`, `!NoTradeNoDestroy`, and
  `RequiredSlot != General`.

- [x] **Step 4:** Run:

```bash
uv run erenshor -V playtest extract code-facts
uv run erenshor -V playtest extract build
```

Validate that `items.is_auctionable` contains no `General`-slot rows and that
the count is lower than the total item count.

- [x] **Step 5: Commit** — `feat(pipeline): derive item auctionability from player rules`

### Task A6: Surface `is_auctionable` and complete item flag repository mapping

**Files:** `src/erenshor/domain/entities/item.py`, the item repository row→entity mapping, and `tests/unit/infrastructure/database/repositories/test_items.py`.

- [x] `Item` declares `rare_item`.
- [x] **Step 1:** Add `is_auctionable` after `rare_item` with the description
  “Derived: player can list this item on the auction house (boolean).”

```python
is_auctionable: int | None = Field(
    default=None,
    description="Derived: player can list this item on the auction house (boolean)",
)
```

- [x] **Step 2:** Select `player_cannot_sell`, `rare_item`, and
  `is_auctionable` in the item repository, then add a unit test asserting
  fetched `Item` entities carry the item flags.
- [x] **Step 3:** Run the repository test. PASS.
- [x] **Step 4: Commit** — `feat(pipeline): expose rare_item and is_auctionable on the Item entity`

### Task A7: Recapture golden baselines

- [x] **Step 1:** `uv run erenshor -V playtest golden capture` (playtest = the shipping build in waiting; see `skill://refreshing-game-data` variant-safety rules — capture writes the shared `tests/golden/`, so this is only safe because playtest is the build we are cutting over to).
- [x] **Step 2:** Review the diff: `items.csv` adds `is_auctionable`;
  `class_starting_items` has clean-DB coverage from A3/A4 but no golden
  consumer yet. `code_facts.csv` shows the player auction renderings
  (`auction.player_listing_gates.item_level='!= 0'`,
  `auction.player_listing_gates.item_value='!= 0'`,
  `auction.player_listing_gate.ok='true'`) alongside the retained legacy
  SimPlayer auction facts and
  `smithing.upgrade_ids='31377423,46289586,2298018,2265228'`.
- [x] **Step 3:** `uv run pytest` green.
- [x] **Step 4: Commit** — `test(pipeline): refresh item flag golden baselines`

---

## Sub-phase 3B — `ObtainedFrom` unified table (item-owned)

Outcome: a single `ObtainedFrom` Cargo table written from the item page, covering every deterministic source type. `Drops`/`ContainerDrops` keep working until 3E folds and deletes them.

### Task B1: `ItemObtainedFromStore` hidden owner (declares + stores `ObtainedFrom`)

**Files:**
- Create: `wiki/templates/ItemObtainedFromStore.wiki` (hidden store owner: declares + stores `ObtainedFrom`)
- Modify: `wiki-dev/smoke/cargo.py` (FIELDS/KEY/QUERY + loader/checker), `wiki-dev/cargo_check.py` (`CARGO_TABLES`, `CARGO_TEMPLATES_BY_TABLE`)

- [x] **Step 1:** Reserved-word check (a keyword column silently no-ops the whole declare). Verify each proposed column name against SQL keywords before declaring: `ItemKey, SourceType, SourceKey, SourceText, Probability, IsGuaranteed, Quantity, SourceCondition, Origin`. `CONDITION` is a SQL keyword → rename to **`SourceCondition`**. Document in the template comment (like `CastRange`/`CharacterKey`).
- [x] **Step 2:** Write `ItemObtainedFromStore.wiki` — the hidden owner that declares `ObtainedFrom` in `<noinclude>` and stores its rows from `<includeonly>` (Lua-backed `#cargo_store`, wired in B4). Declare the **final** Phase-4 schema up front — `SourceText` and `Origin` are nullable, so generated rows leave them null until Phase 4 adds the community row template:

```wikitext
<includeonly>{{#invoke:Erenshor/Item|cargoObtainedFromStore|stablekey={{{stablekey|}}}}}</includeonly><noinclude>{{#cargo_declare:_table=ObtainedFrom
|ItemKey=String
|SourceType=String
|SourceKey=String
|SourceText=String
|Probability=Float
|IsGuaranteed=Boolean
|Quantity=Integer
|SourceCondition=String
|Origin=String
}}
Hidden store owner of the unified item-obtainability junction (one row per item × source × condition when a source has variants).
ItemKey is the obtained item's StableKey; SourceType ∈ drop|vendor|dialog|quest|craft|item_use|mining|fishing|item_bag|starting|community; SourceKey resolves by type (character/quest/item/mining-node/water/item-bag/zone/class StableKey, or null for free-text community rows) at display time. World-point SourceKeys preserve mining-node, water, and item-bag identities and resolve through their connected zone for display via `zones.scene_name`; SourceText carries free-text community sources; Origin ∈ generated|community. `SourceCondition` is part of the generated-row identity so fishing day/night rows remain distinct. The `Item` page transcludes this hidden owner, whose `<includeonly>` runs the Lua-backed `#cargo_store`; `Item` itself declares only the `Items` table.
</noinclude>
```

- [x] **Step 3:** Add to `wiki-dev/smoke/cargo.py` the
  `CARGO_OBTAINED_FROM_FIELDS`, `OBTAINED_FROM_KEY =
  ("ItemKey", "SourceType", "SourceKey", "SourceCondition"),` query fields,
  and `load_/check_cargo_obtained_from_rows` helpers mirroring ContainerDrops.
  Register the table/template in `cargo_check.py`, including a required
  `--cargo-obtained-from` fixture argument and validation call.
- [ ] **Step 4:** `import_pages.py` then `cargo_check.py`; expect the empty
  table to recreate cleanly.
- [ ] **Step 5: Commit** — `feat(wiki): declare the unified ObtainedFrom Cargo junction`

### Task B2: Repository methods for ObtainedFrom sources

**Files:** `infrastructure/database/repositories/{characters,items,quests,zones}.py`,
`domain/value_objects/source_info.py`, `application/wiki_lua/{items,generation}.py`,
their Protocols, and focused repository tests.

Define a frozen `ObtainedFromInfo` record carrying `source_type`, the
StableKey `source_key`, optional `probability`, `is_guaranteed`, `quantity`, and
`condition`. This preserves stable source identity that the existing
`WikiLink` tuples intentionally omit.

Add one method and focused test for each source path:
- **`get_character_drop_sources(item_key)`** — deduplicated character groups
  from `loot_drops`; retain the maximum probability per character group and
  the guaranteed-pool flag. SourceType `drop`.
- **`get_vendor_sources_for_item(item_key)`** — existing vendor query plus
  quest-unlock vendors from `character_vendor_quest_unlocks`, attributed through
  `quest_variants.unlock_item_for_vendor_stable_key = item_key`; emit one
  representative character StableKey and `condition="requires quest <name>"`
  for each gated item/quest pair. SourceType `vendor`.
- **`get_characters_giving_item(item_key)`** — `character_dialogs` with
  optional quest-gate condition. SourceType `dialog`.
- **`get_quest_reward_sources(item_key)`** — quest reward variants with quest
  StableKey and QuestLink. SourceType `quest`.
- **`get_recipes_rewarding_item(item_key)`** — `crafting_rewards` with recipe
  item StableKey and reward quantity. SourceType `craft`.
- **`get_item_use_sources(item_key)`** — reverse `item_drops` plus
  `spell_created_items` (offering-bag products). SourceType `item_use`.
- **`get_mining_nodes_for_item(item_key)`** — join mining nodes to their
  connected zones; preserve one row per item×mining-node with the node's drop
  chance. SourceKey is the mining-node StableKey. SourceType `mining`.
- **`get_fishing_waters_for_item(item_key)`** — join fishables to waters (and
  their connected zones), normalize `DayFishable`/`NightFishable` to `day`/`night`,
  and deduplicate one row per item×water×condition using the maximum drop chance.
  SourceKey is the water StableKey, not the containing zone. SourceType `fishing`.
- **`get_item_bag_sources_for_item(item_key)`** — join item bags through their
  connected zones and preserve one row per item-bag StableKey. SourceType
  `item_bag`.
- **`get_classes_starting_with_item(item_key)`** — join
  `class_starting_items` to `classes`; use `class:<class_name>` as the
  canonical SourceKey because no ClassRepository or ClassLink exists.
  SourceType `starting`.

The mining, fishing, and item-bag methods belong to `ZoneRepository`; each
joins through `zones.scene_name` to validate the world-point connection while
preserving the smallest source StableKey (mining node, water, or item bag).
The starting-item method belongs to `ItemRepository` and reads the existing
`classes` table. Extend the Lua generation/builder protocols and call sites to
pass the already-available `zone_repo`; do not invent a `classes.py` repository
or derive keys from page titles. Existing display methods remain responsible for
legacy infobox fields; the new source methods provide stable-keyed records.

- [x] **Commit** — `feat(pipeline): add stable-keyed ObtainedFrom reverse-source queries`; corrected world-point granularity is committed separately as `fix(pipeline): preserve granular world source identities`.

### Task B3: Python builder — `obtainedFrom` on the item data module

**Files:** `wiki_lua/{items,generation}.py`, `domain/value_objects/source_info.py`,
`tests/unit/application/wiki_lua/test_items_module.py`, and the Lua test fakes.

- [x] **Step 1: Write tests** asserting a fixture item yields typed rows: inert
  diamond from a treasure chest (`drop` with character key, probability,
  guaranteed flag), a fished item (`fishing` with water key and day/night
  condition), bread (`starting` with `class:<name>`), and offering stone
  (`item_use` with the bag source key).
- [x] **Step 2:** Focused tests covered the legacy fields and the new typed
  fixture contract before the formatter implementation.
- [x] **Step 3:** Extend `SourceInfo` with `obtained_from: list[ObtainedFromInfo]`.
  Add `_format_obtained_from(sources)` building one dict per source
  `{type, sourceKey, probability, guaranteed, quantity, condition}` and omit
  null/empty values through `_put`. Sort deterministically by
  `(type, sourceKey, condition, probability, quantity, guaranteed)`.
  Preserve the existing `vendorSource`, `source`, `questSource`,
  `relatedQuest`, `componentFor`, and `containerDrops` fields while adding
  `_put(row, "obtainedFrom", ...)`.
- [x] **Step 4:** Run tests; `uv run erenshor wiki generate-lua`; expect PASS.
- [x] **Step 5:** Commit — `feat(wiki): build item obtainedFrom source lists`


### Task B4: Lua store in the `ItemObtainedFromStore` owner

**Files:** `wiki/modules/Erenshor/Item.lua` (after `containerDropRows`, ~line 821), `wiki/templates/Item.wiki` (transclude the hidden owner), `wiki/templates/ItemObtainedFromStore.wiki`, `wiki/modules/Erenshor/Item/testcases.lua`.

- [x] **Step 1: Write failing testcase** in `Item/testcases.lua`: `Item.cargoObtainedFromRows({ args = { stablekey = "item:<fixture>" } })` returns rows with `ItemKey`/`SourceType`/`SourceKey` set (mirror the `cargoContainerDropRows` testcase at `Item/testcases.lua:120`).
- [x] **Step 2:** Add `obtainedFromRows(item)` (mirror `containerDropRows`, `Item.lua:805`): one `{ {"ItemKey", item.stableKey}, {"SourceType", src.type}, {"SourceKey", src.sourceKey}, {"SourceText", src.sourceText}, {"Probability", src.probability}, {"IsGuaranteed", src.guaranteed == true}, {"Quantity", src.quantity}, {"SourceCondition", src.condition}, {"Origin", "generated"} }` per entry in `item.obtainedFrom` (generated rows always carry `Origin="generated"`, `SourceText=nil`). Expose `p.cargoObtainedFromStore(frame)` — resolves the item by `stablekey` and runs the `Cargo.store("ObtainedFrom", fields)` loop — as the entrypoint the hidden `ItemObtainedFromStore` owner invokes from its `<includeonly>`.
- [x] **Step 3:** In `Item.wiki` `<includeonly>`, transclude `{{ItemObtainedFromStore|stablekey={{{stablekey|}}}}}` so each item page renders the hidden owner, whose `<includeonly>` stores the `ObtainedFrom` rows. `Item` keeps `#cargo_declare:Items`; its existing `#cargo_attach` for the legacy `ContainerDrops` table remains unchanged until that table is migrated to its own storing owner.
- [x] **Step 4:** `import_pages.py` → `smoke_test.py` → `cargo_check.py`. Expect ObtainedFrom rows for fixture item pages; local MediaWiki validation passes.
- [x] **Step 5: Commit** — `feat(wiki): store item ObtainedFrom rows from the item page`

### Task B5: Fixtures + smoke expectations

**Files:** `wiki-dev/fixtures/cargo_obtained_from.tsv`, an item fixture page exercising ≥3 source types, `cargo_check.py` validation wiring.

- [x] **Step 1:** Extend the `Magical Bag` fixture page/module with `drop`, `fishing`, `item_use`, and `starting` source rows, and add their expected Cargo rows to `wiki-dev/fixtures/cargo_obtained_from.tsv`.
- [x] **Step 2:** Recreate the local Cargo tables, null-edit all fixture pages, and run `cargo_check.py`; ObtainedFrom validation passes for all four Magical Bag source rows.
- [x] **Step 3: Commit** — `test(wiki): cover ObtainedFrom rows on the local harness`

---

## Sub-phase 3C — `UsedIn` unified table (item-owned)

Outcome: `UsedIn` written from the item page for `craft_material`, `quest_requirement`, `upgrade_material`, and `blessing_removal_material`.

### Task C1: `ItemUsedInStore` hidden owner (declares + stores `UsedIn`)

**Files:** `wiki/templates/ItemUsedInStore.wiki`, `wiki-dev/smoke/cargo.py`, `cargo_check.py`.

- [x] **Step 1:** Columns `ItemKey, UseType, TargetKey, Quantity, Slot` — `SLOT` is safe in the existing Cargo schema. Write the hidden owner `ItemUsedInStore.wiki` (declares + stores `UsedIn`) mirroring `ItemObtainedFromStore.wiki`. `UseType ∈ craft_material|quest_requirement|upgrade_material|blessing_removal_material`. The Merging Vessel forge/merge mechanic (`2265228`) is not emitted in Phase 3.
- [x] **Step 2:** Add smoke fields/key (`("ItemKey","UseType","TargetKey")`) and checker; register in `cargo_check.py`.
- [x] **Step 3:** Import the owner and recreate the clean local Cargo tables; `UsedIn` recreates successfully.
- [x] **Step 4: Commit** — `feat(wiki): declare the unified UsedIn Cargo junction`

### Task C2: smithing special-use materials via the `smithing.upgrade_ids` code fact

**Files:** new repo method `get_item_smithing_special_uses(item_key)` + a small code-fact-backed resolver; tests.

- [x] **Step 1:** Write tests: the resolver validates the full pinned set `31377423,46289586,2298018,2265228`, maps Planar Stone to `upgrade_material`, maps Inert Diamond to `blessing_removal_material`, omits the Merging Vessel forge/merge mechanic, and fails fast on missing or changed facts.
- [x] **Step 2:** Implement a resolver that reads `smithing.upgrade_ids` from the clean `code_facts`, splits the CSV, joins `items.id`, validates the full four-ID set, then classifies by game semantics from `Smithing.Combine`: `31377423` + `46289586` → `upgrade_material`; `2298018` → `blessing_removal_material`; `2265228` → deferred forge/merge mechanic, no `UsedIn` row in Phase 3. Tag `# code-fact: smithing.upgrade_ids`. The fact name is historical: the matcher is `string_constants`, so it bundles heterogeneous string literals from `Smithing.Combine`; consumers must classify, not bulk-map.
- [x] **Step 3:** Add `craft_material` reverse rows from `crafting_recipes WHERE material_item_stable_key = ?` with recipe target, quantity, and slot; add quantity-bearing `quest_requirement` rows from `quest_required_items`.
- [x] **Step 4:** Focused repository tests pass.
- [x] **Step 5: Commit** — `feat(pipeline): resolve UsedIn rows for smithing special materials via code facts`

### Task C3: Python builder — `usedIn` on the item data module

- [x] Mirror B3: `_format_used_in(sources)` → `usedIn` list `{type, targetKey, quantity, slot}`; extend `SourceInfo`/`build_item_sources_by_item`; `_put(row, "usedIn", ...)`. Tests cover each emitted UseType (`craft_material`, `quest_requirement`, `upgrade_material`, `blessing_removal_material`). **Commit** — `feat(wiki): build the item usedIn list in Lua data`

### Task C4: Lua store in the `ItemUsedInStore` owner

- [x] Add `usedInRows(item)` + `p.cargoUsedInStore` + store loop in `Item.lua` (mirror B4). Transclude `{{ItemUsedInStore|stablekey=…}}` from `Item.wiki` `<includeonly>` alongside `{{ItemObtainedFromStore}}` — no attach-trick. `Item/testcases.lua` covers the store; local smoke and a direct `UsedIn` Cargo query pass. **Commit** — `feat(wiki): store item UsedIn rows via the ItemUsedInStore owner`

### Task C5: Fixtures + smoke

- [x] Add `wiki-dev/fixtures/cargo_used_in.tsv` and fixture pages for Planar Stone → `upgrade_material`, Inert Diamond → `blessing_removal_material`, Bronze Ore → `craft_material`; import, null-edit, `smoke_test.py`, and `cargo_check.py` all pass. **Commit** — `test(wiki): cover UsedIn rows on the local harness`

---

## Sub-phase 3D — Character junctions

Outcome: `Spawns` + `CharacterAbilities` written from the character page (Character.lua already has `cargoStore`). Cargo declares the semantic usage label as `AbilityUsage` because `Usage` is an SQL keyword in the local Cargo fork.

### Task D1-D3: `Spawns`

- [x] **D1:** `wiki/templates/CharacterSpawnsStore.wiki` — hidden owner declaring + storing `Spawns`: `CharacterKey, Zone, Scene, X, Y, Z, SpawnChance, NightSpawn, SpawnUponQuestComplete, LevelMod, RareNpcChance, SpawnType, Origin` (reserved-word check on `Zone`/`Scene`; both safe). `Origin` declared up front so Phase 4 adds only `{{SpawnPoint}}` rows, no schema recreate. smoke + cargo_check wiring. **Commit** — `feat(wiki): declare the Spawns Cargo junction`
- [x] **D2:** Python builder `spawns` on the character data module from `spawn_points.py` (`wiki_character_spawns`, which filters `character_spawns` to `is_wiki_generated` and already expands `character_chained_spawns`). **Fold treasure-chest possible locations in here**: for each of the four `Lost Treasure (…)` chest characters, join `treasure_chest_possible_spawns` × `treasure_locations` and emit one row per pickable location with `SpawnType='treasure_chest'`, `SpawnChance=nil` (the game's per-location chest odds are not exported), coordinates from the location; without this, a treasure-hunting item's `ObtainedFrom` `drop` row resolves to a chest character whose page shows no spawn locations. Generated rows carry `Origin='generated'`. Tests cover a chest character yielding `treasure_chest` rows. **Commit** — `feat(wiki): build character spawns list in Lua data`
- [x] **D3:** `spawnRows(character)` + store entrypoint in `Character.lua`; `Character.wiki` `<includeonly>` transcludes `{{CharacterSpawnsStore|stablekey=…}}` (no attach-trick — `Character` declares only `Characters`; each junction has its own hidden owner). `Character/testcases.lua`. `cargo_check.py`. **Commit** — `feat(wiki): store character Spawns rows`

### Task D4-D6: `CharacterAbilities`

- [x] **D4:** `wiki/templates/CharacterAbilitiesStore.wiki` — hidden owner declaring + storing `CharacterAbilities`: `CharacterKey, AbilityKey, AbilityUsage`. smoke + cargo_check. **Commit** — `feat(wiki): declare the CharacterAbilities Cargo junction`
- [x] **D5:** Python builder unioning `character_attack_spells` + `character_buff_spells` + `character_heal_spells` + `character_cc_spells` + `character_taunt_spells` + `character_group_heal_spells` + `character_attack_skills` (currently 0 rows but include for completeness), each tagged with its `AbilityUsage` (attack/buff/heal/cc/taunt/group_heal/attack_skill). `character_death_shouts` is intentionally excluded: the game treats `ShoutOnDeath` as a death-event chat message, not an ability; defer it to a dedicated ordered table preserving `SequenceIndex`. Tests. **Commit** — `feat(wiki): build character abilities list in Lua data`
- [x] **D6:** `characterAbilityRows` + store entrypoint in `Character.lua`; `Character.wiki` transcludes `{{CharacterAbilitiesStore|stablekey=…}}` (no attach-trick). `Character/testcases.lua`. `cargo_check.py`. **Commit** — `feat(wiki): store CharacterAbilities rows`
- [x] **D7:** Fixtures `wiki-dev/fixtures/cargo_spawns.tsv`, `cargo_character_abilities.tsv` + a multi-spawn / multi-ability character fixture; `cargo_check.py` green. **Commit** — `test(wiki): cover Spawns and CharacterAbilities on the harness`

---

## Sub-phase 3E — Reverse-query cutover, fold/delete, freshness

Outcome: reverse displays read Cargo; `Drops`/`ContainerDrops` are gone; freshness handles item-ownership.

### Task E1: Fold `drop` + delete `Drops`

- [ ] Confirm every `Drops` fact is reproduced as an `ObtainedFrom` `drop` row (item-owned) — write a parity test comparing the old `Drops` expectations against `ObtainedFrom WHERE SourceType='drop'`. Then remove `dropCargoRows`/`Drops` store from `Character.lua`, delete `wiki/templates/Drops.wiki`, and remove the `Drops` entries from `smoke/cargo.py` + `cargo_check.py`. **Commit** — `refactor(wiki): fold character drops into item-owned ObtainedFrom`

### Task E2: Fold `item_use` + delete `ContainerDrops`

- [ ] Same parity check for `ContainerDrops` → `ObtainedFrom WHERE SourceType='item_use'`; remove `containerDropRows`/store from `Item.lua`, delete `wiki/templates/ContainerDrops.wiki`, drop the smoke/cargo_check entries. `Item` now declares `Items` and transcludes `{{ItemObtainedFromStore}}` + `{{ItemUsedInStore}}` (no `ContainerDrops`). **Commit** — `refactor(wiki): fold container drops into item-owned ObtainedFrom`

### Task E3: Reverse-query rendering; remove denormalized arrays

- [ ] Render item "How to Obtain" (`ObtainedFrom`) and "Used For" (`UsedIn`), character "Dropped by", and quest "Rewards" via Cargo queries (per `docs/plans/2026-06-04-wiki-cargo-data-architecture.md` §8.1). Remove the denormalized reverse arrays from the Lua data modules: `source`, `vendorSource`, `questSource`, `componentFor`, `containerDrops` (item) and the `dropRates` **Cargo** path (character keeps its own-page display only if still sourced from its module; otherwise query). Update `Item.wiki`/`Character.wiki` infobox fields to the query renderers. Update `Item/`,`Character/testcases.lua`. Full `smoke_test.py` + `cargo_check.py`. **Commit** — `refactor(wiki): render item/character reverse relations from Cargo queries`

### Task E4: Item-ownership freshness

- [ ] Extend `src/erenshor/application/wiki_deploy/refresh.py` so a change in a source table (loot/vendor/dialog/quest/craft/mining/fishing/item_bag/class) reparses the **owning item pages** (item-owned rows only refresh on item-page parse — the §10 freshness model). On the harness, drive this via the recreate + null-edit path. Add/extend a `tests/unit/.../test_refresh.py` assertion. **Commit** — `fix(wiki): reparse owning item pages so relationship Cargo stays fresh`

### Task E5: Full validation gate

- [ ] `uv run pytest`; full harness sequence (`uv run erenshor -V playtest wiki generate-lua` → `import_pages.py` → `smoke_test.py` → `parity_check.py` → `cargo_check.py`); `uv run erenshor -V playtest golden capture` diff review. **Commit** — `test(wiki): full Phase 3 harness + golden validation`

---

## Special & hardcoded logic paths (do-not-forget register)

Every non-standard obtainability/usage path found in the game code is listed here with its disposition. Deferred paths stay in this plan register until they are implemented or moved into a future `docs/plans/` artifact; modeling any of them must consume a **code fact** (never transcribe an item ID from decompiled `.cs`).

| Path | Source (file:line) | Disposition |
|---|---|---|
| Vendor quest-unlock | `VendorWindow.cs:57-60`, `character_vendor_quest_unlocks` | **Implemented** — `vendor` + `SourceCondition` (Task B2) |
| Smithing golden combine | `Smithing.cs:83` (`31377423` Mold: An Otherwordly Box + `46289586` Planar Stone) | **Implemented** — `upgrade_material` via `smithing.upgrade_ids` (Task C2) |
| Smithing blessing removal | `Smithing.cs:120` (`2298018` Inert Diamond) | **Implemented** — `blessing_removal_material` via `smithing.upgrade_ids` (Task C2) |
| Smithing merge/forge box | `Smithing.cs:159-240` (`2265228` Merging Vessel; requires fuel, two matching items, 15-qty cap) | **Deferred** — distinct forge/merge mechanic; keep out of Phase 3 `UsedIn` until the item forging mechanic is documented/modelled. |
| Break Fossil | `SpellVessel.cs:1942`, `item_drops` | **Implemented** — `item_use` (Task B2/B3) |
| Offering Stone bag | `SpellVessel.cs:2043` (id `340104`), `spell_created_items` | **Implemented** — `item_use` (Task B2/B3) |
| PlanarShard byproduct | `Smithing.cs:278` (`GM.PlanarShard`, blessing-removal output) | **Deferred** — hardcoded output, no data table; needs a `smithing.planar_shard_output` code fact. |
| Chessboard Candlekeeper → mold | `Chessboard.cs:108-112` (`ReplaceStatue`, inspector-set) | **Deferred** — 1-off, inspector reference; needs export of the field. |
| Time Stone | `SpellVessel.cs:1997` (id `2936548`, ShiveringTomb2/StowawayPortal) | **Deferred** — hardcoded `item_use`; needs a `spellvessel.time_stone_id` code fact. |
| Braxonian Flame Well quality ritual | `TradeWindow.cs:219-222` (`CheckOfferingStones`, quality 2/1) | **Deferred** — hardcoded quality upgrade; needs an offering-stone code fact. |
| Runtime global random world-drop pool | `LootTable.cs:88-158` (Maps/Molds/Planar/etc., per-NPC at runtime) | **Deferred** — not per-source; `loot.world_drop.*` facts exist; needs "may drop globally" renderer. |
| 1-in-20 fished Map | `Fishing.cs:68-70` (`GM.Maps` random) | **Deferred** — random, folds into the global-pool follow-up. |

- [ ] **Task SP1:** before Phase 3 completion, either implement each Deferred row or move it into a future `docs/plans/` artifact so it survives the phase.

---

## Pre-Phase-3 gate — live storage validation (complete)

Resolved by the `2026-07-09-wiki-cargo-storage-validation` plan. Outcome:

- **Storage shape:** nested hidden store templates (each declares + stores one table,
  transcluded by `Item`/`Character`); no attach-trick. Direct multi-attach also works
  on wiki.gg but is not used.
- **Refresh:** a data-only change needs no recreate — reparsing a page rewrites its
  rows in place (validated: edits/deletes remove stale rows after a forced-link purge).
  A schema change recreates via `cargorecreatetables` + per-table `cargorecreatedata`
  with row-count polling; a large table uses a replacement table (manual
  `Special:CargoTables` switch-in) to avoid the empty-table window.
- **Rights:** the main account can drive `edit`/`delete`/`recreatecargodata`; `WoWBot`
  still lacks `delete`/`recreatecargodata`, so confirming the deploy bot's recreate
  right stays a Phase 7 gate.

Run the probe with `uv run python src/tools/wiki_cargo_storage_probe.py --live --candidate all`.

---

## Self-review

- **Spec coverage (§ of `2026-06-04-wiki-cargo-data-architecture.md`):** §7.1 IsAuctionable → A5/A6; IsRare raw/clean export → A1/A2 (complete), with repository mapping in A6; §8 ObtainedFrom → 3B; §8 UsedIn → 3C; §8 Spawns/CharacterAbilities → 3D; §8.1 reverse-query rendering + drop denormalized arrays → E3; §10 freshness → E4; item→ability scalar columns → already shipped in Phase 2 (excluded). `class_starting_items` `starting` source → A3/A4 + B2/B3.
- **Ownership trap:** resolved by item-owning ObtainedFrom/UsedIn; quest/zone/class need no Cargo template in Phase 3.
- **Code-fact boundary:** every constant (player auction-listing gates, legacy SimPlayer auction bounds, smithing string IDs) is consumed from `code_facts` with a drift gate + `# code-fact:` tag; none transcribed from `.cs`. Pins are the **playtest** renderings (the shipping build's); `auction.player_listing_gates` pins both nonzero comparisons and `auction.player_listing_gate` pins the equippable-only confirmation rejection. Legacy auction facts remain extracted but are intentionally outside the `is_auctionable` derivation.
- **Reserved words:** `Condition`→`SourceCondition`; `CharacterKey` retained;
  re-check each new column at declare time (a keyword silently no-ops the
  table). `SourceCondition` is included in `ObtainedFrom` identity so
  day/night fishing rows do not collide.
- **Type consistency:** `obtainedFrom`/`usedIn` Lua field names,
  `SourceType`/`UseType` literals, and the smoke `*_KEY` tuples are used
  identically across B/C/E.
- **Deferred paths:** enumerated in SP1 and retained in planning docs, none dropped silently.
