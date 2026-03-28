# Adventure Guide Rewrite — Audit Findings (Revised)

Systematic comparison of old implementation (commit `112f2ace`) vs current (`23eb02d6`).
Revised based on triage feedback. ALL items must be fixed.

## Priority Summary

| Priority | Count | Description |
|----------|-------|-------------|
| P0 — Blocks ship | 12 | Core navigation, tracking, and marker features that define the mod |
| P1 — Major gaps | 18 | Important UX features and data completeness |
| P2 — Polish | 16 | Refinements, edge cases, minor improvements |
| P3 — Deferred | 5 | Items deprioritized per triage (achievements, quest types, chain groups, etc.) |

---

## P0 — Blocks Ship (12)

### P0-1: Live NPC position tracking architecture [NAV-4]
**Status**: Needs thorough evaluation and potential redesign.
CharacterPositionResolver calls EntityRegistry per frame via NavigationEngine.Update(), but creates new List<ResolvedPosition> each call (GC pressure). This is the mod's core selling point — the arrow following live NPCs.
**Design needed**: Evaluate current per-frame resolution. If it works functionally but has GC issues, switch to a buffer-write pattern (resolvers write into a passed-in list). If it doesn't track smoothly, add per-frame NPC transform tracking as a first-class feature.

### P0-2: Per-spawn-point markers instead of per-character [NAV-13]
**Severity**: Escalated from HIGH to CRITICAL.
MarkerComputer emits one marker per character node. Characters with multiple spawn points in the same zone collapse to one marker. Each spawn should get its own marker with independent alive/dead state and respawn timer.
**Fix**: Iterate HasSpawn edges from character nodes to spawn_point nodes. Emit one marker per spawn point, each with its own position and live state from LiveStateTracker.

### P0-3: Action text on marker sub-text [NAV-19]
**Severity**: Escalated from MEDIUM to CRITICAL.
Markers show quest name as sub-text instead of contextual action text. Players need to see "Say 'Hail'", "Kill", "Kill (3)", "Shout 'keyword'" on markers to know what to do.
**Design needed**: Determine optimal sub-text for each marker type:
- Quest giver markers: action text ("Talk to" / "Say '{kw}'") — quest names aren't actionable
- Objective markers (step targets): action + keyword ("Say 'tomb'", "Kill", "Shout 'Shadowtide'")
- Turn-in markers: "Give {item}" or "Say '{keyword}'" or quest name
- Dead spawn markers: "{NPC name}\n~M:SS" (live timer, line break between name and timer)
- Night spawn markers: "{NPC name}\nNight only (23:00-4:00)\nNow: HH:MM"
- Quest-locked markers: "{NPC name}\nRequires: {gating quest name}"

### P0-4: Item collection progress on markers [NAV-20]
**Severity**: Escalated from MEDIUM to CRITICAL.
Item source markers show no collection progress. Players need "2/5 Dragon Scale" to know how much more they need to farm.
**Fix**: When emitting markers for item-requiring frontier nodes, compute have/need from QuestStateTracker.CountItem and include in sub-text.

### P0-5: Proximity sort implementation [UI-F01]
Tracker proximity sort button renders but does nothing. Players need to see which quests are closest to make movement decisions.
**Fix**: Implement distance computation from player to each tracked quest's frontier. Sort current-zone quests first, then by distance. Shorter refresh interval preferred if performance allows; 2s acceptable as fallback.

### P0-6: Per-frame view tree rebuild in tracker [UI-F21]
TrackerPanel.GetFrontierSummary calls QuestViewBuilder.Build() + FrontierComputer for every tracked quest every frame. 5 quests = 5 full graph traversals per frame.
**Fix**: Cache frontier summaries per quest. Recompute only when QuestStateTracker.Version changes. Store summary string + version snapshot.

### P0-7: Collect step item count (have/need) display [UI-F05]
No inventory count anywhere. "Obtain: Iron Ore (x3)" shows required qty but not current progress.
**Fix**: For RequiresItem edges with quantity, show "(have/need)" using QuestStateTracker.CountItem. In both tracker frontier summary and detail panel labels.

### P0-8: Per-frame alive/dead marker transitions [NAV-14]
Markers don't update when NPCs die or respawn between full rebuilds. Marker stays as quest type until next dirty cycle.
**Fix**: Prefer event-based detection via Harmony patches (DeathPatch, SpawnPatch) where possible. Fall back to per-frame LiveStateTracker checks only where events aren't available. Track alive/dead per marker, update type/sub-text on transitions.

### P0-9: Respawn timer text on dead-spawn markers [NAV-15]
Dead spawn markers show frozen timer from computation time. Timer must count down live.
**Fix**: MarkerSystem per-frame update reads respawn timer from LiveStateTracker and formats countdown text.

