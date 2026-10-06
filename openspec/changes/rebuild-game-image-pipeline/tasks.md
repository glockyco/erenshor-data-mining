# Tasks

## 1. Resolve icons through the game's references

- [x] 1.1 `feat(export): record the texture that each icon sprite references`: in `ItemListener`, `SpellListener`, and `SkillListener`, record the asset path of the icon sprite's texture instead of the sprite name, in `ItemRecord`, `SpellRecord`, and `SkillRecord` (design D1). The coverage manifest already lists `ItemIcon`, `SpellIcon`, and `SkillIcon` as captured. Verify: after `uv run erenshor extract export`, the raw rows name `4_8.png` for Thorned Branch and `4_3.png` for the five Willow Seeds, and every item, spell, and skill with an icon has a texture path.
  - Done on 2026-10-06 together with task 1.2, because the clean build cannot read the new raw columns without it. `IconTextures.PathOf` records the texture of the sprite and fails the export when a sprite references none. It does not judge the sprite's rect: AssetRipper reconstructs 714 editor sprites with rects tighter than their textures, while in game every one of the 1,299 icon sprites covers its whole texture. The export names a texture for 1,535 of 1,537 items and for every spell and skill, all in `Assets/Texture2D`.
- [x] 1.2 `fix(pipeline): resolve icon pictures through the referenced texture`: carry the texture paths into the clean database so that every consumer that opens an icon file opens the referenced texture. The catalog of task 2.1, which reads the files, fails the build on a missing texture. Add processor tests for the shifted `4_*` family and for a texture outside `Assets/Texture2D`. Verify: after `uv run erenshor extract build`, the 13 entities of the proposal resolve to the textures that the game draws, and the unit and contract tests pass.
  - Done on 2026-10-06: the clean build names each icon by the file of its texture, so `item_icon_name`, `spell_icon_name`, and `skill_icon_name` give the texture that the image pipeline, the map's icon script, and the sheets open. A texture outside `Assets/Texture2D` fails the build. Against the sprite names that `registry.db` recorded, exactly the 13 entities of the proposal changed, from `4_7` to `4_8` for Thorned Branch, for example. Tasks 2.1, 2.2, and 6.1 replace these columns with the catalog.

## 2. Build the image catalog

- [x] 2.1 `feat(images): catalogue game pictures by pixel hash`:
  - The clean build writes `images`, `image_sources`, and `image_titles`, an `image_hash` column on each entity table, and the files under `variants/<variant>/images/catalog/` (design D2).
  - Icons come from their textures unchanged. `ma_frame` enters as a picture of kind `frame`. Approved portraits enter from `approved.json` after their hash check.
  - Each entity gets its wiki title: the stance through its activating skill, and a colon title with its upload title.
  - Add tests for the scenarios of the `game-image-catalog` spec: a shifted sprite name, a missing texture, unchanged margins, a texture shared by many items, equal pixels from two textures, a determinism rebuild, an encoder-only change, provenance, a changed or repeated portrait capture, and the stance title.
  - Verify: two builds of one export write byte-identical catalog files and tables. The 35 spell scrolls of texture `8_5` share one picture, and the clean database lists every one of the 118 approved portraits.
  - Done on 2026-10-06: the build catalogues 1,273 icon pictures from 1,299 textures, because 26 pairs of textures have equal pixels, plus 111 portraits from the 118 approvals and the hotbar frame, under 2,012 wiki titles. Two builds wrote identical files and tables. 36 items share the picture of `8_5`. All 118 approved titles are listed, the six of the unused pages included. The first build stopped on two titles that named two pictures each, and `mapping.json` now gives the Vitheo artifact and the Group Regrowth effect their own image names. Generation changes only the Vitheo artifact's tooltip. `approved.json` records each approval's build and preset, so approvals of different builds coexist. Generators and the catalog share `image_file_title`.
- [x] 2.2 `feat(maps): build item icons from the image catalog`:
  - `erenshor maps build` and `maps dev` write each map-visible item's icon from its catalog picture as WebP at 20 and 48 px, named by pixel hash, fitted within the square at its own proportions (design D9).
  - The map's consumers address icons by the pixel hash from the clean database. Remove `src/maps/scripts/generate-item-icons.mjs`. `sharp` stays for the other image scripts.
  - Add tests for rebuilding on a changed hash and keeping files on an unchanged one.
  - Verify: the map unit and browser tests pass, and in a browser the map search shows the branch for Thorned Branch and the seed for the Willow Seeds.
  - Done on 2026-10-06: the build wrote 1,064 icons for the 1,514 map-visible items, one per picture, and removed the 2,180 files named by texture. The 183 unit tests and 12 browser tests passed. In the preview, the search showed the seed for all five Willow Seeds and the branch for Thorned Branch, and the item popup showed the branch at 48 px. `maps dev` builds the icons too, and `sharp` stays for the other image scripts.

