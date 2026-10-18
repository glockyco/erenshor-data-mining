## Context

See `proposal.md` for the motivation. The state on 2026-10-18, on a clean database built from the export of build 24405256:

- `quest_acquisition_sources` and `quest_completion_sources` have no key and hold `method`, `source_type`, `source_stable_key`, and `note`. `processor/entities.py` writes them from the export, and `gates.py` then deletes and rewrites the rows of the Shivering Step quests, so each table has two writers. Two readers add their own rules: `QuestRepository.get_quest_panel_rows` (about 250 lines that decide which routes execute, attach dialog conditions and furniture, and attribute rewards) and the guide's `edge_builder.py` and `node_builder.py`.
- `get_quest_panel_rows` projects 117 start routes and 239 completion routes for 196 quests. Dialog keywords, required and blocking quests come from `character_dialogs`.
- `gate_conditions` holds 469 gates with 543 atoms. A door gate is named by its door key and repeated on every target the door guards, for example 171 `key_held` atoms on spawn points.
- The item provenance contract holds 8,985 acquisitions and 10,303 uses with conditions, locations, and player access states, behind `ItemProvenanceRepository` and a versioned `item_provenance_meta`.
- `character_damage_releases` holds 33 rows of ten release mechanisms, among them `trade_turn_in` for Stardust and the Flickering Souls and `npc_protector_weather` with the state `raining` for Evadne the Corrupted.
- A throwaway projection of these facts, written while planning, found about 3,000 nodes. Its playthrough from Stowaway's Step put Brax's Plane of Elements at 38 milestones over 25 tiers, and showed where the facts are missing: Fallen Braxonia looked open because nothing gates rain, and the Jaws of Sivakaya chain was absent because nothing gates Vessel Siraethe. `model-progression-mechanics` closes those gaps. This change makes them visible.

## Goals / Non-Goals

**Goals:**

- One derivation of quest routes and one derivation of requirements, both in the clean build, both checked, both readable by any consumer in any language.
- A playthrough order that a reviewer can read and that the build-to-build report compares.

**Non-Goals:**

- Telling a player what their own save can do next.
- Wording. The graph holds stable keys and typed condition keys, and each consumer words them.

## Decisions

### D1. Canonical quest routes

`quest_routes` has one row per route, keyed by a `route_key` derived from its quest, phase, method, source, variant, and dialog index. Its columns are the quest, the phase (`start` or `completion`), the method, the source kind and exact source key (a character copy, an item, a quest, a zone, or a script), the resource variant, the dialog index and keywords, and whether the route executes the resource's rewards. `quest_route_conditions` holds route conditions in the gate shape of `gate_conditions` and the provenance conditions: gate, group, and atom.

A route's conditions are only its own: a dialog's required or blocking quest, an item that must not be carried, and a stored portal slot. The availability of the source copy, such as a furnished room or a gate on its spawn point, stays with the copy, so that one fact has one home. The quest panel joins the two for its rows as it does now.

The rules that decide whether a route executes move from `get_quest_panel_rows` into the stage, each with its code evidence: `TradeWindow.CompleteTrade` assigns a partially turned-in quest only with a partial-success dialog and a proper subset of the required units, `GameData.FinishQuest` grants no resource reward, `NPCDialog.GiveItem` gives its item only when it is not carried, and `QuestAvailable` ignores `DisableQuest`. The stage runs after item provenance, because reward attribution reads the canonical `quest_reward` acquisitions.

The source tables stay as the stage's inputs. The Shivering Step event rule keeps rewriting its rows there while the guide reads the source tables. When a guide change moves the guide onto the routes, the rule hands its routes to the route stage instead, and each table has one writer.

Alternatives considered:

- Keep the rules in the repository and let the requirement stage call it. Rejected: a clean-build stage would depend on a wiki view's row format, and the guide's third derivation would remain.
- Replace the source tables. Rejected for this change: the guide reads them, and guide code changes in its own change.

### D2. Requirement graph tables

- `progression_nodes`: `stable_key`, `kind`, `is_milestone`, `tier`, and `first_way_key`.
- `progression_ways`: `node_stable_key` and `way_key`. A way can have no needs, such as a starting class.
- `progression_needs`: `node_stable_key`, `way_key`, `need_index`, `relation`, `need_stable_key`, and the optional `quantity`, `slot`, `keywords`, `condition_key`, `advisory`, and `unconfirmed`.
- `progression_meta`: the contract version and the build.

`way_key` is a digest of the way's needs in canonical order, so that an unchanged way keeps its key and `extract changes` shows only changed ways. `condition_key` names a typed condition without a node, such as a health-phase release, and each consumer holds the wording for it. A consumer fails on a key it cannot word.

Alternative considered: compute the graph in each consumer from a shared Python library. Rejected: the map reads the clean database from TypeScript, the change report would not see requirements, and the projection's checks would run only when a consumer runs.

### D3. Nodes

