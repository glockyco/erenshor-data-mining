# Design

## Context

The picture catalog of `rebuild-game-image-pipeline` gives every entity one title, `image_file_title(*names)`, which is the entity's image name with `.png`. A name with a colon cannot hold a file, so `upload_file_title` drops the colon, the catalog keeps the colon title as a redirect, and the planner's `titles()` and `_upload()` join the two. 326 of the catalog's titles have a colon.

On 2026-10-07 the wiki held 2,515 files, and none had a role word in its name. The latest publication plan (`publish/20261007T165751Z`) counts 1,385 project files, 954 project redirects, and 758 character titles that hold an editor's file: 752 opaque screenshots, 4 cut-outs on transparency, and 2 not cached. Editors own no icon title.

2,913 pages show the project's titles. 133 of them are not generated. Those pages write 1,118 file names out in full and get 1,421 more through templates: the project's `ItemLink`, `AbilityLink`, and `Gear/Slot`, and the editors' `Gear/MiniSlot`. The Lua link and tooltip modules append `.png` to a name, and so do `Gear/Slot` and `Gear/MiniSlot`. Hand-written pages call the project's infoboxes with an image parameter 37 times: in template documentation, in a user's sandbox, and on pages that generation does not write.

The local wiki runs Portable Infobox 0.8. Its `NodeMedia` turns a `<gallery>` in an image field into tabs labelled by the gallery captions. It drops a gallery file that does not exist, and it shows a gallery with one existing file as a single picture with its label as the caption, both observed on 2026-10-07. A tabbed infobox shows no `<caption>`.

30 generated character pages carry an editor's `imagecaption`. Some describe the screenshot, such as "Gherist holding a Sivakayan Straightsword", and the others are flavour lines.

## Goals / Non-Goals

**Goals:**

- One rule derives every picture title, and it never needs a redirect from another spelling.
- A title's owner follows from its role. The bot owns `icon` and `render`, and the editors own `screenshot`.
- Every file keeps its history, and every old title keeps resolving.

**Non-Goals:**

- Picking a "better" title for an editor's file beyond its role. The subject stays the character's.
- Removing the old titles' redirects. Wikimedia Commons' file renaming guideline prefers redirects, because they are cheap and keep old revisions and outside links working.

## Decisions

### D1. A title is `<subject> <role>.png`

`picture_file_title(role, *names)` in `domain/value_objects/wiki_filename.py` replaces `image_file_title` and `upload_file_title`. The subject is the first non-empty name, with the characters of `MEDIAWIKI_PROHIBITED_CHARS` dropped and whitespace collapsed. The roles are `icon`, `render`, and `screenshot`, and `equipped` joins when item captures arrive. The catalog owns the `icon` and `render` titles, and generation names the `screenshot` title from the same subject.

Alternatives:

- **The plain title for the main picture.** It means the icon for an item and the render for a character, and it is the title that editors upload to by habit, so the bot and editors would keep competing for it.
- **The role in parentheses**, as in `Faith (render).png`. Parentheses already disambiguate subjects, as in `Training Dummy (1000 AC)`, and two of them read badly.
- **A role prefix**, as in `Render Faith.png`. Sorting would group files by role instead of by subject.
- **Path of Exile's `inventory icon`.** It says more than this wiki needs, because the game has one icon per item.

The Old School RuneScape wiki names files the same way, by subject then role (`<Item> detail.png`, `<NPC> chathead.png`). Its policy asks file names to say how the subject is shown.

### D2. Models are named by subject

The model manifest, the captures, and the approvals name a model by its subject, and they derive the render title from it. Today they name it by its file title, which would tie every approval to a title rule. The local `approved.json` is rewritten once by a throwaway script that maps each title's stem to its subject. The approved PNG files stay as they are, and their SHA-256 binding stays valid.

### D3. The character infobox is a gallery

`Template:Character` puts `{{#tag:gallery|<render>{{!}}Render⏎<screenshot>{{!}}Screenshot}}` in the image's `<default>`. Portable Infobox drops a file that does not exist, shows tabs only when both files exist, and shows a single picture otherwise. The template needs no existence check to choose the layout. `imagecaption` moves from `<caption>`, which a tabbed infobox drops, to a `<data>` row without a label right below the image, styled as a caption.

The `Needs Image` categories check both titles with `{{#ifexist:Media:…}}`, so each infobox costs two expensive parser functions, well within the limit of 500 per page.

A lone picture shows its tab label, Render or Screenshot, as its caption. A picture's alt text is its label as well. Portable Infobox offers no way to set either for a gallery file, and adding one would mean patching the extension.

Alternatives:

- **Tabs built with `#if` and `filepath` checks**, which the prototype of 2026-10-07 used. They duplicate what Portable Infobox does with missing files.
- **A tabber extension.** The wiki does not have one, and Portable Infobox handles galleries already.

### D4. Infobox parameters name the role

The Item, Ability, and Stance infoboxes take `icon`, and Character takes `render` and `screenshot`. All four are generation-owned. Ability's `image` loses its `prefer_manual` rule, because no live Ability page differs from generation and its icon is the game's picture. `imagecaption` stays an editor field under its current name. Zone keeps `image` and `imagecaption`, which the editors own.

### D5. The data modules carry titles

The Lua builders in `application/wiki_lua` write each entity's full file title, `image` becoming `icon`, so `Module:Erenshor/Link`, `Module:Erenshor/Spell/Tooltip`, and the item templates never append `.png`. `Gear/Slot` resolves the item's icon through `Module:Erenshor/Link` instead of `{{{1}}}.png`. Its `image` parameter still overrides the icon, as editors use it today.

