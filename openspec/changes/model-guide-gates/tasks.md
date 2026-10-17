# Tasks

## Proof stages

A checked task proves its named behavior and checks, not newer shared-data integration. The original gate slices remain below. Common-consumer cutovers are tracked separately in section 9.

| Unit | Implementation | Exported data | Integrated data | Host proof |
| --- | --- | --- | --- | --- |
| Keyed doors and entrance routing | Landed | Existing raw used | Landed slice 1 | Both loaders checked |
| Shivering Step event | Implemented | Native producer certified | Canonical consumer integrated | Earlier ordered-phase proof retained |
| Inactive placements and obstructions | Isolated derivation and expanded discovery fixtures | Exact positive bindings audited, missing negative coverage remains | Never cutover blocked | Remaining geometry and native discovery pending |
| Physical usability | Isolated common derivation and reader cutover | Native capability retained | Owned actual-data smoke passed, shared overview-owner cutover pending | Issue 298 and barrier approaches pending |
| Compact sources and preparation | Compact rows, semantic grouping and independent tracker implemented | Canonical source and use evidence retained | Integrated generated resource | Both loader UI checked, remaining nested workflows tracked by U1b |
| Ten planning portals | Ten-route and stored-slot consumer verified | Native producer certified | Common ten-route/forty-binding generation verified | Actual instructions pending |
| Account claim and saved return | Schema-8 consumer implemented | Native producer certified | Coherent generation and pure-state transitions verified | Fresh false account and absent return observed, positive native transitions pending |
| Performance | Existing lookup/rebuild fixes retained | Not applicable | Final observations integrated | Current samples scoped below, exact final protocol still pending |

## 0. Remove the unused dense guide

- [x] 0.1 `refactor(guide): stop generating guide.json`: confirm that no code, CI job, map file, or document reads `quest_guides/guide.json`, then remove `guide compile`, `json_writer.py`, their tests, and the file, and update the README, the AdventureGuide README, and `skill://refreshing-game-data`. Verify: a repository search for `guide.json` finds only `quest-guide.json`, and `uv run erenshor test unit` passes.
  - Done in 6c28bd251. The compiler stages that only `guide.json` serialized went too. `quest-guide.json` was byte-identical before and after. The only remaining mention is a historical note in `adopt-data-backed-wiki`.

## 1. Condition model and keyed doors

- [x] 1.1 Measure the baseline of design D10 on the mod built from the current commit (BepInEx, main variant, test character with twelve tracked quests, one navigated) in Stowaway's Step and Shivering Step. Verify: the averages, minimums, and maximums are recorded under this task, and `pgrep -f Erenshor.exe` prints nothing afterwards.
  - Done on 2026-10-16 with the mod of 6c28bd251 on the test character Gatetest (slot 11). Times are synchronous calls in the running game through HotRepl: the runtime tick (`TickActive`, without drawing) as a direct delegate, the guide's half of an event (the patch handler, then one tick), and the runtime's scene-load handler plus one tick. A synchronous loop of ticks skips the 0.25 s source re-pick, which runs in real frames only.

    | Measurement | Stowaway's Step | Shivering Step |
    | --- | --- | --- |
    | Tick, 600 calls | avg 0.04, min 0.03, max 0.28 ms | avg 0.02, min 0.01, max 0.28 ms |
    | Managed allocation per tick (`GC.GetTotalMemory` over 600 ticks) | 0 B | 0 B |
    | Inventory change, 10 events | avg 2.0, min 1.2, max 4.8 ms | avg 1.8, min 1.3, max 3.9 ms |
    | Quest completion, 10 events | avg 3.2, min 1.4, max 6.7 ms | avg 2.8, min 1.4, max 10.2 ms |
    | Scene load, 5 repeats after a warm-up | avg 15.9, min 12.5, max 23.4 ms | avg 16.9, min 13.3, max 22.2 ms |

    The slowest quest completion (10.2 ms) already exceeds the absolute 8 ms the spec named, so the event budget is now relative to the baseline. These first numbers are not comparable with the slice 1 results under 1.4: the navigated quest and the tracked set were not fixed, and `GC.GetAllocatedBytesForCurrentThread` always returns 0 under the game's Mono runtime.
