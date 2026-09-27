## ADDED Requirements

### Requirement: Each backed-up build keeps its clean database

After a successful clean build, the backup of the installed game build SHALL hold the clean database next to the raw database and the decompiled scripts. A failed clean build SHALL leave the existing backup unchanged. A clean copy that cannot be written SHALL fail the build command and name the backup.

#### Scenario: Clean build of an installed build

- **WHEN** `extract build` succeeds for a variant whose installed build is 24405256
- **THEN** `backups/build-24405256/` holds the raw database, the clean database, and the scripts
- **AND** the backup metadata names both databases

#### Scenario: Failed clean build

- **WHEN** `extract build` fails
- **THEN** the backup of the installed build is unchanged

### Requirement: Two clean databases compare table by table

The comparison SHALL report, for every table present in either database, the rows only in the new database, the rows only in the old database, and the rows present in both whose values differ. Rows SHALL be matched by the table's primary key. A table without a primary key SHALL be compared as a multiset of whole rows. A changed row SHALL name each changed column with its old and new value. A table present in only one database SHALL be reported as added or removed with its row count.

#### Scenario: Changed item stat

- **WHEN** an item row keeps its stable key and its `item_level` changes from 10 to 12
- **THEN** the report lists that row under changed rows of `items` with `item_level: 10 → 12`

#### Scenario: Removed spawn

- **WHEN** a `character_spawns` row exists only in the old database
- **THEN** the report lists it under removed rows of `character_spawns`

#### Scenario: Unchanged tables

- **WHEN** a table has identical rows in both databases
- **THEN** the report counts it as unchanged and prints no row detail for it

### Requirement: Build-to-build report

`extract changes --since <build-id>` SHALL compare the variant's current clean database with the clean database in the backup of the named build. Without `--since`, it SHALL use the newest backed-up build that differs from the build the current clean database records. The report SHALL name both builds, and SHALL be written to the path given by `--output` or printed.

#### Scenario: Backup without a clean database

- **WHEN** the selected backup holds no clean database
- **THEN** the command exits 1 and names the backup and the build that has to be rebuilt

#### Scenario: No earlier build

- **WHEN** no backed-up build other than the current one holds a clean database
- **THEN** the command exits 1 and says that no earlier build is available

### Requirement: Variant comparison uses the same report

`extract compare-variants` SHALL produce the same table-by-table report for the clean databases of two variants, naming each variant and the build its database records.

#### Scenario: Playtest against main

- **WHEN** `extract compare-variants --base-variant main --new-variant playtest` runs with both clean databases present
- **THEN** the report lists added, removed, and changed rows per table between main and playtest
