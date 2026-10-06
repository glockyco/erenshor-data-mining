## Context

See `proposal.md` for the problem. The first inventory listed 117 files. A live scan on 2026-10-05 of the image fields of all 2,816 generated pages, with `{{PAGENAME}}` and `{{PAGENAMEE}}` expanded, found 120 missing files: the 117 and three new ones, `Trick Target.png`, `Wandering Gladiator.png`, and `Prielian Cascade.png`. The six pages that carry the unused notice of `content-lifecycle.json` add six more files, because generation does not write those pages. Of the 126 files, 124 names match `characters.image_name` in the main clean database. `Underspine Hollow.png` and `Prielian Cascade.png` belong to zone pages. No row matches an item, spell, skill, or stance image. The table below is the authoritative input to this change until a new live scan replaces it.

Two findings of 2026-10-06 changed rows of the table. The 400 and 800 AC training dummies share one mesh and material with the plain dummies of the Wood Training Set and the Port Azure dummy, so the clean build gives them the existing `Training Dummy.png`. The Expert Training Set's 1000 AC dummy has its own mesh and material, so it needs `Training Dummy (1000 AC).png`. The six rune receptacles became unused pages, and they share one model with the Portal Receptacle of the Celestine Portal set.

`images process` reads the icon fields of items, spells, and skills. It takes their PNGs from the exported `Texture2D` directory and stores processed images in `variants/main/images/current/` with metadata in `variants/main/images/registry.db`. `images compare` classifies changes, and `images upload` uploads selected or changed registry images. Discovery never reads characters or zones. The registry currently has 1,515 item, 348 spell, and 51 skill rows, and no character row. It does not contain a source for any file in this inventory.

The source check compared the first 117 names with exported `Texture2D/*.png` and `Sprite/*.asset` names, ignoring case. None is a matching portrait sprite. Character rows have no icon column. Nine missing summons have a spell whose icon is present in game data, but that icon depicts the spell, not a portrait of its creature. `UnderspineMap.png` and its sprite asset exist, but that is a map graphic, not the `Underspine Hollow.png` image that an editor put in the zone infobox.

## Goals / Non-Goals

**Goals:**

- Give every file a named source or a clear request for a person to provide an image.
- Keep character, chest, summon, and zone pictures distinct from item and ability icons.
- Resolve missing images without changing an existing file or an editor's chosen image.

**Non-Goals:**

- Change infobox image names to make a source easier to find. A title changes only where the page shows the wrong model (D5).
- Use a map sprite such as `UnderspineMap.png` as a replacement for a zone illustration without editor approval.
- Reprocess every icon or redesign the existing icon pipeline.

## Decisions

### D1. Image source inventory

Each table row is one missing file, not one character record. The 101 character rows include people, creatures, and scene props that the game models as characters. Six of them belong to pages with the unused notice: their prefabs are under `Resources/NPCs`, but nothing in the current game spawns them. The 10 chest or receptacle rows and 13 summon rows are subclasses of those character records. `Summoned: Elder Dryad.png` is a character row, because no spell summons that creature. The remaining two rows are zones. There are no item or spell or skill files in this list. The database `image_name` gives the file stem, while `wiki_page_name` gives the article. A file may serve several pages or several infoboxes.

`In-game model or scene` means the game contains a character or scene object, not a usable PNG. It does **not** mean that a capture implementation already works. The chosen source is a reviewed capture from the running game. A person can supply a better screenshot if the model cannot be captured well.

