---
title: Wiki Cargo Phase 3 — Item Relationships, Flags & Character Junctions
type: plan
status: active
created: 2026-06-23
parent: 2026-06-04-wiki-cargo-data-architecture
---

# Wiki Cargo Phase 3 — Item Relationships, Flags & Character Junctions

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Read `skill://wiki-templates`, `skill://unity-export-system`, `skill://code-facts`, and `skill://refreshing-game-data` before starting.

**Goal:** Build the unified, item-owned `ObtainedFrom` / `UsedIn` Cargo relationship tables plus the `IsRare` / `IsAuctionable` item flags and the `CharacterAbilities` / `Spawns` junctions, then cut reverse displays over to Cargo queries — all on the local `wiki-dev` harness, with the live wiki untouched (production cutover is Phase 7).

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
- **`Item.RareItem`** exists (`Item.cs:210`) but is not exported. **`SellValue`** is a derived export (0.65×`ItemValue`), not a game field; the auction gate uses `ItemValue`.
- **Attach budget:** the Item template currently does `#cargo_declare:Items` + `#cargo_attach:ContainerDrops` (within the wiki.gg 1-declare+1-attach budget). After folding `ContainerDrops`→`ObtainedFrom` and adding `UsedIn`, the item page writes `Items` + `ObtainedFrom` + `UsedIn` = 3 tables → the **attach-trick** is required (declare-only owner templates + a transcluded zero-output attach helper), mirroring `wiki/templates/ContainerDrops.wiki`. **The local harness cannot validate the budget** — `wiki-dev/Dockerfile` clones stock upstream Cargo, not wiki.gg's LIBRARIAN fork, so budget acceptance is probed live once before Phase 3 (see Pre-Phase-3 gate below).

## File map (created / modified)

- C# export: `src/Assets/Editor/Database/ItemRecord.cs`, `ClassStartingItemRecord.cs` (new); `src/Assets/Editor/ExportSystem/AssetScanner/Listener/ItemListener.cs`, `ClassStartingItemsListener.cs` (new); `src/Assets/Editor/ExportBatch.cs`.
- Code facts: `src/tools/CodeFacts/specs/erenshor-facts.json` (only if a drift fix or a new `smithing`/`auction` spec is needed — see 3C2).
- Python build: `src/erenshor/application/processor/writer.py` (schemas), `processor/entities.py` (process_items + class_starting_items), `processor/auction.py` (new, `is_auctionable`), `domain/entities/item.py`, the repositories under `infrastructure/database/repositories/`.
- Lua gen: `src/erenshor/application/wiki_lua/items.py`, `characters.py`, new builders; `domain/value_objects/source_info.py`.
- Lua modules: `wiki/modules/Erenshor/Item.lua`, `Character.lua`.
- Templates: `wiki/templates/Item.wiki`, new `ObtainedFrom.wiki`, `UsedIn.wiki`, `Spawns.wiki`, `CharacterAbilities.wiki`; delete `Drops.wiki`, `ContainerDrops.wiki` at the end of 3E.
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
```

Per-module Lua assertions live in `wiki/modules/Erenshor/<Type>/testcases.lua` and are exercised by the harness render; Cargo row shape is asserted by `cargo_check.py` against `wiki-dev/fixtures/cargo_*.tsv`.

---

## Sub-phase 3A — Exports & item flags

Outcome: clean `items` carries `rare_item` + `is_auctionable`; `class_starting_items` exists; golden recaptured. No wiki changes yet.

### Task A1: Export `Item.RareItem`

**Files:**
- Modify: `src/Assets/Editor/Database/ItemRecord.cs` (Economy/Inventory block, near line 85)
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/Listener/ItemListener.cs:209` (Economy block of `CreateItemRecord`)

- [ ] **Step 1:** Add the column to `ItemRecord` after `NoTradeNoDestroy`:

