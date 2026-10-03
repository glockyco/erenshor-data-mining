## 1. Prerequisites

- [ ] 1.1 The maintainer enables the `cargoadmin` grant for the `WoWMuch@InterfaceDeploy` bot password at Special:BotPasswords. Verify: the interface session's rights include `recreatecargodata`.
- [ ] 1.2 `refresh-wiki-articles` is archived, so the guarded writes, the drift check, and the `lua=1` selector of the entity templates exist. Verify: `openspec list` no longer shows it as active.

## 2. Data rules

- [ ] 2.1 `fix(pipeline): place the Fernalla portal event spawns in their zone`: give the three `FernallaPortalEvent` spawn rows the zone of the event, or publish them as zone-less rows with a reason. Add a test. Verify: no wiki-visible spawn row lacks a zone without a reason.
- [ ] 2.2 Confirm in game with HotRepl (`uv run erenshor eval`) that a newly created character of each class knows no spell or skill until it uses a teaching item. Record the result in design D4. This decides that class lists come from teaching items.
- [ ] 2.3 Confirm in game with HotRepl the gold received for selling one item with the sell button and for selling a stack. Record the rule in design D4 and in the `SellValue` documentation.

## 3. Schema and commands (one commit each)

- [ ] 3.1 `feat(wiki): define the Cargo schema and its generation`: add `src/erenshor/application/wiki_cargo/` with the schema model, the D1 checks, the D2 escaper, the D3 sharding and page rendering, and the `Entities` and `Spawns` builders. Add tests for each failure rule, for escaping, and for stable shard assignment. Verify: the tests pass, and the generated `Spawns` rows equal the wiki-visible spawn rows of the clean database.
- [ ] 3.2 `feat(wiki): add the wiki cargo commands`: add `generate`, `deploy`, `verify`, and `create-tables` (design D6), the manifest stages, and the preconditions. Add tests with a fake wiki: a missing grant fails before any change, `verify` names a differing row, `deploy` saves only changed pages and stops while a table is missing, and drift stops the deploy. Verify: the tests pass and `uv run erenshor wiki cargo --help` lists the four commands.
- [ ] 3.3 `test(wiki-dev): check the Cargo slice in the local stack`: import the generated table templates and storage pages into `wiki-dev`, recreate the tables, and check the row counts and sample rows against the schema. Verify: `uv run erenshor test wiki --warm` passes.

## 4. First slice on the live wiki

- [ ] 4.1 Parse the largest `Spawns` storage page through TemplateSandbox with its table template, and record the parse time and memory. Verify: both stay below a quarter of the live limits.
- [ ] 4.2 Run `wiki cargo deploy`, `wiki cargo create-tables`, and `wiki cargo deploy` again for `Entities` and `Spawns`. Verify: `wiki cargo verify` reports no difference, and Special:CargoTables shows both tables with the expected row counts.

## 5. Remaining tables (one commit each)

- [ ] 5.1 `feat(wiki): publish items to Cargo`: `Items`, `ItemStats`, `ItemClasses`, and `ItemEffects`. Verify: every equippable item has a stats row for each quality of `item_stats`.
- [ ] 5.2 `feat(wiki): publish characters to Cargo`: `Characters`, `CharacterAbilities`, `CharacterFactionEffects`, and `Factions`. Verify: row counts equal their source tables.
- [ ] 5.3 `feat(wiki): publish abilities to Cargo`: `Spells`, `Skills`, `Stances`, and `AbilityClasses`. Verify: every class ability with a teaching item resolves to that item through `ItemEffects`.
- [ ] 5.4 `feat(wiki): publish item sources and uses to Cargo`: `ItemSources` and `ItemUses` with every source type of design D4. Verify: Breena Carpenter has 7 base items and 14 quest-unlocked items, and Crystallized Balance has its world drop row.
- [ ] 5.5 `feat(wiki): publish zones and quests to Cargo`: `Zones`, `ZoneConnections`, `Quests`, `QuestRoles`, `QuestPrerequisites`, and `QuestFactionEffects`. Compare the hostile level ranges with the levels on the live `Zones` page and explain each difference. Verify: Secure Port Azure lists Captain Kilkay as the giver with his keyword.
- [ ] 5.6 Review the full schema and its generated documentation with the maintainer, because a later change to a created table needs a sysop. Then deploy, create, and verify the remaining tables on live. Verify: `wiki cargo verify` reports no difference for any table.

## 6. Editor surface (one commit each)

- [ ] 6.1 `feat(wiki): add Cargo query templates`: add `Module:Erenshor/Query` and the templates of design D5 with TemplateData and examples. Check that each name is free on the wiki first. Add Scribunto testcases and smoke checks in the local stack. Verify: each example renders on live through TemplateSandbox, and an ambiguous page name lists its keys.
- [ ] 6.2 `feat(wiki): let editors add item sources and spawn points`: add `{{ItemSource}}` and `{{SpawnPoint}}` with key resolution and the tracking category. Verify in the local stack and on a live sandbox page: a valid row appears in the item source query marked as community, an unknown key stores nothing and adds the category, and a generated refresh keeps the community row.
- [ ] 6.3 `docs(wiki): document the Cargo tables for editors`: write `wiki/content/Erenshor Wiki/Cargo.wiki` as design D3 describes, and deploy it with the templates. Verify: every table and template is linked from the hub.

## 7. Removal

- [ ] 7.1 `refactor(wiki): remove Cargo from the article path`: delete what design D7 lists, with the tests and fixtures that only served it. Verify: `uv run erenshor test ci` passes, no repository file declares a table outside `Template:Cargo/`, and the deploy lists the live pages for an administrator to delete.

## 8. Documentation and verification

- [ ] 8.1 `docs(skills): describe the Cargo workflow`: add the generate, deploy, verify, and table-creation steps to `.agent/skills/wiki-templates/SKILL.md`, and the Cargo refresh to `.agent/skills/refreshing-game-data/SKILL.md`. Verify: `uv run pytest tests/contract/test_document_paths.py` passes.
- [ ] 8.2 `test(golden): add the Cargo rows to the baselines`: include each table's generated rows in `golden capture`. Show the diff to the maintainer and commit it only after approval.
- [ ] 8.3 Run `uv run erenshor test ci` and `uv run erenshor test wiki --warm`. Both pass.
- [ ] 8.4 Close GitHub issue #115 with a summary and archive the change with `openspec archive publish-wiki-cargo-data --yes`.