| File | Kind | Source |
|---|---|---|
| A Golden Spirit.png | character | In-game model or scene. No matching portrait sprite. |
| Ancient Canine.png | character | In-game model or scene. No matching portrait sprite. |
| Adonalle Thistlewich.png | character | In-game model or scene. No matching portrait sprite. |
| A Wisp.png | character | In-game model or scene. No matching portrait sprite. |
| Apprentice Smith.png | character | In-game model or scene. No matching portrait sprite. |
| Apostalo Ostagla.png | character | In-game model or scene. No matching portrait sprite. |
| Aphis Anglevas.png | character | In-game model or scene. No matching portrait sprite. |
| Animation of Grace.png | character | In-game model or scene. No matching portrait sprite. |
| Animation of Faith.png | character | In-game model or scene. No matching portrait sprite. |
| Azynthian Shadow.png | character | In-game model or scene. No matching portrait sprite. |
| Azynthian Sacrifice.png | character | In-game model or scene. No matching portrait sprite. |
| Azynthian Keeper.png | character | In-game model or scene. No matching portrait sprite. |
| Azynthian Corruptor.png | character | In-game model or scene. No matching portrait sprite. |
| Bowmistress of Sivakaya.png | character | In-game model or scene. No matching portrait sprite. |
| Bellsie Belwain.png | character | In-game model or scene. No matching portrait sprite. |
| Captain Bellwain.png | character | In-game model or scene. No matching portrait sprite. |
| Breena Carpenter.png | character | In-game model or scene. No matching portrait sprite. |
| Braxonian Receptacle.png | chest or receptacle (unused page) | No upload. The page points at `Portal Receptacle.png`, which shows the same model (D5). |
| Braxonian Chest.png | chest or receptacle | In-game model or scene. No matching portrait sprite. |
| Braxon Verono.png | character | In-game model or scene. No matching portrait sprite. |
| Braxon Ice Crystal.png | character | In-game model or scene. No matching portrait sprite. |
| Constellation: Wolf.png | character | In-game model or scene. No matching portrait sprite. |
| Constellation: Snake.png | character | In-game model or scene. No matching portrait sprite. |
| Constellation: Nightmare.png | character | In-game model or scene. No matching portrait sprite. |
| Constellation: Bear.png | character | In-game model or scene. No matching portrait sprite. |
| Cluster of Eggs.png | character | In-game model or scene. No matching portrait sprite. |
| Chosen Fawn.png | character | In-game model or scene. No matching portrait sprite. |
| Chell Rezza.png | character | In-game model or scene. No matching portrait sprite. |
| Ceremonial Brazier.png | character | In-game model or scene. No matching portrait sprite. |
| Deadly Spiderling.png | character | In-game model or scene. No matching portrait sprite. |
| Dark Flame Brazier.png | character | In-game model or scene. No matching portrait sprite. |
| Expert Gladiator.png | character | In-game model or scene. No matching portrait sprite. |
| Enterprising Spirit.png | character | In-game model or scene. No matching portrait sprite. |
| Elemental Crystal.png | character | In-game model or scene. No matching portrait sprite. |
| Elemental Construct.png | character | In-game model or scene. No matching portrait sprite. |
| Echo of Grace.png | character | In-game model or scene. No matching portrait sprite. |
| Forming Constellation.png | character | In-game model or scene. No matching portrait sprite. |
| Forge Golem.png | character | In-game model or scene. No matching portrait sprite. |
| Felthir Bumbers.png | character | In-game model or scene. No matching portrait sprite. |
| Faith.png | character | In-game model or scene. No matching portrait sprite. |
| Faerie Trickster.png | character | In-game model or scene. No matching portrait sprite. |
| Ice Golem.png | character | In-game model or scene. No matching portrait sprite. |
| Honsus.png | character | In-game model or scene. No matching portrait sprite. |
| Hidden Hills Receptacle.png | chest or receptacle (unused page) | No upload. The page points at `Portal Receptacle.png`, which shows the same model (D5). |
| Headless.png | character | In-game model or scene. No matching portrait sprite. |
| Growing Void.png | character | In-game model or scene. No matching portrait sprite. |
| Khorso, Soluna's Advisor.png | character | In-game model or scene. No matching portrait sprite. |
| Katia Marado.png | character | In-game model or scene. No matching portrait sprite. |
| Lighthouse Flame.png | character | In-game model or scene. No matching portrait sprite. |
| Lifeflame Brazier.png | character | In-game model or scene. No matching portrait sprite. |
| Large Ice Elemental.png | character | In-game model or scene. No matching portrait sprite. |
| Large Fire Elemental.png | character | In-game model or scene. No matching portrait sprite. |
| Molorai Archmage.png | character | In-game model or scene. No matching portrait sprite. |
| Molorai Archivist.png | character | In-game model or scene. No matching portrait sprite. |
| Nadir.png | character | In-game model or scene. No matching portrait sprite. |
| Mutt.png | character | In-game model or scene. No matching portrait sprite. |
| Planar Flame Energy.png | character | In-game model or scene. No matching portrait sprite. |
| Phantom's Ward.png | character | In-game model or scene. No matching portrait sprite. |
| Pack Mother.png | character | In-game model or scene. No matching portrait sprite. |
| Opus.png | character | In-game model or scene. No matching portrait sprite. |
| Prichard Zemoro.png | character | In-game model or scene. No matching portrait sprite. |
| Portal Receptacle.png | chest or receptacle | In-game model or scene. No matching portrait sprite. |
| Planar Frost Energy.png | character | In-game model or scene. No matching portrait sprite. |
| Ripparian Receptacle.png | chest or receptacle (unused page) | No upload. The page points at `Portal Receptacle.png`, which shows the same model (D5). |
| Reliquary Ward.png | character | In-game model or scene. No matching portrait sprite. |
| Reliquary Guard.png | character | In-game model or scene. No matching portrait sprite. |
| Reliquary Fiend.png | character | In-game model or scene. No matching portrait sprite. |
| Reaver of Sivakaya.png | character | In-game model or scene. No matching portrait sprite. |
| Sivakayan Doomshade.png | character | In-game model or scene. No matching portrait sprite. |
| Silkengrass Receptacle.png | chest or receptacle (unused page) | No upload. The page points at `Portal Receptacle.png`, which shows the same model (D5). |
| Shrouded Sivakayan.png | character | In-game model or scene. No matching portrait sprite. |
| Shadow of Vitheo.png | character | In-game model or scene. No matching portrait sprite. |
| Shadow of Soluna.png | character | In-game model or scene. No matching portrait sprite. |
| Shadow of Fernalla.png | character | In-game model or scene. No matching portrait sprite. |
| Shadow of Brax.png | character | In-game model or scene. No matching portrait sprite. |
| Scorpling.png | character | In-game model or scene. No matching portrait sprite. |
| Sapling.png | character | In-game model or scene. No matching portrait sprite. |
| Soul Linked Spider.png | character | In-game model or scene. No matching portrait sprite. |
| Solunarian Sunbringer.png | character | In-game model or scene. No matching portrait sprite. |
| Solunarian Receptacle.png | chest or receptacle (unused page) | No upload. The page points at `Portal Receptacle.png`, which shows the same model (D5). |
| Solunarian Paladin.png | character | In-game model or scene. No matching portrait sprite. |
| Solunarian Moonkeeper.png | character | In-game model or scene. No matching portrait sprite. |
| Solunarian Chest.png | chest or receptacle | In-game model or scene. No matching portrait sprite. |
| Sivakayan Voidmaster.png | character | In-game model or scene. No matching portrait sprite. |
| Sivakayan Shadow.png | character | In-game model or scene. No matching portrait sprite. |
| Sivakayan High Shadow.png | character | In-game model or scene. No matching portrait sprite. |
| Ta'Dah, Sorcerer of Ripper.png | character | In-game model or scene. No matching portrait sprite. |
| Syzygy.png | character | In-game model or scene. No matching portrait sprite. |
| Summoned: Wretched Fawn.png | summon | In-game model or scene. No matching portrait sprite. |
| Summoned: Treant.png | summon | In-game model or scene. No matching portrait sprite. |
| Summoned: Protector.png | summon | In-game model or scene. No matching portrait sprite. |
| Summoned: Pocket Vendor.png | character | In-game model of a Reliquary furnishing. No spell summons it. No matching portrait sprite. |
| Summoned: Pocket Bank.png | character | In-game model of a Reliquary furnishing. No spell summons it. No matching portrait sprite. |
| Summoned: Pocket Auctions.png | character | In-game model of a Reliquary furnishing. No spell summons it. No matching portrait sprite. |
| Summoned: Magma Fiend.png | summon | In-game model or scene. No matching portrait sprite. |
| Summoned: Forest Spirit.png | summon | In-game model or scene. No matching portrait sprite. |
| Summoned: Decayed Fawn.png | summon | In-game model or scene. No matching portrait sprite. |
| Summoned: Cursed Fawn.png | summon | In-game model or scene. No matching portrait sprite. |
| Summoned: Brute.png | summon | In-game model or scene. No matching portrait sprite. |
| Summoned Widow.png | summon | In-game model or scene. No matching portrait sprite. |
| Summoned Dire Wolf.png | summon | In-game model or scene. No matching portrait sprite. |
| Undying Light.png | character | In-game model or scene. No matching portrait sprite. |
| Underspine Hollow.png | other (zone) | Editor image or zone screenshot. `UnderspineMap.png` is a different map sprite. |
| Training Dummy (1000 AC).png | character | In-game model of the Expert Training Set in a Reliquary room. No matching portrait sprite. |
| Vithean Chest (Round 8).png | chest | In-game model of the eighth arena chest, which is golden while the seven others are blue. No matching portrait sprite. |
| Tojokom.png | character | In-game model or scene. No matching portrait sprite. |
| Vithean Myrmidon.png | character | In-game model or scene. No matching portrait sprite. |
| Vithean Executioner.png | character | In-game model or scene. No matching portrait sprite. |
| Vithean Conscript.png | character | In-game model or scene. No matching portrait sprite. |
| Vithean Chest.png | chest or receptacle | In-game model or scene. No matching portrait sprite. |
| Vithean Archer.png | character | In-game model or scene. No matching portrait sprite. |
| Zenith.png | character | In-game model or scene. No matching portrait sprite. |
| Windwashed Receptacle.png | chest or receptacle (unused page) | No upload. The page points at `Portal Receptacle.png`, which shows the same model (D5). |
| Warming Flame.png | character | In-game model or scene. No matching portrait sprite. |
| Warded Shadow.png | character | In-game model or scene. No matching portrait sprite. |
| Ward of the Forest.png | character | In-game model or scene. No matching portrait sprite. |
| Ward of Siraethe.png | character | In-game model or scene. No matching portrait sprite. |
| Trick Target.png | character | In-game model or scene. No matching portrait sprite. |
| Wandering Gladiator.png | character | In-game model or scene. No matching portrait sprite. |
| Prielian Cascade.png | other (zone) | Editor image or zone screenshot. The zone page names it with `{{PAGENAME}}.png`. |
| Ancient Sentinel.png | character (unused page) | Prefab under `Resources/NPCs`. No matching portrait sprite. |
| Bazxzoth.png | character (unused page) | Prefab under `Resources/NPCs`. No matching portrait sprite. |
| Fernalla's Guardian Golem.png | character (unused page) | Prefab under `Resources/NPCs`. No matching portrait sprite. |
| Holy Corpse.png | character (unused page) | Prefab under `Resources/NPCs`. No matching portrait sprite. |
| Queen Evadne.png | character (unused page) | Prefab under `Resources/NPCs`. No matching portrait sprite. |
| Summoned: Elder Dryad.png | character (unused page) | Prefab under `Resources/NPCs`. No matching portrait sprite. |

