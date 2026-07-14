---
title: Standard Item Quality Cutover and Article Rewrite
type: plan
status: implemented
created: 2026-07-14
parent: 2026-07-13-planar-march-release-refresh
archived: 2026-07-14
---

# Standard Item Quality Cutover and Article Rewrite

This plan replaces the base item-quality label with **Standard** throughout the maintained pipeline and ships a human-written Planar March Item Quality article.

## File map

### Export and data contract

- Modify `src/Assets/Editor/ExportSystem/AssetScanner/Listener/ItemListener.cs`: emit `Standard` for runtime quality ID 1.
- Modify `src/Assets/Editor/Database/ItemStatsRecord.cs`: document the canonical quality labels stored in raw SQLite.
- Regenerate `variants/main/erenshor-main-raw.sqlite` and `variants/main/erenshor-main.sqlite` through the canonical extract pipeline. These are generated, gitignored outputs and must not be edited directly.

### Python consumers

- Modify `src/erenshor/shared/game_constants.py`: make `Standard` the only tier-0 string key.
- Modify `src/erenshor/infrastructure/database/repositories/items.py`: order `Standard` first and remove the `Normal` string path.
- Modify `src/erenshor/domain/entities/item_stats.py`: document the canonical quality field.
- Modify `src/erenshor/domain/entities/__init__.py`: use the canonical label in domain documentation.
- Modify `src/erenshor/domain/enriched_data/item.py`: use the canonical label in enriched-item documentation.
- Modify `tests/unit/infrastructure/database/repositories/test_items.py`: defend progression ordering from Standard through Ascended.

### Wiki generation

- Modify `src/erenshor/application/wiki/generators/sections/item.py`: select Standard base rows for parameterized equipment tooltips.
- Modify `src/erenshor/application/wiki/generators/pages/armor_overview.py`: select Standard rows for base armor values.
- Modify `src/erenshor/application/wiki/generators/pages/weapons_overview.py`: select Standard rows for base weapon values.
- Modify `src/erenshor/application/wiki_lua/items.py`: summarize Standard rows in generated Lua item data.
- Modify `src/erenshor/application/wiki/services/generate_service.py`: describe the Standard/base rendering contract.
- Modify `tests/unit/application/wiki/generators/test_item_section_generator.py`: use Standard source rows.
- Modify `tests/unit/application/wiki_lua/test_items_module.py`: verify Standard source rows and progression order.
- Modify `tests/unit/application/generators/test_template_generator_base.py`: use Standard quality contexts.
- Regenerate `variants/main/wiki/generated/` and local Lua data through `uv run erenshor wiki generate`. These outputs are generated and must not be edited directly.

### Lua quality and tooltip core

- Modify `wiki/modules/Erenshor/Item/Quality.lua`: make Standard the canonical runtime-ID-1 name and remove Normal aliases.
- Modify `wiki/modules/Erenshor/Item.lua`: resolve Standard base rows without `Normal` or numeric-`0` compatibility.
- Modify `wiki/modules/Erenshor/Item/Tooltip.lua`: order, validate, select, and emit Standard quality cards.
- Modify `wiki/modules/Erenshor/Item/ParameterizedTooltip.lua`: use Standard/base terminology.
- Modify `wiki/modules/Erenshor/Item/testcases.lua`: verify Standard variants, metadata, defaults, and obsolete-label rejection.

### Item links and contributor documentation

- Modify `wiki/modules/Erenshor/Link/testcases.lua`: verify explicit and default Standard metadata and rejection of Normal aliases.
- Modify `wiki/templates/ItemLink/doc.wiki`: list Standard, document the Standard default, and update TemplateData.
- Modify `wiki/templates/ItemTooltip.wiki`: describe Standard/base parameter input.
- Inspect `wiki/templates/Gear/Slot.wiki`: retain its existing Blessed/Ascended contract unless a focused test proves Standard metadata can leak an obsolete label. Do not broaden its supported sparkle set without a real green asset.

### Hover gadget