- [x] 1.2 `feat(pipeline): record gates as conditions in the clean database`: add `gate_conditions` to `writer.py` and derive it from the existing quest unlocks of zone lines and characters, quest-started and quest-stopped spawn points, Reliquary furnishings, vendor stock unlocks, item bag unlocks, and keyed doors through `barriers.toml`. Add `barriers.toml` with an entry for every keyed door, moving the door and item edges out of `graph_overrides.toml`, and fail the build on a missing or stale entry. Drop `zone_line_quest_unlocks` and `character_quest_unlocks`. Document `barriers.toml` in the README's concepts. Add unit tests for each atom source and both completeness failures. Verify: the tests pass, and after a clean build (announced in the status) the slice 1 scenarios of `guide-gate-data` hold in SQL.
  - Done, with `[[entries]]` added in `feat(pipeline): record targets that only some entrances reach`. `barriers.toml` has 29 entries for the 40 keyed doors of the main build. Each was reviewed in the game: a NavMesh obstacle carved into the door, paths from the scene entry compared before and after, and plan renders, perspective renders, and the wiki for what the NavMesh does not reach. The five Bellwain house doors guard nothing in the data, because the house has no NavMesh. On a clean build from the current raw export the slice 1 scenarios hold in SQL: no quest-only unlock tables, Ghost of Wyland Sercher's spawn point and the Stowaway's Step lighthouse zone line carry the matching key atoms, and every Reliquary room placement carries its furnishing atom.
- [x] 1.3 `feat(guide): compile and ship typed gate conditions`: build unlock edges from `gate_conditions`, extend `_compile_unlock_predicates` to the atom kinds, add the size limit and the acyclicity check, and write `quest-guide.json` version 7 as design D4 describes. In the mod, load the conditions, add `GateConditions` with the keyring check of design D6, remove `FurnishingStatus` and the separate furnishing checks, and migrate every consumer of the old gate fields. Add compiler tests for each atom kind and a cycle, the database-to-JSON contract test, and `GateConditions` tests on the real data, moving the existing furnishing tests onto the atom. Update the AdventureGuide README's data section. Verify: Python and C# tests pass, `uv run erenshor mod build --mod adventure-guide --loader all` succeeds, and the regenerated `quest-guide.json` holds the door gates of the spec scenarios.
  - Done. The regenerated `quest-guide.json` gives Founder the Dockhouse Key, Ghost of Wyland Sercher the Ghostly Key, and the Duskenlight Coast line to the Jaws of Sivakaya a candle group and a She Sees You group. The contract test passes.
- [x] 1.4 `feat(adventure-guide): lead navigation to what unlocks a gate`: add requirement selection and chains (design D7) to navigation, the navigation display, the detail panel, and the tracker, and `DumpGate` with the chain in `DumpNav`. Update `skill://runtime-eval`. Add tests on the real data for the lighthouse key, the Jaws alternatives, and a chain of two requirements. Verify: tests pass, the slice 1 checks of design D12 pass in the game with screenshots, and the budgets hold.
  - Done. Requirement chains, entrance routing for placements with `entries`, door zones in key requirements, and a keyring event that re-resolves navigation. The slice 1 checks of design D12 pass in the game on Gatetest: Whispers of Wyland without the Ghostly Key names the key and stops, because the key is crafted, and with the key on the keyring it navigates to the ghost. Occuphage from Blacksalt Strand routes through Stowaway's Step to the lighthouse line, and without the key the chain leads to Garrey Ambrose. The Shivering Step crypt from Stowaway's Step leads to the Crypt Keeper. A Reliquary vendor appears when its room holds the set, and Bassle Wavebreak is available after The Angler's Ring. The Lunaris build loads, navigates Occuphage with the same chain, and quits after the save.
  - Budgets, both builds measured the same way in one session: twelve fixed tracked quests, Alice Hewer's Necklace navigated, one untimed warm-up event, then ten timed events of a patch handler plus one tick. Allocation is `GC.GetTotalMemory` over 600 ticks.

    | Measurement | Stowaway's Step, main / this change | Shivering Step, main / this change |
    | --- | --- | --- |
    | Tick avg | 0.027 / 0.022 to 0.024 ms | 0.012 / 0.009 to 0.010 ms |
    | Allocation per tick | 0 / 0 B | 0 / 0 B |
    | Inventory change avg, max | 1.15, 1.47 / 1.14 to 1.43, 1.43 to 1.66 ms | 1.09, 1.48 / 1.30 to 1.34, 1.75 to 2.66 ms |
    | Keyring change avg | 0.07 / 0.85 to 1.01 ms | 0.06 / 0.90 to 0.95 ms |
    | Quest completion avg, max | 1.09, 1.33 / 1.29 to 1.32, 1.69 to 2.51 ms | 1.06, 1.32 / 1.18 to 1.19, 1.42 to 1.63 ms |
    | Scene load avg | 11.5 / 9.6 to 10.4 ms | 8.0 / 7.3 to 7.8 ms |

    An inventory event allocates about 25 KB on this change against 1 to 2.5 KB on main. Navigating cross-zone to Ghost of Wyland Sercher from Stowaway's Step, an inventory event costs 1.3 ms against 5.7 ms on main, because a state change that leaves the route and its zone lines unchanged keeps the waypoint instead of recomputing NavMesh paths to every line.