```csharp
    public bool NoTradeNoDestroy { get; set; }
    public bool RareItem { get; set; } // Authored "prized item" flag (Item.RareItem); drives auction ×20 and the rare draw soft-rejec
```

- [ ] **Step 2:** Map it in `CreateItemRecord` after `NoTradeNoDestroy = item.NoTradeNoDestroy,`:

```csharp
            NoTradeNoDestroy = item.NoTradeNoDestroy,
            RareItem = item.RareItem,
```

- [ ] **Step 3:** Re-export and confirm the raw column is populated:

```bash
uv run erenshor -V playtest extract export
sqlite3 variants/playtest/erenshor-playtest-raw.sqlite
  "SELECT COUNT(*) FROM Items WHERE RareItem=1"
```
Expected: a non-zero count (rare items exist).

- [ ] **Step 4: Commit** — `feat(export): export the authored Item.RareItem flag`

### Task A2: Carry `rare_item` into the clean `items` table

**Files:**
- Modify: `src/erenshor/application/processor/writer.py` (CREATE TABLE items, near line 345)
- Test: `tests/unit/application/processor/test_entities.py` (or the existing items-processor test)

- [ ] **Step 1: Write the failing test** — assert the clean column exists and a known rare item is flagged:

```python
def test_process_items_carries_rare_item(clean_db):
    row = clean_db.execute(
        "SELECT rare_item FROM items WHERE stable_key = :k", {"k": KNOWN_RARE_ITEM_KEY}
    ).fetchone()
    assert row["rare_item"] == 1
```

- [ ] **Step 2:** Run it; expect failure (`no such column: rare_item`).

- [ ] **Step 3:** Add `rare_item INTEGER,` and `is_auctionable INTEGER,` to the `CREATE TABLE items (...)` body in `writer.py` (group with the other boolean flags). `process_items` already does `_rename_cols` PascalCase→snake, so the exported `RareItem` flows to `rare_item` automatically once the column exists; `_insert` is column-name keyed.

- [ ] **Step 4:** `uv run erenshor extract build` then run the test. Expected: PASS.

- [ ] **Step 5: Commit** — `feat(pipeline): carry the rare_item flag into the clean items table`

### Task A3: Export `class_starting_items`

**Files:**
- Create: `src/Assets/Editor/Database/ClassStartingItemRecord.cs`
- Create: `src/Assets/Editor/ExportSystem/AssetScanner/Listener/ClassStartingItemsListener.cs`
- Modify: `src/Assets/Editor/ExportBatch.cs` (component-listener block, ~lines 307-329)

- [ ] **Step 1:** Record class (junction; no single PK — mirror `QuestRequiredItemRecord.cs`):

```csharp
#nullable enable
using SQLite;

[Table("ClassStartingItems")]
public class ClassStartingItemRecord
{
    public string ClassName { get; set; } = string.Empty;    // 'Arcanist','Paladin','Duelist','Druid','Stormcaller','Reaver'
    public string ItemStableKey { get; set; } = string.Empty; // StableKeyGenerator.ForItem(item)
    public int SortOrder { get; set; }                         // 0-based position within the class lis
}
```

- [ ] **Step 2:** Listener (CharSelectManager is a MonoBehaviour → component listener). Field→ClassName mapping is verified: `WarStart`→Paladin, `DueslistStart`→Duelist (game-side typo), the rest match their names.

```csharp
#nullable enable
using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class ClassStartingItemsListener : IAssetScanListener<CharSelectManager>
{
    private readonly SQLiteConnection _db;
    private readonly List<ClassStartingItemRecord> _records = new();
    public ClassStartingItemsListener(SQLiteConnection db) => _db = db;

    public void OnAssetFound(CharSelectManager m)
    {
        Add("Arcanist", m.ArcanistStart);
        Add("Paladin", m.WarStart);
        Add("Duelist", m.DueslistStart);
        Add("Druid", m.DruidStart);
        Add("Stormcaller", m.StormStart);
        Add("Reaver", m.ReaverStart);
    }

    private void Add(string className, List<Item> items)
    {
        if (items == null) return;
        for (int i = 0; i < items.Count; i++)
        {
            var item = items[i];
            if (item == null) continue;
            _records.Add(new ClassStartingItemRecord
            {
                ClassName = className,
                ItemStableKey = StableKeyGenerator.ForItem(item),
                SortOrder = i,
            });
        }
    }

    public void OnScanFinished()
    {
        _db.CreateTable<ClassStartingItemRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<ClassStartingItemRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }
}
```

