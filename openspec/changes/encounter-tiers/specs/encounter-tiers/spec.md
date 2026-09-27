## ADDED Requirements

### Requirement: Every character has one encounter tier

The clean database SHALL store one encounter tier per character: `npc`, `boss`, `elite`, or `enemy`. Effective BossXp SHALL be the prefab BossXp, raised to 2 when the character's level is 40 or higher. Members of one deduplication group SHALL share the tier computed from all their spawns. Friendly characters SHALL be `npc`. A hostile character SHALL be `boss` when its effective BossXp is above 1 and it has at most one ordinary spawn placement, or when it has exactly one ordinary spawn placement. A hostile character with effective BossXp above 1 and several ordinary placements SHALL be `elite`. Every other hostile character SHALL be `enemy`.

#### Scenario: Event-spawned boss

- **WHEN** a hostile character has BossXp 3 and appears only through an event script
- **THEN** its tier is `boss`

#### Scenario: Roaming named character

- **WHEN** a hostile character has BossXp 5 and 14 ordinary spawn placements
- **THEN** its tier is `elite`

#### Scenario: Level 40 character without BossXp

- **WHEN** a hostile level-42 character has BossXp 0 and 20 ordinary placements
- **THEN** its tier is `elite`

#### Scenario: Single placement without BossXp

- **WHEN** a hostile character has BossXp 0 and exactly one ordinary placement
- **THEN** its tier is `boss`

### Requirement: Consumers read the stored tier

The wiki type field, the wiki character categories, the map labels, colours, filters and sort order, and the spawn-points sheet SHALL derive from the stored tier and SHALL NOT recompute it. A Boss page SHALL carry Category:Bosses, and an Elite page Category:Elites.

#### Scenario: Wiki page of an elite

- **WHEN** the wiki page of an `elite` character is generated
- **THEN** its type is Elite and it carries Category:Enemies and Category:Elites

### Requirement: The game rules behind the tier are pinned

The code-facts registry SHALL assert the level-40 BossXp rule and the BossXp threshold of the consider text, so a game change to either stops the refresh.

#### Scenario: Game changes the level threshold

- **WHEN** a game update changes the level at which NPCs receive BossXp 2
- **THEN** `extract code-facts` fails and names the fact
