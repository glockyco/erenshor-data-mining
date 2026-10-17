---
name: sheets-queries
description: Add, revise, preview, or deploy SQL-backed Google Sheets tabs. Use when changing sheet queries, running sheets deploy, or preparing reviewed Sheets publication.
---

# Google Sheets queries

1. Inspect a related query in `src/erenshor/application/sheets/queries/`.
   Inspect the clean database schema before writing SQL:

   ```bash
   sqlite3 variants/main/erenshor-main.sqlite ".tables"
   sqlite3 variants/main/erenshor-main.sqlite "PRAGMA table_info(items);"
   ```

   Select the intended variant when it is not `main`.
2. Add or edit one `.sql` file per tab.
   Its filename without `.sql` is the tab name.
   Alias selected columns when the header needs a display name.
   Join entities by stable keys, not display names.
3. For map-marker links, use `map_marker_url(stable_key)` as existing queries do.
   Plain `sqlite3` does not register this SQL function.
   Verify a query that uses it through the CLI dry run.
4. List tabs with `uv run erenshor sheets list`.
   Preview the changed tab with `uv run erenshor --dry-run sheets deploy --sheets items`.
   Replace `items` with the file stem.
   Repeat `--sheets` to select more tabs.
   This standalone dry run executes and formats SQL without inspecting live tables.
   `uv run pytest tests/contract/test_sheet_queries.py` runs every query against the empty clean schema. CI runs it too, so a renamed or dropped column fails there.
5. After approval to publish, run `uv run erenshor sheets deploy --sheets items`.
   Use `uv run erenshor sheets deploy --all-sheets` only when publishing all tabs is intended.

The formatter uses SQL column names as the header row.
It preserves numbers, renders null as an empty cell, and writes values as `RAW`.
The CLI requires a valid clean database with items before deployment.
The selected variant needs a configured spreadsheet ID and a service account with Editor access.
An invalid tab name fails before publication.
During a multi-tab deployment, a failed tab does not stop the remaining tabs.
The CLI exits with a failure when any tab fails. Read the per-tab results before retrying.

## Reviewed cross-surface publication

Use the prepared `publish` workflow when Sheets must follow wiki or map publication.
Select exact tab names through the selection schema in
`src/erenshor/application/publish/models.py`. Standalone batch deployment remains independent.

Preparation executes the selected SQL once and requires existing regular Google Sheets tables.
All selected tabs for the spreadsheet form one atomic native batch. Review the complete stable
workbook preimage, typed RAW rows, SQL, identities, final table ranges, exact request body and
its byte size. The snapshot includes unselected dependencies, formulas, chip identities,
explicit formatting and surrounding content. Destructive non-owned overlaps block preparation.

Apply only after a human reviews the immutable plan digest. Changed SQL, database,
configuration, account identity, payload bytes or live preimage requires a new plan.
The publisher checks the whole stable workbook before the batch and owned outputs afterward.
Google manages formula and named-range rebasing. The publisher does not invent those postimages.
The complete observed stable postimage becomes the receipt for later exact reconciliation.
Batch atomicity is not a compare-and-set guard. A concurrent writer can still race preflight.

The journal retains one atomic intent and acknowledgement. There is no silent chunking or
automatic retry. Resume skips the spreadsheet only while its full observed receipt still matches.
A lost response stays uncertain. Reconcile it before preparing a newly reviewed continuation.
Sheets offers no transactional restore or automatic rollback. Calculated output, scoped execution
status and threaded comments are outside the stable snapshot contract.
