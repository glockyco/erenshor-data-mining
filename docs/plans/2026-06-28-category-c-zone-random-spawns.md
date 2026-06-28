---
title: Category C — Zone-Wide Random Spawners
type: note
status: active
created: 2026-06-28
parent: 2026-05-28-dynamic-spawn-coverage-design
---

# Category C — Zone-Wide Random Spawners

Deferred follow-up from the dynamic spawn coverage work
(`2026-05-28-dynamic-spawn-coverage-design`, archived). Categories A (direct
event-script spawns) and B (chained `Spawns[]`) shipped; Category C —
characters placed by zone-tick random spawners — was explicitly out of scope.
Captured here so the scope and entry points aren't lost; graduate to a spec or
plan when prioritized.

## What's deferred

The Sivakayan spectre family is placed by `ZoneAnnounce.SpawnSivakayanSpecter`,
which reads `Misc.SivakayanSpectres[]` and instantiates one spectre at a random
point once per scene per tick under low odds — a *zone-wide random* placement,
not a fixed `SpawnPoint` and not a deterministic event-script spawn. Five
characters are affected (current `playtest`):

- Sivakayan Shadow — `character:24 - sivakayan spectre`
- Shrouded Sivakayan — `character:28 - sivakayan spectre`
- Sivakayan High Shadow — `character:32 - sivakayan spectre`
- Sivakayan Doomshade — `character:36 - sivakayan spectre`
- Sivakayan Voidmaster — `character:39 - sivakayan spectre`

They are the residual "needs investigation" orphans `audit_spawn_coverage.py`
reports after A+B coverage, alongside the four runtime-positioned Lost Treasure
chests (handled separately as wiki-visible / map-hidden).

## Current handling

`dynamic-spawn-catalog.toml` denies the source field so the fail-fast gate
stays green:

```toml
[[denied]]
script = "Misc"
fields = ["SivakayanSpectres"]
reason = "category-c-pending: zone-wide random spawner; needs zone_random_spawns table in follow-up plan."
```

Keep it `denied`, not uncataloged (uncataloged would fail the gate) and not
`allowed`: the `character_spawns` emission models a fixed `(scene, x, y, z)`
placement, which is wrong for a random per-tick spawn.

## Why it needs its own design

A `character_spawns` row implies a fixed location; a zone-wide random spawner
has none. The right model is a per-zone "may appear in {zone}" relationship,
not one row per `SpawnPoint` × prefab. That needs:

1. **A `zone_random_spawns` table** — `(character_stable_key, zone_stable_key,
   source_script, odds?)`, populated by extending `DynamicSpawnSourceListener`
   (or a dedicated listener) to read `Misc.SivakayanSpectres[]` and resolve the
   zones `ZoneAnnounce` runs in.
2. **A wiki/map renderer** — "May appear in {zone}" on the character page and a
   zone-level annotation, distinct from the fixed-marker spawn rendering.

## Entry points

- `Misc.cs` — `SivakayanSpectres[]` field.
- `ZoneAnnounce.cs` — `SpawnSivakayanSpecter` (random point, per-scene tick,
  low odds).
- Original orphan taxonomy and audit method:
  `docs/plans/archive/2026-05-28-spawn-coverage-audit.md`.
- Listener architecture: `skill://unity-export-system`. Audit workflow and the
  catalog gate: `skill://auditing-spawn-coverage`.

## Acceptance (when graduated)

- `zone_random_spawns` populated for the five Sivakayan spectres across the
  zones `ZoneAnnounce` covers.
- The five no longer surface as "needs investigation" orphans in
  `audit_spawn_coverage.py`.
- Character pages and the map render the "may appear in {zone}" relationship.
- `Misc.SivakayanSpectres` moves off `denied` (allowed, or handled by the new
  listener) with the gate still green.

## Related residual — treasure hunting chests (handled, not deferred)

The four Lost Treasure chests (`character:treasurechest 0-10 1`, `10-20 1`,
`20-30 1`, `30-35`) are the other half of the nine "needs investigation"
orphans, but they are **not** Category C and need no follow-up. They spawn from
`PlayerControl.LeftClick()` at the clicked treasure-marker position —
player-triggered, not a zone tick — so there is no fixed coordinate and no
"may appear in {zone}" probability to model. They are resolved in `mapping.json`
as wiki-visible / map-hidden (`mapping_type = "dynamic_spawn"`): loot tables
ship to the wiki, the map omits them. The only open idea, if ever wanted, is a
separate treasure-hunting map/zone feature — distinct from this note and not
currently scoped.
