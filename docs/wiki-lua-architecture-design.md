# Wiki Lua Architecture Design

**Date**: 2026-05-27  
**Status**: Design document — research complete, pre-implementation  
**Prerequisites**: Read `docs/wiki-export-audit.md` and `docs/wiki-export-architecture-research.md` first

---

## What the Evidence Says

Before proposing anything, here is what comparable wikis actually do and what
documented best practices say. All conclusions below are grounded in these sources.

**Terraria wiki (wiki.gg)** — closest analogue: game on steam, thousands of entity
pages, multiple contributors, automated data from game source code.
- Bot writes `Module:Iteminfo/data` (Lua table of all item stats)
- `{{Item infobox|auto=<id>}}` on article pages reads from the Lua module via
  `mw.loadData()` and renders the infobox
- Manually specified template parameters (e.g. `|image=custom.png`) always override
  the auto-generated values — no field-preservation system needed
- The same template also calls `#cargo_store:` to populate the LIBRARIAN/Cargo "Items"
  table, including any per-page overrides
- Overview pages and cross-reference tables use `#cargo_query:` or `mw.ext.cargo.query()`
  from Lua modules
- Source: https://terraria.wiki.gg/wiki/Template:Item_infobox/doc

**PoE wiki** — large, complex, editor-focused, heavy automation via PyPoE.
- Uses a `store_from_lua` pattern: a factory function that reads from Lua data modules
  and writes to Cargo in bulk, from dedicated cargo-population template pages rather
  than from individual article pages
- This avoids having to null-edit every article page, but means per-page overrides are
  not reflected in Cargo unless handled separately
- Source: https://www.poewiki.net/wiki/Module:Cargo/doc

**Melvor Idle wiki** — mid-scale game, explicitly migrated away from an article-writing
bot in favour of pure Lua data modules. No Cargo used for game data.
- Works well for display, but overview pages require iterating Lua tables in Lua code
  (editors must know some Lua to add new overview pages)
- Source: https://wiki.melvoridle.com/index.php?title=Bot

**wiki.gg official documentation** — the platform hosting the Erenshor wiki.
- "Option 1: Use Lua modules as your data-store method instead of Cargo."
- "If you have development experience, it's highly recommended to use the Scribunto
  extension and write Lua modules as well."
- Cargo and Lua are described as complementary: Lua for logic and display, Cargo for
  queryable storage
- Source: https://support.wiki.gg/wiki/Cargo

**Null-edit documented requirement** — when game data is stored in a Lua data module
and the article template both reads from that module AND stores to Cargo, updating the
Lua module does NOT automatically refresh Cargo. A null-edit (empty save) of every
affected article page is required to re-trigger `#cargo_store:`.

> *"Even if the page will display correct information after a cache update (or forcing
> it with a purge), we still need to force a stored-data update, which you do by blank
> editing."* — https://support.wiki.gg/wiki/Null_edit

This is automatable via pywikibot: `python pwb.py touch -transcludes:"Template:Item"`,
and the bot already has API credentials, so it can do this as part of its own update
run via `action=edit` with an unchanged content body.

---

## Architecture

### The two-layer principle

The fundamental split is: **game data** lives in Lua data modules (bot writes); **how
to display and query it** lives in Lua display modules and templates (wiki-side, human
maintained). Individual article pages contain template calls with per-page overrides.
The bot never writes to article pages.

```
┌─────────────────────────────────────────────────────────────────┐
│ Bot writes (game update triggers this)                          │
│                                                                 │
│  Module:Erenshor/Data/Items   ← all item data as Lua table      │
│  Module:Erenshor/Data/Chars   ← all NPC/enemy data             │
│  Module:Erenshor/Data/Spells  ← all spells/abilities           │
│  Module:Erenshor/Data/Skills  ← all skills                     │
│  Module:Erenshor/Data/Zones   ← all zone metadata              │
│                                                                 │
│  Then: null-edit pass via API (re-triggers #cargo_store:)       │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│ Wiki-side (human maintained, evolves independently of bot)      │
│                                                                 │
│  Module:Erenshor/Item      ← renders {{Item}} infobox + tooltips│
│  Module:Erenshor/Character ← renders {{Character}} infobox     │
│  Module:Erenshor/Spell     ← renders {{Ability}} infobox       │
│  Module:Erenshor/Tables    ← generates overview/list tables     │
│  Template:Item, Template:Character, ...   ← thin wrappers      │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│ Article pages (human maintained, bot never writes here)         │
│                                                                 │
│  {{Item|name=Sword of Flames|image=Custom.png}}                 │
│  Human-written lore, notes, strategy below the template call.   │
│  Override parameters take precedence over data module values.   │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│ LIBRARIAN/Cargo tables (populated by template calls)            │
│                                                                 │
│  Items table    ← populated when {{Item|...}} is saved/purged  │
│  Characters table, Spells table, ...                            │
│  Overview pages query these via mw.ext.cargo.query()           │
└─────────────────────────────────────────────────────────────────┘
```

