# Spec Delta

## MODIFIED Requirements

### Requirement: Raid scene and boss identification

A raid scene SHALL be a scene whose PlanarMusicManager lists boss spawn points, a scene with an active raid event controller that names a boss spawn point, or the scene of Vitheo's arena. The game names a raid boss when the character spawns at a PlanarMusicManager's BigBossSpawn or MidBossSpawns, spawns at the boss point named by an active raid event controller, or fights in an arena round that starts boss music (rounds 2, 5, 7, and 8). A hostile character that spawns only in raid scenes SHALL be `boss` when the game names it as a raid boss, and `enemy` otherwise.

#### Scenario: Add in a raid fight

- **WHEN** a fight script in a raid plane spawns a character that the raid boss rules do not name as a boss
- **THEN** its tier is `enemy`, whatever its BossXp

#### Scenario: Raid mid-boss

- **WHEN** a character spawns at a spawn point in a PlanarMusicManager's MidBossSpawns
- **THEN** its tier is `boss`

#### Scenario: Raid event boss and its adds

- **WHEN** a raid event controller names a boss spawn point absent from the PlanarMusicManager lists and names separate spawn points for its adds
- **THEN** the boss point's hostile character is `boss`
- **AND** the adds are `enemy` unless another raid boss rule names them
