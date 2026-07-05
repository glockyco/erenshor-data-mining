---
title: Essential SpawnPoint Relationship Modeling
type: spec
status: implemented
created: 2026-06-30
archived: 2026-07-05
---

# Essential SpawnPoint Relationship Modeling

**Goal:** Decide whether `SpawnPoint.EssentailSpawnPoints` should be exported as an encounter relationship between spawn points.

## Problem

`SpawnPoint.EssentailSpawnPoints` is a serialized list of other `SpawnPoint` components. It is used by scripts such as `HardSetStats`, `NPCShoutListener`, and `ReliquaryFiend` to inspect related spawns during encounter logic. It is not live spawn state, and it is not a direct character placement by itself.

Ignoring it as generic spawn-point runtime state loses a possible encounter relationship. Exporting it as a character spawn row would be wrong.

## Desired model

If useful, export it as a spawnpoint-to-spawnpoint relationship, not as a character placement.

A likely table shape:

```text
spawnpoint_essential_links
- source_spawn_point_stable_key
- essential_spawn_point_stable_key
- source_scene
```

Downstream processors can join those spawn points to their possible characters where needed.

## Acceptance

- `EssentailSpawnPoints` is classified with a precise decision: exported relationship, or ignored with a code-backed reason.
- If exported, relationship rows reference existing spawn point stable keys.
- No additional `character_spawns` rows are created directly from this field.
- Encounter consumers can opt into the relationship without changing ordinary spawn rendering.