### D2. Existing image pipeline and ownership

The bot owns processed game icons and reviewed model captures. The source icons and character objects come from the installed game. The AssetRipper export is read-only. Editors own the zone illustrations and may replace any bot capture with a better screenshot. A new bot-generated portrait needs a selected game object, a reviewed PNG, a source record, and an exact destination file title.

The current upload command deduplicates by `image_name`, uses registry upload state, sanitizes colons, and creates redirects for altered titles. It uploads with `ignore_warnings=True`. The capture upload path must check the live file and redirect target before each write and refuse to replace existing bytes. A targeted missing-file batch is separate from an all-icons upload. The contract is the file title used by the article, even when a sanitized destination requires a redirect.

No repository image command discovers characters, so the existing character files did not come from this icon path. The uploader of a specific existing file must be read from its live file history. That check waits until the concurrent wiki deploy finishes. Do not attribute those files to editors or a bot without the history.

The chest files need no separate uploads for each boss. `Braxonian Chest.png` also appears on Frost and Inferno. `Solunarian Chest.png` also appears on Nadir and Zenith. `Vithean Chest.png` also appears on Honsus, Opus, Tojokom, and Vitheo the Tactician. Those chest infoboxes were added to boss pages by editors. Keep their box and image link intact. The four training dummy kinds share one page. Three show `Training Dummy.png`, and the 1000 AC kind needs its own file because its model differs (D5). `Faith.png` is the character Faith, not an item or spell icon. Its game object is present as `GameObject/Faith.prefab`, but it has no portrait sprite.

