---
name: wiki-templates
description: Fetch, generate, validate, deploy, and roll back Erenshor wiki articles, Lua modules, templates, and interface gadgets. Use when editing or publishing wiki content.
---

# Wiki content workflow

Run commands from the repository root. Use `-V <variant>` on `erenshor` when the target is not `main`.
Keep generated articles, repository-owned pages, and interface gadgets on their separate deployment paths.

## Rules

The plan for the wiki is the OpenSpec change `adopt-data-backed-wiki`. Read its `design.md` before any wiki change. Older plans, issues, and notes do not count.

- Track wiki work only in OpenSpec. Do not open GitHub issues for wiki work.
- The legacy templates `Item`, `Character`, `Ability`, `Stance`, `Quest`, `Zone`, and `MapLink` render only their parameters. They call no module and store no Cargo row. Do not add a Lua branch or a `lua=1` switch. `stablekey` is an identity, never a switch.
- Data-backed rendering comes with new templates in step 4 of the plan, not with changes to the legacy templates.
- Generated data lives on bot-owned pages: `Module:Erenshor/Data/*` and, with the Cargo work, `Erenshor Wiki:Cargo/*`. Articles do not store Cargo rows.
- A fact the export misses goes into code facts or the export. A correction of how the export is read goes into `mapping.json` with a reason. A fact that editors add goes into a Cargo community row. Article parameters only present fields that people own.
- Do not change the structure of a live data module in place. Publish the new structure under a new title, move the readers, then remove the old page.
- Every live write needs approval after a dry run and the render check. The bot cannot delete pages. The plan's task group 9 lists the pages for an administrator.

## Generated articles

1. Fetch existing articles before generation so manual fields survive: `uv run erenshor wiki fetch`.
   Use `--pages-file pages.txt` to fetch only named pages.
   `--pages-file -` reads titles from stdin. A title file has one title per line.
   Fetch compares saved and live revisions. Use `--force` to download unchanged pages again.
   Fetched pages go to `variants/<variant>/wiki/fetched/`.

2. Generate articles from the clean database and inspect the generated text:

   ```bash
   uv run erenshor wiki generate
   uv run erenshor wiki generate --pages-file pages.txt
   ```

   Generated pages go to `variants/<variant>/wiki/generated/`.
   Generation merges fetched content, then validates every page of the run: page structure, stable keys, preserved fields, categories, and semantic links.
   A validation finding fails the run, and the command prints the first findings. The offline link audit goes to `variants/<variant>/wiki/link-audit.json`.

3. Review the merge output and the generation warnings.
   A generated root replaces the live root with its `stablekey`, or the live root with its name when the live root has no key.
   Same-name roots pair so that the most field values agree. A merged root takes the generated companion templates.
   A live root that matches no generated entity stays unchanged. Generation lists it as a warning and records it for the deploy review.
   Generation fails a page when equal pairings give different pages. The error names the stable keys to add to the live roots.
   Generation owns item icons, which the tooltip templates show. Item `othersource` is preserved.
   Item `type`, `questsource`, and `relatedquest` merge by link target: a generated link replaces live links to the same page.
   Character `type` comes from the database. Character `zones`, `coordinates`, and `respawn` use database values when present.
   Character `imagecaption` and `location` are preserved. Ability `image` prefers manual values. Generation owns the Character and Stance `image`, and Stance `imagecaption` is preserved.
   Character infoboxes carry `imagefile`, the bare title of the image that the page shows, so that a missing file puts the page into a hidden `Needs Image` category. Infoboxes of summoned creatures also carry `imagekind=summon`. Item, spell, skill, and stance icons come from the game's icon export, so their infoboxes check nothing.
   Zone pages merge in the same way. Each `Zone` field other than `title` keeps its live value when that value is not blank.
   Generated zone values fill new pages and blank fields only.
   On `Weapons` and `Armor`, generation replaces only the table whose header row equals the generated header.
   Header cells compare by kind and text, not by attributes. Generation fails the page when no table or several tables match.
   See `src/erenshor/application/wiki/generators/field_preservation.py` for the other rules.

