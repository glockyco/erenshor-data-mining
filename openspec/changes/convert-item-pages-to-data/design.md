# Design

## Context and Evidence

This is the item conversion slice of `adopt-data-backed-wiki/design.md`, especially D1, D2, D3 and D8. `unify-item-provenance` supplies authoritative facts and migrates their selection for every consumer before this conversion starts. The two changes are separate because source correctness benefits all consumers without requiring a wiki cutover, while article conversion has its own editorial and production approval gates.

Current executing interfaces establish the migration boundary:

- `src/erenshor/application/wiki_lua/items.py:192-220,354-403` generates an index and kind-based shards. Records include stats, effects and provenance but omit the item database index and approved render catalog used by articles. Conversion must close that field inventory, not merely reuse a partial record.
- `src/erenshor/application/wiki/generators/pages/entities.py:199-227` assembles item stats, effects, sources and renders. Its source selection is replaced by the prerequisite change.
- `src/erenshor/application/wiki/generators/sections/item.py:632-650` writes generated source fields and starts `othersource` empty.
- `src/erenshor/application/wiki/generators/field_preservation.py:339-346` preserves `othersource` and merges `type`, `questsource`, and `relatedquest`. Those editor additions must not disappear.
- `wiki/templates/Item.wiki:17-28` renders parameter-based source fields. It remains parameter-only.
- `wiki/templates/ItemTooltip.wiki:1-5` invokes `Erenshor/Item/ParameterizedTooltip`. `wiki/modules/Erenshor/Item/ParameterizedTooltip.lua:317-333` emits quality wrappers.
- `wiki/gadgets/item-tooltips.js:4,369-386,418-459` finds semantic links and reads rendered `.item-tooltip` and quality metadata from the target article. Data-backed conversion must preserve that DOM contract.
- `tests/system/wiki/test_wiki_item_tooltip_layout.py:44-68` exercises centered effect rows and historical-notice/tooltip layout.

A read-only query of the current clean database found 1,531 item roots on 1,523 nonblank item pages. These are not a fixed conversion count. The run inventory must come from actual current generated identities plus fetched live roots, including multi-root pages. The often-repeated 958-page estimate is not a migration acceptance count.

## Goals and Non-Goals

An ordinary item article contains one compact identity call per entity plus editor-owned additions and prose. A game update changes data, not copied facts or repeated explanatory strings. The full rendered item surface, including details used by hover, remains available. This change does not convert Character, Ability, Stance, Zone or Quest pages, remove their generators, modify legacy template semantics, or publish a guide release.

## Decisions

### 1. A new public template and explicit ownership

The new article root is `{{ItemData|stablekey=item:...}}`. `Template:ItemData` calls `Module:Erenshor/ItemData`, whose public `render(frame)` resolves the key and delegates to item infobox, quality/details and provenance renderers. Missing, ambiguous, wrong-kind and unknown keys produce a visible diagnostic and tracking category, not a name lookup or silent parameter fallback.

Data owns name and aliases, item kind, stats and all quality variants, prices/flags, required slot and classes, click/proc/worn/teaching effects and conditions, lore/book title, recipes/materials/rewards, sources and uses, image file titles, `item_db_index`, lifecycle notices and build identity. Emit full picture titles from the existing filename helper. Approved renders and sex-specific variants come from the catalog. Missing images follow the existing no-broken-file-link policy. Item identity and acquisition variants are not collapsed to a page title.

Only these article parameters carry editor input:

| Parameter | Meaning |
|---|---|
| `type` | Additional editorial classifications, appended to the data kind without replacing it. |
| `questsource` | Additional editor-described reward relationships, shown as editorial additions without replacing canonical rewards. |
| `relatedquest` | Additional editor-described quest associations, shown as editorial additions without replacing canonical requirements. |
| `othersource` | Transitional editor-owned source note/prose, visibly separate from canonical sources until incorporated through the pipeline. |

The exact values of those fields survive conversion. An entry already represented by data is tracked for review, not silently deleted. No parameter can override a name, price, stat, effect, source chance, condition, lifecycle state, icon or render. Unknown factual parameter names are ignored for rendering and place the page in a documented tracking category. Identity `stablekey` is required and is not an override.

Use `Category:Item data calls with unsupported parameters`, `Category:Item data notes covered by game data`, and `Category:Item data calls with invalid identities`. Add repository-owned category explanations with the responsible editor action. Arbitrary freeform notes are preserved verbatim and are not guessed into factual relationships. For new machine-checkable notes, provide `Template:ItemData/SourceNote` with explicit `item`, `kind`, `source` stable identity and `text`. Its module compares that identity with canonical acquisitions and emits the covered-note category when data already covers it. It never mutates or replaces a canonical fact. Legacy notes can remain freeform until reviewed.

The source-note helper exists only to meet the explicit editor-note tracking requirement. It is not a second provenance input, generic query template, or replacement for a canonical source row. Reuse an existing equivalent helper if one is present when implementation starts.

