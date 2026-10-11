# Design

## Context

See proposal.md for the motivation. The facts below were checked on 2026-10-11 against build 24405256, the clean database, and the live wiki.

- Character renders come from the running game. `uv run erenshor images manifest` lists every character model under its subject, `images capture` sends one request for each subject to the MapTileCapture mod over its WebSocket, and the mod's `PortraitStudio` clones the model under a hidden studio, keeps the renderers that a player sees, and renders a transparent 1024 × 1024 PNG with the preset `portrait-4`. `images review` checks each output and draws contact sheets, `images approve` binds the approved PNG to its SHA-256 in `approved.json`, and `extract build` adds it to the catalog as kind `portrait`. The publication planner works on any catalog title, but the file description it writes for a `portrait` describes a character.
- The game has no model of its own for most items. `ModularParts.UpdateSlot` switches on the child of the body's slot transform whose name is the item's `EquipmentToActivate`, and colours it through seven shader properties from the item's colour fields (`ModularParts.cs:535-559`). Arms, bracers, hands, and feet switch on a left and a right part. Weapons and shields are children of the male body's hand anchors, which `ModularParts.SpawnWeapons` clones for simulated players. Masks are the objects of `Inventory.Modulars.HalloweenMasks`. A Reliquary furniture set turns on the furnishing child of a room whose name is the set's `EquipmentToActivate` (`PlanningTable.cs:223-240`). The body exists as a male and a female rig with parts of the same names.
- `GameData.ItemDB.GetItemByID` returns the game's item record for the item ID that the clean database holds, with its slot, part name, and colours.
- 684 wiki items name a part: 216 weapons and shields with 192 distinct parts, 408 worn items with 129 distinct parts, 16 masks, 37 furniture sets, and 7 blueprints that name their set's furnishing. Rings, necks, waists, charms, auras, and the other general items name none. The common and the rare Letters and Words share a page, an image name, and a part.
- Template:Item shows `icon` in the infobox. Template:Character shows a `<gallery>` of `render` and `screenshot`, which Portable Infobox shows as tabs, as one picture, or not at all, depending on which files exist.
- The 1,523 item pages show 233 files besides their own icons. 205 are the bot's spell icons in tooltip parameters, 2 are sparkle animations on 13 pages, 5 are Jerigord's maps of where a willow seed lies, 3 are commented-out links to files that do not exist, and 18 show an item: WoWMuch's 16 pictures of the masks when worn (`Mask Fox.png`), Kris9727's picture of the Shrine of Blessings, and DeathEmber's of the Stone Statue: Soluna. The 16 mask pages are hand-written, and the bot does not generate them.

## Goals / Non-Goals

**Goals:**

- One capture workflow and one catalog for character and item renders, with the same review and approval.
- The item infobox decides from the files that exist which picture to show, so no deploy step depends on another to keep a picture on the page.

**Non-Goals:**

- Item renders in the Lua data modules. The data-backed item template of `adopt-data-backed-wiki` task 8.6 adds the render and screenshot titles to `Data/Items` when it reads them.
- Renders of blueprints. A blueprint names the furnishing of its set, but it is a paper item, and the set's page shows the furnishing.

## Decisions

### D1. The icon stays in tooltips, and the infobox prefers the render and the screenshot

Template:Item takes `render`, `render_male`, `render_female`, and `screenshot` beside `icon`. Its image shows a gallery when one of those files exists, checked with `{{#ifexist:Media:…}}`, and shows `icon` otherwise. The gallery holds the render, or the male and the female render, then the screenshot, labelled Render, Male, Female, and Screenshot, so Portable Infobox shows the existing files as tabs or one alone. Every item page keeps a picture, and the search thumbnail, which the wiki takes from the infobox picture, becomes the first render where there is one. An infobox spends at most three expensive parser functions, well within the limit of 500. `imagecaption` stays below the image. The infobox shows the icon at most 160 pixels on its longer side, through `Template:Item/styles.css`, because an icon filling the infobox width looks blown up (decided with the user on 2026-10-11); renders and screenshots keep the full width.

Generation owns these parameters on generated pages. It fills the render parameters with the catalog's titles of the item's approved renders and `screenshot` with `<subject> screenshot.png` on every item page. Field preservation treats them like the character parameters. The tooltip templates, `ItemLink`, `Gear/Slot`, and the hover cards keep reading the icon.

Alternatives:

- **The icon as a third tab.** It would repeat the tooltip's icon on every page with a render.
- **No picture without a render or a screenshot.** The user chose on 2026-10-11 to keep the icon, as WoWMuch decided for the infobox on 2026-10-07.