## 3. Draw icon frames on the wiki

- [x] 3.1 `feat(wiki): draw game icon frames like the game`:
  - Add `Module:Erenshor/Icon` and `Template:Icon/styles.css` with the item slot and the hotbar frame of design D7.
  - Switch every icon site to them: the `Item/*` headers, `Gear/Slot`, `Item/SpellDetails`, `SparkleIcon` (the sparkle draws above the slot), `Erenshor/Link`, and `Erenshor/Spell/Tooltip`. The large infobox pictures stay bare (design D7).
  - Add Lua test cases for the item and spell markup at every size, and smoke expectations for an item, a spell, and a skill page in the local stack. Document the module and the parameters of the changed templates.
  - Verify in the local stack's browser, with catalog pictures uploaded locally:
    - The ring runs from `#fdffff` through `#01aaff` at 50% to `#688f9d`, at 75% opacity, with a 3.5% inset of at least 1 px.
    - The 501 × 486 branch keeps its proportions inside the square.
    - Spells lie under `ma_frame`.
    - The Blessed sparkle shows above the slot.
    - The local smoke test passes.
  - Done on 2026-10-06: in Chromium on the local stack, the computed ring matched the measured stops, the insets were 3 px at 80, 2 px at 60, and 1 px at 24, and the branch rendered at 80 × 78, 60 × 58, and 24 × 23, centred. Florablast and the spell, skill, and stance links lie under the hotbar frame, the Blessed sparkle shows above the slot without a link, and a click on a 24 px spell icon opens the spell. The smoke test passed all 51 pages. Deploying gained the `stylesheet` stage for stylesheets that modules load, `Format.fileLink` lost its last caller and was removed, and a link whose entity has no image keeps its text link.

## 4. Publish against the live wiki

- [x] 4.1 `feat(wiki): read and write files the way publishing needs`: add to the MediaWiki client:
  - a listing of every file with its SHA-1, latest uploader, upload comment, and size, through `list=allimages` with continuation
  - a listing of the File namespace's redirects with their final targets and of its other pages
  - an image-usage check through `list=imageusage`
  - a file move with `suppressredirect`
  - an upload that returns the wiki's warnings and the stash `filekey`, and a confirmation through that `filekey`
  - a file's version history and the download of a version, which a revert re-uploads

  Add client tests with recorded responses, including continuation and a warning that an upload does not expect. Verify: the listing of the live wiki reads every file, 3,127 on 2026-10-06, and the tests pass.
  - Done on 2026-10-06: the client lists files and File pages, checks image use, moves pages, confirms stashed uploads, and reads file versions. One helper follows every continuation and fails on a malformed or repeated one; the user-contribution and wanted-page listings use it too. The live wiki refuses `redirects` with the `allpages` generator, so the File pages are listed as redirects and other pages and the redirects are resolved by title. Anonymous, the live listing read 3,236 files (the 3,127 of the morning and the 109 portrait uploads) in 4.5 s, and 379 file redirects and 3,236 other File pages in 3.7 s. `upload_file` no longer sends `bot`, which the upload API does not have.
- [x] 4.2 `feat(images): plan publication against one listing of the live wiki`:
  - Plan every catalog title with the verdicts, the pixel comparison, the title choice, and the retirements of design D4 to D6.
  - Write the plan and the contact sheet of creates and updates to `variants/<variant>/images/publish/<stamp>/`.
  - `erenshor --dry-run images publish` prints the verdict counts, conflicts, and orphans.
  - Add tests for the scenarios of the `wiki-images` spec: two changed icons, an interrupted run, the same pixels in another encoding, an editor's newer version, a new item sharing a picture, a changed shared picture, an identical copy to retire, an icon under an old spelling, and a title with a colon.
  - Verify: a dry run against the live wiki lists Thorned Branch as an update and `Spell_Scroll-_Aetherstorm.png` as an orphan, and names the uploader of every conflict.
  - Done on 2026-10-06: `erenshor --dry-run images publish` planned the live wiki in 433 s: 1,269 updates, 622 retirements, 242 redirects, 199 unchanged titles, 2 creates (the hotbar frame and the Vitheo artifact), and 4 conflicts, with 100 orphans (79 WoWBot, 21 WoWMuch) and 32 contact sheets. Thorned Branch is an update, `Spell Scroll- Aetherstorm.png` an orphan, and `Spell Scroll Meditative Trance.png` a retirement, because it is an output of the old pipeline that WoWMuch uploaded before WoWBot existed, like 102 other files (design D3). The 4 conflicts are the two summons whose upload titles hold Snedn's and Ulor's pictures. The listing settles every pixel comparison without a download, by bytes or size. Live redirects are judged by the page they name, because MediaWiki follows one file redirect, which a local parse confirmed.