| Kind | Identity | Ways |
|---|---|---|
| `zone` | zone key | its usable incoming zone lines and teleports |
| `quest` | quest key | its completion routes, each needing the quest's start node when the quest has start routes |
| `quest_start` | `quest_start:` and the quest key | its start routes |
| `item` | item key | its acquisitions that a player can use |
| `character` | exact copy key | its placements |
| `barrier` | the gate name, which is the door or barrier key | its opening condition groups |
| `mechanism` | the acquisition's source key, such as `mechanic:auction_house`, or a key for a source without one | its access, such as the broker copies of the auction house, or one way without needs when the mechanism has no place |
| `class` | class key | none needed, as a new character's choice |
| `world_state`, `account_state` | a typed state key that includes its value, such as `account_state:reliquary_claimed:true` or `world_state:weather:raining:<zone>` | the producers that the clean database records, and one way without needs for a value that holds at the start |

A quest start is its own node so that a quest with several starts and several completions does not multiply into their product.

### D4. Relations

| Relation | Needs | Fact |
|---|---|---|
| `zone line` | the source zone of a usable incoming line | `zone_lines_with_zoning_capability`, or a line with an activation gate |
| `teleport` | the teleport item | `teleports` |
| `in zone`, `entered from` | the zone of a placement, or the source zone of each of its entry lines | placements, `target_entries` |
| `barrier` | the barrier node | a gate named by a door or barrier |
| `quest done`, `quest active`, `quest not done` | a quest | gate atoms, stop quests, quest spawns, route conditions |
| `key`, `held` | an item | `key_held`, `item_held` |
| `planning slot` | an item, with `slot` set to the slot or to `rune slot` | `planning_slot_item` with `planning_portal_slots` |
| `room furnished` | a furniture item, with the room | `room_furnished`, placement furniture |
| `defeated` | a character copy, marked advisory | `encounter_won` |
| `state` | a world or account state node with its value | state atoms and account-scoped encounter conditions |
| `summoned with` | the trigger item | placement trigger items |
| `drops`, `sells`, `gives` | the source copy | acquisitions `character_drop`, `vendor`, `dialog` |
| `reward` | the quest | acquisition `quest_reward` |
| `mold`, `material` | the template and each material with its quantity | acquisition `crafting`, uses `crafting_material` |
| `mined in`, `fished in`, `found in` | the zone of the location | acquisitions `mining`, `fishing`, `fishing_bonus`, `item_bag` |
| `contained in` | the containing item | acquisition `item_drop` |
| `created by` | the item whose spell creates this item | acquisition `spell_created` |
| `converted from` | the item that the conversion consumes | acquisition `item_conversion` |
| `from` | a mechanism or class node | acquisitions `auction_house`, `special_world_drop`, `common_world_item`, `starting_class`, `ui_grant` |
| `started` | the quest's own start node | quest routes with a start |
| `talk to`, `read`, `after`, `enter`, `turn in to`, `defeat`, `hear`, `event` | a start or completion route's source, with keywords: dialog and talk `talk to`, item read and read `read`, quest chain and chain `after`, zone entry and zone `enter`, partial and full turn-in `turn in to`, death `defeat`, shout `hear`, script `event` | quest routes |
| `in zone` (zone use) | the zone where an item must be used | the `zone_use` condition of an acquisition or use |
| `required item` | an item with its quantity | the route's resource variant |
| `release` | the item, copy, or state that makes a copy vulnerable | `character_damage_releases` |
| `condition`, `event` | no node, a `condition_key` | releases and scripted routes without a node |

An acquisition condition becomes a need when its phase is `availability` and its predicate is one of the gate atoms above. The operation inputs of a turn-in are the quest's own required items. Predicates of quantity, rolls, class, level window, time of day, and ownership limits describe a source, not a progression step, and the item pages show them.

Gates on one subject multiply out into ways. A subject whose gates yield more than 32 ways fails the build, so that a reviewer sees a combinatorial gate instead of a silent cut. The planning table's interchangeable rune slots (`planning_portal_slots.slot_kind = 'rune'`) collapse into one need per rune.

Each kind of gate in `gate_conditions`, read from its name, has one treatment in one table: availability of its subject, a barrier node, or a vulnerability that joins the kill ways of D6. The `damage_release` gates that `_ward_gates` derives from `character_damage_releases` are vulnerability, so a copy's placement ways ignore them and its kill ways take the release branches. A gate kind that the table does not list fails the build.

### D5. Quests follow their intended route

A quest's ways are its completion routes, and each needs the quest start node when the quest has start routes. The game completes a quest without checking the journal: `TradeWindow.CompleteTrade` (`TradeWindow.cs`, lines 299 to 386), `NPCDialog` (line 75), `ItemIcon` on read (line 161), `ZoneAnnounce` (line 80), and `Character` on death (line 912) call `GameData.FinishQuest` without that check. The graph still requires the start, because finishing a quest that was never started skips its story and its dialog gates. `CompleteOtherQuests` completes another quest only while that quest is active (`TradeWindow.cs`, line 392), so the other quest's way needs the first quest and `quest active` for itself.

### D6. Releases

A release joins the ways that kill the copy: its `drops` acquisitions, a `defeat` completion, and a `defeated` atom. A copy that a turn-in releases is also that turn-in's target, so a release on the copy itself would close the turn-in. The mechanisms map as follows, and an unmapped one fails the build:

