# Proposal

## Why

AdventureGuide must explain physical access and source availability without directing players to absent characters or unreachable zone lines. This change preserves the implemented keyed-door, Occuphage entrance, Shivering event, probability and compact-UI behavior while completing the common source, account, encounter and portal consumers. Reliability and performance budgets apply to the complete runtime extension.

The gate kinds, highest player impact first:

1. Keyed doors in front of quest targets and zone lines, including Island Tomb and Occuphage, Shivering Step, Ghost of Wyland Sercher, Founder, Lighthouse Flame, Warded Shadow, Fallen Braxonia and Sablehart. Preserve keyring-or-inventory semantics and reviewed entrance identities.
2. The Shivering Step event (`ShiverEvent`), including keeper completion, the two Kio copies, darkness, The Hider and trigger activation, and Kio's departure. Preserve the derived event rule rather than reintroducing prerequisite overrides.
3. Placements that are inactive when a scene starts. Activation coverage and per-copy eligibility follow the authoritative inactive-placement audit referenced by tasks.md, rather than a copied inventory count. Unused roots remain distinct from valid spawned prefabs, restored gods and portal groups.
4. Zone lines that players cannot use (issue #298), including disabled components, invalid trigger capability and reviewed unreachable geometry. Physical usability remains independent of object activation.
5. Quest scripts that remove barriers and the dungeon locks behind them, including Blooming Sepulcher, Vitheo's Rest and the quest listener removal lists. Exact guarded targets require host proof.
6. Encounters that must be won first, including restored planar gods, ward-protected characters, A Strange Hermit and plane barriers. Persistent account claiming remains distinct from transient fight advice.

## What Changes

- Record gates as OR groups of AND-ed typed atoms. Observable state includes quests, inventory, keys, room furnishings, stored planning-slot items and explicitly supported account predicates. Unobservable encounter and transient activation state remains advice, not a hard availability test. Guarded initialization and outcome effects retain their separate semantics.
- Replace the quest-only unlock representation entirely. The clean condition model replaces the old unlock tables. The breaking embedded schema 8 cutover carries common canonical source facts, encounter placements, conditions, completions and guarded event conditions, typed account atoms and dynamic zone-line destination contexts. No schema-7 compatibility path runs beside it.
- Export every activation effect of the quest listeners in both directions with its trigger (quest, active quest, held item), the usability of each zone line component, and the serialized targets of the scripted activators. Pin the hand-encoded rules of those scripts and the door key rule as code facts.
- Give each reviewed fact one home. Corrections of exported rows, such as zone lines that players cannot reach, go into `mapping.json` with a reason. Which targets a keyed door or a removable barrier guards goes into a new reviewed file, `barriers.toml`, that the clean build reads and checks for completeness. The door and item curation of `quest_guides/graph_overrides.toml` moves to its proper home, and the Shivering Step overrides give way to the event rule.
- Model the Shivering Step event from its rules. Meet Shivering Step is acquired on zone entry and completed by the four keeper quests.
- Consume canonical acquisitions and uses through the shared repository and eligibility contract, preserving acquisition/location identity, variants, material slots, phaseful conditions and exact local probabilities. Keep reviewed presentation notes.
- Model the native carried-item offering controllers, the Vitheo arena, the Malaroth feeding site and the Braxonian chessboard, as activations of the exact placements they spawn. Sources, kill targets and encounter requirements lead through the offering, and the quest list holds native quests only. Synthetic guide-only workflow quests are removed.
- Navigate a selected crafted source through its missing ingredients, including crafted keys. Preserve the original goal and recipe choice while accounting for repeated material slots and quantities.
- Project the Reliquary account claim and character completion through explicitly guarded initialization implications without mutating game state. Preserve exact root and four support placements, account-claim purpose and the post-completion player-home role.
- Derive all ten PlanningTable portals from one immutable reference selection. Four dedicated slots retain their actual destinations and six rune slots are interchangeable. Resolve the physical saved-character return through common destination contexts and typed live state, never a fixed Hidden fallback.
- Evaluate conditions in AdventureGuide in one place and migrate every gate consumer to it. When a target or a route hop is gated, explain the gate and navigate to what satisfies it.
- Derive one physical zone-line usability result and migrate guide, map, legacy wiki and shared zone providers to it. Close issue #298 only after the named host geometry and zoning checks establish the exact unusable lines.
- Stop generating `quest_guides/guide.json`, which nothing reads, and remove its writer and command.
- Preserve the six gate families while tracking implementation, exported data, integrated data and host proof separately. Source patches, acknowledgements and baseline checks do not prove a production cutover.

Non-goals, each recorded as an issue in the format of issue #282:

- Navigating several quests at once. It becomes its own OpenSpec change after this one lands, with budgets measured on the current navigation first.
- Travel that is not a physical zone line: teleport items and spells, the Azynthian Riftstone, movable teleport endpoints and the Box of Portals return. Actual planning-table portal zone lines, their initialization and the saved-character physical return are included.
- The Bellwain Isle puzzle, secret passages, and forced travel. The zone-wide spectre spawner keeps issue #282.
- Weather as a condition. Evadne keeps a plain explanation of the rain requirement.

## Capabilities

### New Capabilities

- `guide-gate-data`: how the export, code facts, reviewed facts, and the clean build record the conditions under which zone lines, placements, and sources are available, and how the guide compiler and `quest-guide.json` carry them.
- `guide-gated-navigation`: how AdventureGuide evaluates those conditions, explains unmet gates, navigates to what satisfies them, and which reliability and performance budgets it meets.

### Modified Capabilities

None.

## Impact

- Unity export: `QuestActivationListener`, a new scripted-activator listener, `ZoneLineListener`, `dynamic-spawn-catalog.toml`, `src/tools/ExportSurface/field-coverage.json`, and the records under `src/Assets/Editor/Database/`.
- Code facts: `src/tools/CodeFacts/specs/erenshor-facts.json`.
- Clean build: `src/erenshor/application/processor/`, the schema in `writer.py`, `mapping.json`, and the new `barriers.toml`.
- Guide: `src/erenshor/application/guide/`, the `guide` CLI commands, `quest_guides/graph_overrides.toml`, the regenerated `quest_guides/quest-guide.json`, and the removal of `quest_guides/guide.json` and `json_writer.py`.
- Readers of zone line usability and destination contexts: the map's zone line query, the legacy wiki zone page generator and the shared zone overview/wiki Lua providers.
- AdventureGuide: `Data/`, `State/`, `Navigation/`, `UI/`, `Diagnostics/DebugAPI.cs`, the test project, the README, and both changelogs.
- Documentation: the README, the AdventureGuide README, and the `refreshing-game-data`, `unity-export-system`, and `runtime-eval` skills.
- Ownership: ExportBundleIntegrator owns native refresh. CanonicalSources owns common DDL and source hooks. WikiOverviews/DataZones own generic encounter and navigation projections. AdventureGuide owns its consumer. Rebuilds use announced worktree-owned databases and writable inputs, never shared main databases.
- No release, publication, push, game launch or Unity launch is authorized by this plan.
