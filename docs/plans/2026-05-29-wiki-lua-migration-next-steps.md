# Wiki Lua/Cargo Migration Next Steps

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the wiki export system from Python-generated article wikitext to a tested Lua data-module architecture with Cargo-backed queryability and article-local overrides.

**Architecture:** Use the modern game-wiki pattern validated by Terraria/wiki.gg and PoE: bot-generated Lua data modules are the canonical game-data source; templates/modules render article content; article template parameters override generated values; Cargo is populated from resolved template/module output so non-programmer maintainers can build overview pages with queries. Build the local dev/test harness first, prove the architecture with one low-risk local vertical, then complete and verify every vertical locally before a single coordinated production cutover.

**Tech Stack:** Python/uv/Typer, MediaWiki 1.43.x, Scribunto Lua, LIBRARIAN/Cargo, TemplateSandbox, ScribuntoUnit, Docker Compose, MediaWiki API.

---

## Evidence and constraints

This plan is grounded in these observed practices and pitfalls:

- **TemplateSandbox before production:** MediaWiki's TemplateSandbox previews pages using sandboxed templates and also works with Scribunto modules. Use it for live-wiki preflight after local validation, not as the primary dev environment. Source: https://www.mediawiki.org/wiki/Extension:TemplateSandbox
- **Test Lua modules with ScribuntoUnit:** MediaWiki's standard Lua test pattern is `Module:Name/testcases`, runnable via debug console or `{{#invoke:Name/testcases|run}}`. Source: https://www.mediawiki.org/wiki/Module:ScribuntoUnit
- **Cargo data refresh requires null-edits:** wiki.gg documents that when data is read from Lua and stored in Cargo, purging display cache is not enough; stored Cargo rows require blank/null edits. Source: https://support.wiki.gg/wiki/Null_edit
- **Large Cargo tables need replacement-table discipline:** Cargo documentation and experience reports warn that recreating tables can be slow/incomplete and large tables often need blank edits; replacement tables reduce downtime. Sources: https://support.wiki.gg/wiki/Cargo/recreating_tables and https://www.mediawiki.org/wiki/Extension:Cargo/Storing_data
- **Start with non-controversial modules:** MediaWiki transition guidance recommends phased rollout beginning with basic, low-risk templates/modules. Source: https://www.mediawiki.org/wiki/Global_templates/Transition
- **Lua data tables have sandbox limitations:** `mw.loadData()` is the right primitive for large data tables, but returned tables are read-only and must be copied before sorting/filtering. Source: https://www.mediawiki.org/wiki/Extension:Scribunto/Lua_reference_manual

## Migration principles

1. **Do not rewrite article pages during data refreshes.** Article pages become human-owned. The bot writes `Module:Erenshor/Data/*` and performs null-edits only to refresh Cargo.
2. **Prototype locally by vertical; cut production over all at once.** A small Item vertical is useful for proving the architecture in local MediaWiki, but production should not run a mixed old/new article system unless explicitly chosen as an emergency fallback.
3. **Treat wiki code as source-controlled code.** Lua modules and templates live in git and deploy through the bot with diffs and `basetimestamp`.
4. **Keep Cargo useful for non-programmers.** Overview pages, class pages, and maintainer-built tables should use Cargo queries where possible.
5. **Gate every phase with observable output.** A phase is complete only when local MediaWiki rendering, Cargo rows, live TemplateSandbox, and rollback path are proven.

## Recommended order

### Milestone 1: Build the dev/test harness first

**Why first:** The highest-risk failure mode is making wiki-side changes without a reproducible local MediaWiki environment. Best practice is not to rely on production preview alone.

**Planned commit:** `feat(wiki): add local MediaWiki Lua development harness`

**Implemented files:**
- `wiki-dev/compose.yml`
- `wiki-dev/Dockerfile`
- `wiki-dev/bootstrap.sh`
- `wiki-dev/LocalSettings.extra.php`
- `wiki-dev/README.md`
- `wiki-dev/import_pages.py`
- `wiki-dev/smoke_test.py`
- `wiki-dev/fixtures/pages/Smoke_Page.wiki`
- `wiki-dev/fixtures/smoke.tsv`
- `wiki/modules/Erenshor/README.md`
- `wiki/modules/Erenshor/Smoke.lua`
- `wiki/templates/README.md`
- `wiki/templates/Smoke.wiki`
- `tests/unit/test_wiki_dev_harness.py`
- `.gitignore`

