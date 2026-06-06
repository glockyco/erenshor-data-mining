# Cargo Phase 1a: Remove `Items.ClassLinks` rendered markup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop storing rendered semantic-link markup in the `Items` Cargo table. Drop the `ClassLinks=Wikitext` field; render class links at display time from the existing `Classes` (List of String of bare names) field.

**Architecture:** Per spec §5.1/§6.1, Cargo stores names, not markup. The infobox already renders classes from the data module; the weapon/armor overview tables currently query the pre-rendered `ClassLinks` and echo it. After this change, the overviews query `Classes` and render links via a new `Module:Erenshor/Item|classLinks` invoke that splits the comma-joined names and emits `Module:Erenshor/Link` markup.

**Tech Stack:** Lua (Scribunto), MediaWiki templates (LIBRARIAN/Cargo), Python smoke harness (`wiki-dev`), local MediaWiki at `http://localhost:8088`.

**Scope:** Items only. Characters (`Faction`→WorldFaction stablekey, `Zones`→names, drop `SpawnChance`) and the new `Spawns` table are subsequent Phase 1 increments.

---

## File Structure

- `wiki/modules/Erenshor/Item.lua` — drop the `ClassLinks` cargo field; replace the private `classOverviewLinks` with a public `p.classLinks(frame)` that renders from a comma-joined names string.
- `wiki/templates/Item.wiki` + `wiki/templates/Item/CargoDeclare.wiki` — drop `|ClassLinks=Wikitext`.
- `wiki/templates/ArmorTable.wiki` + `wiki/templates/WeaponTable.wiki` — query `Classes` instead of `ClassLinks=Classes`.
- `wiki/templates/ArmorTable/Row.wiki` + `wiki/templates/WeaponTable/Row.wiki` — render `{{{Classes}}}` through the new invoke.
- `wiki-dev/smoke/cargo.py` — remove `ClassLinks` from `CARGO_ITEM_FIELDS`.
- `wiki-dev/fixtures/cargo_items.tsv` — drop the `ClassLinks` (span-markup) column.
- `wiki/modules/Erenshor/Item/testcases.lua` — assert the cargo store carries plain `Classes` names (not markup) and that `classLinks` renders semantic links.

---

## Task 1: Items ClassLinks removal

- [ ] **Step 1: Replace `classOverviewLinks` with public `p.classLinks` and drop the cargo field**

In `wiki/modules/Erenshor/Item.lua`, delete the private `classOverviewLinks` function (it has one caller, removed below) and the `{ "ClassLinks", classOverviewLinks(item.classes) }` line in `cargoStoreText`. Add a public render entry (near the other `function p.*` entries, after `p.field`):

```lua
function p.classLinks(frame)
	local value = frame.args[1]
	if value == nil or isBlank(value) then
		return ""
	end
	local links = {}
	for class in string.gmatch(value, "[^,]+") do
		local trimmed = mw.text.trim(class)
		if not isBlank(trimmed) then
			table.insert(links, Link.render({ kind = "class", page = trimmed }))
		end
	end
	return table.concat(links, ", ")
end
```

- [ ] **Step 2: Drop the Cargo declarations**

Remove `|ClassLinks=Wikitext` from both `wiki/templates/Item.wiki` and `wiki/templates/Item/CargoDeclare.wiki`.

- [ ] **Step 3: Query `Classes` in the overview tables**

In `wiki/templates/ArmorTable.wiki` and `wiki/templates/WeaponTable.wiki`, change the trailing `ClassLinks=Classes` in the `|fields=` list to `Classes`.

- [ ] **Step 4: Render links in the row templates**

In `wiki/templates/ArmorTable/Row.wiki` and `wiki/templates/WeaponTable/Row.wiki`, change the `|{{{Classes|}}}` cell to:

```
|{{#invoke:Erenshor/Item|classLinks|{{{Classes|}}}}}
```

- [ ] **Step 5: Update the smoke field list + fixture**

Remove `"ClassLinks",` from `CARGO_ITEM_FIELDS` in `wiki-dev/smoke/cargo.py`. Drop the corresponding column (the `<span …>` markup column, immediately after the `Classes` names column) from every row of `wiki-dev/fixtures/cargo_items.tsv`. Do the column drop programmatically to stay aligned:

```python
from pathlib import Path
p = Path("wiki-dev/fixtures/cargo_items.tsv")
DROP = 28  # 0-based index of ClassLinks in CARGO_ITEM_FIELDS
rows = [ln.split("\t") for ln in p.read_text().splitlines() if ln]
out = ["\t".join(c for i, c in enumerate(r) if i != DROP) for r in rows]
p.write_text("\n".join(out) + "\n")
```

- [ ] **Step 6: Update the Lua testcases**

In `wiki/modules/Erenshor/Item/testcases.lua`, replace the three cargo-store class-link assertions (currently asserting `erenshor-link--class`, `[[Paladin]]`, `[[Warrior]]` in the *cargo store*) with a plain-names assertion, and add a render check for the new invoke:

```lua
	assertContains(cargo, "|Classes=Paladin,Warrior", "cargo store contains plain class names")
	local classRender = Item.classLinks({ args = { "Paladin,Warrior" } })
	assertContains(classRender, "erenshor-link--class", "classLinks renders semantic class links")
	assertContains(classRender, "[[Paladin]]", "classLinks renders Paladin link")
```

- [ ] **Step 7: Import + smoke + cargo-check**

```bash
uv run python wiki-dev/import_pages.py
uv run python wiki-dev/smoke_test.py
uv run python wiki-dev/cargo_check.py
```
Expected: all PASS. The Item testcases pass; the Cargo `Items` rows no longer have `ClassLinks`; the weapon/armor overview smoke still shows class links (now rendered from `Classes`).

- [ ] **Step 8: Targeted Python + static gate**

```bash
uv run pytest tests/unit/application/wiki_lua tests/unit/test_wiki_dev_harness.py -q --no-cov
uv run ruff check wiki-dev && uv run mypy src
```

- [ ] **Step 9: Commit**

```bash
git add wiki/modules/Erenshor/Item.lua wiki/templates/Item.wiki wiki/templates/Item/CargoDeclare.wiki \
  wiki/templates/ArmorTable.wiki wiki/templates/WeaponTable.wiki \
  wiki/templates/ArmorTable/Row.wiki wiki/templates/WeaponTable/Row.wiki \
  wiki-dev/smoke/cargo.py wiki-dev/fixtures/cargo_items.tsv \
  wiki/modules/Erenshor/Item/testcases.lua
# commit-helper with a feat(wiki) message
```

---

## Self-Review

**Spec coverage:** Implements spec §5.1 "drop `ClassLinks`" and §6.1 "render at display from `Classes`". Item→ability `Overview*` columns and the Characters/Spawns work are out of scope for this increment (later Phase 1 increments / Phase 2).

**Placeholder scan:** None — every edit site and code block is concrete.

**Type consistency:** `p.classLinks` consumes the comma-joined `Classes` value the overview query passes; `Classes` remains `List (,) of String`; `classCargo` (names) is unchanged.