- [ ] **Step 3:** Register in `ExportBatch.cs`, in the `RegisterComponentListener` block:

```csharp
["classstartingitems"] = () => scanner.RegisterComponentListener(new ClassStartingItemsListener(db)),
```

- [ ] **Step 4:** Re-export, confirm rows per class:

```bash
uv run erenshor -V playtest extract export
sqlite3 variants/playtest/erenshor-playtest-raw.sqlite
  "SELECT ClassName, COUNT(*) FROM ClassStartingItems GROUP BY ClassName"
```
Expected: six rows, one per class, each with ≥1 item.

- [ ] **Step 5: Commit** — `feat(export): export per-class starting items from CharSelectManager`

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

### Task A6: Surface the flags on the `Item` domain entity

**Files:** `src/erenshor/domain/entities/item.py` + the item repository row→entity mapping.

- [ ] **Step 1:** Add fields after `no_trade_no_destroy`:

```python
    rare_item: int | None = Field(default=None, description="Authored prized-item flag (boolean)")
    is_auctionable: int | None = Field(default=None, description="Derived: appears on the auction house (boolean)")
```

- [ ] **Step 2:** Confirm the repository `SELECT *`/mapping carries the new columns (Pydantic ignores extras only if not declared — declared here, so they bind). Add a unit test asserting a fetched `Item` has `rare_item`/`is_auctionable` set.
- [ ] **Step 3:** Run the test. Expected: PASS.
- [ ] **Step 4: Commit** — `feat(pipeline): expose rare_item and is_auctionable on the Item entity`

### Task A7: Recapture golden baselines

- [ ] **Step 1:** `uv run erenshor -V playtest golden capture` (playtest = the shipping build in waiting; see `skill://refreshing-game-data` variant-safety rules — capture writes the shared `tests/golden/`, so this is only safe because playtest is the build we are cutting over to).
- [ ] **Step 2:** Review the diff in `tests/golden/`: expect only added `rare_item`/`is_auctionable` columns and the new `class_starting_items` rows; `code_facts.csv` shows the playtest renderings (`auction.updateah_gates.item_level='>= 40'`, `smithing.upgrade_ids='31377423,46289586,2298018,2265228'`).
- [ ] **Step 3:** `uv run pytest` green.
- [ ] **Step 4: Commit** — `test(pipeline): recapture golden baselines for item flags + class starting items`

---

## Sub-phase 3B — `ObtainedFrom` unified table (item-owned)

Outcome: a single `ObtainedFrom` Cargo table written from the item page, covering every deterministic source type. `Drops`/`ContainerDrops` keep working until 3E folds and deletes them.

### Task B1: Declare-only `ObtainedFrom` table + harness wiring

**Files:**
- Create: `wiki/templates/ObtainedFrom.wiki` (mirror `wiki/templates/ContainerDrops.wiki`)
- Modify: `wiki-dev/smoke/cargo.py` (FIELDS/KEY/QUERY + loader/checker), `wiki-dev/cargo_check.py` (`CARGO_TABLES`, `CARGO_TEMPLATES_BY_TABLE`)

