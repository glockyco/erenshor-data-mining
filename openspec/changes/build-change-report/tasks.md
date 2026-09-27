## 1. Clean database in the backup

- [ ] 1.1 Add the clean database to `backups/build-<id>/database/` after a successful `extract build`, publish it through a validated temporary directory, and record both database names in the metadata. Verify with a unit test that a failed copy leaves the old backup unchanged.
- [ ] 1.2 Make backup validation require the raw database and accept the clean one. Verify with the existing backup tests plus one for a backup holding both.
- [ ] 1.3 Run `extract build` for main and confirm `backups/build-24405256/database/` holds both databases.

## 2. Table diff

- [ ] 2.1 Implement the schema-driven diff: added, removed, and changed rows by primary key, keyless tables as multisets, added and removed tables and columns. Verify with unit tests for each case in the spec.
- [ ] 2.2 Render the diff as Markdown with a per-category row limit. Verify with a test that a table over the limit states the omitted count.

## 3. Commands

- [ ] 3.1 Replace the per-entity queries of `extract compare-variants` with the diff. Verify with the existing command tests, updated to the new sections.
- [ ] 3.2 Add `extract changes [--since BUILD] [--output PATH] [--limit N]` with the errors the spec names. Verify with command tests for an explicit build, the default build, a backup without a clean database, and no earlier build.

## 4. Verification and documentation

- [ ] 4.1 Copy the main clean database, change an item level, delete a spawn row, and insert an item. Run the diff against the original and confirm exactly those three changes are reported.
- [ ] 4.2 Add the review step to the `refreshing-game-data` skill and the command to the README.
- [ ] 4.3 Run `uv run erenshor test ci` and `openspec validate build-change-report --strict`.
