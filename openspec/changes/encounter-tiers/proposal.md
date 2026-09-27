## Why

The wiki, the map and the companion mod each decide what a boss is, and they disagree. The wiki calls a character a Boss when it has exactly one spawn placement, so event-spawned bosses such as Shivunax, Monarch of the Flame and Astra show as Enemy. The live map and the companion mod call a character a boss when its BossXp is above 1, the game's own signal ("This opponent looks unique, and may have special abilities"). The rare flag used for the Rare type only says that a character sits in a spawn point's rare list. Its chance is often higher than common spawns elsewhere (122 rare placements have 25% or more, 57 common placements have 10% or less), so it does not tell a reader how rare a character is.

## Goals

- One classification of every character, computed once in the clean database and read by the wiki, the map, and the sheets.
- The classification follows the game's BossXp signal and separates bosses from roaming named characters.

## Non-Goals

- Changing spawn chances or the per-placement rare-list flag in `character_spawns`, which stay as game facts.
- Changing the companion mod protocol.

## What Changes

- The clean database gains `characters.encounter_tier` with the values `npc`, `boss`, `elite`, and `enemy`. Effective BossXp is the prefab BossXp, raised to 2 at level 40 and above as the game's NPC start-up does.
  - `npc`: friendly characters.
  - `boss`: effective BossXp above 1 with at most one ordinary spawn placement (including only event spawns), or exactly one ordinary placement.
  - `elite`: effective BossXp above 1 with several ordinary spawn placements.
  - `enemy`: every other hostile character.
- **BREAKING** The character-level `is_unique`, `is_rare`, and `is_common` columns leave the clean database. The Rare type and its category go.
- The wiki type field shows Boss, Elite, Enemy, or NPC. Pages get Category:Bosses or Category:Elites.
- The map labels, colours, sorts, and filters characters by tier instead of unique/rare. Live markers take the tier of the character with the same name when one exists.
- The spawn-points sheet shows the tier.
- A code fact pins the level-40 BossXp rule and the BossXp threshold of the consider text.

## Capabilities

### New Capabilities

- `encounter-tiers`: how a character's tier is derived and which consumers read it.

### Modified Capabilities

None.

## Impact

- **Code:** `src/erenshor/application/processor/characters.py` and `writer.py`, the wiki character generators and Lua exporters, `wiki/modules/Erenshor/Character.lua`, `wiki/templates/Character.wiki`, map database queries and components, `spawn-points.sql`, the golden query, the map fixture schema.
- **Wiki:** Category:Elites is a new category. Pages that were Rare become Enemy or Elite.
- **Baselines:** wiki, sheets, and map golden files change and need review.
