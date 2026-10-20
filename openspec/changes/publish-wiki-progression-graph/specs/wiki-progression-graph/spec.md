## Purpose

Renders the clean database's requirement graph on the wiki: a target's playthrough route as chapters of plain steps with their alternatives and sources, as text that works without JavaScript, and as a chapter map that places each step in its goal's route.

## ADDED Requirements

### Requirement: The data module mirrors the requirement graph

`Module:Erenshor/Data/Progression` SHALL hold every node of the requirement graph that has a way, that a need references, or whose start has a way, with its kind, tier, milestone flag, native name and page, and every way of those nodes with its needs and its plain sentence, including a way without needs. It SHALL leave out a way that needs its own node, because such a way cannot be how a player gets the node. It SHALL use one table per node and escaped JSON strings for ways, preserving first-way selection and every need field, including required character level. It SHALL name the relations whose targets must stay undone. The renderer SHALL decode ways lazily. Generation SHALL validate source rows before compaction and fail with the node when a condition or a relation has no wording, a sentence names a node outside the module, an identity resolves in neither catalog, or the module exceeds its page budget.

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

### Requirement: Every way reads as a plain sentence

Each way SHALL read as one imperative sentence that names its node, what the player does, with whom, and where, followed by the way's conditions. A character SHALL be placed in the zone of its first way. A need that another need of the same way implies SHALL NOT be repeated. A quest to leave undone SHALL read as a condition to meet before finishing it. `erenshor progression show` SHALL print the same sentence for each way.

#### Scenario: A drop that needs rain

- **WHEN** the Ancient Braxonian Key's way is its drop from Evadne the Corrupted with the rain of Braxonian Desert as its release
- **THEN** its sentence tells the reader to defeat Evadne the Corrupted in Braxonian Desert for the key and names the rain as the condition

#### Scenario: A quest and its start

- **WHEN** a quest is finished by giving an item to a character, and its start is a talk with another character
- **THEN** its sentence names the start, the item, the receiving character, and that character's zone

#### Scenario: A reward way

- **WHEN** Tempestalia, Ring of Storms is the reward of Repairing Orion's Ring, Part 2, whose way also needs the quest's turn-in items held and the quest undone
- **THEN** its sentence names only the quest

#### Scenario: A relation without wording

- **WHEN** a need's relation has no phrase in the wording table
- **THEN** generation fails and names the node, the way, and the relation

### Requirement: Shared page inference uses a complete compact index

`Module:Erenshor/Data/PageKeys` SHALL preserve `Data/Links` page-to-key membership and order, including several identities on one page. Shared `Link.pageKeys` SHALL read this index without loading full link records and SHALL retain its existing page normalization and kind filtering. Generation SHALL fail when any catalog key is absent from its own page, appears under another page, or is duplicated.

#### Scenario: A shared page has several identities

- **WHEN** a page-inferring view requests the keys of a page shared by several entities
- **THEN** it receives the same keys in the same order as the full link catalog

#### Scenario: Index coverage is incomplete

- **WHEN** a catalog key is removed from its page in the generated index
- **THEN** generation fails and identifies the missing key and page

### Requirement: A page renders a target's route as chapters of plain steps

`{{Progression graph}}` SHALL take its target from `stablekey`, or else from the one entity whose page is the current page. It SHALL render the milestones of the target's persisted first-way route as numbered steps in their sentences, grouped into chapters titled by the area, gate, or goal that each unlocks, in an order where every step follows the steps it needs. A need to leave a quest undone SHALL NOT bring that quest or its requirements into the route. An item that its quest's reward alone yields SHALL be named in that quest's step. Each step SHALL offer one disclosure with its other ways and, for each need that is no step of its own and no open area, where to get it, and a list of more than four ways SHALL collapse after the fourth into a counted group. Each node of a sentence SHALL link to its page. The rendering SHALL work without JavaScript. A target without data SHALL show a message and join the category `Pages with missing Erenshor progression data`. A hidden JSON container SHALL retain the chapters, the steps with their requirements, and the records that the sentences name.

#### Scenario: A zone page

- **WHEN** the template is placed without arguments on the Fallen Braxonia page
- **THEN** it shows the chapter that unlocks Fallen Braxonia, whose steps lead from the Tempest Stone through Orion Mycon's Lost Ring and Tempestalia, Ring of Storms to the Ancient Braxonian Key and the gate, and links each node

#### Scenario: A quest to leave undone

- **WHEN** a step's first way needs The Loss Stone undone
- **THEN** the step's sentence says to act before finishing The Loss Stone, and the route holds no step for The Loss Stone or for what only it needs

#### Scenario: A common ingredient

- **WHEN** a step needs Wolf Meat, which is no step and has many sources
- **THEN** the step's disclosure lists its first four sources and a counted group of the rest

#### Scenario: Several entities on one page

- **WHEN** the template is placed without `stablekey` on a page that two entities share
- **THEN** it shows an error that lists both stable keys

#### Scenario: A key without data

- **WHEN** `stablekey` names an entity that the data module lacks
- **THEN** the template says that the data is missing and adds the tracking category

### Requirement: The route is labeled as one playthrough order

Every rendering of the route SHALL say that it is one order of play from a new character's start, and SHALL NOT present it as what a reader can do with their own character. No rendering SHALL show a tier number.

#### Scenario: The legend

- **WHEN** a page renders the template
- **THEN** its legend says that the steps are one order from a new character's start and that other ways sit under each step

### Requirement: The chapter map shows one goal at a time

With the gadget, the template SHALL draw the chapters of one goal as a map, with a line between two chapters when a step of the later one needs a step of the earlier one and no other path of the map joins them. The reader SHALL be able to choose the goal among the template's targets and the steps of the route, choose a chapter to bring its steps into view in the text, and show a step's neighbourhood: what its first way needs and what needs it, with the action on each line. The text SHALL hide the steps that the goal does not need. The reader SHALL be able to search every node by name and open each node's page. Every action SHALL work with the keyboard. When the gadget cannot draw, the text SHALL stay visible.

#### Scenario: One goal

- **WHEN** the reader chooses Brax's Plane of Elements on the page with the four raid planes
- **THEN** the map draws only the chapters that Brax's Plane of Elements needs, and the text hides the steps that only the other planes need

#### Scenario: A chapter

- **WHEN** the reader chooses the chapter that unlocks Fallen Braxonia in the map
- **THEN** the text scrolls to that chapter and marks it

#### Scenario: What a key unlocks

- **WHEN** the reader shows the neighbourhood of the Ancient Braxonian Key
- **THEN** it draws Evadne the Corrupted and the rain of Braxonian Desert before the key and the gate into Fallen Braxonia after it, with the action on each line

#### Scenario: Search

- **WHEN** a reader searches for Rune of Elements and selects it
- **THEN** the text shows the step of A Lost Portal Pt. 2, which yields it

#### Scenario: Keyboard

- **WHEN** a reader moves to a chapter with the Tab key and presses Enter
- **THEN** the text scrolls to that chapter

#### Scenario: A failed load

- **WHEN** the gadget fails to load or to read the data
- **THEN** the text stays visible and the page shows no script error
