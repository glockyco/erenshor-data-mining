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
- **BREAKING**: `Template:Item`, `Character`, `Ability`, `Stance`, `Quest`, `Zone`, and `MapLink` become plain parameter templates. They call no module, have no `lua=1` switch, and store no Cargo row. `stablekey` identifies an entity and does not change the rendering. `Template:Character` keeps the Elite and Chest tiers that the refresh needs. After this cleanup, these templates do not change again.
- **BREAKING**: These parts of the old plans are removed:
  - The article Cargo path: declarations and stores in templates, the store and query templates, `ArmorTable`, `WeaponTable`, `AbilityClasses`, `Module:Erenshor/Cargo`, the `cargoStore` entry points, and the local article-row checks.
  - The templates `Spell` and `Skill`, the data path of `Template:ItemTooltip`, and the modules `Module:Erenshor/Item` and `Item/Tooltip`. No live page uses them: all 793 item tooltips render from their own parameters.
  - The infobox entry points (`field`, `status`) of the Stance, Spell, and Skill modules. Their resolvers stop applying article parameters over the data, because no caller passes one.
  - The Character, Quest, and Zone renderers and their data modules `Data/Characters`, `Data/Quests`, and `Data/Zones`.
  - `override_classifier.py`, `override_migration.py`, and `wiki review-overrides`.
  - The Cargo storage probe.
  - The local test pages that pass `lua=1`.
  The Spell, Skill, Stance, and item tooltips and the semantic links keep working. The conversion of step 4 builds the new renderers and can reuse removed code from the history.
- `wiki deploy-repo-pages` refuses a module or template whose required modules are neither live nor written earlier in the same run. Before it writes a module or template that live pages use, it renders those pages through TemplateSandbox: by default a selection that covers every template, filled parameter, `type` or `kind` value, and entity kind among them, and on request every page. A new script error blocks the write. The dry run lists every visible change for review.
- `wiki generate-lua` fails when a data module is larger than the wiki's page size limit.
- The README, the wiki skill, `wiki-dev/README.md`, the template documentation, `openspec/config.yaml`, and both active wiki changes describe only the current plan.
- Each of the 19 open wiki issues is checked against the current code, data, and live wiki. Verified open work moves into this change or into the change that owns it. Each issue is then closed with a link to its new place or with the evidence that it is stale.
- A task group of this change lists the live pages that only an administrator can delete, each with the condition for its deletion.

## Capabilities

### New Capabilities

- `wiki-publishing`: who owns each kind of wiki page and input, how generated data reaches the wiki, what the legacy templates may do, and the checks a repository-page deploy runs before it writes.

### Modified Capabilities

None. The `lua=1` requirement of `refresh-wiki-articles` is corrected inside that change, which is not archived yet.

## Impact

- Code: `wiki/templates/`, `wiki/modules/Erenshor/`, `src/erenshor/application/wiki_lua/`, `src/erenshor/application/wiki_deploy/`, `src/erenshor/cli/commands/wiki.py`, `src/erenshor/tools/wiki_cargo_probe/`, `wiki-dev/`, `config.toml`, and their tests.
- Live wiki: task 6.2 of `refresh-wiki-articles` deploys the cleaned pages, among them `Template:Character`, `Template:Item`, and `Template:ItemTooltip`, after a dry run, the render check, and approval. The pages that then have no user go on the deletion list of this change.
- Other changes: `refresh-wiki-articles` loses the `lua=1` lock, and its task 6.2 deploys every cleaned page that differs. `publish-wiki-cargo-data` loses its `lua=1` prerequisite and its article-path removal, which this cleanup does.
- GitHub: the 19 open wiki issues are closed after their verified work moves into OpenSpec. Issues of other areas stay open.
- Migration boundary: the cleanup lands before task 6.2 of `refresh-wiki-articles`. Every live write needs approval after a dry run and the render check.
- Non-goals: the work of steps 1 to 4, which their own changes do. The names of the new data-backed templates, which the conversion change decides. A redesign of the main page, which this plan lists as later wiki work.