- [x] **Step 1: Add local MediaWiki stack**

  Create `wiki-dev/compose.yml` with MediaWiki, MySQL/MariaDB, and mounted extension/source directories. The first implementation should prefer MediaWiki 1.43.x to match live `MediaWiki 1.43.6`. If exact `mediawiki:1.43` image availability differs, pin the closest official image and document the mismatch in `wiki-dev/README.md`.

- [x] **Step 2: Enable required extensions**

  Create `wiki-dev/LocalSettings.extra.php` enabling Scribunto, ParserFunctions, Cargo or LIBRARIAN-equivalent Cargo, and TemplateSandbox. Confirm `Special:Version` locally lists them.

- [x] **Step 3: Add page import helper**

  Create `wiki-dev/import_pages.py` that maps repository files to wiki page titles:

  ```text
  wiki/modules/Erenshor/Item.lua      -> Module:Erenshor/Item
  wiki/modules/Erenshor/Data/Items.lua -> Module:Erenshor/Data/Items
  wiki/templates/Item.wiki            -> Template:Item
  ```

  It must use MediaWiki API edit tokens and fail on edit errors.

- [x] **Step 4: Add local smoke test helper**

  Create `wiki-dev/smoke_test.py` that calls `action=parse` for one fixture article and verifies expected text in rendered HTML. Add a placeholder fixture page only if needed for the smoke test; do not generate production wiki content yet.

- [x] **Step 5: Verify locally**

  Run the stack, import a trivial module/template, and render a trivial test page. Expected result: local `action=parse` returns HTML containing a known marker from the module.

- [x] **Step 6: Commit**

  Commit the harness before any migration code. This keeps the testing foundation reviewable independently.

### Milestone 2: Build Lua data generation without touching production templates

**Why second:** We can validate the bot-to-Lua serialization path without changing live wiki behaviour.

**Planned commit:** `feat(wiki): generate Lua data modules from clean database`

**Files:**
- Create: `src/erenshor/application/wiki_lua/__init__.py`
- Create: `src/erenshor/application/wiki_lua/lua_writer.py`
- Create: `src/erenshor/application/wiki_lua/items.py`
- Create: `tests/unit/application/wiki_lua/test_lua_writer.py`
- Create: `tests/unit/application/wiki_lua/test_items_module.py`
- Modify: `src/erenshor/cli/commands/wiki.py` or create a new CLI module if the existing command file is too large

- [ ] **Step 1: Add failing serializer tests**

  Tests must cover escaping of quotes, backslashes, newlines, braces, unicode, nil omission, booleans, integers, floats, lists, and nested tables. Include a test that rejects unsupported values rather than serializing invalid Lua.

- [ ] **Step 2: Implement deterministic Lua writer**

  The writer must sort map keys deterministically so diffs are stable. It must emit only values accepted by `mw.loadData()`: strings, numbers, booleans, and tables.

- [ ] **Step 3: Add item data module generator**

  Generate a compact item data module from the clean DB. Do not include long prose fields unless display requires them; large text increases Scribunto memory pressure.

- [ ] **Step 4: Add CLI dry-run output**

  Add a command that writes generated Lua modules to disk under `variants/{variant}/wiki/lua/` or another gitignored variant output path. It must not deploy to the live wiki.

- [ ] **Step 5: Validate generated Lua syntax**

  Prefer `luac -p` if available. If not available, at minimum run a parser/grammar validation step and document the limitation.

- [ ] **Step 6: Run unit tests**

  Run only the new wiki Lua unit tests. Expected: all pass.

- [ ] **Step 7: Commit**

  Keep data generation separate from deployment.

### Milestone 3: Create the first complete vertical in local MediaWiki

**Recommended vertical:** Items, but only a narrow subset: one general item, one weapon with tiers, one armor with tiers, one aura/scroll/book-style tooltip item. Items are the highest-value vertical, but the initial test set must be small.

**Planned commit:** `feat(wiki): add local Item Lua module prototype`

**Files:**
- Create: `wiki/modules/Erenshor/Item.lua`
- Create: `wiki/modules/Erenshor/Item/testcases.lua`
- Create: `wiki/modules/Erenshor/Data/Items.lua` fixture or generated sample
- Create: `wiki/templates/Item.wiki`
- Create: `wiki-dev/fixtures/pages/Sword_of_Flames.wiki`
- Modify: `wiki-dev/smoke_test.py`