- Modify `wiki/gadgets/item-tooltips.js`: default to Standard, select tier 0 as Standard, and reject Normal aliases.
- Modify `wiki/gadgets/erenshor.css`: use Standard in quality-related presentation comments.
- Keep `wiki/gadgets/gadgets.toml` unchanged unless the interface deployment manifest requires a source-list change.

### Sheets

- Modify `src/erenshor/application/sheets/queries/items.sql`: order Standard before Improved qualities.
- Regenerate `tests/golden/sheets/items.csv` through `uv run erenshor golden capture`. Do not edit the golden CSV directly.
- Do not deploy Google Sheets without separate authorization.

### Manual wiki page

- Rewrite the manual production page `Item Quality` through a revision-guarded MediaWiki edit.
- Use `http://localhost:8088/index.php/Item_Quality` for the complete local preview.
- Keep the transient draft outside repository-owned wiki source because `Item Quality` is not in the repo-page manifest.

## Tasks

### Task 1: Cut over the Unity export label

**Files:**
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/Listener/ItemListener.cs`
- Modify: `src/Assets/Editor/Database/ItemStatsRecord.cs`

- [x] Change runtime quality ID 1 from `Normal` to `Standard` in the raw item-stats export contract. Keep runtime IDs and all numerical formulas unchanged.
- [x] Run `uv run erenshor extract export`.
  Verification: query `variants/main/erenshor-main-raw.sqlite` for distinct `item_stats.quality` values.
  Expected: `Standard`, Improved +1 through Improved +5, Blessed, and Ascended are present as applicable, and no item-quality row contains `Normal`.
- [x] Commit the exporter change independently.
  Message: `fix(export): emit Standard item quality`

### Task 2: Cut over Python's quality contract

**Files:**
- Modify: `src/erenshor/shared/game_constants.py`
- Modify: `src/erenshor/infrastructure/database/repositories/items.py`
- Modify: `src/erenshor/domain/entities/item_stats.py`
- Modify: `src/erenshor/domain/entities/__init__.py`
- Modify: `src/erenshor/domain/enriched_data/item.py`
- Modify: `tests/unit/infrastructure/database/repositories/test_items.py`

- [x] Replace the tier-0 string key and repository ordering case with `Standard`. Remove `Normal` and numeric-`0` item-quality compatibility rather than retaining aliases.
- [x] Update domain field descriptions without changing persisted runtime IDs or progression ranks.
- [x] Run `uv run pytest tests/unit/infrastructure/database/repositories/test_items.py`.
  Expected: the repository returns Standard, Improved +1 through +5, Blessed, and Ascended in progression order, and the test fixture contains no obsolete base label.
- [x] Run `uv run erenshor extract code-facts` followed by `uv run erenshor extract build`.
  Verification: query the clean `item_stats` table for distinct quality values and tier counts.
  Expected: Standard replaces Normal without changing row counts or numerical stats.
- [x] Commit the Python contract independently.
  Message: `fix(pipeline): consume Standard item quality`

### Task 3: Cut over wiki generators

**Files:**
- Modify: `src/erenshor/application/wiki/generators/sections/item.py`
- Modify: `src/erenshor/application/wiki/generators/pages/armor_overview.py`
- Modify: `src/erenshor/application/wiki/generators/pages/weapons_overview.py`
- Modify: `src/erenshor/application/wiki_lua/items.py`
- Modify: `src/erenshor/application/wiki/services/generate_service.py`
- Modify: `tests/unit/application/wiki/generators/test_item_section_generator.py`
- Modify: `tests/unit/application/wiki_lua/test_items_module.py`
- Modify: `tests/unit/application/generators/test_template_generator_base.py`

- [x] Make every base-row selector require `Standard`. Remove `Normal` and numeric-`0` fallbacks.
- [x] Update generator contracts and fixtures so generated equipment pages and Lua summaries receive Standard rows.
- [x] Run `uv run pytest tests/unit/application/wiki/generators/test_item_section_generator.py tests/unit/application/wiki_lua/test_items_module.py tests/unit/application/generators/test_template_generator_base.py`.
  Expected: parameterized tooltip contexts, overview base values, and Lua summaries all use Standard and preserve existing numerical output.
- [x] Run `uv run erenshor wiki generate`.
  Verification: generated equipment page parsing succeeds, the Weapons and Armor overview tables retain their values, and generated quality metadata contains Standard with no Normal alias.
- [x] Commit the generator change independently.
  Message: `fix(wiki): generate Standard item quality`

### Task 4: Cut over the Lua quality API

**Files:**
- Modify: `wiki/modules/Erenshor/Item/Quality.lua`
- Modify: `wiki/modules/Erenshor/Item.lua`
- Modify: `wiki/modules/Erenshor/Item/Tooltip.lua`
- Modify: `wiki/modules/Erenshor/Item/ParameterizedTooltip.lua`
- Modify: `wiki/modules/Erenshor/Item/testcases.lua`

- [x] Rename the canonical tier-0 quality to Standard in the registry, ordering, fallback, error, and rendered metadata paths.
- [x] Reject `Normal`, `normal`, and numeric `0` as item-quality inputs. Continue accepting the existing case-insensitive spellings of current canonical labels only if the module's tests already establish that contract.
- [x] Update the Scribunto test fixtures to expect eight cards in this order: Standard, Improved +1 through Improved +5, Blessed, Ascended.
- [x] Run `uv run python wiki-dev/import_pages.py`.
  Verification: parse `Module:Erenshor/Item/testcases` in the local MediaWiki harness.
  Expected: all testcase assertions pass, Standard metadata occurs once per quality set, and obsolete base-label requests fail fast.
- [x] Commit the Lua core independently.
  Message: `fix(wiki): canonicalize Standard item quality`

### Task 5: Cut over ItemLink and template documentation

**Files:**
- Modify: `wiki/modules/Erenshor/Link/testcases.lua`
- Modify: `wiki/templates/ItemLink/doc.wiki`
- Modify: `wiki/templates/ItemTooltip.wiki`
- Inspect: `wiki/templates/Gear/Slot.wiki`

- [x] Update ItemLink's supported-quality list, omission behavior, examples, and TemplateData to Standard.
- [x] Add focused link tests proving omitted quality and explicit `quality=Standard` emit canonical Standard metadata, while `quality=Normal` fails.
- [x] Parse representative `ItemLink` and `Gear/Slot` calls locally.
  Expected: Standard links resolve to tier 0, Blessed and Ascended gear slots retain their icon overlays, and no template emits obsolete quality metadata.
- [x] Commit the link and template contract independently.
  Message: `docs(wiki): document Standard item quality`

### Task 6: Cut over the hover gadget

**Files:**
- Modify: `wiki/gadgets/item-tooltips.js`
- Modify: `wiki/gadgets/erenshor.css`

- [x] Replace the gadget's duplicated tier-0 canonical name, request default, and single-card selection branches with Standard.
- [x] Keep the tooltip interaction contract unchanged: hover or keyboard focus opens the requested card, pointer exit closes it, Escape closes it, and touch remains an ordinary link.
- [x] Run `node --check wiki/gadgets/item-tooltips.js`.
  Expected: JavaScript parses successfully.
- [x] Import the gadget into local MediaWiki and test omitted quality, explicit Standard, every Improved tier, Blessed, Ascended, invalid Normal, pointer exit, keyboard focus, Escape, and touch suppression.
  Expected: each valid request selects exactly one matching card, and Normal never resolves as a quality.
- [x] Commit the client cutover independently.
  Message: `fix(wiki): select Standard item tooltips`

### Task 7: Cut over Sheets ordering

**Files:**
- Modify: `src/erenshor/application/sheets/queries/items.sql`
- Regenerate: `tests/golden/sheets/items.csv`

- [x] Replace the base-quality ordering branch with `Standard`.
- [x] Run `uv run erenshor golden capture` and review the complete diff.
  Expected: quality labels change from Normal to Standard, progression ordering stays unchanged, and no unrelated sheet or pipeline baseline changes.
- [x] Run the focused sheet-query tests that cover `items.sql`.
  Expected: the items query emits Standard first and retains all item/stat rows.
- [x] Commit the Sheets change and its regenerated baseline independently.
  Message: `fix(sheets): order Standard item quality`

### Task 8: Rewrite for human readers and review by persona

**Surfaces:**
- Local page: `http://localhost:8088/index.php/Item_Quality`
- Production page: `https://erenshor.wiki.gg/wiki/Item_Quality`

