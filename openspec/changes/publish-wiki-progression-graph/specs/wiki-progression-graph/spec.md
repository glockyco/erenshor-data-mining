## Purpose

Renders the clean database's requirement graph on the wiki: a target's playthrough route, its alternatives, and their sources, as text that works without JavaScript and as an explorer that draws and navigates the graph.

## ADDED Requirements

### Requirement: The data module mirrors the requirement graph

`Module:Erenshor/Data/Progression` SHALL hold every node of the requirement graph with its kind, tier, milestone flag, and native identity reference, and every way with its needs. Generation SHALL fail and name the node when a need's condition has no wording, when an identity resolves in neither the link catalog nor the native identity catalog, or when the module exceeds its page budget.

#### Scenario: A raid plane

- **WHEN** `wiki generate-lua` runs on the current main build
- **THEN** the module holds Brax's Plane of Elements with its tier and its way through Reliquary Hall with Rune of Elements in its planning slot

#### Scenario: A condition without wording

- **WHEN** a need names a condition key that the builder cannot word
- **THEN** generation fails and names the node, the way, and the key

### Requirement: A page renders a target's progression as text

`{{Progression graph}}` SHALL take its target from `stablekey`, or else from the one entity whose page is the current page. It SHALL render the milestones of the target's playthrough route in tier order, then each milestone's ways and needs as nested lists, linking each node. A node already shown SHALL be referenced instead of repeated. The rendering SHALL work without JavaScript. A target without data SHALL show a message and join the category `Pages with missing Erenshor progression data`.

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

Every rendering of tiers SHALL say that a tier is a step of a playthrough from a new character in Stowaway's Step, and SHALL NOT present a tier as what a reader can do with their own character.

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