- [ ] **Step 1: Implement article-local override resolution**

  `Module:Erenshor/Item` must expose a testable pure function, e.g. `_resolveForTest(args, data)`, where explicit args win over data-module values. This function is the core contract.

- [ ] **Step 2: Add ScribuntoUnit tests**

  Test at minimum:
  - page title default lookup;
  - `|name=` lookup override;
  - `|image=` explicit override wins;
  - empty override can intentionally blank a field where supported;
  - missing entity emits loud error text and an error category.

- [ ] **Step 3: Render item infobox locally**

  Use `mw.html` rather than string concatenation for table markup where practical. Avoid Cargo until rendering works.

- [ ] **Step 4: Render tier/tooltips locally**

  Add rendering paths for weapon tiers, armor tiers, and one tooltip-like subtype. These replace the current Python-side `Item/Weapon`, `Item/Armor`, and subtype template generation paths.

- [ ] **Step 5: Run local parse smoke tests**

  Import pages into the local wiki and parse fixture article pages. Assert HTML contains expected values and override text.

- [ ] **Step 6: Commit**

  Do not add Cargo in the same commit as rendering. Rendering bugs and Cargo bugs need to be isolated.

### Milestone 4: Add Cargo storage and prove null-edit behaviour locally

**Planned commit:** `feat(wiki): store resolved item data in Cargo`

**Files:**
- Modify: `wiki/modules/Erenshor/Item.lua`
- Modify: `wiki/templates/Item.wiki`
- Modify: `wiki-dev/smoke_test.py`
- Create: `wiki-dev/null_edit.py` or add a mode to existing helper

- [ ] **Step 1: Declare Cargo table**

  Add the minimal `Items` table schema needed for the first overview query. Keep schema small: name, page, type, slot, damage/ac range, buy/sell, image.

- [ ] **Step 2: Store resolved values**

  Cargo rows must use resolved values after article-local overrides. If `|image=Custom.png` is on the article, Cargo must store `Custom.png`, not the raw generated default.

- [ ] **Step 3: Add local Cargo query test**

  Query the local `Items` table and assert expected row values.

- [ ] **Step 4: Add null-edit proof test**

  Implement the documented failure mode:
  1. import data module v1;
  2. parse article and assert Cargo row v1;
  3. import data module v2;
  4. assert Cargo remains v1 before null-edit;
  5. null-edit article;
  6. assert Cargo row updates to v2.

- [ ] **Step 5: Commit**

  Cargo support is not complete until this null-edit test passes.

### Milestone 5: Expand the local implementation to all wiki surfaces

**Planned commit series:** one commit per entity/display surface, all local-only until the full system passes the verification matrix.

**Files:**
- Create/modify: `wiki/modules/Erenshor/Character.lua`
- Create/modify: `wiki/modules/Erenshor/Spell.lua`
- Create/modify: `wiki/modules/Erenshor/Skill.lua`
- Create/modify: `wiki/modules/Erenshor/Stance.lua`
- Create/modify: `wiki/modules/Erenshor/Zone.lua`
- Create/modify: `wiki/modules/Erenshor/Tables.lua`
- Create/modify: `wiki/modules/Erenshor/Data/*.lua`
- Create/modify: `wiki/templates/*.wiki`
- Modify: `src/erenshor/application/wiki_lua/*.py`
- Modify: `wiki-dev/smoke_test.py`
- [ ] **Step 1: Add Character/NPC and vendor inventory support**

  Implement generated character data, `Module:Erenshor/Character`, `Template:Character`, Cargo storage, and local tests for ordinary NPCs, enemies, bosses, vendors, drop tables, and vendor inventories.

- [ ] **Step 2: Add spells, skills, and stances**

  Implement generated spell/skill/stance data, display modules, templates, Cargo storage, and local tests for class restrictions, level requirements, spell/skill overview rows, and page-local overrides.

- [ ] **Step 3: Add zones and map/connection data**

  Implement generated zone data, `Module:Erenshor/Zone`, zone templates, Cargo storage if useful for query pages, and local tests for map links, connections, and coordinates.