### 2. Versioned data and bounded loading

Keep existing `Module:Erenshor/Data/Items` readers working. Publish the conversion schema under `Module:Erenshor/Data/ItemsV2` and versioned child shards rather than changing live module structure in place. The index maps stable keys to deterministic shards. Add a small new-version relation index only where needed, rather than loading all characters, zones or acquisitions to render one item. One resolved item loads its own entity shard and the needed provenance shards. Avoid duplicating the complete provenance dataset across every entity shard.

The prerequisite's canonical acquisition/use IDs, typed conditions, ranges, quantities, source/copy identities, locations, dispositions and build identity are serialized, not reselected. `wiki_lua/items.py` remains a serializer, not a renderer or prose generator. Include the item database index and all fields required to replace item companions. Shared explanations and labels live once in `ItemData` modules/templates. They do not become 958 or any other number of copied article strings. Data facts remain available to documented editor-written modules.

Render for ordinary visitors using the existing concise vocabulary. Shared wording means one maintained label, not a longer disclaimer repeated everywhere. Keep "Any enemy" and a short annotation such as "At the default loot rate." when applicable. State actionable quest, furnishing, time and player-level requirements briefly. Preserve internal distinctions in data and tests without exposing source-stage enums, ownership-replacement explanations, independent-roll paragraphs or unresolved research notes as public UI.

### 3. Measure actual limits before fixing shard size

Generation enforces the configured UTF-8 page-size limit. That alone does not establish Scribunto feasibility. Build a reproducible corpus from all actual item roots with the shipped candidate modules, not only `wiki-dev` fixtures. Find the largest item record, most acquisition variants, most effects, all-quality equipment, longest recipe/source lists, every multi-root page and a page with many item links. Measure cold text parses and repeated parses through local MediaWiki `action=parse` with `prop=limitreportdata|text|categories`, plus the host's available Scribunto CPU/memory measurements. Record Lua memory and CPU, expensive function count, expanded wikitext size, post-expand include size, loaded shards and UTF-8 bytes. Query the host for configured limits rather than hard-code wiki.gg defaults.

Set measured shard and parse budgets with at least 25 percent headroom under each observed enforcing limit. If a host does not expose a metric, record that limitation and use its real parse failure/limit report boundary, not a fabricated measurement. Repeat the heaviest corpus with generated production-scale data in the local stack and perform production read-only TemplateSandbox/text-parse checks against the staged modules once available. Production writes needed to make new data dependencies available remain a separately approved first pass.

If a budget fails, reshard by deterministic stable-key buckets or split detail/provenance loads and measure again before conversion. Do not hide source rows, remove quality details, round probabilities to zero or lazily omit canonical facts to make a parse succeed. Lua render cost and source completeness are joint gates.

### 4. Preserve details and hover behavior

The renderer resolves data once and supplies render-only arguments to reusable details functions. `ParameterizedTooltip` may be refactored into a render-from-record entry point with its existing public parameter entry point unchanged. A wiki module calling a formatter is acceptable. An article supplying copied data parameters is not.

Preserve `.item-tooltip`, `.item-tooltip-quality-set`, `.item-tooltip-quality`, `data-erenshor-quality`, canonical quality names, effect/details adjacency, full file titles, existing semantic-link selectors and any stable identity metadata required to select a card on a multi-item page. Keep all item kinds, lore, teaching/click/worn effects, class restrictions, improved +1 through +5, Blessed and Ascended variants. Spell details already shown below an item remain the details surface. Do not add right-click-for-details behavior.

Compare visible text, categories, semantic links, images and structured tooltip fields between each live legacy page and its candidate conversion. Classify intended factual corrections from canonical provenance separately from rendering regressions. Do not normalize away missing source conditions or quantities. Browser-check representative equipment and non-equipment, no-image and historical items, multi-root identity selection, hover and keyboard/coarse-pointer behavior, effect details, centered labels, quality navigation and notice/infobox layout. Capture local rendered screenshots for approval.

### 5. Guarded migration and editorial preservation

Extend the existing guarded article edit/deploy path. It owns no permanent article copy. The migration inventory records title, fetched revision/hash, all legacy roots and stable identities, companion ownership, editor fields and prose hashes. Resolve unkeyed roots only when the existing matching rules yield a unique identity. Ambiguous roots, unmatched roots, unexpected companions, duplicate identity calls or conflicting ownership stop that page and the conversion batch until reviewed. Every exception is accounted for. A page is not declared converted because one of several roots converted.

Generate a candidate compact call for each matched root and retain the four editor-owned values and all text outside owned roots/companions. Remove only bot-generated companions proven to belong to that root. Do not delete a hand-written tooltip or source section on resemblance alone. Where merged fields contain old generated contributions, retain them rather than reconstruct an editor's intent from a current database. Optionally remove exact proven bot-only contributions only when the fetched revision/baseline records prove ownership and the dry run shows the removal. Otherwise flag duplicates for editorial review. Changed target syntax must not erase additional editor text.