### D3. Repeatable in-game capture

`MapTileCapture` gives a scene loader, a WebSocket request loop, a render texture to PNG path, and cleanup patterns. It is not an entity camera. Its map camera looks straight down from world height 1000 and its suppressor hides characters, particles, nameplates, and canvases. A portrait mode needs a separate request and rendering path, not a change that turns map tiles into portraits.

A generated manifest contains the target file name, entity stable key, scene or prefab source, game build, and camera preset. Each missing file appears once. The manifest picks one visible instance when several records share an image name. It takes the 1000 AC training dummy from the Expert Training Set of a Reliquary room. It must handle event-only objects and summons that are not naturally present in a loaded scene. Every NPC prefab under `Resources/NPCs` loads without a scene, as the game's own `Resources.LoadAll<GameObject>("NPCs")` shows, so the six unused characters with prefabs can be captured from them. The six unused rune receptacles need no capture of their own (D5). A character whose object exists only in a scene, such as `Enterprising Spirit`, needs that scene. Probe representatives through HotRepl: a normal NPC, a chest, a summon, a scene prop, Faith, the 1000 AC Training Dummy, and one unused prefab. For each, inspect renderers, bounds, pose, materials, effects, and the scene or spawn step. An object without useful renderers goes to an editor review list, not a blank file.

