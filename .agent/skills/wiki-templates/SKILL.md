---
name: wiki-templates
description: Fetch, generate, validate, deploy, and roll back Erenshor wiki articles, Lua modules, templates, and interface gadgets. Use when editing or publishing wiki content.
---

# Wiki content workflow

Run commands from the repository root. Use `-V <variant>` on `erenshor` when the target is not `main`.
Keep legacy articles, repository-owned pages, and interface gadgets on their separate deployment paths.

## Legacy generated articles

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
   Generation merges fetched content and runs a local semantic-link audit before reporting success.

3. Review the merge output and the generation warnings.
   A generated root replaces the live root with its `stablekey`, or the live root with its name when the live root has no key.
   Same-name roots pair so that the most field values agree. A merged root takes the generated companion templates.
   A live root that matches no generated entity stays unchanged, and generation lists it as a warning.
   Generation fails a page when equal pairings give different pages. The error names the stable keys to add to the live roots.
   Item `image` and `imagecaption` prefer manual values, and `othersource` is preserved.
   Item `type`, `questsource`, and `relatedquest` merge by link target: a generated link replaces live links to the same page.
   Character `type` comes from the database. Character `zones`, `coordinates`, and `respawn` use database values when present.
   Character `imagecaption` and `location` are preserved. Ability and Stance `image` prefer manual values. Stance `imagecaption` is preserved.
   See `src/erenshor/application/wiki/generators/field_preservation.py` for the other rules.

4. Audit links and preview the intentional legacy deploy:

   ```bash
   uv run erenshor wiki audit-links
   uv run erenshor --dry-run wiki deploy --legacy-article-deploy
   uv run erenshor wiki deploy --legacy-article-deploy
   ```

   `wiki deploy` refuses to run without `--legacy-article-deploy`, even for a dry run.
   Its generated-storage path checks the live semantic-link catalog against the generated catalog.
   If that catalog is stale, deploy repository-owned Lua data first. `--from-dir` bypasses this audit.

## Lua data and repository-owned pages

1. Regenerate database-backed Lua data after clean database changes: `uv run erenshor wiki generate-lua`.
   Data modules are written under `variants/<variant>/wiki/lua/`.
   Keep generated values deterministic and compatible with `mw.loadData()`: strings, numbers, booleans, and tables.

2. Edit maintained Lua modules under `wiki/modules/Erenshor/` and templates under `wiki/templates/`.
   For example, `wiki/modules/Erenshor/Item.lua` maps to `Module:Erenshor/Item`.
   `wiki/templates/Item.wiki` maps to `Template:Item`.
   Keep editor-supplied template parameters effective in the Lua display module.
   Test public `p.<name>(frame)` entry points through the local Scribunto testcases.

3. Select only the pages needed for a live deploy. The default selects maintained Lua modules only.
   Opt in to templates, maintained content pages, and generated data explicitly:

   ```bash
   uv run erenshor --dry-run wiki deploy-repo-pages --include-templates
   uv run erenshor wiki deploy-repo-pages --include-templates
   uv run erenshor wiki deploy-repo-pages --include-generated-data --pages-file pages.txt
   ```

   `--include-generated-data` requires `--pages-file` with exact page titles.
   The `--pages-file` filter also narrows other selected pages. Missing opt-in flags reject requested optional pages.
   Deploy generated data before direct link consumers and Cargo declarations before templates.

4. Keep the deploy manifest and its rollback sidecars. By default, the manifest is written in the selected variant's wiki directory.
   Use `--manifest-output` for a distinct manifest for each deploy you may need to undo.
   Deployment checks source hashes, saves old text, and guards edits with live revisions.
   The default assertion is `bot`. Use `--assert-user <username>` to guard the account identity.
   If a Cargo declaration changes, recreate its table and refresh dependent articles before checking rows.

5. Roll back edits with their exact deployment manifest:

   ```bash
   uv run erenshor --dry-run wiki rollback-repo-pages --manifest <manifest.json>
   uv run erenshor wiki rollback-repo-pages --manifest <manifest.json>
   ```

   Rollback refuses to overwrite later edits unless you pass `--force`.
   Rollback leaves pages created by the deploy in place. Delete them manually if appropriate.

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
   uv run erenshor wiki refresh-embedded --source-table Items
   uv run erenshor wiki refresh-embedded --page 'Example Page'
   ```

   Use at least one `--dependency-title`, `--source-table`, or `--page`.
   A dependency title also requires at least one `--namespace`.
   Use `wiki audit-links` to include live link checks. An error finding exits nonzero.

## Local MediaWiki validation

Use `wiki-dev/` for real parser and Cargo behavior. It uses upstream Cargo, not the live wiki.gg fork.
Run from the repository root in this order:

```bash
wiki-dev/bootstrap.sh
uv run erenshor wiki sync-interface
uv run python wiki-dev/import_pages.py
uv run python wiki-dev/cargo_check.py --recreate
uv run python wiki-dev/null_edit.py
uv run python wiki-dev/cargo_check.py
uv run python wiki-dev/smoke_test.py
```

Recreate Cargo tables when declarations change or on a fresh stack.
The recreate step exits before row checks. Null edits refill and refresh affected article rows.
The smoke harness checks rendered pages through MediaWiki `action=parse`, not raw source-text comparison.
For a regenerated article, copy its text to a temporary `.wiki` file under `wiki-dev/fixtures/pages/`, then reimport.
Check its title through `action=parse` and inspect the parsed HTML. Remove the temporary fixture afterward:

```bash
curl --get 'http://localhost:8088/api.php' --data-urlencode 'action=parse' --data-urlencode 'page=<article title>' --data-urlencode 'prop=text' --data-urlencode 'format=json'
```

Use live TemplateSandbox for the final compatibility check with wiki.gg.

The wiki is moving to Cargo tables populated by bot-owned storage pages. An OpenSpec change will define that workflow.
