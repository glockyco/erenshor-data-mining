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
- The Phase 3 storage shape should prefer nested hidden storage templates because each
  Cargo table has one declaring/storing template and one explicit recreate-data target.
- `action=cargorecreatetables` is not a complete refresh: it recreates schemas and
  clears rows; forced purge alone does not repopulate rows.
- `action=cargorecreatedata` repopulates nested-template rows when called per owning
  template/table.
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
2. Run cargorecreatetables for each owning storage template.
3. Run cargorecreatedata for each owning template/table pair until complete.
4. Query expected row counts and smoke rows before article conversion is considered healthy.
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

- [ ] Probe the actual production path: hidden storage templates invoke Lua, and Lua
      calls `#cargo_store` through `frame:callParserFunction`.
- [ ] Assert multiple rows, zero rows, booleans, integers, and strings round-trip through
      `cargoquery` with the expected Cargo representations.
- [ ] Assert hidden storage templates emit no visible output or whitespace noise.

### Task V3: Validate stale-row lifecycle

- [ ] Mutate one sandbox item from three `ObtainedFrom` rows to one row and assert the
      two old rows disappear.
- [ ] Mutate one sandbox item from one `UsedIn` row to zero rows and assert the table has
      no rows for that `ItemKey`.
- [ ] Remove one item call from a multi-item page and assert only that stablekey's rows
      disappear.
- [ ] Delete the sandbox page and assert rows either disappear or are reported by a
      deterministic orphan check.

### Task V4: Validate multi-entity pages

- [ ] Store two `{{Item|stablekey=...}}` calls on one sandbox page.
- [ ] Assert `Items`, `ObtainedFrom`, and `UsedIn` rows share `_pageName` but remain
      distinct by `StableKey` / `ItemKey`.
- [ ] Assert reverse queries never dedupe or join by page title alone.

### Task V5: Validate `cargorecreatedata` batching

- [ ] Create enough sandbox pages to force or simulate multiple recreation batches.
- [ ] Record the live API response shape for `offset` / completion.
- [ ] Implement the loop contract needed by production automation or document the exact
      admin-run sequence if looping is UI-only.

### Task V6: Decide replacement-table workflow

- [ ] Probe `cargorecreatetables createReplacement=1` on toy tables.
- [ ] Determine whether replacement population and switch-in can be automated through
      API calls or require admin UI steps.
- [ ] Choose either replacement-table refresh or direct table recreation for Phase 7,
      with the downtime/operational tradeoff stated explicitly.

### Task V7: Freeze the Phase 3 storage contract

- [ ] Update the Cargo architecture spec and Phase 3 plan with the final template names,
      Cargo table owners, and production refresh sequence.
- [ ] Remove any remaining wording that treats helper attaches as required.
- [ ] Promote the accepted probe runner command into the Phase 3 / Phase 7 verification
      commands.

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
