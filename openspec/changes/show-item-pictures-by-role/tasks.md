# Tasks

## 1. Capture and catalog item renders

- [ ] 1.1 `refactor(images): call rendered pictures renders`: rename the image kind `portrait` to `render` in the clean schema, `application/processor/pictures.py`, and `image_publication_run.py` (design D4). Let each approval's entity kind decide the file description, so that a render of an item says that it shows the item by itself. Verify: a unit test for the description of a character render and of an item render passes, and after `extract build` the catalog's titles and hashes equal those before, and `--dry-run images publish` plans nothing.
- [ ] 1.2 `feat(images): list item models in the capture manifest` (design D3): add one entry for each item subject with a part, without blueprints: subject, render title, kind (`weapon`, `worn`, `mask`, `furnishing`), item ID, slot, part name, and pages. Verify: unit tests cover the four kinds, the shared subject of the two Letters and Words, and the exclusion of an item without a part and of a blueprint, and `images manifest --dry-run` lists every other item with a part once.
- [ ] 1.3 `feat(maptilecapture): capture an item by itself` (design D2 and D3): add the item source to the capture protocol, build each kind's source in `PortraitStudio` from clones of the male body, its hand anchors, the mask objects, and the Reliquary furnishings, colour worn parts from the item record that `GameData.ItemDB.GetItemByID` returns, add the preset `item-1`, and fail a capture whose part does not exist with the subject and the name. Verify: the mod builds, and a capture of the Wolfhide Boots in game leaves the player's equipment and colours as they were.
- [ ] 1.4 Capture the Molorai Bow, the Wolfhide Boots, the Feathered Cape, one helmet, Mask: Fox, and the Wood Training Set, and show the six pictures to the user. Change the source or the preset until the user approves the look, and record the decision in design D2. Verify: the user approves the six pictures.
- [ ] 1.5 `feat(images): catalog approved item renders` (design D4): `images review` checks that an item capture shows the expected part, `images approve` records the entity kind `item`, and `extract build` adds `<subject> render.png` for each item with an approved render and a page, and fails when an item's and a character's render share a title and differ. Verify: unit tests cover an item title, two items whose renders have equal pixels, and the collision, and after the prototypes of task 1.4 are approved the catalog lists their six titles.
- [ ] 1.6 `docs(images): describe item captures in the image skills`: add the item kinds, the preset, and the review of item captures to `.agent/skills/wiki-templates/SKILL.md`, and the recapture of item subjects after a game update to `.agent/skills/refreshing-game-data/SKILL.md`. Verify: `uv run pytest tests/contract/test_document_paths.py` passes.

## 2. Item infobox

- [ ] 2.1 `feat(wiki): show item renders and screenshots in the infobox` (design D1): Template:Item takes `render` and `screenshot` and shows their gallery when one of the files exists and `icon` otherwise, with `imagecaption` below. The item generator fills `render` from the catalog and `screenshot` as `<subject> screenshot.png`, field preservation owns both, and semantic validation knows them. Add local fixture pages for an item with both pictures, a render only, a screenshot only, and neither, with smoke rows. Verify: the unit tests pass, the local wiki's smoke checks pass, and the user sees a screenshot of the four layouts.
- [ ] 2.2 `docs(wiki): tell editors where item screenshots go`: extend the Images section of `wiki/content/Erenshor Wiki/Game Data.wiki` and the documentation of Template:Item with the item's render, its screenshot title, and the icon that tooltips keep. Verify: the local wiki renders the guide without errors, and the contract tests pass.

## 3. Publish the renders

- [ ] 3.1 Capture, review, and approve every item subject of the manifest. Record the numbers approved and rejected, and the reason for each rejection, in this task. Verify: `approved.json` holds an approval for every subject that is not recorded as rejected.
- [ ] 3.2 Deploy Template:Item and the guide after a dry run with the render check and approval. Verify: the render check shows no change on the item pages it selects, because no page passes `render` or `screenshot` yet.
- [ ] 3.3 Publish the item renders after a dry run and approval, and review its contact sheets. Verify: the next dry run plans nothing, and `File:Molorai Bow render.png` exists.
- [ ] 3.4 Deploy the generated item pages after an article dry run and approval. Verify: the next dry run plans no edit, the Molorai Bow's infobox shows its render, and Bread's shows its icon.

## 4. Editors' item pictures

- [ ] 4.1 `feat(images): move editors' item pictures to their screenshot titles` (design D6): restore `images move-screenshots` of `name-pictures-by-role` from the history and let it take a reviewed list of title pairs, with its dry run, the publication run's move and redirect retargeting, and a run record that `images publish --revert` undoes. Run it for the 18 files after approval. Verify: unit tests cover a listed move and its revert, and after the run each listed file is at its screenshot title and its old title redirects there.
- [ ] 4.2 Build the page edits of design D6 with a throwaway script: add `render` and `screenshot` to the 16 hand-written mask infoboxes, and remove the in-text copies of the moved pictures on the mask pages, the Shrine of Blessings, and the Stone Statue: Soluna. Replace whole picture lines only, never a parameter value that equals a title. Apply them after WoWMuch reviews each diff of `wiki apply-page-edits --dry-run`. Verify: each mask page shows its render and its screenshot as tabs, and `prop=fileusage` of the 18 old titles lists no page.
- [ ] 4.3 `refactor(images): remove the one-time screenshot move`: delete the command of task 4.1 and its tests. Verify: no file under `src/` names it, and the unit tests pass.

## 5. Lamps and the Watcher's Lens

- [ ] 5.1 After task 5.45 of `adopt-data-backed-wiki` exports the `Inventory` references, `feat(images): capture the lamps and the lens`: add a kind for the objects that `Inventory.BeltLamp` and `FernallanLensObj` name, capture, review, approve, and publish them, and deploy their pages, each live step after a dry run and approval. Verify: the Belt Lamp, the Shivering Belt Lamp, and the Keeper's Lantern show one shared render, and the Watcher's Lens shows its own.

## 6. Integration and archive

- [ ] 6.1 Run `uv run erenshor test ci` and `uv run erenshor test wiki --warm`, and check on live a weapon, a pair of boots, a mask, a furnishing, and a consumable. Verify: both commands pass, and each page shows the picture that the `wiki-images` spec names for it.
- [ ] 6.2 Archive the change with `openspec archive show-item-pictures-by-role --yes`. Verify: `openspec/specs/wiki-images/spec.md` holds the item requirements.