### P0-10: FrontierComputer ignores edge.Quantity [DATA-R14]
Having 1 of required 3 items shows as satisfied. FrontierComputer checks IsSatisfied without considering edge quantity.
**Fix**: In FrontierComputer.CollectFrontier, when node state is ItemCount and edge has Quantity, check Count >= Quantity instead of just IsSatisfied.

### P0-11: Auto-advance navigation on step completion [NAV-2]
Arrow keeps pointing at completed targets. NavigationEngine has no state-change listener.
**Fix**: When NavigationSet contains a quest key, the frontier-based resolution already picks the right step each frame. The issue is if the set contains a specific non-quest node key that's been completed — it should be cleared. Also: NavigationEngine should detect when its resolved target changes and update accordingly.

### P0-12: Cross-zone route caching [NAV-25]
BFS runs every frame for cross-zone targets. Route doesn't change within a scene.
**Fix**: Cache route result per (currentScene, targetScene) pair. Invalidate on scene change only.

---

## P1 — Major Gaps (18)

### P1-1: Navigation persistence per character [NAV-1]
NavigationSet is in-memory only. Nav lost on restart/reload.
**Fix**: Save node keys to per-character config on destroy/clear. Restore on character load.

### P1-2: NAV button behavior [NAV-3, per triage]
The navigation model changed:
- Auto-nav goes to closest frontier node across ALL active nav targets
- Normal click = override (clear all, set single target). Clicking the ONLY active node toggles it off (returns to auto mode)
- Shift+click = toggle (add/remove without affecting others)
- All active nav targets get color highlighting in the tree
Current implementation partially does this but lacks multi-target visual feedback and the single-node toggle-off behavior.

### P1-3: Respawn timer navigation fallback [NAV-5]
When all NPCs matching a nav target are dead, arrow should point at spawn with shortest timer.
**Fix**: CharacterPositionResolver: when EntityRegistry returns null, query LiveStateTracker for spawn with shortest respawn.

### P1-4: Mining node live tracking [NAV-6]
DirectPositionResolver returns static coords. No alive/mined filtering.
**Fix**: MiningNodePositionResolver that queries LiveStateTracker, prefers alive nodes, falls back to shortest respawn.

### P1-5: Corpse/chest loot priority navigation [NAV-8]
Arrow should prioritize corpses with quest loot over alive NPCs.
**Fix**: Reintroduce corpse/chest scanning under a name that fits the new architecture (e.g., LootTracker or ItemSourceScanner). Integrate into navigation resolution chain.

### P1-6: Zone line alternatives display [NAV-9]
Multiple zone lines to same destination — player can't see or choose between them. Some zone entries are not connected within the target zone (e.g., locked doors).
**Fix**: Expose alternative zone lines in the detail panel UI when navigating cross-zone. Show number of required hops/zone changes for cross-zone nav targets.

### P1-7: Requirement text on arrow labels [NAV-10, NAV-11]
Arrow shows bare NPC name without indicating quest-gate requirements.
Format: "Requires: {quest name}" (without "Complete").
**Fix**: Check GatedByQuest edges on target character's spawn points. Append requirement text to TargetDisplayName.

### P1-8: Distance display in tracker [UI-F02]
No meters-to-target shown next to quest names.
**Fix**: Once proximity sort distance computation exists (P0-5), display it: "(42m)" for same-zone or "({n} hops)" for cross-zone. Sort cross-zone entries by hop count.

### P1-9: Step advance detection and animation [UI-F03]
TrackerState.StepAdvanced event is dead code. No frontier change detection.
**Fix**: Track frontier node sets per quest. When set changes between frames, fire StepAdvanced. Add yellow flash animation.

### P1-10: Cross-zone display in tracker [UI-F04]
Tracker shows raw frontier summary without zone awareness for off-zone quests.
**Fix**: When all frontier nodes are outside current scene, prepend "In {zone}: " to the frontier summary text.

### P1-11: XP/Gold/Item rewards and unlocks in quest detail [UI-F06]
Node has XpReward, GoldReward, RewardItemKey but nothing renders them. Also missing: quest unlocks (zone lines, characters, vendor items, chained quests).
**Fix**: Add rewards section after description in ViewRenderer. Show XP, Gold, reward item name, unlocked zone lines, unlocked characters, vendor unlocks, chain-to quest.

### P1-12: Collapsible source lists [UI-F13]
Quest items with 20+ drop sources show all as tree nodes.
**Design**: Show sources in current zone first (sorted by level ascending), collapsed rest. Fixed maximum for display (e.g., 5 visible + "{N} more sources" collapse node). If none in current zone, show lowest-level sources first.

