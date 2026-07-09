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
mods. The current planning north-star is the playtest→main promotion: make the wiki
Cargo cutover and data model robust enough to ship the new build without hand-fixing
relationships, then publish the map/domain work once the wiki-facing data is stable.

**This document is forward-looking only.** It holds the strategy sequence, ranked work,
and standing gates. Completed implementation belongs in commits and archived plans;
point-in-time findings belong in audits. When an item ships, it leaves this queue.

## Strategy sequence

1. **Stabilize the wiki Cargo data model for the promotion build.** The wiki is the
   public consumer most sensitive to relationship correctness. Phase 3 establishes the
   item-owned `ObtainedFrom`/`UsedIn` model, item flags, `Spawns`, and
   `CharacterAbilities`, with playtest code-fact pins and treasure-chest locations
   modeled before any live article conversion.
2. **Cut over wiki content safely.** Once Cargo relationships are correct locally and
   the live attach-trick/recreate gate is resolved, finish the remaining dual-path
   templates, thin-page generation, community-row templates, production recreate
   automation or an admin-run recreate runbook, and the incremental article cutover.
3. **Publish map/domain changes after wiki links are stable.** The map domain and URL
   restructure changes canonical URLs and wiki backlinks. It should happen once, after
   the wiki data model and map-link template expectations are settled, so external URLs
   churn once.
4. **Only then add user-facing map features.** Annotation UX, item-to-droppers search,
   and textual `/zones` content are valuable, but they should not compete with the
   promotion-critical data/wiki work unless a deploy window blocks the wiki path.
5. **Keep residual data gaps honest.** Parked or low-priority export gaps stay recorded
   until a consumer makes them important; they do not block the promotion unless they
   affect the wiki/map surface being shipped.

## Priority queue

Every planned work item, ranked. Ordering logic: promotion-critical data correctness
first; then live-deploy gates that can invalidate the architecture; then the wiki
migration phases that depend on those gates; then URL/domain publishing; then map UX;
then residual export/data debt. Evidence-gated items never start before their gate.

**P0 — unblock the wiki Cargo implementation**
1. **Live Cargo attach/recreate gate** *(inside `2026-06-23-wiki-cargo-phase-3`)* —
   the configured bot can edit but lacks `recreatecargodata` and `delete`. Before Phase
   3B creates live probe pages, get a recreate-capable account or decide on an
   admin-run recreate runbook. Then probe a toy 3-table attach-trick template on the
   live wiki. If LIBRARIAN rejects it, revisit the relationship-owner design before
   implementing the tables.

**P1 — promotion-critical wiki data model**
2. **`2026-06-23-wiki-cargo-phase-3`** *(plan, active)* — implement the item-owned
   `ObtainedFrom`/`UsedIn` tables, playtest-pinned `IsAuctionable`, `IsRare`,
   `class_starting_items`, `Spawns` with treasure-chest locations, and
   `CharacterAbilities`; fold/delete `Drops`/`ContainerDrops`; move reverse rendering
   to Cargo. This is first because later wiki cutover work is unsafe without correct
   relationship tables and recreate behavior.
3. **`2026-06-04-wiki-cargo-data-architecture`** *(spec, active)* — keep as the design
   authority while Phase 3 and later phases change reality. Update it only when the
   implementation discovers a better steady-state design.

**P2 — wiki cutover phases after Phase 3 is green**
4. **Community contribution layer** *(future Phase 4 plan from the Cargo spec)* — add
   `{{ItemSource}}` → `ObtainedFrom` and `{{SpawnPoint}}` → `Spawns`, stablekey
   validation, and editor docs. It waits for Phase 3 because Phase 3 declares the final
   schemas and generated rows.
5. **Dual-path remaining templates + thin-page generator** *(future Phases 5–6 plans)* —
   add legacy fallbacks for spell/skill/stance/zone/quest templates, then generate thin
   `{{Type|stablekey=…}}` article pages while preserving community content. It waits for
   the Cargo model and community-row templates because article conversion should be a
   clean cutover, not a second migration.
6. **Production wiki cutover** *(future Phase 7 plan)* — TemplateSandbox gate, deploy
   modules/templates, recreate Cargo via bot or admin runbook, incrementally convert
   pages, retire legacy branches, smoke live pages, and report orphan pages for manual
   deletion.

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
- **Live Cargo recreate access.** Do not build production plans around bot-driven
  `cargorecreatetables` until an account with `recreatecargodata` is confirmed. If the
  bot cannot receive it, write the admin-run recreate runbook into the cutover plan.
- **Wiki article deploy is single-target.** `erenshor.wiki.gg` is not variant-scoped;
  do not deploy article changes from a non-shipping build.
- **Golden baselines are shared.** Recapture only for the build we intend to ship and
  review the diff, especially `code_facts.csv` and new relationship tables.
- **No broad map URL churn twice.** Domain and `/maps/{slug}` restructuring ship in one
  coordinated release; defer lower-value route work until then.

## Parked / not scheduled

- Photo mode spec — draft, unrelated to the current data/wiki/map promotion path.
- LootTable gold range export — active but parked by operator decision; not on the path
  unless a consumer needs it.
- Map search deferred UX — polish backlog; keep as a note.
- Research-grade or speculative data gaps without a current consumer stay out of the
  queue until an audit or user-facing surface ranks them.

## Reference map

- `2026-06-04-wiki-cargo-data-architecture` — Cargo/Lua cutover design authority.
- `2026-06-23-wiki-cargo-phase-3` — current executable wiki Cargo plan.
- `2026-06-26-maps-domain-url-migration` — map domain and URL migration tasks.
- `2026-06-27-map-annotations` — standalone annotations feature design.
- `2026-06-28-category-c-zone-random-spawns` — residual dynamic-spawn gap.
- `2026-06-28-map-search-deferred-ux` — low-priority search polish.
- `docs/plans/INDEX.md` — generated navigation.
- `HANDOFF.md` — session-level current pipeline state and promotion context.
