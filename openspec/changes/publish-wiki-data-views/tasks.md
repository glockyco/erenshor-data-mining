## 1. Foundation (one commit each)

- [ ] 1.1 `feat(wiki): declare view data fields and check them at generation`: in `src/erenshor/application/wiki_lua/`, add the field declarations of design D2, the writer that renders them as the module's opening comment, and the checks for unresolved keys, markup, line breaks, and types. Add a test for each failure and one for the header. Verify: the tests pass, and each failure names the module, the row, and the field.
- [ ] 1.2 `feat(wiki): resolve a page's entities in the link module`: add `Link.pageKeys(kind, page)` over the `byPage` index of `Module:Erenshor/Data/Links`, with Scribunto testcases for one entity, several entities, and none. Verify: the testcases pass in the local stack.

## 2. Vendor stock

- [ ] 2.1 `feat(wiki): render vendor stock from generated data`: build `Module:Erenshor/Data/VendorStock` by vendor: item key, price as `round(ItemValue)`, item type label from the article generator's item type display, and the key of the quest that adds the item. Add `Module:Erenshor/VendorStock` and `Template:Vendor stock` after checking that the name is free, with testcases and structural smoke rows. Verify: in the local stack, Breena Carpenter's stock lists 7 items and 14 quest items with their prices and quests, and a page without stock shows the missing-data message and category.
- [ ] 2.2 Deploy the data module, the link module change, the view module, and the template to live after a dry run and approval. Render `{{Vendor stock}}` on the 54 vendor pages through TemplateSandbox, compare each with its `Store inventory` table, and record each difference with its cause. Record the Lua memory and time of the heaviest page. Verify: every difference is a stale table row or a fixed pipeline gap, and the heaviest page stays under a quarter of both live limits.
- [ ] 2.3 Replace the 54 `Store inventory` tables as design D5 describes: announce, review, and write one guarded edit per page. Verify: no vendor page holds a `Store inventory` table, each renders `{{Vendor stock}}`, and the rollback manifest lists every edit.
- [ ] 2.4 `refactor(tools): delete the vendor table script`: delete `src/tools/update_vendor_inventory_tables.py`, `src/tools/generate_vendor_inventory_tables.py`, `src/erenshor/tools/vendor_inventory_tables.py`, `tests/unit/tools/test_generate_vendor_inventory_tables.py`, and every reference to them. Verify: no file refers to `vendor_inventory_tables`, and the unit tests pass.

## 3. Zone rosters

- [ ] 3.1 `feat(wiki): render zone rosters from generated data`: build `Module:Erenshor/Data/ZoneRosters` by zone: character key, encounter tier, level range, spawn chance, and whether the character spawns only at night or as a rare spawn. Add `Module:Erenshor/ZoneRoster` and `Template:Zone roster` with testcases and smoke rows. Verify: in the local stack, Abyssal Lake lists its 9 enemies and 6 bosses under their tiers.
- [ ] 3.2 Deploy after approval, list the zone pages that hold a roster table, compare each with the view, and decide each page with WoWMuch, Port Azure's sub-areas among them. Then replace the tables as design D5 describes. Verify: each listed table renders from the view or stays by a decision that this task records.

## 4. Class abilities

- [ ] 4.1 Confirm in game with HotRepl (`uv run erenshor eval`) that a newly created character of each class knows no spell or skill until it uses an item that teaches it. Record the result in the Context of `design.md`. This decides that class lists come from teaching items.
- [ ] 4.2 `feat(wiki): render class abilities from generated data`: build `Module:Erenshor/Data/ClassAbilities` by class: ability key, required level, and the keys of the items that teach it. Add `Module:Erenshor/ClassAbilities` and `Template:Class abilities` with testcases and smoke rows. Verify: in the local stack, the Druid list shows the six summon spells, each with its spell scroll.
- [ ] 4.3 Deploy after approval, compare the view with the "Abilities and Spells" tables of the class pages and with the Ability Books page, and replace them as design D5 describes. Verify: the class pages and Ability Books render from the view.

## 5. Quest panel

- [ ] 5.1 `feat(wiki): render the quest panel from generated data`: build `Module:Erenshor/Data/Quests` by quest: how it is acquired with its sources and keywords, who completes it, required items, rewards, faction effects, prerequisites, and whether it repeats. Add `Module:Erenshor/QuestData` and `Template:Quest data` with testcases and smoke rows. Verify: in the local stack, the three quest scenarios of the `wiki-data-views` spec hold.
- [ ] 5.2 Deploy after approval and place the panel on the quest pages as design D5 describes, after a dry-run list of every page and the place of its panel. Verify: each quest page shows its panel, and the rollback manifest lists every edit.

## 6. Overviews

- [ ] 6.1 `feat(wiki): render the zone and quest overviews from generated data`: build `Module:Erenshor/Data/Zones` by zone: type, hostile level minimum, median, and maximum, and connections. Add `Template:Zone list` with the notes parameters of design D4 and `Template:Quest list` over `Data/Quests`, with testcases and smoke rows. Compare the hostile level ranges with the levels on the live Zones page and explain each difference. Verify: in the local stack, the quest list shows that The Tragedy at Goodsoil gives no reward, and a note parameter that names no zone adds the tracking category.
- [ ] 6.2 Deploy after approval and replace the Zones and Quests overview tables as design D5 describes, moving each note into a parameter. Verify: both overviews render from the views, and every note is in its zone's row.

## 7. Documentation and verification

- [ ] 7.1 `docs(wiki): explain the views and data modules to editors`: add a section to `wiki/content/Erenshor Wiki/Game Data.wiki` that lists the view templates and the data modules, shows how a module reads a data module and renders links, and says where to report a missing fact. Deploy it after approval. Verify: the guide links every view template and data module, and the contract tests pass.
- [ ] 7.2 `docs(skills): describe the view workflow`: describe adding and deploying a view in `.agent/skills/wiki-templates/SKILL.md`, and the view refresh after a data deploy in `.agent/skills/refreshing-game-data/SKILL.md`. Verify: `uv run pytest tests/contract/test_document_paths.py` passes.
- [ ] 7.3 Run `uv run erenshor test ci` and `uv run erenshor test wiki --warm`. Both pass.
- [ ] 7.4 Archive the change with `openspec archive publish-wiki-data-views --yes`. Verify: `openspec/specs/wiki-data-views/spec.md` exists.
