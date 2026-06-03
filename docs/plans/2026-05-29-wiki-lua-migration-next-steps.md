# Wiki Lua/Cargo Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Python-generated wiki article wikitext with a clean Lua data-module, template/module rendering, and Cargo/LIBRARIAN query architecture.

**Architecture:** Public templates remain the stable editor-facing API. Lua modules resolve article parameters against generated game-data modules, render infoboxes/tooltips/links/categories, and store resolved values into Cargo. Python generates and deploys repo-owned modules/templates/data pages, performs null-edits, and validates output; it no longer generates or rewrites human article content after cutover.

**Tech Stack:** Python/uv/Typer, MediaWiki 1.43.x, Scribunto Lua 5.1, ParserFunctions, TemplateSandbox, ScribuntoUnit-style Lua tests, Cargo/LIBRARIAN, Docker Compose, MediaWiki API, Lefthook, StyLua, Luacheck.

---

## Source evidence

### Erenshor production wiki

- Production template inventory: https://erenshor.wiki.gg/api.php?action=query&list=allpages&apnamespace=10&aplimit=max&format=json&formatversion=2
- `Template:Item` raw source: https://erenshor.wiki.gg/index.php?title=Template:Item&action=raw
- `Template:Item/Weapon` raw source: https://erenshor.wiki.gg/index.php?title=Template:Item/Weapon&action=raw
- `Template:Item/Header` raw source: https://erenshor.wiki.gg/index.php?title=Template:Item/Header&action=raw
- `Template:Item/CargoStore` raw source: https://erenshor.wiki.gg/index.php?title=Template:Item/CargoStore&action=raw
- `Template:Character` raw source: https://erenshor.wiki.gg/index.php?title=Template:Character&action=raw
- `Template:ItemLink` raw source: https://erenshor.wiki.gg/index.php?title=Template:ItemLink&action=raw
- `Template:Quest` raw source: https://erenshor.wiki.gg/index.php?title=Template:Quest&action=raw
- `Template:AbilityLink` raw source: https://erenshor.wiki.gg/index.php?title=Template:AbilityLink&action=raw
- `Template:Zone` raw source: https://erenshor.wiki.gg/index.php?title=Template:Zone&action=raw
- `Template:MapLink` raw source: https://erenshor.wiki.gg/index.php?title=Template:MapLink&action=raw
- `Template:ArmorTable` raw source: https://erenshor.wiki.gg/index.php?title=Template:ArmorTable&action=raw
- `Template:Item` transclusions: https://erenshor.wiki.gg/api.php?action=query&list=embeddedin&eititle=Template:Item&einamespace=0%7C10&eilimit=max&format=json&formatversion=2
- `Template:Character` transclusions: https://erenshor.wiki.gg/api.php?action=query&list=embeddedin&eititle=Template:Character&einamespace=0%7C10&eilimit=max&format=json&formatversion=2
- `Template:Quest` transclusions: https://erenshor.wiki.gg/api.php?action=query&list=embeddedin&eititle=Template:Quest&eilimit=50&format=json
- `Template:AbilityLink` transclusions: https://erenshor.wiki.gg/api.php?action=query&list=embeddedin&eititle=Template:AbilityLink&eilimit=50&format=json
- `Template:Zone` transclusions: https://erenshor.wiki.gg/api.php?action=query&list=embeddedin&eititle=Template:Zone&eilimit=50&format=json
- `Template:MapLink` transclusions: https://erenshor.wiki.gg/api.php?action=query&list=embeddedin&eititle=Template:MapLink&eilimit=50&format=json

### Platform and implementation references

- Scribunto Lua reference manual: https://www.mediawiki.org/wiki/Extension:Scribunto/Lua_reference_manual
- TemplateSandbox: https://www.mediawiki.org/wiki/Extension:TemplateSandbox
- MediaWiki template limits: https://www.mediawiki.org/wiki/Manual:Template_limits
- ScribuntoUnit pattern: https://www.mediawiki.org/wiki/Module:ScribuntoUnit
- wiki.gg Cargo/LIBRARIAN guide: https://support.wiki.gg/index.php?title=Cargo&action=raw
- Cargo storing data: https://www.mediawiki.org/wiki/Extension:Cargo/Storing_data
- wiki.gg null-edit guide: https://support.wiki.gg/wiki/Null_edit
- PoE module guidance: https://www.poewiki.net/wiki/Help:Modules
- Terraria high-use data cache note: https://terraria.wiki.gg/index.php?title=Module:Iteminfo/loaddata&action=raw
- wiki.gg LuaCache README: https://raw.githubusercontent.com/wiki-gg-oss/mediawiki-extensions-LuaCache/master/README.md
- MediaWiki site CSS/JS customization: https://www.mediawiki.org/wiki/Manual:Interface/Stylesheets
- MediaWiki Gadgets extension: https://www.mediawiki.org/wiki/Extension:Gadgets
- MediaWiki XML import/export: https://www.mediawiki.org/wiki/Manual:Importing_XML_dumps

## Production constraints