- [x] Rewrite the lead and section introductions as direct player guidance. Avoid implementation words such as `candidate`, `conditional`, `validator`, `runtime`, and `record`. Avoid contrast filler shaped like “it is not X, it is Y.” Do not frame the page around the Planar March patch release — a single reference link is sufficient.
- [x] Use this reading order: quality ladder, drop chances, player upgrade recipes, SimPlayer upgrades, plain-language stat effects, exact formulas, worked item example, sources.
- [x] Introduce drop odds with a concrete sentence a player can visualize, such as “When a weapon or armor piece appears as enemy loot, the game gives it one of these qualities.” Do not add a paragraph explaining conditional probability unless a reader action depends on it.
- [x] Keep exact mechanics available without front-loading them: 94% Standard, 5% total Improved with exact sub-tier odds, 1% Blessed, Merging Vessel progression, Ancient Coal, Flame Well odds and consumption, Ascended recipe, Inert Diamond reset, SimPlayer routes, rounding, all field formulas, zero-base behavior, and the Stinging Bracer comparison.
- [x] Present exact formulas in narrow two-column tables or a collapsed reference section. Explain each symbol once, adjacent to the formulas, and use Standard item values in worked language.
- [x] Make the worked comparison readable without hover. Keep hover and keyboard focus as enhancements, and tell touch readers that the item page contains all quality cards.
- [x] Render the page locally and obtain independent reviews from these reader perspectives: first-time player, experienced optimizer, mobile/touch reader, accessibility-focused keyboard reader, and wiki contributor. Each review must identify concrete confusing sentences, missing player actions, and unnecessary caveats.
- [x] Resolve every material persona finding, then repeat local desktop and mobile rendering plus the quality-link interaction smoke test.
  Expected: no parser errors, no broken quality-name images, no obsolete Normal label, no desktop or page-level mobile overflow, and no unexplained implementation terminology.

