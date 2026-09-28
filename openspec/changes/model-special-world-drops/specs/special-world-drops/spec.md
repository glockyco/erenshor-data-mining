## Purpose

Defines how the pipeline records the special world drops that every loot-table kill rolls in addition to its own table, and how item-facing outputs present them.

## ADDED Requirements

### Requirement: Special world drops come from game data and game code

The pipeline SHALL take the items of each special world drop roll from the exported `GameManager` and `Misc` components of the shipping build, and the chance, level gate, and branch split of each roll from code facts. It SHALL NOT hardcode any item, chance, or level gate.

#### Scenario: A game update changes a roll

- **WHEN** a new build changes the chance, the level gate, or the mask split of a special world drop roll
- **THEN** `extract code-facts` fails and names the fact

#### Scenario: A game update changes a pool

- **WHEN** a new build adds an item to the world drop mold pool
- **THEN** the next clean build lists that item as a world drop without a code change

### Requirement: One row per item and roll with a per-kill chance

The clean database SHALL hold one special world drop row for each item and roll. Each row SHALL state the chance per kill at the default loot rate and without bonuses, and the level that the killed character must exceed. For a roll that picks from a pool, the chance of an item SHALL be the roll chance times the item's share of the pool entries. For the mask roll, ordinary masks SHALL share 98% of the roll and the Molorai Mask SHALL receive 2%.

#### Scenario: A single-item roll

- **WHEN** the clean build runs on the current main build
- **THEN** Crystallized Balance has a row with a chance of 0.05% and a level gate above 30

#### Scenario: A pool roll

- **WHEN** the world drop mold pool has 11 entries and one of them is a given mold
- **THEN** that mold has a chance of 0.5% divided by 11 per kill and no level gate

#### Scenario: The mask roll

- **WHEN** the mask pool has 15 entries
- **THEN** each ordinary mask has a chance of 0.1% times 98% divided by 15
- **AND** the Molorai Mask has a chance of 0.1% times 2%

### Requirement: Disabled rolls produce no rows

A roll that a game flag disables in the shipping build SHALL produce no rows.

#### Scenario: The demo-only roll in the main build

- **WHEN** `DemoBuild` is off
- **THEN** the demo-only roll has no rows

#### Scenario: Masks are off

- **WHEN** `DropMasks` is off
- **THEN** no mask has a special world drop row

### Requirement: Item outputs show world drops as a source

The wiki item page, the drop-chances sheet, the Lua/Cargo item data, and the map item search SHALL show each special world drop row of an item as a world drop source with its chance and level gate. They SHALL NOT attribute the drop to a specific character.

#### Scenario: Crystallized Balance on the wiki

- **WHEN** the wiki pages are generated
- **THEN** the Crystallized Balance page lists a world drop from any enemy above level 30 at 0.05% per kill
- **AND** it still lists the Braxonian Fossil source

#### Scenario: Crystallized Balance in the map search

- **WHEN** a visitor searches the map for Crystallized Balance
- **THEN** the item result shows the world drop source with its chance and level gate
- **AND** the result is not reported as having an unknown source

#### Scenario: The drop-chances sheet

- **WHEN** the sheets are generated
- **THEN** the drop-chances sheet has a world drop row for each special world drop row, with the level gate