1. `Template:Item` and `Template:Character` each have more than one API page of live transclusions. They are compatibility contracts, not optional examples.
2. Production has overlapping template generations: old root entity infobox templates, newer `Template:Item/*` display templates, Cargo declare/store templates, link templates, gear templates, overview row templates, docs, helper templates, navboxes, and license templates.
3. `Template:Item` exposes a broad public parameter surface: `title`, `image`, `imagecaption`, `type`, `vendorsource`, `source`, `othersource`, `questsource`, `relatedquest`, `craftsource`, `componentfor`, `relic`, `classes`, `effects`, `damage`, `delay`, `dps`, `casttime`, `duration`, `cooldown`, `effect`, `worneffect`, `proceffect`, `buffgiven`, `taughtspell`, `taughtskill`, `spelltype`, `skilltype`, `manacost`, `disposable`, `produces`, `ingredients`, `description`, `buy`, `sell`, `guaranteeddrops`, and `droprates`.
4. `Template:Character` exposes character/enemy fields including `name`, `image`, `imagecaption`, `type`, `faction`, `factionChange`, `class`, `zones`, `coordinates`, `respawn`, `spawnchance`, `level`, `experience`, `guaranteeddrops`, `droprates`, `spells`, `health`, `ac`, and resists.
5. The newer `Template:Item/*` templates prove the desired visual model, but they are still parser-function-heavy wikitext. They are not the target implementation style.
6. Cargo is useful as a query/index layer, but wiki.gg warns against centralized automated Cargo data-store pages. Generated Lua modules are the source of truth for game data; Cargo stores resolved page output.
7. MediaWiki template limits make deeply nested parser-function templates expensive and hard to debug. Public templates should invoke Lua once and avoid nested wikitext logic.
8. High-use generated data changes can invalidate many dependent pages. Do not add LuaCache now, but keep data modules sharded and keep deployment/null-edit batching explicit so LuaCache remains a future decision gate.

## Ownership model

### Repo-owned pages

The deployment system owns these pages and may overwrite them from git:

```text
Module:Erenshor/*
Module:Erenshor/*/testcases
Template:Item
Template:Character
Template:Quest
Template:Zone
Template:ItemLink
Template:AbilityLink
Template:MapLink
Template:* / CargoDeclare pages created for concrete query/index needs
Template:* / CargoStore pages created for concrete query/index needs
```

### Human-owned pages

The deployment system must not rewrite these pages during normal refreshes:

```text
Main namespace articles such as Sword of Flames, A Grizzly Bear, Ember, quests, zones, and guide pages
Human prose sections
Article-local template parameters
Manual source/quest/crafting notes
Manual images and captions
```

### Generated and fixture artifacts

Production-size Lua data is generated from the clean database and is not
committed:

```text
variants/{variant}/wiki/lua/Erenshor/Data/*.lua
variants/{variant}/wiki/lua/Erenshor/Data/**/*.lua
variants/{variant}/wiki/deploy-manifest.json
variants/{variant}/wiki/null-edit-pages.txt
```

Small local smoke data fixtures are committed separately from hand-authored
modules:

```text
wiki-dev/fixtures/modules/Erenshor/Data/*.lua
wiki-dev/fixtures/modules/Erenshor/Data/**/*.lua
```

## Page classes

### Generated data modules

Generated modules are static tables suitable for `mw.loadData()`:

```text
Module:Erenshor/Data/Items
Module:Erenshor/Data/Items/*
Module:Erenshor/Data/Characters
Module:Erenshor/Data/AbilityLinks
Module:Erenshor/Data/Quests
Module:Erenshor/Data/Zones
```

Rules:

- Return one Lua table.
- Contain only booleans, numbers, strings, and tables.
- Contain no functions, metatables, `mw` calls, or computed values.
- Entity data modules resolve records by explicit stable key only. Do not add
  page-title or display-name fallback indexes for entities; those create the
  same ambiguity stable keys exist to avoid.
- Link modules may render plain page links from explicit page/text/image
  parameters. They may use a stable key only when generated metadata such as
  canonical image/page/text is needed.
- Avoid long prose unless a display surface requires it.
- Split by domain so one data refresh does not create one large dependency blast radius.

### Source-controlled Lua modules

Use focused modules instead of one giant module:

```text
Module:Erenshor/Args        -- frame argument normalization
Module:Erenshor/Format      -- links, files, classes, currency, booleans
Module:Erenshor/Render      -- shared infobox/table rendering helpers
Module:Erenshor/Item        -- item resolve/render/store
Module:Erenshor/Character   -- NPC/enemy resolve/render/store
Module:Erenshor/Quest       -- quest resolve/render
Module:Erenshor/AbilityLink -- spell/skill/stance link resolve/render
Module:Erenshor/Zone        -- zone/map resolve/render
Module:Erenshor/Table       -- query/table display helpers
```

Rules:

- Invoke Lua through public templates, not directly from article pages.
- Keep module variables and helper functions local unless they are exported for tests or reuse.
- Resolve data once per template invocation, then render from the resolved object.
- Use `mw.html` or table-buffered string assembly for generated markup.
- Avoid calling parser functions from Lua except for Cargo declare/store and cases where MediaWiki requires parser-function compatibility.

### Public templates

Public templates are thin compatibility wrappers:

```wikitext
<includeonly>{{#invoke:Erenshor/Item|render}}</includeonly><noinclude>{{Documentation}}</noinclude>
```

They keep existing editor-facing names and parameter contracts while moving logic into Lua:

```text
Template:Item      -> Module:Erenshor/Item
Template:Character -> Module:Erenshor/Character
Template:Quest       -> Module:Erenshor/Quest
Template:Zone        -> Module:Erenshor/Zone
Template:AbilityLink -> Module:Erenshor/AbilityLink
Template:MapLink     -> Module:Erenshor/Zone
```

### Cargo/LIBRARIAN pages

Cargo declaration and store pages live in template namespace only for surfaces
with a concrete query/index requirement:

```text
Template:Item/CargoDeclare
Template:Item/CargoStore
Template:Character/CargoDeclare
Template:Character/CargoStore
Template:<Domain>/CargoDeclare  -- added only when Milestone 9 needs it
Template:<Domain>/CargoStore    -- added only when Milestone 9 needs it
```

Rules:

- Cargo is not the generated data source of truth.
- Store resolved values after article overrides have been applied.
- Declare schemas explicitly.
- Store booleans as Cargo-compatible yes/no values.
- Prefer indexed `String`, `Integer`, `Float`, and `Boolean` fields for query filters.
- Use `Text` only for display-only fields that will not be filtered or joined.
- Avoid storing wikitext unless query output specifically needs rendered wikitext.

## Resolution contract

Every public entity template resolves values in this order:

```text
article parameter, if explicitly present
else generated Lua data value
else absent
```

Parameter semantics:

- Missing parameter means use generated value.
- Non-empty parameter means override generated value.
- A documented sentinel value such as `-` means intentionally blank the resolved value.
- Empty string should not silently erase generated data unless the specific field documents blank-as-override semantics.
- Missing generated entity emits visible error output and a tracking category.

Tracking categories:

```text
Category:Pages with missing Erenshor item data
Category:Pages with missing Erenshor character data
Category:Pages with missing Erenshor quest data
Category:Pages with missing Erenshor ability data
Category:Pages with missing Erenshor zone data
Category:Pages overriding generated Erenshor data
Category:Pages using legacy Erenshor templates
Category:Pages with unresolved Erenshor template data
```

## Data flow

```text
Clean SQLite database
  -> Python Lua data generator
  -> Module:Erenshor/Data/*
  -> public template invocation on human article
  -> Module:Erenshor/<Domain> resolves article args + generated defaults
  -> rendered infobox/tooltip/link/categories
  -> #cargo_store resolved fields
  -> Cargo/LIBRARIAN query pages and overview tables
```

Python must not generate expanded article pages after production cutover.

## Local live-interface preview contract

Local validation must render repo-owned templates/modules and fixture articles
through a MediaWiki runtime that is close enough to production to catch CSS,
JavaScript, ResourceLoader gadget, skin, Scribunto, Cargo, and parser-health
breakage before TemplateSandbox or production changes.

Local preview rules:

- Match the production MediaWiki major/minor runtime surface where practical:
  MediaWiki 1.43, Classic Vector (`skin-vector-legacy`), Scribunto,
  ParserFunctions, TemplateSandbox, Cargo/LIBRARIAN compatibility, Gadgets,
  and the production article-size limit.
- Treat live interface code as a current-revision local mirror, not source
  history. The mirror is gitignored under `wiki-dev/interface/MediaWiki/` and
  is refreshed by one obvious sync command.
- Sync fixed site interface pages plus gadget source pages discovered from
  `MediaWiki:Gadgets-definition`: `Common.css`, `Vector.css`, `Common.js`,
  `Vector.js`, `Gadgets-definition`, `Sidebar`, sidebar display messages, and
  referenced `Gadget-*` CSS/JS/JSON/Vue pages.
- Print unified diffs from the existing local mirror to freshly fetched live
  content before overwriting files. Git history is not used for mirrored
  third-party interface pages.
- Mirror fixed skin assets and static assets referenced by synced CSS into
  `wiki-dev/images/` so production `/images/...` URLs, including the site logo,
  resolve against the local MediaWiki container instead of returning file-page
  HTML or broken backgrounds.
- Import mirrored interface pages as real `MediaWiki:*` pages in the local
  wiki before modules, templates, and fixture articles. Fail loudly when the
  mirror is missing instead of silently rendering without site CSS/JS.
- Keep authored local compatibility shims separate from mirrored live files.
  The committed local theme shims may provide fallback wiki.gg/platform CSS
  custom properties and must activate the same dark-theme and wiki.gg Vector
  classes that live pages apply so synced CSS drives local styling instead of
  local hard-coded table/body rules.
- Validate ResourceLoader and browser behavior for representative pages; HTML
  parse success alone is not enough for gadget-backed query surfaces such as
  DataTables.

## Completed foundation

### Milestone 1: Local MediaWiki/Scribunto/Cargo harness

**Commit:** `9501dfbe feat(wiki): add local MediaWiki Lua harness`

**Implemented files:**