Use a dedicated temporary camera with one fixed angle, projection, and lighting preset. Render at 1024 × 1024 pixels, then crop the subject with a consistent margin. Frame the combined visible renderer bounds. Pause or set a neutral idle pose, then wait for stable materials and animation. Render only the target with transparent pixels outside its silhouette. Hide the player, other actors, UI, target rings, names, and distracting scene geometry without hiding useful target effects. Keep the alpha channel in the final PNG. Store the image, manifest entry, and a contact sheet together for human review. Reject clipped, dark, empty, or wrong-model output.

Do not alter live play after a run. Use a temporary camera rather than `ChunkRenderer.RenderChunk`, which changes MainCam's pose and projection without restoring them. Record and restore all state, destroy temporary objects, stop active coroutines before disposal, and close the game through its regular shutdown path. Test an aborted capture as well as a successful one. A HotRepl probe finds the correct game object and camera preset, but it is not the final pipeline.

### D4. Missing-image categories and reviewed uploads

The selected route is hidden tracking categories, in-game capture, human review, and bot upload. RuneScape Wiki uses hidden `Needs image` categories, including kind-specific subcategories. It has a project that generated missing model images in bulk and then asked editors to review and upload them. Sources: https://runescape.wiki/w/Category:Needs_image and https://runescape.wiki/w/User:Isobel/Model_viewer_project . Erenshor also uses bulk capture with human review, but its bot uploads only approved captures. Editors can replace a bot file with a better screenshot.

Add hidden `Category:Needs Image` with `Needs Character Image`, `Needs Chest Image`, and `Needs Summon Image` child pages under `wiki/content/Category/`. Their instructions tell editors what image is missing and how to submit or replace one. The `Character` infobox template adds the category only in the main namespace. Decided on 2026-10-06: only character images are tracked. Item, spell, skill, and stance icons come from the game's icon export, which `erenshor images upload` publishes, and a live check on 2026-10-06 found none of the 1,899 of them missing. A missing icon is a gap of the icon pipeline that only the bot can close, not a request to editors, so those infoboxes check nothing. The first deploy had created `Needs Item Image` and `Needs Stance Image`, which wait for an administrator to delete them. A missing character file uses the chest or summon category when appropriate. No category text appears inside an infobox.

Existing `image` parameters contain rendered wikitext such as `[[File:Faith.png|thumb]]`, not a bare file title. Add optional `imagefile` and `imagekind` to `Character`. The generator supplies the actual final file title of every image that it generates. Decided on 2026-10-06: the merge rules and the Game Data guide no longer promise editors an item infobox image, because no item infobox carries one and the merge dropped any that an editor added. A template without `imagefile` can classify a blank `image` field, but it does not guess a title from arbitrary wikitext. This keeps hand-written legacy calls compatible. `Character` already knows the Chest type for generated chest pages, while `imagekind=summon` distinguishes summoned creatures. The editor-added chest boxes on boss pages still say `type=Enemy` and have no stable key. Add `imagefile` and `imagekind=chest` to those boxes through a guarded, approved article edit. Keep the box and every existing field.

