## MODIFIED Requirements

### Requirement: Item outputs show world drops as a source

The wiki item page, the drop-chances sheet, the wiki's Lua item data, and the map item search SHALL show each special world drop row of an item as a world drop source with its default selection chance and level gate. They SHALL NOT attribute the drop to a specific character. Visitor-facing text SHALL use concise conventional drop-chance labels. The world-drop view SHALL use a concise default-rate note without technical eligibility or ownership-replacement disclaimers. Developer documentation SHALL retain the exact host, bonus, independence and unique-item replacement semantics.

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