```text
wiki-dev/compose.yml
wiki-dev/Dockerfile
wiki-dev/bootstrap.sh
wiki-dev/LocalSettings.extra.php
wiki-dev/README.md
wiki-dev/import_pages.py
wiki-dev/smoke_test.py
wiki-dev/fixtures/pages/Smoke_Page.wiki
wiki-dev/fixtures/smoke.tsv
wiki/modules/Erenshor/README.md
wiki/modules/Erenshor/Smoke.lua
wiki/templates/README.md
wiki/templates/Smoke.wiki
tests/unit/test_wiki_dev_harness.py
.gitignore
```

- [x] Build local MediaWiki 1.43 stack with Scribunto, ParserFunctions, TemplateSandbox, and Cargo.
- [x] Import repo-owned modules/templates into local MediaWiki.
- [x] Parse local fixture pages through the MediaWiki API.
- [x] Verify local Scribunto works on ARM64 by using system Lua 5.1 in the container.

### Milestone 2: Lefthook and Lua tooling cutover

**Commit:** `6cb352d1 chore(config): consolidate dev hooks with lefthook`

**Implemented files:**

```text
lefthook.yml
commitlint.config.cjs
.stylua.toml
.luacheckrc
tests/unit/test_development_tooling.py
package.json
pnpm-lock.yaml
pnpm-workspace.yaml
pyproject.toml
uv.lock
src/maps/package.json
README.md
.agent/skills/mod-pipeline/SKILL.md
wiki/modules/Erenshor/Smoke.lua
```

- [x] Replace split pre-commit/Husky hooks with Lefthook.
- [x] Add commitlint, StyLua, and Luacheck configuration.
- [x] Keep Ruff, mypy, unit tests, map lint, C# formatting, whitespace, and local Gitleaks gates.

### Milestone 3: Local Lua data generation

**Commit:** `377b73d2 feat(wiki): generate Lua data modules locally`

**Implemented files:**

```text
src/erenshor/application/wiki_lua/__init__.py
src/erenshor/application/wiki_lua/lua_writer.py
src/erenshor/application/wiki_lua/items.py
src/erenshor/application/wiki_lua/generation.py
src/erenshor/application/wiki_lua/validation.py
tests/unit/application/wiki_lua/fakes.py
tests/unit/application/wiki_lua/test_lua_writer.py
tests/unit/application/wiki_lua/test_items_module.py
tests/unit/application/wiki_lua/test_generation.py
tests/unit/application/wiki_lua/test_lua_validation.py
src/erenshor/cli/commands/wiki.py
tests/unit/cli/commands/test_wiki.py
```

- [x] Generate deterministic Lua table text for `mw.loadData()`.
- [x] Generate compact item data under `variants/{variant}/wiki/lua/`.
- [x] Add `erenshor wiki generate-lua` with dry-run output.
- [x] Validate generated Lua with `luac -p` when available and StyLua Lua 5.1 parsing fallback otherwise.

### Milestone 4: Production template inventory and ownership manifest

**Commits:**

```text
2c065391 feat(wiki): add MediaWiki request policy
f75d0190 feat(wiki): inventory production template ownership
```

**Implemented files:**

```text
src/erenshor/infrastructure/wiki/rate_limit.py
tests/unit/infrastructure/wiki/test_rate_limit.py
src/erenshor/infrastructure/wiki/__init__.py
src/erenshor/application/wiki_inventory/__init__.py
src/erenshor/application/wiki_inventory/api.py
src/erenshor/application/wiki_inventory/templates.py
src/erenshor/cli/commands/wiki.py
tests/fixtures/wiki_inventory/allpages-page1.json
tests/fixtures/wiki_inventory/allpages-page2.json
tests/fixtures/wiki_inventory/embeddedin-ability-page1.json
tests/fixtures/wiki_inventory/embeddedin-character-page1.json
tests/fixtures/wiki_inventory/embeddedin-item-page1.json
tests/fixtures/wiki_inventory/embeddedin-item-page2.json
tests/unit/application/wiki_inventory/test_templates.py
tests/unit/cli/commands/test_wiki.py
wiki/ownership.yml
```

- [x] Add shared MediaWiki request policy for serial non-interactive jobs.
- [x] Add bounded retry handling for HTTP `429`, API `maxlag`, API `ratelimited`, and retry-signaled HTTP `503`.
- [x] Add production template inventory client using exact MediaWiki continuation values.
- [x] Classify production templates into the ownership model.
- [x] Encode cutover-blocking public contracts in the ownership manifest.
- [x] Test classification with recorded live API fixtures instead of mocks.
- [x] Add `erenshor wiki inventory-templates --output wiki/ownership.yml`.
- [x] Generate `wiki/ownership.yml` from the live production wiki.
- [x] Verify inventory tests, Ruff format/check, and mypy.

## Implementation milestones

### Milestone 5: Build shared Lua foundations

**Commit:** `c5531eaf feat(wiki): add shared Lua template foundations`

**Files:**

```text
wiki/modules/Erenshor/Args.lua
wiki/modules/Erenshor/Format.lua
wiki/modules/Erenshor/Render.lua
wiki/modules/Erenshor/Args/testcases.lua
wiki/modules/Erenshor/Format/testcases.lua
wiki/modules/Erenshor/Render/testcases.lua
wiki-dev/fixtures/pages/Lua_Foundation_Smoke.wiki
wiki-dev/fixtures/smoke.tsv
wiki-dev/smoke_test.py
tests/unit/test_wiki_dev_harness.py
```

