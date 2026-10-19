## ADDED Requirements

### Requirement: Ways carry their rank and their facts

Each way whose needs all have a tier SHALL carry its tier and depth, ordered as first ways are chosen, and each way SHALL keep the clean facts that produced it. A node's first way SHALL have the node's tier and the lowest rank among its ways.

#### Scenario: The arena's first fee

- **WHEN** reading the ways to Vithean Arena Fee (1)
- **THEN** the Planar Stone trade of An Arena Token has the lowest rank and keeps its quest reward acquisition as its fact
- **AND** the round 8 chest and the Master of Battle's buy-back rank after it

#### Scenario: A way that cannot be reached

- **WHEN** a way needs a node without a tier
- **THEN** the way has no rank

### Requirement: Random listings are no way

The requirement graph SHALL NOT give an item a way through the Auction House, because simulated players list random stock that no player can plan on. Reference views that list where an item can appear MAY still show the Auction House.

#### Scenario: An item the Auction House also lists

- **WHEN** reading the ways to Remnants of a Daydream
- **THEN** every way is a drop in Mysterious Portal (2) and none names the Auction House

#### Scenario: An item only the Auction House lists

- **WHEN** an item's only player acquisition is an Auction House listing
- **THEN** the item has no way and no tier

### Requirement: Travel routes give zones their ways

A zone's ways SHALL come from the travel routes that lead to it: a zone line with its gates, and a spell that switches scenes, which needs the spell and, when it works in one zone only, that zone. A spell SHALL need the items that cast or teach it. A route to a saved place, such as a bind point, SHALL give no way. The requirement graph SHALL NOT give a way through being jailed, because a punishment is no plan.

#### Scenario: The Dimensional Rift

- **WHEN** reading the ways to Azynthi's Garden (Dimensional Rift)
- **THEN** one way casts Dimensional Rift in Azynthi's Garden, and the spell needs the Azynthian Riftstone

#### Scenario: Prison

- **WHEN** reading the ways to Prison
- **THEN** it has none, although the travel routes record the jailings that send a player there