- [ ] **Step 1:** Reserved-word check (a keyword column silently no-ops the whole declare). Verify each proposed column name against SQL keywords before declaring: `ItemKey, SourceType, SourceKey, SourceText, Probability, IsGuaranteed, Quantity, SourceCondition, Origin`. `CONDITION` is a SQL keyword → rename to **`SourceCondition`**. Document in the template comment (like `CastRange`/`CharacterKey`).
- [ ] **Step 2:** Write `ObtainedFrom.wiki` (declare-only owner; stores nothing). Declare the **final** Phase-4 schema up front — `SourceText` and `Origin` are nullable, so generated rows simply leave them null until Phase 4 adds the community row template:

```wikitext
<includeonly></includeonly><noinclude>{{#cargo_declare:_table=ObtainedFrom
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
Declare-only owner of the unified item-obtainability junction (one row per item × source).
ItemKey is the obtained item's StableKey; SourceType ∈ drop|vendor|dialog|quest|craft|item_use|mining|fishing|item_bag|starting|community; SourceKey resolves by type (character/quest/item/zone/class StableKey, or null for free-text community rows) at display time; SourceText carries free-text community sources; Origin ∈ generated|community. Rows are written by {{tl|Item}} via the attach trick; this template stores nothing.
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

### Task B4: Lua store + Item template attach

**Files:** `wiki/modules/Erenshor/Item.lua` (after `containerDropRows`, ~line 821), `wiki/templates/Item.wiki` (attach), `wiki/modules/Erenshor/Item/testcases.lua`.

- [ ] **Step 1: Write failing testcase** in `Item/testcases.lua`: `Item.cargoObtainedFromRows({ args = { stablekey = "item:<fixture>" } })` returns rows with `ItemKey`/`SourceType`/`SourceKey` set (mirror the `cargoContainerDropRows` testcase at `Item/testcases.lua:120`).
- [ ] **Step 2:** Add `obtainedFromRows(item)` (mirror `containerDropRows`, `Item.lua:805`): one `{ {"ItemKey", item.stableKey}, {"SourceType", src.type}, {"SourceKey", src.sourceKey}, {"SourceText", src.sourceText}, {"Probability", src.probability}, {"IsGuaranteed", src.guaranteed == true}, {"Quantity", src.quantity}, {"SourceCondition", src.condition}, {"Origin", "generated"} }` per entry in `item.obtainedFrom` (generated rows always carry `Origin="generated"`, `SourceText=nil`). Add `p.cargoObtainedFromRows(frame)` and a `Cargo.store("ObtainedFrom", fields)` loop in `p.cargoStore`.
- [ ] **Step 3:** In `Item.wiki` `<noinclude>`, attach the table. Item now writes Items + ContainerDrops + ObtainedFrom = 3 tables → apply the **attach-trick**: keep `#cargo_declare:Items`, transclude the declare-only `{{ObtainedFrom}}` and `{{ContainerDrops}}` owners, and `#cargo_attach` only what the budget allows directly; route the overflow through a zero-output attach helper. (3E removes ContainerDrops, returning to Items + ObtainedFrom + UsedIn.)
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

### Task C1: Declare-only `UsedIn` table + harness wiring

**Files:** `wiki/templates/UsedIn.wiki`, `wiki-dev/smoke/cargo.py`, `cargo_check.py`.

- [ ] **Step 1:** Columns `ItemKey, UseType, TargetKey, Quantity, Slot` — reserved-word check (`SLOT` is safe; confirm). Write the declare-only owner mirroring `ObtainedFrom.wiki`. `UseType ∈ craft_material|quest_requirement|upgrade_material|blessing_removal_material`. The Merging Vessel forge/merge mechanic (`2265228`) is not emitted in Phase 3.
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

### Task C4: Lua store + attach-trick (Item → 3 tables)

- [ ] Add `usedInRows(item)` + `p.cargoUsedInRows` + store loop in `Item.lua` (mirror B4). Attach `UsedIn` in `Item.wiki` via the attach-trick alongside `ObtainedFrom`. `Item/testcases.lua` for `cargoUsedInRows`. Verify via `cargo_check.py`. **Commit** — `feat(wiki): store item UsedIn rows from the item page`

