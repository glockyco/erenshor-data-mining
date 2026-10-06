## ADDED Requirements

### Requirement: Publishing plans against one listing of the live wiki

Publishing SHALL read the live wiki's files in one listing that gives each file's hash, latest uploader, and upload comment. It SHALL give every catalog title one verdict: create, update, unchanged, redirect, conflict, retire, or orphan. A dry run SHALL write nothing and SHALL show the count of each verdict and a contact sheet of every picture that would change, with the live and the new picture side by side.

#### Scenario: A game update changes two icons

- **WHEN** the catalog differs from the live wiki in two icon pictures and nothing else
- **THEN** the dry run plans two updates and counts every other title as unchanged
- **AND** its contact sheet shows the live and new picture of both icons

#### Scenario: A run is interrupted

- **WHEN** a publish run stops after half of its uploads
- **THEN** the next run plans only the uploads that did not happen

### Requirement: Unchanged pictures are not uploaded

Publishing SHALL NOT upload a picture whose pixels equal those of the live file at its title, even when the files' bytes differ.

#### Scenario: The live file has the same pixels in another encoding

- **WHEN** the live file at a title decodes to the same pixels as the catalog picture but its bytes differ
- **THEN** the plan counts the title as unchanged and uploads nothing

### Requirement: The bot updates only the files it owns

The bot SHALL update a file only when the bot account or the operator account that runs it uploaded its latest version. A file whose latest version someone else uploaded SHALL be a conflict: the plan SHALL name the file and its uploader, and the bot SHALL NOT overwrite it. An upload SHALL be confirmed only when the wiki's warnings are among those expected for that verdict.

#### Scenario: An editor improved a bot icon

- **WHEN** an editor uploaded a new version of a bot icon and the game later changes that icon
- **THEN** the plan reports a conflict naming the file and the editor
- **AND** the editor's version stays the latest version

#### Scenario: An icon that the old pipeline uploaded under the operator's account

- **WHEN** the operator's account uploaded the latest version of an icon before the bot account existed
- **THEN** the plan updates or retires that file like one of the bot's

#### Scenario: An unexpected warning

- **WHEN** the wiki answers an update with a warning other than the one its verdict expects
- **THEN** the bot skips the upload and reports the warning

### Requirement: Every bot upload records its provenance

Every bot upload SHALL carry an upload comment with the game build, the picture's kind and source asset, and its pixel hash. A new file's description page SHALL say how the picture was made and carry the game's copyright notice. Later uploads SHALL NOT replace the description page.

#### Scenario: An icon is updated after a game update

- **WHEN** the bot uploads a changed icon
- **THEN** the new file version's comment names the game build, the source texture, and the pixel hash
- **AND** the file's description page keeps its text

### Requirement: One file holds each picture

Each distinct picture SHALL have one file. Every other entity title that uses the picture SHALL be a file redirect that names that file directly, because MediaWiki shows a file through one redirect only, so that every title a page names keeps resolving. When the entity that names a file no longer uses the picture, the bot SHALL move the file to a title that still uses it and leave a redirect only where a page needs one.

#### Scenario: Two items share a picture

- **WHEN** a new item uses the same picture as an existing item
- **THEN** the bot creates the new item's title as a redirect to the existing file and uploads nothing

#### Scenario: A shared picture changes

- **WHEN** a game update changes a picture that 35 items use
- **THEN** the bot uploads one new file version, and all 35 titles show it

### Requirement: Copies of a picture are deleted

When a title that the catalog makes a redirect holds a file whose latest version the project uploaded, publishing SHALL delete that file with the operator's administrator account and create the redirect at the freed title at once. Every other File redirect that names the deleted copy SHALL then name the picture's file. Publishing SHALL NOT delete a file whose latest version someone else uploaded.

#### Scenario: An identical copy from the old pipeline

- **WHEN** `File:Spell Scroll Annihilate.png` holds a bot copy of a picture whose file has another title
- **THEN** the run deletes the copy and makes the title a redirect to the picture's file

#### Scenario: A title with a colon during a deletion

