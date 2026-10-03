## Context

See `proposal.md`. The facts that shape the approach, measured on 2026-10-03 against the fetch of 2026-09-27 and the generation of 2026-09-28:

- Generation reads `variants/main/wiki/fetched/<title>.txt`, merges generated templates into it, and writes `variants/main/wiki/generated/`. `metadata.json` keeps the fetched revision ID of each page.
- `merge_handler` (`field_preservation.py`) deduplicates exact strings. `merge_templates` pairs old and new roots by position, removes old roots beyond the generated count, and returns the old text unchanged when the generated page has no root of the listed families (`Item`, `Character`, `Ability`). Stance pages are therefore never updated.
- `ZonePageGenerator` merges with the repository file in `wiki/zones/` when it exists and with the fetched page only otherwise.
- `_replace_overview_table` keeps the text before the first `{|` and replaces the rest.
- `HotkeyManager` decrements a hotkey cooldown by `60 × Time.deltaTime`, so a skill cooldown of N ticks lasts N/60 seconds. Ten of the 52 skills have fractional seconds.
- `WikiDeployService` calls `edit_page`, which sends no base revision. The client already has `get_page_snapshots`, `safe_edit_page`, and `safe_create_page`. `deploy-repo-pages` uses them, checkpoints a manifest, and writes rollback sidecars.
- Live: `Template:Character` differs from the repository only by the Elite tier. No main-namespace page passes `stablekey` to `Template:Character` or `lua=1` to any template. `Template:Ability`, `Stance`, `Quest`, and `Zone` do not read `stablekey` and do not check for unknown parameters. The 28 live pages with `type=Rare` are all regenerated pages. `Category:Elites`, `Template:StanceTooltip`, and `Module:Erenshor/Data/Stances` do not exist.
- An anonymous `action=parse` with `templatesandboxtitle` and `templatesandboxtext` renders a page with a candidate template or module and writes nothing.

## Goals / Non-Goals

**Goals:** live articles equal the generator output for the shipping build, editor content survives, and no write can overwrite an edit made after the fetch.

**Non-Goals:** changing which fields the bot owns. The preservation rules stay as they are, except that merging and matching use identity. See `proposal.md` for the scope boundary.

## Decisions

### D1. Merge list fields by link target

Each entry of a merged field is parsed as a link: a semantic link template (`ItemLink`, `QuestLink`, and the others) resolves to its page through `Data/Links` for `stablekey=` and through `link=` or the first positional argument otherwise. A wikilink resolves to its target. Anything else is plain text and compares as text. The merge keeps the live order, puts the generated form in place of each live entry with the same target, and appends generated entries that were not present.

Alternative: change the three fields to `prefer_database`. Rejected: editors list quests and item types that the export does not link, and those would be lost.

### D1a. Generated lists group by what the reader sees

The section generators build `source`, `droprates`, `guaranteeddrops`, `vendorsource`, `used_by`, and the other link lists from rows keyed by stable key. Several entities can share one page and one label, such as the three variants of A Highwayman Raider. One list builder groups the rows by the catalog's page and name, prints the chance once when all members agree and as a range otherwise, and keeps distinct labels apart. The stable-key link of the group points to its first member, which resolves to the same page and label.

### D2. Roots carry their stable key

Generated `Character`, `Ability`, and `Stance` roots gain `stablekey=`, as `Item` roots already have. Matching uses the key. On the first refresh, live roots have no key, so they match by name. When several roots share a name, every pairing of the largest size is scored by the number of fields whose live and generated values are equal. A live root holds the values that an earlier generation wrote for its entity, so its coordinates, level, and drops point to the right variant. The pairing with the best score wins. When several pairings reach the best score and merge to different pages, generation fails for the page, names the keys, and the maintainer adds them by hand once. After the refresh, every root carries its key. A live root that matches nothing stays unchanged and is listed. This keeps editor additions such as the chest infobox on Frost, and it lists stale roots for a human to remove.

Pairing by position gives the same pages today, because the generator and the live pages list variants in the same order, but it breaks when that order changes. A rule that fails whenever the order of same-name roots could change the result stopped 15 pages, and the field values tell all of them apart. The scored pairing stops none of the current pages and does not depend on the order.

