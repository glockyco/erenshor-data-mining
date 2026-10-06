# Design

## Context

See proposal.md for the motivation. Facts measured on 2026-10-06 that shape the approach:

- **The export records names, not references.**
  - The Unity export writes `ItemIcon.name`, `SpellIcon.name`, and `SkillIcon.name`, the sprite object names of the ripped project. `ImageProcessor` and `generate-item-icons.mjs` open `Texture2D/<name>.png`.
  - AssetRipper names a sprite and its texture independently. In the `4_*` family they are one number apart: the sprite `4_7` references `4_8.png`. 13 entities show the wrong picture, and the clean database holds no other link between an entity and its texture.
  - In game, Thorned Branch's sprite is named `4` and draws the 501 × 486 branch texture.
- **Runtime sprites show their whole texture.** Through HotRepl, all 1,299 icon sprites of items, spells, and skills have a rect equal to their texture. None is packed in an atlas, and 314 are not square. The 1,296 distinct icon textures total 172.7 MB, 133 KB on average, and the largest is 1024 × 1024.
- **How the game builds an item slot:**
  - The slot is an `Image` of `ActionBar_Slot_Border_Big`, a 124 × 124 texture with a 2 px opaque edge, drawn with the material `ITEM ICON`.
  - That shader's exported source is a stub. Rendered in game, it draws a ring 3.5% of the slot's width at 75% opacity, with a linear vertical gradient from `#fdffff` at the top through `#01aaff` at 50% to `#688f9d` at the bottom. It ignores the `Image` tint, so every window shows the same ring.
  - The ring's inside is transparent and shows the semi-transparent `UI_OUTLINE` window panels.
  - The icon is a child `Image` as large as the slot, drawn over the ring, with `preserveAspect` off.
- **How the game builds a hotbar slot:** it draws the sprite `ma_frame` (62 × 63), the spell art at the slot's size, and `ma_frame` again over the art.
- **The live wiki:**
  - The wiki holds 3,127 files and 2,418 distinct SHA-1s.
  - WoWBot has `apihighlimits`, `movefile`, and `suppressredirect`, but not `delete`, `filerevert`, or `purge`.
  - Its rate limits list no `upload` bucket. `move` is limited to 8 per 60 s and `edit` to 90 per 60 s.
  - Past bot sessions uploaded about one file a second.
  - Anonymous `list=allimages` read all 3,127 files in seven requests within four seconds.
- **MediaWiki's upload rules:** uploading identical bytes is refused with `fileexists-no-change` even with `ignorewarnings`. `comment` belongs to the file version and `text` only to the first upload. `ignorewarnings` waives every warning, so a client must judge the warnings itself.

## Goals / Non-Goals

**Goals:**
- One owner for each image artifact, with a write boundary that refuses anything outside its plan.
- A publish run's network cost is about one listing plus the writes it plans.
- Each publish step can run again safely.

**Non-Goals:**
- No parallel uploads. The API etiquette asks for serial writes, and serial writes already take minutes once publishing diffs.
- No re-rendering of portraits when the game changes. Capture stays an explicit step that is reviewed.

## Decisions

### D1. The export records each icon's referenced texture

The item, spell, and skill listeners record `AssetDatabase.GetAssetPath(icon.texture)`, the texture path in the ripped project, next to the sprite name. The clean build resolves pictures only through that path. A missing texture fails the build and names the entity (spec: "Icons resolve through the game's sprite references").

Alternatives considered:
- Parsing `Sprite/<name>.asset` and the `.meta` GUIDs in Python works, but repeats Unity's own reference resolution outside Unity, and breaks when AssetRipper changes its YAML.
- Keeping the name join and adding a correction table repairs a symptom; the next game update can shift other families.

**Owner:** the Unity export listeners and the clean build's icon processor.

### D2. A content-addressed catalog in the clean build

The clean build copies each picture's file to `variants/<variant>/images/catalog/<pixel-hash>.png` and writes three tables to the clean database:

