---
title: Erenshor — Planning Overview
type: overview
status: active
created: 2026-07-09
parent:
---

# Erenshor — Planning Overview

Erenshor's data pipeline turns the current shipping build into reliable public
artifacts: clean SQLite, wiki pages, sheets, maps, quest-guide data, and companion
mods. The current focus is readiness for the next game patch, then the map, then a
Stance-only trial of the Lua/Cargo wiki cutover.

This overview is the steering source. It holds strategy, current focus, linked child
artifacts, and standing gates by reference. Evidence belongs in audits, design in
specs, and executable work in plans.

## Current sequence

1. Prepare for the next game patch: `fail-loudly-on-partial-work`, a
   build-to-build change report, then `single-game-installation` and
   `describe-the-supported-setup`.
2. Map work: a browser smoke test in the maps gate, prerendered popup data
   instead of the browser database download, live NPC identity, and service
   discovery.
3. Wiki: plan a Stance-only vertical slice as an OpenSpec change, with sizes and
   limits measured again against the current build. Decide whether the other six
   entity types follow after the slice passes its gates.
4. Keep Quest conversion deferred until its article strategy is approved.
5. Build the crawlable zone content layer after service discovery.

## Planning system

OpenSpec owns new work. A record in this directory moves to an OpenSpec change
when work on it starts, after its facts are checked against the code again.
Records that nobody picks up stay here unchanged.

## Wiki cutover

### Active authority

- [`2026-06-04-wiki-cargo-data-architecture`](2026-06-04-wiki-cargo-data-architecture.md)
  defines selector, identity, Cargo ownership, refresh, replacement-table, and
  community-row architecture.

### Draft design and execution

- [`2026-08-01-wiki-render-parity-gate`](2026-08-01-wiki-render-parity-gate.md)
- [`2026-07-30-wiki-cargo-schema-revision`](2026-07-30-wiki-cargo-schema-revision.md)
- [`2026-07-30-wiki-deploy-sync-discipline`](2026-07-30-wiki-deploy-sync-discipline.md)
- [`2026-08-01-wiki-cargo-cutover-foundation`](2026-08-01-wiki-cargo-cutover-foundation.md)
- [`2026-07-11-wiki-article-cutover`](2026-07-11-wiki-article-cutover.md)
- [`2026-07-31-wiki-quest-article-strategy`](2026-07-31-wiki-quest-article-strategy.md)

The all-seven foundation is not the next wiki step. The Stance slice comes first
and reuses the parts of these specifications that answer observed incidents.

The archived
[`2026-07-30-wiki-cutover-state-audit`](archive/2026-07-30-wiki-cutover-state-audit.md)
is the dated production evidence baseline.

### Presentation

- [`2026-08-06-wiki-main-page-redesign`](2026-08-06-wiki-main-page-redesign.md)
  rebuilds the landing page and its TemplateStyles sheet. Independent of the Cargo
  cutover: it touches no entity article and no generated content.

## Map work

- [`2026-08-05-live-npc-identity`](2026-08-05-live-npc-identity.md)
- [`2026-07-30-map-service-discovery`](2026-07-30-map-service-discovery.md)
- [`2026-07-04-maps-zones-content-layer`](2026-07-04-maps-zones-content-layer.md)

Parked: [`2026-06-27-map-annotations`](2026-06-27-map-annotations.md) and
[`2026-06-28-map-search-deferred-ux`](2026-06-28-map-search-deferred-ux.md).

## Residual and deferred work

- [`2026-07-11-dynamic-spawn-semantics-map-ux`](2026-07-11-dynamic-spawn-semantics-map-ux.md)
- [`2026-06-28-category-c-zone-random-spawns`](2026-06-28-category-c-zone-random-spawns.md)
- [`2026-07-10-wiki-deferred-mechanics`](2026-07-10-wiki-deferred-mechanics.md)
  activates only after at least one entity type completes article conversion and
  legacy retirement.
- [`2026-08-01-loot-table-gold-range-trigger`](2026-08-01-loot-table-gold-range-trigger.md)
- [`2026-05-02-prd-photo-mode`](2026-05-02-prd-photo-mode.md)

## Standing gates

- **Wiki cutover safety:** follow
  [`2026-07-30-wiki-deploy-sync-discipline`](2026-07-30-wiki-deploy-sync-discipline.md)
  for size, rights and protection preflight, drift, TemplateSandbox, guarded writes,
  rollback, job polling, and privileged operations.
- **Render equivalence:** follow
  [`2026-08-01-wiki-render-parity-gate`](2026-08-01-wiki-render-parity-gate.md).
  No production article converts while a required case is failed or
  `not_exercised`.
- **Gates before articles:** a production article converts only under an approved
  OpenSpec change that defines its render parity, deploy safety, and rollback
  gates. The Stance slice is the first such change.
- **Single shipping target:** wiki article deployment uses the current shipping build
  only. A non-shipping variant fails preflight.
- **Per-type retirement:** follow
  [`2026-07-11-wiki-article-cutover`](2026-07-11-wiki-article-cutover.md). A failed or
  skipped page blocks legacy retirement for its type.
- **Quest content safety:** no quest article receives `lua=1` before
  [`2026-07-31-wiki-quest-article-strategy`](2026-07-31-wiki-quest-article-strategy.md)
  is approved.
- **Map compatibility:** future map changes retain the deployed legacy-host and
  companion-overlay compatibility contract recorded in the archived map migration
  plans.

## Navigation

[`INDEX.md`](INDEX.md) is the generated complete planning tree.