### P1-13: Loot container markers [NAV-16]
No corpse/chest markers for quest items. Player can't see that a nearby corpse has items they need.
**Fix**: Reintroduce corpse/chest scanning. Emit Objective markers with progress text.

### P1-14: Prerequisite filtering for quest giver markers [NAV-17]
All not-started quest givers show markers regardless of unmet prerequisites.
**Fix**: Check graph for RequiresQuest edges. If any prerequisite quest is incomplete, show as grey star marker (new: QuestGiverBlocked) with sub-text "Requires: {quest name}" instead of suppressing entirely. Three giver marker colors: gold (acceptable), blue (repeatable), grey (blocked/prerequisites unmet).

### P1-15: Repeatable quest marker distinction [NAV-18]
No blue star/question mark for repeatable quests. Completed repeatables get no marker.
**Fix**: Check Node.Repeatable. Use QuestGiverRepeat (blue star) and TurnInRepeatReady (blue question mark). Show markers for completed repeatable quests.

### P1-16: REQUIRES_QUEST edges missing from pipeline [PIPE-1]
character_dialogs.required_quest_stable_key not queried. 2 explicit prerequisites lost.
**Fix**: Add _add_quest_prerequisite_edges() to graph_builder.py.

### P1-17: Quest flag columns missing from pipeline [PIPE-2]
kill_turn_in_holder, destroy_turn_in_holder, drop_invuln_on_holder, once_per_spawn_instance. 9+ quests affected.
**Fix**: Add fields to Node, fetch in _add_quest_nodes().

### P1-18: Vendor quest unlocks missing from pipeline [PIPE-4]
character_vendor_quest_unlocks table (12 rows) not queried.
**Fix**: Add edge type and builder function.

---

## P2 — Polish (16)

### P2-1: MergeUnknownQuests runtime discovery [DATA-R01]
Quests not in entity-graph.json are invisible. Old system created stubs from GameData.QuestDB.
**Fix**: Add runtime discovery that creates stub nodes for unknown quests.

### P2-2: Tracker hidden on menu/load scenes [DATA-R07]
Tracker overlay visible on main menu.
**Fix**: Add _trackerPanel?.Hide() in !_inGameplay branch.

### P2-3: Navigation cleared on non-gameplay scenes [DATA-R08]
Nav persists into menu transitions.
**Fix**: Clear NavigationSet in !_inGameplay branch.

### P2-4: OR-group visualization [UI-F10]
Old "---OR---" separators were hamfisted.
**Design needed**: Better visualization for alternative paths. Perhaps indented "or" label between siblings sharing the same Edge.Group value, or a visual grouping container.

### P2-5: Tips/notes display [UI-F11]
Edge.Note exists but not rendered.
**Fix**: Audit what's stored in Edge.Note — only render if content is user-consumable. Show as indented secondary-colored text under relevant tree node.

### P2-6: Per-step level/zone on tree nodes [UI-F12]
No level suffix on individual step targets.
**Fix**: Prepend node.Level where available for consistent visual position (e.g., "Lv 15 Drops from: Frenzy").

### P2-7: Source highlighting (active nav targets) [UI-F14]
No visual distinction between auto-selected and manually-selected nav sources.
**Design**: Active nav targets in the tree get accent color. Shift+clicked (toggled) targets get a different accent. Non-navigable items dimmed.

### P2-8: Level tooltip on metadata line [UI-F17]
No hover tooltip showing per-dependency level breakdown.
**Fix**: Add tooltip listing children with their levels.

### P2-9: Concurrent vs sequential step visualization [UI-F09, F23, F18, triage]
The tree is intentional (multiple steps can be active simultaneously). Frontier coloring (satisfied nodes greyed, frontier nodes highlighted) handles the visual distinction between "can do now" and "blocked".
**Fix**: Rely on frontier-based coloring. No separate concurrent/sequential visualization needed beyond what the tree + state colors already communicate.

### P2-10: NAV button disabled state for non-resolvable targets [UI-F19, F22]
Show NAV for everything (consistency), but disabled with tooltip for non-resolvable.
**Fix**: Check if PositionResolverRegistry would return empty. If so, render disabled button with "No known location" tooltip.

### P2-11: Night-spawn marker text [NAV-23]
Night-locked markers should show time window and current time.
**Fix**: Sub-text: "{NPC} Night only (now: HH:MM)".

### P2-12: Quest-locked marker sub-text [NAV-22]
Should show which quest to complete, not the tracked quest name.
**Fix**: Extract gating quest name from NodeState and include in sub-text.

### P2-13: Live NPC position for markers [NAV-21]
Markers float at static spawn coords instead of following wandering NPCs.
**Fix**: For alive character markers, look up live NPC via EntityRegistry and update position from transform. Review old WorldMarkerSystem.GetMarkerPosition(npc) implementation for CapsuleCollider height handling.

