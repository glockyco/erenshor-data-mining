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

**Architecture:** Item obtainability and usage become two unified typed tables keyed on `ItemKey`, **stored from the item page** (the only owner that already has Cargo + a dual-path gate), which collapses the Phase-5 ordering trap (Quest/Zone/Class templates have no `cargoStore` yet). Generated relationship rows are written forward via `Module:Erenshor/Cargo` and read reverse via Cargo queries; the denormalized reverse arrays are removed. Hardcoded game constants (auction bounds, smithing upgrade IDs) are **consumed from the `code_facts` table**, never transcribed — derivations assert the exact extracted comparison strings and hard-fail on drift. `Drops` (character-owned) and `ContainerDrops` (item-owned) are folded into `ObtainedFrom` and deleted.

**Variant scope — clean cut to playtest.** The wiki ships from the current shipping build; playtest is the shipping build in waiting (promotes to main within ~a week). Every pipeline run, code-fact pin, and golden baseline in this plan targets the **playtest** variant — no dual-variant support. The pinned renderings are the shipping build's renderings, so they carry over unchanged at promotion and any stale non-shipping build fails fast. `ObtainedFrom` and `Spawns` declare `Origin` (`generated`|`community`) + (for `ObtainedFrom`) `SourceText` **up front**, so the Phase 4 community layer adds only rows and templates — never a production schema recreate.

**Tech Stack:** C# Unity export (`src/Assets/Editor/`), Python clean-build processor + repositories (`src/erenshor/`), Lua Scribunto modules + PortableInfobox templates (`wiki/modules/`, `wiki/templates/`), the `wiki-dev` Docker MediaWiki+Cargo harness, SQLite, pytest, golden baselines.

---

## Grounding (verified before planning)

- **Item-owned decision:** only `Item.lua` and `Character.lua` have `cargoStore` today (`wiki/modules/Erenshor/{Item,Character}.lua`). `Quest.lua`/`Zone.lua` do not and there is no Class template, so quest/zone/class-owned `ObtainedFrom` rows are impossible until Phase 5. Making `ObtainedFrom`/`UsedIn` item-owned makes Phase 3 fully harness-testable now.
- **Taxonomy is complete & deterministic.** `ObtainedFrom` SourceTypes: `drop, vendor, dialog, quest, craft, item_use, mining, fishing, item_bag, starting`. `UsedIn` UseTypes: `craft_material, quest_requirement, upgrade_material, blessing_removal_material`. Treasure hunting = the four `Lost Treasure (…)` **chest characters** carrying authored `loot_drops` (covered by `drop`, no special-casing). Wishing wells grant nothing (coordinate markers only).
- **Existing repos** already answer most reverse queries: `get_vendors_selling_item`, `get_characters_dropping_item` (`repositories/characters.py:262,311`), `get_item_drops`/`get_item_sources` (`repositories/items.py:528,568`), `get_quests_rewarding_item` (uses `quest_variants.item_on_complete_stable_key`, `repositories/quests.py:72`), `get_quests_requiring_item` (`:109`), `get_items_requiring_item` (`:233`), and Spawns reads `wiki_character_spawns` (`repositories/spawn_points.py:47`). New methods needed: dialog, craft-reward, mining, fishing, item_bag, starting, smithing special uses.
- **Code facts already extracted** (playtest `code_facts` table, values are comparison strings). The pins are the **playtest** renderings (the shipping build's renderings):
  - `auction.updateah_gates` → `item_level='>= 40'`, `item_value='<= 0'`
  - `auction.replacebag_gates` → `item_level='<= 0,> 39'`, `rare_reject_roll='< 19'`
  - `smithing.upgrade_ids` → `strings='31377423,46289586,2298018,2265228'`
  `auction.updateah_gates.item_level='>= 40'` is the listing skip branch (verified against `AuctionHouse.cs:626`: `if (itemByID.ItemLevel >= 40) continue;`, so items ≥40 are skipped and the auctionable predicate is `1 ≤ level ≤ 39`). `ReplaceBag:120` rejects `ItemLevel <= 0 || > 39` and `RareItem && Random(0,20) < 19`. The four smithing IDs are `items.id` values (TEXT), not stable keys: `31377423`=Mold: An Otherwordly Box, `46289586`=Planar Stone, `2298018`=Inert Diamond, `2265228`=Merging Vessel.
- **`Item.RareItem`** reaches raw export, clean `items.rare_item`, and sheets; the `Item` domain model and Lua data map declare it, but the item repository must select it before generated Lua receives its value (Task A6). `is_auctionable` remains a derived field for Task A5. **`SellValue`** is a derived export (0.65×`ItemValue`), not a game field; the auction gate uses `ItemValue`.
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
- Modify: `src/erenshor/application/processor/entities.py` (`process_classes` or a new `_process_class_starting_items`)
- Test: processor test asserting a known class has starting items keyed to valid item stable keys.

- [ ] **Step 1: Write the failing test** asserting `class_starting_items` rows exist and `item_stable_key` ∈ valid items.
- [ ] **Step 2:** Run; expect failure.
- [ ] **Step 3:** Add `CREATE TABLE class_starting_items (class_name TEXT, item_stable_key TEXT, sort_order INTEGER)` + `insert_class_starting_items`; in the processor, `_rows` from raw `ClassStartingItems`, `_filter_junction` on `ItemStableKey` against valid item keys, `_rename_cols`, insert.
- [ ] **Step 4:** `extract build`; run test. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pipeline): carry class starting items into the clean DB`

### Task A5: Derive `is_auctionable` from code facts (drift-gated)

**Files:**
- Create: `src/erenshor/application/processor/auction.py`
- Modify: `src/erenshor/application/processor/entities.py` (`process_items`)
- Test: `tests/unit/application/processor/test_auction.py`

- [ ] **Step 1: Write failing tests** for the pure predicate and the drift gate:

```python
import pytest
from erenshor.application.processor.auction import (
    EXPECTED_AUCTION_GATES, validate_auction_gates, derive_is_auctionable,
)

