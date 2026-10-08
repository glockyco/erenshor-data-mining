# Spec Delta

## Evidence

This modifies the existing requirements at `openspec/specs/map-site-data/spec.md:8-25,72-92`. Current name-only candidate and loot behavior is in `src/maps/src/lib/map/character-details.ts:28-71`, `src/maps/src/lib/components/map/popups/LiveNpcPopupContent.svelte:17-33,59-77`; data is prerendered by `src/maps/src/lib/map-world-data.server.ts:568-605`. Runtime names differ from curated names because extraction uses game statistics (`src/mods/InteractiveMapCompanion/src/Entities/EntityExtractor.cs:16`, `variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/NPC.cs:518`) while the current name index uses `display_name` (`src/maps/src/lib/database.base.ts:1463`). Export provenance and variants are defined by `src/Assets/Editor/StableKeyGenerator.cs:155-183`; the existing 2 m placement policy is `src/mods/AdventureGuide/src/Navigation/DirectPlacementPolicy.cs:25-27`. The new behaviors below are proposed changes.

## MODIFIED Requirements

### Requirement: Legacy companion interfaces keep working

Every interface that a shipped companion mod build uses SHALL keep its behavior: the `/map` document on both hosts with its `layers` and `sel` query parameters, including layer keys that earlier site versions wrote, the live-entity WebSocket messages on port 18585 for `/map`, the player-position WebSocket messages on port 18584 for `/maps/[mapName]`, and the `/db/erenshor.sqlite` resource. Optional NPC identity enrichment SHALL NOT become a connection or entity-display prerequisite.

#### Scenario: A shipped overlay hides the spawn markers

- **WHEN** a companion overlay loads `/map?layers=-sp,-spr,-spu,-npc` on either host
- **THEN** the enemy, elite, boss, and NPC spawn layers are hidden

#### Scenario: An older mod reports a live enemy with a rarity

- **WHEN** the companion mod sends a live enemy with `rarity` set to `boss` or `rare` and no stored tier matches its name
- **THEN** the map shows the enemy as a boss or an elite

#### Scenario: The retired zone map mod sends a player position

- **WHEN** a zone page receives a player-position message on port 18584
- **THEN** the page shows the player marker at that position

#### Scenario: A legacy entity protocol omits identity

- **WHEN** a shipped companion sends usable handshake and entity snapshots without `characterOrigin`, including protocol `0.2.0`
- **THEN** the connection continues despite the non-fatal version mismatch warning
- **AND** NPC markers and popups remain usable through runtime-name and scene-based fallback
- **AND** layer/selection query behavior and the existing database URL remain usable on both hosts

### Requirement: Popups show details from the prerendered page data

The world map popups SHALL take drops and vendor stock from the prerendered `/map` data, without a further request. They SHALL show the same items that the map item search shows: items that the mapping hides from the map SHALL NOT appear. Live NPC popups SHALL prefer a uniquely resolved exported character's own drops; when identity is unresolved, they SHALL disclose that and show scene-preferred runtime-name candidates rather than claim exactness.

#### Scenario: A spawn-point popup opens

- **WHEN** a visitor opens the popup of a spawn point
- **THEN** the popup shows each character's drops, ordered by drop chance from high to low and then by item name
- **AND** the popup shows the vendor stock of each vendor character, including items that a quest unlocks for that vendor, ordered by item name
- **AND** the page makes no network request for this content

#### Scenario: A drop is hidden from the map

- **WHEN** a character drops an item whose mapping hides it from the map
- **THEN** the character's popup does not list that item

#### Scenario: A live entity has a name that several characters share

- **WHEN** the companion reports a live entity with unresolved identity whose runtime NPC name belongs to several map-visible characters
- **THEN** the popup combines the drops of the candidates that are placed in the live scene
- **AND** the popup combines the drops of all candidates with that runtime name when none is placed in the live scene
- **AND** the popup discloses unresolved identity and the candidate count when multiple candidates remain
- **AND** differing chances for a shared item retain the existing range presentation

#### Scenario: A prefab origin resolves exactly

- **WHEN** a supported prefab origin matches exactly one exported prefab-style character by original object name
- **THEN** the popup shows only that raw character key's map-visible drops
- **AND** it prints plain percentages, ordered by chance descending and then item name
- **AND** it does not show a shared-name or unresolved-identity note
- **AND** it performs no content or database request

#### Scenario: A placed origin resolves exactly

- **WHEN** a supported placed origin's captured scene matches the live zone and exactly one exported character with that scene and original object name is within 2 m in three-dimensional distance of the captured starting position
- **THEN** the popup shows only that placed character's map-visible drops with plain percentages
- **AND** the result is unchanged when the live NPC moves
- **AND** a character at the same coordinates in another scene is not a match

#### Scenario: Export variants or nearby placements are ambiguous

- **WHEN** a prefab origin matches multiple raw exported rows, or multiple placed rows satisfy the origin's object-name, scene and 2 m placement match
- **THEN** the popup uses the unresolved name-based fallback
- **AND** it does not prefer the unsuffixed key, the first row, the nearest placement or a matching display name as an exact answer

#### Scenario: An unknown origin has a known runtime name

- **WHEN** origin is absent, malformed, unsupported, unmatched or associated with a different live scene, but name-based candidates exist
- **THEN** the popup uses the scene-preferred name-based candidates and explicitly labels identity unresolved
- **AND** it does not interpret missing loot rows as proof that a proposed identity exists

#### Scenario: Curated and runtime names differ

- **WHEN** a legacy companion reports an NPC's runtime name and the corresponding map-visible character has a different curated display name
- **THEN** the fallback finds it by runtime NPC name
- **AND** presentation names are not substituted into the identity lookup

#### Scenario: A known exact character has no visible drops

- **WHEN** origin uniquely resolves a catalog character whose map-visible drop list is empty
- **THEN** the popup says “No map-visible drops recorded.”
- **AND** it does not substitute the drops of another character with the same runtime name

#### Scenario: No exported fallback candidate exists

- **WHEN** identity cannot resolve and the runtime-name index has no matching candidate
- **THEN** the popup discloses unresolved identity and says “No matching character data.”
- **AND** it does not invent a loot list or claim that the NPC cannot drop anything

#### Scenario: A single name-based candidate remains

- **WHEN** identity cannot resolve but scene-preferred name lookup returns only one candidate
- **THEN** the popup can show that candidate's plain percentages
- **AND** it still labels identity unresolved rather than treating candidate count as proof of provenance
