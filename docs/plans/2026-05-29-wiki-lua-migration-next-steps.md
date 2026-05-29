# Wiki Lua/Cargo Migration Next Steps

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the wiki export system from Python-generated article wikitext to a tested Lua data-module architecture with Cargo-backed queryability and article-local overrides.

**Architecture:** Use the modern game-wiki pattern validated by Terraria/wiki.gg and PoE: bot-generated Lua data modules are the canonical game-data source; templates/modules render article content; article template parameters override generated values; Cargo is populated from resolved template/module output so non-programmer maintainers can build overview pages with queries. Build the local dev/test harness first, then migrate one low-risk entity vertical, then expand by entity type.

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
2. **Do not migrate all entity types at once.** Prove the architecture with one complete vertical before touching broad template surfaces.
3. **Treat wiki code as source-controlled code.** Lua modules and templates live in git and deploy through the bot with diffs and `basetimestamp`.
4. **Keep Cargo useful for non-programmers.** Overview pages, class pages, and maintainer-built tables should use Cargo queries where possible.
5. **Gate every phase with observable output.** A phase is complete only when local MediaWiki rendering, Cargo rows, live TemplateSandbox, and rollback path are proven.

## Recommended order

### Milestone 1: Build the dev/test harness first

**Why first:** The highest-risk failure mode is making wiki-side changes without a reproducible local MediaWiki environment. Best practice is not to rely on production preview alone.

**Planned commit:** `feat(wiki): add local MediaWiki Lua development harness`

**Files:**
- Create: `wiki-dev/compose.yml`
- Create: `wiki-dev/LocalSettings.extra.php`
- Create: `wiki-dev/README.md`
- Create: `wiki-dev/import_pages.py`
- Create: `wiki-dev/smoke_test.py`
- Create: `wiki/modules/Erenshor/README.md`
- Create: `wiki/templates/README.md`
- Modify: `pyproject.toml` only if new dev dependencies are required

- [ ] **Step 1: Add local MediaWiki stack**

  Create `wiki-dev/compose.yml` with MediaWiki, MySQL/MariaDB, and mounted extension/source directories. The first implementation should prefer MediaWiki 1.43.x to match live `MediaWiki 1.43.6`. If exact `mediawiki:1.43` image availability differs, pin the closest official image and document the mismatch in `wiki-dev/README.md`.

- [ ] **Step 2: Enable required extensions**

  Create `wiki-dev/LocalSettings.extra.php` enabling Scribunto, ParserFunctions, Cargo or LIBRARIAN-equivalent Cargo, and TemplateSandbox. Confirm `Special:Version` locally lists them.

- [ ] **Step 3: Add page import helper**

  Create `wiki-dev/import_pages.py` that maps repository files to wiki page titles:

  ```text
  wiki/modules/Erenshor/Item.lua      -> Module:Erenshor/Item
  wiki/modules/Erenshor/Data/Items.lua -> Module:Erenshor/Data/Items
  wiki/templates/Item.wiki            -> Template:Item
  ```

  It must use MediaWiki API edit tokens and fail on edit errors.

- [ ] **Step 4: Add local smoke test helper**

  Create `wiki-dev/smoke_test.py` that calls `action=parse` for one fixture article and verifies expected text in rendered HTML. Add a placeholder fixture page only if needed for the smoke test; do not generate production wiki content yet.

- [ ] **Step 5: Verify locally**

  Run the stack, import a trivial module/template, and render a trivial test page. Expected result: local `action=parse` returns HTML containing a known marker from the module.

- [ ] **Step 6: Commit**

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

### Milestone 5: Live TemplateSandbox validation only after local tests pass

**Planned commit:** `docs(wiki): record Item Lua sandbox validation`

**Files:**
- Create: `docs/wiki-sandbox-validation/item-lua-prototype.md`

- [ ] **Step 1: Upload sandbox pages only**

  Upload candidate pages under a user sandbox prefix, not production names.

- [ ] **Step 2: Render representative production pages through TemplateSandbox**

  Use real pages with current article content and sandboxed templates/modules.

- [ ] **Step 3: Capture validation evidence**

  Record page titles tested, expected differences, unexpected differences, and screenshots or parsed-output excerpts where helpful.

- [ ] **Step 4: Fix local/source files for any issues**

  The wiki sandbox is validation, not the source of truth. Any edits made in the wiki UI must be copied back into repo files before deployment.

- [ ] **Step 5: Commit validation notes**

  Commit the validation record. Do not promote production templates without it.

### Milestone 6: Production cutover for Item only

**Planned commit:** `feat(wiki): deploy Lua-backed Item template`

**Files:**
- Modify deployment code created in earlier milestones
- Add deploy manifest output under gitignored variant/wiki deployment directory

- [ ] **Step 1: Deploy data modules first**

  Upload `Module:Erenshor/Data/Items` with build number in edit summary.

- [ ] **Step 2: Deploy display module and template**

  Upload `Module:Erenshor/Item` and `Template:Item` with `basetimestamp` protection.

- [ ] **Step 3: Recreate Cargo table if schema changed**

  Use replacement table workflow where available. Do not rely on normal page refreshes to repopulate a large table.

- [ ] **Step 4: Null-edit affected item pages**

  Use changed-only null-edit if the generator can compute affected pages. Otherwise full item page null-edit pass is acceptable but must be rate-limited.

- [ ] **Step 5: Smoke-test live pages and Cargo queries**

  Check representative item pages plus Weapons/Armor overview queries if they depend on `Items` Cargo.

- [ ] **Step 6: Keep rollback manifest**

  Record old and new revision IDs for every changed module/template.

### Milestone 7: Expand by vertical, not by infrastructure layer

After Item succeeds end-to-end, repeat complete vertical migrations:

1. Character/NPC pages and vendor inventories
2. Spells/abilities
3. Skills and stances
4. Zones and connections
5. Overview pages (weapons, armor, classes, vendors, spells/skills)

Each vertical must include: generated Lua data, display module, override contract,
Cargo schema/storage, local tests, TemplateSandbox validation, production cutover,
null-edit, rollback manifest.

---

## What not to do

- Do not port every current Jinja2 template to Lua before anything is deployed. That recreates the current big-bang risk.
- Do not make Cargo the source of truth. Cargo is the query/index layer; Lua data modules are the generated game-data source.
- Do not skip null-edit testing. Cargo will appear to work in simple tests and fail after real data updates.
- Do not edit live modules/templates directly without pulling changes back into git.
- Do not let article pages contain bot-generated expanded wikitext after cutover. Article pages should contain compact template calls plus human prose/overrides.

## Immediate next action

Implement **Milestone 1 only**: the local MediaWiki/Scribunto/Cargo development harness. Until this exists, every other migration step is speculation against production behaviour.