def test_predicate_truth_table():
    assert derive_is_auctionable(item_level=10, item_value=5, sim_players_cant_get=0) is True
    assert derive_is_auctionable(item_level=0,  item_value=5, sim_players_cant_get=0) is False   # level < 1
    assert derive_is_auctionable(item_level=40, item_value=5, sim_players_cant_get=0) is False   # level > 39
    assert derive_is_auctionable(item_level=10, item_value=0, sim_players_cant_get=0) is False   # value <= 0
    assert derive_is_auctionable(item_level=10, item_value=5, sim_players_cant_get=1) is False   # sim-locked

def test_drift_gate_hard_fails_on_changed_comparison():
    bad = dict(EXPECTED_AUCTION_GATES)
    bad[("auction.updateah_gates", "item_level")] = "< 50"
    with pytest.raises(ValueError, match="auction gate drift"):
        validate_auction_gates(bad)
```

- [ ] **Step 2:** Run; expect import failure.

- [ ] **Step 3:** Implement. The code facts are tripwires: pin the exact extracted comparison strings, hard-fail on drift, then apply the human-verified hardcoded predicate (`AuctionHouse.UpdateAH`/`ReplaceBag`).

```python
"""Derive the IsAuctionable item flag from auction code facts.

The hardcoded predicate is verified against AuctionHouse.cs (UpdateAH listing gate
+ ReplaceBag random-restock gate). The code_facts comparison strings are pinned as
tripwires: if the game changes a bound, validate_auction_gates hard-fails so the
predicate is re-derived rather than silently inverted.
"""
from __future__ import annotations

# code-fact: auction.updateah_gates
# code-fact: auction.replacebag_gates
# Pinned to the playtest (shipping) renderings.
EXPECTED_AUCTION_GATES: dict[tuple[str, str], str] = {
    ("auction.updateah_gates", "item_level"): ">= 40",   # listing skip: ItemLevel >= 40 (AuctionHouse.cs:626)
    ("auction.updateah_gates", "item_value"): "<= 0",    # listing purge: ItemValue <= 0 removed -> require > 0
    ("auction.replacebag_gates", "item_level"): "<= 0,> 39",  # restock reject: level <= 0 OR level > 39
}

