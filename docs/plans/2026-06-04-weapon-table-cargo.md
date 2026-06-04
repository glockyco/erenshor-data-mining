# Weapon Cargo Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate the `Weapons` overview table from the repo-owned Cargo item rows instead of hand-maintained page wikitext.

**Architecture:** Reuse the completed `ArmorTable` Cargo pattern. `Template:WeaponTable` queries `Items` where `Type="Weapon"` and delegates one row at a time to `Template:WeaponTable/Row`; `Module:Erenshor/Item` stores normal-quality stats, weapon subtype (`WeaponType`), weapon damage/delay, generated notes, class links, and image/page values into Cargo. `Template:Item` is the source of truth for the `Items` Cargo schema; `Template:Item/CargoDeclare` is documentation only and must not be treated as the declaration source.

**Tech Stack:** MediaWiki templates, Cargo, Lua item data, local `wiki-dev` MediaWiki/Scribunto/Cargo smoke harness, pytest.

---

### Task 1: Add the WeaponTable templates

**Files:**
- Create: `wiki/templates/WeaponTable.wiki`
- Create: `wiki/templates/WeaponTable/Row.wiki`
- Test fixture: `wiki-dev/fixtures/pages/Cargo_WeaponTable_Smoke.wiki`
- Test expectations: `wiki-dev/fixtures/smoke.tsv`

- [x] **Step 1: Write the failing smoke fixture**

Create `wiki-dev/fixtures/pages/Cargo_WeaponTable_Smoke.wiki` with:

```wiki
{{WeaponTable}}
```

Append smoke expectations for the fixture page:

```tsv
Cargo WeaponTable Smoke	Ember Longsword
Cargo WeaponTable Smoke	OneHandMelee
Cargo WeaponTable Smoke	20% on attack
Cargo WeaponTable Smoke	Paladin
Cargo WeaponTable Smoke	Reaver
```

- [x] **Step 2: Run the smoke to verify RED**

Run:

```bash
uv run python wiki-dev/import_pages.py && uv run python wiki-dev/smoke_test.py
```

Expected: FAIL because `Template:WeaponTable` does not exist.

- [x] **Step 3: Add `Template:WeaponTable`**

Create `wiki/templates/WeaponTable.wiki`:

```wiki
<includeonly>{| class="wikitable datatable compact hover" style="font-size: 14px; text-align: center;"
!Weapon
!Slot
!Type
!class="numeric"|Level
!class="numeric"|Damage
!class="numeric"|Delay
!class="numeric"|HP
!class="numeric"|Mana
!class="numeric"|AC
!class="numeric"|Str
!class="numeric"|End
!class="numeric"|Dex
!class="numeric"|Agi
!class="numeric"|Int
!class="numeric"|Wis
!class="numeric"|Cha
!class="numeric"|Res
!class="numeric"|MR
!class="numeric"|PR
!class="numeric"|ER
!class="numeric"|VR
!Notes
![[Classes]]
{{#cargo_query:
tables=Items
|fields=Page,Name,Image,Slot,WeaponType=Type,ItemLevel,Damage,Delay,Armor=AC,Str,End,Dex,Agi,Intellect=Int,Wis,Cha,Res,MR,PR,ER,VR,OverviewNotes=Notes,ClassLinks=Classes
|where=Type="Weapon"
|order by=Slot ASC,Name ASC
|format=template
|template=WeaponTable/Row
|named args=yes
|delimiter=\n
|default=
}}
|}</includeonly><noinclude>Cargo-backed weapon overview table.</noinclude>
```

- [x] **Step 4: Add `Template:WeaponTable/Row`**

Create `wiki/templates/WeaponTable/Row.wiki`:

```wiki
<includeonly>|-
|style="text-align: left;"|{{ItemLink|{{{Page|}}}|text={{{Name|}}}|image={{{Image|}}}}}
|{{{Slot|}}}
|{{{Type|}}}
|{{{ItemLevel|}}}
|{{{Damage|}}}
|{{{Delay|}}}
|{{{HP|}}}
|{{{Mana|}}}
|{{{AC|}}}
|{{{Str|}}}
|{{{End|}}}
|{{{Dex|}}}
|{{{Agi|}}}
|{{{Int|}}}
|{{{Wis|}}}
|{{{Cha|}}}
|{{{Res|}}}
|{{{MR|}}}
|{{{PR|}}}
|{{{ER|}}}
|{{{VR|}}}
|{{{Notes|}}}
|{{{Classes|}}}
</includeonly><noinclude>Renders one Cargo row for [[Template:WeaponTable]].</noinclude>
```

