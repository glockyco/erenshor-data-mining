## 1. Step 0: remove the old plans' code (one commit each)

- [x] 1.1 `refactor(wiki): remove the July override review`: delete `override_classifier.py`, `override_migration.py`, the `wiki review-overrides` command, and their tests, including the review part of `tests/system/wiki/test_wiki_deploy.py`. Verify: `uv run erenshor wiki --help` lists no `review-overrides`, and the unit tests of `wiki_deploy` and the CLI pass.
- [x] 1.2 `refactor(wiki): remove Cargo from the article path`: delete the Cargo declarations and store calls from `Item.wiki`, `Character.wiki`, `Stance.wiki`, `Spell.wiki`, and `Skill.wiki`, the five store templates, the four query templates with their row subpages, `Item/CargoDeclare`, `Item/CargoStore`, `AbilityClasses`, `ArmorTable`, and `WeaponTable` with their rows, `Module:Erenshor/Cargo`, every `cargo*` entry point and its testcases, and `wiki-dev/cargo_check.py` with its fixtures and smoke pages. Verify: no file under `wiki/` contains `#cargo_`, and the touched tests pass.
- [x] 1.3 `refactor(tools): remove the Cargo storage probe`: delete `src/erenshor/tools/wiki_cargo_probe/`, its registration, and its tests. Verify: the unit tests pass, and no file refers to `wiki_cargo_probe`.
- [x] 1.4 `refactor(wiki): reduce the legacy templates to their parameters`: `Stance.wiki`, `Quest.wiki`, `Zone.wiki`, and `MapLink.wiki` equal their live text. `Character.wiki` equals its live parameter branch plus the Elite and Chest tiers. `Item.wiki` equals its live parameter branch. `ItemTooltip.wiki` keeps only the parameter renderer. Delete `Spell.wiki` and `Skill.wiki`. The template documentation describes `stablekey` as identity only. Delete the `wiki-dev` pages that pass `lua=1` and update the harness tests. Add a contract test that the seven legacy templates call no module and contain no `lua` switch and no `#cargo_` (spec: legacy entity templates render only their parameters). Verify: the contract test passes, and the warm local wiki suite passes.
- [ ] 1.5 `refactor(wiki): remove the July renderers and their data`: delete `Module:Erenshor/Item`, `Item/Tooltip`, `Character`, `Quest`, and `Zone` with their testcases. Delete `field`, `status`, and their accessors from the Stance, Spell, and Skill modules, and stop their resolvers from applying article parameters over the data. Delete the Lua data writers for Characters, Quests, and Zones, and keep the repositories that other generators read. The commit message names the last revision that has the removed code. Verify: `uv run erenshor wiki generate-lua` writes only Items and its shards, Links, Skills, Spells, and Stances. The Scribunto testcases pass in the local stack, and a full `uv run erenshor wiki generate` passes.

## 2. Step 0: make deploys safe (one commit each)

- [ ] 2.1 `feat(wiki): check repo-page dependencies before a deploy`: implement design D6. Add tests with a fake wiki: a template whose module loads a missing data module is blocked and named, a module and its new data module in one run pass, modules are written in dependency order, and a dry run reports the same result. Verify: the tests pass, and a dry run against live reports no blocked page.
- [ ] 2.2 `feat(wiki): render repo pages through TemplateSandbox before writing`: implement design D7 with the coverage selection and a full-check option. Add tests with a fake wiki: a new script error blocks the write, a visible change is reported, the selection covers a feature that only one page has, the full option parses every page, and a page without users is reported. Verify: the tests pass, and a dry run against live reports each changed page with its selection.
- [ ] 2.3 `feat(wiki): fail Lua data generation above the page size limit`: implement design D8 with `max_page_bytes` in `[global.mediawiki]`. Add a test with a module over the limit. Verify: the test passes, and `uv run erenshor wiki generate-lua` passes on the current data.

## 3. Step 0: write the plan down (one commit each, except 3.3)

