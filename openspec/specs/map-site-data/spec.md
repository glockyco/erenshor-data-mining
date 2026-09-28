# map-site-data Specification

## Purpose
Defines how the interactive map site delivers game data to the browser: the build computes all page data from the clean database, the site publishes that database for other consumers, and no page downloads it.

## Requirements

### Requirement: Legacy companion interfaces keep working

Every interface that a shipped companion mod build uses SHALL keep its behavior: the `/map` document on both hosts with its `layers` and `sel` query parameters, including layer keys that earlier site versions wrote, the live-entity WebSocket messages on port 18585 for `/map`, the player-position WebSocket messages on port 18584 for `/maps/[mapName]`, and the `/db/erenshor.sqlite` resource.

#### Scenario: A shipped overlay hides the spawn markers

- **WHEN** a companion overlay loads `/map?layers=-sp,-spr,-spu,-npc` on either host
- **THEN** the enemy, elite, boss, and NPC spawn layers are hidden

#### Scenario: An older mod reports a live enemy with a rarity

- **WHEN** the companion mod sends a live enemy with `rarity` set to `boss` or `rare` and no stored tier matches its name
- **THEN** the map shows the enemy as a boss or an elite

#### Scenario: The retired zone map mod sends a player position

- **WHEN** a zone page receives a player-position message on port 18584
- **THEN** the page shows the player marker at that position

### Requirement: The site publishes the clean database

The map build output SHALL contain the selected variant's clean database at `/db/erenshor.sqlite`, byte-identical to the source file. The build output SHALL contain no other `.sqlite` file.

#### Scenario: Build output is inspected

- **WHEN** `maps build` completes
- **THEN** `db/erenshor.sqlite` in the build directory has the same bytes as the selected variant's clean database
- **AND** the build directory contains no other file that ends in `.sqlite`

#### Scenario: An external consumer downloads the database

- **WHEN** a client requests `/db/erenshor.sqlite` from a deployed host
- **THEN** the response is a valid SQLite database

#### Scenario: A database file remains in the static assets

- **WHEN** `maps build` finds a `.sqlite` file or link under the maps static asset directory
- **THEN** the build fails before it prerenders
- **AND** the error names the path to delete

### Requirement: Pages do not download the database

No page and no service worker SHALL request a `.sqlite` resource.

#### Scenario: A first-time visitor opens the home page

- **WHEN** a browser with no cache opens `/` and the service worker installs
- **THEN** no request for a `.sqlite` resource occurs

#### Scenario: A visitor uses the world map and a zone map

- **WHEN** a visitor opens `/map`, opens a spawn-point popup, and opens `/maps/Stowaway`
- **THEN** no request for a `.sqlite` resource occurs

### Requirement: Zone pages render from prerendered data

Each `/maps/[mapName]` page SHALL receive its markers and its north bearing as prerendered data from the build. The markers SHALL match what the clean database defines for that zone.

#### Scenario: A zone page loads

- **WHEN** a visitor opens `/maps/Stowaway`
- **THEN** the page shows the spawn points, zone lines, and other markers that the clean database places in that zone
- **AND** the map uses the zone's north bearing from the clean database

### Requirement: Popups show details from the prerendered page data

The world map popups SHALL take drops and vendor stock from the prerendered `/map` data, without a further request. They SHALL show the same items that the map item search shows: items that the mapping hides from the map SHALL NOT appear.

#### Scenario: A spawn-point popup opens

- **WHEN** a visitor opens the popup of a spawn point
- **THEN** the popup shows each character's drops, ordered by drop chance from high to low and then by item name
- **AND** the popup shows the vendor stock of each vendor character, including items that a quest unlocks for that vendor, ordered by item name
- **AND** the page makes no network request for this content

#### Scenario: A drop is hidden from the map

- **WHEN** a character drops an item whose mapping hides it from the map
- **THEN** the character's popup does not list that item

#### Scenario: A live entity has a name that several characters share

- **WHEN** the companion mod reports a live entity whose display name belongs to several map-visible characters
- **THEN** the popup combines the drops of the characters that are placed in the live scene
- **AND** the popup combines the drops of all characters with that name when none is placed in the live scene

### Requirement: The service worker removes the old database cache

The service worker SHALL delete any cache that an earlier version created for the database file when it activates.

#### Scenario: A returning visitor has the old service worker

- **WHEN** the new service worker activates in a browser that holds a database cache from an earlier version
- **THEN** that cache no longer exists

### Requirement: The build reads the clean database from the selected variant

`maps build` and `maps dev` SHALL pass the selected variant's clean database path to the site build. They SHALL NOT create, replace, or remove files under the maps source directory to do this.

#### Scenario: A variant build runs

- **WHEN** a user runs `erenshor -V playtest maps build`
- **THEN** the prerendered data and the published database come from `variants/playtest/erenshor-playtest.sqlite`
- **AND** the maps source directory is unchanged after the command exits

#### Scenario: The database path is not set

- **WHEN** the site build runs without a database path
- **THEN** the build fails with an error that names the missing setting
