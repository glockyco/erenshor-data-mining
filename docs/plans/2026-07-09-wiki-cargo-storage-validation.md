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
- The Phase 3 storage shape should prefer nested hidden storage templates because each
  Cargo table has one declaring/storing template and one explicit recreate-data target.
- `action=cargorecreatetables` is not a complete refresh: it recreates schemas and
  clears rows; forced purge alone does not repopulate rows.
- `action=cargorecreatedata` repopulates nested-template rows when called once per
  owning template/table. Live wiki.gg returns immediate `{"success": true}` responses;
  completion is verified by polling row counts until expected totals return, matching
  Cargo's documented job-queue recreation model rather than an offset/continuation API.
- Live wiki.gg accepts `action=cargorecreatetables` with `createReplacement=1`:
  the original table remains queryable with its original row, while the staged
  `__NEXT` table is not API-queryable before switch-in through `Special:CargoTables`.
- Replacement-table switch-in is an admin/UI operation, not an automated Phase 7 API
  step. Replacement tables are therefore a manual downtime-minimizing option rather
  than the production automation path.
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

Production refresh contract:

```text
1. Deploy modules/templates.
2. Run direct `cargorecreatetables` for each owning storage template.
3. Call `cargorecreatedata` once for each owning template/table pair.
4. Poll expected row counts until complete, then query smoke rows before article
   conversion is considered healthy.
```

For a manually supervised, downtime-minimizing refresh, an administrator may instead
create replacement tables and switch them in through `Special:CargoTables`. Automated
Phase 7 does not use that path because the switch-in is not available through the API.

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

- [ ] Update the Cargo architecture spec and Phase 3 plan with the final template names,
      Cargo table owners, and production refresh sequence.
- [ ] Remove any remaining wording that treats helper attaches as required.
- [ ] Promote the accepted probe runner command into the Phase 3 / Phase 7 verification
      commands.
- [ ] Reconcile architecture §9: `{{ItemSource}}`/`{{SpawnPoint}}` attach and store
      community rows into the single-declaring-owner tables, with the recreation model
      stated; add cross-links between the validation plan, Phase 3, and the architecture spec.

### Task V8: Harden the probe runner as a Phase 7 verification gate

The reusable probe runner (V1) is promoted to a Phase 7 verification gate, so its
`validation_ok` must fail closed — a false "success" could green-light a broken
production recreate.

- [ ] Type the operation contract: `ProbeOperations` / `CargoQuerier` protocols so the
      scenario runners and query helpers no longer depend on the concrete
      `ProbeRunContext`, and the test fakes conform without `cast` (purge returns the real
      `tuple[str, ...]` shape).
- [ ] Fail closed: every scenario's `validation_ok` also requires each mutating operation
      (`cargorecreatetables`, `cargorecreatedata`, purge) to have succeeded, not only the
      row-state queries.
- [ ] Report the replacement scenario honestly — a pre-switch diagnostic, never a
      "population verified" claim — and record that switch-in is not API-automatable.
- [ ] The CLI records a raising scenario as a failed candidate and still emits the JSON
      report with a deterministic exit code.
- [ ] Failure-injection tests cover each scenario's operation-failure branches.

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
