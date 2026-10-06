## ADDED Requirements

### Requirement: Map item icons come from the image catalog

The map build SHALL make each map-visible item's icon from that item's picture in the image catalog, at the sizes the site shows, fitted within a square and keeping its proportions. It SHALL rebuild an icon when its picture's hash changes and SHALL NOT decide by file times or by matching a sprite name to a file name.

#### Scenario: An icon picture changes in a game update

- **WHEN** a game update changes the picture of a map-visible item
- **THEN** the next map build writes new icon files for that item

#### Scenario: A file is copied with a newer time

- **WHEN** a source picture's file time changes and its pixels do not
- **THEN** the map build keeps that item's icon files unchanged

#### Scenario: A sprite name differs from its texture's file name

- **WHEN** Thorned Branch is map-visible and its sprite is named `4_7` but references the texture `4_8.png`
- **THEN** the map shows the branch picture of `4_8.png`