### D6. Publishing moves files

The planner gains a `move` verdict. When a picture's chosen file title has no file and a file of the project elsewhere holds the picture, by SHA-1 or by the pixel hash in its upload comment, the plan moves that file. A file at another title of the same picture does not count, because it is that title's copy or file.

The run moves files first, through `action=move` with a redirect left behind, and checks the moved file's SHA-1 at its new title. Then it uploads, then it writes redirects, then it deletes copies and orphans, as it does today.

Every live File redirect that names a moved title joins the plan as a `redirect` to the new title, just as redirects that name a deleted copy join it today. So no redirect leads through another, and MediaWiki shows a file through one redirect only.

A revert moves each file back with `noredirect` and restores each redirect's previous text. The bot account holds `movefile` and `suppressredirect`, which was checked on 2026-10-07.

`titles()`, `_upload()`, and the colon handling go, because no catalog title has a colon. The existing spec already asks the bot to move a file whose entity stops using it, and the planner does not do so today. This decision implements that requirement.

### D7. One cutover moves the editors' screenshots and edits hand-written pages

Publication never touches a screenshot title (see the spec), so moving the 758 editors' files is a one-time step. `erenshor images move-screenshots` plans each character whose plain title, or its colon-free upload title, holds a file that someone else uploaded, where the screenshot title is free. It shows the moves in a dry run, and executes them with the publication run's move, redirect retargeting, and run record. So `images publish --revert <stamp>` undoes it like any run. The command is removed once the cutover is verified. Its run records stay revertible, because revert reads only the record.

The hand-written pages change through the existing `wiki apply-page-edits`, whose revision guards and render checks already protect people's text. A throwaway script builds its TOML from the run records:

- each written-out old file name, as `File:`/`Image:` links, gallery lines, and template values, becomes the moved file's new title
- each hand-written call of a project infobox renames its image parameter
- the editors' `Gear/MiniSlot`, which builds `<name>.png` itself, takes the item's icon title from `Module:Erenshor/Link`, like `Gear/Slot` (D5). Its 30 px picture and its `image` override stay, and WoWMuch approved the edit on 2026-10-07.

The edits replace whole lines, so each old text occurs once.

### D8. Order of the cutover

Each step leaves every page showing a picture:

1. WoWMuch announces the cutover in `#wiki-chat`.
2. The publication run moves the project's files and retargets their redirects. It uploads renders where an editor's file holds the plain title. Old titles resolve through the redirects that the moves leave.
3. `images move-screenshots` moves the editors' files. Their plain titles now redirect to the screenshot titles.
4. A repository-page deploy brings the templates and modules in a transitional form that reads the role parameters and fields and falls back to the retired ones: `render`, then `imagefile`, `icon`, then `image`, and a record's `icon`, then its `image`. The data modules go before the code modules, because the earlier `Module:Erenshor/Link` already accepts a full title. Pages still name the retired parameters, which resolve through the old titles' redirects.
5. The article deploy brings the generated pages that name role titles.
6. `wiki apply-page-edits` edits the hand-written pages, including the editor-written infoboxes that generation keeps unchanged inside generated pages, such as the chest infoboxes beside some bosses.
7. A last repository-page deploy brings the templates and modules without the fallbacks, once a search of the wiki's source finds no page that passes a retired parameter.

Templates and pages cannot change in one write, so without the fallbacks either the old pages or the new pages would show no picture for the hours that the article deploy takes. The fallbacks live only between steps 4 and 7 of one cutover and leave the repository in the commit of step 7.

Each step has its own dry run and approval. Rollback runs in reverse order: the page edits' own guarded reverts, the repository-page and article deploys' rollback commands, then `images publish --revert` for the screenshot run and the publication run.

## Risks / Trade-offs

- [An editor uploads to a plain title after the cutover] → The guide and the infobox's `screenshot` parameter name the screenshot title. An upload to a redirect title hides behind the redirect, as `File:Azure Loyalty Medal .png` did, and no check reports a file of someone else at a title outside the catalog. Such an upload needs a person to notice it.
- [About 8,000 writes hit the wiki's rate limit] → The writes are about 2,100 moves, 2,000 redirects, 760 uploads, 2,900 generated pages, and 133 page edits. Every step resumes from its run record, and the read-only listing plans only what is left.
- [Outside links to full-size file URLs break] → Commons notes that thumbnails follow a file redirect but direct links to the full-size file do not. Links to file pages and to thumbnails keep working.
- [A lone picture is captioned Render or Screenshot] → This is how Portable Infobox shows a lone gallery file. The caption names the picture's kind, which is true. WoWMuch sees a screenshot of the local wiki before the deploy.
- [A caption that describes the screenshot shows under the render tab too] → It stays below both tabs, where an editor can reword it. Four of the 30 captions describe a scene: the town crier, Woe, Gherist Morthario, and the Molorai Militia Arcanist.
- [A literal replacement hits a longer name that ends in an old title, such as `Mold A Ceremonial Ring.png` for `A Ceremonial Ring.png`] → The script matches whole names, bounded by `:`, `|`, `=`, `[`, or a line start before them and by `|`, `]`, `}`, or a line end after them. The apply step shows every diff.

## Migration Plan

See D8 for the order. Before step 2, the local approvals are rewritten to subjects (D2), and the build is rerun. The publication dry run must then plan:

- 1,385 moves
- the creates of the renders whose plain title an editor holds
- the redirects of the role titles and the retargets of the old ones
- no conflict

After step 5, a `prop=fileusage` query over the old titles must list no page. The local wiki's smoke checks cover the infobox layouts, and a live check of Faith, the Aetherfiend, and a character without a screenshot confirms them.