Run a full legacy-vs-candidate production `action=parse` comparison for every item page as required by the governing plan. Save complete reports, not only a feature-selected subset. A full dry run lists visible text/category changes, preserved editor additions, removed owned companions, ambiguous/unmatched identities, parse errors and Lua-limit measurements. Read it in full. Incomplete dependency parses are provisional and do not approve article conversion.

Live writes use the fetched base revision immediately before each write. A changed/deleted page is a conflict and requires fetch/regeneration, not force overwrite. Before the first write persist all planned titles/base revisions and old text. Record each successful new revision in the manifest. An interrupted pass can roll back only the pages actually written and must be resolved before another pass. Rollback refuses later edits and restores original legacy roots, companions, editor fields and prose. Canary rollback must be exercised before a broad conversion.

### 6. Reconciliation and deletion gate

After conversion, `wiki generate` creates compact item stubs for new identities and reconciles only identity membership changes on an existing page. It does not refresh existing item facts or rewrite editor fields/prose. Deleted or renamed identities use existing lifecycle workflows. Store no default legacy item generation path or fallback after cutover.

Delete the item-specific full-article generator, source/section formatting now replaced by Lua, `templates/item.jinja2`, item companions that have no remaining reader, and Item-specific merge/validation branches only after all current generated item identities have a guarded disposition, full parse and browser gates pass, and rollback manifests are usable. Search callers before deleting any shared item formatter because legacy hand-written templates remain supported. `Template:Item` and compatible shared tooltip entry points stay if still used by editors. The generic merge engine and non-item templates stay for later conversions. Retain the manifest-driven rollback command and old publication bytes during the rollback window so rollback does not require restoring a legacy generator.

Remove old generated data module pages only after every reader has migrated and after the rollback window is deliberately closed. The bot cannot delete pages. Produce an administrator deletion list with no-live-reader and rollback-window conditions. Do not remove a module still used by semantic links, views, editor modules or legacy article rollbacks.

## Interfaces, Tests and Documentation

Implementation touches `wiki_lua/items.py` and generation orchestration, new `wiki/modules/Erenshor/ItemData.lua` with render helpers/testcases, new `wiki/templates/ItemData.wiki` and owned styles, item details reuse under `Item/`, guarded article migration/reconciliation services, root matching/semantic validation and Item-only preservation rules. The CLI remains in the established `wiki` command family. If options are added, read the CLI skill and test dry-run/write boundaries rather than introduce an ad hoc script.

Extend `tests/unit/application/wiki_lua/test_items_module.py` for required fields, identity variants and deterministic new-version shards. Add migration tests beside field-preservation/generate-service tests for all four editor fields, multiple roots, preserved prose/companions, conflict revisions, interrupted manifests, rollback and data-only updates. Extend `tests/data/test_item_source_rows.py` to compare rendered canonical coverage IDs, not nonempty HTML. Extend `tests/contract/test_game_data_guide.py` to compare the editor-owned allowlist to the guide. Add real Scribunto testcases and production-scale Lua-limit coverage. Extend `tests/system/wiki/test_wiki_item_tooltip_layout.py` and the existing gadget browser suite for the exact hover/details DOM contract. Run owning narrow checks once after implementation and then `uv run erenshor test ci`.

Update `wiki/content/Erenshor Wiki/Game Data.wiki`, template documentation and existing contributor procedures in place. Readers need the new compact call, additive fields, fact-reporting path, source-note review action and tracking-category actions. Do not copy evidence counts or benchmark history into permanent guides. Record measured results and reviewed render diffs in this change instead.

## Ordered Rollout and Approval Boundaries

1. Complete shared provenance and coordinate guide gating through its persistent owner. This is a hard correctness dependency, not permission to edit or release that mod.
2. Prepare versioned data, renderers and templates, validate generated bytes and local full-data parses, and obtain local screenshot review.
3. Run and review the complete first-pass repository-page dry run. Obtain explicit approval to publish new data, then readers/styles/templates in dependency order. Existing legacy pages remain unchanged and working.
4. Complete real production parse/limit checks once dependencies exist. Run a separate guarded canary article dry run and obtain approval. Convert canaries, verify, and exercise manifest rollback before reapplying an approved canary pass.
5. Run a new full item conversion dry run against fresh fetched revisions and review every parse difference. Obtain separate approval for broad conversion. Verify full identity and fact coverage, hover/details behavior and data-only refresh behavior.
6. Remove obsolete item generator code only after the migration/rollback gates. Retire unused old wiki pages only through an approved administrator pass after the rollback window.

No live write, local service write, game launch, release or implementation is performed by this design-only change. Sound stays off. The repository remains disconnected from automatic live publication.