### D2. A render shows the piece by itself

The user chose on 2026-10-11 to show the piece by itself, not worn on a body. Each kind's capture source:

| Kind | Slots | What the studio renders |
|---|---|---|
| `weapon` | Primary, Secondary, PrimaryOrSecondary | The child of the male body's hand anchors with the item's part name, by itself, seen straight at its broad face, turned 15° so its thickness shows, without pitch, and standing along its longest side; a long weapon has its grip down, and a bow its grip on the left |
| `worn` | Head, Chest, Arm, Bracer, Hand, Foot, Leg, Back | The parts that `UpdateSlot` switches on for the item, both sides where the slot has two, in the item's colours, on a hidden body in its rest pose: once on each body whose parts differ. A cape is seen from behind, as the player sees it |
| `mask` | General, cosmetic | The `HalloweenMasks` object with the item's part name |
| `furnishing` | General, furniture set | The furnishing that the set turns on in a Reliquary room, without the room |

The male and female bodies hold separate meshes for most armour parts of the same name. The export of 2026-10-11 records every part under the player's slot transforms in `LoadScene`, as `UpdateSlot` finds them among all descendants: 315 of the 408 worn items switch on parts whose male and female meshes differ, such as the `HeavyPlate` chest with 1,572 and 1,692 vertices, 92 switch on parts that both bodies draw alike or that only one body holds, and the part of one, the Igniting Brace's `Plate Bracer`, is on neither body. The user decided on 2026-10-11 to show both versions where they differ:

- An item whose parts differ between the bodies gets `<subject> render (male).png` and `<subject> render (female).png`.
- Every other item gets one `<subject> render.png`: shared parts, male-only parts, weapons and shields from the male body's hand anchors, masks, and furnishings.
- The qualifier follows the role, so the subject stays whole before ` render`, and all renders of an item sort and search together. No worn item's picture name on build 24405256 holds parentheses, `male`, or ` render`.
- An item whose part neither body holds is listed apart, with the missing name, until the source that holds it is found.

The colours come from the game's item record at capture time, through the same shader properties as `UpdateSlot`, so the export needs no colour fields and a render cannot drift from the game's colours. The studio copies the logged-in player, so the player's own equipment and colours stay as they are, shows the requested body's parts, and hides every other renderer. Skin that an armour part draws, such as a shirt's neckline, takes the first colour of the game's skin palette, `SimPlayerMngr.SkinColors[0]` (0.83, 0.79, 0.76), so a render does not depend on the character that captures it (decided with the user on 2026-10-11). Paired parts stay where the rest pose holds them (decided with the user on 2026-10-11). A furnishing's characters, such as a training dummy, lose their target ring, as `Character.Start` removes it in the game. The user approved this look on 2026-10-11 from captures of each kind but the mask. After the first full batch the user chose on 2026-10-11 the face-on view of weapons and shields, capes from behind, and to keep only the particle effects that stay close to the meshes, such as a sword's flame, and not ones that spread, such as the Molten Axe's smoke. An item whose part shows only particles, such as Lamplighter's Spark, fails its capture and keeps its icon in the infobox. Items that share a subject share their renders, as characters do. Two renders with equal pixels become one picture with redirects, as icons do.

Alternatives:

- **Worn on a body**, the paper doll. The user chose the piece by itself.
- **One render from the male body for every item.** It would show the wrong shape on 315 pages for players of the other body.
- **`<subject> male render.png`.** A reader could not tell whether `male` belongs to the item's name.
- **The piece in its bind pose without a rig.** Skinned parts need the body's bones to deform, so the studio keeps a hidden body and shows only the item's renderers.

### D3. The capture workflow learns item subjects

`images manifest` adds item entries beside the character entries: subject, render title, kind, body (`male`, `female`, or none), the item's ID, slot, part name, and pages. A worn item whose parts differ between the bodies has one entry for each body. The manifest learns the parts from the export: the export records each child of the slot transforms of the player's male and female `ModularParts` in `LoadScene`, with the meshes it draws, the mask objects, and the furnishings of the Reliquary's planning table. Two bodies differ for an item when their parts of its name draw different meshes. An item whose part no body holds is listed apart with the missing name. The capture request carries the kind, the body, and the item ID. The studio looks up the item with `GetItemByID`, builds the source of D2 from clones, and never touches the player's own body or equipment. A source that has no object of the item's part name fails the capture with the subject and the name.

A new preset `item-1` keeps the light and camera effects of `portrait-4` and frames the item's bounds, so a long spear and a ring of gloves both fill the square with the usual margin. `images review` applies the character checks: the expected object, renderer count, clipping, and alpha. `images approve` records the entity kind `item`.

