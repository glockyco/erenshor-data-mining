# Proposal

## Why

Item acquisition is selected independently by article generation, Lua data, map queries, guide graph construction, and Sheets. These paths already discard different conditions, quantities, identities, and probability variants, so checking that each has a nonempty row does not establish agreement.

## What Changes

- Select acquisition and item-use facts once during clean database construction, without wiki or map visibility filtering.
- Derive one versioned, stable-keyed public view from the selection: the sources and uses a player can act on, the conditions a player must meet, each source's places once, and reviewed lifecycle dispositions. Every output reads only that view, and the clean database stores it instead of the complete selection. The build checks which input rows each fact uses without publishing that evidence, and reports what the public view leaves out.
- Preserve encountered character copies separately from display representatives, item variants separately from page aliases, and random or unlocated sources separately from marker locations.
- Migrate all maintained consumers, including existing parameter-based article generation during the transition. Remove their independent source-selection queries rather than retain a second implementation.
- Add input accounting that fails on input rows the selector neither uses nor excludes, and identity coverage that fails when an output silently drops a public source or use.
- Keep rendering, navigation ranking, and surface-specific grouping in their respective consumers.

## Capabilities

### New Capabilities

- `item-provenance`: One complete acquisition and use contract shared by maintained outputs, with explicit dispositions for facts not rendered on a surface.

### Modified Capabilities

None. Existing publication and lifecycle contracts remain in force.

## Impact

The processor, clean SQLite schema, database repositories, wiki article and Lua generators, vendor/world-drop views, map item sources and character loot, guide graph/compiler/JSON and the mod's data readers, obtainability queries, and Sheets source queries change together. The map stops publishing the clean database at `/db/erenshor.sqlite`, which no first-party code has read since September and no application requested in the last 30 days. Low-level relations remain only where they are producer inputs. Remove obsolete source-selection schema after the maintained cutover rather than preserve compatibility tables or views for unknown consumers.

## Goals and Non-Goals

The goal is semantic agreement without a universal presentation layer. This change does not redesign the game export, invent missing facts, publish live wiki or Sheets writes, release Adventure Guide, or convert item article templates. `convert-item-pages-to-data` is a dependent change and can proceed after this contract is complete.

## Migration Boundary and Dependencies

One coherent repository cutover switches every maintained reader before old selector code is removed. Implementation starts in an isolated worktree only after `WorktreeIsolation` lands. Active roster, class and quest view changes own `generation.py` and their repositories until integrated, so the provenance change must not edit those main-worktree paths concurrently. Guide gating is owned by `model-guide-gates`. Reconcile its final gate semantics and payload consumer with that change before guide adapters land. This proposal grants no mod release or live-write approval.
