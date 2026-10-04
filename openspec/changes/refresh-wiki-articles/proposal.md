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
- Chests have combat tiers. The tier rule makes Braxonian Chest, Solunarian Chest, and the Vithean Chest rounds Enemy or Boss, because nothing in it knows the TreasureChest faction.
- Live lacks what the new pages need: `Category:Elites`, `Category:Chests`, the Elite and Chest tiers in `Template:Character`, `Template:StanceTooltip`, and `Module:Erenshor/Data/Stances`. Its link, spell, skill, and item data modules date from July and August.

## What Changes

- Merged list fields identify each entry by the page it links to. A generated entry replaces an entry for the same page, and the other entries stay.
- A generated list shows each entry once per linked page and label. Variants of one entity share the entry, which shows their chance, or the range when the chances differ.
- Every generated root template carries its entity's stable key, and preserved fields follow the key. Generation never deletes a live root template that it cannot match. It leaves the root unchanged and lists it for review.
- Zone pages merge into the fetched live page like every other article. `wiki/zones/` is removed.
- Stance pages merge generated values like the other entity pages.
- The overview refresh replaces only the generated table.
- Skill cooldowns keep fractions of a second, in the legacy and the Lua output.
- Characters of the TreasureChest faction get the encounter tier `chest`. Their pages have the type Chest and `Category:Chests` instead of `Category:Enemies`, and the map shows them with their own marker and filter.
- `wiki deploy` writes an article only while its live revision is the revision the page was generated from. It parses each new text on the wiki first, and it does not write a page whose parse shows a script error, a missing template, a missing category page, or a new link tracking category. It records each write with its rollback text, reports every conflict and blocked page, and fails if there is one. It stops at the first error that is not specific to one page. A dry run lists the planned changes by kind.
- A repository-page deploy does not overwrite a page that another account changed, unless the maintainer accepts that page.
- The entity templates are plain parameter templates (`adopt-data-backed-wiki` task 1.4), so `stablekey` identifies an entity without changing the rendering. `Template:Character` gains the Elite and Chest tiers. `Template:Ability` is copied from live into the repository.
- **BREAKING**: `wiki deploy --from-dir`, `wiki deploy --legacy-article-deploy`, the unguarded edit call, and `wiki refresh-embedded --source-table` are removed. No page stores Cargo rows, so the source-table refresh has no use.
- The live wiki is refreshed: data modules, templates, `Category:Elites`, and `Category:Chests` first, then canary pages, then every changed article.

## Capabilities

### New Capabilities

- `wiki-article-refresh`: How generated data merges into live wiki articles, and how article and repository-page writes reach the live wiki without losing edits.

### Modified Capabilities

- `encounter-tiers`: characters of the TreasureChest faction get the tier `chest`, with their own wiki category and map marker.

## Impact

- Code: `src/erenshor/application/processor/` (encounter tier), `src/erenshor/application/wiki/` (field preservation, generate and deploy services, zone generation, skill section, categories), `src/erenshor/application/wiki_deploy/` (manifest, page deploy, refresh, link audit), `src/erenshor/application/wiki_lua/skills.py`, `src/erenshor/infrastructure/wiki/client.py`, `src/erenshor/cli/commands/wiki.py`, `src/maps/` (chest markers), `wiki/templates/`, `wiki/modules/`, and their tests.
- Removed: `wiki/zones/`, the zone output directory, `deploy_from_dir`, and `edit_page`.
- Live wiki: about 2,700 bot-flagged article edits by WoWBot, at least two seconds apart, plus about 20 module, template, and category pages.
- Non-goals: Cargo tables (`publish-wiki-cargo-data`), replacing hand-maintained tables, data-backed article templates, the quest article strategy (#288), the repository drafts in `wiki/*.txt` and `wiki/mechanics/`, the main page (#291), and legacy fields that are always blank (spell `effects`, skill `itemswitheffect`).