def validate_auction_gates(code_facts: dict[tuple[str, str], str]) -> None:
    for key, expected in EXPECTED_AUCTION_GATES.items():
        actual = code_facts.get(key)
        if actual != expected:
            raise ValueError(
                f"auction gate drift: {key} expected {expected!r}, got {actual!r}. "
                "Re-derive IsAuctionable from AuctionHouse.cs (UpdateAH/ReplaceBag)."
            )

def derive_is_auctionable(item_level, item_value, sim_players_cant_get) -> bool:
    if sim_players_cant_get:
        return False
    if item_level is None or not (1 <= item_level <= 39):
        return False
    return item_value is not None and item_value > 0
```

In `process_items`, before `writer.insert_items(rows)`: load the gates from raw `code_facts`, `validate_auction_gates(...)`, then set `r["is_auctionable"] = int(derive_is_auctionable(r.get("item_level"), r.get("item_value"), r.get("sim_players_cant_get")))` for each row. Tag the call site `# code-fact: auction.updateah_gates` / `# code-fact: auction.replacebag_gates`.

- [ ] **Step 4:** Run the unit tests + `uv run erenshor -V playtest extract build`; spot-check:

```bash
sqlite3 variants/playtest/erenshor-playtest.sqlite
 "SELECT COUNT(*) FROM items WHERE is_auctionable=1"
```
Expected: a large but < total count.

- [ ] **Step 5: Commit** — `feat(pipeline): derive IsAuctionable from auction code facts`

### Task A6: Surface `is_auctionable` and complete item flag repository mapping

**Files:** `src/erenshor/domain/entities/item.py` + the item repository row→entity mapping.

- [x] `Item` declares `rare_item`.
- [ ] **Step 1:** Add `is_auctionable` after `rare_item`:

```python
    is_auctionable: int | None = Field(default=None, description="Derived: appears on the auction house (boolean)")
```

- [ ] **Step 2:** Select both `rare_item` and `is_auctionable` in the item repository, then add a unit test asserting fetched `Item` entities carry both flags.
- [ ] **Step 3:** Run the test. Expected: PASS.
- [ ] **Step 4: Commit** — `feat(pipeline): expose rare_item and is_auctionable on the Item entity`

### Task A7: Recapture golden baselines

- [ ] **Step 1:** `uv run erenshor -V playtest golden capture` (playtest = the shipping build in waiting; see `skill://refreshing-game-data` variant-safety rules — capture writes the shared `tests/golden/`, so this is only safe because playtest is the build we are cutting over to).
- [ ] **Step 2:** Review the diff: expect added `is_auctionable` and `class_starting_items`; `rare_item` already appears in the baseline. `code_facts.csv` shows the playtest renderings (`auction.updateah_gates.item_level='>= 40'`, `smithing.upgrade_ids='31377423,46289586,2298018,2265228'`).
- [ ] **Step 3:** `uv run pytest` green.
- [ ] **Step 4: Commit** — `test(pipeline): recapture golden baselines for item flags + class starting items`

---

## Sub-phase 3B — `ObtainedFrom` unified table (item-owned)

Outcome: a single `ObtainedFrom` Cargo table written from the item page, covering every deterministic source type. `Drops`/`ContainerDrops` keep working until 3E folds and deletes them.

### Task B1: `ItemObtainedFromStore` hidden owner (declares + stores `ObtainedFrom`)

**Files:**
- Create: `wiki/templates/ItemObtainedFromStore.wiki` (hidden store owner: declares + stores `ObtainedFrom`)
- Modify: `wiki-dev/smoke/cargo.py` (FIELDS/KEY/QUERY + loader/checker), `wiki-dev/cargo_check.py` (`CARGO_TABLES`, `CARGO_TEMPLATES_BY_TABLE`)