- `images`: each picture's pixel hash, kind (`icon`, `portrait`, or `frame`), width, height, file SHA-1 and size, and for a portrait its capture preset and approval build
- `image_sources`: the source of each picture, a texture path of the export or an approved capture
- `image_titles`: every wiki file title that a page names, with its picture

Items, spells, skills, stances, and characters get an `image_hash` column that references `images`.

- **The pixel hash** is SHA-256 over the width, the height, and the RGBA bytes, so it ignores encoding.
- **The catalog keeps the source bytes.** An icon's file is its texture as the export wrote it, and a portrait's file is its approved copy, so nothing is re-encoded. A rebuild of one export writes byte-identical files and rows (spec: "Picture bytes are deterministic"). When a new export encodes an unchanged texture differently, only the file SHA-1 changes, and publishing compares pixels (D4).
- **Approved portraits enter through `approved.json`.** The build checks each approved copy against the SHA-256 it was approved with and fails on a mismatch, because only a review replaces an approved copy. Each approval records its own game build and preset, so approvals of different builds coexist, and a capture that reproduces approved pixels keeps the same picture. `images approve` keeps writing the record, now a domain value object shared by the build and the uploader.
- **The hotbar frame** (`ma_frame`, design D7) is no entity's icon, so the build names its texture and its title `Hotbar Frame.png`, and fails when a game update removes it.
- **Titles:**
  - An entity's title comes from its image name by the same rule the generators use, `image_file_title`, which both now share. An icon's title counts when its entity has a generated page. A character has a picture only through an approved portrait, approved for a page that names it, so a character's title counts whenever it has a picture. That covers the pages marked unused, which have no generated page.
  - A title with a colon keeps its exact name. Publishing uploads it without the colon and redirects (D5).
  - A title that would name two pictures fails the build and names both entities. The first build found two: the items A Strange Artifact fished in the Planes of Fernalla and Vitheo, and the cast and effect spells of Group Regrowth. Each pair shares a page but draws different icons, so the second item and the effect get their own image names in `mapping.json`.
- **Files go before rows.** The build writes a picture's file only when it is missing or differs, through a temporary file, and only adds files. After a new database is published, the files it no longer references are removed. A failed build therefore leaves every file that the published database references.

Alternatives considered:
- Keeping `registry.db` as a separate store duplicates state that the build can derive. That state is also what went stale.
- Re-encoding every picture with pinned settings would make the bytes independent of the exporter, but would change every file on the first run, when the pixel comparison already ignores encoding.
- Files named by entity in the catalog would need one copy per entity again.

**Owner:** the clean build writes the catalog files and tables. `images approve` owns `approved.json`.

### D3. Ownership and conflicts from the latest version's uploader

A file is the project's when one of its accounts uploaded the latest version: the bot account, or the operator account that runs it. The CLI takes both from the account part of the configured bot and interface usernames, so they need no setting of their own. The listing's `user` field answers this for every file at once.

The operator account is included because of evidence from the first live plan of 2026-10-06. 103 of the files that publishing must replace or retire had WoWMuch as their latest uploader. Every one was byte-identical to an output of the old pipeline: 150 × 150 frame composites uploaded with empty comments in bulk runs in June and September 2025, before WoWBot existed. That includes `Spell Scroll Meditative Trance.png`, which this design first called the one editor conflict. Under a bot-only rule they would all have kept their baked frame and shown a double frame inside the new slot markup. The user chose to treat every upload of the operator's account as the project's.

Any other account's latest version makes the title a conflict:
- The plan names the file and its uploader, and the bot never writes it.
- The editor's picture stays until they or the operator resolve it.

An upload comment is not used as the ownership signal, because editors can copy comments; it serves only as provenance.

Alternative considered: adopting only files whose bytes equal an output of the old pipeline. That rule is exact, but it depends on the old pipeline's outputs, which task 6.1 removes.

