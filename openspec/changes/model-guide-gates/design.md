# Design

## Context

See proposal.md for the six gate families and their ranking. The following describes the pre-change baseline, not current implementation or acceptance. Current implementation, export, integration and host evidence belong in tasks.md.

- The export records doors with their key (`doors.key_item_stable_key`, 247 doors, 40 keyed placements, 26 keys), zone lines and placements with `is_enabled`, and the positive effects of the three quest listeners (`QuestActivationListener`, which skips item conditions and every removal).
- The guide graph has `DOOR` nodes, `UNLOCKS_DOOR` edges, and curated door and item edges in `quest_guides/graph_overrides.toml`. `compiler._compile_unlock_predicates` resolves a door to its key item. `mod_writer` ignores those predicates and rebuilds quest-only groups, so the mod never sees a door or item gate. `guide compile` writes a dense `quest_guides/guide.json` that no code, CI job, or the map reads.
- The mod has no shared gate evaluation. `ZoneGraph`, `NavigationController`, `WorldMarkerSystem`, `QuestDetailPanel`, `StepSceneResolver`, and `TrackerSorter` each read `required_quest_groups`, `_character_quest_unlocks`, or `required_quest_db_names` themselves, and `FurnishingPolicy` is a second availability mechanism beside them. Nothing reads `GameData.Keyring`.
- The runtime updates every frame, re-picks among a step's sources every 0.25 s, recomputes cross-zone waypoints after 10 m of movement, and rebuilds markers on a state version that quest and inventory patches increment.
- The earlier runtime rewrite exposed risks from per-frame resolution, cloned dependency trees, synchronous cold resolution and incomplete cache dependencies. The design retains the existing runtime lifecycle rather than repeating that rewrite.
- The dynamic spawn catalog already classifies the character and object fields of the scripted activators, as denied spawn sources (`ShiverEvent`, `MemorySphere`, `QuestSpawnListener`, `MultiQuestListener`, and others). The export fails on an unclassified field.
- `mapping.json` holds reviewed corrections of exported rows, each with a reason, and already overrides spawn point flags.
- Zone lines are read by the guide, the map's zone line layer (`database.base.ts`), and the wiki zone page generator (`zones.py`).

## Goals / Non-Goals

**Goals:**

- One condition model from the export to the runtime, with one derivation in the compiler and one evaluation in the mod, and no second representation.
- Every gate either derived from game data or held in one reviewed home that fails the build when the game changes.
- No availability-result cache. Conditions read mirrored observable state on demand. Bounded identity parsing, presentation caches and static implication indices remain valid.
- Each gate kind lands as a verified slice, checked in the running game on a test character.

**Non-Goals:**

- Navigating several quests at once. A separate change follows.
- A general travel graph for teleport items, spells and the Riftstone. Actual physical planning portals and the saved-character return remain within the zone-line graph.
- Spatial reachability analysis. Which targets a door guards is reviewed data.
- General gate overlays on the map or wiki. These readers consume common usability and destination contexts, with generic saved-return descriptions rather than invented fixed connections.

## Decisions

### D1. Conditions are flat OR groups of typed atoms

A condition is a list of OR groups of AND-ed typed atoms. A subject without a condition is always available, and a condition without groups never holds. Observable atoms include `quest_done`, `quest_not_done`, `item_held`, `key_held`, `room_furnished`, `planning_slot_item` and supported `account_state`. Advisory `encounter_won` retains actual member identities and counts. Account atoms carry actor, boolean value, phase and scope. Only observable availability-phase predicates enter current-state conjunctions. Initialization, operation inputs and outcomes retain their own semantics.

Transient encounter deaths and activation state are advisory when no reliable primitive exists. They never hide a potentially active target, while actual live-entity withholding remains intact. Persistent account claims are different: the supported loaded account flag and explicit initialization implications can suppress a repeat encounter without inventing kill history.

A general boolean tree was rejected. Combinations such as two alternative listeners in front of a keyed door distribute into this form with a few groups, and the compiler fails when a condition exceeds a fixed size. A flat form is cheap to evaluate, to serialize, to diff in a contract test, and to explain to the player.

### D2. Each kind of gate fact has one home

