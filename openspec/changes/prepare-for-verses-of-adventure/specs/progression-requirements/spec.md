## MODIFIED Requirements

### Requirement: A barrier is one node for everything it guards

Each door or other barrier that a gate names SHALL be one node whose ways are its opening conditions. A reviewed door SHALL have a node even when no tracked target depends on it. Each target that a barrier guards SHALL need that node instead of repeating its conditions. A barrier opened by player speech SHALL record its spoken phrase and the zone containing its trigger as one opening need, not as NPC dialogue.

#### Scenario: A keyed door

- **WHEN** reading the door between Braxonian Desert and Fallen Braxonia
- **THEN** its way needs the Ancient Braxonian Key
- **AND** the zone line through it needs the door

#### Scenario: A wall opened by speech

- **WHEN** reading the moved wall in Glowmere Grotto
- **THEN** its way needs the player to say `respite` at the wall in Glowmere Grotto
- **AND** the placement inside the hidden room needs the wall
- **AND** the exterior zone lines into Glowmere Grotto do not need the wall

#### Scenario: A door within a zone

- **WHEN** reading Ripper's Keep's gate
- **THEN** the gate has its own way that needs Ripper's Gate Key
- **AND** neither arrivals in the zone nor the separate ritual portal need the gate

### Requirement: A reviewer can inspect any node

`erenshor progression show <stable key>` SHALL print the node's tier and ways with their needs and names, and the milestones of its first way in tier order. For a zone it SHALL also list local door ways and gated exits separately from arrival ways. For a quest it SHALL also name the holders killed by its exact item-turn-in routes.

#### Scenario: A ritual portal

- **WHEN** a reviewer runs `erenshor progression show zone:duskenportal`
- **THEN** the output lists its way and the milestones of its first way from a start to The Duskenlight Ritual, each with its tier

#### Scenario: A node without a tier

- **WHEN** a reviewer runs `erenshor progression show zone:planeofbrax` while rain in Braxonian Desert has no producer
- **THEN** the output lists the plane's way and says that no way reaches it from the start

#### Scenario: Ripper's Keep

- **WHEN** a reviewer runs `erenshor progression show zone:ripper`
- **THEN** the output lists the portal spell among the arrivals
- **AND** it lists the gate and its key as a local door, not as a condition of entering the zone
- **AND** it lists the exit to Mysterious Portal (3) and its ritual requirement separately

#### Scenario: A turn-in that kills its holder

- **WHEN** a reviewer runs `erenshor progression show quest:flickeringsouls`
- **THEN** the ways still require a turn-in to Flicker of Souls, not a combat kill
- **AND** the output identifies Flicker of Souls as the holder who dies