- [x] 4.3 `feat(images): publish a plan with a resumable run record`:
  - `erenshor images publish` carries out the plan in the write order of design D8. Before each write it checks the title again, and it confirms an upload only on the warning its verdict expects.
  - Every upload records its provenance in the comment, and a new file gets a description with the game's copyright notice. A retired file gets `{{Delete}}`.
  - Every write goes to `run.json`, with the replaced bytes saved for `--revert`.
  - Remove `images upload-captures`, which publish replaces, and update the `refreshing-game-data` skill and the Images section of the Game Data guide for the new commands, one file per picture, and how an editor's replacement is kept.
  - Add tests for a title that changes after the plan, an unexpected warning, a rerun after an interruption, and a revert.
  - Verify: the tests pass, and a publish against the local wiki stack, a rerun, and a revert leave the local files as the plan says.
  - Done on 2026-10-06: against the local stack, set up like the old pipeline with 150 px copies of Stone of Arcanism, Aura: Aracnism, and Azure Willow Seed, a publish updated two files, retired the spell's copy, and wrote the redirects and the deletion notice. A second plan found every title unchanged, and every title rendered an image. The revert uploaded the replaced bytes again, pointed the retired title back at its retired file, and removed the notice. The local runs changed the design in three places (D6, D8). Each retirement now writes its redirect at once, after the redirects to the pictures' files, where the first order left titles without a picture for the length of all moves. A redirect write reads the page, because the file history of a redirect title is its target's. Updates and reverts accept `duplicateversions`. `upload-captures` and `Approval.batch` are gone, and `model_image_upload` became `model_image_approval`.
  - Changed on 2026-10-06 after the review: the operator is an administrator and asked for deletions through a bot password, so a run deletes copies and the bot's orphans with that account instead of moving copies to `Retired` titles with `{{Delete}}` (design D6), and `move_page` gave way to `delete_page` and `undelete_page`. The plan also points redirects outside the catalog that name a deleted copy at the picture's file, which the live plan found four of.

## 5. Migrate the live wiki

- [ ] 5.1 Run `uv run erenshor --dry-run images publish` against the live wiki and review it with WoWMuch: the verdict counts, every conflict, the orphans, the retirements, and the contact sheet of updates. Verify: WoWMuch approves the plan, or the review leads to fixes and a new dry run.
- [ ] 5.2 With approval, run `uv run erenshor images publish`, then deploy the stylesheet, the icon module, and the changed templates, modules, and guide in the same session, and `Module:Erenshor/Format` in a second deploy once the new `Erenshor/Link`, which no longer calls `Format.fileLink`, is live (design D8). Publishing comes first, because it takes over two hours: the native icons then show bare under the old templates for that time, rather than the old composites showing a second frame inside the new slots, and `File:Hotbar Frame.png` exists before any template draws it. Verify live:
  - a fresh parse of an item, a spell, and a skill page shows the frames
  - the 13 corrected icons show the game's pictures
  - a second dry run plans no create or update
  - the deleted copies' titles and the redirects that named them show the pictures' files
- [x] 5.3 Rebuild and dry-run the map deploy, and deploy it with approval. Verify in a browser that the site's item icons show the catalog pictures, the 12 corrected ones included.
  - Done on 2026-10-06 with approval: the map rebuilt with all 1,064 icons kept and deployed to both services (site version `9df0626c`, legacy version `8bf95c51`). On the live site the search shows the branch for Thorned Branch, the seed for all five Willow Seeds, and Royal Carapace's icon, none broken.

## 6. Remove the old pipeline

- [x] 6.1 `refactor(images): remove the old icon pipeline`: remove the following and their tests:
  - `erenshor images process`, `compare`, `report`, and `upload`
  - `ImageRegistry`, `ImageComparator`, `ImageProcessor`, and the `image_versions` registry
  - `images/icon-background.png`

  Update the README's pipeline description. Verify: no source, test, skill, or document refers to the removed commands or files, and the unit and contract tests pass.
  - Done on 2026-10-06, before the migration, because the publication no longer needs the registry: ownership comes from the uploader alone (design D3). The commands, the three services, their domain entities, `needs_redirect`, the background images, and the `imagehash` dependency are gone, and the dev shell builds without it. The README never described the old pipeline. No source, test, skill, or guide refers to the removed pieces, and the 1,975 unit and contract tests pass. The local `variants/main/images/registry.db` and `current/` are unused data now.
- [ ] 6.2 Decide with WoWMuch about the operator's unused files that the plan lists, which the bot never deletes as orphans: 20 composites of the old pipeline and `Raids.png` on 2026-10-06. Delete the approved ones with the deletion account and record them. Verify: each deleted file has an empty `list=imageusage` result before its deletion.
