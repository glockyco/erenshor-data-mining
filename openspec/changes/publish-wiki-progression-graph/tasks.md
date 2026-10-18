## Publication permission

Do not upload any new Lua module, template, or gadget to the live wiki without explicit user permission for the reviewed deployment plan. Local verification does not authorize publication.

## 1. Data and text view (after `derive-progression-requirements`, design D2 to D4)

- [ ] 1.1 `feat(wiki): build the progression data view`: add `src/erenshor/application/wiki_lua/progression.py` with the `DataView` of D2, the condition wording table, the labels of mechanism, barrier, and state nodes, and the size report, and call it from `generate_lua_data_modules`. Add unit tests with a fake repository for each row type and each failure. Verify: the tests pass, and `uv run erenshor wiki generate-lua` writes `Module:Erenshor/Data/Progression` under its page budget.
- [ ] 1.2 `feat(wiki): render progression as text`: add `wiki/modules/Erenshor/Progression.lua` with `p.render` and a frame entry point, `wiki/templates/Progression graph.wiki` with documentation and an example in `<noinclude>`, the category page `wiki/content/Category/Pages with missing Erenshor progression data.wiki`, Scribunto testcases, and smoke rows. The testcases cover a target by key and by page, several entities on one page, a key without data, a node shown earlier, the depth limit, the legend, and the gadget container. Verify: the testcases and smoke rows pass in the local stack, and with the real data module the Fallen Braxonia page lists its door, the Ancient Braxonian Key, and the milestones before them.
- [ ] 1.3 Measure the explorer page and the heaviest raid route with the real data module in the local stack. Verify: Lua memory and time stay under a quarter of the live limits of 50 MiB and 15 s, and the post-expand include size stays under the wiki's limit. Record the numbers here.
- [ ] 1.4 `docs(wiki): describe the progression graph in the data guide`: add the view, its data module, the meaning of ways, needs, and tiers, and where to report a wrong requirement to `wiki/content/Erenshor Wiki/Game Data.wiki`. Verify: the guide links the template and the module, and `uv run pytest tests/contract` passes.

## 2. Explorer (design D5)

- [ ] 2.1 `feat(wiki): draw the progression graph`: add the pure core (graph model, levels of detail, reversed edges, filters, ordering, search), the DOM module, its stylesheet, and the loader under `wiki/gadgets/`, register `progression-graph` and `progression-graph-loader` in `gadgets.toml`, and add node tests with a `package.json` script that `erenshor test ci` runs. Verify: the node tests pass inside `uv run erenshor test ci`, covering collapsed sources, gate-free entrances, the reversed edges of an item, a filtered edge with its hidden steps, and the tier invariant.
- [ ] 2.2 Check the explorer in the local MediaWiki stack in a browser, with the real data module and the synced interface: search Rune of Elements, show what the Ancient Braxonian Key unlocks, expand The Duskenlight Ritual and the sources of Wolf Meat, filter to quests, reach and focus a node with the keyboard alone, switch the light and dark themes, and block the gadget to see the text stay. Verify: each check passes, and screenshots of the explorer page and of Fallen Braxonia are shown to the maintainer before any deploy.

## 3. Publication (after design D6 holds and after approval)

- [ ] 3.1 Dry-run `wiki deploy-repo-pages --include-templates --include-generated-data --render-check` with a pages file that names `Module:Erenshor/Data/Progression`, `Module:Erenshor/Progression`, its testcases, `Template:Progression graph`, the category page, and `Erenshor Wiki:Game Data`. Read the whole output, ask for approval, deploy, and keep the manifest. Verify: a live parse of a page with the template shows no script error, missing template, or tracking category.
- [ ] 3.2 Dry-run `wiki deploy-interface` for the two gadgets, ask for approval, deploy, and keep the manifest. Verify: a live page with the template draws the graph in a browser and answers the keyboard.
- [ ] 3.3 After the maintainer creates `Progression Graph` with the template, open it on live. Verify: it opens on the four raid planes and searches every node.
- [ ] 3.4 Place the template on the Raid Unlocking Walkthrough as `publish-wiki-data-views` D5 describes: announce it, render it through TemplateSandbox on that page, review it with the maintainer, and write one guarded edit that keeps every other text. Verify: the page renders the graph, its prose is unchanged, and the rollback manifest lists the edit.

## 4. Integration

- [ ] 4.1 Run `uv run erenshor test ci` and `uv run erenshor test wiki --warm`. Verify: both pass.
- [ ] 4.2 Archive the change with `openspec archive publish-wiki-progression-graph --yes`. Verify: `openspec/specs/wiki-progression-graph/spec.md` exists and `openspec validate --specs` passes.
