## ADDED Requirements

### Requirement: Character infoboxes show the render and the screenshot

A character infobox SHALL take the title of the character's render in `render` and of its screenshot in `screenshot`, and generation SHALL fill both: the render title from the catalog and the screenshot title as `<subject> screenshot.png`. The infobox SHALL show the render first. When both files exist, it SHALL show them as two tabs labelled Render and Screenshot. When only one exists, it SHALL show that one alone. An editor's `imagecaption` SHALL show beneath the pictures in every case.

#### Scenario: A character with a render and a screenshot

- **WHEN** `Faith render.png` and `Faith screenshot.png` both exist
- **THEN** Faith's infobox shows the render under the selected Render tab
- **AND** the Screenshot tab shows the screenshot

#### Scenario: A character with a render only

- **WHEN** `Faith render.png` exists and `Faith screenshot.png` does not
- **THEN** Faith's infobox shows the render alone, without tabs

#### Scenario: An editor uploads a screenshot

- **WHEN** an editor uploads `Faith screenshot.png` and the page is refreshed
- **THEN** Faith's infobox gains the Screenshot tab without an edit of the page

#### Scenario: A caption with two pictures

- **WHEN** a character infobox with both pictures has the caption "Ruff and ready"
- **THEN** the caption shows beneath the tabs

### Requirement: Editors' screenshots have their own title

The bot SHALL NOT upload to a character's screenshot title, and SHALL NOT move or delete a file there, because the title belongs to the editors. The publication plan SHALL NOT count a screenshot title as a conflict. The Game Data guide SHALL tell editors to upload a character's screenshot under the screenshot title that its infobox names.

#### Scenario: A screenshot beside a bot render

- **WHEN** an editor uploaded `Faith screenshot.png` and the bot updates `Faith render.png`
- **THEN** the publication plan lists the render's update and nothing for the screenshot

### Requirement: A picture whose title changes keeps its file history

When a picture's file title changes and a file of the project at another title holds the picture, publishing SHALL move that file to the new title instead of uploading a copy. The move SHALL leave a file redirect at the old title. Every other File redirect that named the old title SHALL then name the new title, so no redirect leads through another. The plan SHALL list each move with its old and new title, and a reverted run SHALL move each file back and restore each redirect it changed. Publishing SHALL NOT move a file whose latest version someone else uploaded.

#### Scenario: A game update renames an entity

- **WHEN** a game update changes an item's image name and its picture stays the same
- **THEN** the run moves the file from the old title to the new one, and the old title redirects to it

#### Scenario: A redirect to the moved file

- **WHEN** another item's title redirects to the file that the run moves
- **THEN** the redirect names the file's new title

#### Scenario: A run is reverted

- **WHEN** an operator reverts a run that moved a file and retargeted its redirects
- **THEN** the file is back at its old title and every redirect names the title it named before the run

## MODIFIED Requirements

### Requirement: Character infoboxes identify missing images by kind

Character infoboxes SHALL add a hidden, kind-specific `Needs Image` category to a main-namespace page when neither the render nor the screenshot title has an uploaded image, including when a file description page or redirect exists at the title. They SHALL NOT add that category when either image exists. They SHALL distinguish chest, summon, and other character images. Item, spell, skill, and stance icons come from the game's icon export, so their infoboxes SHALL NOT add a `Needs Image` category. A later upload SHALL remove the page from the category when the page is refreshed.

#### Scenario: A missing chest appears on a boss page

- **WHEN** Frost holds a Braxonian Chest infobox whose render and screenshot do not exist
- **THEN** Frost is in `Category:Needs Chest Image`
- **AND** its chest infobox remains on the page

#### Scenario: An exported icon is not an image request

- **WHEN** an item, spell, skill, or stance page shows an icon from the game's icon export
- **THEN** its infobox adds no `Needs Image` category

#### Scenario: A screenshot without a render

- **WHEN** the Aetherfiend has no render and an editor's screenshot exists at its screenshot title
- **THEN** its page is in no `Needs Image` category and shows the screenshot alone

