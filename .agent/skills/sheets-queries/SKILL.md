---
name: sheets-queries
description: Add, revise, preview, or deploy SQL-backed Google Sheets tabs. Use when changing src/erenshor/application/sheets/queries/ or running sheets deploy.
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
   The dry run executes and formats SQL but does not publish.
5. After approval to publish, run `uv run erenshor sheets deploy --sheets items`.
   Use `uv run erenshor sheets deploy --all-sheets` only when publishing all tabs is intended.

The formatter uses SQL column names as the header row.
It preserves numbers, renders null as an empty cell, and writes values as `RAW`.
The CLI requires a valid clean database with items before deployment.
The selected variant needs a configured spreadsheet ID and a service account with Editor access.
An invalid tab name fails before publication.
During a multi-tab deployment, a failed tab does not stop the remaining tabs.
The CLI exits with a failure when any tab fails. Read the per-tab results before retrying.
