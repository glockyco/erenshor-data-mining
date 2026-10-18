## Purpose

Shows on the wiki what each zone, quest, item, and character copy of the current build needs and what each unlocks, drawn from the relations that the clean database records.

## ADDED Requirements

### Requirement: The graph holds the progression relations of the clean database

The data module `Module:Erenshor/Data/Progression` SHALL hold a node for every quest and zone, every subject of a gate, every item that a quest, craft, gate, or turn-in produces, and every node that these need, transitively. Each relation SHALL come from a clean database fact. The module SHALL hold no relation that the clean database does not record.

#### Scenario: A raid plane

- **WHEN** the graph is generated from the current main build
- **THEN** Brax's Plane of Elements has one way
- **AND** that way needs Reliquary Hall and Rune of Elements in the planning table's slot for that portal

#### Scenario: A keyed zone

- **WHEN** reading Fallen Braxonia
- **THEN** its way needs Braxonian Desert and the Ancient Braxonian Key

#### Scenario: A ritual portal

- **WHEN** reading Mysterious Portal (1)
- **THEN** its way needs The Duskenlight Coast and The Duskenlight Ritual done

#### Scenario: A vendor unlock

- **WHEN** reading Azynthian Resting place
- **THEN** one of its ways needs Breena Carpenter, who sells it, and Crafting: Azynthian Resting Place done

### Requirement: Ways are alternatives and their needs are joint

Each node SHALL list its ways as alternatives, and every need of a way SHALL be required. Independent gates on one subject SHALL apply to every way of that subject, and the alternative groups of one gate SHALL become separate ways. The interchangeable rune slots of the planning table SHALL yield one way for each rune, not one for each slot.

#### Scenario: Leaving Stowaway's Step

- **WHEN** reading Hidden Hills
- **THEN** three of its ways start in Stowaway's Step
- **AND** they need The Game Continues... held, A Way To Erenshor done, and Wyland's Note done, one each

#### Scenario: A rune portal

- **WHEN** reading Braxonian Desert
- **THEN** exactly one of its ways needs Reliquary Hall and Rune of Sands in a rune slot of the planning table

### Requirement: A quest needs only a completion route

A quest SHALL be done through any of its completion routes. A route SHALL need its source, the required items of its resource variant, and the route's own conditions. The acquisition of a quest SHALL NOT be a need, because the game completes a quest that is not in the journal. When completing one quest also completes another, the other quest SHALL list that way with the condition that it is active.

#### Scenario: A turn-in quest

- **WHEN** reading Repairing Orion's Ring, Part 2
- **THEN** it has two ways, turning in Unsocketed Ring, Elderstone Shard, and Chunk of Citrine Sandsilver to Parmalee Gemlyn or to Violet Smithfield
- **AND** neither way needs Repairing Orion's Ring, whose completion assigns it

#### Scenario: A quest completed by another

- **WHEN** reading The Loss Stone Pt. 2
- **THEN** one of its ways needs Completing the Ritual and says that The Loss Stone Pt. 2 must be active

#### Scenario: A scripted completion

- **WHEN** reading She Sees You
- **THEN** its way says that a scripted event completes it and names no source, because the export records the script and no source

### Requirement: Character copies carry their own places and loot

A character node SHALL be the exact copy that the game places or spawns, labelled with the copy's name and linked to its article. Its ways SHALL be its placements, each with the zone and the gates of that placement. An item's way SHALL name the copy that drops, sells, or gives the item.

#### Scenario: A boss copy

- **WHEN** reading Eldrich Crystal
- **THEN** one way needs the Azynthian Keeper copy that drops it
- **AND** that copy's way needs Secluded Sanctuary

#### Scenario: A summoned boss

- **WHEN** reading Candlekeeper
- **THEN** its way needs Braxonian Desert and A Strange Figurine, which summons it

### Requirement: A kill release belongs to the kill

When a character is invulnerable until a turn-in or another kill releases it, the release SHALL be a need of each way that requires killing that character: its drops, a completion on its death, and an encounter won. Ways that only meet the character SHALL NOT need the release.

#### Scenario: Stardust

- **WHEN** reading the item Stardust
- **THEN** its way from the Stardust character needs Lost Faith, turned in to make the character vulnerable
- **AND** the quest Lost Faith, turned in to that character, does not need the release

#### Scenario: A release without an item

