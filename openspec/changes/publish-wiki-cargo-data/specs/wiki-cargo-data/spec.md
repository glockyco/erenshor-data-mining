## Purpose

Defines what the wiki's Cargo tables hold, how generated rows from the shipping build and rows that editors write reach them, and how editors query them without access to the export pipeline.

## ADDED Requirements

### Requirement: Generated tables are complete and exact

For each table, the rows that the pipeline generates SHALL equal the rows that the schema derives from the clean database of the shipping build. `wiki cargo verify` SHALL compare every live table with the expected rows, report each missing, extra, and different row by table and key, and fail on any difference.

#### Scenario: After a deploy

- **WHEN** a deploy has finished and the storage pages are saved
- **THEN** `wiki cargo verify` reports no difference for any table

#### Scenario: A row differs

- **WHEN** a live row of `Spawns` has another spawn chance than the expected row
- **THEN** `wiki cargo verify` fails and names the table and the row's key

#### Scenario: A world drop

- **WHEN** the tables are verified on the current main build
- **THEN** the item sources hold a world drop row for Crystallized Balance at 0.05% per kill above level 30

### Requirement: Generated rows do not depend on articles

Generated rows SHALL be stored only by bot-owned storage pages. No article SHALL store a generated row. Each storage page SHALL state that it is generated and SHALL link the documentation hub.

#### Scenario: Articles do not change

- **WHEN** the tables are created and filled
- **THEN** no article was edited, and every table already holds its rows

### Requirement: One schema defines each table

Each table SHALL have one declaration, generated from the schema together with its rows and its documentation. The documentation SHALL list every column with its type and meaning. Generation SHALL fail when a declared column is never filled by any generated or community row.

#### Scenario: Column documentation

- **WHEN** an editor opens the template that declares `Spawns`
- **THEN** it lists every column of `Spawns` with its type and meaning

#### Scenario: A column without values

- **WHEN** a schema change declares a column that no row builder fills
- **THEN** generation fails and names the table and the column

### Requirement: Values are plain data and keys resolve

Stored values SHALL hold no wiki markup. A column whose value is an entity's stable key SHALL end in `Key`, and every such value SHALL match a row of `Entities`, which holds the kind, name, page, and image of each entity. Generation SHALL fail on a value that breaks either rule and name its table, row, and column.

#### Scenario: A link in a value

- **WHEN** a row builder produces a value that contains `[[`
- **THEN** generation fails and names the table, the row, and the column

#### Scenario: Joining a name

- **WHEN** an editor joins `Spawns.CharacterKey` to `Entities.StableKey`
- **THEN** every spawn row has a character name and, when the character has an article, its page

### Requirement: Editors can add rows

`{{ItemSource}}` SHALL store an item source row and `{{SpawnPoint}}` SHALL store a spawn row, each marked as a community row, on the page where an editor writes it. A community row whose entity key does not resolve SHALL NOT be stored, and the page SHALL join a tracking category. A refresh of generated rows SHALL NOT change community rows. Query templates SHALL show community rows next to generated rows, marked as community rows with a link to the page that stores them.

#### Scenario: A source the export misses

- **WHEN** an editor writes `{{ItemSource}}` for an item with a source and a chance
- **THEN** the item's source query lists that row, marked as a community row

#### Scenario: An unknown key

- **WHEN** a `{{SpawnPoint}}` names a character key that does not exist
- **THEN** no row is stored and the page joins the tracking category

#### Scenario: A game update

- **WHEN** generated rows are refreshed for a new build
- **THEN** every community row still exists

### Requirement: Query templates answer the common questions

Documented query templates SHALL render, from the tables: the roster of a zone, the abilities of a class by level with the item that teaches each, the stock of a vendor with prices and quest unlocks, the sources of an item, the drops of a character, the drops in a zone, the data of a quest, the faction effects of kills and quests, and sortable lists of items, zones, quests, and bosses. A template SHALL accept a page name or a stable key and default to the current page. A page name that matches several entities SHALL produce an error that lists their keys. Each template's documentation SHALL hold an example with its output.

#### Scenario: A zone roster

- **WHEN** `{{Zone roster}}` is placed on the Port Azure page
- **THEN** it lists every character that spawns in Port Azure with tier, level, spawn chance, and whether it spawns only at night

#### Scenario: An ambiguous name

- **WHEN** a template receives a page name shared by several entities
- **THEN** it shows an error that lists their stable keys

### Requirement: A game update refreshes the tables

`wiki cargo deploy` SHALL save only the storage pages whose text changed, then verify every table, then purge the pages that use query templates. A failed verification SHALL fail the deploy.

#### Scenario: A drop chance changes

- **WHEN** a new build changes a drop chance
- **THEN** the deploy saves the storage page that holds the row, verification passes, and pages that show the chance show the new value

### Requirement: Privileged operations fail before they change anything

`wiki cargo create-tables` SHALL run through the interface-admin session. When that session lacks `recreatecargodata`, the command SHALL fail before any change and name the grant to enable. A schema change to an existing table SHALL use a replacement table, SHALL stop with instructions for the switch-in at Special:CargoTables, and SHALL verify the switched table when it runs again.

#### Scenario: The grant is missing

- **WHEN** the interface session lacks `recreatecargodata`
- **THEN** the command fails before any change and names the `cargoadmin` grant

#### Scenario: A schema change

- **WHEN** a column is added to an existing table
- **THEN** the command creates the replacement table, fills it, and stops with the switch-in instructions

### Requirement: Storage pages stay within limits

A storage page SHALL hold at most 1,000 rows and at most 1 MB of text. Generation SHALL fail when a table's shard would exceed either limit and name the table.

#### Scenario: A table grows

- **WHEN** a new build adds rows so that a shard of `Spawns` would hold 1,001 rows
- **THEN** generation fails and names `Spawns`