- `trade_turn_in` with a `quest_variant` condition needs that variant's required items.
- `shivering_phantom_wards`, `combat_ward_cycle`, and `reliquary_wards` with character or spawn conditions need those copies defeated.
- `npc_protector_weather` with the state `raining` needs the world state of rain in the copy's scene.
- `health_phase_timer`, `spawn_health_phase_timer`, and `combat_empty_wards` become condition keys.
- A branch with `can_release = 0` is not a way.

### D7. Exclusions

A zone line is left out when `zone_line_destination_contexts` marks it a saved return, when it is inactive and no gate records its activation, or when a `never` atom closes every group. An acquisition counts when its player access state is `verified_player` or `unconfirmed_player`, and an unconfirmed one sets `unconfirmed` on its needs.

### D8. Playthrough tiers

Tiers are a least fixpoint: a node's tier is the lowest, over its ways, of the highest tier among the way's needs, plus one when the node is a milestone. The start holds the two scenes that the game offers a new character, each read from an extract code fact: the scene of a fresh save slot, which `CharSelectManager.Awake` creates with `new SaveGameData(i, "", "Stowaway")` and `Play` loads, and the alternate start, which `PlayAlternate` loads with `ChangeScene("Willowwatch", ...)`. An assert fact pins `DetermineStart`, which offers both to every new character outside the demo. Each start is a mechanism node with one way without needs, and the zone of its scene needs it. The start also holds every class with its starting items. Negative conditions and the initial account state hold at the start (`GameData.AccountClaimedReliquary` starts false, `GameData.cs`, line 430). An item once obtained stays available, and quantities do not change tiers.

The first way minimizes the tier, then a derivation depth, then `way_key`. The depth is 0 at the start and for needs that hold at the start, and a way's depth is one more than the highest depth among its needs. Without the depth, equal-tier nodes that are not milestones, such as two zones that connect both ways, could name each other as first ways and never reach the start. Both measures are a maximum plus one, so the fixpoint converges (Knuth's generalization of Dijkstra's algorithm) and depth grows along every first way. The build checks that each node with a tier reaches the start through first ways without revisiting a node.

The tier is a playthrough order under these rules, the same idea as a randomizer's spheres. It is not a claim about what a player can do with their save, because a later step can close a way that a negative condition guards. The requirement and the README say so.

### D9. Milestones

A node is a milestone when it is a quest or a barrier, a zone or character copy whose every way needs a gate, or an item that a gate, a summon, or a release needs, or whose every source is a quest reward, a craft, or a gated copy. The rule is computed before tiers and does not depend on them. Wording, levels of detail, and filters belong to consumers.

### D10. Checks

The build fails, naming the node, the way, and the fact, on an unmapped acquisition kind, route method, atom kind, release mechanism, or source kind, on a need that resolves to no node, and on the expansion limit. Every quest and zone must be a node. The build logs the number of nodes without a way and without a tier, and `erenshor progression show --gaps` lists them.

### D11. Reading the graph

`ProgressionRepository` reads the tables and checks `progression_meta`. A change of the table structure raises the version, and readers fail on a version they do not know. `erenshor progression show <key>` prints the node's tier and ways with names from the clean database, and the first-way milestones in tier order. `--gaps` lists the nodes without a way or a tier.

### D12. Build-to-build report

`extract changes` compares clean tables row by row (`build-change-report`). With stable way keys, a changed requirement appears as an added or removed way of the node, and a moved tier as a changed node row. No report code changes.

### D13. Owners and write boundaries

| Artifact | Owner | Written by |
|---|---|---|
| `quest_routes`, `quest_route_conditions` | clean build | the quest route stage of `extract build` |
| `progression_*` tables | clean build | the requirement stage of `extract build` |
| `ProgressionRepository` | repository | consumers read through it |
| Quest panel rows | wiki | `wiki generate-lua` from the canonical routes |
| Guide edges | Adventure Guide | unchanged until a guide change adopts the routes |

### D14. Failure handling, grouping, and rollback

The clean build fails closed on every check of D1, D4, D6, and D10, and a failed build leaves the published database and the backup unchanged. Commits group by unit: the routes, the panel switch, the graph, the tiers, the command, and the documentation. A rollback reverts the commit and rebuilds, because the clean database is generated.

## Risks / Trade-offs

- The panel switch could change a wiki row by accident. `Data/Quests` must be byte-identical before and after on the same database.
- Tiers could read as advice. Consumers label them as a playthrough order from a new character, and the requirement states the policy.
- The milestone rule could misjudge an item. It is one function with unit tests, and the review of the raid chains checks it on real data.
- The guide keeps a separate derivation for a while. The guide change that adopts the routes is part of the coordination plan in `model-progression-mechanics`.

## Migration Plan

1. Land the routes, then switch the quest panel and compare `Data/Quests`.
2. Land the graph, the tiers, and the command. Review the four raid chains and record each gap with the task of `model-progression-mechanics` that closes it.
3. Rebuild the clean database. No live write is part of this change.

Rollback follows D14.