- [ ] **Step 1:** Reserved-word check (a keyword column silently no-ops the whole declare). Verify each proposed column name against SQL keywords before declaring: `ItemKey, SourceType, SourceKey, SourceText, Probability, IsGuaranteed, Quantity, SourceCondition, Origin`. `CONDITION` is a SQL keyword → rename to **`SourceCondition`**. Document in the template comment (like `CastRange`/`CharacterKey`).
- [ ] **Step 2:** Write `ItemObtainedFromStore.wiki` — the hidden owner that declares `ObtainedFrom` in `<noinclude>` and stores its rows from `<includeonly>` (Lua-backed `#cargo_store`, wired in B4). Declare the **final** Phase-4 schema up front — `SourceText` and `Origin` are nullable, so generated rows leave them null until Phase 4 adds the community row template:

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
Hidden store owner of the unified item-obtainability junction (one row per item × source), transcluded by the item page.
ItemKey is the obtained item's StableKey; SourceType ∈ drop|vendor|dialog|quest|craft|item_use|mining|fishing|item_bag|starting|community; SourceKey resolves by type (character/quest/item/zone/class StableKey, or null for free-text community rows) at display time; SourceText carries free-text community sources; Origin ∈ generated|community. The `Item` page transcludes this hidden owner, whose `<includeonly>` runs the Lua-backed `#cargo_store`; `Item` itself declares only the `Items` table.
</noinclude>
```

- [ ] **Step 3:** Add to `wiki-dev/smoke/cargo.py`: `CARGO_OBTAINED_FROM_FIELDS`, `OBTAINED_FROM_KEY = ("ItemKey", "SourceType", "SourceKey")`, `CARGO_OBTAINED_FROM_QUERY_FIELDS = ("_pageName=Page", "ItemKey", "SourceType", "SourceKey", "SourceText", "Probability", "IsGuaranteed", "Quantity", "SourceCondition", "Origin")`, plus `load_/check_cargo_obtained_from_rows` mirroring the ContainerDrops helpers. Register the table + template in `cargo_check.py`.
- [ ] **Step 4:** `import_pages.py` then `cargo_check.py`; expect the empty table to recreate cleanly.
- [ ] **Step 5: Commit** — `feat(wiki): declare the unified ObtainedFrom Cargo junction`

### Task B2: Repository methods for the missing sources

**Files:** `infrastructure/database/repositories/{characters,items,quests,zones,classes}.py` + their Protocols in `wiki_lua/items.py`. Test each with a known fixture key.

Add (one method + one test each; concrete SQL):
- [ ] **`get_characters_giving_item(item_key)`** — `character_dialogs WHERE give_item_stable_key = ?` → `(CharacterLink, condition)` where condition derives from `required_quest_stable_key` (quest-gate). SourceType `dialog`.
- [ ] **`get_recipes_rewarding_item(item_key)`** — `crafting_rewards WHERE reward_item_stable_key = ?` → `(ItemLink recipe, quantity)`. SourceType `craft`.
- [ ] **`get_mining_zones_for_item(item_key)`** — `mining_node_items JOIN mining_nodes` → distinct `(scene→ZoneLink, drop_chance)`. SourceType `mining`.
- [ ] **`get_fishing_waters_for_item(item_key)`** — `water_fishables JOIN waters` → `(ZoneLink, drop_chance, condition=type day/night)`. SourceType `fishing`.
- [ ] **`get_item_bag_zones_for_item(item_key)`** — `item_bags WHERE item_stable_key = ?` → distinct `(scene→ZoneLink)`. SourceType `item_bag`.
- [ ] **`get_classes_starting_with_item(item_key)`** — `class_starting_items WHERE item_stable_key = ?` → `ClassLink`. SourceType `starting`.
- [ ] **Vendor condition:** extend `get_vendors_selling_item` to also surface quest-unlock vendors via `character_vendor_quest_unlocks` with `SourceCondition` = "requires quest <name>".

World-point sources (`mining`/`fishing`/`item_bag`) carry the zone as `SourceKey`; dedup to one row per item×type×zone.

- [ ] **Commit per method or grouped logically** — `feat(pipeline): add <source> reverse-source repository query`

### Task B3: Python builder — `obtainedFrom` on the item data module

**Files:** `wiki_lua/items.py` (+ `SourceInfo` in `domain/value_objects/source_info.py`), test `tests/unit/application/wiki_lua/test_items.py`.

- [ ] **Step 1: Write failing tests** asserting a fixture item yields typed rows: a chest-dropped item → a `drop` row with the chest character key + probability; a fished item → a `fishing` row with a zone key + day/night condition; a starting item → a `starting` row with a class key; an offering-bag product → an `item_use` row.
- [ ] **Step 2:** Run; expect failure.
- [ ] **Step 3:** Add `_format_obtained_from(sources) -> list[LuaData]` building one dict per source `{type, sourceKey, probability, guaranteed, quantity, condition}` (omit nil/empty per `_put`), mirroring `_format_container_drops` (`items.py:373`). Wire it into `build_item_sources_by_item` (extend `SourceInfo` with the new lists) and emit `_put(row, "obtainedFrom", _format_obtained_from(sources))` in `_item_record`. Sort deterministically (type, then sourceKey).
- [ ] **Step 4:** Run tests; `uv run erenshor wiki generate-lua`; expect PASS.
- [ ] **Step 5: Commit** — `feat(wiki): build the item obtainedFrom source list in Lua data`

### Task B4: Lua store in the `ItemObtainedFromStore` owner

**Files:** `wiki/modules/Erenshor/Item.lua` (after `containerDropRows`, ~line 821), `wiki/templates/Item.wiki` (transclude the hidden owner), `wiki/templates/ItemObtainedFromStore.wiki`, `wiki/modules/Erenshor/Item/testcases.lua`.

- [ ] **Step 1: Write failing testcase** in `Item/testcases.lua`: `Item.cargoObtainedFromRows({ args = { stablekey = "item:<fixture>" } })` returns rows with `ItemKey`/`SourceType`/`SourceKey` set (mirror the `cargoContainerDropRows` testcase at `Item/testcases.lua:120`).
- [ ] **Step 2:** Add `obtainedFromRows(item)` (mirror `containerDropRows`, `Item.lua:805`): one `{ {"ItemKey", item.stableKey}, {"SourceType", src.type}, {"SourceKey", src.sourceKey}, {"SourceText", src.sourceText}, {"Probability", src.probability}, {"IsGuaranteed", src.guaranteed == true}, {"Quantity", src.quantity}, {"SourceCondition", src.condition}, {"Origin", "generated"} }` per entry in `item.obtainedFrom` (generated rows always carry `Origin="generated"`, `SourceText=nil`). Expose `p.cargoObtainedFromStore(frame)` — resolves the item by `stablekey` and runs the `Cargo.store("ObtainedFrom", fields)` loop — as the entrypoint the hidden `ItemObtainedFromStore` owner invokes from its `<includeonly>`.
- [ ] **Step 3:** In `Item.wiki` `<includeonly>`, transclude `{{ItemObtainedFromStore|stablekey={{{stablekey|}}}}}` so each item page renders the hidden owner, whose `<includeonly>` stores the `ObtainedFrom` rows. `Item` keeps `#cargo_declare:Items` and stores only its own `Items` row — no `#cargo_attach`, no attach-trick, since each table has its own declaring+storing owner.
- [ ] **Step 4:** `import_pages.py` → `smoke_test.py` → `cargo_check.py`. Expect ObtainedFrom rows for fixture item pages.
- [ ] **Step 5: Commit** — `feat(wiki): store item ObtainedFrom rows from the item page`

