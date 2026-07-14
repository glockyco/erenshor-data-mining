---
title: Erenshor — Planning Overview
type: overview
status: active
created: 2026-07-09
parent:
---

# Erenshor — Planning Overview

Erenshor's data pipeline turns the current shipping build into reliable public
artifacts: clean SQLite, wiki pages, sheets, maps, quest guide data, and companion
mods. The current planning north-star is the Planar March release refresh: promote
the playtest build on release day with production-tested wiki modules, templates,
generated data, and legacy display compatibility, then complete the remaining
Lua/Cargo cutover and publish the map/domain work once wiki-facing data is stable.

**This document is forward-looking only.** It holds the strategy sequence, ranked work,
and standing gates. Completed implementation belongs in commits and archived plans;
point-in-time findings belong in audits. When an item ships, it leaves this queue.

## Strategy sequence

1. **Execute the Planar March release refresh.** Promote the playtest build on
   release day using the shipped quality-tooltip architecture
   (`docs/plans/archive/2026-07-12-wiki-item-quality-tooltips.md`) and the restored legacy
   display contract; keep the full article deploy release-gated because playtest
   data is a spoiler.
2. **Cut over wiki content safely.** The live storage model is validated (nested
   store owners; reparse for data, recreate only on a schema change). Production
   keeps non-equipment item kinds on legacy Jinja templates. Finish the remaining
   dual-path templates, thin-page generation, community-row templates, styling
   delivery for Lua-owned markup, the production deploy/refresh path, and the
   incremental article cutover only after Lua parity with the legacy display
   contract is proven.
3. **Publish map/domain changes after wiki links are stable.** The map domain and URL
   restructure changes canonical URLs and wiki backlinks. It should happen once, after
   the wiki data model and map-link template expectations are settled, so external URLs
   churn once.
4. **Only then add user-facing map features.** Annotation UX, item-to-droppers search,
   and textual `/zones` content are valuable, but they should not compete with the
   promotion-critical data/wiki work unless a deploy window blocks the wiki path.
5. **Keep residual data gaps honest.** Parked or low-priority export gaps stay recorded
   until a consumer makes them important; they do not block the promotion unless they
   affect the wiki/map/sheets/guide surface being shipped.

## Priority queue

Every planned work item, ranked. Ordering logic: promotion-critical data correctness
first; then live-deploy gates that can invalidate the architecture; then the wiki
migration phases that depend on those gates; then URL/domain publishing; then map UX;
then residual export/data debt. Evidence-gated items never start before their gate.

**P1 — release/promotion-critical operations**
1. **`2026-07-13-planar-march-release-refresh`** *(plan, active)* — promote
   playtest build 24157014 on release day and deploy the prepared production wiki
   refresh. The shipped quality-tooltip architecture is documented in
   `docs/plans/archive/2026-07-12-wiki-item-quality-tooltips.md`: equipment articles use
   one parameterized `{{ItemTooltip|kind=...}}` invocation, while non-equipment
   kinds remain on legacy Jinja templates until the cutover gates clear. Keep the
   full article-page deploy release-gated because playtest data is a spoiler.
2. **`2026-06-04-wiki-cargo-data-architecture`** *(spec, active)* — keep as the design
   authority while later phases change reality. Update it only when the
   implementation discovers a better steady-state design.

**P2 — wiki cutover phases after live-deploy gates are green**
3. **Lua presentation and parity gate** *(required before any type converts)* —
   the live wiki has no TemplateStyles extension and
   `MediaWiki:Gadget-erenshor.css` is interface-protected, so Lua-owned markup
   needs a deliverable styling path. Prove Lua presentation parity with the
   restored legacy display contract (links, units, zero handling, and other
   display conventions) against live pages. Keep non-equipment item kinds on
   legacy Jinja templates until both gates clear.
4. **Community contribution layer** *(future Phase 4 plan from the Cargo spec)* —
   add `{{ItemSource}}` → `ObtainedFrom` and `{{SpawnPoint}}` → `Spawns`, stablekey
   validation, and editor docs. It waits for the Cargo model and the
   styling/parity gate because generated rows and article conversion must share
   the final presentation contract.
5. **Dual-path remaining templates + thin-page generator** *(future Phases 5–6 plans)* —
   add legacy fallbacks for spell/skill/stance/zone/quest templates, then generate thin
   `{{Type|stablekey=…}}` article pages while preserving community content. It waits for
   the Cargo model, community-row templates, and the styling/parity gate because
   article conversion should be a clean cutover, not a second migration.
6. **Production wiki cutover** *(future Phases 7–8 plan)* — TemplateSandbox gate, deploy
   modules/templates, create the Cargo tables, then refresh by reparse (recreate only on
   schema change; replacement table for a large recreate), incrementally convert pages,
   retire legacy branches, smoke live pages, report orphan pages for manual deletion,
   and establish the steady-state cutover operation.