### Data modules

Each module is a Lua file returning a single table keyed by stable identifier.
The bot serialises the current SQLite data into Lua syntax on every game update.

```lua
-- Module:Erenshor/Data/Items
-- Bot-generated. Do not edit. Last updated: build 1.0.52.
return {
    ["Sword of Flames"] = {
        type = "weapon",
        slot = "Primary",
        buy = 0,
        sell = 120,
        tiers = {
            {quality="Normal",  damage_min=12, damage_max=18, speed="Fast"},
            {quality="Blessed", damage_min=14, damage_max=21, speed="Fast"},
            {quality="Godly",   damage_min=17, damage_max=25, speed="Very Fast"},
        },
        drop_sources = {
            {name="Flame Wraith", rate=3.5},
            {name="Ash Golem",    rate=1.2},
        },
        vendor_sources = {},
        -- image intentionally absent: article page provides custom image
    },
    ["Cloth Sleeves"] = {
        type = "armor",
        slot = "Arms",
        buy = 45,
        sell = 10,
        tiers = {
            {quality="Normal",  ac=4},
            {quality="Blessed", ac=6},
            {quality="Godly",   ac=9},
        },
        drop_sources = {},
        vendor_sources = {
            {name="Aldric the Tailor", price=45},
        },
    },
    -- ... all other items
}
```

**`mw.loadData` constraints**: The table returned is read-only. You cannot use `#t`
(the length operator), `next()`, or `table.*` functions directly on it. `pairs()` and
`ipairs()` work. If a display module needs to sort, filter, or count items, it must
copy the relevant entries into a local mutable table first. This is a documented
Scribunto constraint.
— https://www.mediawiki.org/wiki/Extension:Scribunto/Lua_reference_manual

**Module size and splitting**: Scribunto imposes memory limits per page render.
Experience from en.wiktionary and Terraria wiki shows that modules above ~500KB can
cause "not enough memory" errors on pages with many template calls. For Erenshor, with
~2000 items, a single module is likely fine if the data is compact (no long lore text).
If it becomes a problem, the standard split is by type: `Data/Items/Weapons`,
`Data/Items/Armor`, `Data/Items/Consumables` etc., each loaded only by the module
that needs it.

### Override mechanism

This is the Terraria wiki's approach, confirmed by their published documentation:
**manually supplied template parameters always take precedence over auto-generated
Lua data**. The display module implements this with a simple `or` chain:

```lua
-- Inside Module:Erenshor/Item
local function render(frame)
    local args    = frame:getParent().args
    local data    = mw.loadData('Module:Erenshor/Data/Items')
    local name    = args.name or mw.title.getCurrentTitle().text
    local item    = data[name]

    if not item then
        return '<strong class="error">Item not found: ' .. name .. '</strong>'
    end

    -- Explicit template param wins; fall back to data module; then hard default.
    local image   = args.image   or item.image   or (name .. '.png')
    local caption = args.imagecaption or item.imagecaption or ''
    -- ... render the infobox using mw.html or a string template
end
```

On the article page:

```wikitext
{{Item|name=Sword of Flames|image=SwordOfFlames_custom.png}}
```

The `image` parameter overrides whatever the data module says. All other fields come
from the data module automatically. If the game data changes (new drop rate, new
vendor), the article page needs no edit — it picks up the change after the bot
updates the data module and the null-edit pass runs.

There is no Python-side field-preservation system. No fetching. No merging. The override
lives in the article page source, where it is visible to all editors and tracked by
wiki revision history.

### Non-infobox content: quality tiers and item tooltips

The current system has `{{Item/Weapon}}`, `{{Item/Armor}}`, `{{Item/Charm}}`,
`{{Item/Aura}}`, `{{Item/SpellScroll}}`, etc. — separate templates that the Python bot
generates and splices into pages alongside the main `{{Item}}` template. This is the
primary source of the `_replace_fancy_tables` / `_replace_item_type_templates`
complexity.

In the Lua architecture, the display module renders **everything** for an item in a
single `{{Item|name=...}}` call:

