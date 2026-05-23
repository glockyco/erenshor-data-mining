# Wiki Export Architecture Research

**Date**: 2026-05-23  
**Context**: Architecture research for redesigning the Erenshor wiki export pipeline.  
The wiki is hosted on **erenshor.wiki.gg**. The wiki has multiple contributors, several
thousand pages, and a significant amount of manually-maintained content that must survive
automated game-data refreshes.

---

## Part 1: How Mature Game Wikis Solve This Problem

The three canonical patterns used by the most-maintained game wikis today are distinct
strategies, not variations on a theme. Understanding all three is necessary to make a
sound architectural choice.

### Pattern A — Lua Data Modules (Terraria wiki, Melvor Idle wiki)

**The model**: The bot writes exactly *one thing*: a wiki page in the `Module:`
namespace containing all game data as a Lua table. Display templates and article pages
*read* from that module; they are never touched by the bot.

The Terraria wiki uses this extensively:

> *"Module:Iteminfo provides the functionality of the `{{iteminfo}}` template. It is
> used to dynamically and reliably obtain an item's stats. It takes its data directly
> from the source code. The database is `Module:Iteminfo/data` and is currently
> synchronized with the Desktop version 1.4.5.6 of Terraria."*
> — https://terraria.wiki.gg/wiki/Module:Iteminfo

`Module:Iteminfo/datagen` ports Terraria's C# `Item.SetDefaults()` logic into Lua.
After a game update, a wiki admin invokes the datagen module on a sandbox page, copies
the output, and pastes it into `Module:Iteminfo/data`. The bot (Ryebot, driven by GitHub
Actions) then handles bulk operations like category maintenance and link fixes —
*not individual article generation*.

The Melvor Idle wiki followed the same evolution explicitly:

> *"Note: As of V0.17.0, the bot has been discontinued in favour of automating page
> updates using Lua modules."*  
> — https://wiki.melvoridle.com/index.php?title=Bot

The Melvor workflow today: open the game in a browser, run a console script to dump
the game's JSON data, paste it into `Module:GameData/data` (split across `data`,
`data2`, `data3` for size). All pages render dynamically from that data.
— https://wiki.melvoridle.com/w/Module:GameData/doc

**How the bot interacts with article pages**: It doesn't. Individual article pages
contain a single template call like `{{iteminfo|Vampire Knife}}`. The template invokes
the Lua module, which looks up the item by name in the data module and renders all
stats. Human editors write lore text, strategy notes, and trivia below the template
call. The bot's writes never touch those sections.

**Tradeoffs**:
- ✅ No per-article fetch/merge needed: the bot writes O(entity types) pages, not O(entities) pages
- ✅ Template changes and data changes are fully decoupled
- ✅ Field preservation is a non-problem: human content is structurally separate
- ✅ Works perfectly with wiki.gg's Scribunto (Lua) extension (confirmed available on erenshor.wiki.gg)
- ⚠️ Requires Lua modules on the wiki side (display logic moves into the wiki)
- ⚠️ The data module pages can be very large (Melvor splits across 3 pages)
- ⚠️ Debugging display issues requires knowing some Lua

### Pattern B — Cargo / LIBRARIAN (Path of Exile wiki, wiki.gg)

**The model**: Data is stored in SQL-like Cargo tables via `#cargo_store:` calls inside
templates. Any page can then query the data with `#cargo_query:`, similar to a SQL
`SELECT`. The bot writes template calls that include `#cargo_store:` to populate tables;
human editors write article content that queries those tables for display.

The PoE wiki uses PyPoE for this:

> *"PyPoE is a Python 3 based collection of development tools to work with Path of Exile.
> The command line interface for the wiki is used extensively to update many pages on the
> wiki with game data... Each new PoE league has an updated game data file, which has to
> be parsed out and mined for information about the items, monsters, league mechanics."*  
> — https://www.poewiki.net/wiki/Path_of_Exile_Wiki:PyPoE

The PoE data architecture:

> *"Generally the data is stored in `Template:Name/cargo/table_name/N` where `N` is a
> sequential identifier for every 1000 entries."*

Human editors and bot both write to the same `{{Item}}` template calls, but the PoE
wiki has established conventions about which fields are bot-managed and which are
editor-managed. Cargo stores all this in queryable tables that drive overview pages,
comparison tables, and cross-references.

wiki.gg calls their Cargo fork **LIBRARIAN** and it is confirmed available on the
Erenshor wiki (v4.21.0, confirmed via API).
— https://support.wiki.gg/wiki/Cargo