### D4. The plan compares pixels with as few downloads as possible

For each title, the planner reads the listing entry at the title, and at the page that its redirect names:

1. **Same bytes.** If the live SHA-1 equals the catalog file's SHA-1, the file holds the picture.
2. **Other size.** If the listing's width and height differ from the picture's, the pixels differ. Every 150 px composite of the old pipeline is settled this way.
3. **Recorded hash.** If the project uploaded the live version and its comment names the picture's hash, the file holds the picture.
4. **Bytes differ, size equal.** Otherwise the planner downloads the live file once and compares pixel hashes. Downloads are cached by SHA-1 under `images/publish/live/`, with an index of their pixel hashes.

The first live plan, on 2026-10-06, needed no download. The contact sheets download the live pictures they show, once each.

Redirects are judged by the page they name, because MediaWiki shows a file through one file redirect only. A title that redirects to another redirect shows nothing on the wiki, and the plan points it at the file.

Verdicts:

| Verdict | When | Action |
|---|---|---|
| create | the picture's file is missing | upload |
| update | the project's file at the picture's file title has other pixels | new version |
| unchanged | the file has the picture, or the redirect names the picture's file | nothing |
| redirect | the title should redirect to the picture's file and does not | create or retarget the redirect |
| retire | the title holds a copy that the project uploaded | move it aside (D6) |
| conflict | someone else's file, or a page without a file, holds the title | report it |

Besides the verdicts, the plan reports orphans: files of the project that no title produces and no page shows (`list=imageusage` with redirects followed). It lists the retired files that await deletion and those whose page lacks the deletion notice. A dry run writes the plan and contact sheets: one row per changing picture, with the new picture beside up to three live pictures that its titles show now.

The first live plan counted 1,269 updates, 622 retirements, 242 redirects, 199 unchanged titles, 2 creates, no conflicts, and 100 orphans.

### D5. One file per picture, named after a stable user

Every picture has one file. Its title, by preference:
1. a file that holds the picture already, at one of its titles or at the page that one of them redirects to, unless that page is another picture's title
2. a title whose file the project may update, which saves a move
3. a missing title

Within each group the order is item, spell, skill, stance, character, then title. A title with a colon cannot hold a file, so it competes through its upload title without the colon. That upload title joins the plan whenever the wiki has a page there, so that its copy becomes the file or retires.

Every other title of the picture is a redirect that names the file directly (spec: "One file holds each picture"). When that entity drops the picture, the bot moves the file to the next title in the same order and leaves no redirect behind. Pages name entity titles, so they keep resolving.

