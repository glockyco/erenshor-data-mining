## RENAMED Requirements

- FROM: `### Requirement: Rendered portraits enter after review`
- TO: `### Requirement: Renders enter after review`

## MODIFIED Requirements

### Requirement: Each distinct picture appears once

The catalog SHALL hold each distinct picture once, identified by a hash of its decoded pixels. It SHALL link every item, spell, skill, stance, and character to each of its pictures, an item to its icon and its render. Entities whose pictures have equal pixels SHALL share one picture.

#### Scenario: Many items share one texture

- **WHEN** 35 spell scroll items reference the same texture
- **THEN** the catalog holds one picture with 35 item links

#### Scenario: Two textures have equal pixels

- **WHEN** two different texture assets decode to identical pixels
- **THEN** the catalog holds one picture that records both source assets

#### Scenario: Two item renders have equal pixels

- **WHEN** two items switch on the same part in the same colours and their approved renders have equal pixels
- **THEN** the catalog holds one render with both items linked

### Requirement: Every picture records its provenance

The catalog SHALL record, for each picture, the game build, its kind, its source assets, and how it was produced: the export for an icon, or the capture preset and approval for a render.

#### Scenario: A reader asks where an icon came from

- **WHEN** the catalog lists the Florablast icon
- **THEN** it shows the game build, the kind `icon`, and the texture asset it was taken from

#### Scenario: A reader asks where an item render came from

- **WHEN** the catalog lists the Molorai Bow's render
- **THEN** it shows the game build, the kind `render`, the capture preset, and the approval

### Requirement: Renders enter after review

A render of a character or an item SHALL enter the catalog only when a review approved it, bound to the hash of the bytes it was approved with. An approved copy whose bytes differ from that hash SHALL fail the build and name the file, because only a review replaces an approved copy. A new capture with the same pixels as an approved one SHALL keep the same picture.

#### Scenario: An approved copy changes

- **WHEN** an approved render file is overwritten outside a review
- **THEN** the build fails and names the file

#### Scenario: A repeat capture of an unchanged model

- **WHEN** a capture after a game update has the same pixels as the approved one
- **THEN** the render stays approved and unchanged in the catalog

### Requirement: Every picture has the wiki title of each entity

The catalog SHALL give every linked entity the wiki file title of its picture, made of the entity's subject, a space, the picture's role, and `.png`. The subject SHALL be the entity's image name without the characters that MediaWiki forbids in file names, with runs of whitespace collapsed. The role SHALL be `icon` for the game picture of an item, spell, skill, or stance and `render` for the rendered model of a character or an item. An item whose parts differ between the male and the female body SHALL have `render (male)` and `render (female)` instead of `render`. Every title SHALL be one that MediaWiki can hold a file at, so no title needs a redirect from another spelling. A build SHALL fail when one title names two different pictures, and name both entities.

#### Scenario: A stance uses its activating skill's picture

- **WHEN** the stance Aggressive, whose image name is `Stance: Aggressive`, is activated by a skill
- **THEN** the catalog links Aggressive to that skill's picture under the title `Stance Aggressive icon.png`

#### Scenario: A character's portrait

- **WHEN** the catalog holds the approved render of Faith
- **THEN** Faith's title is `Faith render.png`

#### Scenario: An item and a character share an image name

- **WHEN** an item without a render and a character have the same image name
- **THEN** the item's title ends in ` icon.png`, the character's in ` render.png`, and both are in the catalog

#### Scenario: An item's render

- **WHEN** the catalog holds the approved render of the Molorai Bow
- **THEN** the Molorai Bow's titles are `Molorai Bow icon.png` and `Molorai Bow render.png`

#### Scenario: An item render and a character render share a title

- **WHEN** an item with an approved render and a character with an approved render have the same image name, and their renders differ
- **THEN** the build fails and names both

#### Scenario: An item with a render for each body

- **WHEN** the catalog holds the approved male and female renders of the Wolfhide Boots
- **THEN** their titles are `Wolfhide Boots render (male).png` and `Wolfhide Boots render (female).png`, and the item has no `Wolfhide Boots render.png`

#### Scenario: An item with both kinds of render

- **WHEN** an item has an approved plain render and an approved render for one body
- **THEN** the build fails and names the item
