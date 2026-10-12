# Proposal

## Why

An item page shows one picture, the game's inventory icon, and since 2026-10-07 the infobox shows it too. A character page shows a render that the project captures from the game's 3D model and a screenshot that editors upload, as two tabs (`name-pictures-by-role`). That change reserved the `render` title for items but captured none, and WoWMuch wants item renders next. Editors already show what some items look like: WoWMuch's 16 pictures of the masks when worn and two pictures of Reliquary furniture sit in the page text, outside the infobox.

## What Changes

- **Items get three pictures, each with one role.** `<subject> icon.png` is the game's icon, `<subject> render.png` is the project's capture of the item's 3D model, or `<subject> render (male).png` and `<subject> render (female).png` where the two bodies have different models, and `<subject> screenshot.png` is an editor's picture from the game, the titles that `name-pictures-by-role` defined.
- **The infobox shows the render and the screenshot, and tooltips keep the icon.** The item infobox shows the render, or the male and the female render, first and the screenshot as a further tab, like the character infobox, and shows one of them alone when the other does not exist. An item with neither shows its icon, so every item page keeps a picture and its search thumbnail. Tooltips, item links, gear slots, and hover cards keep showing the icon.
- **A render shows the piece by itself** (decided on 2026-10-11). Weapons and shields show their model, worn items show the parts that the game switches on for them without the body, in the item's own colours, masks show the mask, and a Reliquary furniture set shows the furnishing that it builds. The male and female bodies have separate models for 315 worn items, which get one render for each body (decided on 2026-10-11). Every other item gets one render: 974 renders for the items with a model, besides the masks. Consumables, scrolls, books, rings, necks, waists, charms, and auras have none and keep their icon.
- **The capture workflow covers item models.** The capture manifest, the in-game capture studio of the MapTileCapture mod, the review, and the approval learn item subjects. Item renders enter the catalog only after review, as character renders do.
- **Editors' item pictures move to their screenshot titles once.** The 18 files that show an item move to the screenshot titles, and the infobox shows them. A reviewed page edit adds the render and screenshot titles to the 16 hand-written mask infoboxes and removes the in-text copies that the infobox then shows.
- **BREAKING:** the image kind `portrait` of the clean database becomes `render`, because it no longer holds only character portraits.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `wiki-images`: item infoboxes show the render and the screenshot and fall back to the icon, editors' item screenshots have their own title, and the capture manifest and studio cover item models.
- `game-image-catalog`: item renders enter the catalog after review under `<subject> render.png`, and an entity links to each of its pictures.

## Impact

- **Goals:**
  - An item page shows what the item looks like in the game, and the tooltip still shows the icon that the game's inventory shows.
  - Editors and the bot never compete for an item's title.
  - A game update that changes an item's model or colours reaches its render through the same review as a character's.
- **Non-goals:**
  - Items worn on a body. The piece by itself was chosen instead.
  - Renders of the belt lamps and the Watcher's Lens before task 5.45 of `adopt-data-backed-wiki` exports the `Inventory` references that name them.
  - Item pictures on the interactive map, which keeps its icons.
  - A `Needs Image` category for items: every item has its icon.
- **Migration boundary:** the item infobox shows the icon whenever an item has neither picture, so the template, the renders, the generated pages, and the screenshot moves can each go live after their own dry run and approval, in any order that the design names, without a page that loses its picture.
- **Affected systems:**
  - Capture: `src/erenshor/application/services/model_image_manifest.py`, `application/capture/portraits.py`, `application/services/model_image_approval.py`, `domain/value_objects/capture_approval.py`, `cli/commands/images.py`, and the MapTileCapture mod's `Capture/PortraitController.cs`, `Capture/PortraitStudio.cs`, `Protocol/Messages.cs`, and `Protocol/PortraitPreset.cs`
  - Catalog and publication: `application/processor/pictures.py`, the `images` table in `application/processor/writer.py`, `application/services/image_publication.py`, and `image_publication_run.py`
  - Wiki: `wiki/templates/Item.wiki`, the item generator (`application/wiki/generators/sections/item.py`, `templates/item.jinja2`) and `field_preservation.py`, the local wiki's fixtures and smoke checks, the Game Data guide, and the `wiki-templates` and `refreshing-game-data` skills
  - Live wiki: about 1,000 render uploads, a `Template:Item` deploy, an article deploy of the item pages, 18 file moves, and page edits of the 16 mask pages and the pages that show a moved picture in their text
- **Ordering:** independent of `publish-wiki-data-views`. The data-backed item template of `adopt-data-backed-wiki` task 8.6 takes over the same pictures and rules.