- [x] 1.5 `fix(guide): list the common world item swap as one world-drop source`: after the clean build of `adopt-data-backed-wiki` task 5.44, a `loot_drops` row with `is_common_world_item = 1` and no other drop flag comes only from the swap of `GameManager.CommonWorldItems`. Turn those rows into one background source per item, like the special world drops, instead of a drop edge from every character, and keep rows that also carry their own drop flag as character drops. Add unit tests for both kinds of row. Verify: tests pass, and the regenerated `quest-guide.json` lists Bread, Water, Brackfruit Juice, Luminstone, Citrine Stone, and Star Stone with one swap source each and no swap-only character drops. This lands before the first regeneration of `quest-guide.json` from that build.
  - Done. Each of the six items has one `common_world_item` source, "Any enemy with common drops", with the chance range over placed characters (Bread 0.92-8.12%). Bread drops from 334 sources to 42 droppers that have their own flag plus that one source.

## 2. Export for slices 2 to 6

- [x] 2.1 `feat(export): export both directions of quest listener effects`: replace `ZoneLineQuestUnlocks` and `CharacterQuestUnlocks` with `QuestActivationEffects`, recording enable and disable effects of `QuestSpawnListener`, `MultiQuestListener`, and `DynamicContentManager` for every scene object, with the quest, active quest, or held item that triggers them. Switch the clean build to the new table in the same commit, so the existing conditions stay unchanged. Update `field-coverage.json`. Verify after 2.5: the conditions of slice 1 are unchanged, and rows exist for the item condition in Stowaway's Step, the A Dying Wish removals, and both effects of Meet the Fisherman.
  - Owned exports and clean build passed. SQL verified Stowaway's held-item effects, both Meet the Fisherman directions, every A Dying Wish removal and retention of the prior non-activation atoms. Producer and clean adapters are frozen separately for coordinated integration.
- [x] 2.2 `feat(export): export zone line component and collider state`: add the enabled state of the `Zoneline` component and whether its collider is a trigger to the zone line record. Verify after 2.5: the six components of the gating audit read disabled or non-trigger, and every other zone line reads usable.
  - Private export/build verified. Six components are disabled, three also lack a trigger collider. The other 123 have enabled components and enabled trigger colliders. Runtime accessibility remains task 5.1.
- [x] 2.3 `feat(export): export the targets of scripted activators`: add the `[[activation]]` class with a rule ID to `dynamic-spawn-catalog.toml`, move the fields of `ShiverEvent`, `ShiveringAngel`, `ShiveringPhantomWardListener`, `MemorySphere`, `SivTorchLight`, the planar fight reveals, and the boss barriers into it, and add a listener that records each referenced scene object with its script, field, and stable key. Update `skill://unity-export-system`. Verify after 2.5: the export lists `Kio the Lightkeeper (1)` for `FirstKio`, `Kio the Lightkeeper` for `Kio`, the four keepers for `WelcomeCrew`, The Hider, the ten spawn triggers, and the four restored gods.
  - Two private exports passed with shared placement-key resolution. SQL verified both Kio identities, four keeper targets, Hider, ten trigger references and four restored gods. The exporter skill now requires activation classification and the shared target resolver.