#### Scenario: A file description exists without image bytes

- **WHEN** a page or redirect exists at the render title but no image is uploaded there or at the screenshot title
- **THEN** the page remains in the right `Needs Image` category

#### Scenario: A missing file is uploaded

- **WHEN** a reviewed render is uploaded and the article is refreshed
- **THEN** the article leaves its `Needs Image` category

### Requirement: Every character model has a capture source

The image workflow SHALL list every character model of the clean database once, under the subject that its characters share, whether or not the wiki has a picture for it. It SHALL show the subject, the render title, the pages of its characters, including pages with the unused notice, its kind, and the game object to capture. Captures and approvals SHALL name a model by its subject. A model whose characters no capture can locate SHALL be listed apart, so that every character belongs to one listed model.

#### Scenario: Characters share a model

- **WHEN** the Vithean Chests of several arena rounds share one model
- **THEN** the manifest captures the subject `Vithean Chest` once, for `Vithean Chest render.png`, from the chest of a generated page

#### Scenario: A character has no page

- **WHEN** a character's model is not shown on any page
- **THEN** the manifest still selects the character for capture, with no pages

#### Scenario: A page with the unused notice

- **WHEN** `Queen Evadne` carries the unused notice
- **THEN** the manifest names her model with that page and selects her prefab for capture

### Requirement: Captures are repeatable and reviewable

The capture workflow SHALL read the manifest of character models. It SHALL record the game build and camera preset for each output. It SHALL render each subject at 1024 × 1024 pixels as the player's camera shows it in an outdoor zone at midday: in the game's day sun and ambient light, through the camera's image effects at the game's default graphics options. It SHALL crop each render with a consistent margin and save one transparent PNG per subject. The output SHALL show the right subject without UI, another character, a clipped model, or a blank image. An unsuccessful capture SHALL be reported, not uploaded. The workflow SHALL restore game state after success, failure, or cancellation.

#### Scenario: Kinds with different models share a page

- **WHEN** the Training Dummy page holds the plain, 400 AC, and 800 AC kinds, which share one model, and the 1000 AC kind, which has its own
- **THEN** the first three show `Training Dummy render.png`
- **AND** the manifest captures `Training Dummy (1000 AC) render.png` from the Expert Training Set's dummy

#### Scenario: A capture shows the game's colours

- **WHEN** the Fernallan Sister Hailey is captured
- **THEN** her robe shows the saturated orange that the player's camera shows in Port Azure at noon, not the duller texture colour

#### Scenario: A capture fails

- **WHEN** the selected game entity has no visible model
- **THEN** the workflow reports its subject and entity and does not offer a blank file for upload
- **AND** the running game is restored to its prior state

#### Scenario: A capture is cancelled

- **WHEN** a capture is cancelled after it changes lighting or hides other characters
- **THEN** the game restores its lighting, characters, camera, and UI

### Requirement: A missing image upload does not replace an existing file

Before each write, publishing SHALL check the exact file title against the live wiki again, including a redirect target. A title that gained a file since the plan SHALL be skipped and reported with its uploader. The bot SHALL NOT overwrite an image whose latest version someone else uploaded, including an editor's replacement of a bot capture. Uploads SHALL use the title that the generated page names.

#### Scenario: An editor fills a missing title while the upload is prepared

- **WHEN** an editor uploads the file after the plan was made but before the bot uploads it
- **THEN** the bot leaves the editor's file intact and reports that it skipped the title

#### Scenario: A file name contains a colon

- **WHEN** the summon spell's creature has the image name `Summoned: Brute`
- **THEN** its page names `Summoned Brute render.png`, and the bot uploads the reviewed creature image under that title

### Requirement: People keep their chosen zone images

A missing image on a zone page SHALL remain the editors' work. The workflow SHALL NOT upload a different map sprite as its image or change the zone page's image field.

#### Scenario: The game has a map sprite with a different name

- **WHEN** a page names `Underspine Hollow.png` and the game has `UnderspineMap.png`
- **THEN** the bot does not upload the map sprite as the page's image or change the page's image field

