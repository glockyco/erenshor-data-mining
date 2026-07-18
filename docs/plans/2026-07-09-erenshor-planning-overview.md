---
title: Erenshor — Planning Overview
type: overview
status: active
created: 2026-07-09
parent:
---

# Erenshor — Planning Overview

Erenshor's data pipeline turns the current shipping build into reliable public
artifacts: clean SQLite, wiki pages, sheets, maps, quest-guide data, and
companion mods. The current planning focus is the remaining wiki Cargo/Lua
cutover: preserve the live legacy presentation contract while finishing styling,
data ownership, and incremental article migration. The maps domain and URL
migration is complete: `erenshor.compendiums.org` is canonical, interactive zone
maps live at `/maps/{slug}`, controlled backlinks and Search Console have moved,
and the legacy Worker route remains available for shipped companion overlays.

**This document is forward-looking only.** It holds the strategy sequence,
ranked work, and standing gates. Completed implementation belongs in commits and
archived plans; point-in-time findings belong in audits. When an item ships, it
leaves this queue.

## Strategy sequence

1. **Cut over wiki content safely.** The live storage model is validated (nested
   store owners; reparse for data, recreate only on a schema change). Finish the
   remaining dual-path templates, thin-page generation, community-row
   templates, styling delivery for Lua-owned markup, the production deploy path,
   and incremental article conversion only after Lua parity with the legacy
   display contract is proven.
2. **Only then add user-facing map features.** Annotation UX, item-to-droppers
   search, and textual `/zones/{slug}` content are valuable, but they follow the
   wiki/data work.
3. **Keep residual data gaps honest.** Parked or low-priority export gaps stay
   recorded until a consumer makes them important; they do not block active
   work unless they affect the surface being shipped.

## Priority queue

Every planned work item below is ranked. Ordering logic: complete the Cargo/Lua
work while preserving wiki links and presentation; then later map UX; then
residual export/data debt. Evidence-gated items never start before their gate.

**P1 — wiki Cargo/Lua cutover and backlink stability**

1. **[`2026-06-04-wiki-cargo-data-architecture`](2026-06-04-wiki-cargo-data-architecture.md)**
   *(spec, active)* — remain the design authority while later phases change
   reality; update only when implementation discovers a better steady state.
2. **[`2026-07-10-wiki-deferred-mechanics`](2026-07-10-wiki-deferred-mechanics.md)**
   *(plan, active)* — preserve and implement deferred smithing, conversion, and
   other non-standard obtainability paths under the Cargo/Lua gates.
3. **[`2026-07-11-wiki-article-cutover`](2026-07-11-wiki-article-cutover.md)**
   *(plan, active)* — incrementally convert legacy articles only after Lua parity
   and styling gates are proven, preserving community content and the restored
   legacy display contract.
4. **Lua presentation and parity gate** *(required before any type converts)* —
   provide a deliverable styling path for Lua-owned markup and prove links,
   units, zero handling, and other display conventions against live pages.
   Keep non-equipment kinds on legacy Jinja templates until both gates clear.
5. **Community contribution layer** *(future Phase 4 plan)* — add
   `{{ItemSource}}` → `ObtainedFrom`, `{{SpawnPoint}}` → `Spawns`, stablekey
   validation, and editor docs after the Cargo model and presentation gate.
6. **Dual-path templates and thin-page generator** *(future Phases 5–6)* — add
   legacy fallbacks for spell/skill/stance/zone/quest templates, then generate
   thin `{{Type|stablekey=…}}` pages without losing community content.
7. **Production wiki cutover** *(future Phases 7–8)* — pass TemplateSandbox,
   deploy modules/templates, create or reparse Cargo tables according to schema
   change, convert pages incrementally, retire legacy branches, and smoke-test
   live pages.

**P2 — later map UX**

