---
title: Dynamic Spawn Semantics and Map UX Audit
type: plan
status: active
created: 2026-07-11
parent:
superseded_by:
archived:
---

# Goal

Make dynamic event spawns truthful and usable across export, clean data, maps,
wiki, and sheets without treating event triggers as ordinary world respawns.

## Constraints

- Preserve serialized NPC instantiate coordinates as `spawn_position`.
- Model a distinct event or interaction anchor when the script exposes one.
- Never expose source script filenames in user-facing map or wiki text.
- Dynamic rows remain map-visible unless an explicit mapping rule says otherwise.
- Keep release data refreshes separate from behavior and UX commits.

## Atomic changes

### 1. Overlapping marker presentation

- [ ] Inventory exact-coordinate marker collisions in all configured zones.
- [ ] Define deterministic cluster, spiderfy, or alternate hit-testing behavior.
- [ ] Keep stored and displayed world coordinates truthful while making every
      coincident character selectable.
- [ ] Add map tests for two characters sharing one spawn position and for mixed
      ordinary/dynamic rows.

### 2. Dynamic unique classification

- [ ] Audit every dynamic-only character with explicit prefab rarity flags,
      including Astra, Demented Malaroth, Shivunax, Brax, and all other
      single-spawn candidates.
- [ ] Trace uniqueness to explicit game metadata or an approved mapping rule,
      not dynamic spawn cardinality.
- [ ] Add focused processor and map/wiki regressions for unique, rare, common,
      and mixed ordinary/dynamic groups.
- [ ] Record intentional exceptions in the authoritative mapping or catalog.

### 3. Brax active-versus-unused references

- [ ] Trace both `Brax, God of Elements` references through shipped scripts,
      serialized prefabs, scene placements, and event fields.
- [ ] Determine whether each reference can be active in normal play, requires a
      quest/event state, or is an unused/duplicate asset.
- [ ] Represent active spawn semantics and any conditional state explicitly,
      without deleting evidence or inventing availability percentages.
- [ ] Add a regression covering the final classification and both coordinates.

### 4. Spawn wording and respawn semantics

- [ ] Separate dynamic event labels from automatic zone-entry respawn text.
- [ ] Make dynamic rows omit ordinary respawn timing unless the source actually
      provides an automatic respawn contract.
- [ ] Verify Fallen Fernalla and every other dynamic-only character in map popup,
      search popup, wiki article, Cargo rows, and sheets output.
- [ ] Add formatter and UI tests preventing `zone re-entry` for event-only rows.

## Cross-surface audit

- [ ] Verify raw `DynamicCharacterSpawns` retains spawn and event positions.
- [ ] Verify `extract build` carries both positions into clean `character_spawns`.
- [ ] Verify map marker SQL, types, popup, and search paths consume both roles.
- [ ] Verify wiki coordinates and labels preserve all dynamic positions without
      source filenames or fabricated spawn chances.
- [ ] Verify sheet query columns distinguish dynamic spawn type and event anchor.
- [ ] Run focused tests, maps verification/build, wiki generation, and release
      data checks after each atomic change.

## Instruction alignment

- [ ] Commit the AGENTS.md test-file scope clarification separately and run
      `omp-plans check` plus the relevant focused tests.


- [ ] All overlapping markers remain individually selectable.
- [ ] Named dynamic uniques are classified from explicit evidence.
- [ ] Brax references have a documented active/unused determination.
- [ ] Dynamic event rows never claim automatic zone-entry respawn without proof.
- [ ] Raw-to-clean-to-map/wiki/sheets propagation is verified.
- [ ] Atomic commits exist for each completed change.