4. Audit links, review the deploy plan, and deploy:

   ```bash
   uv run erenshor wiki audit-links
   uv run erenshor --dry-run wiki deploy
   uv run erenshor wiki deploy --pages-file canaries.txt
   uv run erenshor wiki deploy
   ```

   `wiki audit-links` fails when a generated link points to an item, ability, character, or zone article that is neither live nor in the deploy.
   People write the quest, faction, and class articles. A generated link to such an article that does not exist is a red link.
   The audit lists it as the warning `missing_manual_target_article`, so that a contributor can write the article.

   A dry run writes nothing to the wiki. It groups the planned writes by kind of change: new pages, encounter tiers, field values, links, stable keys, categories, and structure.
   Field values compare with link syntax ignored. A value whose links reach the same pages through other syntax is a link change.
   The dry run lists each encounter tier change, each live root that generation kept, and each conflict. It fails when a page is a conflict.
   It saves the full report to `variants/<variant>/wiki/deploy-plan.json`.
   `wiki deploy` writes an article only while its live page is still at the fetched revision.
   A page that changed or was deleted after the fetch is a conflict. Fetch and generate it again.
   A page that differs from its fetched text only by page normalization is not written.
   Before each write, the deploy parses the new text on the wiki. A script error or a missing template blocks the page.
   A new category without a page or a new Erenshor link tracking category also blocks it.
   Before it writes, the deploy checks the live semantic-link catalog. If that catalog is stale, deploy repository-owned Lua data first.
   Each run writes a manifest and rollback text under `variants/<variant>/wiki/article-deploys/<run>/`.
   Restore a run with `uv run erenshor wiki rollback-repo-pages --manifest <manifest>`.
   The command fails when a page is a conflict or blocked, or when the run stops early.
   Before the first write, the manifest lists every planned page with its base revision. Each written page gets its new revision, and a rollback restores only those pages.

## Lua data and repository-owned pages

1. Regenerate database-backed Lua data after clean database changes: `uv run erenshor wiki generate-lua`.
   Data modules are written under `variants/<variant>/wiki/lua/`.
   Keep generated values deterministic and compatible with `mw.loadData()`: strings, numbers, booleans, and tables.

2. Edit maintained Lua modules under `wiki/modules/Erenshor/` and templates under `wiki/templates/`.
   For example, `wiki/modules/Erenshor/Link.lua` maps to `Module:Erenshor/Link`.
   `wiki/templates/Item.wiki` maps to `Template:Item`.
   A template's CSS goes in a TemplateStyles stylesheet: `wiki/templates/Character/styles.css` maps to `Template:Character/styles.css` with the `sanitized-css` content model, and the template loads it with `<templatestyles src="Template:Character/styles.css" />`.
   The deploy treats the stylesheet as a dependency of the template, like an `#invoke` module: it writes the stylesheet first and stops a template whose stylesheet is missing.
   The legacy entity templates render from article parameters.
   Spell, Skill, and Stance tooltips read generated data by stable key.
   Test public Lua entry points through the local Scribunto testcases.

3. Select only the pages needed for a live deploy. The default selects maintained Lua modules only.
   Opt in to templates, maintained content pages, and generated data explicitly:

   ```bash
   uv run erenshor --dry-run wiki deploy-repo-pages --include-templates
   uv run erenshor wiki deploy-repo-pages --include-templates
   uv run erenshor wiki deploy-repo-pages --include-generated-data --pages-file pages.txt
   ```

   `--include-generated-data` requires `--pages-file` with exact page titles.
   The `--pages-file` filter also narrows other selected pages. Missing opt-in flags reject requested optional pages.
   Generated data deploys before the modules that read it, modules deploy in dependency order, then templates, then content pages.
   Before any write, the deploy checks dependencies: a module or template whose `#invoke`, `require`, or `mw.loadData` target is neither live nor written earlier in the run is blocked, and the output names both pages.
   Before each module or template write, the render check parses pages that use it twice through `action=parse`, once as live and once with the new text through TemplateSandbox.
   By default it selects pages that cover every template, filled parameter, `type` or `kind` value, and entity kind among the users. `--full-render-check` parses every user page.
   A new script error or missing template blocks the write. The dry run lists every page whose visible text or categories change. Review that list before approving the deploy.
   In a dry run, a page that depends on another page of the same run shows a provisional result. The real deploy checks it again directly before its write.
   Before the first write, the deploy stops when another account made the latest revision of a page whose live text differs from the repository.
   The bot edits as the account part of `bot_username`, so edits by your own main account count as another account.
   A dry run reads the live pages, counts the planned changes, and names each such page. Review each one.
   Copy live text that the repository should keep into the source file. Pass `--accept-drift <title>` for a page to overwrite.

4. Keep the deploy manifest and its rollback sidecars. Each deploy writes them to a new `repo-page-deploys/<UTC time>-<id>/` directory in the selected variant's wiki directory.
   Pass that run's `manifest.json` to `wiki rollback-repo-pages --manifest` to undo the deploy. `--manifest-output` chooses another path.
   Deployment checks source hashes, saves old text, and guards edits with live revisions.
   The default assertion is `bot`. Use `--assert-user <username>` to guard the account identity.