### Task 9: Deploy atomically and verify production

**Repo-owned deployment surfaces:**
- `Module:Erenshor/Item/Quality`
- `Module:Erenshor/Item`
- `Module:Erenshor/Item/Tooltip`
- `Module:Erenshor/Item/ParameterizedTooltip`
- `Template:ItemLink/doc`
- `Template:ItemTooltip`
- `MediaWiki:Gadget-item-tooltips.js`
- `MediaWiki:Gadget-erenshor.css`

**Manual deployment surface:**
- `Item Quality`

- [x] Run revision-aware dry runs for the exact repo-owned module/template page list and the interface gadget. Review every diff before editing production.
- [x] Deploy repo-owned Lua modules and templates first, then the interface gadget, using separate deployment commands and summaries so each production cutover remains independently auditable.
- [x] Purge the changed modules, templates, gadget, generated equipment transclusions, and local browser ResourceLoader cache.
- [x] Fetch a fresh `Item Quality` production snapshot. Abort if revision 40125 has changed without reconciling the new source. Apply the reviewed article with `MediaWikiClient.safe_edit_page` and a specific edit summary.
- [x] Verify production source and rendered behavior: Standard appears in the canonical list and all eight item cards, `quality=Standard` works, `quality=Normal` returns a clear error, omitted ItemLink quality selects Standard, generated equipment pages retain their stats, Recommended Gear Blessed/Ascended tooltips still work, and the Item Quality article is readable on desktop and mobile.
- [x] Search maintained repo sources and the production API for item-quality uses of `Normal` or numeric `0`.
  Expected: no obsolete base-quality path remains. Unrelated uses such as stance names, normal vectors, ordinary prose, and difficulty labels remain unchanged.
- [x] Record the completed deployment in the plan, run `omp-plans complete 2026-07-14-standard-item-quality-cutover`, and commit the archived plan separately.
  Message: `docs(plans): complete Standard quality cutover`
