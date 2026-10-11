## Purpose

Defines how lists that span several entities, such as a vendor's stock or a zone's roster, reach wiki pages from generated data, what each view shows, and how editors use and extend them.

## ADDED Requirements

### Requirement: Views render generated data

A view template SHALL render its rows only from its generated data module under `Module:Erenshor/Data/`, with entity names, pages, and icons from the link catalog `Module:Erenshor/Data/Links`. An edit of an article SHALL NOT change the rows of any view.

#### Scenario: A vendor's stock

- **WHEN** `{{Vendor stock}}` is placed on the Breena Carpenter page on the current main build
- **THEN** it lists her 7 items and the 14 items that quests add, each with its price from the clean database
- **AND** each item that a quest adds names that quest

#### Scenario: A game update

- **WHEN** a new game build changes a vendor's stock
- **THEN** the data deploy changes the vendor stock data module and no article
- **AND** the vendor's page shows the new stock after MediaWiki re-renders it

### Requirement: Generated view data is checked before it is written

Generation SHALL fail and name the module, the row, and the field when a stable key does not resolve in the link catalog, when a value holds wiki markup or a line break, or when a value has another type than its field's declaration.

#### Scenario: An unknown key

- **WHEN** a builder emits a row whose item key matches no entity of the link catalog
- **THEN** `wiki generate-lua` fails and names the module, the row, and the field

#### Scenario: Markup in a value

- **WHEN** a builder emits a value that contains `[[`
- **THEN** `wiki generate-lua` fails and names the module, the row, and the field

### Requirement: Each data module describes its fields

Each view data module SHALL begin with a comment that lists every field with its type and meaning, generated from the same declaration as the rows.

#### Scenario: Reading a data module

- **WHEN** an editor opens `Module:Erenshor/Data/VendorStock`
- **THEN** its opening comment names each field of a row with its type and meaning

### Requirement: A view finds the entity of its page

A view SHALL use its `stablekey` argument when one is given. Otherwise it SHALL use the entity of its kind whose page is the current page. When several entities of the kind share the page, the view SHALL show an error that lists their stable keys. When the entity has no rows, the view SHALL say that the data is missing and add the page to the view's tracking category.

#### Scenario: A page with several entities

- **WHEN** a view is placed without `stablekey` on a page that two vendors share
- **THEN** it shows an error that lists both stable keys

#### Scenario: An entity without data

- **WHEN** `{{Vendor stock}}` is placed on the page of a character that sells nothing
- **THEN** it says that the vendor stock data is missing
- **AND** the page joins the tracking category of the view

### Requirement: Zone rosters group characters by encounter tier

The zone roster SHALL list each character that the clean database places in the zone, grouped by encounter tier, with its level.

#### Scenario: Abyssal Lake

- **WHEN** `{{Zone roster}}` is placed on the Abyssal Lake page on the current main build
- **THEN** it lists the same 9 enemies and 6 bosses as the page's hand-written table, each under its tier

### Requirement: Class ability lists show how each ability is learned

The class abilities view SHALL list each ability that an item teaches to the class, with its required level and the items that teach it.

#### Scenario: Druid summons

- **WHEN** `{{Class abilities}}` is placed on the Druid page on the current main build
- **THEN** it lists the six Druid summon spells, each with the spell scroll that teaches it

### Requirement: The quest panel shows how a quest is reached and what it gives

The quest panel SHALL show how a quest is acquired, who completes it, the items it requires, and its rewards. When the export records no reward of a kind, the panel SHALL say so instead of showing a placeholder.

#### Scenario: A quest given on a keyword

- **WHEN** the panel is placed on A Skeleton Eye for Alyssia Fearnon
- **THEN** it shows that Alyssia Fearnon gives the quest on the keyword "favor"
- **AND** it shows 155 experience and the Bonestudded Belt as rewards

#### Scenario: A quest that follows other quests

- **WHEN** the panel is placed on Secure Port Azure
- **THEN** it shows that the quest follows Sivakayan Intel for Kilkay (1) or Sivakayan Intel for Ripper
- **AND** it shows that the quest is turned in to Captain Kilkay

#### Scenario: A quest without rewards

- **WHEN** the panel is placed on The Tragedy at Goodsoil
- **THEN** it says that the quest gives no experience, gold, or item

### Requirement: Views replace the hand-maintained tables

Each table that design D3 of `adopt-data-backed-wiki` lists for step 3 SHALL render from a view. A replacement SHALL keep the text that editors wrote outside the table and the column values that only editors know. No tool outside the `erenshor` package SHALL write wiki tables.

#### Scenario: The vendor pages

- **WHEN** the vendor slice is complete
- **THEN** no vendor page holds a `Store inventory` table, each shows `{{Vendor stock}}`, and no file refers to `vendor_inventory_tables`

#### Scenario: Notes on the Zones overview

- **WHEN** the Zones overview is replaced by `{{Zone list}}`
- **THEN** each note that editors wrote in the old table appears in the notes column of its zone
- **AND** a parameter that names no zone adds the page to a tracking category
