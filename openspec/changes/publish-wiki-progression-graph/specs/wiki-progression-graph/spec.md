## Purpose

Renders the clean database's requirement graph on the wiki: a target's playthrough route, its alternatives, and their sources, as text that works without JavaScript and as an explorer that draws and navigates the graph.

## ADDED Requirements

### Requirement: The data module mirrors the requirement graph

`Module:Erenshor/Data/Progression` SHALL hold every node of the requirement graph that has a way or that a need references, with its kind, tier, milestone flag, native name and page, and every way of those nodes with its needs, including a way without needs. It SHALL leave out a way that needs its own node, because such a way cannot be how a player gets the node. It SHALL use one table per node and escaped JSON strings for ways, preserving first-way selection and every need field, including required character level. The renderer SHALL decode ways lazily. Generation SHALL validate source rows before compaction and fail with the node when a condition has no wording, an identity resolves in neither catalog, or the module exceeds its page budget.

#### Scenario: A raid plane

- **WHEN** `wiki generate-lua` runs on the current main build
- **THEN** the module holds Brax's Plane of Elements with its tier and its way through Reliquary Hall with Rune of Elements in its planning slot

#### Scenario: A condition without wording

- **WHEN** a need names a condition key that the builder cannot word
- **THEN** generation fails and names the node, the way, and the key

#### Scenario: A node that carries no requirement

- **WHEN** a node has no way and no need references it, such as an item that the game leaves unnamed and unobtainable
- **THEN** the module leaves it out

#### Scenario: A way that needs its own node

- **WHEN** a way to get the Loss Stone needs the Loss Stone held
- **THEN** the module leaves that way out and keeps the Loss Stone's other ways

#### Scenario: A packed way preserves optional requirements

- **WHEN** a way has a class or level restriction, dialog keywords, quantities, slots, advice, or unconfirmed access
- **THEN** packing and lazy decoding preserve those requirements without changing first-way selection

### Requirement: Shared page inference uses a complete compact index

`Module:Erenshor/Data/PageKeys` SHALL preserve `Data/Links` page-to-key membership and order, including several identities on one page. Shared `Link.pageKeys` SHALL read this index without loading full link records and SHALL retain its existing page normalization and kind filtering. Generation SHALL fail when any catalog key is absent from its own page, appears under another page, or is duplicated.

#### Scenario: A shared page has several identities

- **WHEN** a page-inferring view requests the keys of a page shared by several entities
- **THEN** it receives the same keys in the same order as the full link catalog

#### Scenario: Index coverage is incomplete

- **WHEN** a catalog key is removed from its page in the generated index
- **THEN** generation fails and identifies the missing key and page


### Requirement: A page renders a target's progression as text

`{{Progression graph}}` SHALL take its target from `stablekey`, or else from the one entity whose page is the current page. It SHALL render the milestones of the target's persisted first-way route in tier order, then each milestone's ways and needs as nested lists, linking each node. A node already shown SHALL be referenced instead of repeated, and nested sources SHALL stop at depth 6. The rendering SHALL work without JavaScript. A target without data SHALL show a message and join the category `Pages with missing Erenshor progression data`. A hidden JSON container SHALL retain the rendered target subgraph and boundary labels for the gadget.

#### Scenario: A zone page

- **WHEN** the template is placed without arguments on the Fallen Braxonia page
- **THEN** it lists the door that the Ancient Braxonian Key opens and the milestones before it, and links each page

#### Scenario: Several entities on one page

- **WHEN** the template is placed without `stablekey` on a page that two entities share
- **THEN** it shows an error that lists both stable keys

#### Scenario: A key without data

- **WHEN** `stablekey` names an entity that the data module lacks
- **THEN** the template says that the data is missing and adds the tracking category

### Requirement: Tiers are labeled as a playthrough order

Every rendering of tiers SHALL say that a tier is a step of a playthrough from a new character's start, and SHALL NOT present a tier as what a reader can do with their own character.

#### Scenario: The legend

- **WHEN** a page renders the template
- **THEN** its legend explains ways, needs, and tiers as a playthrough order from a new character

### Requirement: The explorer draws and navigates the milestone graph

With the gadget, the template SHALL draw its target's milestones as a graph with one column per tier. The reader SHALL be able to search every node by name, focus any node, switch between what it needs and what it unlocks, expand a milestone to its ways and sources and collapse it again, and open each node's page. Every action SHALL work with the keyboard. When the gadget cannot draw, the text SHALL stay visible.

#### Scenario: Focus by search

- **WHEN** a reader searches for Rune of Elements and selects it
- **THEN** the graph shows A Lost Portal Pt. 2, whose reward it is, turned in to the Elemental Energy with Inert Rune of Brax and Eldrich Crystal

#### Scenario: What a key unlocks

- **WHEN** the reader shows what the Ancient Braxonian Key unlocks
- **THEN** the graph shows the door into Fallen Braxonia and what lies behind it

#### Scenario: Keyboard focus

- **WHEN** a reader moves to a node with the Tab key and presses Enter
- **THEN** the graph focuses that node

#### Scenario: A failed load

- **WHEN** the gadget fails to load or to read the data
- **THEN** the text stays visible and the page shows no script error

### Requirement: Filters keep the playthrough route honest

The explorer SHALL offer a quests-only and an areas-only filter. A filtered edge SHALL stand for the steps it hides on the playthrough route and SHALL say so, and SHALL NOT be presented as a direct requirement between the two nodes it joins.

#### Scenario: Quests only

- **WHEN** the reader filters Brax's Plane of Elements to quests
- **THEN** each edge between two quests names the hidden steps between them on the playthrough route

### Requirement: Common sources and open travel stay collapsed

The explorer SHALL show an item's sources beyond the first four, and a zone's entrances that need no gate, as collapsed groups with their count, which the reader can expand.

#### Scenario: A common ingredient

- **WHEN** the explorer expands The Duskenlight Ritual
- **THEN** Wolf Meat shows its first sources and a collapsed group of the rest