- [x] 2.4 `feat(tools): pin the gate rules of the scripted activators`: add `assert` facts for the `Door.OpenOrShut` key rule, each quest check, assignment, finish, and activation of `ShiverEvent.Update` and `ShiverEvent.InitAll`, the `STANDANGEL` check of `ShiveringAngel`, the ward rules, the reveal and reset of each planar fight script, the essential-spawn block of `NPCShoutListener`, the boss barriers, `MemorySphere`, and the gaze rule of `SivTorchLight`. Follow `skill://code-facts`. Verify: `uv run erenshor extract code-facts` binds every new fact, and a changed literal in a test fixture fails it.
  - All 54 gate and damage-release assertions bound in the private 215-fact extraction. CodeFacts tests passed 32 cases, including semantic mutations. The producer and clean adapters were handed off separately for combined integration.
- [x] 2.5 Announce the export in the status, then run the export, code facts, and clean build of the main variant. Verify: the checks of 2.1 to 2.4 hold.
  - Completed against owned main-variant clones only. No shared main database was written. Final CI and both loader builds pass. The parent owns the combined native export and shared DDL integration.

## 3. The Shivering Step event

- [x] 3.1 `fix(guide): model the Shivering Step event from its rules`: add the event rule of design D5 to the clean build, give Meet Shivering Step its zone-entry acquisition and keeper completion, correct the keeper notes of `CharacterListener`, and remove the Shivering Step edges of `graph_overrides.toml`. Add unit tests for each phase. Verify: tests pass, the Shivering Step scenarios of both specs hold, and the slice 2 check of design D12 passes in the game.
  - The owned runtime observed the initial and three-keeper states, all-four transition, torch/darkness delay, Hider and ten active triggers, warming and lighthouse completion. `/tmp/erenshor-guide/shiver-phase-evidence.json` records live objects and guide availability separately. The serialized Hider instruction includes the ten-second wait. Phase and serialized-checklist tests pass.

## 4. Inactive placements

- [ ] 4.1 Audit all inactive direct placements outside furnished-room placements against the game code. Verify each as unused or activated by a named script, classify every activating script, and fail export for unknown serialized character references through supported object/component hierarchies before deriving never conditions.
  - Current inventory and exact positive/unresolved classifications are recorded in `/tmp/erenshor-guide/inactive-continued-evidence.json`, superseding the earlier direct-only audit. The six receptacle NPCs remain unused roots, not portal groups. Full negative coverage and additive discovery/code-fact refresh remain missing. JawsStatueStartup is a positive component-enable control, not evidence of a restored Zoneline.
- [ ] 4.2 `fix(guide): keep inactive placements unavailable without an activator`: give each inactive placement the condition of its activation effects, or a never-holding condition without one, and carry it to the mod. Add unit tests. Verify: tests pass and the slice 3 check of design D12 passes in the game.

## 5. Unusable zone lines

- [ ] 5.1 Check each candidate zone line of issue #298 in the game. Verify: the result for each line is recorded under this task.
- [ ] 5.2 `fix(pipeline): mark zone lines that players cannot use`: derive `is_usable` and `unusable_reason` from the component and collider state and from `zoneline:` rules in `mapping.json`, add those rules with reasons, exclude unusable lines in the guide, the map's zone line query, and the wiki zone page generator. Add unit tests. Verify: tests pass, the zone line scenarios of both specs hold, the map preview and the generated zone pages omit the lines, and the slice 4 check of design D12 passes in the game, including the NavMesh check of every `barriers.toml` entry.
  - Isolated consumer-selection cutover covers Guide nodes/edges/entries, map markers, legacy wiki connections and character placement entries. Raw capability remains an audit view. The parent-owned new overview provider is absent from that base and still needs its owner's reviewed-usability selection. Exact native source evidence, all six disabled-component audits, actual-data smoke and remaining proof boundaries are recorded in `local://guide-producer-combined-contract-93.json`. No shared producer integration or geometric exclusion was applied.
  - Shared actual-data review is coordinated with WikiOverviews and CanonicalSources. Ten actual PlanningTable portals require one v3 selection for gates and typed roles, with four dedicated Planar slots and six interchangeable rune slots. Physical Fernalla/Soluna returns must not be copied from prose. Shivering lines still need geometry evidence, not an invented lifecycle-disable. Slice-4 map/wiki reader permission already exists. No game launch before parent handoff.