```lua
-- Module:Erenshor/Item, continued
local function renderWeaponTierTable(item)
    -- item.tiers is already in the data module
    local t = mw.html.create('table'):addClass('wikitable')
    local header = t:tag('tr')
    header:tag('th'):wikitext('Quality')
    header:tag('th'):wikitext('Damage')
    header:tag('th'):wikitext('Speed')
    for _, tier in ipairs(item.tiers) do
        local row = t:tag('tr')
        row:tag('td'):wikitext(tier.quality)
        row:tag('td'):wikitext(tier.damage_min .. '–' .. tier.damage_max)
        row:tag('td'):wikitext(tier.speed)
    end
    return tostring(t)
end
```

The module detects item type from `item.type` and branches: weapons and armor get the
tier table; auras, spell scrolls, skill books get their respective tooltip section;
charms get the charm stats block. All from one template call. No Python-side wikitext
surgery.

Terraria's `{{Item infobox}}` takes this further with a `|view=` parameter
(`infobox`, `table`, `item`, `void`) that changes what the template renders. The table
view renders a single `|-` `||` row for use in overview tables — the same template call
used for the infobox can render a table row by changing one parameter. This pattern is
worth adopting.

### Cargo / LIBRARIAN integration

The `{{Item}}` template (the thin wikitext wrapper around `Module:Erenshor/Item`)
includes `#cargo_declare:` and `#cargo_store:` calls. This is exactly what the Terraria
wiki does: the display template is also the storage template.

```wikitext
<!-- Template:Item -->
{{#cargo_declare:_table=Items
|name=String
|type=String
|slot=String
|damage_min=Integer
|damage_max=Integer
|sell=Integer
|buy=Integer
}}
{{#cargo_store:_table=Items
|name={{{name|{{PAGENAME}}}}}
|type={{#invoke:Erenshor/Item|cargoType|{{{name|{{PAGENAME}}}}}}}
|slot={{#invoke:Erenshor/Item|cargoSlot|{{{name|{{PAGENAME}}}}}}}
|damage_min=...
...
}}
{{#invoke:Erenshor/Item|render|{{#if:{{{name|}}}|name={{{name}}}}}}}
```

In practice, the `#cargo_store:` call is typically also driven by the Lua module to
avoid duplicating field logic in both wikitext and Lua. Cargo can be called from Lua
via `mw.ext.cargo.store()`:
— https://www.mediawiki.org/wiki/Extension:Cargo/Other_features

```lua
-- Called by Template:Item to populate Cargo
function p.storeToCargoAndRender(frame)
    local args = frame:getParent().args
    local data = mw.loadData('Module:Erenshor/Data/Items')
    local name = args.name or mw.title.getCurrentTitle().text
    local item = data[name]
    -- Resolve with overrides
    local resolved = resolveItem(item, args)
    -- Store resolved values (including any per-page overrides)
    mw.ext.cargo.store('Items', {
        name        = name,
        type        = resolved.type,
        damage_min  = resolved.damage_min,
        -- ...
    })
    -- Render and return
    return renderIntoHtml(resolved)
end
```

**Why this matters for overrides**: since Cargo is populated from the resolved values
(Lua data merged with per-page overrides), a contributor who adds `|image=custom.png`
to an article's `{{Item}}` call will have that override reflected in Cargo queries.
Overview pages that query Cargo will show the correct, contributor-curated data, not
just raw game data.

**The null-edit requirement**: Updating `Module:Erenshor/Data/Items` does not
automatically refresh Cargo for the ~2000 item article pages. A null-edit of each is
required. The bot's update workflow should include:

```python
# After writing all data modules:
for title in all_item_titles:
    wiki_client.edit_page(
        title=title,
        content=wiki_client.get_page(title),   # fetch current content
        summary=f"Null-edit: refresh Cargo after build {build_number}",
    )
```

Or via pywikibot: `python pwb.py touch -transcludes:Template:Item`

This is O(entity count) API calls, but they are empty saves — no parsing of wikitext,
no merge logic. The MediaWiki API handles this correctly and does not create revision
history entries.

wiki.gg confirms this is the standard workflow for Cargo-using wikis.
— https://support.wiki.gg/wiki/Null_edit

**Schema changes**: If a new field is added to the Cargo table (e.g., a new weapon
stat appears in a game update), an admin must run "Recreate data tables" from
Special:CargoTables. This is a one-click admin operation. It is NOT something that
needs to happen every game update — only when the schema changes.

### Overview pages: Lua iteration vs. Cargo queries

