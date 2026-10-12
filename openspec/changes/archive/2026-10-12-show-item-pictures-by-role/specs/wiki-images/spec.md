## ADDED Requirements

### Requirement: Every item model has a capture source

The image workflow SHALL list once, under the subject that its items share, every item whose model the game shows: a weapon or shield, a worn item, a mask, the furnishing of a Reliquary furniture set, and the belt lamp or the lens that a lamp or the Watcher's Lens turns on in a cosmetic slot. It SHALL show the subject, the render title, the item's page, its kind, and the game object to capture. An item without a model SHALL NOT be listed. A capture that cannot find an item's model SHALL report the subject and the missing object.

#### Scenario: Items share a subject

- **WHEN** the common and the rare Letters and Words share the page and the image name `Letters and Words`
- **THEN** the manifest captures the subject `Letters and Words` once, for `Letters and Words render.png`

#### Scenario: An item without a model

- **WHEN** an item has no model in the game, such as Bread
- **THEN** the manifest does not list it

#### Scenario: A furniture set

- **WHEN** the Wood Training Set builds its furnishing in a Reliquary room
- **THEN** the manifest captures that furnishing for `Wood Training Set render.png`

#### Scenario: Lamps that light the same belt lamp

- **WHEN** the Belt Lamp, the Shivering Belt Lamp, and the Keeper's Lantern each light the player's belt lamp in a cosmetic slot
- **THEN** the manifest captures the belt lamp for each of their render titles
- **AND** the catalog holds one picture that all three titles name

#### Scenario: A model that the capture cannot find

- **WHEN** the capture finds no object of the name that an item switches on
- **THEN** it reports the item's subject and the name, and offers no file for upload

### Requirement: An item render shows the piece by itself

A render of an item SHALL show only the item's model, as the game shows it in use: a weapon or shield, the parts that the game switches on for a worn item, a mask, the furnishing of a furniture set, or the belt lamp or the lens of the player. A worn item SHALL show every part that it switches on, in its own colours, without the body: once on each body when the male and female bodies have different models for its parts, and once otherwise. A render SHALL NOT show a body, other equipment, a room, or UI.

#### Scenario: A pair of boots

- **WHEN** the Wolfhide Boots are captured
- **THEN** the render shows both boots in the item's colours
- **AND** it shows no body and no other equipment

#### Scenario: Parts that differ between the bodies

- **WHEN** the Wolfhide Boots switch on `LeatherBoots`, which the male and the female body hold as separate models
- **THEN** the workflow captures `Wolfhide Boots render (male).png` from the male body's parts and `Wolfhide Boots render (female).png` from the female body's parts

#### Scenario: A part that both bodies share

- **WHEN** the Feathered Cape switches on a cape that both bodies share
- **THEN** the workflow captures one `Feathered Cape render.png`

#### Scenario: Items that share a part

- **WHEN** the Aged Plate Bracer and the Azure Plate Bracer both switch on the `ThickPlate` part
- **THEN** each render shows that part in its own item's colours

#### Scenario: A weapon

- **WHEN** the Molorai Bow is captured
- **THEN** the render shows the bow by itself

### Requirement: Item infoboxes show the render and the screenshot

An item infobox SHALL take the titles of the item's renders in `render`, `render_male`, and `render_female`, and of its screenshot in `screenshot`. Generation SHALL fill the render parameters from the item's approved renders in the catalog, and `screenshot` as `<subject> screenshot.png`. The infobox SHALL show the existing files in the order render, male, female, screenshot, as tabs labelled Render, Male, Female, and Screenshot, or one alone. When none exists, it SHALL show the item's icon.

#### Scenario: An item with a render and a screenshot

- **WHEN** `Molorai Bow render.png` and `Molorai Bow screenshot.png` both exist
- **THEN** the Molorai Bow's infobox shows the render under the selected Render tab
- **AND** the Screenshot tab shows the screenshot

#### Scenario: An item with a render only

- **WHEN** `Molorai Bow render.png` exists and `Molorai Bow screenshot.png` does not
- **THEN** the infobox shows the render alone, without tabs