- [x] **Step 1: Implement argument normalization**

  `Module:Erenshor/Args` must expose helpers for parent-frame args, blank handling, trim, sentinel blanking with `-`, boolean parsing, numeric parsing, and explicit-presence checks.

- [x] **Step 2: Implement formatting helpers**

  `Module:Erenshor/Format` must expose helpers for file links, page links, class lists, currency, signed stats, resist labels, and category emission.

- [x] **Step 3: Implement render helpers**

  `Module:Erenshor/Render` must expose infobox/table helpers that avoid deeply nested wikitext and keep generated markup deterministic.

- [x] **Step 4: Add Lua testcase modules**

  Add testcases for normalization, override sentinels, formatting escaping, and deterministic markup.

- [x] **Step 5: Harden local smoke tests**

  Smoke tests must fail on `Lua error`, `Script error`, parser error markers, unresolved templates, and known template-limit error comments.

- [x] **Step 6: Verify locally**

  Import modules into local MediaWiki, run Lua testcases through `{{#invoke:...|run}}`, and parse `Lua_Foundation_Smoke.wiki`.

### Milestone 6: Replace Item templates with Lua-backed compatibility contract

**Commit:** `327d5685 feat(wiki): render item templates through Lua`

**Files:**

```text
wiki/modules/Erenshor/Item.lua
wiki/modules/Erenshor/Item/testcases.lua
wiki/modules/Erenshor/Data/Items.lua
wiki/templates/Item.wiki
wiki/templates/ItemLink.wiki
wiki/templates/Item/CargoDeclare.wiki
wiki/templates/Item/CargoStore.wiki
wiki/templates/Item/Armor.wiki
wiki/templates/Item/Aura.wiki
wiki/templates/Item/Charm.wiki
wiki/templates/Item/Consumable.wiki
wiki/templates/Item/General.wiki
wiki/templates/Item/Mold.wiki
wiki/templates/Item/SkillBook.wiki
wiki/templates/Item/SpellScroll.wiki
wiki/templates/Item/Weapon.wiki
wiki-dev/fixtures/pages/*.wiki
wiki-dev/fixtures/smoke.tsv
wiki-dev/fixtures/cargo_items.tsv
wiki-dev/fixtures/cargo_absent.tsv
wiki-dev/smoke_test.py
src/erenshor/application/wiki_lua/items.py
tests/unit/application/wiki_lua/test_items_module.py
tests/unit/test_wiki_dev_harness.py
```

- [x] **Step 1: Preserve root `Template:Item` public parameters**

  `Template:Item` accepts the production root parameter contract listed in this plan. Existing article pages do not need bot rewrites to render after cutover.

- [x] **Step 2: Resolve generated data plus article overrides**

  `Module:Erenshor/Item` resolves entity records by explicit stable item key only. Article-local parameters override generated values. The sentinel `-` intentionally blanks fields that support blanking. `Template:ItemLink` renders explicit page links by default and uses `stablekey` only when generated item metadata is requested.

- [x] **Step 3: Render item display modes**

  Lua-backed compatibility wrappers render the root infobox and item tooltip modes represented by production templates:

  ```text
  Item/Weapon
  Item/Armor
  Item/Charm
  Item/Consumable
  Item/General
  Item/Mold
  Item/Aura
  Item/SkillBook
  Item/SpellScroll
  ```

- [x] **Step 4: Replace `Template:ItemLink` behavior through Lua**

  `Template:ItemLink` preserves editor-facing behavior for page target, default image, explicit `image`, explicit `link`, explicit `text`, and `imageonly`.

- [x] **Step 5: Store resolved Cargo item rows**

  Cargo rows use resolved values after overrides. The initial schema covers overview queries without storing large prose blobs:

  ```text
  Page, StableKey, Name, Type, Slot, ItemLevel, Damage, Delay, Armor,
  BuyValue, SellValue, Image, Classes, Relic, HasProc, HasWornEffect
  ```

- [x] **Step 6: Test with production-shaped fixtures**

  Local fixture pages cover weapon, armor, charm, consumable, general item, mold, aura, skill book, spell scroll, manual item overrides, positional item links, boolean overrides, and missing data tracking category.

- [x] **Step 7: Verify locally**

  Local verification imports modules/templates/data into MediaWiki, parses every item fixture, checks parser health, validates missing-data categories, and queries Cargo item rows by `(Page, StableKey)`.

### Milestone 7: Replace Character/Enemy templates with Lua-backed compatibility contract

**Commit:** `90238beb feat(wiki): render character templates through Lua`

**Files:**

