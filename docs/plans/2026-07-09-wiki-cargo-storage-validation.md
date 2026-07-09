---
title: Wiki Cargo Storage Validation Plan
type: plan
status: active
created: 2026-07-09
parent: 2026-06-23-wiki-cargo-phase-3
---

# Wiki Cargo Storage Validation Plan

Purpose: retire the remaining live Cargo uncertainty before Phase 3 commits to the
`Item` → `Items` / `ObtainedFrom` / `UsedIn` implementation shape.

## Current facts

- Live wiki.gg accepts both direct multi-attach and nested hidden storage templates for
  a toy 3-table item shape: one sandbox page stored rows into all three tables.
- Live wiki.gg accepts the real Lua nested-storage path: hidden storage templates invoke
  Lua, Lua calls `#cargo_store` through `frame:callParserFunction`, and Cargo stores
  multiple rows plus Boolean/Integer/String values with expected query representations.
- Live wiki.gg removes stale rows on normal page edits for the production-like Lua
  nested shape: shrinking `ObtainedFrom`, clearing `UsedIn`, removing one item call
  from a multi-item page, and deleting the sandbox page all removed the matching
  Cargo rows after forced link-update purges.
- Live wiki.gg stores two `Item` calls on one page as distinct `Items`,
  `ObtainedFrom`, and `UsedIn` rows sharing `_pageName`; reverse lookups must use
  `ItemKey`/`StableKey` identity because page title alone is ambiguous.
- The Phase 3 storage shape uses nested hidden storage templates: each Cargo table has
  one declaring (schema) owner — its `cargorecreatetables` / recreate-data target — and
  community row templates (`{{ItemSource}}`/`{{SpawnPoint}}`) attach that shared table.
- A data-only refresh needs no recreate: once a table exists, reparsing a page rewrites
  its rows in place (the stale-row findings above are that mechanism). `cargorecreatetables`
  is for schema changes / first creation — it recreates the table empty, and a forced purge
  alone did not repopulate it afterward.
- `action=cargorecreatedata` repopulates nested-template rows when called once per
  owning template/table. Live wiki.gg returns immediate `{"success": true}` responses;
  completion is verified by polling row counts until expected totals return, matching
  Cargo's documented job-queue recreation model rather than an offset/continuation API.
- Live wiki.gg accepts `action=cargorecreatetables` with `createReplacement=1`:
  the original table remains queryable with its original row, while the staged
  `__NEXT` table is not API-queryable before switch-in through `Special:CargoTables`.
- Replacement-table switch-in is an admin `Special:CargoTables` step, not an API call.
  Replacement tables are the recommended no-downtime path for a large-table schema
  recreate (the old table serves queries while `__NEXT` fills); a routine refresh needs
  no recreate at all.
- Temporary probe pages are deleted after each run, but Cargo table deletion remains a
  manual admin cleanup step through `Special:CargoTables` / `Special:DeleteCargoTable`.

## Target storage contract

```text
Template:Item
  visible render
  declares/stores Items
  transcludes hidden storage templates

Template:ItemObtainedFromStore
  no visible output
  declares/stores ObtainedFrom
  Lua writes one row per acquisition relationship

Template:ItemUsedInStore
  no visible output
  declares/stores UsedIn
  Lua writes one row per usage relationship
```

Refresh contract (two paths):

```text
Routine (schema unchanged — the common case):
  1. Regenerate + deploy the Lua Data modules.
  2. Reparse dependent pages (job queue / forced-link purge); each page's #cargo_store
     rewrites its rows in place. No recreate, no downtime.

Schema change (a column added/removed/retyped, or first creation):
  1. Deploy modules/templates.
  2. cargorecreatetables (structure) + cargorecreatedata per owning table.
  3. Poll row counts, then query smoke rows before conversion is healthy.
  For a large table, use a replacement table (createReplacement=1) so the old table
  keeps serving queries while __NEXT fills; an admin switches it in at Special:CargoTables.
```

## Tasks

### Task V1: Build a reusable live Cargo probe runner

- [x] Add a repo-owned probe runner that creates timestamped sandbox templates/pages,
      prints exact API responses, deletes pages, and prints manual Cargo-table cleanup
      URLs for every table it creates.
- [x] Support dry-run naming output so the operator can inspect what will be created
      before live writes.
- [x] Fail closed on missing `recreatecargodata` or `delete` rights.

### Task V2: Validate real Lua nested storage

- [x] Probe the actual production path: hidden storage templates invoke Lua, and Lua
      calls `#cargo_store` through `frame:callParserFunction`.
