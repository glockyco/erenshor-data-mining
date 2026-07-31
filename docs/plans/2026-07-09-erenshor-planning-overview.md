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
2. **Only then add user-facing map features.** Annotation UX, service discovery,
   and textual `/zones/{slug}` content are valuable, but they follow the
   wiki/data work.
3. **Keep residual data gaps honest.** Parked or low-priority export gaps stay
   recorded until a consumer makes them important; they do not block active
   work unless they affect the surface being shipped.

## Priority queue

Every planned work item below is ranked. Ordering logic: complete the Cargo/Lua
work while preserving wiki links and presentation; then later map UX; then
residual export/data debt. Evidence-gated items never start before their gate.
**P1 — wiki Cargo/Lua cutover and backlink stability**

1. **Create the Cargo tables on production** as `WoWMuch`. One operation, and every
   Cargo deliverable is unexercised until it happens.
2. **Build the parity instrument** — render each entity through the legacy and Lua
   paths and diff extracted field values. Nothing measures this today, so "working
   properly" is currently unfalsifiable.
3. **[`2026-07-30-wiki-cargo-schema-revision`](2026-07-30-wiki-cargo-schema-revision.md)**
   *(spec, draft)* — schema defects fixed before the tables are created, because a
   later change costs a recreate plus a manual sysop switch-in.
4. **[`2026-07-30-wiki-deploy-sync-discipline`](2026-07-30-wiki-deploy-sync-discipline.md)**
   *(spec, draft)* — drift detection, size preflight, and the canary render gate. The
   controls whose absence caused two production breakages.
5. **[`2026-07-11-wiki-article-cutover`](2026-07-11-wiki-article-cutover.md)**
   *(plan, active)* — convert one entity type end to end, stances first, and retire
   that type's Jinja generator before starting the next.
6. **[`2026-06-04-wiki-cargo-data-architecture`](2026-06-04-wiki-cargo-data-architecture.md)**
   *(spec, active)* — remains the design authority; update it when implementation
   discovers a better steady state.
7. **[`2026-07-10-wiki-deferred-mechanics`](2026-07-10-wiki-deferred-mechanics.md)**
   *(plan, active)* — deferred smithing, conversion, and other non-standard
   obtainability paths, after at least one type is converted.
8. **Adopt `Template:Ability` into the repo.** It renders 390 live pages, has no repo
   source, and was last edited on the wiki in November 2025. Spells and skills share it
   because the game does not present them as clearly distinct, so splitting them into
   `{{Spell}}` and `{{Skill}}` needs a repo-owned legacy body first.
9. **[`2026-07-31-wiki-quest-article-strategy`](2026-07-31-wiki-quest-article-strategy.md)**
   *(spec, draft)* — quest article conversion is deferred pending a design decision on
   how generated step-by-step guides and hand-written community prose should combine.
   96 of 115 live quest pages are human prose by at least eight editors.
10. **Community contribution layer** *(future)* — `{{ItemSource}}` and
   `{{SpawnPoint}}`, after a converted type proves the row shapes in production.

**P2 — later map UX**

11. **[`2026-06-27-map-annotations`](2026-06-27-map-annotations.md)** *(spec,
   active)* — standalone annotation UX for later map work or periods when
   wiki/data work is blocked on permissions.
12. **Map search deferred UX** *(note, active)* — category empty states and
    recent searches; polish only.
13. **[`2026-07-30-map-service-discovery`](2026-07-30-map-service-discovery.md)**
    *(spec, draft)* — make merchants, bankers, and auction brokers first-class
    map roles with distinct markers, filters, generic service search, and
    analyzer-backed role data.
14. **[`2026-07-04-maps-zones-content-layer`](2026-07-04-maps-zones-content-layer.md)**
    *(spec, draft)* — textual zone references after the service roles they
    consume and the settled `/maps/{slug}` routes.

**P3 — residual data/export debt**

15. **[`2026-07-11-dynamic-spawn-semantics-map-ux`](2026-07-11-dynamic-spawn-semantics-map-ux.md)**
    *(plan, active)* — make dynamic-only rarity and Brax spawn provenance
    authoritative for processor, map, and wiki consumers.
16. **Category C zone-wide random spawns** *(note, active)* — model Sivakayan
    spectres as per-zone random appearances, not fixed spawn points.
17. **[`2026-06-30-loot-table-gold-range-export`](2026-06-30-loot-table-gold-range-export.md)**
    *(plan, parked)* — resume only if a consumer needs static gold ranges.
18. **Small content debt, no planning doc needed:** hand-curate the four planar
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

- **Cargo tables do not exist on production.** None of the ten designed tables are
  live, so every Cargo deliverable is unexercised there. Declaring does not create a
  table, and `WoWBot` lacks `recreatecargodata`. Creation and every schema change run
  as `WoWMuch` or another sysop-equivalent account. This is the real blocker ahead of
  Phases 4 to 8.
- **Cargo refresh model.** A data-only change needs no recreate: reparsing a page
  rewrites rows in place. Recreate is for schema changes; a large recreate uses
  a replacement table and a manual `Special:CargoTables` switch-in.
- **Wiki article deploy is single-target.** `erenshor.wiki.gg` is not
  variant-scoped; do not deploy article changes from a non-shipping build.
- **Template deploys have broken live twice.** `WoWBot` pushed Lua-only `Quest`,
  `Zone`, and `Stance` bodies on 2026-07-14 and 2026-07-22, and an admin reverted both
  rounds. Prove the legacy branch renders parameter-only articles before any template
  deploy.
- **Lua-owned presentation gate is integration, not platform.** `TemplateStyles` and
  `TemplateStylesExtender` are installed and already used on live, and the gadget
  stylesheet deploys through the configured interface-admin account. Before any type
  converts, wire deterministic `<templatestyles>` emission, own a CSS source for Lua
  markup, and prove Lua presentation parity with the legacy display contract against
  live pages.
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
- `docs/plans/2026-07-30-wiki-cutover-state-audit.md` — measured live wiki state as of 2026-07-30.
- `docs/plans/2026-07-30-wiki-cargo-schema-revision.md` — schema fixes to land before first Cargo table creation.
- `docs/plans/2026-07-30-wiki-deploy-sync-discipline.md` — live-versus-repo sync gates.
- `docs/plans/2026-07-31-wiki-quest-article-strategy.md` — deferred quest article decision.
- `docs/plans/archive/2026-07-04-export-gap-analysis.md` — archived export and formula gap audit.
- `docs/plans/archive/2026-07-13-planar-march-release-refresh.md` — archived release plan.
- `docs/plans/archive/2026-07-12-adventure-guide-tracker-and-data-refresh.md` — archived guide plan.
- `docs/plans/INDEX.md` — generated navigation.