- **WHEN** reading Ancient Braxonian Key
- **THEN** its way from Evadne says that she is vulnerable only while it rains
- **AND** it names no item that the clean database does not link to the rain

### Requirement: Only usable paths count

The graph SHALL leave out zone lines whose destination is saved state, inactive zone lines without a recorded activation, ways that a gate makes impossible, and sources that no player can use. A node without a way SHALL say that the game data records none.

#### Scenario: A saved-return portal

- **WHEN** reading Hidden Hills
- **THEN** no way passes through the Reliquary Hall exit, which returns the player to the zone they came from

#### Scenario: A node without a way

- **WHEN** a target has no way in the data
- **THEN** its rendering says that the game data records no way to reach it

### Requirement: Generation fails on facts that it cannot represent

`wiki generate-lua` SHALL fail and name the node and the fact when it meets an acquisition kind, a completion method, a gate atom kind, or a release mechanism that the view does not map, a key that resolves in neither the link catalog nor the native identity catalog, a node with more ways than the expansion limit, or a module above its page budget.

#### Scenario: An unmapped gate atom

- **WHEN** the clean database holds a gate atom kind that the view does not map
- **THEN** generation fails and names the subject, the gate, and the atom kind

#### Scenario: An unresolved key

- **WHEN** a way needs a key that neither catalog holds
- **THEN** generation fails and names the node, the way, and the key

### Requirement: A page renders a target's requirements as text

`{{Progression graph}}` SHALL take its target from `stablekey`, or else from the one entity whose page is the current page. It SHALL render the target's ways and needs as nested lists that link each node and work without JavaScript. A node already shown SHALL be referenced instead of repeated. A target without data SHALL show a message and join the category `Pages with missing Erenshor progression data`.

#### Scenario: A zone page

- **WHEN** the template is placed without arguments on the Fallen Braxonia page
- **THEN** it lists the way through Braxonian Desert with the Ancient Braxonian Key and links both pages

#### Scenario: Several entities on one page

- **WHEN** the template is placed without `stablekey` on a page that two entities share
- **THEN** it shows an error that lists both stable keys

#### Scenario: A key without data

- **WHEN** `stablekey` names an entity that the data module lacks
- **THEN** the template says that the data is missing and adds the tracking category

### Requirement: The explorer draws and navigates the graph

With the gadget, the template SHALL draw its target's requirements as a graph. The reader SHALL be able to search every node by name, focus any node, switch between what a node needs and what it unlocks, expand and collapse nodes, and open each node's page. Every action SHALL work with the keyboard. When the gadget cannot draw, the text rendering SHALL stay visible.

#### Scenario: Focus by search

- **WHEN** a reader searches for Rune of Elements and selects it
- **THEN** the graph shows A Lost Portal Pt. 2, whose reward it is, turned in to the Elemental Energy with Inert Rune of Brax and Eldrich Crystal

#### Scenario: What a key unlocks

- **WHEN** the reader shows what the Ancient Braxonian Key unlocks
- **THEN** the graph shows Fallen Braxonia

#### Scenario: Keyboard focus

- **WHEN** a reader moves to a node with the Tab key and presses Enter
- **THEN** the graph focuses that node

#### Scenario: A failed load

- **WHEN** the gadget fails to load or to read the data
- **THEN** the nested lists stay visible and the page shows no script error

### Requirement: The default view collapses navigation and common sources

The explorer SHALL expand quests, gates, and the items that they need. It SHALL show the gate-free entrances of a zone and the sources of an item beyond the first four as collapsed groups that the reader can expand.

#### Scenario: A common ingredient

- **WHEN** the explorer shows what Mysterious Portal (1) needs
- **THEN** Wolf Meat shows its first sources and a collapsed group of the rest

### Requirement: The clean database holds the facts that only the guide held

The clean build SHALL record the entry condition of Jaws of Sivakaya, the gate before Vessel Siraethe, the angel statue before Shivering Tomb (2), the planning table's dependence on Claiming the Reliquary, and the Dimensional Rift between the two Azynthi's Garden scenes. The graph and every other consumer SHALL read them from the clean database.

#### Scenario: The planning table

- **WHEN** reading Brax's Plane of Elements
- **THEN** its way also needs the condition under which the planning table exists

#### Scenario: The rift

- **WHEN** reading Azynthi's Garden (Dimensional Rift)
- **THEN** a way needs Azynthi's Garden and the Azynthian Riftstone