```text
wiki/modules/Erenshor/Character.lua
wiki/modules/Erenshor/Character/testcases.lua
wiki/modules/Erenshor/Data/Characters.lua
wiki/templates/Character.wiki
wiki/templates/Character/CargoDeclare.wiki
wiki/templates/Character/CargoStore.wiki
wiki-dev/fixtures/pages/A_Grizzly_Bear.wiki
wiki-dev/fixtures/pages/Captain_Rowan.wiki
wiki-dev/fixtures/pages/Lua_Character_Smoke.wiki
wiki-dev/fixtures/pages/Manual_Character_Override.wiki
wiki-dev/fixtures/pages/Missing_Character_Data.wiki
wiki-dev/fixtures/pages/Rare_Cave_Spider.wiki
wiki-dev/fixtures/smoke.tsv
wiki-dev/fixtures/cargo_characters.tsv
wiki-dev/smoke_test.py
src/erenshor/application/wiki_lua/characters.py
src/erenshor/application/wiki_lua/generation.py
src/erenshor/cli/commands/wiki.py
tests/unit/application/wiki_lua/test_characters_module.py
tests/unit/application/wiki_lua/test_generation.py
tests/unit/cli/commands/test_wiki.py
tests/unit/test_wiki_dev_harness.py
```

- [x] **Step 1: Preserve root `Template:Character` public parameters**

  `Template:Character` accepts production-shaped fields for NPCs, enemies, drops, map links, zones, coordinates, stats, resists, spells, faction, class, respawn, and spawn chance. Article parameters remain explicit overrides over generated Lua data.

- [x] **Step 2: Resolve characters from generated data plus article overrides**

  `Module:Erenshor/Character` resolves character/enemy records by explicit stable key only. Missing data emits a visible error and `[[Category:Pages with missing Erenshor character data]]`.

- [x] **Step 3: Generate map links in Lua**

  Character data includes `npc:` or `enemy:` map selectors derived from character type. Lua rendering turns those selectors into interactive map links.

- [x] **Step 4: Store resolved Cargo character rows**

  `Template:Character` declares the Cargo `Characters` table and stores resolved rows through Lua using `frame:preprocess()`. The initial query schema is:

  ```text
  Page, StableKey, Name, Type, Zones, Level, Class, Faction,
  SpawnChance, HasDrops, HasSpells, MapSelector
  ```

- [x] **Step 5: Verify locally**

  Local validation imports modules/templates/data into MediaWiki, parses representative enemy, NPC, rare, manual override, and missing-data fixtures, runs Lua testcase modules, recreates the `Characters` Cargo table, validates Cargo rows by `(Page, StableKey)`, and proves null-edit refresh behavior for Character rows.

### Milestone 8: Replace quest, ability, stance, zone, and link surfaces

**Commits:**

```text
969c7175 feat(wiki): render ability links through Lua
bdbd992b feat(wiki): render quest templates through Lua
8d1bdf24 feat(wiki): render zone templates through Lua
```

**Implemented files:**

```text
wiki/modules/Erenshor/AbilityLink.lua
wiki/modules/Erenshor/AbilityLink/testcases.lua
wiki/modules/Erenshor/Data/AbilityLinks.lua
wiki/modules/Erenshor/Quest.lua
wiki/modules/Erenshor/Quest/testcases.lua
wiki/modules/Erenshor/Data/Quests.lua
wiki/modules/Erenshor/Zone.lua
wiki/modules/Erenshor/Zone/testcases.lua
wiki/modules/Erenshor/Data/Zones.lua
wiki/templates/AbilityLink.wiki
wiki/templates/Quest.wiki
wiki/templates/Zone.wiki
wiki/templates/MapLink.wiki
src/erenshor/application/wiki_lua/ability_links.py
src/erenshor/application/wiki_lua/quests.py
src/erenshor/application/wiki_lua/zones.py
src/erenshor/application/wiki_lua/generation.py
wiki-dev/fixtures/pages/*.wiki
wiki-dev/fixtures/smoke.tsv
tests/unit/application/wiki_lua/test_ability_links_module.py
tests/unit/application/wiki_lua/test_quests_module.py
tests/unit/application/wiki_lua/test_zones_module.py
tests/unit/application/wiki_lua/test_generation.py
tests/unit/cli/commands/test_wiki.py
```

- [x] **Step 1: Replace production ability link surface**

  Production uses `Template:AbilityLink`; `Template:SkillLink`, `Template:SpellLink`, `Template:StanceLink`, and `Template:ZoneLink` do not exist and have no transclusions. `Template:AbilityLink` now invokes `Module:Erenshor/AbilityLink`, resolves spells, skills, and stances from generated Lua data, and preserves the production `image`, `link`, `text`, `imageonly`, and positional target parameters.

- [x] **Step 2: Replace quest display surface**

  `Template:Quest` now invokes `Module:Erenshor/Quest`, resolves quest records by explicit stable key only, and preserves production quest infobox parameters as article overrides. Missing generated quest data emits visible output and `[[Category:Pages with missing Erenshor quest data]]`.

- [x] **Step 3: Replace zone and map-link display surfaces**

  `Template:Zone` and `Template:MapLink` now invoke `Module:Erenshor/Zone`. Generated zone data includes type, image, map selector, and raw connection page titles. Lua renders map links, connection links, zone categories, dungeon categories, manual overrides, and missing-zone tracking. `Template:Zone` resolves zone records by explicit stable key only; `Template:MapLink` remains a page/map-selector link surface.

