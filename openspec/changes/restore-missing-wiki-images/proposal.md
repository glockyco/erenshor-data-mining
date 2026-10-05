## Why

Generated wiki pages name image files that do not exist on the wiki. Their infoboxes show no image and put the page in no category, so nobody notices the gap. The current image command handles item and ability icons, but these missing images are mostly characters and chests with no portrait sprite.

## What Changes

- Add hidden, kind-specific `Needs Image` categories to character, stance, and item infoboxes when their image files do not exist. The categories make missing images visible to editors.
- Build a repeatable in-game capture mode for character models, summons, chests, and receptacles. A manifest names each file, entity, game build, and camera preset. A temporary camera renders at 1024 × 1024 pixels with fixed lighting, then crops a transparent PNG around the subject.
- Keep icons and portraits separate. Use the existing icon pipeline only when the entity has a matching game icon. Do not use a spell's summon icon as a portrait of its creature.
- Review each captured set before the bot uploads it. Check each file title immediately before upload and never replace a file that a person has uploaded. Editors can replace a bot capture with a better in-game screenshot.
- Keep the editors' zone images separate from game-map sprites. In particular, do not replace `Underspine Hollow.png` with the game's `UnderspineMap.png` without editor approval.

## Capabilities

### New Capabilities

- `wiki-images`: missing-image tracking, repeatable in-game capture, reviewed upload, and verification for images used by generated pages.

### Modified Capabilities

None. Article ownership and field preservation remain as specified by the wiki publishing and article refresh plans.

## Impact

- Code: `wiki/templates/Character.wiki`, `wiki/templates/Item.wiki`, `wiki/templates/Stance.wiki`, their generated infobox inputs, `wiki/content/Category/`, `src/mods/MapTileCapture/` or a dedicated capture mod, the image CLI and service, and focused tests.
- Read-only inputs: `variants/main/erenshor-main.sqlite` and the AssetRipper export under `variants/main/unity/ExportedProject/Assets`.
- Live wiki: the new categories deploy after a dry run and render check. Up to 124 missing character-derived files upload in reviewed batches, among them the images of the six pages with the unused notice. Two zone files remain with editors. No existing file is overwritten by the bot.
- Boundary: this change does not rewrite chest infoboxes on boss pages or replace editor images. It does not take ownership of editor-supplied zone photographs.