5. Roll back edits with their exact deployment manifest:

   ```bash
   uv run erenshor --dry-run wiki rollback-repo-pages --manifest <manifest.json>
   uv run erenshor wiki rollback-repo-pages --manifest <manifest.json>
   ```

   Rollback refuses to overwrite later edits unless you pass `--force`.
   Rollback leaves pages created by the deploy in place. Delete them manually if appropriate.

## Removed, renamed, and unused content

`content-lifecycle.json` records what happened to content that a wiki page still names. `openspec/specs/wiki-content-lifecycle/spec.md` holds the rules.

- `pages` gives a page the state `removed`, `unobtainable`, or `unused`, with its `source` evidence. Generation shows the notice of `Template:Historical Content` on that page. The notice of an unused page also says that simulated players can name it in chat when its knowledge entry has a zone. The file holds no chat flag: the retired-page commands read it from the clean database.
- `renames` sends an old title to the current title of the same stable key. `apply-retired-pages` writes the redirect.
- `splits` lists the current titles of one old page. `apply-retired-pages` writes a disambiguation page.

1. After a game update, run `uv run erenshor wiki audit-retired-pages`. It lists each live page that WoWBot created and generation no longer writes. An unexplained page, one with no record, makes it fail. A pending page has a record that is not live yet.
2. Record each unexplained page in `content-lifecycle.json`. Use the renamed copies of `skill://auditing-spawn-coverage` for characters. Never record a state that the game files do not show.
3. Run `uv run erenshor --dry-run wiki apply-retired-pages`, review each planned notice, redirect, and disambiguation page, and apply them only after approval. Each run keeps a rollback manifest in `retired-page-deploys/` in the variant's wiki directory.

## One-time edits of text that people own

Generation never rewrites prose or templates outside the generated roots. When such text is wrong, or when a page must give up a legacy template before generation can add its root, write a reviewed one-time edit.

1. Write a TOML file under the variant's wiki directory, never in the repository, because it quotes text that people wrote. Each `[[pages]]` entry has a `title`, an edit `summary`, and one or more `[[pages.replace]]` entries with the exact `old` live text and its `new` text.
2. Run `uv run erenshor --dry-run wiki apply-page-edits <file>`. Each `old` text must occur exactly once on the live page. The dry run prints a diff for each page and parses the new text: a script error, a missing template, or a new category without a page blocks the run.
3. Apply it only after approval: `uv run erenshor wiki apply-page-edits <file>`. Each write is guarded by the revision that the run read, and the run keeps a rollback manifest in `page-edit-deploys/` in the variant's wiki directory. Restore it with `wiki rollback-repo-pages --manifest`.

## Interface gadgets and dependent pages

1. Sync live `MediaWiki:` pages into the local preview before importing: `uv run erenshor wiki sync-interface`.
   Maintain gadget sources and registration in `wiki/gadgets/gadgets.toml`.

2. Set dedicated interface-admin credentials in the local configuration before a production deploy.
   The content bot cannot edit `MediaWiki:` pages. Preview, deploy, or restore gadget source pages:

   ```bash
   uv run erenshor --dry-run wiki deploy-interface
   uv run erenshor wiki deploy-interface
   uv run erenshor wiki rollback-interface
   ```

   `deploy-interface` records its own manifest under `output/wiki-interface/`.
   Rollback checks revisions and leaves newly created interface pages in place.

3. After a module or template change, refresh pages that embed it:

   ```bash
   uv run erenshor wiki refresh-embedded --dependency-title Template:Item --namespace 0
   uv run erenshor wiki refresh-embedded --page 'Example Page'
   ```

   Use at least one `--dependency-title` or `--page`.
   A dependency title also requires at least one `--namespace`.
   Use `wiki audit-links` to include live link checks. An error finding exits nonzero.

## Local MediaWiki validation

Use `wiki-dev/` to check the rendered pages through MediaWiki `action=parse`.
Run these commands from the repository root:

```bash
wiki-dev/bootstrap.sh
uv run erenshor wiki sync-interface
uv run python wiki-dev/import_pages.py
uv run python wiki-dev/null_edit.py
uv run python wiki-dev/smoke_test.py
```

Null edits refresh fixture pages after a module or template change.
The smoke harness checks rendered pages through MediaWiki `action=parse`, not raw source text.
For a regenerated article, copy its text to a temporary `.wiki` file under `wiki-dev/fixtures/pages/`, then reimport.
Check its title through `action=parse` and inspect the parsed HTML. Remove the temporary fixture afterward:

```bash
curl --get 'http://localhost:8088/api.php' --data-urlencode 'action=parse' --data-urlencode 'page=<article title>' --data-urlencode 'prop=text' --data-urlencode 'format=json'
```

Use the live render check of `wiki deploy-repo-pages` for the final compatibility check with wiki.gg. The local stack holds every generated data module, so it cannot show a module that is missing live.