### Task B5: Fixtures + smoke expectations

**Files:** `wiki-dev/fixtures/cargo_obtained_from.tsv`, an item fixture page exercising ≥3 source types, `cargo_check.py` validation wiring.

- [ ] **Step 1:** Add a fixture page (e.g. extend `Braxonian Fossil`/a chest-dropped item) and the TSV with expected rows (chest `drop`, `item_use`, `starting`).
- [ ] **Step 2:** `cargo_check.py` green for ObtainedFrom.
- [ ] **Step 3: Commit** — `test(wiki): cover ObtainedFrom rows on the local harness`

---

## Sub-phase 3C — `UsedIn` unified table (item-owned)

Outcome: `UsedIn` written from the item page for `craft_material`, `quest_requirement`, `upgrade_material`, and `blessing_removal_material`.

### Task C1: `ItemUsedInStore` hidden owner (declares + stores `UsedIn`)

**Files:** `wiki/templates/ItemUsedInStore.wiki`, `wiki-dev/smoke/cargo.py`, `cargo_check.py`.

- [ ] **Step 1:** Columns `ItemKey, UseType, TargetKey, Quantity, Slot` — reserved-word check (`SLOT` is safe; confirm). Write the hidden owner `ItemUsedInStore.wiki` (declares + stores `UsedIn`) mirroring `ItemObtainedFromStore.wiki`. `UseType ∈ craft_material|quest_requirement|upgrade_material|blessing_removal_material`. The Merging Vessel forge/merge mechanic (`2265228`) is not emitted in Phase 3.
- [ ] **Step 2:** smoke fields/key (`("ItemKey","UseType","TargetKey")`) + checker; register in `cargo_check.py`.
- [ ] **Step 3:** recreate clean.
- [ ] **Step 4: Commit** — `feat(wiki): declare the unified UsedIn Cargo junction`

