# Proposal

## Why

A wiki file title names only its subject, so `File:Faith.png` is a render on one character page and an editor's screenshot on the next, and the item renders that WoWMuch wants next have no title left to take. Character pages cannot show both pictures yet: the bot's 886 approved renders and editors' 758 screenshots compete for the same 878 titles, and the bot never overwrites an editor's file.

## What Changes

- **Titles name subject and role.** Every picture title is `<subject> <role>.png`: `Thorned Branch icon.png`, `Faith render.png`, `Faith screenshot.png`. The subject is the entity's image name without the characters that MediaWiki forbids, so no title needs a redirect from a spelling with a colon. Item renders take `render` and armour worn on a body takes `equipped`, when a later change captures them.
- **Character infoboxes show the render first and the screenshot second.** Portable Infobox shows the two as tabs, labelled Render and Screenshot. A character with only one of the two shows it alone. The `Needs Image` categories track characters with neither.
- **Editors' screenshots get their own title.** Editors upload a character's screenshot to `<subject> screenshot.png`, a title that the bot never uploads to, and the infobox shows it beside the render without any page edit.
- **Infobox parameters name the role.** Item, Ability, and Stance infoboxes take the game picture in `icon`, and Character infoboxes take `render` and `screenshot`. Generation owns all four.
- **Modules and templates use the catalog's titles.** The Lua data modules carry each entity's full file title, and no module or template appends `.png` to a name.
- **Publishing moves files instead of uploading copies.** When a picture's file title changes, the bot moves the project's file to the new title, which keeps its history and leaves a redirect at the old title, and points every other redirect that named the old title at the file.
- **One cutover renames the live files.** The bot moves the project's 1,385 files to their role titles and retargets their 954 redirects. It moves the 758 editors' character files to their screenshot titles. It rewrites the 1,118 file names written out in 133 hand-written pages and the parameters of hand-written infoboxes, and it makes the editors' `Gear/MiniSlot` look up an item's icon the way `Gear/Slot` does, which WoWMuch approved on 2026-10-07. Every old title stays a redirect, so old revisions and outside links keep working.
- **BREAKING:** the infobox parameters `image` and `imagefile` of Item, Ability, Stance, and Character are removed. The title builder that derived `<name>.png`, the upload titles for names with colons, and the planner's handling of them are removed. Model captures and approvals name a model by its subject instead of by a file title.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `game-image-catalog`: entity file titles name the subject and the role, without forbidden characters.
- `wiki-images`: character infoboxes show the render and the editors' screenshot, editors' screenshots have their own title, publication moves files when their titles change, and capture manifests name models by subject.

## Impact

- **Goals:**
  - A file title alone says what the picture shows.
  - Every character page shows the same kind of render first and keeps the editors' screenshot one click away.
  - Editors and the bot never compete for a title.
  - No page that the project generates or edits names an old title after the cutover.
- **Non-goals:**
  - Capturing item renders or equipped armour. This change fixes their titles only.
  - Zone pictures, which stay with the editors under their current titles.
- **Migration boundary:** one cutover, announced in `#wiki-chat` before it starts.
  - The publication run moves the project's files and retargets redirects, the screenshot move renames the editors' character files, and a repository-page deploy switches the templates, modules, and generated pages to role titles. One-time page edits rewrite the hand-written pages.
  - The old titles remain file redirects. MediaWiki leaves them on each move, and Wikimedia Commons' file renaming guideline keeps them by default.
- **Affected systems:**
  - `src/erenshor/domain/value_objects/wiki_filename.py`, the picture catalog in `application/processor/pictures.py`, and its `image_titles` table
  - `application/services/image_publication.py` and `image_publication_run.py`, the model image manifest and approval, and `cli/commands/images.py`
  - The page generators and field preservation rules of Item, Ability, Stance, and Character, and the Lua data builders in `application/wiki_lua`
  - Templates `Character`, `Ability`, `Stance`, `Item` with its parts, `Gear/Slot`, and `SparkleIcon`, and modules `Erenshor/Link` and `Erenshor/Spell/Tooltip`
  - The local wiki's fixtures and smoke checks, the Game Data guide, the template documentation, and the `wiki-templates` and `refreshing-game-data` skills
  - The `Image` column that `publish-wiki-cargo-data` plans stores the role title.
- **Ordering:** this change completes task 5.38 of `adopt-data-backed-wiki`, before task 5.39 puts the portraits on the map.