### D4. The catalog names renders by role, not by subject

The image kind `portrait` becomes `render`. Each approval records its entity's stable key and the wiki title that the review compared it with, and the file description reads both, so it says what the picture is: a character, or an item by itself, on the male or female body where the title names one. The catalog adds each approved item render under its approval's title, `<subject> render.png`, or `<subject> render (male).png` and `<subject> render (female).png`, when its item has a page. Items that share a subject share the render; the item rows keep their icon, and `item_renders` links each item to its renders. Meshes that differ between the bodies can still draw the same picture, as for 33 of 315 items on build 24405256, so an item whose male and female renders have equal pixels gets that picture once under its plain render title, and the infobox shows no Male and Female tabs of one picture. The build fails when an item has both the plain title and a body's title, and when an item's and a character's render share a title and differ, as it already fails for any title that names two pictures. On build 24405256 no item subject equals a character subject.

### D5. Owners and write boundaries

| Artifact | Owner | Guard |
|---|---|---|
| Captures, `approved.json` | Operator, local | SHA-256 binding, checked at every build |
| `<subject> render.png` of an item | The bot | Approved set only, the publication's owned-file and re-check rules, dry-run contact sheets |
| `<subject> screenshot.png` of an item | Editors | The bot never writes there, except the one-time move of D6 |
| `Template:Item` | Repository | `wiki deploy-repo-pages` with its render check |
| Generated item pages | The bot | Article deploy, with `icon`, `render`, `screenshot` generation-owned |
| The 16 mask pages | Editors | One reviewed, guarded page edit (D6) |
| MapTileCapture mod | Repository | Local build, runs only on the operator's machine |

### D6. Editors' item pictures move once

The 18 files that show an item move to `<subject> screenshot.png`, so that the infobox shows them: the 16 mask pictures, `Screenshot 2026-08-25 142237.png` to `Shrine of Blessings screenshot.png`, and `Stone statue of soluna.png` to `Stone Statue Soluna screenshot.png`. The list is fixed and reviewed, because two of the titles are not the plain titles that the character cutover matched. The move restores `images move-screenshots` of `name-pictures-by-role` from the history, takes the reviewed list instead of plain titles, runs once through the publication run's move and run record, so `images publish --revert` undoes it, and is removed again. The willow seed maps and the sparkles stay where they are.

A guarded page edit through `wiki apply-page-edits` adds `render` and `screenshot` to the 16 hand-written mask infoboxes and removes the in-text copies of the moved pictures there and on the Shrine of Blessings and Stone Statue: Soluna pages, after WoWMuch reviews each diff.

### D7. Order of the cutover

Each step keeps every page's picture, because the infobox falls back to the icon:

1. Land the catalog kind, the manifest, the studio, and the preset. Nothing goes live.
2. Capture one weapon, one pair of boots on both bodies, one cape, one helmet, one mask, and one furnishing, and show them to the user before the batch.
3. Capture, review, and approve every item subject.
4. Deploy Template:Item. Pages without `render` and `screenshot` show their icon as before, so the render check must show no change.
5. Publish the renders, after a dry run and approval.
6. Deploy the generated item pages with `render` and `screenshot`, after a dry run and approval.
7. Move the 18 editors' files and apply the page edits, after approval.

Rollback runs in reverse: the page edits' guarded reverts, `images publish --revert` for the move and the render runs, and the article and repository-page rollbacks.

## Risks / Trade-offs

- [Paired parts in the rest pose spread wide or look odd] → Step 2 shows each kind to the user before the batch, and the preset or the source changes before about 1,000 captures.
- [A body's version differs from what a player expects] → Each body's parts render on their own hidden body, and step 2 shows one item in both versions.
- [About 1,000 uploads and 1,500 page edits meet the wiki's rate limits] → Both runs resume from their records, and the article deploy takes about 20 minutes at 90 edits a minute.
- [A game update changes a part or an item's colours] → The game-data refresh recaptures the item subjects with the characters, and a capture with new pixels needs a new review.
- [A furnishing spreads over a room with characters and props] → It is framed as one subject, and its review can reject it. The Shrine of Blessings and the Stone Statue: Soluna keep their editors' screenshots in any case.
- [A page edit replaces text that equals a picture title but is not a picture] → On 2026-10-08 the character cutover's page edits replaced the `title` and `name` of three Eldoth Writings pages whose old picture title was the item's name, and the article deploy of 2026-10-11 restored them. These edits replace only whole picture lines, and WoWMuch reviews each diff.
