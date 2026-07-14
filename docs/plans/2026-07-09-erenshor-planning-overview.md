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
companion mods. The current planning focus is the coordinated maps domain and
URL migration: bind `erenshor.compendiums.org`, move interactive zone maps to
`/maps/{slug}`, preserve legacy links with host-aware compatibility routing, and
update the consumers we control. Repository implementation and local verification
are complete, and the new Search Console Domain property is DNS-verified. The
Cloudflare deployment and live-verification gates now control the cutover. This
work remains deliberately ahead of later map features and residual data debt.

**This document is forward-looking only.** It holds the strategy sequence,
ranked work, and standing gates. Completed implementation belongs in commits and
archived plans; point-in-time findings belong in audits. When an item ships, it
leaves this queue.

## Strategy sequence

1. **Execute the coordinated maps domain/URL migration.** Repository routes,
   SEO and generated-link configuration, maintained consumers, and the shared
   `erenshor-maps` Worker are prepared and locally verified for both
   `erenshor-maps.wowmuch1.workers.dev` and `erenshor.compendiums.org`. The new
   Search Console Domain property is DNS-verified; pass the Cloudflare
   deployment and live-verification gates before the single production
   cutover. The custom domain and `/maps/{slug}` move together so canonical
   URLs churn once.
2. **Cut over wiki content safely.** The live storage model is validated (nested
   store owners; reparse for data, recreate only on a schema change). Finish the
   remaining dual-path templates, thin-page generation, community-row
   templates, styling delivery for Lua-owned markup, the production deploy path,
   and incremental article conversion only after Lua parity with the legacy
   display contract is proven. The map-link template remains a migration
   dependency because it owns many wiki backlinks.
3. **Only then add user-facing map features.** Annotation UX, item-to-droppers
   search, and textual `/zones/{slug}` content are valuable, but they follow the
   domain/URL cutover and the wiki/data work.
4. **Keep residual data gaps honest.** Parked or low-priority export gaps stay
   recorded until a consumer makes them important; they do not block the
   migration unless they affect the surface being shipped.

## Priority queue

Every planned work item below is ranked. Ordering logic: the coordinated domain
and route cutover first; then the Cargo/Lua work that must preserve wiki links
and presentation; then later map UX; then residual export/data debt.
Evidence-gated items never start before their gate.

**P1 — coordinated maps publishing**

1. **[`2026-06-26-maps-domain-url-migration`](2026-06-26-maps-domain-url-migration.md)**
   *(plan, active; current focus)* — bind `erenshor.compendiums.org`, move zone
   maps to `/maps/{slug}`, and update wiki, Steam, in-game, mod, and README
   links. The single `erenshor-maps` Worker serves one shared static build on
   both the custom domain and its existing `erenshor-maps.wowmuch1.workers.dev`
   route. The legacy host remains indefinitely for old Interactive Map
   Companion overlays: legacy `/map` and same-origin runtime resources
   (service worker, Svelte assets/data, SQLite, tiles, images, fonts, and other
   non-HTML resources) stay `200`; other known legacy HTML routes redirect to
   the canonical custom domain. Legacy `/map` is cross-domain-canonicalized to
   the custom-domain `/map`, is absent from sitemaps/internal links, and does
   not use `noindex`. Exact known root map keys redirect to `/maps/{key}`;
   unknown and reserved paths remain `404`, while the old GSC token remains
   `200`.

   Execute in this order: prepare and review repository changes; manually
   verify Cloudflare account/token, zone ownership, custom-domain
   certificate/DNS, Worker authorization, and GSC access; deploy and verify the
   shared build on the custom host while retaining the existing workers.dev
   route; then update GSC Change of Address, sitemap, and external links.
   Verify representative routes/assets, HTTPS, canonicals, OG/JSON-LD, sitemap,
   robots, redirects, query preservation, and embedded-browser access. Keep the
   shared Worker/build and old host available until verification passes; roll
   back the single Worker deployment or binding if deployment, routing, or
   verification fails. The plan's active task checklist is the execution
   authority.

**P2 — wiki Cargo/Lua cutover and backlink stability**

2. **[`2026-06-04-wiki-cargo-data-architecture`](2026-06-04-wiki-cargo-data-architecture.md)**
   *(spec, active)* — remain the design authority while later phases change
   reality; update only when implementation discovers a better steady state.
3. **[`2026-07-10-wiki-deferred-mechanics`](2026-07-10-wiki-deferred-mechanics.md)**
   *(plan, active)* — preserve and implement deferred smithing, conversion, and
   other non-standard obtainability paths under the Cargo/Lua gates.