### Task C2: smithing special-use materials via the `smithing.upgrade_ids` code fact

**Files:** new repo method `get_item_smithing_special_uses(item_key)` + a small code-fact-backed resolver; tests.

- [ ] **Step 1: Write failing tests:** (a) the resolver reads `code_facts['smithing.upgrade_ids']` (CSV of `items.id`) and validates the full pinned set `31377423,46289586,2298018,2265228`; (b) it maps `46289586 → item:ore - planar stone` as `UseType='upgrade_material'`; (c) it maps `2298018 → item:template - inert diamond` as `UseType='blessing_removal_material'`; (d) it explicitly does **not** emit a row for `2265228 → item:template - merging vessel`; (e) the drift gate hard-fails if the fact is absent or the ID set differs.
- [ ] **Step 2:** Implement a resolver that reads `smithing.upgrade_ids` from the clean `code_facts`, splits the CSV, joins `items.id`, validates the full four-ID set, then classifies by game semantics from `Smithing.Combine`: `31377423` + `46289586` → `upgrade_material`; `2298018` → `blessing_removal_material`; `2265228` → deferred forge/merge mechanic, no `UsedIn` row in Phase 3. Tag `# code-fact: smithing.upgrade_ids`. The fact name is historical: the matcher is `string_constants`, so it bundles heterogeneous string literals from `Smithing.Combine`; consumers must classify, not bulk-map.
- [ ] **Step 3:** `craft_material` from `crafting_recipes WHERE material_item_stable_key = ?` → `(recipe ItemLink, quantity, slot)`; `quest_requirement` reuses `get_quests_requiring_item`.
- [ ] **Step 4:** tests green.
- [ ] **Step 5: Commit** — `feat(pipeline): resolve UsedIn rows for smithing special materials via code facts`

### Task C3: Python builder — `usedIn` on the item data module

- [ ] Mirror B3: `_format_used_in(sources)` → `usedIn` list `{type, targetKey, quantity, slot}`; extend `SourceInfo`/`build_item_sources_by_item`; `_put(row, "usedIn", ...)`. Tests for each emitted UseType (`craft_material`, `quest_requirement`, `upgrade_material`, `blessing_removal_material`). **Commit** — `feat(wiki): build the item usedIn list in Lua data`

### Task C4: Lua store in the `ItemUsedInStore` owner

- [ ] Add `usedInRows(item)` + `p.cargoUsedInStore` + store loop in `Item.lua` (mirror B4). Transclude `{{ItemUsedInStore|stablekey=…}}` from `Item.wiki` `<includeonly>` alongside `{{ItemObtainedFromStore}}` — no attach-trick. `Item/testcases.lua` for the store. Verify via `cargo_check.py`. **Commit** — `feat(wiki): store item UsedIn rows via the ItemUsedInStore owner`

### Task C5: Fixtures + smoke

- [ ] `wiki-dev/fixtures/cargo_used_in.tsv` + fixtures for Planar Stone → `upgrade_material`, Inert Diamond → `blessing_removal_material`, and a normal ingredient item → `craft_material`; `cargo_check.py` green. **Commit** — `test(wiki): cover UsedIn rows on the local harness`

---

## Sub-phase 3D — Character junctions

Outcome: `Spawns` + `CharacterAbilities` written from the character page (Character.lua already has `cargoStore`).

### Task D1-D3: `Spawns`