**P3 — map/domain publishing once wiki backlinks are stable**
7. **`2026-06-26-maps-domain-url-migration`** *(plan, active; blocked on go-ahead)* —
   bind `erenshor.compendiums.org`, move zone maps to `/maps/{slug}`, deploy legacy
   redirects, and update backlinks we control. Ship domain + URL restructure together
   so URLs churn once. The wiki map-link template update should happen after the Cargo
   template path is known.
8. **Crawlable `/zones` content layer** *(draft child of maps-domain work)* — textual
   zone reference pages belong after `/maps/{slug}` is established and wiki/map links
   have settled. Keep it draft until the domain migration is either scheduled or done.

**P4 — independent map UX features**
9. **`2026-06-27-map-annotations`** *(spec, active)* — useful standalone feature; no
    backend dependency. Start when wiki/data work is blocked on live permissions or after
    P3 ships.
10. **Map search deferred UX** *(note, active)* — per-category empty states and recent
    searches are polish. Graduate only if working in the search area anyway.

**P5 — residual data/export debt**
11. **Category C zone-wide random spawns** *(note, active)* — model Sivakayan spectres as
    per-zone random appearances, not fixed spawn points. This becomes important when the
    remaining orphan count or character-page completeness is the active concern.
12. **LootTable gold range export** *(plan, parked)* — straightforward export/clean DB
    work, explicitly skipped for now. Resume only if a consumer needs static gold ranges.
13. **Small content debt, no planning doc needed:** hand-curate the four new planar zone
    pages before the next wiki article deploy; document forging/merge mechanics before
    exposing Merging Vessel as a `UsedIn` relationship.

## Standing gates

- **Playtest is the shipping build in waiting.** Use `-V playtest` for pipeline,
  code-fact, wiki Lua, and golden work until promotion. Commands that write shared
  outputs (`golden capture`, wiki deploy, guide compile, maps deploy) are safe only
  because playtest is the cutover build.
- **Cargo refresh model.** A data-only change needs no recreate — reparsing a page
  rewrites its rows in place; recreate (`cargorecreatetables` + `cargorecreatedata`) is
  for schema changes, and a large-table recreate uses a replacement table with a manual
  `Special:CargoTables` switch-in. The main account holds the recreate right; confirming
  the deploy bot's `recreatecargodata` right stays a Phase 7 gate.
- **Wiki article deploy is single-target.** `erenshor.wiki.gg` is not variant-scoped;
  do not deploy article changes from a non-shipping build.
- **Golden baselines are shared.** Recapture only for the build we intend to ship and
  review the diff, especially `code_facts.csv` and new relationship tables.
- **No broad map URL churn twice.** Domain and `/maps/{slug}` restructuring ship in one
  coordinated release; defer lower-value route work until then.
- **Lua-owned presentation gate.** The live wiki has no TemplateStyles extension, and
  `MediaWiki:Gadget-erenshor.css` is interface-protected. Before any type converts,
  provide a deliverable styling path for Lua-owned markup and prove Lua presentation
  parity with the restored legacy display contract (links, units, zero handling)
  against live pages. Non-equipment item kinds remain on legacy Jinja until both
  gates clear.

## Parked / not scheduled

- Photo mode spec — draft, unrelated to the current data/wiki/map promotion path.
- LootTable gold range export — active but parked by operator decision; not on the path
  unless a consumer needs it.
- Map search deferred UX — polish backlog; keep as a note.
- Research-grade or speculative data gaps without a current consumer stay out of the
  queue until an audit or user-facing surface ranks them.
- Cargo probe runner deep refactor — declarative scenario specs, one shared
  transaction/cleanup runner, a metadata descriptor registry, and a public MediaWiki
  adapter (replacing direct `client._request`). The probe is a one-off diagnostic whose
  verdict is now fail-closed; the rewrite is optional polish, not scheduled.

## Reference map

- `docs/plans/2026-07-13-planar-march-release-refresh.md` — release-day playtest
  promotion and production wiki refresh.
- `docs/plans/archive/2026-07-12-wiki-item-quality-tooltips.md` — shipped item quality-tooltip
  architecture and production rendering contract.
- `2026-06-04-wiki-cargo-data-architecture` — Cargo/Lua cutover design authority.
- `archive/2026-06-23-wiki-cargo-phase-3` — completed Phase 3 record.
- `docs/audits/2026-07-04-export-gap-analysis.md` — promotion-facing export and formula
  gap audit that must be triaged before broad deploys.
- `2026-06-26-maps-domain-url-migration` — map domain and URL migration tasks.
- `2026-06-27-map-annotations` — standalone annotations feature design.
- `2026-06-28-category-c-zone-random-spawns` — residual dynamic-spawn gap.
- `2026-06-28-map-search-deferred-ux` — low-priority search polish.
- `docs/plans/INDEX.md` — generated navigation.
- `HANDOFF.md` — session-level current pipeline state and promotion context.