- [x] **Step 5: Recreate the local Cargo schema after adding `WeaponType`**

Run:

```bash
docker compose exec -T mediawiki php extensions/Cargo/maintenance/cargoRecreateData.php --table Items
```

Expected: Cargo recreates the `Items` table from `Template:Item`'s real `#cargo_declare`, and `cargo__Items` contains a `WeaponType` column.

- [x] **Step 6: Run the smoke to verify GREEN**

Run:

```bash
uv run python wiki-dev/import_pages.py && uv run python wiki-dev/smoke_test.py
```

Expected: PASS and the weapon table renders the fixture weapon row.

### Task 2: Add Cargo row assertions for weapon overview fields

**Files:**
- Modify: `wiki/templates/Item.wiki`
- Modify: `wiki/templates/Item/CargoDeclare.wiki`
- Modify: `wiki/modules/Erenshor/Item.lua`
- Modify: `wiki-dev/smoke/cargo.py`
- Modify: `wiki-dev/fixtures/cargo_items.tsv`
- Modify: `wiki/modules/Erenshor/Item/testcases.lua`

- [x] **Step 1: Add `WeaponType` to the real Items Cargo declaration**

Add `|WeaponType=String` to `Template:Item`'s `<noinclude>{{#cargo_declare:...}}</noinclude>` declaration, immediately after `Slot`.

- [x] **Step 2: Store `WeaponType` from Lua item data**

Add `{ "WeaponType", item.weaponType }` to `cargoStoreText()` in `Module:Erenshor/Item`, immediately after `Slot`.

- [x] **Step 3: Extend local Cargo smoke fields and expectations**

Add `WeaponType` after `Slot` in `wiki-dev/smoke/cargo.py` and insert the field into every row in `wiki-dev/fixtures/cargo_items.tsv`. Weapon rows should assert `OneHandMelee`; non-weapons should leave the field blank.

- [x] **Step 4: Add a Lua cargo-store assertion**

Extend `wiki/modules/Erenshor/Item/testcases.lua` to assert the Ember Longsword cargo output contains `|WeaponType=OneHandMelee`, `|Damage=18`, and `|Delay=2.5`.

- [x] **Step 5: Run the Cargo checker**

Run:

```bash
uv run pytest tests/unit/test_wiki_dev_harness.py -q
```

Expected: PASS.

### Task 3: Update the migration plan checkpoint

**Files:**
- Modify: `docs/plans/2026-05-29-wiki-lua-migration-next-steps.md`

- [x] **Step 1: Mark Milestone 9b Step 1 complete**

Change the Weapon overview checkbox to checked and record that the real local Cargo smoke validates item links, slot/type, normal-quality values, generated proc notes, and class links.

- [ ] **Step 2: Run focused verification**

Run:

```bash
pnpm exec stylua wiki/modules/Erenshor/Item.lua wiki/modules/Erenshor/Item/testcases.lua
uv run python wiki-dev/import_pages.py
docker compose exec -T mediawiki php extensions/Cargo/maintenance/cargoRecreateData.php --table Items
uv run python wiki-dev/smoke_test.py
uv run pytest tests/unit/test_wiki_dev_harness.py -q
```

Expected: all commands pass.

- [ ] **Step 3: Commit**

Use the commit helper with subject:

```text
feat(wiki): generate weapon overview from Cargo
```

Body:

```text
Add a repo-owned WeaponTable query surface that renders the Weapons overview from the same item Cargo rows used by ArmorTable. This removes another hand-maintained item statistics table while preserving the live page columns and generated proc/class notes.

The local Cargo smoke now exercises the weapon overview row so future changes to item Cargo storage cannot silently drop damage, delay, proc notes, weapon subtype, or class links.
```
