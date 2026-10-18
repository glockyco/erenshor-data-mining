## ADDED Requirements

### Requirement: Ways that repeat their node are marked

A way SHALL be marked as repeating its node when one of its needs can only be reached through that node. Each way SHALL keep the clean facts that produced it. No first way SHALL repeat its node.

#### Scenario: The arena's first fee

- **WHEN** reading the ways to Vithean Arena Fee (1)
- **THEN** the round 8 chest's way and the Master of Battle's buy-back are marked as repeating
- **AND** its first way trades a Planar Stone through An Arena Token and is not marked

#### Scenario: A later fee

- **WHEN** reading the ways to Vithean Arena Fee (7)
- **THEN** its first way is the round 6 chest, which needs earlier rounds and is not marked
- **AND** the Master of Battle's buy-back is marked as repeating