1. The export, for facts that game data states: the quest listeners in both directions with item conditions, zone line component and collider state, and the scene objects referenced by the scripted activators. `QuestActivationListener` owns listener effects and writes them to a raw `QuestActivationEffects` table that replaces `ZoneLineQuestUnlocks` and `CharacterQuestUnlocks`. A new listener exports the serialized targets of the scripted activators, driven by a new `[[activation]]` class in `dynamic-spawn-catalog.toml`: each entry names a script, its fields, and a rule ID. The scripted acquisition and completion notes in `CharacterListener` that describe the Shivering Step keepers as kills are corrected with the event rule.
2. Rules in the pipeline, for logic that lives in game code: the Shivering Step event, the angel statue, the ward listeners, the planar fight reveals, the essential spawn that blocks A Strange Hermit, the boss barriers, `MemorySphere`, `SivTorchLight`, and the door key rule. A rule maps each field of its script to a condition template. Each rule carries `code-fact` tags, and `assert` facts in `erenshor-facts.json` pin the quests, comparisons, and calls the rule encodes.
3. `mapping.json`, for reviewed corrections of exported rows: a `zoneline:` rule with `is_usable: 0` and a reason marks a zone line that players cannot reach (issue #298). This follows the existing spawn point rules.
4. `barriers.toml`, a new reviewed file beside `mapping.json`, for the one fact no existing file can hold: which targets each keyed door and each removed object guards. Each entry has a reason. The clean build fails on a keyed door or removed object without an entry, and on an entry whose object no longer exists. The door and item edges of `graph_overrides.toml` move here or to the rule that owns them (the candle to `MemorySphere` and the listener export, the Tempestalia ring to Evadne's weather note). The Shivering Step edges give way to the event rule. `graph_overrides.toml` keeps only guide-only content, such as the Reliquary planning table node.

`barriers.toml` also holds `[[entries]]`: a target that only some zone lines into its scene reach, such as Occuphage's ledge in the Island Tomb, names those lines. The clean build writes them to `target_entries`, `quest-guide.json` carries them on placements, and routing enters through the cheapest of them. Without them the route ends at the entrance closest to the player, which may not reach the target.

Keep activation decisions in shipped code, typed catalog rules and exported references rather than a per-placement exception list. Before deriving never conditions for inactive placements, export coverage must reject unknown serialized references reaching characters through object/component hierarchies. Denied fields that call SetActive need review too. A successful direct-reference spawn scan alone does not prove that every activation path is represented. Automatic door containment by NavMesh analysis was rejected as the source of truth because a wrong guess silently misleads. The in-game NavMesh check reviews `barriers.toml` instead.

`MorphTrigger` entry effects and `FernallaPortalBoss` HP phases establish potentially active exact targets with controller provenance and advice, not fabricated persistent completion gates. `PietyTrigger.RequiredQuest` is an activation-time guard. Completing it does not despawn Guardians already enabled, so it must not become a current `quest_not_done` predicate. `AngelScript.TheBellwains` uses the exported target group and BELLWAIN completion without implementing the puzzle workflow. Unknown inactive placements fail the expanded audit before a never-condition cutover.

Barrier entries accept `doors` or `objects`, never both, with reviewed guards and a reason. Passage conditions use positive removal triggers, with alternative triggers OR-ed and independent obstructions AND-ed. Unsupported inverse or item-state removal semantics fail explicitly. Geometry review compares actual closed/present and open/removed approaches, including independent entrances, rather than trusting NavMesh reachability alone.

### D3. The clean database owns gates and every reader follows

CanonicalSources owns common DDL and source hooks. The clean build writes `gate_conditions`, common acquisition/use relations, the four encounter row families, planning-slot roles, destination contexts and one `zone_lines.is_usable`/`unusable_reason` result. Reviewed exclusions take precedence over disabled components, missing trigger colliders and disabled trigger callbacks. Missing physical input fails. Object SetActive alone cannot repair disabled capability. The raw capability view remains raw. Guide, map, legacy wiki and shared zone providers require common usability and preserve dynamic destination semantics.

### D4. The compiler derives conditions once and only `quest-guide.json` is written

The compiler combines gates once and the writer emits embedded schema 8 with no schema-7 compatibility path. Typed common source facts live once in `_source_facts`, indexed by acquisition key, while source trees retain acquisition and actual location references. The canonical adapter uses `ItemProvenanceRepository.iter_acquisitions/iter_uses` and shared eligibility rather than independently selecting source families. It preserves item variants, source copies, material slots, operation IDs, quantity and probability semantics and phaseful conditions. No-location sources gain no fabricated character or position. Missing common schema, references or unknown actionable kinds fail before replacing the artifact.

`guide compile`, `json_writer.py`, and `quest_guides/guide.json` are removed, with their tests and the documentation that names them. The compiled data stays as the in-memory input of `mod_writer`.

### D5. The Shivering Step event is a rule, not overrides

The event rule reads the exported targets of each `ShiverEvent` field and assigns conditions: `FirstKio` while the four keeper quests are not all complete, `Kio` once they are and while Changing the Lighthouse is not, `WelcomeCrew` while not all four are complete, `Hider` from The Shivering Torch until Warming the Isle, `SpawnTriggers` from The Shivering Torch, `Phantom` from Seeing the Truth. Meet Shivering Step gets a zone-entry acquisition and the four keeper quests as its completion. The ten seconds of darkness before The Hider and the triggers appear become a step note. The rule's code facts pin each `CompletedQuests.Contains`, `AssignQuest`, `FinishQuest`, and `SetActive` call of `ShiverEvent.Update` and `ShiverEvent.InitAll`.

Re-entry hides the keepers as soon as all four quests are complete, while the live sequence keeps them until darkness. The condition follows re-entry, because the keepers have no purpose after their quests.

### D6. The mod evaluates conditions on demand, without an availability-result cache

`GateConditions` holds typed atoms parsed at load. `IsAvailable(condition)` treats advisory atoms as holding. `Explain(condition)` lists unmet observable atoms and advisory atoms. Both read the existing completed-quest and inventory mirrors, the shared stored planning-slot mirror and `GameData.Keyring` directly. Room furnishings and planar portal items use the same stored-slot observation path. Inventory ownership or a completed quest does not satisfy a stored-item atom. No availability-result cache can become stale.

Consumers rebuild on the existing state version. `QuestStateTracker.Update` already polls furnishings and treasure hunts each frame, and it also compares `GameData.Keyring.Count` with the last value and increments the version on a change. During play only `Door.OpenOrShut` changes the keyring, and it only adds a key. A character load replaces the keyring before the gameplay scene loads, and the scene load already refreshes all guide state.

Evaluating a condition costs a few set lookups, and the data has a few hundred gated subjects. Caching results per state version was rejected: it adds a key that must cover every fact, which is the defect class that sank the rewrite, for no measurable gain. If a budget fails, the fix goes to the consumer that evaluates too often.

All consumers call `GateConditions`. No consumer reads atoms itself.

The account consumer preserves `encounter_placements`, `encounter_conditions`, `encounter_completions` and `encounter_event_conditions`, including `context_kind`, `post_completion_role`, exact root/support keys and all guarded effects. Account availability uses `availability` and completion uses the existing `operation_outcome` phase, as do canonical item outcomes. No new phase spelling or alias is introduced.

`EncounterProjection` indexes reverse reachability of supported positive `scene_awake_quest_completed` and `scene_awake_account_claimed` implications at load, including their account/character cycle. Effective state is the OR of reachable raw true sources. Host-death outcomes never enter that closure. Raw quest mirrors and `IsGameQuestCompleted` remain raw. Only explicitly bound quests use projected completion before active/implicit status selection. Fresh false/unfinished state remains claimable. Claimed accounts and completed legacy characters do not propose a repeat fight, including before Awake.

Typed live bindings read only `GameData.AccountClaimedReliquary`, `GameData.ReliqDest` and `GameData.ReliqLanding` for their supported keys. Unknown keys throw. Both character-entry callers must have successful ordered code-fact assertions proving LoadReliquary precedes world entry before the account binding is emitted. The guide never parses saves, loads account state or mutates progression. Tracker update/load boundaries observe account and saved-return changes, increment the existing version and invalidate consumers once.

One immutable `PlanningPortalSelection` carries line, slot, typed role, item key and actual destination key. Gate atoms and `planning_portal_slots` project from that same selection. Four dedicated portals each have one exact-slot group. Six ordinary portals each have six rune-slot OR groups. Missing or ambiguous references fail. Authoritative stored-slot gates supersede quest-enable alternatives while retaining initialization provenance. Instructions derive from common role/destination metadata, not a native slot-name map. Six identical rune actions deduplicate only in presentation. Warm slot polling stays allocation-free.

### D7. Requirement guidance is resolved where the target is resolved

`NavigationController` resolves requirements on a NAV click, state change, or scene change. Its existing 0.25 s source re-pick prefers live sources without rebuilding requirements when state is unchanged. Requirement resolution inspects the target and route-hop conditions, selects the group with the fewest unmet atoms and the nearest first requirement on ties, then follows item sources, a missing quest's current step, or the planning table. A per-resolution visited set prevents hangs on defective data. Advisory atoms add NAV links without redirecting the target. Navigation owns the chain rendered by the detail panel and tracker and exposed through diagnostics. Cross-zone waypoints remain valid across unrelated state changes when the physical target, hop, required entrance, and whole hop's accessible-line set are unchanged.

The shared renderer puts action and location together when space allows, with fishing windows/rates and preparation below. The tracker retains the originating quest independently of the guide's visibility and selection. Expanded source lists suppress the collapsed preview. There is no separate guidance HUD or explanation tree. Presentation strings are built when endpoints or display state change, not by resolving routes during drawing. Dynamic text uses literal ImGui rendering because native printf-style text interprets percent signs.

`SourceChoice` projects immutable DTO lists into acquisition/material-use choices. It retains original member references and IDs, with optional physical-location details. Semantic comparison preserves independent condition families and OR groups, rebinding only exact own location/placement/gate scopes after actor and physical equivalence. External scopes and all room slots remain distinct. Navigation retains the choice while selecting an eligible real endpoint. This is an identity/presentation cache, not an availability-result cache. Character load and menu suspension clear the in-session choice.

Combat preparation consumes the clean release provenance. Per-spawn trades, ward counts and weather become source instructions, not persistent quest-completed availability gates. Potential damageability remains a separate per-copy property for combat-level consumers.

### D8. Routing drops unusable zone lines and asks the condition

`ZoneGraph` leaves unusable zone lines out of the graph. The accessible-first search asks `GateConditions` about each zone line. The locked fallback route stays, and requirement guidance applies to its first gated hop.

`ZoneGraph.ResolveDestination` centrally resolves every line. Static lines retain their normal destination. Common `zone_line_destination_contexts` bind stored returns by stable line key to typed character zone and landing state. The producer requires the actual portal/line binding and exported `$portal_active_self=false`, not activeInHierarchy. Empty or unknown zones and nonfinite landings remove the edge from accessible and locked fallback routing. No Hidden or zero-vector fallback exists. Rebuild, entry selection, placement routing and navigation labels/landings all use the resolver and existing adjacency lifecycle. Offline map/wiki readers describe the return generically because they have no player save.

### D9. Slices follow player impact

The six gate families remain separate acceptance units. Completed behavior is preserved while explicit common source, account/encounter, ten-portal and dynamic-return units close the remaining consumer gaps. Each unit records implementation, exported-data, integrated-data and host-proof evidence separately in tasks.md. Nested source workflows and final host checks remain distinct from implemented compact UI behavior.

ExportBundleIntegrator owns the additive native refresh, including the startup bool and audited loot-binding repairs, without changing the completed candidate. CanonicalSources owns coherent common schema/codec output. WikiOverviews/DataZones own generic encounter/navigation projections and the guide owns its consumer. A source packet or ACK is not refreshed production data. Missing scalar/native bindings remain fail-closed.

### D10. Budgets are measured against the mod before this change

Repeat the existing fixed-cohort protocol after slot, account and saved-return observations are integrated. Use twelve identical tracked quests, Alice's Necklace step 2 navigated, the same two scenes, warm-up, 600 actual tick calls, ten actual patch-plus-tick events, five scene-handler samples and separately sampled real repaint frames. GC.GetTotalMemory requires a positive allocation control and no gen-0 collection. This is not exact per-thread allocation or whole-scene timing. Keep baseline and prior measurements in tasks.md, scoped to the behavior measured. Existing relative budgets and zero avoidable hot growth still apply.

### D11. Testing follows the layer that owns the logic

- Export: the export run and SQL checks against the scenarios of the `guide-gate-data` spec. Unity listeners have no unit tests in this repository.
- Clean build and compiler: unit tests for each atom source, the completeness failures of `barriers.toml`, the contradictory listener, the Shivering Step rule, and the cycle check. A contract test compares database conditions with `quest-guide.json`.
- Mod: `GateConditions` and requirement selection are pure classes that take state through small interfaces, compiled into `AdventureGuide.Tests` like the existing policies. Their scenario tests load the real `quest-guide.json` and assert the spec scenarios.
- Game: the verification plan below.

### D12. In-game verification uses a test character and the diagnostics

Host checks require an explicit parent runtime-slot handoff. Use a uniquely named task-only save in a confirmed empty slot with approved save/account isolation. Never overwrite existing test characters or restore a blanket backup over newer user state. Test-only progress is not normal acquisition. Verify native geometry, source flows, dedicated/rune instructions, saved returns and fresh/claimed/legacy account behavior. Account-mutating claim checks remain blocked without account isolation. Keep sound off, explicitly enable Lunaris in its UI, verify input and Escape behavior, quit through the normal game path and confirm process exit.

| Slice | In-game check |
| --- | --- |
| 1 | Whispers of Wyland without and with the Ghostly Key, the key moved to the keyring, Occuphage through the lighthouse entrance, the Shivering Step entrance, a Reliquary vendor with and without its room set, Bassle Wavebreak after Angler's Ring. |
| 2 | Each phase in order: keepers, both Kio copies, The Hider after darkness, trigger spawns, Kio leaving, Founder and Warded Shadow behind their doors. |
| 3 | The disabled Lucian Revald and Revan Gavault copies and The Hider before the torch get no markers. Boss-revealed restored gods retain advisory encounter guidance and remain navigable. |
| 4 | Routes out of Shivering Step and both Shivering Tomb scenes avoid the unusable lines. A NavMesh path from the scene entry checks each `barriers.toml` entry. |
| 5 | A Dying Wish parts one to three route to the barrier's quest before the deeper section. |
| 6 | Restored Fernalla, Warded Shadow, and A Strange Hermit show their encounter requirement and stay navigable. |
| All | The BepInEx build runs every check. The Lunaris build loads, navigates a gated quest, and quits cleanly. |

### D13. Native offering activations replace synthetic workflow quests

`VithArena`, `MalarothFeed` and `Chessboard` share one native mechanism. Entering the controller's trigger while none of its spawned characters is alive consumes the first matching carried offering and spawns that offering's characters. The arena then spawns the round's reward chest once those characters die, and its eighth round also reveals restored Vitheo. The chessboard's Faceless offering spawns one of six characters at random.

The guide records each controller once as an activation with its exact identity, scene, site, display name and offerings. Each offering has its item, spawned characters with counts, an optional reward container and whether its outcome is one random member. Each spawned placement references the offerings that create it and its role, spawned or reward. Arena rounds bind through `arena_rounds` and `arena_round_enemies`. Trigger placements bind through their exported trigger item, script and site. A controller placement that cannot be bound exactly fails generation.

No offering becomes a quest, a gate condition or persisted cycle state. Native quests, item sources, kill targets and encounter requirements reach these placements through their normal identities. Runtime resolution reads observable state in this order: a live spawned target, live precursors of a reward, the offering held, then the offering item's own acquisition. Another carried offering of the same controller can be consumed first, so guidance asks the player to carry only the intended one. Live entity tracking covers a reload during a fight. Obtainability of a spawned placement includes obtaining its offering item.

The chessboard placements carry exact trigger items, but its trigger site and display name are not exported. Until the native export records them, chessboard guidance names the item and navigates to the actual exported spawn position without calling that position the trigger.

## Risks / Trade-offs

- A reviewed barrier may misclassify guarded targets. Verify actual player approaches with the obstruction present and removed, including independent entrances. Ambiguous selectors remain incomplete.
- A rule drifts from a game update. The code facts fail extraction, and the export fails on a new unclassified field.
- Unobservable transient encounter requirements remain advice after a fight. Supported persistent account state instead follows the common projection and can suppress repeat guidance.
- Slice 1 is large, because the cutover cannot be split without a second path. Its pipeline and mod halves are separate commits, and the mod half is verified in the game before the next slice starts.
- The scope is large. The non-goals become issues, so nothing found by the audit is lost.

## Migration Plan

1. Reconcile the artifacts and freeze the single-selection ten-portal adapter with typed roles and assertions. Preserve earlier frozen packets.
2. Hand the scalar capture and both ordered entry assertions to ExportBundleIntegrator for its additive refresh. Preserve the immutable completed candidate. Obtain the frozen receipt and coherent CanonicalSources revision before cloning inputs.
3. Develop pure consumer fixtures independently. Announce rebuilds and use worktree-owned APFS raw/clean clones and writable catalogs, backups, profiles and logs. Never write shared main databases or alter isolation tooling.
4. Preserve the common `operation_outcome` vocabulary for account and item outcomes. Require refreshed activator/suppressor records, startup bool, resolved loot bindings and all common tables before production cutover. Never fabricate bindings or silently omit sources.
5. Migrate Python/C# DTOs, validation, runtime consumers, real fixtures and generated embedded data atomically to schema 8. Remove independent source selectors and old wire paths. Serialize a common-producer fixture through the real Python writer and load that exact output in C# to prove the cross-language contract.
6. Finish inactive/obstruction derivation and migrate all usability/destination readers. Run offline workflows only after edits are coherent. Parent-owned host verification follows explicit runtime permission and does not follow automatically from plan approval.
7. Regenerate from the final coherent owned clean database. Only completed behavior with its required exported, integrated and host evidence permits spec sync and archive. No release, publication or push is included.

Rollback reverts the coherent task-owned unit and regenerates its artifact from matching owned data. Do not mix schema-8 consumers with old production data.