Each root owns the companion templates after it: `ItemTooltip` and the `Item/<kind>` templates belong to `Item`, `SpellTooltip` and `SkillTooltip` to `Ability`, and `StanceTooltip` to `Stance`. A companion belongs to the nearest root of its template before it, also when prose or an editor's table stands between them. A merged root takes the companions of its generated root: they replace its first live companion in place, and its other live companions go. A generated root without a live root follows the last live root of its template and that root's companions. This replaces the ordinal reconciliation of ability tooltips and the positional replacement of item tooltips, which attach a companion to the wrong root once roots match by key.

`Template:Character` selects its Lua branch when `stablekey` is present, so the key cannot be added while that selector stands. Character, Stance, Quest, and Zone switch to the selector of `Template:Item`: the Lua branch needs exact `lua=1` and a key. No live page passes `lua=1` or a key to these templates, so every page keeps its parameter infobox. The repository bodies of the Stance, Quest, and Zone parameter branches already equal their live templates. Of the four, only Character is deployed, because it also carries the Elite tier. `Template:Ability` is copied from live into `wiki/templates/` so that the repository owns every template the generated articles use.

The Lua branches stay. The local MediaWiki stack renders 35 fixture pages through them, and they are the entry point of the Lua renderers until the article conversion moves them to the new data-backed templates. Removing them now would rewrite the harness twice, once here and again for the Cargo storage pages. Their Cargo declarations and store calls go with `publish-wiki-cargo-data`.

Alternative: an HTML comment with the key before each root. Rejected: hidden state in the page text that an editor can break without seeing it.

### D3. Zone pages are articles

The zone generator writes to the generated storage like the entity generator, and the generate service merges each zone page into its fetched live page. `wiki/zones/` and the zone output directory are removed. The old reason for repository authority, a generation without a fetch that produces bare stubs, is handled by D5: such a page can only be created, never overwrite a live page.

Every `Zone` field except `title` is prefer-manual. Editors know more than the zone lines. The maintainer removed the zone lines that players cannot reach from Shivering Step and Shivering Tomb. Editors gave Reliquary Hall as the connection of the raid planes and linked both maps of Shivering Tomb. With `maplink` and `connects` as override, a refresh reverts each of these edits. Generated values fill new pages and blank fields, so a new zone line does not reach a page whose `connects` has a value.

The zone migration (`{{Dungeon}}` to `{{Zone}}`, a linked `type`) and the legacy categories of the page normalizer go. No fetched page uses them, except four zone pages that carry an old category name as their own zone category. The normalizer would delete that category.

Alternative: keep `connects` as override and derive it from the zone lines in both directions. Rejected: that gives the raid planes Reliquary Hall, but the zone lines that the maintainer removed are still in the data, and two of them are enabled.

### D4. Stance merge, overview table, cooldowns

- `Stance` joins the merged families with `image` as prefer-manual and `imagecaption` as preserve, matching the other entity templates.
- The overview handler parses the old page, finds the table whose header row equals the generated header, and replaces that table node only. Header cells compare by kind and text, so an editor can restyle them. Zero or several such tables fail the page. A generator that changes its columns must first change the header of the live table.
- One duration formatter divides ticks by 60 and prints up to two decimals. The legacy skill section and the Lua skill data use it. The game's own spell tooltip prints `Cooldown: <seconds> sec`, so seconds are the reader's unit.

### D5. Guarded article deploy

For each page whose generated text differs from its fetched text after page normalization:

1. Read live revisions in batches of 50. A live revision that differs from the fetched revision is a conflict. A page fetched as missing must still be missing.
2. Parse the new text on the wiki with `action=parse` (`prop=text|templates|categories`). A script error or a missing template blocks the page. A category without a page, or one of the three Erenshor link tracking categories, blocks the page when the live page is not in that category. The live categories are read with the revisions, in the same batches. A write must not make a page worse, but it does not have to repair a red category that an editor added.
3. Write with `safe_edit_page`, whose base revision is the snapshot that equals the fetched revision, or with `safe_create_page`.
4. Checkpoint the manifest after each write. The rollback text is the live text at the fetched revision. Each run keeps its manifest and rollback texts under `variants/<variant>/wiki/article-deploys/<run>/`. After a write, the fetched copy becomes the saved text at the new revision, so a second run without a fetch plans nothing for that page.

