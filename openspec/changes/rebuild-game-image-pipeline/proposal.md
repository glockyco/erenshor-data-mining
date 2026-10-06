# Proposal

## Why

Updating the wiki's game images has always meant re-uploading nearly everything, because the icon pipeline never reads what the wiki already holds. On 2026-10-06 the wiki held 1,874 of the 1,891 icon titles byte for byte, yet the local registry, rebuilt on 2026-09-27, marked all 1,914 icons as new with no upload record. The last full run, on 2026-01-30, uploaded 1,530 files over 88 minutes. The pipeline also picks the wrong picture for 13 entities. It joins the exported sprite name to `Texture2D/<name>.png`, while the export names the sprites of one icon family one number behind their textures. So Thorned Branch shows frosty hands instead of its branch, and the five Willow Seeds show a tassel. The map shows 12 of these wrong pictures, and the wiki has shown the wrong picture for Aura: Ice's Memory since July. A run would replace 12 more correct wiki icons with wrong ones.

## What Changes

- **Icons resolve through the game's references.** The Unity export records the texture asset that each item, spell, and skill icon sprite references, instead of the sprite's name. The image catalog takes each icon from that texture as the game shows it. On 2026-10-06 all 1,299 runtime icon sprites showed their full texture.
- **One catalog of game pictures.** The clean build gains an image catalog. It lists each distinct picture once, with its source asset, pixel hash, and game build, and links every item, spell, skill, stance, and character to its picture and its wiki file title. Rendered portraits enter the same catalog through their reviewed capture.
- **Files are the game's pictures, and the wiki draws the frames.** The bot uploads each icon as the game's texture, unmodified and at native size. The 150 px composites with a painted inventory frame or black border go away. The icon templates and modules draw the frame with TemplateStyles, as the game builds it. An item sits in a slot whose ring copies the vertical gradient of the game's `ITEM ICON` shader, measured in game. A spell or skill lies under the game's own `ma_frame` bezel, as on the hotbar. An icon always fits within the slot's outer square and keeps its proportions.
- **One file per picture.** Every distinct picture has one file. Every other entity that uses it gets a file redirect at its own title, so `File:<Entity>.png` keeps resolving. A changed picture needs one upload.
- **Publishing diffs against the live wiki.** One `list=allimages` listing gives every file's SHA-1, latest uploader, and upload comment. The planner compares the catalog against it and gives each title a verdict: create, update, unchanged, redirect, conflict, retire, or orphan. Only files the bot owns are updated. A file whose latest version an editor uploaded is a conflict to report and is never overwritten. Every upload comment records the game build, the source asset, and the pixel hash. A dry run shows the counts and an old and new contact sheet of every changed picture.
- **The map uses the catalog.** The map build makes its WebP icon sizes from the catalog's pictures and their hashes. Today a separate script joins names the same wrong way and detects changes by file time.
- **BREAKING:** `erenshor images process`, `compare`, `report`, and `upload`, the `--force` overwrite path, `variants/<variant>/images/registry.db`, `images/icon-background.png`, and `src/maps/scripts/generate-item-icons.mjs` are removed. `erenshor images publish` replaces them, and `erenshor images capture` and `approve` remain for portraits. The `upload-captures` step moves into `publish`.

## Capabilities

### New Capabilities
- `game-image-catalog`: how the build identifies, extracts, and catalogues every game picture that the wiki or the map shows. This covers icon resolution through the game's sprite references, deterministic image bytes, pixel hashes, provenance, the entity-to-picture links, and portrait captures that enter the catalog after review.

### Modified Capabilities
- `wiki-images`: publication becomes a plan against the live wiki for every image kind, not only missing portraits. The modified requirements cover one file per picture with entity redirects, updates limited to bot-owned files, conflict reporting, provenance in upload comments, and icon frames drawn by the wiki rather than baked into files.
- `map-site-data`: the map's item icons come from the image catalog and are rebuilt when a picture's hash changes.

## Impact

- **Goals:**
  - Every icon shows the picture the game shows.
  - A game update uploads only the pictures that changed, after one listing of the wiki and a reviewed dry run.
  - Editors' replacements are never overwritten.
  - Every bot file says where it came from.
  - One pipeline serves the wiki and the map.
- **Non-goals:**
  - Zone and editor-owned pictures stay with the editors.
  - Historical images of earlier game builds are not kept or uploaded.
  - Sprite sheets are not used: individual files keep their own history and licensing, and HTTP/2 removed the request cost that once justified sheets.
  - Portrait capture, review, and approval keep their current flow.
- **Migration boundary:** one cutover.
  - The migration uploads about 1,270 native pictures, then moves the old pipeline's 622 other copies aside so their titles can become redirects (first plan, 2026-10-06). WoWBot has the `movefile` and `suppressredirect` rights, so the moves need no administrator.
  - The retired copies and the project's files that nothing produces and no page shows (100 in the first plan, most under older spellings of current titles) go on a deletion list for an administrator.
  - The icon templates and modules switch to the slot markup in the same deploy as the new files.
- **Affected systems:**
  - The Unity export's item, spell, and skill records and listeners, and the clean build's processor and schema
  - `src/erenshor/application/services/image_*`, `model_image_upload.py`, and `cli/commands/images.py`
  - The MediaWiki client
  - Wiki templates `Item/*`, `Gear/Slot`, `SparkleIcon`, and `Item/SpellDetails`, and a new `Template:Icon`
  - Lua modules `Erenshor/Link`, `Erenshor/Format`, and `Erenshor/Spell/Tooltip`, and a new `Erenshor/Icon`
  - The wiki deploy's stages and dependency check, which learn stylesheets that Lua modules load
  - The map's icon build and its consumers
  - The `refreshing-game-data` skill and the Game Data guide
- **Ordering:**
  - This change runs after `restore-missing-wiki-images` is archived, because it modifies that change's `wiki-images` capability.
  - It runs before the Cargo publication of `publish-wiki-cargo-data`, which then stores each entity's picture title from the catalog.
