# game-image-catalog Specification

## Purpose

Identify, extract, and catalogue every game picture that the wiki or the map shows, so that each consumer shows the picture the game shows and can tell exactly which pictures changed between builds.

## Requirements

### Requirement: Icons resolve through the game's sprite references

The export SHALL record, for each item, spell, and skill icon, the texture asset that its sprite references. The catalog SHALL take the icon's picture from that texture and SHALL NOT find a picture by matching a sprite name to a file name. An icon whose referenced texture is missing from the export SHALL fail the build and name the entity and the texture.

#### Scenario: A sprite name differs from its texture's file name

- **WHEN** the export names Thorned Branch's icon sprite `4_7` and that sprite references the texture `4_8.png`
- **THEN** the catalog takes Thorned Branch's picture from `4_8.png`

#### Scenario: A referenced texture is missing

- **WHEN** an item's icon sprite references a texture that the export did not write
- **THEN** the build fails and names the item and the texture

### Requirement: An icon picture is the game's texture

The catalog SHALL store an icon as its referenced texture at native size, with no frame, border, background, crop, or padding added. The game shows the whole texture in the slot, so the catalog SHALL keep the whole texture, including its transparent margins.

#### Scenario: An item icon keeps its own margins

- **WHEN** the catalog stores the Solunarian Armguard icon, whose texture has a transparent margin around the art
- **THEN** the stored picture has the texture's size and the same margin

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

### Requirement: Picture bytes are deterministic

Building the catalog twice from the same export SHALL produce byte-identical files for every picture. A picture's identity SHALL depend on its decoded pixels, not on its encoding, so a change of encoder or compression alone SHALL NOT make a picture count as changed.

#### Scenario: A rebuild without game changes

- **WHEN** the catalog is built twice from one export
- **THEN** every picture file and every pixel hash is identical between the two builds

#### Scenario: Only the encoder changes

- **WHEN** the image library changes how it compresses PNG files and the pixels stay the same
- **THEN** no picture counts as changed

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

The catalog SHALL give every linked entity the wiki file title of its picture, made of the entity's subject, a space, the picture's role, and `.png`. The subject SHALL be the entity's image name without the characters that MediaWiki forbids in file names, with runs of whitespace collapsed. Every title SHALL be one that MediaWiki can hold a file at, so no title needs a redirect from another spelling.

#### Scenario: A stance uses its activating skill's picture

- **WHEN** the stance Aggressive, whose image name is `Stance: Aggressive`, is activated by a skill
- **THEN** the catalog links Aggressive to that skill's picture under the title `Stance Aggressive icon.png`

### Requirement: Picture roles distinguish icons and renders

The role SHALL be `icon` for the game picture of an item, spell, skill, or stance and `render` for the rendered model of a character or an item.

#### Scenario: A character's portrait

- **WHEN** the catalog holds the approved render of Faith
- **THEN** Faith's title is `Faith render.png`

#### Scenario: An item and a character share an image name

- **WHEN** an item without a render and a character have the same image name
- **THEN** the item's title ends in ` icon.png`, the character's in ` render.png`, and both are in the catalog

#### Scenario: An item's render

- **WHEN** the catalog holds the approved render of the Molorai Bow
- **THEN** the Molorai Bow's titles are `Molorai Bow icon.png` and `Molorai Bow render.png`

### Requirement: Wiki picture titles are unambiguous

A build SHALL fail when one title names two different pictures, and name both entities.

#### Scenario: An item render and a character render share a title

- **WHEN** an item with an approved render and a character with an approved render have the same image name, and their renders differ
- **THEN** the build fails and names both

### Requirement: Body-specific render titles reflect pixel differences

An item whose parts differ between the male and the female body SHALL have `render (male)` and `render (female)` instead of `render`, unless its two approved renders have equal pixels, which SHALL give it one `render`.

#### Scenario: An item with a render for each body

- **WHEN** the catalog holds the approved male and female renders of the Wolfhide Boots
- **THEN** their titles are `Wolfhide Boots render (male).png` and `Wolfhide Boots render (female).png`, and the item has no `Wolfhide Boots render.png`

#### Scenario: Two body renders with equal pixels

- **WHEN** the approved male and female renders of the Adorned Mitts have equal pixels
- **THEN** the item's title is `Adorned Mitts render.png`, with no title for one body

#### Scenario: An item with both kinds of render

- **WHEN** an item has an approved plain render and an approved render for one body
- **THEN** the build fails and names the item
