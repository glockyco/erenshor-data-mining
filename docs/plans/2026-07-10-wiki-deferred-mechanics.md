---
title: Wiki Deferred Obtainability Mechanics
type: plan
status: active
created: 2026-07-10
parent: 2026-06-23-wiki-cargo-phase-3
---

# Wiki Deferred Obtainability Mechanics

Phase 3 deliberately leaves seven non-standard obtainability and usage paths
outside the item-owned `ObtainedFrom` / `UsedIn` taxonomy. This plan preserves
their implementation requirements so they can be modeled without silently
losing game behavior.

## Tasks

### Task 1: Model smithing merge and forge-box usage

- [ ] Export and represent the Smithing merge/forge-box mechanic, including the
  Merging Vessel requirement, fuel, matching-item inputs, and 15-item quantity
  cap. Add a dedicated relationship type only after the data ownership and
  rendering rules are specified.
- [ ] Add the required `smithing` code facts for hardcoded identifiers and
  drift-gate their exact comparison strings before consuming them.

### Task 2: Export PlanarShard blessing-removal output

- [ ] Add a `smithing.planar_shard_output` code fact for the hardcoded output,
  export the relationship, and render it from the owning page.
- [ ] Add exact-string drift coverage and a Cargo/golden regression fixture.

### Task 3: Export Chessboard candlekeeper mold conversion

- [ ] Export the inspector-set `ReplaceStatue` reference used by the
  Chessboard candlekeeper conversion and represent the one-off mold output.
- [ ] Add a stable source key, generated-page rendering, and parity coverage;
  do not transcribe the inspector value from decompiled source.

### Task 4: Model Time Stone item use

- [ ] Add a `spellvessel.time_stone_id` code fact for the Shivering Tomb 2 /
  Stowaway Portal use path and map it to item-owned `ObtainedFrom` with the
  correct source type.
- [ ] Add exact comparison-string drift coverage, fixture coverage, and a
  golden baseline update.

### Task 5: Model Braxonian Flame Well quality ritual

- [ ] Add a code fact for the offering-stone quality upgrade (quality 2 to 1),
  export its item relationship, and define the reverse display semantics.
- [ ] Add Cargo, parity, and golden regression coverage for the ritual.

### Task 6: Render the runtime global random world-drop pool

- [ ] Define a "may drop globally" relationship for the runtime pool covering
  Maps, Molds, Planar items, and other globally rolled rewards.
- [ ] Consume the existing `loot.world_drop.*` code facts, add a deterministic
  renderer and fixtures, and keep random-pool rows distinct from per-NPC loot.

### Task 7: Render the random fished Map reward

- [ ] Model the 1-in-20 random Map reward from Fishing as a global/random
  source rather than a per-water source.
- [ ] Add the required code fact for the random rule, then cover rendering,
  parity, and golden output without assigning the reward to a specific water.
