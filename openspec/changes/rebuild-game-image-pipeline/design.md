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

A file is the project's when one of its accounts uploaded the latest version: the bot account, or the operator account that runs it. The CLI takes both from the account part of the configured bot, interface, and deletion usernames, so they need no setting of their own. The listing's `user` field answers this for every file at once.

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

Redirects are judged by the page they name, because MediaWiki shows a file through one file redirect only. A title can hold both a file and a redirect page, a leftover of the old pipeline, and then the file wins: a project copy whose page redirects to a planned title is retired, and the picture's own file gets its description instead of the redirect. A title that redirects to another redirect shows nothing on the wiki, and the plan points it at the file.

Verdicts:

| Verdict | When | Action |
|---|---|---|
| create | the picture's file is missing | upload |
| update | the project's file at the picture's file title has other pixels | new version |
| unchanged | the file has the picture, or the redirect names the picture's file | nothing |
| redirect | the title should redirect to the picture's file and does not | create or retarget the redirect |
| retire | the title holds a copy that the project uploaded | delete it and redirect the title (D6) |
| describe | the picture's file holds the picture, but its description page is a redirect | write the picture's description |
| conflict | someone else's file, or a page without a file, holds the title | report it |

Besides the verdicts, the plan lists the orphans: the bot account's files that no title produces and no page shows (`list=imageusage` with redirects followed), with the redirects that name them. The operator's files that nothing shows are listed apart, as unused, and stay (D6). A dry run writes the plan and contact sheets: one row per changing picture, with the new picture beside up to three live pictures that its titles show now.

The first live plan counted 1,269 updates, 622 retirements, 242 redirects, 199 unchanged titles, 2 creates, and 4 conflicts. Of 100 unused files of the project, 79 were the bot's orphans and 21 the operator's.

### D5. One file per picture, named after a stable user

Every picture has one file. Its title, by preference:
1. a file that holds the picture already, at one of its titles or at the page that one of them redirects to, unless that page is another picture's title
2. a title whose file the project may update, which saves a move
3. a missing title

Within each group the order is item, spell, skill, stance, character, then title. A title with a colon cannot hold a file, so it competes through its upload title without the colon. That upload title joins the plan whenever the wiki has a page there, so that its copy becomes the file or retires.

Every other title of the picture is a redirect that names the file directly (spec: "One file holds each picture"). When the entity that names the file drops the picture, the next plan gives the picture a file at the next title and points the other titles there; the old file then shows on no page, and the run after deletes it as an orphan. Pages name entity titles, so they keep resolving.