These are different tools with different strengths. The right choice depends on the
page.

**Use Lua iteration (from data modules) when**:
- The page needs complex logic (e.g., grouping weapons by slot then sorting by tier)
- The output is always fully derived from game data with no editor-curated additions
- The module author is comfortable writing Lua

```lua
-- Module:Erenshor/Tables, weapons function
function p.weapons(frame)
    local data = mw.loadData('Module:Erenshor/Data/Items')
    local weapons = {}
    for name, item in pairs(data) do
        if item.type == 'weapon' then
            weapons[#weapons+1] = {name=name, item=item}
        end
    end
    table.sort(weapons, function(a,b) return a.name < b.name end)
    -- render mw.html table
end
```

**Use Cargo queries when**:
- Wiki contributors who don't write Lua need to maintain or extend the table
- The table should include editor-curated per-page overrides (because Cargo captures those)
- Cross-table JOINs are needed (e.g., items + their drop sources in one query)
- The data set is large and Lua iteration would be slow or hit memory limits

```wikitext
<!-- On the Weapons overview page -->
{{#cargo_query:tables=Items
|fields=_pageName,name,slot,damage_min,damage_max
|where=type='weapon'
|order by=damage_max DESC
|format=template|template=WeaponRow}}
```

**Specific Erenshor use cases**:

| Page | Recommended approach | Why |
|---|---|---|
| Individual item infobox | Lua (data module) | Single-item lookup, override support |
| Weapon quality tier table | Lua (embedded in item module) | Always derived from game data |
| Item tooltips (aura, scroll etc.) | Lua (embedded in item module) | Always derived from game data |
| Weapons overview table | Cargo query | Editors may add rows, sortable columns, filtering |
| Armor overview table | Cargo query | Same |
| Vendor inventory table on NPC page | Lua (character data module) | Data is complete from game export |
| Vendor listings overview page | Cargo query (JOIN items + chars) | Cross-table data, editor-useful |
| Class pages (skills/spells for a class) | Cargo query | Editors curate class page content |
| Spell/skill overview pages | Cargo query | Sortable, filterable by class |
| Zone page infobox | Lua (zone data module) | Derived from game data |
| Zone connections map | Lua (zone data module) | Always derived from game data |

### What the bot still does

After this migration, the bot's role is dramatically simpler:

1. Read all entities from SQLite
2. Serialise each entity type to a Lua data module (one API write per entity type)
3. Null-edit all affected article pages (to refresh Cargo)
4. Log the game build number used

Steps 1–2 replace the entire current fetch/generate/merge/deploy pipeline. Step 3 is
new but trivial. The bot no longer needs to:
- Fetch existing article pages
- Parse wikitext with `mwparserfromhell`
- Apply field-preservation rules
- Handle legacy templates
- Navigate five different code paths depending on item type

The Python codebase loses `generate_service.py` (746 lines), `field_preservation.py`
(595 lines), `legacy_template_remover.py` (276 lines), `template_parser.py` (404 lines),
the five `_replace_*` methods, `PageNormalizer`, and the entire fetch step. What remains
is: read SQLite → serialise to Lua → write to wiki.

---

## Pitfalls and How to Avoid Them

### `mw.loadData` returns a read-only table

The returned table cannot be modified. `#t` (length), `next()`, `table.sort()`,
`table.insert()` all fail on it directly. Copy entries to a local mutable table before
sorting or filtering:

```lua
local raw   = mw.loadData('Module:Erenshor/Data/Items')
local items = {}                            -- mutable copy
for name, item in pairs(raw) do
    items[#items+1] = {name=name, data=item}
end
table.sort(items, function(a,b) return a.name < b.name end)
```

### `mw.loadData` is cached per page, not per call

Multiple `mw.loadData('Module:Erenshor/Data/Items')` calls on the same page are free
after the first. Do not try to optimise away calls. The cache is keyed by module name
per-page render.

### Expensive function limit

Each `mw.loadData` call counts as an "expensive parser function" (the limit is usually
500 per page). For pages with many items (like an overview table), call `loadData`
once, store the result, and reuse it. This is already how well-written Lua modules work.

### Module size and memory

The Scribunto Lua sandbox has a memory limit (typically 50MB per page, but the exact
limit on wiki.gg may differ). Large data modules can exhaust this on overview pages that
load multiple entity types. The symptom is a "Lua error: not enough memory" on specific
pages. Mitigation: split data modules by entity subtype (weapons separate from armor
separate from consumables), and load only what a given page needs.

