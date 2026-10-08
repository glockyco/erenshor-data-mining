## MODIFIED Requirements

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
