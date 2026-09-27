## Purpose

Defines how the interactive map site delivers game data to the browser: the build computes all data from the clean database, and the browser never downloads that database.

## ADDED Requirements

### Requirement: The site does not publish the database

The map build output SHALL NOT contain a SQLite database file. No page and no service worker SHALL request a `.sqlite` resource.

#### Scenario: Build output is inspected

- **WHEN** `maps build` completes
- **THEN** the build directory contains no file that ends in `.sqlite`

#### Scenario: A database file remains in the static assets

- **WHEN** `maps build` finds a `.sqlite` file or link under the maps static asset directory
- **THEN** the build fails before it prerenders
- **AND** the error names the path to delete

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

### Requirement: Popup details come from one prerendered document

The build SHALL write one popup-detail document for the world map. The document SHALL contain the drops and the vendor stock of each map-visible character, and an index from display name to the map-visible characters with that name and their scenes. The world map SHALL fetch the document on the first popup that needs it, and SHALL NOT fetch it again during the page session.

#### Scenario: A spawn-point popup opens

- **WHEN** a visitor opens the popup of a spawn point
- **THEN** the popup shows each character's drops, ordered by drop chance from high to low and then by item name
- **AND** the popup shows the vendor stock of each vendor character, including items that a quest unlocks for that vendor, ordered by item name

#### Scenario: A live entity has a name that several characters share

- **WHEN** the companion mod reports a live entity whose display name belongs to several map-visible characters
- **THEN** the popup combines the drops of the characters that are placed in the live scene
- **AND** the popup combines the drops of all characters with that name when none is placed in the live scene

#### Scenario: A second popup opens

- **WHEN** a visitor opens a second popup after the document has loaded
- **THEN** the page does not request the document again

#### Scenario: The document cannot be loaded

- **WHEN** the popup-detail request fails
- **THEN** the popup shows an error in place of the drops and the vendor stock
- **AND** the next popup retries the request

### Requirement: The service worker removes the old database cache

The service worker SHALL delete any cache that an earlier version created for the database file when it activates.

#### Scenario: A returning visitor has the old service worker

- **WHEN** the new service worker activates in a browser that holds a database cache from an earlier version
- **THEN** that cache no longer exists

### Requirement: The build reads the clean database from the selected variant

`maps build` and `maps dev` SHALL pass the selected variant's clean database path to the site build. They SHALL NOT create, replace, or remove files under the maps source directory to do this.

#### Scenario: A variant build runs

- **WHEN** a user runs `erenshor -V playtest maps build`
- **THEN** the prerendered data comes from `variants/playtest/erenshor-playtest.sqlite`
- **AND** the maps source directory is unchanged after the command exits

#### Scenario: The database path is not set

- **WHEN** the site build runs without a database path
- **THEN** the build fails with an error that names the missing setting
