## MODIFIED Requirements

### Requirement: A barrier is one node for everything it guards

Each door or other barrier that a gate names SHALL be one node whose ways are its opening conditions. Each target that the barrier guards SHALL need that node instead of repeating its conditions. A barrier opened by player speech SHALL record its spoken phrase and the zone containing its trigger as one opening need, not as NPC dialogue.

#### Scenario: A keyed door

- **WHEN** reading the door between Braxonian Desert and Fallen Braxonia
- **THEN** its way needs the Ancient Braxonian Key
- **AND** the zone line through it needs the door

#### Scenario: A wall opened by speech

- **WHEN** reading the moved wall in Glowmere Grotto
- **THEN** its way needs the player to say `respite` at the wall in Glowmere Grotto
- **AND** the placement inside the hidden room needs the wall
- **AND** the exterior zone lines into Glowmere Grotto do not need the wall