### Task C5: Fixtures + smoke

- [ ] `wiki-dev/fixtures/cargo_used_in.tsv` + fixtures for Planar Stone → `upgrade_material`, Inert Diamond → `blessing_removal_material`, and a normal ingredient item → `craft_material`; `cargo_check.py` green. **Commit** — `test(wiki): cover UsedIn rows on the local harness`

---

## Sub-phase 3D — Character junctions

Outcome: `Spawns` + `CharacterAbilities` written from the character page (Character.lua already has `cargoStore`).

### Task D1-D3: `Spawns`

- [ ] **D1:** `wiki/templates/Spawns.wiki` declare-only: `CharacterKey, Zone, Scene, X, Y, Z, SpawnChance, NightSpawn, SpawnUponQuestComplete, LevelMod, RareNpcChance, SpawnType, Origin` (reserved-word check on `Zone`/`Scene`; both safe). `Origin` declared up front so Phase 4 adds only `{{SpawnPoint}}` rows, no schema recreate. smoke + cargo_check wiring. **Commit** — `feat(wiki): declare the Spawns Cargo junction`
- [ ] **D2:** Python builder `spawns` on the character data module from `spawn_points.py` (`wiki_character_spawns`, which filters `character_spawns` to `is_wiki_generated` and already expands `character_chained_spawns`). **Fold treasure-chest possible locations in here**: for each of the four `Lost Treasure (…)` chest characters, join `treasure_chest_possible_spawns` × `treasure_locations` and emit one row per pickable location with `SpawnType='treasure_chest'`, `SpawnChance=nil` (the game's per-location chest odds are not exported), coordinates from the location; without this, a treasure-hunting item's `ObtainedFrom` `drop` row resolves to a chest character whose page shows no spawn locations. Generated rows carry `Origin='generated'`. Tests cover a chest character yielding `treasure_chest` rows. **Commit** — `feat(wiki): build character spawns list in Lua data`
- [ ] **D3:** `spawnRows(character)` + store in `Character.lua` + attach in `Character.wiki` (character now declares Characters + attaches Drops + Spawns → attach-trick; Drops is removed in 3E, leaving Characters + Spawns + CharacterAbilities). `Character/testcases.lua`. `cargo_check.py`. **Commit** — `feat(wiki): store character Spawns rows`

### Task D4-D6: `CharacterAbilities`

- [ ] **D4:** `wiki/templates/CharacterAbilities.wiki` declare-only: `CharacterKey, AbilityKey, Usage`. smoke + cargo_check. **Commit** — `feat(wiki): declare the CharacterAbilities Cargo junction`
- [ ] **D5:** Python builder unioning `character_attack_spells` + `character_buff_spells` + `character_heal_spells` + `character_cc_spells` + `character_taunt_spells` + `character_group_heal_spells` + `character_death_shouts` + `character_attack_skills` (currently 0 rows but include for completeness), each tagged with its `Usage` (attack/buff/heal/cc/taunt/group_heal/death_shout). Tests. **Commit** — `feat(wiki): build character abilities list in Lua data`
- [ ] **D6:** `characterAbilityRows` + store + attach (attach-trick) in `Character.lua`/`Character.wiki`. `Character/testcases.lua`. `cargo_check.py`. **Commit** — `feat(wiki): store CharacterAbilities rows`
- [ ] **D7:** Fixtures `wiki-dev/fixtures/cargo_spawns.tsv`, `cargo_character_abilities.tsv` + a multi-spawn / multi-ability character fixture; `cargo_check.py` green. **Commit** — `test(wiki): cover Spawns and CharacterAbilities on the harness`

---

## Sub-phase 3E — Reverse-query cutover, fold/delete, freshness

Outcome: reverse displays read Cargo; `Drops`/`ContainerDrops` are gone; freshness handles item-ownership.

### Task E1: Fold `drop` + delete `Drops`

- [ ] Confirm every `Drops` fact is reproduced as an `ObtainedFrom` `drop` row (item-owned) — write a parity test comparing the old `Drops` expectations against `ObtainedFrom WHERE SourceType='drop'`. Then remove `dropCargoRows`/`Drops` store from `Character.lua`, delete `wiki/templates/Drops.wiki`, and remove the `Drops` entries from `smoke/cargo.py` + `cargo_check.py`. **Commit** — `refactor(wiki): fold character drops into item-owned ObtainedFrom`

### Task E2: Fold `item_use` + delete `ContainerDrops`

- [ ] Same parity check for `ContainerDrops` → `ObtainedFrom WHERE SourceType='item_use'`; remove `containerDropRows`/store from `Item.lua`, delete `wiki/templates/ContainerDrops.wiki`, drop the smoke/cargo_check entries. Item template now: declare Items + attach ObtainedFrom + UsedIn. **Commit** — `refactor(wiki): fold container drops into item-owned ObtainedFrom`

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

## Pre-Phase-3 gate — live storage-shape probe

Status: a recreate-capable main-account bot password can drive `edit`, `delete`,
`recreatecargodata`, and `deletecargodata` on the live wiki; `WoWBot` still lacks
`delete` and `recreatecargodata`, so production automation cannot assume those rights.

Live probes validate two viable 3-table storage shapes on wiki.gg:

- **Direct multi-attach:** one template declared table A, directly attached tables B/C,
  and stored rows into all three tables from one sandbox page.
- **Nested storage templates:** the main template declared/stored table A and
  transcluded hidden B/C storage templates, each declaring/storing exactly one table;
  the sandbox page stored rows into all three tables.

Use the nested storage-template shape for Phase 3. It follows Cargo's documented
one-table-per-storing-template model, keeps `Special:CargoTables` ownership clear, and
does not depend on helper attach behavior or multi-attach tolerance.

Recreate and repopulation are separate steps. `action=cargorecreatetables` succeeds
for the toy templates, but it clears rows; `action=purge&forcelinkupdate=1` alone did
not repopulate them. `action=cargorecreatedata` repopulated all three nested-template
tables when called per owning template/table. Phase 7 must therefore recreate schemas
first, then run data recreation for each owning storage template/table, or document the
equivalent admin-run recreate + repopulate runbook.

---

## Self-review

- **Spec coverage (§ of `2026-06-04-wiki-cargo-data-architecture.md`):** §7.1 IsAuctionable/IsRare → A5/A6; §8 ObtainedFrom → 3B; §8 UsedIn → 3C; §8 Spawns/CharacterAbilities → 3D; §8.1 reverse-query rendering + drop denormalized arrays → E3; §10 freshness → E4; item→ability scalar columns → already shipped in Phase 2 (excluded). `class_starting_items` `starting` source → A3/A4 + B2/B3.
- **Ownership trap:** resolved by item-owning ObtainedFrom/UsedIn; quest/zone/class need no Cargo template in Phase 3.
- **Code-fact boundary:** every constant (auction bounds, smithing string IDs) is consumed from `code_facts` with a drift gate + `# code-fact:` tag; none transcribed from `.cs`. Pins are the **playtest** renderings (the shipping build's); `auction.updateah_gates.item_level` pins `'>= 40'`, and `smithing.upgrade_ids` pins the full four-ID set while classifying only the upgrade/blessing-removal IDs into Phase 3 `UsedIn` rows.
- **Reserved words:** `Condition`→`SourceCondition`; `CharacterKey` retained; re-check each new column at declare time (a keyword silently no-ops the table).
- **Type consistency:** `obtainedFrom`/`usedIn` Lua field names, `SourceType`/`UseType` literals, and the smoke `*_KEY` tuples are used identically across B/C/E.
- **Deferred paths:** enumerated in SP1 and retained in planning docs, none dropped silently.
