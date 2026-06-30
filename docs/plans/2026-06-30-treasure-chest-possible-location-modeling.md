---
title: Treasure Chest Possible-Location Modeling
type: spec
status: active
created: 2026-06-30
---

# Treasure Chest Possible-Location Modeling

**Goal:** Model Lost Treasure chest prefabs as possible spawns at exported treasure locations without pretending that every possible chest is currently spawned.

## Problem

`PlayerControl.LeftClick()` instantiates one of `GameData.Misc.TreasureChest0_10`, `TreasureChest10_20`, `TreasureChest20_30`, or `TreasureChest30_35` at the clicked treasure marker position. `TreasureLoc` objects already export possible treasure coordinates, and `TreasureHunting` exports the zone/tier selection rules.

The current fixed `character_spawns` model is not sufficient: a treasure chest is spawned only after the player has an active treasure hunt and clicks the selected marker. However, the possible positions are known and already exported.

## Desired model

Represent treasure chests as possible-location spawns, separate from fixed active spawn rows.

A likely clean table shape:

```text
treasure_chest_possible_spawns
- chest_character_stable_key
- treasure_location_stable_key
- level_min
- level_max
- scene
- x
- y
- z
```

The level bracket maps the four chest prefabs to the player's level bracket used by `PlayerControl.LeftClick()`.

## Rendering semantics

- Wiki pages can list treasure chest loot as obtainable through treasure hunting.
- The map can render treasure locations as treasure locations, not ordinary always-present character spawn pins.
- Character pages can link to possible treasure locations or to the treasure-hunting system, depending on downstream UX.

## Acceptance

- The four Lost Treasure chest characters no longer appear as unresolved orphans.
- Treasure chest possible locations are modeled separately from fixed `character_spawns`.
- Existing `treasure_locations` and `treasure_hunting` exports are reused rather than duplicated.
- `Misc.TreasureChest0_10`, `TreasureChest10_20`, `TreasureChest20_30`, and `TreasureChest30_35` are no longer explained as having no fixed positions; their possible marker positions are represented explicitly.
