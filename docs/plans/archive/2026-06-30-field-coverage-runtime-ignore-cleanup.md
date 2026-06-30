---
title: Field-Coverage Runtime Ignore Reason Cleanup
type: plan
status: implemented
created: 2026-06-30
archived: 2026-06-30
---

# Field-Coverage Runtime Ignore Reason Cleanup

**Goal:** Replace broad ignored-field reasons with precise, code-backed reasons for reviewed runtime, component-reference, visual, and already-handled fields.

**Scope:** This plan covers manifest reason cleanup only. It does not add DB columns or exporter rows.

## Tasks

### Task 1: Update LootTable runtime reasons

- [x] Keep `LootTable.ActualDropsQual`, `LootTable.MyGold`, and `LootTable.qualUps` ignored.
- [x] Update reasons to cite runtime generation in `LootTable.InitLootTable()` and `LootWindow` quantity handling.
- [x] Keep `LootTable.MinGold` and `LootTable.MaxGold` out of this cleanup because they are covered by a separate export plan.

### Task 2: Update SpawnPoint runtime reasons

- [x] Keep live/runtime state fields ignored: `NPCCurrentlySpawned`, `SpawnIteration`, `SpawnedNPC`, `actualSpawnDelay`, and `canSpawn`.
- [x] Clarify `SpawnPointIgnoresPastData` as save-state/respawn behavior rather than spawn identity.
- [x] Leave `EssentailSpawnPoints` out of this cleanup because it is covered by a separate modeling decision.

### Task 3: Update Character runtime and component-reference reasons

- [x] Keep component references ignored: `MyNPC`, `MySkills`, `MySpells`, `MyStats`, `MyCap`, and `MyAEEvent`.
- [x] Keep runtime combat/proximity/cache fields ignored: `Alive`, `LastHitBy`, `Master`, `MyAggro`, `MyCharmedNPC`, `NearbyDoors`, `NearbyEnemies`, `NearbyFriends`, `RecentDirectHit`, `Relax`, `TempFaction`, `UnderThreat`, `contributedDPS`, `savedCorpse`, `lootAlert`, and `trailerRecord`.
- [x] Clarify `factionMods` as already handled through `ModifyFaction` component export.
- [x] Clarify `MiningNode` as handled by the dedicated mining-node exporter.

### Task 4: Update Misc audio reasons

- [x] Keep `Misc.DropItem` and `Misc.CombatStartSound` ignored as `AudioClip` references.
- [x] Ensure treasure chest fields are not changed here because they are covered by the treasure chest possible-spawns spec.

### Task 5: Validate manifest-only cleanup

- [x] Run the field-coverage precondition or `uv run erenshor -V playtest extract export` to verify the manifest remains valid.
- [x] Run focused tests only if parser/tool behavior changes.

## Acceptance

- Reviewed ignored fields have precise reasons tied to game-code behavior or existing exporter coverage.
- No export/schema behavior changes are made by this plan.
- The field-coverage gate remains green for playtest.
