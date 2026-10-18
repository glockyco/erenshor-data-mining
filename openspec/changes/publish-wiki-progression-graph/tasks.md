## Publication permission

Do not upload any new Lua module, template, or gadget to the live wiki without explicit user permission for the reviewed deployment plan. Local verification does not authorize publication.

## 1. Facts that only the guide held (one commit each, design D11)

- [ ] 1.1 `feat(export): record the Jaws of Sivakaya entry condition`: find the script that opens `zoneline:duskenlight:jaws:989.40:148.67:53.90`, record its condition in the scripted activator export or as a code fact, and project it into `gate_conditions`. Verify: after `extract build`, the line has a gate whose groups need the Nighthollow Candle held or She Sees You done, the export and processor tests pass, and a regression test fails without the projection.
- [ ] 1.2 `feat(export): record the gate before Vessel Siraethe`: record the activation that keeps `character:siraethe` away until A Pious Guest is done. Verify: after `extract build`, `gate_conditions` holds a character or spawn-point gate on Vessel Siraethe with `quest_done quest:jawspiety`, and a regression test covers it.
- [ ] 1.3 `feat(export): record the angel statue before Shivering Tomb (2)`: record `ShiveringAngel`, which clears the statue when Stand, Angel! is done, as the activation of `zoneline:shiveringstep:shiveringtomb2:809.72:19.36:645.26`. Verify: after `extract build`, the line has a `quest_done quest:standangel` gate, and a regression test covers it.
- [ ] 1.4 `fix(pipeline): gate the planning portals on the planning desk`: give every planning-slot zone line the activation of `PlanningDesk`, which the clean build already applies to the table's Box of Portals as `ui_access`. Verify: after `extract build`, each of the 40 planning-slot lines needs `quest_done quest:claimreliquary` in a gate of its own, and a regression test covers one dedicated and one rune slot.
- [ ] 1.5 `feat(code-facts): record the Dimensional Rift scene switch`: add an assert code fact for the `Dimensional Rift` case of `SpellVessel` (lines 2261 to 2275) and a clean relation from it: casting the spell in `Azynthi` leads to `AzynthiClear` and back, with the items whose click effect casts it. Verify: `extract code-facts` reports the fact `ok`, the clean database holds both directions with the Azynthian Riftstone, and a processor test covers the relation.
- [ ] 1.6 Hand the four overrides that 1.1 to 1.4 cover to an Adventure Guide change, which removes them from `quest_guides/graph_overrides.toml` and regenerates `quest-guide.json` in its own session. Verify: the hand-off names each override, its clean gate, and the guide tests that the guide change must run.

## 2. Progression data (design D2 to D8)

- [ ] 2.1 `feat(wiki): build the progression graph data view`: add `src/erenshor/application/wiki_lua/progression.py` with the `DataView` of D8, the relation mapping of D4, the quest rule of D5, the release rule of D6, the exclusions of D7, the mechanism and state labels, and the expansion limit of D3. Add unit tests with fake repositories for each relation family and for each failure: an unmapped acquisition kind, completion method, gate atom kind, and release mechanism, an unresolved key, and a subject above the expansion limit. Verify: the tests pass and each failure names the node, the way, and the fact.
- [ ] 2.2 `feat(wiki): generate the progression graph module`: call the builder from `generate_lua_data_modules`, accept entity keys from the link and native identity catalogs, and report the module and JSON sizes. Add data tests on the main build for every scenario of the `wiki-progression-graph` spec that names game content. Verify: `uv run erenshor wiki generate-lua` writes `Module:Erenshor/Data/Progression` under its page budget, and the data tests pass against the owned clean database.

## 3. Text rendering (design D9)

- [ ] 3.1 `feat(wiki): render the progression graph view`: add `wiki/modules/Erenshor/Progression.lua` with `p.render` and a frame entry point, `wiki/templates/Progression graph.wiki` with documentation and an example in `<noinclude>`, the category page `wiki/content/Category/Pages with missing Erenshor progression data.wiki`, Scribunto testcases, and smoke rows. The testcases cover a target by key and by page, several entities on one page, a key without data, a node shown earlier, the depth limit, the legend, and the gadget container. Verify: the testcases and the smoke rows pass in the local stack, and with the real data module the Fallen Braxonia page lists Braxonian Desert and the Ancient Braxonian Key.
- [ ] 3.2 Measure the explorer page, the template without a target, with the real data module in the local stack. Verify: its Lua memory and time stay under a quarter of the live limits of 50 MiB and 15 s, and its post-expand include size stays under the wiki's limit. Record the numbers here.
- [ ] 3.3 `docs(wiki): describe the progression graph in the data guide`: add the view, its data module, the meaning of ways and needs, and where to report a missing relation to `wiki/content/Erenshor Wiki/Game Data.wiki`. Verify: the guide links the template and the module, and `uv run pytest tests/contract` passes.

## 4. Explorer gadget (design D10)

- [ ] 4.1 `feat(wiki): draw the progression graph`: add the pure core (graph model, reversed edges, expansion by relation, layering, ordering, search), the DOM module, its stylesheet, and the loader under `wiki/gadgets/`, register `progression-graph` and `progression-graph-loader` in `gadgets.toml`, and add node tests with a `package.json` script that CI runs. Verify: the node tests pass inside `uv run erenshor test ci`, including collapsed sources beyond the first four, gate-free entrances, a cycle, and the reversed edges of an item.
- [ ] 4.2 Check the explorer in the local MediaWiki stack in a browser, with the real data module and the synced interface: search Rune of Elements, show what the Ancient Braxonian Key unlocks, expand the collapsed sources of Wolf Meat, reach and focus a node with the keyboard alone, switch the light and dark themes, and block the gadget to see the lists stay. Verify: each check passes, and screenshots of the explorer page and of Fallen Braxonia are shown to the maintainer before any deploy.

## 5. Publication (after approval)

- [ ] 5.1 Dry-run `wiki deploy-repo-pages --include-templates --include-generated-data --render-check` with a pages file that names `Module:Erenshor/Data/Progression`, `Module:Erenshor/Progression`, its testcases, `Template:Progression graph`, the category page, and `Erenshor Wiki:Game Data`. Read the whole output, ask for approval, deploy, and keep the manifest. Verify: a live parse of a page with the template shows no script error, missing template, or tracking category.
- [ ] 5.2 Dry-run `wiki deploy-interface` for the two gadgets, ask for approval, deploy, and keep the manifest. Verify: a live page with the template draws the graph in a browser and answers the keyboard.
- [ ] 5.3 After the maintainer creates `Progression Graph` with the template, open it on live. Verify: it opens on the four raid planes and searches every node.
- [ ] 5.4 Place the template on the Raid Unlocking Walkthrough as `publish-wiki-data-views` D5 describes: announce it, render it through TemplateSandbox on that page, review it with the maintainer, and write one guarded edit that keeps every other text. Verify: the page renders the graph, its prose is unchanged, and the rollback manifest lists the edit.

## 6. Integration

- [ ] 6.1 Run `uv run erenshor test ci` and `uv run erenshor test wiki --warm`. Verify: both pass.
- [ ] 6.2 Archive the change with `openspec archive publish-wiki-progression-graph --yes`. Verify: `openspec/specs/wiki-progression-graph/spec.md` exists and `openspec validate --specs` passes.
