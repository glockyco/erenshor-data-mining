---
title: Wiki Item Quality Tooltips
type: plan
status: active
created: 2026-07-12
parent: wiki-article-cutover
---

# Wiki Item Quality Tooltips

Add complete Normal, Improved +1 through +5, Blessed, and Ascended item
presentations to the legacy-compatible wiki tooltip path while keeping the Lua
renderer and migration deterministic.

## Constraints

- Quality progression is Normal, Improved +1 through +5, Blessed, Ascended;
  runtime IDs are not display ordering.
- Improved item names use the game's `+1` through `+5` suffixes.
- Improved derived stats follow the intended non-decreasing progression;
  the wiki corrects the shipped `CalcResists` omission for quality 15.
- The game tints one animated sparkle image green for Improved qualities. The
  wiki reuses the published blue animation with a CSS hue shift; it must not
  require a separate green asset.
- Legacy `Item/Armor` and `Item/Weapon` invocations remain supported until the
  article cutover is complete.
- The parameterized path should invoke `Item/Weapon` or `Item/Armor` through
  `frame:expandTemplate` for each quality row. Lua owns stable-key/parameter
  normalization, quality iteration, and the outer quality-set wrapper; the
  existing templates own card internals, proc rendering, field suppression,
  and shared CSS structure. A pure-Lua inner renderer is only justified if a
  measured template contract prevents correct composition.
- Legacy `Item/Weapon` and `Item/Armor` begin with wikitable markup (`{|`), which
  MediaWiki parses only at line start. `Module:Erenshor/Item/ParameterizedTooltip`
  builds template arguments as a table, expands each template with
  `frame:expandTemplate`, and newline-joins wrapper strings so wikitable markup
  remains at line start. Do not use `frame:preprocess` or `{{#tag:div}}` wrapping:
  already-expanded wikitext contains raw pipes that corrupt parser-function
  argument splitting.
- Scribunto testcases exercise the renderer through a real frame created with
  `mw.getCurrentFrame():newChild`; frame mocks are prohibited because they can
  diverge from production behavior.
- The live wiki has no TemplateStyles extension, and
  `MediaWiki:Gadget-erenshor.css` is interface-protected
  (`protectednamespace-interface` for the deploy account), so new CSS classes
  are undeliverable. Non-equipment kinds (general, consumable, aura, charm,
  spell scroll, skill book, mold) use their legacy jinja-generated templates
  (`Item/General`, etc.) with existing gadget styling; the Lua stablekey path
  remains reserved for a future cutover when styling is deliverable.

## Implementation notes

- `ItemSectionGenerator._build_spell_details_context` emits display-ready
  `proc_spell_name` as a wikilink (`[[Ice Spear]]`), `proc_spell_icon` with
  `.png`, and `proc_cast_time` as ticks/60 to one decimal; optional zero
  numerics are blanks, booleans are `True`/blank, and XP bonus percent is
  emitted only for the XPBonus spell line. The parameterized `ItemTooltip`
  arguments are forwarded by the Lua adapter, which retains only tolerance
  normalization (`.png` append and zero omission) for hand-written pages.
- Item infobox `guaranteeddrops` and `droprates` use `SourceInfo.item_drops`,
  whose end-to-end values are resolved `(ItemLink, probability, is_guaranteed)`
  tuples; `ItemDropInfo` is not part of the repository API.
- Generated pages for weapon, armor, general, aura, charm, spell scroll, skill
  book, mold, consumable, and container were diffed against pre-2026-07-12 live
  revisions. Remaining diffs are playtest data changes and the intended
  equipment `ItemTooltip` parameterization.
- `Module:Erenshor/Item/testcases` is test-only and must never deploy to
  production; the repo-page manifest excludes `testcases.lua` files.

## Tasks

