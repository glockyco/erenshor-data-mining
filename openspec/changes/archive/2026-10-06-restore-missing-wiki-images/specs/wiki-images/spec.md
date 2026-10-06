## Purpose

Track missing images on generated pages, capture game models consistently, and upload reviewed files without replacing images that people own.

## ADDED Requirements

### Requirement: Character infoboxes identify missing images by kind

Character infoboxes SHALL add a hidden, kind-specific `Needs Image` category to a main-namespace page when the named image file has no uploaded image, including when its file description page or redirect exists. They SHALL NOT add that category when the image exists. They SHALL distinguish chest, summon, and other character images. Empty image fields SHALL also be tracked. Item, spell, skill, and stance icons come from the game's icon export, so their infoboxes SHALL NOT add a `Needs Image` category. A later upload SHALL remove the page from the category when the page is refreshed.

#### Scenario: A missing chest appears on a boss page

- **WHEN** Frost holds a Braxonian Chest infobox whose image does not exist
- **THEN** Frost is in `Category:Needs Chest Image`
- **AND** its chest infobox remains on the page

#### Scenario: An exported icon is not an image request

- **WHEN** an item, spell, skill, or stance page shows an icon from the game's icon export
- **THEN** its infobox adds no `Needs Image` category

#### Scenario: A file description exists without image bytes

- **WHEN** a page or redirect exists at the file title but no image is uploaded
- **THEN** the page remains in the right `Needs Image` category

#### Scenario: A missing file is uploaded

- **WHEN** a reviewed image is uploaded and the article is refreshed
- **THEN** the article leaves its `Needs Image` category

### Requirement: Missing images have a source

The image workflow SHALL list every image file that the wiki does not have and that a generated page or a page with the unused notice names. It SHALL show the file title, every page that uses it, its entity kind, and its source. An empty result SHALL mean that every named file exists, not that a source search returned no rows.

#### Scenario: A generated character has no portrait

- **WHEN** a generated character infobox names a file with no image on the wiki
- **THEN** the report names the file and page and selects the character for capture

#### Scenario: A chest image appears on a boss page

- **WHEN** a boss page also holds a chest infobox that names a missing chest image
- **THEN** the report keeps the chest file and the boss page among its uses

#### Scenario: A page with the unused notice has no image

- **WHEN** `Queen Evadne` carries the unused notice and names a missing image
- **THEN** the report names the file and page and selects her prefab for capture

### Requirement: Game icons are not substitutes for character images

The image workflow SHALL use a game's item, spell, or skill icon as the matching item's, spell's, or skill's image. It SHALL NOT treat an icon of a summon spell as an image of the summoned creature. A character or chest without a suitable sprite SHALL be captured from the running game or reported for editor attention when a useful capture cannot be made.

#### Scenario: A summon spell has an icon but its creature does not

- **WHEN** a summon page names a missing creature image and its spell has an icon
- **THEN** the report marks the creature image as needing capture
- **AND** it does not upload the spell icon under the creature's file name

### Requirement: Captures are repeatable and reviewable

The capture workflow SHALL read a manifest of missing file titles and game entities. It SHALL record the game build and camera preset for each output. It SHALL render each subject at 1024 × 1024 pixels, crop it with a consistent margin, and save one transparent PNG per file. The output SHALL show the right subject without UI, another character, a clipped model, or a blank image. An unsuccessful capture SHALL be reported, not uploaded. The workflow SHALL restore game state after success, failure, or cancellation.

#### Scenario: Kinds with different models share a page

- **WHEN** the Training Dummy page holds the plain, 400 AC, and 800 AC kinds, which share one model, and the 1000 AC kind, which has its own
- **THEN** the first three show `Training Dummy.png`
- **AND** the manifest captures `Training Dummy (1000 AC).png` from the Expert Training Set's dummy

#### Scenario: A capture fails

- **WHEN** the selected game entity has no visible model
- **THEN** the workflow reports its file and entity and does not offer a blank file for upload
- **AND** the running game is restored to its prior state

#### Scenario: A capture is cancelled

- **WHEN** a capture is cancelled after it changes lighting or hides other characters
- **THEN** the game restores its lighting, characters, camera, and UI

### Requirement: Rendered pictures stay readable on the wiki's theme

A rendered character picture SHALL keep its transparent background. The character infobox SHALL show it on a surface that keeps very dark and very bright subjects readable on the wiki's theme. The surface SHALL show only through transparent pixels, so an opaque screenshot looks unchanged.

#### Scenario: A black subject on the dark theme

- **WHEN** a character infobox shows the transparent render of an almost black subject, such as a constellation
- **THEN** its silhouette stands out from the surface behind it

#### Scenario: An editor screenshot in the same infobox

- **WHEN** a character infobox shows an opaque screenshot
- **THEN** the screenshot looks as it did before the surface existed

### Requirement: Bot uploads need human review

The bot SHALL upload only images in a set approved after visual review. The review SHALL show each file's title, subject, build, camera preset, and image. An unapproved or failed image SHALL remain unpublished.

#### Scenario: A review rejects one image

- **WHEN** a reviewed batch has one dark or wrong-model image
- **THEN** the bot uploads no copy of that rejected image

### Requirement: A missing image upload does not replace an existing file

Before each upload, the workflow SHALL check the exact file title against the live wiki, including a redirect target. It SHALL skip a title that exists and report the file and its existing owner. The bot SHALL NOT overwrite an existing image, including an editor replacement of a bot capture. Uploads SHALL use the title that the generated page resolves to, including any required redirect.

#### Scenario: An editor fills a missing title while the upload is prepared

- **WHEN** an editor uploads the file after the inventory was made but before the bot uploads it
- **THEN** the bot leaves the editor's file intact and reports that it skipped the title

#### Scenario: A file name contains a colon

- **WHEN** a generated page names `Summoned: Brute.png`
- **THEN** the uploaded file or its redirect makes that exact name resolve to the reviewed creature image

### Requirement: People keep their chosen zone images

A missing image on a zone page SHALL remain the editors' work. The workflow SHALL NOT upload a different map sprite as its image or change the zone page's image field. Editors MAY replace any bot-captured character image with a better screenshot.

#### Scenario: The game has a map sprite with a different name

- **WHEN** a page names `Underspine Hollow.png` and the game has `UnderspineMap.png`
- **THEN** the bot does not upload the map sprite as the page's image or change the page's image field
