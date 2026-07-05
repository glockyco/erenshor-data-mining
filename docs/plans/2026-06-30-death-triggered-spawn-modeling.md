---
title: Death-Triggered Spawn Modeling
type: spec
status: active
created: 2026-06-30
---

# Death-Triggered Spawn Modeling

## Problem

Two fields instantiate characters at a dying parent's position:

1. `Character.SpawnOnDeath` — a `public GameObject` instantiated in `Character.DoDeath()` at the dying character's transform. `Despawn` also instantiates it before destroying the object.
2. `NPCFightEvent.SpawnOnDeath` — a `public List<GameObject>` instantiated in a loop on death, each with a random position offset around the parent. Cleared after use.

Some scripts assign `Character.SpawnOnDeath` at runtime before the parent dies — `BraxFightEvent` (assigns IceGolem/LavaGolem to crystals), `InfernoTwins` (via `RewardListener`), and `FaithTracker` reassign death-spawn-adjacent state. These are the same concept (death-triggered spawns) with different cardinality and different assignment sources.

A direct `character_spawns` row for the child is incomplete because the child's position is inherited from the parent character's actual placement. The parent may be placed by a fixed `SpawnPoint`, trigger, dynamic event script, or another derived source.

## Desired model

Death-triggered spawns are represented as a relationship from parent character to child character, then expanded through the parent's known spawn sources during the clean build. Both the single (`Character.SpawnOnDeath`) and list (`NPCFightEvent.SpawnOnDeath`) variants are modeled.

A likely raw table shape:

```text
character_death_spawns
- parent_character_stable_key
- child_character_stable_key
- source_script                   (BraxFightEvent, NPCFightEvent, etc.)
- source_field                    (Character.SpawnOnDeath | NPCFightEvent.SpawnOnDeath)
- spawn_order                     (0 for single; 0..N index for list variant)
```

A clean expansion mirrors chained-spawn expansion: each parent spawn implies a child spawn at the same position, with `source_script` preserving the death-spawn source. For the list variant, each entry spawns at the parent position plus a runtime random offset, which is documented but not exactly reproducible.

## Runtime-assignment caveat

Serialized `Character.SpawnOnDeath` is only part of the problem. Runtime assignments that change `SpawnOnDeath` before death — `BraxFightEvent` (assigns golem prefabs to crystals), `InfernoTwins`/`RewardListener` (reassigns twin state), `FaithTracker` — must be modeled by the script source that performs the assignment, not by blindly reading the prefab field. Where a runtime assignment cannot be statically resolved, it is documented as an unsupported finding rather than silently dropped.

## Acceptance

- Serialized `Character.SpawnOnDeath` and `NPCFightEvent.SpawnOnDeath` relationships are exported without pretending they are direct placements.
- Runtime assignments that change `SpawnOnDeath` are either exported by explicit script handling or documented as unsupported with a failing audit finding.
- Clean `character_spawns` includes expanded death-spawn rows where the parent has known placement.
- The orphan audit no longer reports children whose only valid source is a modeled death-spawn parent.
- `field-coverage.json` no longer classifies `Character.SpawnOnDeath` as a simple ignored field.
