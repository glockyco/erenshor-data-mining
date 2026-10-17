# Spec Delta

## MODIFIED Requirements

### Requirement: Generated values live only on bot-owned pages

Generated game data SHALL reach the wiki only through the bot-owned Lua data modules under `Module:Erenshor/Data/`. After an entity type is converted, each article of that type SHALL hold, for each entity it describes, one call of the type's data-backed template with the entity's stable key, and otherwise only text that people write. A grouped zone article SHALL instead hold one ZoneData infobox call with a zone stable identity whose generated page relation accounts for every mapped scene on that page. That relation SHALL NOT cause duplicate infoboxes or omit member identities from conversion coverage.

#### Scenario: A game update changes a stat

- **WHEN** a new game build changes the damage of a converted item
- **THEN** the refresh changes the item's data module
- **AND** the refresh changes no article

#### Scenario: A converted article holds no generated value

- **WHEN** an item article is converted
- **THEN** its source holds the item's template call with stablekey and the text that people wrote, and no generated field value

#### Scenario: Multiple zone scenes share an infobox

- **WHEN** a zone article represents multiple mapped scenes
- **THEN** it holds one ZoneData call backed by complete declared scene membership
- **AND** its one infobox renders the distinct scene summaries and maps

### Requirement: Only fields that people own can be overridden

A data-backed template SHALL let an article override only the fields that people own: the image, the image caption, other sources and the location, subject to the converted type's more specific ownership contract. On data-backed zone pages, images and captions remain editor-owned. Confirmed level advice, map presentation and supplemental connection notes MAY remain editor input only through the zone ownership contract. Zone classification, enemy summaries, map identities and usable connection/gate facts SHALL come from their common producer and SHALL NOT be overridden by legacy factual article parameters. A materially ambiguous legacy value SHALL retain its original article bytes and block conversion until its meaning and preserved disposition are approved.

A parameter for a field that is not owned by people SHALL NOT change the rendered value, and the page SHALL join a tracking category that names the parameter. When an entry of other sources links an entity by its stable key, and the data module holds that entity as a source, the page SHALL join a tracking category for editor entries that the data covers.

#### Scenario: An editor sets an owned field

- **WHEN** a converted type whose ownership contract permits image presentation passes an editor image
- **THEN** its infobox shows that image under its documented image behavior

#### Scenario: An editor sets a generated field

- **WHEN** an item article passes damage=99 to its data-backed template
- **THEN** the infobox shows the damage from the data module
- **AND** the page joins the tracking category for parameters that cannot override data

#### Scenario: The data catches up with an editor's source

- **WHEN** an item article lists an explicit stable-key quest under other sources, and a new build exports that quest as a source of the item
- **THEN** the page joins the tracking category for editor entries that the data covers

#### Scenario: A zone classification disagrees with the overview

- **WHEN** an old zone infobox says Dungeon but its common classification says Outdoor
- **THEN** the disagreement requires a reviewed common-producer disposition before conversion
- **AND** the new article cannot conceal it with a contradictory type override

#### Scenario: A level value has no established meaning

- **WHEN** a legacy zone value might mean access, enemy range or advice and available evidence does not settle it
- **THEN** conversion leaves the original article unchanged and reports the exact unresolved value
- **AND** it does not automatically turn the value into a recommendation