#### Scenario: An item with a male and a female render

- **WHEN** `Wolfhide Boots render (male).png`, `Wolfhide Boots render (female).png`, and `Wolfhide Boots screenshot.png` exist
- **THEN** the infobox shows the tabs Male, Female, and Screenshot, with Male selected

#### Scenario: An item without a model or a screenshot

- **WHEN** Bread has no render and no screenshot
- **THEN** its infobox shows `Bread icon.png`

#### Scenario: An editor uploads a screenshot of an item without a model

- **WHEN** an editor uploads `Bread screenshot.png` and the page is refreshed
- **THEN** Bread's infobox shows the screenshot instead of the icon, without an edit of the page

#### Scenario: A caption

- **WHEN** an item infobox with a render and a screenshot has an editor's `imagecaption`
- **THEN** the caption shows beneath the tabs

### Requirement: Item tooltips and links keep the icon

Item tooltips, item links, gear slots, and hover cards SHALL show the item's icon, whether or not the item has a render or a screenshot.

#### Scenario: An item with a render

- **WHEN** the Molorai Bow's infobox shows its render
- **THEN** the tooltip on its page shows `Molorai Bow icon.png` in its header
- **AND** an `ItemLink` to the Molorai Bow shows the same icon

## MODIFIED Requirements

### Requirement: Captures are repeatable and reviewable

The capture workflow SHALL read the manifest of character and item models. It SHALL record the game build and camera preset for each output. It SHALL render each subject at 1024 × 1024 pixels as the player's camera shows it in an outdoor zone at midday: in the game's day sun and ambient light, through the camera's image effects at the game's default graphics options. It SHALL crop each render with a consistent margin and save one transparent PNG per subject. The output SHALL show the right subject without UI, another character, a clipped model, or a blank image. An unsuccessful capture SHALL be reported, not uploaded. The workflow SHALL restore game state after success, failure, or cancellation.

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

#### Scenario: An item capture leaves the player's equipment alone

- **WHEN** the workflow captures the Wolfhide Boots while the player wears other boots
- **THEN** the player wears the same equipment in the same colours after the capture

### Requirement: Rendered pictures stay readable on the wiki's theme

A rendered character or item picture SHALL keep its transparent background. The character and item infoboxes SHALL show it on a surface that keeps very dark and very bright subjects readable on the wiki's theme. The surface SHALL show only through transparent pixels, so an opaque screenshot looks unchanged.

#### Scenario: A black subject on the dark theme

- **WHEN** a character infobox shows the transparent render of an almost black subject, such as a constellation
- **THEN** its silhouette stands out from the surface behind it

#### Scenario: A dark item

- **WHEN** an item infobox shows the transparent render of an almost black weapon
- **THEN** its silhouette stands out from the surface behind it

#### Scenario: An editor screenshot in the same infobox

- **WHEN** a character or item infobox shows an opaque screenshot
- **THEN** the screenshot looks as it did before the surface existed

### Requirement: Editors' screenshots have their own title

The bot SHALL NOT upload to a character's or an item's screenshot title, and SHALL NOT move or delete a file there, because the title belongs to the editors. The publication plan SHALL NOT count a screenshot title as a conflict. The Game Data guide SHALL tell editors to upload a character's or an item's screenshot under the screenshot title that its infobox names, and a picture of a game window under `<subject> interface.png` in the article's text, which the infobox does not show.

#### Scenario: A screenshot beside a bot render

- **WHEN** an editor uploaded `Faith screenshot.png` and the bot updates `Faith render.png`
- **THEN** the publication plan lists the render's update and nothing for the screenshot

#### Scenario: A picture of a game window

- **WHEN** an editor uploads a picture of the Shrine of Blessings' window
- **THEN** the guide names its title `Shrine of Blessings interface.png`
- **AND** the article's text shows it, and the infobox does not

#### Scenario: An item screenshot beside a bot render

- **WHEN** an editor uploaded `Mask Fox screenshot.png` and the bot uploads `Mask Fox render.png`
- **THEN** the publication plan lists the render's upload and nothing for the screenshot