- [x] **Step 4: Keep helper template APIs thin**

  Helper templates stay as stable editor-facing wrappers. No absent production helper templates are invented, and no new god module is introduced.

- [x] **Step 5: Verify locally per domain**

  Local validation imports the ability-link, quest, zone, and map-link modules/templates/data into MediaWiki, parses representative article fixtures, runs Lua testcase modules, and checks missing-data tracking through the smoke harness. Cargo rows are not added for these render-only surfaces until Milestone 9 identifies concrete query/index requirements.

### Milestone 9: Replace overview/list pages with Cargo-backed query surfaces

**Planned commit:** `feat(wiki): render armor overview from Cargo`

**Files:**

```text
wiki/templates/ArmorTable.wiki
wiki/templates/ArmorTable/Row.wiki
wiki-dev/fixtures/pages/Cargo_ArmorTable_Smoke.wiki
wiki-dev/fixtures/smoke.tsv
wiki/templates/Item.wiki
wiki/templates/Item/CargoDeclare.wiki
wiki/modules/Erenshor/Item.lua
wiki/modules/Erenshor/Item/testcases.lua
tests/unit/test_wiki_dev_harness.py
```

- [ ] **Step 1: Replace the armor overview table surface**

  Production `Armor` is a bot-generated static overview table, and
  production `Template:ArmorTable` exists with no live transclusions. Reuse
  that template name as the repo-owned Cargo-backed armor overview surface.
  The human-owned `Armor` article can call `{{ArmorTable}}` during cutover
  instead of being rewritten by Python.

- [ ] **Step 2: Store overview fields in the item Cargo row**

  Item Cargo rows store resolved article values after overrides. Add the
  normal-quality armor-table stat columns and a display-only notes column to
  the existing `Items` table so Cargo queries can reproduce the current armor
  overview without reading generated Lua data directly.

- [ ] **Step 3: Render armor rows through a small row template**

  `Template:ArmorTable` issues one Cargo query against `Items` where
  `Type="Armor"`, ordered by slot and name. `Template:ArmorTable/Row` renders
  a single wikitable row from named Cargo fields. Do not add a generic
  table-helper Lua module until at least two concrete overview surfaces need
  shared behavior.

- [ ] **Step 4: Verify the query page locally**

  Recreate/import local Cargo state, parse a fixture page that calls
  `{{ArmorTable}}`, and assert expected item links, stat values, class links,
  and generated ability notes appear without parser errors.

### Milestone 10: Build clean-cut deployment and rollback pipeline

**Planned commit:** `feat(wiki): deploy repo-owned wiki pages cleanly`

**Files:**

```text
src/erenshor/application/wiki_deploy/__init__.py
src/erenshor/application/wiki_deploy/manifest.py
src/erenshor/application/wiki_deploy/pages.py
src/erenshor/application/wiki_deploy/null_edit.py
src/erenshor/application/wiki_deploy/rollback.py
src/erenshor/cli/commands/wiki.py
tests/unit/application/wiki_deploy/*.py
tests/unit/cli/commands/test_wiki.py
```

- [ ] **Step 1: Add repo-owned page deploy manifest**

  Manifest entries must include page title, source path, ownership class, sha256, old revision ID, new revision ID after deploy, and rollback text source.

- [ ] **Step 2: Add safe upload command**

  Upload repo-owned pages with edit tokens, `basetimestamp`, content hashes, and edit summaries containing variant and game build. Abort on edit conflicts.

- [ ] **Step 3: Add null-edit command**

  Null-edit affected article pages after data/template/module deploys. The page list must come from transclusion/API dependency data, not from guessed filenames.

- [ ] **Step 4: Add rollback command**

  Rollback uploads previous source for every changed repo-owned page and runs the same null-edit pass.

- [ ] **Step 5: Guard legacy commands**

  Legacy Python article generation/deployment commands must be disabled or explicitly marked legacy so they cannot run accidentally during the clean cut.

- [ ] **Step 6: Verify against local MediaWiki**

  Use the local harness to upload pages, capture revision IDs, null-edit articles, and roll back to previous revisions.

### Milestone 11: Complete local full-system verification

**Planned commit:** `test(wiki): verify local Lua Cargo cutover`

**Files:**

```text
wiki-dev/fixtures/pages/*.wiki
wiki-dev/fixtures/smoke.tsv
wiki-dev/smoke_test.py
wiki-dev/null_edit.py
wiki-dev/cargo_check.py
docs/wiki-local-validation/full-lua-cutover.md
```

- [ ] **Step 1: Import all repo-owned pages locally**

  Import every module, data module, template, Cargo declaration, Cargo store page, and fixture article into local MediaWiki.

- [ ] **Step 2: Run Lua testcases**

  Run every `Module:Erenshor/*/testcases` module and fail on any failed assertion.

- [ ] **Step 3: Parse representative article fixtures**

  Cover item subtypes, character types, quests, abilities, stances, zones, links, and overview pages.

- [ ] **Step 4: Verify Cargo rows and queries**

  Recreate local Cargo tables, null-edit fixture articles, query every table, and spot-check resolved values and override behavior.