- [ ] 3.1 `docs(openspec): align the refresh and Cargo changes with the plan`: in `refresh-wiki-articles`, replace the `lua=1` parts of proposal and design D2 with the parameter-template rule of this change, delete the requirement "Entity templates select their Lua branch only by `lua=1`" from its spec delta, note on task 1.1 that task 1.4 of this change replaced its selector, and rewrite task 6.2 to deploy every repository page that differs, after the checks of tasks 2.1 and 2.2 and approval. In `publish-wiki-cargo-data`, remove the `lua=1` prerequisite (task 1.2, proposal, design D7), reduce task 7.1 to what this cleanup leaves, and drop the closing of #115 from task 8.4. Verify: `openspec validate --strict` passes for all three changes, and no active artifact describes `lua=1` as current behavior.
- [ ] 3.2 `docs(wiki): describe the plan in the README, the skill, and the OpenSpec config`: the README describes the wiki in a few lines and links this change. Rewrite `.agent/skills/wiki-templates/SKILL.md` to state the binding rules of this design, the current procedures, and the link to this change, without history. Update `wiki-dev/README.md`. Name this change in the context of `openspec/config.yaml`, and replace its dependency-specific design rules with general ones. Verify: `uv run pytest tests/contract/test_document_paths.py` passes, and the skill contains no `lua=1`, `review-overrides`, or article Cargo instruction.
- [ ] 3.3 Close the 19 wiki issues as design D11 lists: each closing comment states the evidence and the OpenSpec place of the remaining work. Leave #91, #105, and #291 open. Verify: `gh issue list --label wiki --state open` lists only #91, #105, and #291.
- [ ] 3.4 `fix(wiki): give every zone category a page under the zone title` (#299): generation keeps the zone page titles as category names. Add category pages for the six missing names and for the four titles that are redirects today, under `wiki/content/Category/`. The old targets (`Elderstone Mines`, `Duskenlight Coast`, `The Bone Pits`, `Loomingwood`) become redirects in task 6.2 of `refresh-wiki-articles`, after their members move. Verify: every zone category that generation emits has a repository page or a live page that is not a redirect.

## 4. Step 0: verify the cleanup

- [ ] 4.1 Run `uv run erenshor test ci` and `uv run erenshor test wiki --warm`. Both pass.
- [ ] 4.2 Run `uv run erenshor wiki generate-lua`, a full `uv run erenshor wiki generate`, and `uv run erenshor --dry-run wiki deploy-repo-pages --include-templates --include-content-pages`. The dry run lists only intended pages, blocks none, and its render check shows no new script error. Review the report together before task 6.2 of `refresh-wiki-articles`.

## 5. Step 1: refresh the stale articles

- [ ] 5.1 Complete tasks 6.2 to 7.1 of `refresh-wiki-articles`. Verify: the change is archived.

## 6. Step 2: publish complete Cargo tables

- [ ] 6.1 The `cargoadmin` grant is enabled for `WoWMuch@InterfaceDeploy` at Special:BotPasswords. Verify: the interface session holds `recreatecargodata`.
- [ ] 6.2 Propose and complete a change that adds code facts and processor mappings for the four open item mechanics of design D11, before task 5.4 of `publish-wiki-cargo-data`. Verify: the clean database holds each mechanic, and the change is archived.
- [ ] 6.3 Complete `publish-wiki-cargo-data`. Verify: the change is archived.

## 7. Step 3: replace the hand-maintained tables

- [ ] 7.1 Propose the change from design D3, step 3. Verify: `openspec validate --strict` passes.
- [ ] 7.2 Complete it. Verify: every table that design D3 lists renders from a query template, and the change is archived.

## 8. Step 4: convert the articles

- [ ] 8.1 Propose the conversion from design D3, step 4, with the template names, the owned-field sets, the tracking category, and the known points of D3. Verify: `openspec validate --strict` passes.
- [ ] 8.2 Convert Stance. Verify: its pages pass the production parse check, and its legacy generator code is deleted.
- [ ] 8.3 Convert spells and skills, with their categories. Same verification.
- [ ] 8.4 Convert zones. Same verification.
- [ ] 8.5 Convert characters. Same verification.
- [ ] 8.6 Convert items, with the item ID. Same verification.
- [ ] 8.7 Delete the merge engine, the Jinja article templates, and the full-article refresh. Verify: a game update in the local stack edits no article whose entities did not change.

## 9. Live pages for an administrator to delete

- [ ] 9.1 `Module:Erenshor/Data/AbilityLinks`, after task 6.2 of `refresh-wiki-articles` deploys `Module:Erenshor/AbilityLink`. Verify: `list=embeddedin` is empty before the deletion.
- [ ] 9.2 `Module:Erenshor/Cargo`, after that deploy removes it from the Spell, Skill, and Stance modules. Same verification.
- [ ] 9.3 `Module:Erenshor/Item`, `Item/Tooltip`, `Character`, `Quest`, and `Zone`, and their live testcases pages, after that deploy. Same verification.
- [ ] 9.4 `Template:Spell`, `Skill`, `ArmorTable`, `WeaponTable`, `AbilityClasses`, the five store and four query templates, and their subpages. Same verification.
- [ ] 9.5 The Cargo tables `Item` and `Consumable` at Special:CargoTables. Verify: Special:CargoTables no longer lists them.
- [ ] 9.6 The six `SpellScroll*` files and `Kingsman_GP.png` (#97, #98), after the five pages that use `SpellScrollPurple.png` or `SpellScrollYellow.png` use the current images, and after a full scan finds no other `*_GP` file in use. Verify: `list=imageusage` is empty before each deletion.

## 10. Close

- [ ] 10.1 Archive this change with `openspec archive adopt-data-backed-wiki --yes` when groups 1 to 9 are done. Verify: `openspec/specs/wiki-publishing/spec.md` exists.