Alternatives considered:
- Game-asset titles like Warcraft Wiki's: the export's sprite names are not stable (`4_7` against the runtime's `4`), and they mean nothing to readers.
- Copies per entity, as today: each copy needs its own upload when a shared picture changes. With frames out of the files, an item and a spell that share a texture would hold two copies of one picture.

### D6. Copies and orphans are deleted with the operator's administrator account

The bot account cannot delete. The operator is an administrator of the wiki, so a bot password of the operator's account with only the delete grant deletes for publishing (`deletion_username` and `deletion_password`, set only in `.erenshor/config.local.toml`). Before a run that deletes, the CLI logs it in and checks that it has the `delete` and `undelete` rights.

A title that should redirect may hold a copy that the project uploaded. The run then:

1. points every other redirect that names the copy at the picture's file, which the redirect step does for catalog titles and the plan adds for any other redirect, because MediaWiki follows one file redirect
2. deletes the copy
3. creates the redirect at the freed title at once

The bot's orphans go last, each with the redirects that name it. Before each deletion the run reads the file again, and it keeps an orphan that a page has started to show. Files of the operator that nothing shows are listed as unused and stay, because the operator also uploads by hand: on 2026-10-06 they were 20 composites of the old pipeline and `Raids.png`, a picture that the operator composed of the four rune icons.

A copy whose latest version someone else uploaded is a conflict, not a deletion.

Alternatives considered:
- Moving each copy to `File:Retired <title>` with `{{Delete}}` for an administrator, the first design, which stayed within the bot's rights. It needed 622 moves at 8 per minute, 622 notice edits, and a later deletion pass, three log entries per file instead of one.
- Deleting through the operator's browser session. A bot password keeps the run record and the checks of every other write.

### D7. The wiki draws the frames

**Stylesheet and module:**
- One TemplateStyles stylesheet, `Template:Icon/styles.css`, defines the item slot and the layers of the hotbar frame.
- One Lua module, `Module:Erenshor/Icon`, renders an icon for a kind and a size, and `Template:Icon` wraps it for wikitext. Every icon goes through it: the `Item/*` headers, `Gear/Slot`, `Item/SpellDetails`, `SparkleIcon`, `Erenshor/Link`, and `Erenshor/Spell/Tooltip`.
- The large pictures of the infoboxes stay bare. In the game a frame surrounds an icon in a slot, and the infobox shows the picture itself, so the frame belongs to the icon sizes. `Format.fileLink` served only icons and goes away.
- The module loads the stylesheet through `frame:extensionTag`. Deploying reads such literal calls in Lua as dependencies and uploads every sanitized-CSS page in a new first stage, `stylesheet`, because modules as well as templates load stylesheets and modules deploy before templates.

**Kinds, as the game draws each place:** the scene of the game's UI decides, read from the exported `LoadScene`.
- `item`, the inventory slot: gear slots and item links.
- `ability`, the hotbar slots, where `ma_frame` lies over the icon: spell, skill, and stance links.
- `window`, the item window's header, where `ma_frame` (`ItemInfo/BG (1)`) lies behind the 64 px `ItemIcon`, which the code fills at full size: the item tooltip headers.
- `bare`, the item window's spell details, whose 48 px `SpellDetailsImage` has no frame: the spell details and the standalone spell tooltips.

The first deploy gave the tooltip headers the inventory slot and the spell details the hotbar frame, the frames measured on the inventory and the hotbar. A review asked whether the spell details really carry a frame in the game, and the scene showed that the item window draws neither.

**Item slot:**
- The ring is a background gradient with the measured stops at 75% opacity.
- The inner well is a dark gradient: `#282a42`, `#333a41` at 50%, and `#35464b`, sampled from the inventory screenshot that the old frame came from.
- The well is inset by 3.5% of the slot, and by at least 1 px.
- The icon is an absolutely positioned layer as large as the slot, centred, at its own proportions.
- The local mockup of 2026-10-06 matched the game's own renders at 80, 48, 32, and 24 px.

**Hotbar frame:**
- `ma_frame` is published once as a bot file, `File:Hotbar Frame.png`. It is a catalog picture of kind `frame`, taken from the export like an icon.
- The module lays it over the art for `ability`, and under the art for `window`, at 100% of the square.

**Sparkle:** `SparkleIcon` draws its sparkle after the icon, so the sparkle stays above the positioned slot. The sparkle has no link and lets clicks through to the icon, and so does the hotbar frame.

**Hover cards:** TemplateStyles scopes its rules to `.mw-parser-output` and emits a stylesheet once beside the content. The hover gadget lifts a card out of a parsed page, so it mounts the card in a `.mw-parser-output` wrapper with the parsed page's stylesheets.

Alternatives considered:
- Baking the frames into the files is how the 150 px composites came to need a full re-upload for any frame change, and why an item and a spell that share a texture cannot share a file.
- An `<img>` overlay for the item ring would need a second request, while a CSS gradient draws it exactly.

### D8. One publish command with a resumable run record

`erenshor images publish` reads the clean database and the catalog files, lists the wiki once, and plans. It writes the plan and the contact sheets to `variants/<variant>/images/publish/<stamp>/`. With the root `--dry-run`, it stops there.

**Write order of a real run:**
1. uploads: creates and updates
2. redirects to the pictures' files, which also take the titles with a colon off the copies that are about to go
3. each copy's deletion, followed at once by the redirect at its freed title, so a title that pages show goes without a picture only for the moment between the two writes
4. the orphans' deletions with their redirects

A redirect or deletion whose picture's file could not be uploaded is skipped, so the run never points a title at a missing file.

**Before each write**, the run reads the title again: the file's latest version for an upload or a move, and the page for a redirect, because the file history of a redirect title is its target's. A title that changed since the plan is skipped and reported.

**Uploads:**
- An upload never sets `ignorewarnings` up front. On warnings, the run compares them with those its verdict expects: `exists` and `duplicateversions` for an update, and `duplicate` when another live file has the same bytes. `duplicateversions` arises when an earlier version of the file holds the picture, for example after a revert.
- It confirms through the stashed `filekey` only when every warning is expected. Anything else, such as `duplicate-archive` for bytes that an administrator deleted, is skipped and reported.
- The upload comment carries the picture's hash, kind, source asset, and the game build. A new file's description says how the picture was made, under `== Licensing ==` with `{{License|Game}}`, the wiki's notice for the game's pictures.

**Run record:** every write appends to `run.json` at once, with the old and new SHA-1 of an upload, the SHA-1 and description of a deleted copy, the redirects deleted with an orphan, and the old text of a changed redirect. A rerun plans from the live wiki again, so an interruption costs nothing.

**Rollback:**
- The bot lacks `filerevert`. Before an update overwrites a file, the run saves the live bytes into its record, and before it deletes a copy, the copy's description.
- `images publish --revert <stamp>` uploads the saved bytes again where the run's version is still the latest. It undeletes each deleted copy, whose file then shows again, and puts its description back in place of the redirect, which stays the newest revision after the undeletion. It undeletes the orphans with their redirects, and restores each changed redirect.
- Created files and created redirects stay, and the revert lists them.

`images capture` and `images approve` stay. `upload-captures` goes away, because publish covers portraits.

**Owner:** `images publish` is the only writer of files and file redirects, and the only deleter of files. It writes and deletes only the titles of its plan.

### D9. The map builds icons from the catalog

`erenshor maps build` and `erenshor maps dev` write each map-visible item's icon from its catalog picture with Pillow:
- WebP at 20 and 48 px, fitted within the square at its own proportions and centred
- under `static/items/<pixel-hash>.w20.webp` and `.w48.webp`

The items' `image_hash` column gives the map each item's picture, so the consumers address icons by hash. A changed picture gets a new URL, an unchanged one keeps its files, and the files of pictures that no map-visible item shows any more are removed. `maps dev` builds them too, because the development server reads a rebuilt database at once and would otherwise ask for icons that do not exist yet. The build's data hash covers the icons, because their names come from the database. `generate-item-icons.mjs` goes away. `sharp` stays, because the favicon, social image, thumbnail, and transparent icon scripts use it. Following the decision memory, the map change is checked in a browser.

**Owner:** the map build.

## Risks / Trade-offs

- [Native textures are larger than the 150 px composites: 172.7 MB against about 66 MB today] → Pages show thumbnails that MediaWiki renders once and caches. File pages show the full picture, which the 1024 × 1024 textures make sharper.
- [A page that embeds an icon file directly, outside the templates, shows the bare picture without a frame] → The Game Data guide documents the icon module as the way to show a game icon. A scan lists main-namespace pages that embed icon files directly, so editors can see them.
- [The first migration takes long: about 1,270 uploads, 622 deletions, and about 870 redirect edits] → The run record makes it resumable, and it runs once. Later runs touch only what changed.
- [A deletion removes a file that something still needed] → Deletions touch only the project's copies at titles that redirect to the picture, and the bot's files that no page shows when the run reaches them. The revert undeletes them.
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
8. Decide with WoWMuch about the operator's unused files that the plan lists.

**Rollback:** `images publish --revert <stamp>` restores every replaced file version and undeletes every deleted file. The repository deploy's rollback restores the templates and modules.
