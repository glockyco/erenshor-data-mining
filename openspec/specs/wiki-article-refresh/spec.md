# wiki-article-refresh Specification

## Purpose
Defines how generated game data merges into live wiki articles without losing what editors wrote, and how article and repository-page writes reach the live wiki without overwriting edits made in between.

## Requirements

### Requirement: Merged list fields link each page once

When generation merges a list field (`type`, `questsource`, `relatedquest`) of a live article with generated values, it SHALL identify each entry by the page it links to. A live entry that links the same page as a generated entry SHALL be replaced by the generated entry. Entries that link other pages, and plain text, SHALL stay.

#### Scenario: An editor's link and a generated link to the same quest

- **WHEN** the live `relatedquest` field holds `{{QuestLink|The Revival Plains Ritual}}` and generation produces `{{QuestLink|stablekey=quest:therevivalritual}}`
- **THEN** the merged field links that quest once, in the generated form

#### Scenario: An editor's link that generation does not produce

- **WHEN** the live field also links a quest that generation does not produce
- **THEN** the merged field keeps that link

### Requirement: Generated lists show each entry once

A generated list field SHALL show one entry for each pair of linked page and label. When several entities share that pair, the entry SHALL show their common chance, or the lowest and highest chance when they differ.

#### Scenario: Variants of one character drop an item

- **WHEN** three variants of A Highwayman Raider drop Gambler's Cape at 3.0% each
- **THEN** the Gambler's Cape sources list A Highwayman Raider once at 3.0%

#### Scenario: Variants with different chances

- **WHEN** two variants that share a page and a label drop an item at 2.0% and 4.5%
- **THEN** the entry shows 2.0–4.5%

#### Scenario: Entities with their own labels

- **WHEN** Braxonian Planar Guard (Fire) and Braxonian Planar Guard (Ice) drop the same item
- **THEN** the sources list both

### Requirement: Preserved fields follow the entity

Every generated root template of an entity SHALL carry the entity's stable key in `stablekey`. Generation SHALL match a live root template to a generated one by stable key. A live root without a key SHALL match a generated root with the same entity name. When several roots share a name, generation SHALL pair them so that the most field values agree. When several pairings agree equally well and give different pages, generation SHALL fail for that page, name it, and list the stable keys to add by hand. A live root that matches no generated entity SHALL stay unchanged, and generation SHALL list it for review. Generation SHALL NOT delete it.

A merged root SHALL take the companion templates of its generated root, such as `ItemTooltip` or `SpellTooltip`. The generated companions SHALL replace the live companions of that root, also when prose or editor markup stands between the root and a companion.

#### Scenario: Entities change order

- **WHEN** the entities of a page change order between two builds
- **THEN** each preserved field stays with its stable key

#### Scenario: A root that an editor added

- **WHEN** the live Frost page holds a Braxonian Chest character infobox that generation does not produce for Frost
- **THEN** the infobox stays unchanged and the page is listed for review

#### Scenario: Variants that share a name

- **WHEN** a live page has two unkeyed Malignant Thoughts infoboxes and only the second one holds the coordinates of the second generated variant
- **THEN** each infobox merges with the variant whose values it holds, and the coordinates stay with their variant

#### Scenario: Same-name roots that no value tells apart

- **WHEN** a live page has two unkeyed character infoboxes with the same name and the same values, only one of them has an image caption, and generation produces two entities with that name
- **THEN** generation fails for that page and names the stable keys to add

#### Scenario: A tooltip in an editor's table

- **WHEN** an editor placed the `Item/Charm` companion of a charm inside a table
- **THEN** the regenerated companion replaces it inside the table, and no second companion appears

### Requirement: Every generated entity takes current data

Generation SHALL merge current generated values into every generated root template on a live page, including `Stance`, under that template's preservation rules.

#### Scenario: A stance value changes

- **WHEN** a game update changes the damage modifier of a stance
- **THEN** the regenerated stance page shows the new modifier

### Requirement: Zone pages merge into the live page

Zone pages SHALL be generated from the fetched live page, like the other articles. The repository SHALL NOT hold a copy of a zone page. Each `Zone` field other than `title` SHALL keep its live value when that value is not blank. A generated value SHALL fill only a blank field or a new page.

#### Scenario: An editor changed a zone page

- **WHEN** an editor added a paragraph to a zone page on the wiki and the page is fetched and regenerated
- **THEN** the regenerated page holds that paragraph

#### Scenario: An editor corrected the connections

- **WHEN** an editor removed from the `connects` field a zone that players cannot reach, and the game data still has that zone line
- **THEN** the regenerated page keeps the value of the editor

### Requirement: Overview refresh replaces only the generated table

Regeneration of the `Weapons` and `Armor` pages SHALL replace only the generated table. Text and tables before and after it SHALL stay. A page without exactly one generated table SHALL fail generation and be named.

#### Scenario: Notes after the table