**Tradeoffs**:
- ✅ Data is queryable from any wiki page (item tables, comparison pages, etc.)
- ✅ Schema is documented and visible within the wiki itself
- ✅ Native to wiki.gg (LIBRARIAN is available on erenshor.wiki.gg)
- ⚠️ Schema changes require an admin to "recreate data tables"
- ⚠️ More complex to set up (declare table, store, query — three distinct concepts)
- ⚠️ Bot writes to *individual* article pages (still requires the fetch/merge decision)
- ⚠️ Null-edits required to propagate schema changes: *"these changes will not be loaded without null-editing"*

### Pattern C — Section Markers / HTML Comment Fencing

**The model**: Bot-owned content on each article page is enclosed between HTML comment
markers. The bot reads the page, replaces the content between its markers, and never
touches anything outside them. Human editors add content outside the markers.

```wikitext
<!-- BOT:START ErenshorBot -->
{{Item
|title=Sword of Flames
|vendorsource=...
|droprates=...
}}
<!-- BOT:END ErenshorBot -->

The Sword of Flames is a legendary blade forged in the heart of
the Ashen Reaches during the Age of Embers. It deals bonus fire
damage to creatures of the void.

[[Category:Weapons]]
```

HTML comments are invisible in rendered output (satisfying the original "no visible
annotations" preference) but are visible in the source editor, making the bot's domain
explicit to human contributors.

This pattern is documented in the MediaWiki ecosystem:

> *"Bots can be excluded from leaving messages by using `{{bots}}` tags."*  
> — https://www.mediawiki.org/wiki/Wikipedia:Bots

Pywikibot's `archivebot.py` uses a similar marker pattern to identify which talk-page
sections to archive:

> *"This bot only processes pages that are explicitly marked by transcluding a marker
> template."*  
> — https://www.mediawiki.org/wiki/Manual:Pywikibot/archivebot.py/setup

**Tradeoffs**:
- ✅ Simple to implement: regex replace between markers
- ✅ No merge logic needed — bot replaces its entire section atomically
- ✅ HTML comments are invisible in rendered output
- ✅ No wiki-side infrastructure changes needed
- ✅ Straightforward migration path for existing pages
- ⚠️ Initial migration must add markers to all existing pages
- ⚠️ Bot still writes O(entities) pages (one per article)
- ⚠️ Bot must fetch existing page before writing, to detect whether markers exist
- ⚠️ No queryable data — overview tables still need separate generation

---

## Part 2: What the Erenshor Wiki Has Available

Confirmed extensions on erenshor.wiki.gg (via `Special:Version` API):

| Extension | Version | Relevance |
|---|---|---|
| **Scribunto** | current | Lua modules (`Module:` namespace) |
| **LIBRARIAN** | 4.21.0 | wiki.gg's Cargo fork — structured data tables |
| **LabeledSectionTransclusion** | current | Transclude named sections from pages |
| **DynamicPageList3** | 3.6.3 | Query pages by category/property for lists |
| **ParserFunctions** | 1.6.1 | `#if`, `#switch`, conditional display logic |
| **Interactive Data Maps** | 0.17.11 | wiki.gg's DataMaps (used by current maps) |

Both Lua modules and LIBRARIAN/Cargo are available. This is the full toolkit used by
the mature game wikis described above.

---

## Part 3: The Core Problem, Precisely Stated

The current system's complexity is a consequence of one unexamined architectural
assumption: **article pages are the source of truth for bot-generated data**.

Because article pages are the source of truth, the bot must:
1. Read the current version of every article page before writing (the fetch step)
2. Parse the wikitext to separate bot-generated content from human-edited content
3. Apply field-level merge rules to decide which fields to keep
4. Regenerate the bot-generated portion
5. Reassemble the page and write it back

Every problem in the current system traces back to this assumption:
- `FieldPreservationHandler` exists because the bot cannot tell which field values were
  entered by humans
- `LegacyTemplateRemover` exists because template renames must be surgically applied to
  each existing article page
- `_replace_fancy_tables` / `_replace_item_type_templates` exist because the merge
  system needs to operate at template-block granularity, not just field granularity
- `PageNormalizer.LEGACY_CATEGORIES` exists because category migrations must be applied
  to each article page

The correct fix is to **not** make article pages the source of truth for bot-generated
data. There are two ways to achieve this:

**Inversion A (preferred)**: Bot writes to a *separate data repository* (Module: data
pages or Cargo tables). Article pages consume from that repository via templates. Bot
never touches article pages.

**Inversion B (pragmatic intermediate)**: Bot writes to a *fenced section* on article
pages. Everything outside the fence is editable by humans. Bot replaces its fence
atomically, without knowing or caring what surrounds it.

---

## Part 4: Recommended Architecture

### Primary Recommendation: Lua Data Modules

This is the pattern used by Terraria wiki and Melvor Idle. It is the cleanest long-term
solution, and all required wiki infrastructure (Scribunto) is already present on the
Erenshor wiki.

**Data flow**:

```
SQLite DB  →  Python bot  →  Module:Erenshor/items   (Lua table, ~2000 items)
                          →  Module:Erenshor/chars   (Lua table, ~N characters)
                          →  Module:Erenshor/spells  (Lua table, etc.)

Article page:
  {{Item|Sword of Flames}}          (single template call)
      ↓ invokes
  Template:Item  →  {{#invoke:Erenshor/Item|render|Sword of Flames}}
      ↓ invokes
  Module:Erenshor/Item  →  reads Module:Erenshor/items  →  renders infobox

Human-written content lives below the template call.
Bot never writes to article pages.
```

**What the Python bot does per game update**:
1. Read all entities from SQLite
2. Serialize all items to a Lua table: `Module:Erenshor/items` (one API write)
3. Serialize all characters to a Lua table: `Module:Erenshor/chars` (one API write)
4. Repeat for spells, skills, stances, zones

Total writes per game update: O(entity types), not O(entities). For Erenshor,
that is likely 6–8 pages, not 2000.

**What happens to the existing templates**: The current Jinja2 templates move to
become Lua display modules on the wiki. `Template:Item` becomes a thin wrapper that
invokes `Module:Erenshor/Item`, which looks up the item by name and renders the
infobox. This is a one-time migration investment.

**Override handling**: Manual overrides for specific fields (custom images, quest
associations, etc.) live either:
- In the article page outside the template call (for freeform overrides)
- As named `|override_image=` parameters in the template call on the article page
  (overrides the module's data lookup for that field)
- In a small `Module:Erenshor/overrides` Lua table that the display module checks
  before using data module values

This is *far* cleaner than the current `DEFAULT_PRESERVATION_RULES` approach because:
overrides are explicit (visible in the article source), version-controlled as part of
the wiki (not in the bot's codebase), and require no round-trip fetching to apply.

**Migration path**:
1. Build `Module:Erenshor/items` (and other data modules) from the existing SQLite
2. Write `Module:Erenshor/Item` Lua display module (ports current Jinja2 templates)
3. Update `Template:Item` to invoke the module
4. Verify rendering on a handful of pages
5. Existing article pages automatically display new data without any edits

The Melvor Idle wiki completed this migration and documented the benefit clearly: all
data updates now require updating one data module page per game version, with zero
per-article writes.

**Terraria's approach to large data modules**: Split by function. For Erenshor, a
natural split would be:
- `Module:Erenshor/ItemData` — all item data
- `Module:Erenshor/CharacterData` — all character/NPC data
- `Module:Erenshor/SpellData` — spells and abilities
- `Module:Erenshor/ZoneData` — zone metadata

Each module is ~100–300KB of Lua. Scribunto uses `mw.loadData()` for efficient
per-request caching so the data is only parsed once per pageview.

**Reference**:
- Terraria wiki Iteminfo module: https://terraria.wiki.gg/wiki/Module:Iteminfo
- Melvor Idle GameData: https://wiki.melvoridle.com/w/Module:GameData/doc
- Scribunto Lua reference (mw.loadData): https://www.mediawiki.org/wiki/Extension:Scribunto/Lua_reference_manual

---

### Secondary Recommendation: Section Markers (Pragmatic Intermediate)

If the Lua module architecture is too large an investment for immediate implementation,
the section marker approach provides most of the robustness benefit with much lower
up-front cost. It completely eliminates the field-level merge problem.

**Page structure**:
```wikitext
<!-- BOT:START ErenshorBot -->
{{Item
|title=Sword of Flames
|vendorsource=[[Ash Merchant]]
|droprates=[[Flame Wraith]] (3.5%)
}}
<!-- BOT:END ErenshorBot -->

The Sword of Flames was forged by the legendary smith Ardun in the
third age. It is said to burn eternally without heat.

{{ItemLink|Ember Scabbard}}

[[Category:Weapons]]
[[Category:Fire Damage]]
```

**Bot logic becomes trivially simple**:
```python
START = "<!-- BOT:START ErenshorBot -->"
END = "<!-- BOT:END ErenshorBot -->"

def update_page(existing: str, new_infobox: str) -> str:
    if START in existing and END in existing:
        # Replace between markers, preserve everything else
        before = existing[:existing.index(START)]
        after = existing[existing.index(END) + len(END):]
        return f"{before}{START}\n{new_infobox}\n{END}{after}"
    else:
        # New page or un-marked page: prepend the fenced infobox
        return f"{START}\n{new_infobox}\n{END}\n\n{existing}"
```

This is the complete replace logic. No `mwparserfromhell`, no field-level rules, no
`LegacyTemplateRemover`, no `_replace_fancy_tables`.

**Migration**: A one-time bot run that prepends the `<!-- BOT:START -->` / `<!-- BOT:END -->`
markers around the existing infobox template block on every article page. After that,
all future runs use the marker-replace logic above.

**What this eliminates from the current codebase**:
- `FieldPreservationHandler` (595 lines) — entirely deleted
- `LegacyTemplateRemover` (276 lines) — entirely deleted (run once as a migration script)
- `_replace_fancy_tables`, `_replace_item_type_templates`, `_replace_overview_table`,
  `_replace_wiki_table`, `_replace_fancy_charm_template` in `generate_service.py` — all deleted
- The entire fetch→merge pipeline simplifies to: fetch page, check for markers, replace

**What remains**: The fetch step is still needed (to check for existing markers and
preserve article content outside the markers), but it is no longer the primary driver
of complexity.

---

### Tertiary Option: LIBRARIAN / Cargo

LIBRARIAN (Cargo) is available on the Erenshor wiki and is worth noting as a third
option, particularly if queryable data tables are desirable (e.g., a page listing all
items that drop from a specific zone, or all vendors selling a specific item tier).

In the Cargo model, the bot writes `{{Item|...}}` template calls that include
`#cargo_store:` directives. This populates database tables that any wiki page can
query with `#cargo_query:`.

The PoE wiki uses this extensively:

> *"Cargo is a type of database used to store interesting values in various items,
> mods, versions etc. as rows in cargo tables. The stored values can then be used to
> execute powerful queries and retrieve fields from cargo tables. The syntax is very
> similar to MySQL or SQL because it uses MySQL at its core."*  
> — https://www.poewiki.net/wiki/Path_of_Exile_Wiki:Data_query_API

This pattern does *not* eliminate the per-article write problem (the bot still writes
to individual article pages), but it does provide queryable data as a side-benefit.
Combined with section markers, it could be highly effective. However, the schema
management burden (recreating Cargo tables on schema changes) makes it more complex
than either of the above two approaches for an initial redesign.

---

## Part 5: Additional Best Practices

### Edit conflict detection (MediaWiki `basetimestamp`)

Every production MediaWiki bot should pass `basetimestamp` (the revision timestamp of
the page version it read) when submitting edits. Without it, the API will silently
overwrite any concurrent human edit.

> *"Conflicts can be prevented by retrieving the last revision timestamp when we request
> a CSRF token. Adding `prop=info|revisions` to the CSRF token request allows access to
> the timestamp for the last revision, which will be used as the `basetimestamp`."*  
> — https://www.mediawiki.org/wiki/API:Edit

The current `MediaWikiClient.edit_page()` does not pass `basetimestamp`. This is a
correctness bug regardless of which architecture is chosen.

### Edit summaries with version attribution

Edit summaries should include the data source version (game build number) and bot
identifier. This allows wiki contributors to understand the scope of any bot-generated
change and makes rollbacks meaningful.

```
Automated update: Erenshor build 1.0.47 — item stats refresh
```

The Terraria wiki's Ryebot includes a GitHub Actions run ID in every edit summary,
linking directly to the log of the run that produced the edit:

> *"Ryebot usually includes an ID in its edit summaries (e.g. 'Updated. »ID:8545774499«'),
> which refers to its GitHub Actions run."*  
> — https://terraria.wiki.gg/wiki/User:Ryebot/bot

### Rate limiting and maxlag

The current client correctly implements `maxlag=5`. The separate `time.sleep(2.0)` in
the deploy service creates an additional, non-configurable delay. These should be
consolidated into the client with a configurable rate.

The MediaWiki API will automatically throttle when the server is under load via maxlag,
which is more reliable than a fixed sleep.

### Null-edits for cache busting

When using Cargo (LIBRARIAN) or Lua data modules, changing the data does not
automatically re-render display pages. A "null edit" (fetching and immediately
re-saving a page without changes) forces MediaWiki to reparse the page and pick up
new data. AWB automates this well:

> *"AWB is especially useful for automating 'null edits' to update caches for the wiki,
> or related data tables if your wiki uses extensions like Cargo."*  
> — https://support.wiki.gg/wiki/AutoWikiBrowser

With the Lua data module approach, `action=purge` on a small set of high-traffic pages
is often sufficient — the data module's `mw.loadData()` cache is invalidated
automatically when the data module page is edited.

---

## Part 6: Decision Matrix

| Criterion | Current system | Section markers | Lua data modules | Cargo |
|---|---|---|---|---|
| Bot writes per update | O(entities) | O(entities) | O(entity types) ← | O(entities) |
| Fetch step required | Yes | Yes (light) | No ← | Yes |
| Merge/preservation logic | Complex | None ← | None ← | None ← |
| Manual override model | Implicit (in wiki) | Outside marker | Template param / override module | Template param |
| Queryable data | No | No | Via Lua (programmatic) | Yes, SQL-like ← |
| Wiki-side changes needed | None | None | Yes (Lua modules) | Yes (Cargo schema) |
| Template rename cost | High (migration code) | Low (one-time script) | None ← | None ← |
| Long-term maintenance burden | High | Low | Low ← | Medium |
| Implementation cost | (existing) | Low | Medium | Medium-high |

---

## Part 7: Recommended Path Forward

**Immediate step (independent of architecture choice)**:
Add `basetimestamp` to every `edit_page()` call. This is a one-commit change with
no architectural implications.

**Short-term (section markers)**:
Migrate to the section marker model. This removes ~1000 lines of the most fragile code
in the system (field preservation, legacy remover, multi-path merge logic in
`generate_service.py`) and replaces it with ~20 lines. The migration is:
1. Run `LegacyTemplateRemover` as a one-off against the live wiki (then delete the class)
2. Add `<!-- BOT:START ErenshorBot -->` / `<!-- BOT:END ErenshorBot -->` markers around
   the infobox block on every article page (one-off bot run)
3. Simplify `generate_service.py` to use the marker-replace logic
4. Delete `FieldPreservationHandler`, `LegacyTemplateRemover`, `PageNormalizer`
   legacy category list, and the five `_replace_*` methods

**Long-term (Lua data modules)**:
Migrate to the Lua data module pattern. This reduces bot writes from O(entities) to
O(entity types) and completely decouples the bot from article page structure. The bot
no longer needs to know anything about wikitext. Migration:
1. Build Lua display modules (port Jinja2 templates to Lua)
2. Test rendering on a representative set of pages
3. Update `Template:Item`, `Template:Character` etc. to invoke the modules
4. Bot generates and writes data modules only
5. Delete the fetch step, all merge logic, and the deploy logic for article pages

These steps can be done independently and incrementally. Section markers are a stable
intermediate state, not just a stepping stone.

---

## References

| Source | URL |
|---|---|
| Terraria wiki Module:Iteminfo | https://terraria.wiki.gg/wiki/Module:Iteminfo |
| Terraria wiki Module:Iteminfo/datagen | https://terraria.wiki.gg/wiki/Module:Iteminfo/datagen |
| Terraria wiki Module:Npcinfo/data | https://terraria.wiki.gg/wiki/Module:Npcinfo/data/doc |
| Terraria wiki Ryebot documentation | https://terraria.wiki.gg/wiki/User:Ryebot/bot |
| Melvor Idle Module:GameData | https://wiki.melvoridle.com/w/Module:GameData |
| Melvor Idle bot migration notice | https://wiki.melvoridle.com/index.php?title=Bot |
| PoE wiki PyPoE | https://www.poewiki.net/wiki/Path_of_Exile_Wiki:PyPoE |
| PoE wiki Data query API (Cargo) | https://www.poewiki.net/wiki/Path_of_Exile_Wiki:Data_query_API |
| wiki.gg Cargo (LIBRARIAN) docs | https://support.wiki.gg/wiki/Cargo |
| wiki.gg Automation docs | https://support.wiki.gg/wiki/Automation |
| Scribunto Lua reference (mw.loadData) | https://www.mediawiki.org/wiki/Extension:Scribunto/Lua_reference_manual |
| MediaWiki API:Edit (basetimestamp) | https://www.mediawiki.org/wiki/API:Edit |
| MediaWiki Manual:Creating a bot | https://www.mediawiki.org/wiki/Manual:Creating_a_bot |
| Pywikibot archivebot (section markers) | https://www.mediawiki.org/wiki/Manual:Pywikibot/archivebot.py/setup |
| wiki.gg AutoWikiBrowser (null edits) | https://support.wiki.gg/wiki/AutoWikiBrowser |
