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

The catalog SHALL hold each distinct picture once, identified by a hash of its decoded pixels. It SHALL link every item, spell, skill, stance, and character to its picture. Entities whose pictures have equal pixels SHALL share one picture.

#### Scenario: Many items share one texture

- **WHEN** 35 spell scroll items reference the same texture
- **THEN** the catalog holds one picture with 35 item links

#### Scenario: Two textures have equal pixels

- **WHEN** two different texture assets decode to identical pixels
- **THEN** the catalog holds one picture that records both source assets

### Requirement: Picture bytes are deterministic

Building the catalog twice from the same export SHALL produce byte-identical files for every picture. A picture's identity SHALL depend on its decoded pixels, not on its encoding, so a change of encoder or compression alone SHALL NOT make a picture count as changed.

#### Scenario: A rebuild without game changes

- **WHEN** the catalog is built twice from one export
- **THEN** every picture file and every pixel hash is identical between the two builds

#### Scenario: Only the encoder changes

- **WHEN** the image library changes how it compresses PNG files and the pixels stay the same
- **THEN** no picture counts as changed

### Requirement: Every picture records its provenance

The catalog SHALL record, for each picture, the game build, its kind, its source assets, and how it was produced: the export for an icon, or the capture preset and approval for a rendered portrait.

#### Scenario: A reader asks where an icon came from

- **WHEN** the catalog lists the Florablast icon
- **THEN** it shows the game build, the kind `icon`, and the texture asset it was taken from

### Requirement: Rendered portraits enter after review

A rendered portrait SHALL enter the catalog only when a review approved it, bound to the hash of the bytes it was approved with. An approved copy whose bytes differ from that hash SHALL fail the build and name the file, because only a review replaces an approved copy. A new capture with the same pixels as an approved one SHALL keep the same picture.

#### Scenario: An approved copy changes

- **WHEN** an approved portrait file is overwritten outside a review
- **THEN** the build fails and names the file

#### Scenario: A repeat capture of an unchanged model

- **WHEN** a capture after a game update has the same pixels as the approved one
- **THEN** the portrait stays approved and unchanged in the catalog

### Requirement: Every picture has the wiki title of each entity

The catalog SHALL give every linked entity the wiki file title of its picture, made of the entity's subject, a space, the picture's role, and `.png`. The subject SHALL be the entity's image name without the characters that MediaWiki forbids in file names, with runs of whitespace collapsed. The role SHALL be `icon` for the game picture of an item, spell, skill, or stance and `render` for a character's rendered portrait. Every title SHALL be one that MediaWiki can hold a file at, so no title needs a redirect from another spelling. A build SHALL fail when one title names two different pictures, and name both entities.

#### Scenario: A stance uses its activating skill's picture

- **WHEN** the stance Aggressive, whose image name is `Stance: Aggressive`, is activated by a skill
- **THEN** the catalog links Aggressive to that skill's picture under the title `Stance Aggressive icon.png`

#### Scenario: A character's portrait

- **WHEN** the catalog holds the approved render of Faith
- **THEN** Faith's title is `Faith render.png`

#### Scenario: An item and a character share an image name

- **WHEN** an item and a character have the same image name
- **THEN** the item's title ends in ` icon.png`, the character's in ` render.png`, and both are in the catalog