- [x] Assert multiple rows, booleans, integers, and strings round-trip through
      `cargoquery` with the expected Cargo representations.
- [x] Assert hidden storage templates emit no visible probe output.

### Task V3: Validate stale-row lifecycle

- [x] Mutate one sandbox item from three `ObtainedFrom` rows to one row and assert the
      two old rows disappear.
- [x] Mutate one sandbox item from one `UsedIn` row to zero rows and assert the table has
      no rows for that `ItemKey`.
- [x] Remove one item call from a multi-item page and assert only that stablekey's rows
      disappear.
- [x] Delete the sandbox page and assert rows either disappear or are reported by a
      deterministic orphan check.

### Task V4: Validate multi-entity pages

- [x] Store two `{{Item|stablekey=...}}` calls on one sandbox page.
- [x] Assert `Items`, `ObtainedFrom`, and `UsedIn` rows share `_pageName` but remain
      distinct by `StableKey` / `ItemKey`.
- [x] Assert reverse queries never dedupe or join by page title alone.

### Task V5: Validate `cargorecreatedata` job-queue repopulation

- [x] Create multiple sandbox pages for the production-like nested Lua storage shape.
- [x] Record the live API response shape for recreate-data calls.
- [x] Confirm the production loop contract: call `cargorecreatedata` once per owning
      template/table, then poll row counts until all expected rows return.

### Task V6: Decide replacement-table workflow

- [x] Probe `cargorecreatetables createReplacement=1` on toy tables.
- [x] Determine whether replacement population and switch-in can be automated through
      API calls or require admin UI steps.
- [x] Choose either replacement-table refresh or direct table recreation for Phase 7,
      with the downtime/operational tradeoff stated explicitly.

### Task V7: Freeze the Phase 3 storage contract

- [x] Update the Cargo architecture spec and Phase 3 plan with the final template names,
      Cargo table owners, and production refresh sequence.
- [x] Remove any remaining wording that treats helper attaches as required.
- [x] Promote the accepted probe runner command into the Phase 3 / Phase 7 verification
      commands.
- [x] Reconcile architecture §9: `{{ItemSource}}`/`{{SpawnPoint}}` attach and store
      community rows into the single-declaring-owner tables, with the recreation model
      stated; add cross-links between the validation plan, Phase 3, and the architecture spec.

### Task V8: Make the probe's verdict trustworthy

The probe is a manual diagnostic spike (V1–V6 already captured its findings); its only
forward use is an operator re-running it before a production recreate. The single
correctness gap worth fixing: `validation_ok` reports success even when a Cargo
operation actually failed. No broad rework — the probe is not core architecture.

- [x] Type the operation contract: `ProbeOperations` / `CargoQuerier` protocols so the
      scenario runners and query helpers no longer depend on the concrete
      `ProbeRunContext`, and the test fakes conform without `cast` (purge returns the real
      `tuple[str, ...]` shape).
- [x] Fail closed: every scenario's `validation_ok` also requires each mutating operation
      (`cargorecreatetables`, `cargorecreatedata`, purge) to have succeeded, not only the
      row-state queries.
- [x] Report the replacement scenario honestly — a pre-switch diagnostic, never a
      "population verified" claim — and record that switch-in is not API-automatable.
- [x] The CLI records a raising scenario as a failed candidate rather than aborting the run.
- [x] A focused test proves the fail-closed verdict (a failed Cargo op flips
      `validation_ok` to false).

## Acceptance criteria

- Live wiki.gg behavior is validated with the same Lua/template pattern Phase 3 will ship.
- The final storage contract has no hidden dependency on direct multi-attach tolerance or
  helper attach behavior.
- Row lifecycle checks prove stale relationship rows do not survive normal edits,
  deleted template calls, page deletion, or Cargo data recreation.
- The production refresh runbook distinguishes schema recreation from row repopulation and
  states exactly which account or admin action performs each step.
- Every live probe leaves no sandbox pages behind and prints any Cargo tables requiring
  manual deletion.
- The probe runner fails closed: `validation_ok` is false whenever any Cargo operation
  (recreate-tables, recreate-data, purge) fails, and a raising scenario is reported
  rather than aborting the run.

## Outcome

The validated contract now lives in the design authority and the executable plan:

- [`../2026-06-04-wiki-cargo-data-architecture.md`](../2026-06-04-wiki-cargo-data-architecture.md)
  §2.1 / §9 / §10 / §15 — storage ownership and the two-path refresh model.
- [`../2026-06-23-wiki-cargo-phase-3.md`](../2026-06-23-wiki-cargo-phase-3.md) — nested
  store owners (no attach-trick) and the promoted probe command.