Check real uploaded bytes, not merely the existence of a file description page. MediaWiki's `#ifexist:File:...` returns true for a redirect page with no image. `#ifexist:Media:...` may express file existence, but its shared-repository behavior and expensive parser limit need a host check. Verify an uploaded file, a missing file, a redirect to a file, and a redirect to a missing file in the local stack and on the live wiki before selecting the template expression. If the available parser expression cannot make this distinction or exceeds the page limit, use a generated missing-file list and a template parameter that is refreshed from verified file status instead. The resulting categories must still meet the same observable contract.

Rebuild the manifest before each capture run from three inputs: the generated pages, the pages that `content-lifecycle.json` marks as unused, and the live missing-file scan. Expand `{{PAGENAME}}` and `{{PAGENAMEE}}` in image fields before the scan. The unused pages are not generated, so they get no `imagefile` parameter and join no `Needs Image` category. The manifest reads them from the facts file instead. The bot captures only its approved manifest, then produces a contact sheet and source record for review. A second approval follows a targeted dry run against the live file titles. Before every upload, check the title and any redirect target again, skip files that exist, and report the owner. Do not use `--force` or overwrite warnings for this route. Once uploaded, purge affected pages and confirm their missing-image categories clear.

The zone files stay with editors. `Underspine Hollow.png` and `Prielian Cascade.png` are not model captures. Do not replace either with a map sprite such as `UnderspineMap.png`, and do not change the image field of either zone page.

### D5. Image titles follow the model

Decided on 2026-10-06: the export records the model of each character, the meshes and materials of the renderers of its scene object or prefab. When a wiki page holds several kinds of a character, kinds that share a model share one image title, and a kind whose model differs from the others of its page gets its display name as its image title. The training dummies show the case: the plain, 400 AC, and 800 AC kinds keep `Training Dummy.png`, and the 1000 AC kind gets `Training Dummy (1000 AC).png`. The rule may change titles on other pages with several infoboxes, so the article dry run lists each such page for review. The export found one more such page: the eighth Vithean chest is golden while the seven others are blue, so it gets `Vithean Chest (Round 8).png`. An editor-added chest box on the page of Vitheo the Tactician, whose round is the eighth, shows `Vithean Chest.png`, so the editors decide whether it should show the golden chest. The build stops when two kinds with different models share a display name, because no title tells them apart. A character whose look the game changes at runtime, such as an NPC that equipment dresses, needs a check before the rule covers it.

Decided on the same day: the seven receptacles share one model. One capture becomes `Portal Receptacle.png`, and a reviewed one-time edit points the image of the six unused rune receptacle pages at that file, so that no identical file is uploaded six more times.

## Risks / Trade-offs

- Game models can render differently outside their scene. Some prefabs depend on lighting, animation, equipment, or effects that need a live scene. A representative capture and image review must prove each route.
- One file name can refer to several game records. Pick a representative object by stable key and review it, rather than silently taking the first database row.
- A title can gain an editor upload between inventory and deployment. Recheck exact titles and redirects immediately before each write. On conflict, skip and report, not overwrite.
- The 126-row list is a snapshot. Rebuild a live inventory before work and compare file counts and identities. A new game build may add files or remove pages.

## Migration Plan

1. Add the hidden categories and infobox checks. Generate the new optional file and kind parameters and deploy repository pages after the normal dry run, render check, and approval. Refresh the affected articles through their guarded deploy. With editor approval, add only tracking parameters to the chest infoboxes on the eight boss pages.
2. Build the manifest and a separate capture mode. Validate its output against known good files and a representative object from each kind.
3. Run captures into an untracked staging directory. Review the source records and contact sheet. Reject bad images before the bot sees the approved set.
4. Scan the live wiki again and run a targeted dry run. Review file names, redirects, source images, and any existing files. Get approval for each live batch.
5. Upload only missing approved files. Verify the files and each affected page, including chest boxes on boss pages, the 1000 AC Training Dummy, Faith, and the unused pages, of which the six rune receptacles show `Portal Receptacle.png`. Both zone files remain on the editor list.

If a batch produces a wrong new file, stop it. An administrator removes an unwanted new file. Do not edit pages to conceal a failed upload.

## Open Questions

- Main chose 1024 × 1024 render pixels, followed by a consistent crop around the subject. The route and size are decided. No design choice remains open.