Alternatives considered:
- Game-asset titles like Warcraft Wiki's: the export's sprite names are not stable (`4_7` against the runtime's `4`), and they mean nothing to readers.
- Copies per entity, as today: each copy needs its own upload when a shared picture changes. With frames out of the files, an item and a spell that share a texture would hold two copies of one picture.

### D6. Retiring copies without an administrator

A title that should redirect may hold a copy that the project uploaded. The bot then:

1. moves the copy to `File:Retired <title>` with `suppressredirect`
2. creates the redirect at the freed title at once
3. adds `{{Delete}}` to the retired file's description page; the live `Template:Delete` puts it into `Category:Candidates for deletion`

All writes stay within WoWBot's rights. A copy whose latest version someone else uploaded is a conflict, not a retirement, and so is a copy whose retired title is taken. The run record and the plan list every retired file, so an administrator can delete them in one pass. The first migration moves 622 copies. At 8 moves per minute that takes about 80 minutes once, and later runs retire only what a game update makes redundant.

### D7. The wiki draws the frames

**Stylesheet and module:**
- One TemplateStyles stylesheet, `Template:Icon/styles.css`, defines the item slot and the hotbar frame.
- One Lua module, `Module:Erenshor/Icon`, renders an icon for a kind (`item` or `ability`) and a size, and `Template:Icon` wraps it for wikitext. Every icon goes through it: the `Item/*` headers, `Gear/Slot`, `Item/SpellDetails`, `SparkleIcon`, `Erenshor/Link`, and `Erenshor/Spell/Tooltip`.
- The large pictures of the infoboxes stay bare. In the game a frame surrounds an icon in a slot, and the infobox shows the picture itself, so the frame belongs to the icon sizes. `Format.fileLink` served only icons and goes away.
- The module loads the stylesheet through `frame:extensionTag`. Deploying reads such literal calls in Lua as dependencies and uploads every sanitized-CSS page in a new first stage, `stylesheet`, because modules as well as templates load stylesheets and modules deploy before templates.

**Item slot:**
- The ring is a background gradient with the measured stops at 75% opacity.
- The inner well is a dark gradient: `#282a42`, `#333a41` at 50%, and `#35464b`, sampled from the inventory screenshot that the old frame came from.
- The well is inset by 3.5% of the slot, and by at least 1 px.
- The icon is an absolutely positioned layer as large as the slot, centred, at its own proportions.
- The local mockup of 2026-10-06 matched the game's own renders at 80, 48, 32, and 24 px.

**Hotbar frame:**
- `ma_frame` is published once as a bot file, `File:Hotbar Frame.png`. It is a catalog picture of kind `frame`, taken from the export like an icon.
- The module lays it over the spell art at 100% of the slot.

**Sparkle:** `SparkleIcon` draws its sparkle after the icon, so the sparkle stays above the positioned slot. The sparkle has no link and lets clicks through to the icon, and so does the hotbar frame.

Alternatives considered:
- Baking the frames into the files is how the 150 px composites came to need a full re-upload for any frame change, and why an item and a spell that share a texture cannot share a file.
- An `<img>` overlay for the item ring would need a second request, while a CSS gradient draws it exactly.

### D8. One publish command with a resumable run record

`erenshor images publish` reads the clean database and the catalog files, lists the wiki once, and plans. It writes the plan and the contact sheets to `variants/<variant>/images/publish/<stamp>/`. With the root `--dry-run`, it stops there.

**Write order of a real run:**
1. uploads: creates and updates
2. redirects to the pictures' files, which also take the titles with a colon off the copies that are about to move
3. each retirement, followed at once by the redirect at its freed title, so a title that pages show goes without a picture only for the moment between the two writes
4. `{{Delete}}` notices, also for retired files of earlier runs that lack one

A redirect or retirement whose picture's file could not be uploaded is skipped, so the run never points a title at a missing file.

**Before each write**, the run reads the title again: the file's latest version for an upload or a move, and the page for a redirect, because the file history of a redirect title is its target's. A title that changed since the plan is skipped and reported.

**Uploads:**
- An upload never sets `ignorewarnings` up front. On warnings, the run compares them with those its verdict expects: `exists` and `duplicateversions` for an update, and `duplicate` when another live file has the same bytes. `duplicateversions` arises when an earlier version of the file holds the picture, for example after a revert.
- It confirms through the stashed `filekey` only when every warning is expected. Anything else, such as `duplicate-archive` for bytes that an administrator deleted, is skipped and reported.
- The upload comment carries the picture's hash, kind, source asset, and the game build. A new file's description says how the picture was made, under `== Licensing ==` with `{{License|Game}}`, the wiki's notice for the game's pictures.

**Run record:** every write appends to `run.json` at once, with the old and new SHA-1 of an upload, the retired title of a move, and the old text of a changed redirect. A rerun plans from the live wiki again, so an interruption costs nothing.

**Rollback:**
- The bot lacks `filerevert` and `delete`. Before an update overwrites a file, the run saves the live bytes into its record.
- `images publish --revert <stamp>` uploads the saved bytes again where the run's version is still the latest. It points each retired title back at its retired file and removes the deletion notice. It restores a changed redirect, pointed straight at the retired file when it named a retired title, because MediaWiki does not follow two file redirects.
- A move cannot be undone, because moving the file back would need the redirect at its title deleted. Created files and created redirects stay too, and the revert lists them.

`images capture` and `images approve` stay. `upload-captures` goes away, because publish covers portraits.

**Owner:** `images publish` is the only writer of files and file redirects. It writes only the titles of its plan.

### D9. The map builds icons from the catalog

`erenshor maps build` and `erenshor maps dev` write each map-visible item's icon from its catalog picture with Pillow:
- WebP at 20 and 48 px, fitted within the square at its own proportions and centred
- under `static/items/<pixel-hash>.w20.webp` and `.w48.webp`

The items' `image_hash` column gives the map each item's picture, so the consumers address icons by hash. A changed picture gets a new URL, an unchanged one keeps its files, and the files of pictures that no map-visible item shows any more are removed. `maps dev` builds them too, because the development server reads a rebuilt database at once and would otherwise ask for icons that do not exist yet. The build's data hash covers the icons, because their names come from the database. `generate-item-icons.mjs` goes away. `sharp` stays, because the favicon, social image, thumbnail, and transparent icon scripts use it. Following the decision memory, the map change is checked in a browser.

**Owner:** the map build.

## Risks / Trade-offs

- [Native textures are larger than the 150 px composites: 172.7 MB against about 66 MB today] → Pages show thumbnails that MediaWiki renders once and caches. File pages show the full picture, which the 1024 × 1024 textures make sharper.
- [A page that embeds an icon file directly, outside the templates, shows the bare picture without a frame] → The Game Data guide documents the icon module as the way to show a game icon. A scan lists main-namespace pages that embed icon files directly, so editors can see them.
- [The first migration takes long: about 1,270 uploads and 622 moves at 8 per minute] → The run record makes it resumable, and it runs once. Later runs touch only what changed.
- [`css-sanitizer` may reject a property on the live wiki that the local stack accepted] → The local stack runs the same TemplateStyles and TemplateStylesExtender. The repository deploy's render check parses the stylesheet against the live wiki before any write.
- [An editor may edit a redirect page into a file description] → The planner treats any non-redirect page without a file at a redirect title as a conflict and reports it.
- [A retirement moves a file that a page embeds by its old title] → The redirect at the old title is created in the same run, and a failed redirect is retried before the run ends. The run record names every unfinished pair.

## Migration Plan

1. Export and build: the listeners record icon texture paths, and the clean build writes the catalog. Check that the 13 entities resolve to the right textures and that a rebuild is byte-identical.
2. Deploy the icon stylesheet, module, and template changes to the local stack. Verify every icon site against the mockup measurements in a browser.
3. Publish once with `--dry-run`. Review the verdict counts, the conflicts, and the contact sheet of updates with WoWMuch.
4. Run publish, then deploy the templates and modules, and `Module:Erenshor/Format` in a second deploy after the new `Erenshor/Link`. Templates and files change in one session. Publishing comes first: it takes over two hours, and for that time the native icons show bare under the old templates, which reads better than old 150 px files with a second frame inside the new slot markup, and `File:Hotbar Frame.png` exists before the templates draw it. The render check sandboxes one page at a time, so the removal of `Format.fileLink` cannot be checked in the same deploy as the `Link` that stops calling it.
5. Verify live:
   - a fresh parse of an item, a spell, and a skill page
   - the 13 corrected icons
   - zero remaining create or update verdicts in a second dry run
6. Rebuild and deploy the map. Check its item icons in the browser.
7. Remove the old commands, `registry.db`, and `icon-background.png`. Update the `refreshing-game-data` skill, the Game Data guide, and the README.
8. Hand the deletion list to an administrator: the retired copies and the 86 orphans.

**Rollback:** `images publish --revert <stamp>` restores every file version and moves retired files back. The repository deploy's rollback restores the templates and modules.
