# special-world-drops Specification

## Purpose
Defines how the pipeline records independent special selections from eligible loot tables and how item-facing outputs distinguish those selections from receiving an item after unique-item replacement.

## Requirements

### Requirement: Special world drops come from game data and game code

The pipeline SHALL take the items of each special world drop roll from the exported `GameManager` and `Misc` components of the shipping build, and the chance, level gate, and branch split of each roll from code facts. It SHALL NOT hardcode any item, chance, or level gate.

#### Scenario: A game update changes a roll

- **WHEN** a new build changes the chance, the level gate, or the mask split of a special world drop roll
- **THEN** `extract code-facts` fails and names the fact

#### Scenario: A game update changes a pool

- **WHEN** a new build adds an item to the world drop mold pool
- **THEN** the next clean build lists that item as a world drop without a code change

### Requirement: One row per item and roll with a default selection chance

The clean database SHALL hold one special world drop row for each item and roll. Each row SHALL state the selection chance per eligible kill at the default loot rate and without bonuses, before owned unique-item replacement, and the level that the killed character must strictly exceed. For a roll that picks from a pool, the chance of an item SHALL be the roll chance times the item's share of the pool entries. The mask branch split SHALL come from its code fact.


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

#### Scenario: A strict level boundary

- **WHEN** a killed character's level equals a roll's exclusive level gate
- **THEN** that roll cannot select its item
- **AND** the next higher level satisfies that level gate

#### Scenario: An already-owned unique mask

- **WHEN** a mask is unique and the player owns it in stored inventory or equipment when `LootTable.InitLootTable` initializes the source
- **THEN** its published row still describes the pre-replacement selection chance
- **AND** the selected mask is replaced by a draw from `CommonWorldItems`, retaining duplicate and empty slots
- **AND** the selection chance SHALL NOT be labelled an unconditional chance of receiving that mask
- **AND** pickup SHALL NOT be modelled as another ownership check

### Requirement: Special roll eligibility is independent of ordinary caps

The rows SHALL NOT imply that every loot-table host is eligible. A missing host, `DestroyOnDeath`, or an NPC's `DoNotLeaveCorpse` prevents all special rolls. Ordinary noncommon-drop caps do not limit special rolls.

#### Scenario: An ineligible host

- WHEN a host is missing, has `DestroyOnDeath`, or is an NPC with `DoNotLeaveCorpse`
- THEN no special roll is eligible

### Requirement: Special roll probabilities preserve independent checks

Special rolls SHALL be treated as independent checks, not as a categorical pool. Ordinary masks and the Molorai Mask are mutually exclusive branches of one mask check. Adding independent roll probabilities SHALL NOT be used to calculate the probability of at least one special drop.

#### Scenario: Independent successes

- **WHEN** two eligible special checks both succeed
- **THEN** both selections are retained regardless of the ordinary noncommon-drop cap

### Requirement: Default probabilities do not imply adjusted bonuses

Server loot-rate, blessing and top-guild bonuses apply to the other special checks, but not to the mask check. Published default probabilities SHALL NOT be presented as bonus-adjusted probabilities.

#### Scenario: A bonus changes the loot rate

- WHEN a server loot-rate, blessing, or top-guild bonus applies
- THEN the mask check remains unadjusted
- AND published default probabilities are not labelled as bonus-adjusted

### Requirement: Disabled rolls produce no rows

A roll that a game flag disables in the shipping build SHALL produce no rows.

#### Scenario: The demo-only roll in the main build

- **WHEN** `DemoBuild` is off
- **THEN** the demo-only roll has no rows

#### Scenario: Masks are off

- **WHEN** `DropMasks` is off
- **THEN** no mask has a special world drop row

### Requirement: Item outputs show world drops as a source

The wiki item page, the drop-chances sheet, the wiki's Lua item data, and the map item search SHALL show each special world drop row of an item as a world drop source with its default selection chance and level gate. They SHALL NOT attribute the drop to a specific character.

#### Scenario: Crystallized Balance on the wiki

- **WHEN** the wiki pages are generated
- **THEN** the Crystallized Balance page lists a world drop from eligible enemies above level 30 with a default selection chance of 0.05% per kill
- **AND** it still lists the Braxonian Fossil source

#### Scenario: Crystallized Balance in the map search

- **WHEN** a visitor searches the map for Crystallized Balance
- **THEN** the item result shows the world drop source with its chance and level gate
- **AND** the result is not reported as having an unknown source

#### Scenario: The drop-chances sheet

- **WHEN** the sheets are generated
- **THEN** the drop-chances sheet has a world drop row for each special world drop row, with the level gate

### Requirement: Visitor-facing world drop labels stay concise

Visitor-facing text SHALL use concise conventional drop-chance labels. The world-drop view SHALL use a concise default-rate note without technical eligibility or ownership-replacement disclaimers.

#### Scenario: Visitor-facing default-rate note

- WHEN the world-drop view displays its default-rate note
- THEN it uses a concise note without technical eligibility or ownership-replacement disclaimers

### Requirement: Developer documentation retains world drop semantics

Developer documentation SHALL retain the exact host, bonus, independence and unique-item replacement semantics.

#### Scenario: Developer explanation of special rolls

- WHEN developer documentation describes special world drops
- THEN it retains the exact host, bonus, independence and unique-item replacement semantics