## 6. Removed barriers

- [ ] 6.1 `feat(pipeline): gate targets behind objects that quest scripts remove`: derive conditions from the disable effects of the quest listeners and `barriers.toml` entries for every removed object, including the Blooming Sepulcher barriers and the Vitheo's Rest key doors. Add unit tests. Verify: tests pass and the slice 5 check of design D12 passes in the game.

## 7. Encounter prerequisites

- [ ] 7.1 `feat(adventure-guide): show encounter prerequisites as guidance`: derive encounter atoms from the planar fight reveals, the ward rules, the essential-spawn block, and the boss barriers, carry them to the mod, and show them as requirements with NAV links. Add unit tests for the derivation and for the guidance never hiding a target. Verify: tests pass and the slice 6 check of design D12 passes in the game.

## Probability corrections found during implementation

- [x] P1 Preserve fishing day/night chances and zero-probability phases through graph construction, compilation, and serialization. Verify differing day/night probabilities, day-only and night-only waters, and labels/wait guidance in the running guide.
  - Serialized-contract regressions pass. The running source picker shows Octorunners at 39.12% day and 36.94% night in Port Azure. Moongill shows its night window and 7.92% per successful catch without a false daytime rate. The guidance changes with the clock.
- [x] P2 Preserve local mining and drop chances without basis-point quantization or impossible zero-probability acquisition sources. Verify the final serialized consumer contract and actual guide display.
  - Runtime source comparisons show local mining odds and the 16.7% Plaxitheris drop. Contract tests preserve unknown and tiny positive odds and exclude known impossible outcomes. Literal percent rendering was checked in the actual native UI.

## Source guidance and combat preparation

- [x] C1 Derive per-copy potential damageability and release provenance without name exceptions. Verify permanent immunity, actual holder/variant binding, protector weather, ward dependencies and copy isolation against exported data.
  - The clean adapter handoff passed 76 focused tests and a real owned build. Seven Ward of Piety copies are excluded. Stardust, Evadne and Warded Shadow remain eligible. The restored/observer Vitheo copies remain immune and separate combat Vitheo remains eligible.
- [x] U1a Implement compact next-action guidance, inline area levels, collapsed source choices, retained explicit source selection and literal probability text across the shared UI surfaces. Verify: existing serialized and consumer checks pass and real source switching, day/night guidance and guide/tracker/HUD nonduplication are observed.
  - Existing runtime screenshots and receipt are `/tmp/erenshor-guide/ux-*-refined.png` and `/tmp/erenshor-guide/ui-final-performance.json`. This is implementation and existing host proof, not proof of the later canonical adapter or account/portal observations.
- [ ] U1b Verify nested recipe/reward/item-use flows and automatic mining fallback after the canonical cutover, including choosing a source before NAV, preserving the original goal across prerequisites and scene changes, and all shared UI surfaces. Record actual host evidence.
- [x] U2a Carry per-spawn trade, weather and ward preparation into source instructions without treating them as persistent unlocks. Verify: the serialized contract and existing UI show actual Stardust turn-in, Evadne's brazier/rain and both Phantom's Wards.
- [ ] U2b Verify final integrated encounter guidance, exact root/support multiplicity and transient activation advice in the host. Preserve the completed preparation implementation while testing the common context/source cutover.
- [x] U3 Verify current source guidance CPU and managed-heap budgets against the recorded baseline. Remove avoidable steady lookup and event rebuild work without a new availability cache.
  - Fixed cohort is the same twelve tracked quests with Alice's Necklace step 2 navigated. Event work is the actual patch handler plus one runtime tick. Net heap measurement had a positive allocation control and no generation-0 collection during the hot samples.

    | Final measurement | Stowaway's Step | Shivering Step |
    | --- | --- | --- |
    | Hot tick avg, min, max over 600 calls | 0.0345, 0.0282, 0.2003 ms | 0.0054, 0.0039, 0.2923 ms |
    | Net managed-heap growth over 600 hot ticks | 0 B | 0 B |
    | Inventory event avg, min, max over 10 samples | 2.0681, 1.6305, 3.1262 ms | 1.8388, 1.4253, 2.6874 ms |
    | Quest event avg, min, max over 10 samples | 1.9379, 1.5907, 2.4726 ms | 1.6182, 1.2432, 1.9686 ms |
    | Scene handler plus tick avg, min, max over 5 samples | 17.0003, 13.5093, 22.9326 ms | 12.7024, 11.4472, 14.4783 ms |

  - The Shivering scene-handler measurement preceded the final parsed-key cache extension. It is not a separate whole-scene-load measurement. Repaint was sampled separately over 120 actual frames, averaging 0.4159 ms, with 0.3159 ms minimum and 2.3937 ms maximum.
  - Numeric prefab variants no longer create a substring on every NPC lookup. Marker rebuilds no longer format off-zone labels, and unmatched loot containers no longer allocate empty sets. Marker dumps matched apart from the displayed current clock. Source-choice and timing strings remain cached presentation, not availability results.

  - This evidence predates the additional stored-slot, account and saved-return observations. Task 9.6 repeats the same protocol on the final integrated runtime.