- [x] Record game quality IDs, progression, suffix, and stat formulas.
- [x] Implement parameter-driven Lua rendering from Normal base stats.
- [x] Add idempotent legacy quality-table replacement and preserve page text.
- [x] Verify the Cloth Sleeves fixture uses the authoritative lore text.
- [x] Align Improved sparkle overlays with legacy item icon cells.
- [x] Hide obsolete zero-size default sparkle placeholders.
- [x] Add focused assertions for Improved sparkle rendering and resist edge cases.
- [x] Run Lua syntax, wiki smoke, focused Python tests, and generation checks.
- [x] Review generated output and leave deployment to an explicit cutover.
- [x] Draft source-based reports for the CalcResists and SimPlayer quality bugs.
- [x] Deploy the old-formula item runtime spike to four representative live pages.
- [x] Deploy the item runtime's required Lua dependencies and generated item data.
- [x] Keep the production quality gate disabled until the game patch ships.
- [x] Capture the live legacy Item template contracts for styling and field behavior.
- [x] Replace the parameterized renderer's generated-template-string path with
  direct `frame:expandTemplate` calls for `Item/Weapon` and `Item/Armor`, while
  keeping the Lua-owned quality-set wrapper.
- [x] Compare parameterized tooltip markup and field visibility against live legacy
  templates.
- [x] Resolve item and spell icon filenames to existing MediaWiki files without
  redlinks.
- [x] Omit zero-valued optional stats and proc fields while preserving meaningful
  zeroes.
- [x] Restore legacy card layout, centering, image-cell sizing, and typography.
- [x] Confirm new CSS classes are undeliverable on the live wiki; keep non-equipment
  kinds on legacy jinja templates until styling can be delivered.
- [x] Restore display-ready spell detail arguments and forward them through the Lua
  adapter.
- [x] Restore `guaranteeddrops`/`droprates` infobox parameters from resolved item
  drops.
- [x] Exercise Scribunto testcases through a real
  `mw.getCurrentFrame():newChild` frame.
- [x] Diff generated pages for every item kind against pre-2026-07-12 live
  revisions.
- [x] Exclude `Module:Erenshor/Item/testcases` from production deployment
  manifests.
- [x] Re-run the four-page live spike and verify rendered HTML, images, and styling.
- [x] Upload the full playtest image set to the live wiki as a release soft-prepare
  so refreshed pages resolve new icons (e.g. `File:Access Bank.png`).
- [x] Spike one live page per remaining item kind (aura, charm, scroll, book, mold,
  consumable, container) and verify rendered HTML as the WoWBot deploy account.
- [ ] Deploy all item article pages on release day only: bulk playtest stats are
  spoilers until the patch is live (an early partial deploy was reverted).
- [ ] Enable Improved qualities only after the Planar March patch is live.
- [ ] Execute the complete production wiki cutover after explicit approval.

Release-day order: refresh game data from the new build, regenerate pages,
deploy all item articles, flip `PLANAR_MARCH_ENABLED` in
`Module:Erenshor/Item/Quality`, deploy repo pages, and paste
`wiki/gadgets/erenshor.css` into `MediaWiki:Gadget-erenshor.css` by hand (the
page is interface-protected, so no account in the pipeline can deploy it).

## Acceptance

- Every equipment tooltip renders exactly eight quality cards in progression
  order when the post-patch gate is enabled, and exactly three legacy cards while
  the gate is disabled.
- Improved cards display the matching `+N` name suffix and green sparkle;
  Normal cards have no visible placeholder overlay.
- Item and spell icons resolve to real MediaWiki files without `File:` redlinks.
- Optional zero-valued stats and proc fields are omitted as in the legacy
  templates, while values that are semantically meaningful at zero remain
  explicit.
- Card dimensions, image-cell positioning, centering, typography, and tier
  colors match the live legacy `Item/*` template output.
- Improved +4 and Improved +5 resist output is non-decreasing: both retain
  the +1 Improved resist bonus for a base resist of zero.
- Legacy pages retain manual content and do not accumulate duplicate tooltip
  tables after repeated generation.
- Lua and Python checks pass without raw legacy-template or parser-error output.
