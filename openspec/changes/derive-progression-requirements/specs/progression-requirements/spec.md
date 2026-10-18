## Purpose

Derives what each zone, quest, item, and character copy needs from the canonical facts of the clean database, and orders the result as a playthrough from a new character, so that every consumer reads the same requirements.

## ADDED Requirements

### Requirement: The graph holds the progression relations of the clean database

The clean database SHALL hold a requirement graph with a node for every quest and zone, every subject of a gate, every item that a quest, craft, gate, or turn-in produces or needs, and every node that these need, transitively. Each relation SHALL come from a clean database fact. The graph SHALL hold no relation that the clean database does not record.

#### Scenario: A raid plane

- **WHEN** reading Brax's Plane of Elements on the current main build
- **THEN** its way needs Reliquary Hall and Rune of Elements in the planning table's slot for that portal

#### Scenario: A keyed zone

- **WHEN** reading Fallen Braxonia
- **THEN** its way needs Braxonian Desert and the door that the Ancient Braxonian Key opens

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

### Requirement: A quest follows its intended route

A quest's ways SHALL each combine one of its start routes with one of its completion routes, because finishing a quest that was never started skips its story. A quest without a start route SHALL be done through its completion routes alone. When completing one quest also completes another, the other quest SHALL have a way that needs the first while the other is active.

#### Scenario: A chained quest

- **WHEN** reading Repairing Orion's Ring, Part 2
- **THEN** each of its ways needs Repairing Orion's Ring done
- **AND** turns in Unsocketed Ring, Elderstone Shard, and Chunk of Citrine Sandsilver to Parmalee Gemlyn or to Violet Smithfield

#### Scenario: A quest completed by another

- **WHEN** reading The Loss Stone Pt. 2
- **THEN** one of its ways needs Completing the Ritual while The Loss Stone Pt. 2 is active

#### Scenario: A scripted completion

- **WHEN** reading She Sees You
- **THEN** its way says that a scripted event completes it and names no source

### Requirement: Character copies carry their own places and loot

A character node SHALL be the exact copy that the game places or spawns. Its ways SHALL be its placements, each with its zone and the gates of that placement. An item's way SHALL name the copy that drops, sells, or gives it.

#### Scenario: A boss copy

- **WHEN** reading Eldrich Crystal
- **THEN** one way needs the Azynthian Keeper copy that drops it
- **AND** that copy's way needs Secluded Sanctuary

#### Scenario: A summoned boss

- **WHEN** reading Candlekeeper
- **THEN** its way needs Braxonian Desert and A Strange Figurine, which summons it

### Requirement: A kill release belongs to the kill

When a character copy is invulnerable until a turn-in, another kill, or a world state releases it, the release SHALL be a need of each way that requires killing that copy: its drops, a completion on its death, and an encounter won. Ways that only meet the copy SHALL NOT need the release.

#### Scenario: Stardust

- **WHEN** reading the item Stardust
- **THEN** its way from the Stardust character needs Lost Faith turned in to make that character vulnerable
- **AND** the quest Lost Faith, turned in to the same character, does not need the release

#### Scenario: A world state release

- **WHEN** reading Ancient Braxonian Key
- **THEN** its way from Evadne the Corrupted needs rain in Braxonian Desert
- **AND** the rain names only the sources that the clean database records for it

### Requirement: A barrier is one node for everything it guards

Each door or other barrier that a gate names SHALL be one node whose ways are its opening conditions. Each target that the barrier guards SHALL need that node instead of repeating its conditions.

#### Scenario: A keyed door

- **WHEN** reading the door between Braxonian Desert and Fallen Braxonia
- **THEN** its way needs the Ancient Braxonian Key
- **AND** the zone line through it needs the door

### Requirement: Only usable paths count

The graph SHALL leave out zone lines whose destination is saved state, inactive zone lines without a recorded activation, ways that a gate makes impossible, and sources that no player can use. A node without a way SHALL remain in the graph without a way.

#### Scenario: A saved-return portal

- **WHEN** reading Hidden Hills
- **THEN** no way passes through the Reliquary Hall exit, which returns the player to the zone they came from

### Requirement: Nodes have a playthrough tier

Each node SHALL carry the tier of its earliest way from a new character in Stowaway's Step, counting the milestones on that way, and SHALL name the way that achieves it. Negative conditions and the initial account state SHALL hold at the start. Each need of a milestone's first way SHALL have a lower tier than the milestone, and each need of any other node's first way no higher a tier than that node. A node that no way reaches SHALL have no tier.

#### Scenario: The start

- **WHEN** reading Stowaway's Step
- **THEN** its tier is 0

#### Scenario: A raid plane's first way

- **WHEN** reading Brax's Plane of Elements
- **THEN** it has a tier, and its first way needs Rune of Elements in the planning table's slot for that portal

#### Scenario: An unreachable node

- **WHEN** no way reaches a node from the start
- **THEN** the node has no tier

### Requirement: Milestones mark progression steps

A node SHALL be a milestone when it is a quest or a barrier, a zone or character copy whose every way needs a gate, or an item that a gate, a summon, or a release needs or whose every source is a quest reward, a craft, or a gated copy.

#### Scenario: A key and a common ingredient

- **WHEN** reading the Ancient Braxonian Key and Wolf Meat
- **THEN** the key is a milestone and Wolf Meat is not

### Requirement: Ways keep their identity across builds

Each way SHALL have a key derived from its needs, so that an unchanged way keeps its key in the next build and the build-to-build report lists only the ways that changed.

#### Scenario: An added way

- **WHEN** a game update adds one way to a zone and changes nothing else about it
- **THEN** the report lists one added way for that zone and no changed or removed way

### Requirement: Facts that the graph cannot represent fail the build

The clean build SHALL fail and name the node and the fact when it meets an acquisition kind, a route method, a gate atom kind, or a release mechanism that the graph does not map, a need that resolves to no node, or a subject whose gates multiply into more ways than the expansion limit.

#### Scenario: An unmapped gate atom

- **WHEN** the clean database holds a gate atom kind that the graph does not map
- **THEN** `extract build` fails and names the subject, the gate, and the atom kind

### Requirement: A reviewer can inspect any node

`erenshor progression show <stable key>` SHALL print the node's tier and ways with their needs and names, and the milestones of its first way in tier order.

#### Scenario: A raid plane

- **WHEN** a reviewer runs `erenshor progression show zone:planeofbrax`
- **THEN** the output lists its way and the milestones of its first way from Stowaway's Step to Rune of Elements, each with its tier