The manifest uses the repository-page format with a new `article` upload stage, so `wiki rollback-repo-pages` restores articles with its existing revision check. Conflicts and blocked pages are collected and fail the command at the end. A page whose fetched text has no revision cannot be guarded and is reported as stale. A login, assertion, transport, or retry failure stops the run at once. The guarded writes of the client therefore keep transport failures apart from page failures. The command keeps the client's request pacing and two seconds between writes, and uses the summary `Update game data from build <build>`.

Page normalization sorts the categories at the bottom of the page, removes extra blank lines, and strips line-end spaces. A page that differs from its fetched text only in these ways has no data change. A write would only rearrange the text of the editors. After the zone merge, 34 of the 43 zone pages are such pages.

A dry run reads the live revision of each planned page and writes nothing to the wiki. It groups the planned writes by kind of change: new pages, encounter tiers, field values, links, stable keys, categories, and structure. Generated templates pair by name, entity name, and position. A field value compares with each link replaced by the page that the link catalog gives for it. The change from wikilinks to stable-key templates is therefore a link change, and a removed link is a value change. Generation records the live roots that the merge kept, and the report lists them. The full report goes to `variants/<variant>/wiki/deploy-plan.json`, and a conflict fails the dry run.

Alternative: base the edit on a fresh snapshot, as `deploy-repo-pages` does. Rejected: the text was merged from the fetched revision, so a newer live revision means the merge is stale.

### D6. Drift check for repository pages

Before the first write, `deploy-repo-pages` reads the user of each target's latest revision. A page whose latest revision is by another account and whose text differs from the source is drift, and the deploy stops and names it. `--accept-drift <title>` overwrites one reviewed page. For a hand-written source, the maintainer copies the live text into the repository instead. The check needs no stored state, so it works on every machine.

### D7. Removals

`deploy_from_dir`, `--from-dir`, `--legacy-article-deploy`, `edit_page`, and `PageMetadata.should_deploy` go: D5 decides what to write. The remaining callers of `edit_page`, the image redirects and the Cargo probe, use the guarded writes. An image redirect no longer replaces an existing page. `refresh-embedded --source-table` and its item-owner null edits go: they reparsed item pages that store Cargo rows, and no page does after D2. The deploy-service tests that assert `edit_page` calls are replaced by tests that change the live revision between plan and write.

The migrations of retired templates go as well: the legacy template remover (`Enemy`, `Pet`, `Consumable`, `Weapon`, `Armor`, `Auras`, `Enemy Stats`), the `Fancy-*` templates, and the quality tables of `Item/Weapon` and `Item/Armor`. No fetched page uses them, and a full regeneration without them gives the same bytes.

### D8. Rollout order

1. Generate the Lua data and deploy `Data/Links`, `Data/Spells`, `Data/Skills`, `Data/Stances`, and `Data/Items` with its shards.
2. Render canary pages through TemplateSandbox with the candidate `Template:Character`, and compare the HTML with the live render. Only pages of the Elite tier may differ. Deploy it, `Template:StanceTooltip`, and `Category:Elites`.
3. Fetch, generate, and review the dry-run report with the maintainer. Fix the pages that generation names.
4. Deploy about a dozen canary pages: one per template family, a multi-entity page, a zone page, and an overview. Check them in a browser.
5. Deploy the rest. Fetch again and confirm that every generated page equals its live text after page normalization.

## Risks / Trade-offs

- [About 2,700 edits reach editors' watchlists] → The bot flag hides them from recent changes by default. The maintainer approves the full deploy after the canary.
- [The parse gate doubles the requests] → It runs once per changed page. The full refresh takes about two hours at the current pacing.
- [`Template:Character` is used by about 900 pages, so its edit queues a reparse of each] → The sandbox comparison shows no visible change before the deploy. The reparse runs in the job queue.
- [An editor saves a page during the run] → That page is a conflict. Fetch and generate it again, then deploy it alone.
- [Same-name roots that no field value tells apart need manual work] → Generation names the page and the stable keys. None of the current pages needs it.

## Migration Plan

The code changes land first and change only local output, with a golden review. The live order is D8. Each step has its own manifest. Roll back a step with `wiki rollback-repo-pages --manifest <file>`. Pages created by a step stay and are listed for an administrator.

## Open Questions

None.
