## Context

See proposal.md - Why. `BackupService.create_backup` runs after `extract export` and copies the raw database and the scripts into `backups/build-<id>/` through a validated temporary directory. `_validate_backup` expects exactly one database file. `extract build` writes the clean database and records the game build in `code_facts_meta`. `variant_comparison.py` attaches the base database read-only and runs five hand-written "new rows" queries.

In the main clean database, 72 of 75 tables have a primary key. The three without one are `code_facts_meta`, `quest_acquisition_sources`, and `quest_completion_sources`.

## Decisions

**The clean copy joins the existing backup.** `extract build` adds the clean database to `backups/build-<id>/database/` through the same temporary-directory publish that `create_backup` uses, so a failure keeps the old backup. The build id is read from the installed manifest, as `extract export` does. Alternative: a separate `clean-backups/` tree. Rejected, because one directory per build is what the backup listing and the decompile history already key on.

**One generic diff, driven by the schema.** The diff reads each table's columns and primary key from `PRAGMA table_info`, then compares with SQL over an attached old database: `LEFT JOIN` on the key for added and removed rows, and a join with `IS NOT` per column for changed rows. Keyless tables use `EXCEPT ALL` semantics, implemented with grouped counts because SQLite lacks `EXCEPT ALL`. Alternative: keep per-entity queries. Rejected, because hand-written queries covered five tables and missed every removal and every changed value.

**The report is data first, Markdown second.** The diff returns a typed result per table. The Markdown writer renders it. Tests assert on the result, not on text.

**Report size stays bounded.** A table section prints at most 50 rows per category and states how many it omitted. A full-precision diff is available through `--limit 0`. A new build usually changes few tables, but a schema change can change every row of one table.

**compare-variants becomes a caller of the same diff.** It resolves two variants to clean databases and renders the same report. Its old per-entity sections go.

## Risks / Trade-offs

- A schema change between builds makes columns appear or vanish → the diff compares shared columns and lists added and removed columns per table.
- A primary key made of generated ids (`zone_atlas_entries.id`) can renumber between builds → such a table shows as removed and added rows. The report states the key it matched on, so the reader can see why.
- Floating-point columns may differ only in the last digit → values are compared exactly. A real change of this size is still a change.

## Migration Plan

1. Extend the backup with the clean copy and run `extract build` for build 24405256.
2. Build the diff and the report, and use them in `compare-variants`.
3. Add `extract changes`.
4. Verify with a copy of the clean database in which rows were edited, removed, and added.

Rollback is per commit.