## 9. Common source, account and portal integration

- [x] 9.0 Reconcile proposal, design, both delta specs and task proof stages with the approved completion plan. Update the external status and canonical handoff notes, report conflicting main-worktree guidance to the isolation/config owner, and validate OpenSpec. Do not change isolation tooling.
- [x] 9.1 Freeze the v3 ten-portal selection and typed slot-role adapter. One immutable selection feeds gate and role rows. Verify four dedicated groups, six OR groups per ordinary rune portal, exact destinations, wrong/empty/replaced slot states, inventory/quest non-substitution and unrelated-copy isolation. Extend the shared stored-slot reader and generate role-based instructions, deduplicating presentation but not OR identities. Hand off the verified narrow patch to the common owner.
  - Frozen at `/tmp/erenshor-guide/planning-slot-clean-v3/`, with an annotation-only forward correction at `/tmp/erenshor-guide/planning-slot-clean-v3-types.patch`. A complete producer fixture writes four dedicated and 36 rune role rows. Actual generated JSON loads through the C# parser/evaluator and exercises all 40 alternatives, replacement/removal, non-substitution, concise typed instructions and unrelated-copy isolation. The fixture includes the native resolver's object root plus child zone line. Python targeted checks passed 145 cases, the guide suite passed 532, both loaders built without warnings/errors and final CI passed all six leaves. Native production rows and shared clean integration remain task 9.2, not proved by these fixtures.
- [ ] 9.2 Freeze and integrate the activeSelf scalar plus both pre-world LoadReliquary caller/order facts. Bind the shipped methods and fail missing, duplicate, conditional-only or reversed fixture statements. Preserve the completed producer candidate and obtain an additive refresh receipt with actual bool/suppressor records and resolved native loot bindings. No guide save parsing or runtime load calls.
- [ ] 9.3 Consume all four common encounter tables, purpose metadata and guarded initialization effects in embedded schema 8. Preserve account actor/reference/true-or-false/phase/location scope, separate availability from host-death outcomes, retain exact root/four support identities and project legacy pre-Awake claim state without mutating saves or raw quest mirrors. Verify real Python-to-C# serialization and fresh/claimed/legacy transitions. Commit only with coherent owned common inputs and regenerated data.
  - The coupled consumer is integrated in the parent's reported d23cc297c checkpoint. `/tmp/erenshor-guide/canonical-guide-final-integrity-v2/verification.json` records actual producer-backed Python generation, C# loading, false availability/true outcome, fresh/claimed/legacy projection and exact support identity proof. The frozen account ACK requires `operation_outcome`, superseding the earlier proposed `outcome` spelling. No live account flag, character completion or save was changed to test projection. Save-mutating live claim acceptance remains blocked without an authorized account sandbox.
- [ ] 9.4 Resolve the actual saved-character return through common destination contexts and one dynamic ZoneGraph resolver. Migrate every destination consumer. Verify character switches, destination/landing changes, empty/unknown/nonfinite state, no accessible or locked Hidden fallback, and unchanged static lines.
  - The same producer-backed verification covers destination changes, invalid state, static preservation and no Hidden fallback. Actual task-host empty return resolves unknown. The temporary native-field projection receipt is diagnostic only, not a saved-origin transition. Positive native item-entry/return acceptance remains open.