- [ ] **Step 4: Add overview and maintainer query pages**

  Implement local versions of Weapons, Armor, class pages, vendor listings, spell/skill overview pages, and any other high-value query pages. Prefer Cargo queries for contributor-maintained overview pages; use Lua iteration only for tightly game-derived displays.

- [ ] **Step 5: Run the full local verification matrix**

  In local MediaWiki, import every module/template/data page and parse representative pages for every entity type. Run ScribuntoUnit testcases. Query Cargo tables. Run the null-edit refresh proof for each table that stores data from Lua-backed templates.

- [ ] **Step 6: Commit local completion**

  Commit only after all local surfaces pass. No production pages are changed in this milestone.

### Milestone 6: Live TemplateSandbox validation for the complete cutover

**Planned commit:** `docs(wiki): record full Lua sandbox validation`

**Files:**
- Create: `docs/wiki-sandbox-validation/full-lua-cutover.md`

- [ ] **Step 1: Upload complete sandbox pages only**

  Upload all candidate modules/templates/data fixtures under a user sandbox prefix, not production names. The sandbox must represent the whole cutover, not only Item.

- [ ] **Step 2: Render representative production pages through TemplateSandbox**

  Use real pages with current article content and sandboxed templates/modules. Cover every migrated surface: items, weapon/armor tier pages, tooltip item types, characters, vendors, spells, skills, stances, zones, overview pages, class pages, and query pages.

- [ ] **Step 3: Capture validation evidence**

  Record page titles tested, expected differences, unexpected differences, rendered excerpts, Cargo query checks that can be validated in sandbox, and any known local-vs-live parity gaps.

- [ ] **Step 4: Fix local/source files for every issue found**

  The wiki sandbox is validation, not the source of truth. Any edits made in the wiki UI must be copied back into repo files before deployment.

- [ ] **Step 5: Commit validation notes**

  Commit the validation record. Do not promote production templates until the complete sandbox cutover has passed.

### Milestone 7: Single coordinated production cutover

**Planned commit:** `feat(wiki): deploy Lua-backed wiki data system`

**Files:**
- Modify deployment code created in earlier milestones
- Add deploy manifest output under gitignored variant/wiki deployment directory

- [ ] **Step 1: Freeze the legacy deploy path**

  Disable or clearly guard the current Python article-generation deploy command so it cannot run accidentally during or after cutover.

- [ ] **Step 2: Deploy data modules first**

  Upload all `Module:Erenshor/Data/*` pages with game build number in edit summaries.

- [ ] **Step 3: Deploy display modules and templates**

  Upload all production `Module:Erenshor/*` and `Template:*` pages with `basetimestamp` protection. Abort on any edit conflict.

- [ ] **Step 4: Recreate Cargo tables for changed schemas**

  Use replacement-table workflow where available. Do not rely on normal page refreshes to repopulate large tables.

- [ ] **Step 5: Null-edit all affected article pages**

  Run the null-edit pass for every page transcluding the migrated templates. Changed-only null-edit is acceptable only if the dependency graph is proven complete; otherwise do the full pass.

- [ ] **Step 6: Smoke-test live pages and Cargo queries**

  Check representative pages across all entity types plus overview and class pages. Query Cargo tables and verify row counts and spot-check values.

- [ ] **Step 7: Keep rollback manifest**

  Record old and new revision IDs for every changed module/template. Rollback must be uploading previous module/template text, then running the same null-edit refresh.

- [ ] **Step 8: Remove legacy generation only after production verification**

  Delete or deprecate the old Python fetch/generate/merge/deploy path after the Lua/Cargo cutover is verified live, not before.

---

## What not to do

- Do not cut production over one vertical at a time unless we explicitly choose that as an emergency fallback. Local vertical prototypes are fine; production should switch as one coordinated release after full local and sandbox verification.
- Do not make Cargo the source of truth. Cargo is the query/index layer; Lua data modules are the generated game-data source.
- Do not skip null-edit testing. Cargo will appear to work in simple tests and fail after real data updates.
- Do not edit live modules/templates directly without pulling changes back into git.
- Do not let article pages contain bot-generated expanded wikitext after cutover. Article pages should contain compact template calls plus human prose/overrides.

## Immediate next action

Implement **Milestone 1 only**: the local MediaWiki/Scribunto/Cargo development harness. Until this exists, every other migration step is speculation against production behaviour.
