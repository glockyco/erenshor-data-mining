## Why

The bot last refreshed the live wiki articles on 2026-08-11. Of the 2,773 pages that the generator now produces for build 24405256, 2,694 differ from live, and 481 differ in content when link syntax is ignored. Among them, 113 pages change their encounter tier (28 still show the retired Rare tier), and items gain their world drop sources. A refresh cannot run safely today:

- Generation merges `type`, `questsource`, and `relatedquest` by text. An editor's `{{QuestLink|Name}}` and the generated `{{QuestLink|stablekey=…}}` for the same quest both stay, so 228 pages would list a quest twice.
- Lists repeat what a reader sees as one entry. Gambler's Cape lists A Highwayman Raider three times at 3.0%, once for each variant of that character. The generated `source` field repeats an entry on 130 pages. Live already shows such repeats on 67 pages.
- Pages with several entities match preserved fields by position, and generation deletes live root templates it does not produce. On 15 pages it would delete a character infobox, for example the Braxonian Chest infobox that an editor added to Frost.
- Zone pages merge from the repository copies in `wiki/zones/`, not from the live pages, so a deploy overwrites edits made on the wiki.
- Stance pages never take generated values, because the merge skips the `Stance` template.
- The `Weapons` and `Armor` refresh replaces everything after the first table on the page.
- Skill cooldowns lose their fractions. Kick shows 13 seconds, but the game counts 800 ticks at 60 per second, 13.33 seconds.
- `wiki deploy` writes without a base revision, keeps going after errors, and records no rollback data. It overwrites any edit made after the fetch.
- Live lacks what the new pages need: `Category:Elites`, the Elite tier in `Template:Character`, `Template:StanceTooltip`, and `Module:Erenshor/Data/Stances`. Its link, spell, skill, and item data modules date from July and August.

## What Changes

- Merged list fields identify each entry by the page it links to. A generated entry replaces an entry for the same page, and the other entries stay.
- A generated list shows each entry once per linked page and label. Variants of one entity share the entry, which shows their chance, or the range when the chances differ.
- Every generated root template carries its entity's stable key, and preserved fields follow the key. Generation never deletes a live root template that it cannot match. It leaves the root unchanged and lists it for review.
- Zone pages merge into the fetched live page like every other article. `wiki/zones/` is removed.
- Stance pages merge generated values like the other entity pages.
- The overview refresh replaces only the generated table.
- Skill cooldowns keep fractions of a second, in the legacy and the Lua output.
- `wiki deploy` writes an article only while its live revision is the revision the page was generated from. It parses each new text on the wiki first, and it does not write a page whose parse shows a script error, a missing template, a missing category page, or a new link tracking category. It records each write with its rollback text, reports every conflict and blocked page, and fails if there is one. It stops at the first error that is not specific to one page. A dry run lists the planned changes by kind.
- A repository-page deploy does not overwrite a page that another account changed, unless the maintainer accepts that page.
- `Template:Character`, `Stance`, `Quest`, and `Zone` select their Lua branch only by exact `lua=1`, as `Template:Item` already does, so `stablekey` identifies an entity without changing the rendering. No page passes `lua=1`, so every page keeps its parameter infobox. The branches stay as the tested entry point of the Lua renderers until the article conversion moves them to the new data-backed templates. `Template:Ability` is copied from live into the repository.
- **BREAKING**: `wiki deploy --from-dir`, `wiki deploy --legacy-article-deploy`, the unguarded edit call, and `wiki refresh-embedded --source-table` are removed. The source-table refresh served pages that store Cargo rows, and no page does.
- The live wiki is refreshed: data modules, templates, and `Category:Elites` first, then canary pages, then every changed article.

## Capabilities

### New Capabilities

- `wiki-article-refresh`: How generated data merges into live wiki articles, and how article and repository-page writes reach the live wiki without losing edits.

### Modified Capabilities

None. The generator already meets the `encounter-tiers` requirement for Elite pages. This change publishes it.

## Impact

- Code: `src/erenshor/application/wiki/` (field preservation, generate and deploy services, zone generation, skill section), `src/erenshor/application/wiki_deploy/` (manifest, page deploy, refresh), `src/erenshor/application/wiki_lua/skills.py`, `src/erenshor/infrastructure/wiki/client.py`, `src/erenshor/cli/commands/wiki.py`, `wiki/templates/`, and their tests.
- Removed: `wiki/zones/`, the zone output directory, `deploy_from_dir`, and `edit_page`.
- Live wiki: about 2,700 bot-flagged article edits by WoWBot, at least two seconds apart, plus about 20 module, template, and category pages.
- Golden baselines change, which needs approval at capture.
- Non-goals: Cargo tables (`publish-wiki-cargo-data`), replacing hand-maintained tables, data-backed article templates, the quest article strategy (#288), the repository drafts in `wiki/*.txt` and `wiki/mechanics/`, the main page (#291), and legacy fields that are always blank (spell `effects`, skill `itemswitheffect`).