### Requirement: Publishing plans against one listing of the live wiki

Publishing SHALL read the live wiki's files in one listing that gives each file's hash, latest uploader, and upload comment. It SHALL give every catalog title one verdict: create, update, unchanged, move, redirect, retire, describe, or conflict, and list the orphans. A dry run SHALL write nothing and SHALL show the count of each verdict, each move with its old title, and a contact sheet of every picture that would change, with the live and the new picture side by side.

#### Scenario: A game update changes two icons

- **WHEN** the catalog differs from the live wiki in two icon pictures and nothing else
- **THEN** the dry run plans two updates and counts every other title as unchanged
- **AND** its contact sheet shows the live and new picture of both icons

#### Scenario: A run is interrupted

- **WHEN** a publish run stops after half of its uploads
- **THEN** the next run plans only the uploads that did not happen

### Requirement: One file holds each picture

Each distinct picture SHALL have one file. Every other entity title that uses the picture SHALL be a file redirect that names that file directly, because MediaWiki shows a file through one redirect only, so that every title a page names keeps resolving. When the entity that names a file no longer uses the picture, the bot SHALL move the file to a title that still uses it.

#### Scenario: Two items share a picture

- **WHEN** a new item uses the same picture as an existing item
- **THEN** the bot creates the new item's title as a redirect to the existing file and uploads nothing

#### Scenario: A shared picture changes

- **WHEN** a game update changes a picture that 35 items use
- **THEN** the bot uploads one new file version, and all 35 titles show it

### Requirement: Copies of a picture are deleted

When a title that the catalog makes a redirect holds a file whose latest version the project uploaded, publishing SHALL delete that file with the operator's administrator account and create the redirect at the freed title at once. Every other File redirect that names the deleted copy SHALL then name the picture's file. Publishing SHALL NOT delete a file whose latest version someone else uploaded.

#### Scenario: An identical copy from the old pipeline

- **WHEN** `File:Spell Scroll Annihilate icon.png` holds a bot copy of a picture whose file has another title
- **THEN** the run deletes the copy and makes the title a redirect to the picture's file

#### Scenario: A title with a colon during a deletion

- **WHEN** the old title `File:Spell Scroll: Annihilate.png` redirects to a bot copy that the run deletes
- **THEN** the run points the old title at the picture's file before it deletes the copy, so the old title shows a picture throughout

#### Scenario: A redirect that no page names

- **WHEN** `File:RoyalCarapace.png` redirects to a copy that the run deletes, and no catalog title is `File:RoyalCarapace.png`
- **THEN** the run points it at the picture's file

#### Scenario: A redirect through another redirect

- **WHEN** a title redirects to a redirect of the picture's file
- **THEN** the plan points the title at the file itself

#### Scenario: A copy that hides its redirect

- **WHEN** a title holds a bot copy and its description page redirects to the picture's file
- **THEN** the run deletes the copy, so pages that name the title show the picture

#### Scenario: A picture's file whose description page is a redirect

- **WHEN** the title of a picture's file holds the picture but its description page redirects to an old copy
- **THEN** the run writes the picture's description in place of the redirect

### Requirement: The bot's files that nothing produces are deleted

Publishing SHALL delete every file whose latest version the bot account uploaded, that no catalog title produces, that no move takes to a catalog title, and that no page shows, together with the File redirects that name it, and the dry run SHALL list each one before. It SHALL NOT delete a file that a page shows when the run reaches it, and it SHALL NOT delete a file of another account as an orphan.

#### Scenario: An icon under an old spelling

- **WHEN** `File:Spell_Scroll-_Aetherstorm.png` is a bot file, the picture it holds has its file at `File:Spell Scroll Aetherstorm icon.png`, and no page uses the old file
- **THEN** the run deletes the old file

#### Scenario: The operator's own upload that no page shows

- **WHEN** the operator uploaded `File:Raids.png` by hand and no page shows it
- **THEN** the plan lists it as unused and the run leaves it alone
