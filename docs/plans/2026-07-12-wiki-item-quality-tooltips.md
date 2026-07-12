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
- [ ] Refactor the parameterized Lua renderer to compose reusable `Item/*`
  templates instead of maintaining a parallel copy of their layout markup.
- [ ] Compare parameterized tooltip markup and field visibility against live legacy templates.
- [ ] Resolve item and spell icon filenames to existing MediaWiki files without redlinks.
- [ ] Omit zero-valued optional stats and proc fields while preserving meaningful zeroes.
- [ ] Restore legacy card layout, centering, image-cell sizing, and typography.
- [ ] Deploy the required CSS through an interface page the deployment account can edit.
- [ ] Re-run the four-page live spike and verify rendered HTML, images, and styling.
- [ ] Enable Improved qualities only after the Planar March patch is live.
- [ ] Execute the complete production wiki cutover after explicit approval.

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