4. **[`2026-07-11-wiki-article-cutover`](2026-07-11-wiki-article-cutover.md)**
   *(plan, active)* — incrementally convert legacy articles only after Lua parity
   and styling gates are proven, preserving community content and the restored
   legacy display contract.
5. **Lua presentation and parity gate** *(required before any type converts)* —
   provide a deliverable styling path for Lua-owned markup and prove links,
   units, zero handling, and other display conventions against live pages.
   Keep non-equipment kinds on legacy Jinja templates until both gates clear.
6. **Community contribution layer** *(future Phase 4 plan)* — add
   `{{ItemSource}}` → `ObtainedFrom`, `{{SpawnPoint}}` → `Spawns`, stablekey
   validation, and editor docs after the Cargo model and presentation gate.
7. **Dual-path templates and thin-page generator** *(future Phases 5–6)* — add
   legacy fallbacks for spell/skill/stance/zone/quest templates, then generate
   thin `{{Type|stablekey=…}}` pages without losing community content.
8. **Production wiki cutover** *(future Phases 7–8)* — pass TemplateSandbox,
   deploy modules/templates, create or reparse Cargo tables according to schema
   change, convert pages incrementally, retire legacy branches, and smoke-test
   live pages.

**P3 — later map UX**

9. **[`2026-06-27-map-annotations`](2026-06-27-map-annotations.md)** *(spec,
   active)* — standalone annotation UX after the migration or while wiki/data
   work is blocked on permissions.
10. **Map search deferred UX** *(note, active)* — category empty states and
    recent searches; polish only.
11. **Crawlable `/zones/{slug}` content layer** *(draft child of the migration)*
    — textual zone references after `/maps/{slug}` and wiki/map links settle.

**P4 — residual data/export debt**

12. **[`2026-07-11-dynamic-spawn-semantics-map-ux`](2026-07-11-dynamic-spawn-semantics-map-ux.md)**
    *(plan, active)* — make dynamic-only rarity and Brax spawn provenance
    authoritative for processor, map, and wiki consumers.
13. **Category C zone-wide random spawns** *(note, active)* — model Sivakayan
    spectres as per-zone random appearances, not fixed spawn points.
14. **[`2026-06-30-loot-table-gold-range-export`](2026-06-30-loot-table-gold-range-export.md)**
    *(plan, parked)* — resume only if a consumer needs static gold ranges.
15. **Small content debt, no planning doc needed:** hand-curate the four planar
    zone pages before a future wiki article deploy; document forging/merge
    mechanics before exposing Merging Vessel as a `UsedIn` relationship.

## Archived release references

The Planar March promotion and Adventure Guide refresh are complete and are no
longer active priorities. Their implementation records remain available at
[`2026-07-13-planar-march-release-refresh`](archive/2026-07-13-planar-march-release-refresh.md)
and [`2026-07-12-adventure-guide-tracker-and-data-refresh`](archive/2026-07-12-adventure-guide-tracker-and-data-refresh.md).

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
- **Migration cutover gate.** Do not bind the custom domain or change legacy
  routing until repository route/link preparation is reviewed and Cloudflare
  DNS, certificate, Worker authorization, and GSC prerequisites are confirmed.
  The one `erenshor-maps` Worker must serve the reviewed shared static build on
  both hosts. Verify the custom host before changing canonical/link outputs;
  retain the legacy workers.dev route indefinitely for old overlays, with only
  legacy `/map` and runtime resources directly served and other HTML routes
  redirecting. Keep one rollback for the shared Worker deployment or binding,
  not separate Worker rollbacks.

## Parked / not scheduled

- Photo mode spec — draft, unrelated to the current data/wiki/map path.
- LootTable gold range export — parked unless a consumer needs static gold ranges.
- Map search deferred UX — polish backlog; keep as a note.
- Research-grade or speculative data gaps without a current consumer stay out of
  the queue until an audit or user-facing surface ranks them.
- Cargo probe runner deep refactor — optional diagnostic polish, not scheduled.

## Reference map

- `docs/plans/2026-06-26-maps-domain-url-migration.md` — current migration plan.
- `docs/plans/2026-06-04-wiki-cargo-data-architecture.md` — Cargo/Lua design authority.
- `docs/audits/2026-07-04-export-gap-analysis.md` — export and formula gap audit.
- `docs/plans/archive/2026-07-13-planar-march-release-refresh.md` — archived release plan.
- `docs/plans/archive/2026-07-12-adventure-guide-tracker-and-data-refresh.md` — archived guide plan.
- `docs/plans/INDEX.md` — generated navigation.