- [ ] 9.5 Replace independent guide item-source selection with the canonical acquisition/use repository. Preserve acquisition/location IDs, repeated native slots, exact variants, quantities, local phaseful probabilities and outcome quality. Keep initialization/outcome annotations out of current availability. Navigate a chosen crafting recipe through missing ingredients, preserving the original goal and cumulative requirements for repeated material slots. Verify the cross-language contract, negative cases and offline coverage for every represented or explicitly excluded input. Remove superseded selectors and preserve authored content.
  - The canonical consumer, coverage and generated data are integrated. Later native bundle correction 216046538 retains slot-level use evidence while grouping repeated quantities within variants. Item-read correction 00072545d restores a non-variant read step without weakening exact collect-variant matching. Semantic source grouping a5398f42b preserves original endpoints rather than changing producer eligibility.
- [ ] 9.6 Repeat fixed-cohort CPU/heap and real repaint measurements after all new observations. Verify relative budgets, positive heap control, zero avoidable hot growth, actual patch-plus-tick and scene-handler costs. Record authorized BepInEx and explicitly enabled Lunaris navigation/Escape/normal-quit proof, then remove only task-owned save/profile state and verify original save/account preservation.
  - Current evidence is under `/tmp/erenshor-guide/final-host-acceptance/evidence/`. The closed-guide, open-picker and event receipts from sample 93 establish observed CPU costs only. Real-frame heap windows included collections or whole-game growth, so they are not zero-allocation proof. The cohort receipt does not establish the navigated step precisely enough for a final same-state comparison. Repeat the exact protocol before claiming final relative-budget acceptance.

## 10. Independent consumer and UI corrections

- [x] 10.1 Preserve native turn-in AND bundles and whole-variant OR alternatives. Sum repeated items only within their variant and retain canonical native use IDs. Verify thresholds zero/one/three/four, mixed-item bundles, single/multi-slot alternatives and impossible mixed partial variants.
  - Native requirement and read-acquisition checkpoints are separate. Python export checks, consumer regressions and actual BepInEx inventory transitions establish one quantity-four Octorunner objective and turn-in readiness only at four. No canonical use or acquisition fact was dropped.
- [x] 10.2 Group acquisitions and real semantic locations without losing original endpoints, room slots or same-name actor distinctions.
  - Native receipts retain 83 original Octorunner endpoints as 27 choices, all eight furnished-room slots and one Priel choice with 46 locations. Both loaders rendered the compact source picker. No source fact, location or original DTO reference was replaced.
- [x] 10.3 Decouple tracker content from guide visibility and browsing selection. Verify real clicks across the originating quest and other entries while retaining its goal and source.
  - Checkpoint 6102810b6 carries the separately verified tracker correction onto the final composition. Real BepInEx click receipts and Lunaris browsing screenshots retain the originating guidance.
- [x] 10.4 Load Guide through the native Lunaris scanner without weakening JSON contracts or bundling loader-provided libraries.
  - Checkpoint 09dd7e08e uses JsonRequired instead of enum-valued metadata. All 722 host cases pass, including missing/null rejection. Both native builds report zero warnings/errors. Fresh native loading shows JsonRequired on the loaded type and no root Newtonsoft.Json.dll. The user explicitly enabled the mod through Lunaris's UI.
- [ ] 10.5 Verify the final crafting label and remaining reasonably feasible nested-source, timing, account/return and narrow/wide UI states. Preserve sound0 and actual responsive input.

## 8. Close-out

Release planning, packaging dry runs, and publishing are outside this change's assignment.

- [ ] 8.1 Run the Lunaris smoke check of design D12. Verify: the result is recorded under this task and the game has exited.
- [ ] 8.3 Open an issue in the format of issue #282 for each non-goal except multi-quest navigation, after checking it against the current code, and close issue #298 with the commit that fixes it. Verify: each issue link is recorded under this task.
- [ ] 8.4 Run `uv run erenshor test ci`, sync the specs, and archive the change. Propose the multi-quest navigation change afterwards. Verify: CI passes and both specs exist under `openspec/specs/`.