- [ ] **D1:** `wiki/templates/CharacterSpawnsStore.wiki` — hidden owner declaring + storing `Spawns`: `CharacterKey, Zone, Scene, X, Y, Z, SpawnChance, NightSpawn, SpawnUponQuestComplete, LevelMod, RareNpcChance, SpawnType, Origin` (reserved-word check on `Zone`/`Scene`; both safe). `Origin` declared up front so Phase 4 adds only `{{SpawnPoint}}` rows, no schema recreate. smoke + cargo_check wiring. **Commit** — `feat(wiki): declare the Spawns Cargo junction`
- [ ] **D2:** Python builder `spawns` on the character data module from `spawn_points.py` (`wiki_character_spawns`, which filters `character_spawns` to `is_wiki_generated` and already expands `character_chained_spawns`). **Fold treasure-chest possible locations in here**: for each of the four `Lost Treasure (…)` chest characters, join `treasure_chest_possible_spawns` × `treasure_locations` and emit one row per pickable location with `SpawnType='treasure_chest'`, `SpawnChance=nil` (the game's per-location chest odds are not exported), coordinates from the location; without this, a treasure-hunting item's `ObtainedFrom` `drop` row resolves to a chest character whose page shows no spawn locations. Generated rows carry `Origin='generated'`. Tests cover a chest character yielding `treasure_chest` rows. **Commit** — `feat(wiki): build character spawns list in Lua data`
- [ ] **D3:** `spawnRows(character)` + store entrypoint in `Character.lua`; `Character.wiki` `<includeonly>` transcludes `{{CharacterSpawnsStore|stablekey=…}}` (no attach-trick — `Character` declares only `Characters`; each junction has its own hidden owner). `Character/testcases.lua`. `cargo_check.py`. **Commit** — `feat(wiki): store character Spawns rows`

### Task D4-D6: `CharacterAbilities`

- [ ] **D4:** `wiki/templates/CharacterAbilitiesStore.wiki` — hidden owner declaring + storing `CharacterAbilities`: `CharacterKey, AbilityKey, Usage`. smoke + cargo_check. **Commit** — `feat(wiki): declare the CharacterAbilities Cargo junction`
- [ ] **D5:** Python builder unioning `character_attack_spells` + `character_buff_spells` + `character_heal_spells` + `character_cc_spells` + `character_taunt_spells` + `character_group_heal_spells` + `character_death_shouts` + `character_attack_skills` (currently 0 rows but include for completeness), each tagged with its `Usage` (attack/buff/heal/cc/taunt/group_heal/death_shout). Tests. **Commit** — `feat(wiki): build character abilities list in Lua data`
- [ ] **D6:** `characterAbilityRows` + store entrypoint in `Character.lua`; `Character.wiki` transcludes `{{CharacterAbilitiesStore|stablekey=…}}` (no attach-trick). `Character/testcases.lua`. `cargo_check.py`. **Commit** — `feat(wiki): store CharacterAbilities rows`
- [ ] **D7:** Fixtures `wiki-dev/fixtures/cargo_spawns.tsv`, `cargo_character_abilities.tsv` + a multi-spawn / multi-ability character fixture; `cargo_check.py` green. **Commit** — `test(wiki): cover Spawns and CharacterAbilities on the harness`

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
- **Code-fact boundary:** every constant (auction bounds, smithing string IDs) is consumed from `code_facts` with a drift gate + `# code-fact:` tag; none transcribed from `.cs`. Pins are the **playtest** renderings (the shipping build's); `auction.updateah_gates.item_level` pins `'>= 40'`, and `smithing.upgrade_ids` pins the full four-ID set while classifying only the upgrade/blessing-removal IDs into Phase 3 `UsedIn` rows.
- **Reserved words:** `Condition`→`SourceCondition`; `CharacterKey` retained; re-check each new column at declare time (a keyword silently no-ops the table).
- **Type consistency:** `obtainedFrom`/`usedIn` Lua field names, `SourceType`/`UseType` literals, and the smoke `*_KEY` tuples are used identically across B/C/E.
- **Deferred paths:** enumerated in SP1 and retained in planning docs, none dropped silently.
