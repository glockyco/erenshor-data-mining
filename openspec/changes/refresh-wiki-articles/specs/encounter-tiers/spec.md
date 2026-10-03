## MODIFIED Requirements

### Requirement: Every character has one encounter tier

The clean database SHALL store one encounter tier per character: `npc`, `chest`, `boss`, `elite`, or `enemy`. A character of the TreasureChest faction SHALL be `chest`, and a deduplication group that mixes chests and other characters SHALL fail the build. Members of one deduplication group SHALL share the tier computed from all their spawns. Friendly characters SHALL be `npc`. A character SHALL be friendly when its faction is a good faction and its AggressiveTowards list names neither Player nor PC. A raid scene SHALL be a scene whose PlanarMusicManager lists boss spawn points, or the scene of Vitheo's arena. A hostile character that spawns only in raid scenes SHALL be `boss` when the game names it as a raid boss, and `enemy` otherwise. The game names a raid boss when the character spawns at a PlanarMusicManager's BigBossSpawn or MidBossSpawns, or fights in an arena round that starts boss music (rounds 2, 5, 7, and 8). Elsewhere, the rule SHALL read the prefab BossXp, because the game raises the BossXp of every NPC of level 40 or higher. A hostile character SHALL be `boss` when its prefab BossXp is above 1 and it has at most one ordinary spawn placement, or when it has exactly one ordinary spawn placement. A hostile character with prefab BossXp above 1 and several ordinary placements SHALL be `elite`. Every other hostile character SHALL be `enemy`.

#### Scenario: Event-spawned boss

- **WHEN** a hostile character outside the raid scenes has BossXp 3 and appears only through an event script
- **THEN** its tier is `boss`

#### Scenario: Roaming named character

- **WHEN** a hostile character has BossXp 5 and 14 ordinary spawn placements
- **THEN** its tier is `elite`

#### Scenario: Level 40 character without BossXp

- **WHEN** a hostile level-42 character outside the raid scenes has BossXp 0 and 20 ordinary placements
- **THEN** its tier is `enemy`

#### Scenario: Add in a raid fight

- **WHEN** a fight script in a raid plane spawns a character that no PlanarMusicManager list names
- **THEN** its tier is `enemy`, whatever its BossXp

#### Scenario: Raid mid-boss

- **WHEN** a character spawns at a spawn point in a PlanarMusicManager's MidBossSpawns
- **THEN** its tier is `boss`

#### Scenario: Single placement without BossXp

- **WHEN** a hostile character has BossXp 0 and exactly one ordinary placement
- **THEN** its tier is `boss`

#### Scenario: Good-faction character that attacks the player

- **WHEN** a Villager-faction character is aggressive towards Player
- **THEN** it is hostile, and its tier is not `npc`

#### Scenario: Arena award chest

- **WHEN** a TreasureChest-faction character has exactly one ordinary placement
- **THEN** its tier is `chest`, not `boss`

### Requirement: Consumers read the stored tier

The wiki type field, the wiki character categories, the map's NPC, chest, and enemy markers, labels, colours, filters and sort order, and the spawn-points sheet SHALL derive from the stored tier and SHALL NOT recompute it. A Boss page SHALL carry Category:Bosses, an Elite page Category:Elites, and a Chest page Category:Chests. A Chest page SHALL NOT carry Category:Enemies. The map SHALL keep a chest a marker of the enemy category, so that the `sel=enemy:<name>` links of the wiki select it.

#### Scenario: Wiki page of an elite

- **WHEN** the wiki page of an `elite` character is generated
- **THEN** its type is Elite and it carries Category:Enemies and Category:Elites

#### Scenario: Wiki page of a chest

- **WHEN** the wiki page of a `chest` character is generated
- **THEN** its type is Chest and it carries Category:Chests but not Category:Enemies

## REMOVED Requirements

### Requirement: The game rules behind the tier are pinned

**Reason**: The tier no longer reads the level-40 BossXp rule, so the registry no longer asserts it.
**Migration**: The new requirement "The boss markers behind the tier are pinned" asserts the consider threshold and the arena boss rounds.

## ADDED Requirements

### Requirement: The boss markers behind the tier are pinned

The code-facts registry SHALL assert the BossXp threshold of the consider text and the arena rounds that start boss music, so a game change to either stops the refresh.

#### Scenario: Game changes the arena boss rounds

- **WHEN** a game update removes the mid-boss music from an arena round that the rule names
- **THEN** `extract code-facts` fails and names the fact