- **WHEN** `File:Spell Scroll: Annihilate.png` redirects to a bot copy that the run deletes
- **THEN** the run points the title at the picture's file before it deletes the copy, so the title shows a picture throughout

#### Scenario: A redirect through another redirect

- **WHEN** a title redirects to a redirect of the picture's file
- **THEN** the plan points the title at the file itself

#### Scenario: A redirect that no page names

- **WHEN** `File:RoyalCarapace.png` redirects to a copy that the run deletes, and no catalog title is `File:RoyalCarapace.png`
- **THEN** the run points it at the picture's file

### Requirement: The bot's files that nothing produces are deleted

Publishing SHALL delete every file whose latest version the bot account uploaded, that no catalog title produces, and that no page shows, together with the File redirects that name it, and the dry run SHALL list each one before. It SHALL NOT delete a file that a page shows when the run reaches it, and it SHALL NOT delete a file of another account as an orphan.

#### Scenario: An icon under an old spelling

- **WHEN** `File:Spell_Scroll-_Aetherstorm.png` is a bot file, the catalog produces `File:Spell Scroll Aetherstorm.png`, and no page uses the old file
- **THEN** the run deletes the old file

#### Scenario: The operator's own upload that no page shows

- **WHEN** the operator uploaded `File:Raids.png` by hand and no page shows it
- **THEN** the plan lists it as unused and the run leaves it alone

### Requirement: The wiki draws the frames of game icons

Icon files SHALL be the game's pictures without frames. Every template and module that shows an item, spell, skill, or stance icon SHALL draw its frame as the game does, at every size it uses. An item SHALL sit in a slot whose ring is the game's vertical gradient. A spell or skill SHALL lie under the game's hotbar frame. An icon SHALL fit within the slot's outer square, keep its proportions, and never extend past it.

#### Scenario: An item tooltip

- **WHEN** an item's tooltip header shows its icon at 80 px
- **THEN** the icon sits in a slot whose ring runs from light grey at the top through blue to grey-teal at the bottom

#### Scenario: A texture wider than tall

- **WHEN** an item's texture is 501 × 486 pixels
- **THEN** the wiki shows it within the slot's square at its own proportions

#### Scenario: A spell link in running text

- **WHEN** a page links a spell with its icon at 24 px
- **THEN** the spell's art shows under the game's hotbar frame

#### Scenario: An infobox picture

- **WHEN** an Ability infobox shows its spell's picture at full size
- **THEN** the picture shows without a frame, because the game frames icons in slots, not pictures

## MODIFIED Requirements

### Requirement: Bot uploads need human review

The bot SHALL upload a rendered picture only from a set approved after visual review. The review SHALL show each file's title, subject, build, camera preset, and image. An unapproved or failed render SHALL remain unpublished. Game icons, which the game itself ships as pictures, SHALL need no review of single pictures, and every icon that a run changes SHALL appear in its dry run's contact sheet.

#### Scenario: A review rejects one image

- **WHEN** a reviewed batch has one dark or wrong-model image
- **THEN** the bot uploads no copy of that rejected image

#### Scenario: A game update changes an icon

- **WHEN** a game update changes an item's icon texture
- **THEN** the dry run's contact sheet shows the item's live and new icon before anything is uploaded

### Requirement: A missing image upload does not replace an existing file

Before each write, publishing SHALL check the exact file title against the live wiki again, including a redirect target. A title that gained a file since the plan SHALL be skipped and reported with its uploader. The bot SHALL NOT overwrite an image whose latest version someone else uploaded, including an editor's replacement of a bot capture. Uploads SHALL use the title that the generated page resolves to, including any required redirect.

#### Scenario: An editor fills a missing title while the upload is prepared

- **WHEN** an editor uploads the file after the plan was made but before the bot uploads it
- **THEN** the bot leaves the editor's file intact and reports that it skipped the title

#### Scenario: A file name contains a colon

- **WHEN** a generated page names `Summoned: Brute.png`
- **THEN** the uploaded file or its redirect makes that exact name resolve to the reviewed creature image