### P2-14: Directly-placed dead NPC ZoneReentry markers [NAV-32]
NPCs without SpawnPoints show DeadSpawn instead of ZoneReentry.
**Fix**: Distinguish DirectlyPlacedDead from regular dead.

### P2-15: spell_created_items table [PIPE-5]
1 row (Offering Stone chain) not captured.
**Fix**: Add edge builder for item creation.

### P2-16: Multi-variant SQL double-execution [PIPE-10]
graph_builder double-executes SQL for variant grouping.
**Fix**: Fetch rows into list once, iterate twice.

---

## P3 — Deferred (5)

### P3-1: Achievement data [PIPE-3]
Not showing achievement info anywhere. No plan to change. **SKIP**.

### P3-2: Quest type classification [PIPE-8]
Not useful. Quests are defined by their steps. **SKIP**.

### P3-3: Chain group pre-computation [PIPE-12]
Derivable from CHAINS_TO edges. No clear use case for pre-computing. **SKIP**.

### P3-4: Graph overrides TOML file [PIPE-6, PIPE-13]
No overrides defined yet, none existed before either. Create when needed. **DEFER**.

### P3-5: NavMesh reachability for spawn selection [NAV-12]
Euclidean distance is fine. NavMesh-based selection feels arbitrary to players. **SKIP**.

---

## Architectural Decisions Needed

### A1: Resolver allocation pattern
All resolvers allocate new List<ResolvedPosition> per call at 60fps. Options:
a) Buffer-write pattern: resolvers write into a caller-provided list
b) Cache results and invalidate on state change
c) Both: cache + buffer write for zero-alloc hot path
**Recommendation**: (c) — cache resolved positions, invalidate when NavigationSet.Version or QuestStateTracker.Version changes. Re-resolve at most every 0.25s or on dirty flag.

### A2: Marker sub-text strategy
Need consistent approach across all marker types:
| Marker Type | Sub-text content |
|-------------|-----------------|
| QuestGiver | Action text: "Talk to" / "Say '{kw}'" |
| QuestGiverRepeat | Action text: "Talk to" / "Say '{kw}'" |
| QuestGiverBlocked (new) | "Requires: {quest name}" |
| Objective (step target) | Action text: "Say '{kw}'", "Kill", "Shout '{kw}'" |
| Objective (item source) | Item progress: "2/5 Dragon Scale" |
| TurnInReady | "Give {item}" or "Say '{kw}'" |
| TurnInPending | "Give {n} items" |
| DeadSpawn | "{NPC name}\n~M:SS" |
| NightSpawn | "{NPC name}\nNight only (23:00-4:00)\nNow: HH:MM" |
| QuestLocked | "{NPC name}\nRequires: {quest name}" |
| ZoneReentry | "{NPC name}\nRe-enter zone" |

### A3: Tracker frontier summary strategy
Compact per-quest summary in tracker overlay:
- Same zone: "{Frontier node name} (42m)"
- Cross zone: "In {zone}: {frontier node name} ({n} hops)"
- Item progress: "{item} (2/5)"
- Completed: "\u2713 Completed" (brief flash before auto-untrack fade-out)

### A4: Source list collapsing
For items with many sources:
- Show all sources in current zone (sorted by level, max 5)
- If >5 in zone or any outside zone: collapse behind "{N} more sources (Lv {min}-{max})"
- If none in current zone: show 5 lowest-level sources, collapse rest

### A5: Concurrent vs sequential visualization
Frontier-based coloring handles this naturally:
- Satisfied nodes: greyed/checkmarked
- Frontier nodes (actionable now): highlighted/normal color
- Blocked nodes (behind unsatisfied parents): dimmed
No additional visualization needed beyond the tree structure + state coloring.

### A6: EntityGraph mutability for MergeUnknownQuests
Options:
a) Add controlled AddNode method — pragmatic, breaks "immutable" comment
b) Two-layer: immutable base + mutable overlay
c) Rebuild graph with merged nodes — expensive, breaks cached refs
**Recommendation**: (a) — add AddNode/AddToIndex for the runtime discovery case. Update the class comment.

### A7: GameState resolvers for non-entity types
16+ node types (Zone, Faction, Spell, etc.) return Unknown from GameState. FrontierComputer treats Unknown as unsatisfied, blocking frontier resolution through these node types.
**Context**: These node types appear in dependency chains (e.g., a quest step_travel targets a Zone node). If the Zone node's state is Unknown/unsatisfied, the frontier treats it as a blocker even though you can't "complete" a zone — it's just a location.
**Fix**: For node types that represent static world features (zones, factions, spells, skills, etc.), GameState should return a satisfied state since they're always available — they don't have a completion/acquisition lifecycle. Register a simple resolver that returns a static "Available" NodeState for these types.