- **WHEN** the live `Armor` page has an introduction, the generated table, and a notes section
- **THEN** the regenerated page keeps the introduction and the notes section

### Requirement: Durations keep their precision

Skill cooldowns SHALL be shown in seconds as ticks divided by 60, with up to two decimal places, in the legacy and the Lua output alike.

#### Scenario: Kick

- **WHEN** a skill has a cooldown of 800 ticks
- **THEN** its page shows 13.33 seconds

### Requirement: Article writes depend on the revision they were generated from

`wiki deploy` SHALL write a changed article only while the live page is at the revision that generation merged into. It SHALL create a page that had no live revision at generation only while the page still does not exist. Every other page SHALL be reported as a conflict and SHALL NOT be written. A page whose generated text equals its fetched text after page normalization (category order and position, blank lines, and line-end spaces) is not changed, and `wiki deploy` SHALL NOT write it.

#### Scenario: An editor saved the page after the fetch

- **WHEN** a page has a newer live revision than the fetched one
- **THEN** the deploy does not write it and reports it as a conflict

#### Scenario: A page generated without its live text

- **WHEN** a page was generated without a fetched copy and exists on the wiki
- **THEN** the deploy does not write it and reports it as a conflict

#### Scenario: Categories above the infobox

- **WHEN** the categories of a fetched zone page are above its infobox and generation changes no field of the page
- **THEN** the deploy does not write the page

### Requirement: Each article passes a live parse before it is written

Before it writes an article, `wiki deploy` SHALL parse the new text on the live wiki under the page title. It SHALL NOT write the page when the parse reports a script error or a missing template, or when it reports a category without a page or an Erenshor link tracking category that the live page is not in. It SHALL report the page and the reason.

#### Scenario: A missing category page

- **WHEN** a new text adds `Category:Elites` and that category page does not exist
- **THEN** the page is not written and the report names the missing category

### Requirement: Article deploys can be rolled back

`wiki deploy` SHALL record, before its first write, every planned page with its base revision, and after each write the new revision, in the manifest format of `wiki rollback-repo-pages`. That command SHALL restore the fetched text of each written page that is still at the deployed revision, and SHALL refuse a page that changed after the deploy.

#### Scenario: Roll back a canary

- **WHEN** the maintainer rolls back the manifest of a canary deploy and nobody edited the pages since
- **THEN** each page holds its fetched text again

### Requirement: Deploy failures are named

`wiki deploy` SHALL continue past a conflict or a blocked page, and SHALL fail at the end naming each of them with its reason. It SHALL stop at the first error that is not specific to one page, such as a failed login, a failed assertion, or exhausted retries, and SHALL report the output as partial.

#### Scenario: One conflict among many pages

- **WHEN** one page of a deploy is a conflict
- **THEN** the other pages are written and the command fails naming that page

#### Scenario: Lost session

- **WHEN** an edit fails because the session no longer asserts the bot
- **THEN** the deploy stops before the next page and reports which pages it wrote

### Requirement: The deploy plan is reviewable

A dry run of `wiki deploy` SHALL NOT write to the wiki. It SHALL report the pages that it would write, grouped by kind of change (new pages, encounter tiers, field values, links, stable keys, categories, and structure), the live roots that generation kept because they match no generated entity, and the pages that are conflicts. Field values SHALL compare with link syntax ignored: a value whose links reach the same pages through other syntax is a link change. The dry run SHALL fail when a planned page is a conflict.

#### Scenario: Tier changes

- **WHEN** the dry run covers a page whose type changes from Rare to Elite
- **THEN** the report lists that page under encounter tier changes

#### Scenario: Link syntax only

- **WHEN** a field changes from `[[The Brake]]` to `{{ZoneLink|stablekey=zone:brake}}`, and the link catalog places that key on `The Brake`
- **THEN** the report lists the page under link changes and not under field value changes

#### Scenario: A page changed after the fetch

- **WHEN** a planned page has a newer live revision than its fetched revision
- **THEN** the dry run names that page as a conflict and fails

### Requirement: Repository pages are not overwritten after another account's edit

`wiki deploy-repo-pages` SHALL NOT edit a page whose latest revision was made by an account other than the deploying account and whose text differs from the repository source, unless the maintainer accepts that page by title. It SHALL name each such page before the first write.

#### Scenario: An administrator reverted a template

- **WHEN** an administrator reverted a bot edit of `Template:Quest` and the repository source differs from the reverted text
- **THEN** the deploy stops before its first write and names `Template:Quest`

#### Scenario: An accepted page

- **WHEN** the maintainer reviews the live text of `Template:Quest` and passes `--accept-drift Template:Quest`
- **THEN** the deploy overwrites `Template:Quest`

#### Scenario: Live text equal to the source

- **WHEN** another account made the latest revision of a page whose live text equals the repository source
- **THEN** the page is unchanged and the deploy continues
