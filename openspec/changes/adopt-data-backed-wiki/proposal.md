## Why

Three plans for the wiki exist side by side. The July plan switched the legacy templates to Lua with `lua=1`, stored Cargo rows from articles, and kept every value that differs from the data as an override. The August plan staged a Cargo cutover. The plan decided on 2026-10-03 replaces both, but no artifact states it completely. Code, live pages, old GitHub issues, and both active wiki changes still repeat the old plans, so work keeps returning to them. The repository also holds pages that break live pages when they are deployed: WoWMuch reverted the Lua `Template:MapLink` twice, and the same text still waits in `wiki/templates/`.

This change writes the whole plan down in one place, removes everything that serves the old plans, and adds the checks that make a full deploy safe. The correct way then is also the easy way.

## What Changes

- This change holds the plan for the data-backed wiki: the target, the ownership rules, the order of the steps, and the wiki work that has not started yet. OpenSpec is the only tracker for wiki work. This change stays open until the last step is done.
  0. Clean up: this change's own tasks.
  1. Refresh the stale articles: `refresh-wiki-articles`.
  2. Publish complete Cargo tables: `publish-wiki-cargo-data`.
  3. Replace the hand-maintained tables with Cargo query templates: a change that this plan proposes when step 2 is done.
  4. Convert the articles to new data-backed templates, one type at a time: a change that this plan proposes when step 3 is done.
- **BREAKING**: `Template:Item`, `Character`, `Ability`, `Stance`, `Quest`, `Zone`, and `MapLink` become plain parameter templates. They call no module, have no `lua=1` switch, and store no Cargo row. `stablekey` identifies an entity and does not change the rendering. `Template:Character` keeps the Elite and Chest tiers that the refresh needs. After this cleanup, these templates change only in compatible ways: they never lose or rename a parameter.
- **BREAKING**: These parts of the old plans are removed:
  - The article Cargo path: declarations and stores in templates, the store and query templates, `ArmorTable`, `WeaponTable`, `AbilityClasses`, `Module:Erenshor/Cargo`, the `cargoStore` entry points, and the local article-row checks.
  - The templates `Spell` and `Skill`, the data path of `Template:ItemTooltip`, and the modules `Module:Erenshor/Item` and `Item/Tooltip`. No live page uses them: all 793 item tooltips render from their own parameters.
  - The infobox entry points (`field`, `status`) of the Stance, Spell, and Skill modules. Their resolvers stop applying article parameters over the data, because no caller passes one.
  - The Character, Quest, and Zone renderers and their data modules `Data/Characters`, `Data/Quests`, and `Data/Zones`.
  - `override_classifier.py`, `override_migration.py`, and `wiki review-overrides`.
  - The Cargo storage probe.
  - The local test pages that pass `lua=1`.
  - `wiki inventory-templates` and `wiki/ownership.yml`, the July cutover inventory.
  - The repository copies of pages that people own: the main page and its stylesheet, the sidebar, `Raids`, `Zones`, the mechanics pages with two unpublished drafts, and their images.
  The Spell, Skill, Stance, and item tooltips and the semantic links keep working. The conversion of step 4 builds the new renderers and can reuse removed code from the history.
- `wiki deploy-repo-pages` refuses a module or template whose required modules are neither live nor written earlier in the same run. Before it writes a module or template that live pages use, it renders those pages through TemplateSandbox: by default a selection that covers every template, filled parameter, `type` or `kind` value, and entity kind among them, and on request every page. A new script error blocks the write. The dry run lists every visible change for review.
- `wiki generate-lua` fails when a data module is larger than the wiki's page size limit.
- The README, the wiki skill, `wiki-dev/README.md`, the template documentation, `openspec/config.yaml`, and both active wiki changes describe only the current plan.
- Each of the 19 open wiki issues is checked against the current code, data, and live wiki. Verified open work moves into this change or into the change that owns it. Each issue is then closed with a link to its new place or with the evidence that it is stale.
- A task group of this change lists the live pages that only an administrator can delete, each with the condition for its deletion.
- Contributors get one entry point. `Erenshor Wiki:Community Portal`, owned by people, links getting started, rules, tasks, discussion, the administrators, and the data guide. `Erenshor Wiki:Game Data`, owned by the repository, explains how game data reaches the wiki, which build is live, who owns which pages, which fields keep an editor's value, and how to report wrong data. Checks keep the guide's field table equal to the generator's rules, and the build comes from a generated data module. Both land before the article canary of the refresh.
- Every file under `wiki/` is a page source that a deploy command writes. A check fails on any other file.

## Capabilities

### New Capabilities

- `wiki-publishing`: who owns each kind of wiki page and input, how generated data reaches the wiki, what the legacy templates may do, and the checks a repository-page deploy runs before it writes.

### Modified Capabilities

None. The `lua=1` requirement of `refresh-wiki-articles` is corrected inside that change, which is not archived yet.

## Impact

- Code: `wiki/`, `src/erenshor/application/wiki_lua/`, `src/erenshor/application/wiki_deploy/`, `src/erenshor/application/wiki_inventory/`, `src/erenshor/cli/commands/wiki.py`, `src/erenshor/tools/wiki_cargo_probe/`, `src/tools/`, `wiki-dev/`, `config.toml`, and their tests.
- Live wiki: task 6.2 of `refresh-wiki-articles` deploys the cleaned pages, among them `Template:Character`, `Template:Item`, and `Template:ItemTooltip`, after a dry run, the render check, and approval. The data guide, `Module:Erenshor/Data/Build`, and a shorter `User:WoWBot` deploy the same way. WoWMuch creates the community portal and edits the sidebar and the main page. The pages that then have no user go on the deletion list of this change.
- Other changes: `refresh-wiki-articles` loses the `lua=1` lock, its task 6.2 deploys every cleaned page that differs, and its canary waits for the contributor pages. `publish-wiki-cargo-data` loses its `lua=1` prerequisite and its article-path removal, which this cleanup does, and its Cargo hub becomes a child of the data guide.
- GitHub: the 19 open wiki issues are closed after their verified work moves into OpenSpec. Issues of other areas stay open.
- Migration boundary: the cleanup lands before task 6.2 of `refresh-wiki-articles`, and the contributor pages before its task 6.4. Every live write needs approval after a dry run and the render check.
- Non-goals: the work of steps 1 to 4, which their own changes do. The names of the new data-backed templates, which the conversion change decides. A redesign of the main page, the wiki rules, and a style guide, which belong to the people who own those pages.
