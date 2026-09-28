## Purpose

Defines the browser smoke test that the maps CI leaf runs, so that a runtime failure of the map site fails verification before a deploy.

## ADDED Requirements

### Requirement: The maps leaf runs the site in a browser

`erenshor test maps` SHALL build the site from the deterministic map fixture, serve the build over HTTP, and load it in headless Chromium. The leaf SHALL fail when any check of this requirement fails.

#### Scenario: The site works

- **WHEN** the maps leaf runs against a correct build
- **THEN** `/`, `/map`, and `/maps/Stowaway` load without an uncaught page error and without a failed same-origin request
- **AND** `/map` draws the world map canvas
- **AND** `/maps/Stowaway` shows the fixture's spawn-point markers
- **AND** the leaf passes

#### Scenario: A popup is broken

- **WHEN** the spawn-point popup of the fixture enemy does not show the fixture's drop items, or the fixture vendor's popup does not show its stock
- **THEN** the maps leaf fails and names the missing content

#### Scenario: A page raises an error

- **WHEN** any checked page raises an uncaught error
- **THEN** the maps leaf fails and reports the page and the error text

#### Scenario: The legacy overlay query stops working

- **WHEN** `/map?layers=-sp,-spr,-spu,-npc` leaves any spawn layer visible
- **THEN** the maps leaf fails and names the visible layer

### Requirement: The smoke test guards the published database

The browser smoke test SHALL fail when any checked page or the service worker requests a `.sqlite` resource. It SHALL also fail when `/db/erenshor.sqlite` is not served as a valid SQLite database.

#### Scenario: A page requests the database

- **WHEN** a checked page requests a URL that ends in `.sqlite`
- **THEN** the maps leaf fails and reports the URL

#### Scenario: The published database is missing

- **WHEN** `/db/erenshor.sqlite` does not return a body that starts with the SQLite file header
- **THEN** the maps leaf fails

### Requirement: Chromium is a checked precondition

The maps leaf SHALL check before it runs that the Chromium build of the locked Playwright version is installed. When Chromium is absent, the leaf SHALL fail before any build and SHALL name the command that installs it. CI SHALL install that Chromium build before it runs the leaf.

#### Scenario: Chromium is missing

- **WHEN** a user runs `erenshor test maps` on a workstation without the Playwright Chromium build
- **THEN** the preflight fails
- **AND** the message names `pnpm --dir src/maps exec playwright install chromium`

#### Scenario: CI runs the maps job

- **WHEN** the CI maps job runs on a clean runner
- **THEN** it installs the Playwright Chromium build before it runs `erenshor test maps`