- [ ] **Step 5: Verify parser health**

  Fail on `Lua error`, `Script error`, unresolved templates, missing data categories in pages that should resolve, parser limit errors, and unexpected tracking categories.

- [ ] **Step 6: Record local validation evidence**

  Save page titles, commands, expected rows, observed rows, and known local-vs-live differences in `docs/wiki-local-validation/full-lua-cutover.md`.

### Milestone 12: Live TemplateSandbox validation

**Planned commit:** `docs(wiki): record Lua TemplateSandbox validation`

**Files:**

```text
docs/wiki-sandbox-validation/full-lua-cutover.md
```

- [ ] **Step 1: Upload sandbox-prefixed pages**

  Upload the complete candidate set under a user sandbox prefix, including templates, modules, data modules, and Cargo pages where TemplateSandbox can exercise them.

- [ ] **Step 2: Preview real production pages through TemplateSandbox**

  Use real pages with current article content and sandboxed templates/modules. Cover item subtypes, characters, enemies, bosses, vendors, quests, abilities, stances, zones, links, and overview pages.

- [ ] **Step 3: Capture rendered differences**

  Record expected differences, unexpected differences, parser output, rendered excerpts, and screenshots where visual layout matters.

- [ ] **Step 4: Copy any wiki-side fixes back to git**

  The wiki sandbox is validation only. Every source change must land in repository files before production deploy.

- [ ] **Step 5: Record validation evidence**

  Save tested pages, sandbox prefix, result summaries, and blockers resolved in `docs/wiki-sandbox-validation/full-lua-cutover.md`.

### Milestone 13: Single coordinated production cutover

**Planned commit:** `feat(wiki): deploy Lua-backed wiki system`

**Files:**

```text
variants/{variant}/wiki/deploy-manifest.json
variants/{variant}/wiki/null-edit-pages.txt
src/erenshor/application/wiki_deploy/*.py
src/erenshor/cli/commands/wiki.py
```

- [ ] **Step 1: Freeze legacy article deployment**

  Disable old Python article-generation deploy paths before uploading production replacements.

- [ ] **Step 2: Deploy generated data modules**

  Upload all `Module:Erenshor/Data/*` pages first with game build and variant in edit summaries.

- [ ] **Step 3: Deploy display modules and public templates**

  Upload all production `Module:Erenshor/*` and `Template:*` pages with edit conflict protection.

- [ ] **Step 4: Recreate changed Cargo tables**

  Use replacement-table workflow where available. Record table recreation actions in the deploy manifest.

- [ ] **Step 5: Null-edit affected article pages**

  Null-edit every page transcluding migrated templates. Use full transclusion-derived page lists unless a smaller dependency set is proven complete.

- [ ] **Step 6: Smoke-test live pages and Cargo queries**

  Check representative live pages and query Cargo tables for row counts and spot-check values.

- [ ] **Step 7: Keep rollback manifest**

  Record previous and new revision IDs for every repo-owned page and preserve rollback text for every changed page.

### Milestone 14: Delete legacy wiki generation code

**Planned commit:** `refactor(wiki): remove legacy article generation`

**Files:**

```text
src/erenshor/application/wiki/generators/*
src/erenshor/application/wiki/services/*
src/erenshor/application/wiki/templates/*
tests/unit/application/wiki/*
tests/golden/wiki/*
src/erenshor/cli/commands/wiki.py
README.md
.agent/skills/wiki-templates/SKILL.md
```

- [ ] **Step 1: Remove Python article generators**

  Delete Jinja2 article templates, page generators, field preservation, fetch-merge article generation, and golden baselines for generated article pages.

- [ ] **Step 2: Keep API primitives that still serve the new system**

  Preserve or move MediaWiki API edit, token, diff, upload, and null-edit primitives used by the new deploy pipeline.

- [ ] **Step 3: Remove legacy CLI commands**

  Remove or replace commands that fetch/generate/deploy article wikitext. The remaining wiki CLI should generate Lua data, inventory templates, deploy repo-owned pages, null-edit pages, validate Cargo, and roll back manifests.

- [ ] **Step 4: Update documentation and skills**

  Update human docs and the `wiki-templates` skill so future work uses Lua data modules and repo-owned templates/modules only.

- [ ] **Step 5: Verify deletion**

  Run targeted unit tests, mypy, Ruff, local wiki validation, and a search confirming no production path imports deleted article-generation modules.

## Non-goals and prohibitions

- Do not run production as a mixed old/new entity-template architecture except as an explicitly approved emergency fallback.
- Do not rewrite human-owned article content during normal data refreshes.
- Do not use Cargo as the source of truth for generated game data.
- Do not use centralized Cargo data-store pages for generated game data.
- Do not reimplement the old Python fetch/merge/preserve article-generation model in Lua.
- Do not build one giant `Module:Erenshor` or one giant generated data module.
- Do not keep legacy aliases indefinitely after usage tracking categories are empty.
- Do not edit live modules/templates directly without copying changes back into git.
- Do not skip null-edit proof tests for Cargo-backed templates.
- Do not skip TemplateSandbox validation for the complete cutover set.

Proceed to **Milestone 9**: replace overview/list pages with query surfaces
backed by Cargo/LIBRARIAN where a concrete production query need exists.