8. **[`2026-06-27-map-annotations`](2026-06-27-map-annotations.md)** *(spec,
   active)* — standalone annotation UX for later map work or periods when
   wiki/data work is blocked on permissions.
9. **Map search deferred UX** *(note, active)* — category empty states and
    recent searches; polish only.
10. **Crawlable `/zones/{slug}` content layer** *(draft descendant of the archived migration)*
    — textual zone references after `/maps/{slug}` and wiki/map links settle.

**P3 — residual data/export debt**

11. **[`2026-07-11-dynamic-spawn-semantics-map-ux`](2026-07-11-dynamic-spawn-semantics-map-ux.md)**
    *(plan, active)* — make dynamic-only rarity and Brax spawn provenance
    authoritative for processor, map, and wiki consumers.
12. **Category C zone-wide random spawns** *(note, active)* — model Sivakayan
    spectres as per-zone random appearances, not fixed spawn points.
13. **[`2026-06-30-loot-table-gold-range-export`](2026-06-30-loot-table-gold-range-export.md)**
    *(plan, parked)* — resume only if a consumer needs static gold ranges.
14. **Small content debt, no planning doc needed:** hand-curate the four planar
    zone pages before a future wiki article deploy; document forging/merge
    mechanics before exposing Merging Vessel as a `UsedIn` relationship.

## Archived release references

The Planar March promotion, Adventure Guide refresh, and maps domain/URL
migration are complete and are no longer active priorities. Their implementation
records remain available at
[`2026-07-13-planar-march-release-refresh`](archive/2026-07-13-planar-march-release-refresh.md),
[`2026-07-12-adventure-guide-tracker-and-data-refresh`](archive/2026-07-12-adventure-guide-tracker-and-data-refresh.md),
and [`2026-06-26-maps-domain-url-migration`](archive/2026-06-26-maps-domain-url-migration.md).

## Standing gates

- **Cargo refresh model.** A data-only change needs no recreate: reparsing a page
  rewrites rows in place. Recreate is for schema changes; a large recreate uses
  a replacement table and a manual `Special:CargoTables` switch-in. Confirm the
  deploy bot's recreate permission before the production cutover.
- **Wiki article deploy is single-target.** `erenshor.wiki.gg` is not
  variant-scoped; do not deploy article changes from a non-shipping build.
- **Lua-owned presentation gate.** The live wiki has no TemplateStyles extension
  and `MediaWiki:Gadget-erenshor.css` is interface-protected. Before any type
  converts, provide a deliverable styling path and prove Lua presentation parity
  with the legacy display contract against live pages.
- **Legacy map compatibility.** Future maps deployments must retain the single
  `erenshor-maps` Worker on both hosts. The old workers.dev `/map`, verification
  token, and same-origin runtime resources remain available for shipped
  companion overlays; known non-map HTML routes redirect to the canonical
  custom domain. Test the dual-host matrix whenever Worker routing or build
  inputs change.

## Parked / not scheduled

- Photo mode spec — draft, unrelated to the current data/wiki/map path.
- LootTable gold range export — parked unless a consumer needs static gold ranges.
- Map search deferred UX — polish backlog; keep as a note.
- Research-grade or speculative data gaps without a current consumer stay out of
  the queue until an audit or user-facing surface ranks them.
- Cargo probe runner deep refactor — optional diagnostic polish, not scheduled.

## Reference map

- `docs/plans/archive/2026-06-26-maps-domain-url-migration.md` — archived maps domain and URL migration.
- `docs/plans/2026-06-04-wiki-cargo-data-architecture.md` — Cargo/Lua design authority.
- `docs/plans/archive/2026-07-04-export-gap-analysis.md` — archived export and formula gap audit.
- `docs/plans/archive/2026-07-13-planar-march-release-refresh.md` — archived release plan.
- `docs/plans/archive/2026-07-12-adventure-guide-tracker-and-data-refresh.md` — archived guide plan.
- `docs/plans/INDEX.md` — generated navigation.
