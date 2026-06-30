---
title: Death-Triggered Spawn Modeling
type: spec
status: active
created: 2026-06-30
---

# Death-Triggered Spawn Modeling

**Goal:** Model characters spawned when another character dies without treating the child as a fixed direct world placement.

## Problem

`Character.SpawnOnDeath` is a serialized `GameObject` field that `Character.DoDeath()` instantiates at the dying character's transform. `Despawn` also instantiates `Character.SpawnOnDeath` before destroying an object. Some scripts, such as `BraxFightEvent`, assign `SpawnOnDeath` at runtime before the parent dies.

A direct `character_spawns` row for the child is incomplete because the child's position is inherited from the parent character's actual placement. The parent may be placed by a fixed `SpawnPoint`, trigger, dynamic event script, or another derived source.

## Desired model

Death-triggered spawns should be represented as a relationship from parent character to child character, then expanded through the parent's known spawn sources during the clean build.

A likely raw table shape:

```text
character_death_spawns
- parent_character_stable_key
- child_character_stable_key
- source_script
- source_field
```

A clean expansion can mirror chained-spawn expansion: each parent spawn implies a child spawn at the same position, with `source_script` preserving the death-spawn source.

## Runtime-assignment caveat

Serialized `Character.SpawnOnDeath` is only part of the problem. Runtime assignments such as `BraxFightEvent` must be modeled by the script source that performs the assignment, not by blindly reading the prefab field.

## Acceptance

- Serialized `Character.SpawnOnDeath` relationships are exported without pretending they are direct placements.
- Runtime assignments that change `SpawnOnDeath` are either exported by explicit script handling or documented as unsupported with a failing audit finding.
- Clean `character_spawns` includes expanded death-spawn rows where the parent has known placement.
- The orphan audit no longer reports children whose only valid source is a modeled death-spawn parent.
- `field-coverage.json` no longer classifies `Character.SpawnOnDeath` as a simple ignored field.