The Terraria wiki handles ~5000+ items in a single module with no memory errors, which
suggests the limit is not a concern for Erenshor's current scale.

### Cargo table recreation on schema change

When a field is added to or removed from a Cargo table definition, the table must be
recreated via Special:CargoTables by a wiki admin. Failing to do this causes
`#cargo_store:` to silently drop the new field, so overview queries show empty columns.
This is a one-time cost per schema change, not per game update.

### Null-edit volume

2000 null-edits per game update is manageable but not instantaneous. The MediaWiki API
allows batch edits; rate limiting (the current 2 second delay) makes this ~70 minutes
per full null-edit pass. Consider:
- Only null-editing pages where the data actually changed (compare Lua table before/after
  and only touch affected article pages)
- Or accepting the full pass — it runs unattended and does not affect the wiki's
  usability

### Lua errors break page rendering

If `Module:Erenshor/Data/Items` has a syntax error (e.g., a malformed string from the
bot's serialiser), every page using `{{Item}}` will show a Lua error. The current
system fails silently (wrong data displayed). Lua errors are visible and loud. This is
actually better — fail fast — but the bot's serialiser must be tested. Validate the
Lua syntax of generated data modules before uploading (e.g., `luac -p module.lua`
or test-parsing in Python with a Lua library).

---

## Migration path

### Phase 1: Bot side (no wiki changes needed yet)

Build the Lua serialiser in the Python bot:
- Add a new command `erenshor wiki generate-lua` that reads SQLite and writes
  `Module:Erenshor/Data/Items` etc. as `.lua` files to disk
- Validate syntax (`luac -p` or equivalent)
- Deploy to wiki via the existing `MediaWikiClient.edit_page()`
- The existing article pages still use the old `{{Item}}` template — no breakage

### Phase 2: Wiki side (Lua display modules + updated templates)

This work happens on the wiki itself, done by a developer who knows some Lua:
- Write `Module:Erenshor/Item` (renders infobox + tooltips + tier tables)
- Write `Module:Erenshor/Character`, `Module:Erenshor/Spell`, etc.
- Update `Template:Item` to call the Lua module
- Add `#cargo_store:` to the template
- Test on a handful of pages using `Template:Item/sandbox`
- Roll out to all pages — existing pages do not need to be edited, they pick up the
  new template automatically

### Phase 3: Bot side cleanup

Remove from the Python bot:
- `WikiFetchService` and the entire fetch step
- `WikiGenerateService` and all merge logic
- `FieldPreservationHandler`
- `LegacyTemplateRemover`
- `PageNormalizer`
- `WikiStorage`

What remains is: SQLite read → Lua serialisation → wiki write → null-edit pass.

### Phase 4: Null-edit infrastructure

Add `wiki null-edit` CLI command that sends an empty-body edit to all article pages
whose data modules were updated in the current run. Run this as the final step of
every bot update.

### Migration of existing pages with manual overrides

Existing pages that have custom values in their current `{{Item}}` template parameters
(e.g., `|image=Custom.png`) will continue to work because the new `{{Item}}` template
still accepts the same parameter names. Their overrides are preserved in the article
source — no migration script needed for those pages.

---

## Reference implementations

| Wiki | Pattern | URL |
|---|---|---|
| Terraria wiki — item infobox documentation | Lua + Cargo, override via template params | https://terraria.wiki.gg/wiki/Template:Item_infobox/doc |
| Terraria wiki — datagen module | How bot serialises game data to Lua | https://terraria.wiki.gg/wiki/Module:Iteminfo/datagen |
| PoE wiki — Module:Cargo | `store_from_lua` pattern, Cargo from Lua | https://www.poewiki.net/wiki/Module:Cargo |
| wiki.gg — Cargo guide | When to use Cargo vs Lua | https://support.wiki.gg/wiki/Cargo |
| wiki.gg — Null edit guide | Why and how to null-edit after data updates | https://support.wiki.gg/wiki/Null_edit |
| wiki.gg — CargoQuery module | Lua helper for Cargo queries | https://support.wiki.gg/wiki/Module:CargoQuery |
| MediaWiki — Scribunto Lua reference | `mw.loadData` constraints and best practices | https://www.mediawiki.org/wiki/Extension:Scribunto/Lua_reference_manual |
| MediaWiki — Lua best practice | Naming, structure, testing conventions | https://www.mediawiki.org/wiki/Help:Lua/Lua_best_practice |
| MediaWiki — API:Edit (null edit) | API null-edit documentation | https://www.mediawiki.org/wiki/API:Edit |
