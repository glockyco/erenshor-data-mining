## 1. Entity templates (commit: `refactor(wiki): select the entity Lua branches by lua=1`)

- [x] 1.1 Change the Lua-branch selector of `wiki/templates/Character.wiki`, `Stance.wiki`, `Quest.wiki`, and `Zone.wiki` to the exact `lua=1` check of `Item.wiki`. Copy the live text of `Template:Ability` into `wiki/templates/Ability.wiki`. Document `stablekey` as an identity parameter in the Character and Stance documentation. Add `lua=1` to the `wiki-dev` fixture pages that render these templates through Lua. Delete the stale copies `wiki/templates/Template_*.txt` after checking that nothing reads them. Verify: `Ability.wiki` equals its live text, the Stance, Quest, and Zone parameter branches equal their live templates, a TemplateSandbox render of Enemy, Boss, and NPC character pages matches the live HTML, a generated Elite page renders the Elite tier and its categories, and `uv run erenshor test wiki --warm` passes.

## 2. Merge by identity (one commit each)

- [x] 2.1 `fix(wiki): merge preserved list fields by link target`: implement design D1 in `field_preservation.py`. Add behaviour tests for the Bag of Faerie Dust case, an editor-only link, plain text, and the `link=` and wikilink forms. Verify: a regenerated corpus has no merged field that links one page twice (228 pages today).
- [ ] 2.2 `fix(wiki): list each source once per page and label`: implement design D1a in the section generators. Add tests for the three Highwayman Raider variants, variants with different chances, and the Fire and Ice guards. Verify: a regenerated corpus has no list field that repeats a page and label pair (130 `source` fields today).
- [ ] 2.3 `fix(wiki): match preserved fields by stable key`: emit `stablekey` on `Character`, `Ability`, and `Stance` roots. Match roots by key, then by name, fail the page for ambiguous same-name roots with preserved values, and keep and list unmatched live roots. Add tests for reordered, added, and removed entities, an editor-added root, and the ambiguous case. Verify: regeneration keeps the Braxonian Chest infobox on Frost and lists the 15 pages with unmatched roots.

## 3. Generator fixes (one commit each)

- [ ] 3.1 `fix(wiki): refresh stance pages from data`: add `Stance` to the merged families with design D4 rules. Verify with a test that a changed stance modifier reaches the page.
- [ ] 3.2 `fix(wiki): merge zone pages into the live page`: write zone pages to the generated storage, merge them with the fetched page, and delete `wiki/zones/` and the zone output directory. Replace `tests/unit/application/wiki/generators/test_zone_preservation.py` with tests that keep live prose. Verify: generation produces all 43 zone pages, and each keeps the prose of its fetched page.
- [ ] 3.3 `fix(wiki): replace only the generated overview table`: implement design D4 for `Weapons` and `Armor`. Add tests with an introduction, a trailing notes section, a second table, and a page without the generated table. Verify: the regenerated `Armor` page keeps the text around its table.
- [ ] 3.4 `fix(wiki): keep fractional skill cooldowns`: use one duration formatter in the legacy skill section and the Lua skill data. Add a test for 800 ticks shown as 13.33 seconds. Verify in game with HotRepl (`uv run erenshor eval`) that a used skill's hotkey cooldown starts at its tick value and falls by about 60 per second.

## 4. Guarded deploys (one commit each)

- [ ] 4.1 `feat(wiki): write articles only from their fetched revision`: implement design D5 steps 1, 3, and 4 and the failure handling. Add the `article` upload stage to the manifest. Remove `deploy_from_dir`, `--from-dir`, `--legacy-article-deploy`, `edit_page`, and `PageMetadata.should_deploy`. Replace the deploy-service tests that assert `edit_page` calls with tests that change the live revision between plan and write, delete a page, and lose the session. Verify: the tests pass, and `wiki rollback-repo-pages` restores an article manifest in a test.
- [ ] 4.2 `feat(wiki): parse each article on the wiki before writing it`: implement design D5 step 2. Add tests for a script error, a missing template, a category without a page, and a new tracking category. Verify: a test page with `[[Category:Elites]]` is blocked while the category page is missing.
- [ ] 4.3 `feat(wiki): report the article deploy plan`: make `erenshor --dry-run wiki deploy` list the planned pages by kind of change, the unmatched roots, and the conflicts. Verify: a dry run against live reports the 113 tier changes and writes nothing.
- [ ] 4.4 `feat(wiki): stop repo-page deploys at another account's edit`: implement design D6 with `--accept-drift`. Add tests for a reverted template, an accepted page, and a page whose live text equals the source. Verify: a dry run of `wiki deploy-repo-pages --include-templates` names every drifted template.
- [ ] 4.5 `refactor(wiki): remove the source-table refresh`: delete `--source-table` and the item-owner null edits from `refresh-embedded`. Verify: `uv run erenshor wiki refresh-embedded --help` no longer offers it, and the remaining refresh tests pass.

## 5. Documentation and verification

- [ ] 5.1 `docs(skills): describe the guarded article refresh`: update `.agent/skills/wiki-templates/SKILL.md` for the new deploy, its gates, the review report, rollback, and the drift check. Remove the known-defect note. Verify: `uv run pytest tests/contract/test_document_paths.py` passes.
- [ ] 5.2 Run `uv run erenshor test ci` and, with the local MediaWiki stack, `uv run erenshor test wiki --warm`. Both pass.
- [ ] 5.3 Run `uv run erenshor golden capture`. Show the diff to the maintainer and commit it only after approval (`test(golden): refresh the wiki baselines for merged identity`).

## 6. Live refresh

- [ ] 6.1 Run `uv run erenshor wiki generate-lua`, then deploy `Module:Erenshor/Data/Links`, `Data/Spells`, `Data/Skills`, `Data/Stances`, `Data/Items`, and the item shards with `wiki deploy-repo-pages --include-generated-data --pages-file <titles>`. Verify: a dry run first, then the live text of each module equals its generated file, and `{{StanceTooltip|stablekey=stance:aggressive}}` parses without an error.
- [ ] 6.2 Add `wiki/content/Category/Elites.wiki`. Deploy it, `Template:Character`, and `Template:StanceTooltip` with `wiki deploy-repo-pages --include-templates --include-content-pages`. Verify: a dry run shows no drift, and the canary pages of task 1.1 render as the sandbox showed.
- [ ] 6.3 Run `uv run erenshor wiki fetch --force`, `uv run erenshor wiki generate`, and `uv run erenshor --dry-run wiki deploy`. Fix every page that generation names. Show the report to the maintainer and get the go-ahead for the canary.
- [ ] 6.4 Deploy the canary pages with `wiki deploy --pages-file <canaries>`. Check each in a browser: infobox, tooltips, links, categories, and preserved prose.
- [ ] 6.5 After the maintainer approves, deploy the remaining pages. Verify: a new fetch and generation show no difference between generated and live pages, `Category:Pages with script errors` is empty, and the Erenshor link tracking categories did not grow.

## 7. Close

- [ ] 7.1 Archive the change with `openspec archive refresh-wiki-articles --yes` after the live refresh and all checks pass.
