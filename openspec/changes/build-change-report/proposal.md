## Why

After a game update, nobody can see what the update changed in the data. Backups keep the raw database and the decompiled scripts of each build, but not the clean database that the wiki, sheets, map, and guide read. `extract compare-variants` lists only rows that are new in one variant. It does not show removed rows or changed values, and it cannot compare two builds of the same variant. A patch that silently changes item stats or removes a spawn is therefore found by players, not by the pipeline.

## Goals

- Keep the clean database of every build that was extracted.
- Report, per table, the rows a new build adds, removes, and changes, with the changed columns and their old and new values.
- Use the same comparison for two builds of one variant and for two variants.

## Non-Goals

- Publishing the report to the wiki or the map. The report is a local review aid.
- Diffing the raw database or the decompiled scripts. The decompile history repository already covers scripts.
- Deciding whether a change is intended. The report shows changes; people judge them.

## What Changes

- `extract build` copies the clean database into the backup of the installed build, next to the raw database. The backup of a build is complete only when it holds both.
- A new `extract changes` command compares the current clean database with the clean database of an earlier backed-up build and writes a Markdown report.
- **BREAKING** `extract compare-variants` uses the same comparison, so its report gains removed and changed rows and its per-entity sections are replaced by per-table sections.
- Rows are matched by each table's primary key. Tables without a primary key are compared as sets of whole rows.

## Migration Boundary

Existing backups hold no clean database. The first comparison is possible after one `extract build` of a new build following an earlier `extract build` with this change. The current build 24405256 gets its clean copy on the next `extract build`.

## Capabilities

### New Capabilities

- `build-change-report`: which databases each build keeps, and how two clean databases are compared and reported.

### Modified Capabilities

None.

## Impact

- **Code:** `src/erenshor/application/services/backup_service.py`, `src/erenshor/application/extract/variant_comparison.py` (replaced by a table diff module), `src/erenshor/cli/commands/extract.py`.
- **Storage:** about 10 MB per backed-up build for the clean database.
- **Docs:** `refreshing-game-data` skill gains the review step. The README command list gains `extract changes`.
