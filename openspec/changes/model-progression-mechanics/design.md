## Context

See `proposal.md` for the motivation. The state on 2026-10-18, from the shipped scripts of build 24405256, the raw export, and the repository:

- The export walks prefabs and scenes and hands each component to listeners. `DynamicSpawnSourceListener` classifies every serialized field of a script against `dynamic-spawn-catalog.toml` as `allowed`, `denied`, or `activation`, and the export fails on an unclassified field that resolves to a `Character`. `ScriptedActivatorListener` exports the controllers of 19 classified script types with typed field contracts. `QuestActivationListener` exports the enable and disable effects of `QuestSpawnListener`, `MultiQuestListener`, and `DynamicContentManager` into `QuestActivationEffects`. Subject rows (`ZoneLines`, `SpawnPoints`, `Characters`, `ItemBags`, `Doors`) carry no object hierarchy.
- `gates.py` turns these into `gate_conditions`. `_activation_gates` skips effects on plain objects ("Object and door effects are facts for reviewed barrier containment"), which are 104 of the 150 rows of `QuestActivationEffects`. `_scripted_gates` skips disabled controllers and branches on eleven rule IDs. The `shivering_angel` branch and the Shivering Step event rule hold literal quest keys in Python. `barriers.toml` records keyed doors and their guarded targets, and the build fails on an unknown or unlisted door.
- `CodeFacts` decompiles the shipped assembly with `ICSharpCode.Decompiler` and checks hand-chosen methods, with `assert` facts for shapes and `extract` facts for values. No fact lists the scripts that gate progression.
- A planning grep found about 60 script types that read quest, item, account, or weather state, or change scenes, quests, invulnerability, or weather. The semantic inventory of D1, which resolves symbols, lists 58 in build 24405256, and the spawn and activation catalogs name fewer than half of them. Most of the rest are core systems with their own export, such as `TradeWindow`, `Door`, and `ZoneAnnounce`.

How the overrides and the gaps map to mechanisms:

| Case | What the game does | Missing rule |
|---|---|---|
| Planning portals need Claiming the Reliquary | `QuestSpawnListener` on `DisableIfNotClaimed` enables `PlanningDesk` after `CLAIMRELIQUARY`, and `PlanningDesk` hosts `PlanningTable`, which opens the portals (`PlanningTable.cs`, lines 41 to 63, 129 to 145, and 181 to 219). A separate export gives only the Box of Portals UI grant this condition. | Hierarchy activity |
| Shivering Tomb (2) needs Stand, Angel! | `ShiveringAngel` turns its statue once `STANDANGEL` is done (`ShiveringAngel.cs`, line 15). Its `shivering_angel` rule targets the statue, which `_scripted_targets` drops. | Barriers |
| The Jaws entrance needs the Nighthollow Candle or She Sees You | The entrance is open. The candle makes A Memory of Sivakaya appear (`MemorySphere`, already gated). Talking to her completes The Guardian Awakens, and `JawsStatueStartup` then enables the gaze statue (`JawsStatueStartup.cs`, lines 13 to 16). Its `SivTorchLight` completes She Sees You and removes `BreakWall` (`SivTorchLight.cs`, lines 24, 25, 37, and 39). `JawsStatueStartup` is not classified. `SivTorchLight` is exported as `siv_torch_gaze`, starts disabled, and no processor rule reads it. | Behaviour coverage, barriers |
| Vessel Siraethe needs A Pious Guest | Entering `PietyTrigger` without A Pious Guest enables six hostile Wards of Piety at level 99 that cannot be damaged (`PietyTrigger.cs`, lines 18 to 26). Saying "azynthi" to a Ward of Piety completes the quest. The trigger is exported as `piety_guardians`, and no processor rule reads it. | Barriers |
| The Dimensional Rift | `SpellVessel` switches between `Azynthi` and `AzynthiClear` for the spell (`SpellVessel.cs`, lines 2261 to 2275), and the Azynthian Riftstone casts it. Nothing exports it. | Travel |
| Rain for Evadne the Corrupted | `WeatherTrend` on the root object `Environmental` of Braxonian Desert caps the rain weight at 0.15 (`WeatherTrend.cs`, lines 15 to 29). Rain starts only above 0.55 in a scene that uses the sun (`AtmosphereColors.cs`, line 414). Invoke Storm sets the weight to 0.9 and clears the rain timer (`SpellVessel.cs`, lines 2158 to 2163). Four scenes have such a cap: Azynthi's Garden (0.5), Braxonian Desert (0.15), Old Krakengard (0.3), and Underspine Hollow (0.35). | World state |
| `BellsieWineTrigger` on Bellwain Island | Takes an item and enables objects (`BellsieWineTrigger.cs`, lines 19 to 29). Nothing exports or classifies it. | Behaviour coverage |

The Adventure Guide tab holds the open producer tasks of `model-guide-gates`: inactive placements (4.1 and 4.2), unusable zone lines (5.1 and 5.2), and removed barriers (6.1). It has an audit of 45 inactive character copies with the scripts that activate them, and uncommitted proposals for inactive placements, zone line usability, and activation damage. `model-guide-gates` lists travel that is not a zone line and weather as non-goals.

## Goals / Non-Goals

**Goals:**

- A game update that adds or changes a script that gates progression fails a check instead of passing silently.
- Each kind of mechanism has one general rule in the clean build, and reviewed facts cover only what code cannot tell.

**Non-Goals:**

- Replacing the existing export contracts that already work. New mechanisms extend them.
- Modeling combat phases, such as health-phase invulnerability, beyond the release conditions that `character_damage_releases` already records.

## Decisions

### D1. Behaviour coverage in the code-facts run

`CodeFacts` gains an inventory mode. It decompiles every type of `Assembly-CSharp` and lists each type whose code reads `GameData.IsQuestDone`, `GameData.CompletedQuests`, `GameData.HasQuest`, `Inventory.HasItem`, `Inventory.HasCosmetic`, `GameData.AccountClaimedReliquary`, or `AtmosphereColors.isRaining`, or writes through `SceneChange.ChangeScene`, `SceneChange.ChangeSceneSafe`, `GameData.FinishQuest`, `GameData.AssignQuest`, `Character.Invulnerable`, `AtmosphereColors.WeightGoal`, or `AtmosphereColors.SinceRain`. It resolves symbols through the decompiler's type system, not text.

A catalog in `src/tools/CodeFacts/specs/` holds one entry for each listed type: `adapter` with the export adapter or processor rule that models it, `core` with the component of the pipeline that models it, `excluded` with a reason, such as a tutorial popup, or `pending` with the task of this change that will model it. Each entry records the state APIs that the type uses. The run fails on an unlisted type, on a stale entry, on a `pending` entry without a task, and on a type whose set of state APIs changed, because a new read or write can be a new gate. A `pending` entry is a visible, tracked gap, not an exception: the change cannot archive while one remains.

The API set is a starting set. When a review finds a gate that the inventory missed, the API that reveals it joins the set in the same commit, with the miss as evidence.

Alternatives considered:

- Extend the export's field catalog. Rejected: a script can gate progression with no serialized field of interest, as `ShiveringAngel` does with a literal quest key.
- Review scripts by hand after each update. Rejected: nothing would fail when a review is skipped.

### D2. Export adapters and the object hierarchy

The export keeps its contracts and adds:

- An `ObjectHierarchy` record for each object that is a subject, hosts a classified controller, or is an ancestor of one: its key, its parent, its scene, and whether it is active in the scene file. Subject records name their object.
- Adapters, or rules for exported ones, for the types that D1 classifies and nothing models: `JawsStatueStartup` (enables a controller after a quest), `PietyTrigger` (calls guardians unless a quest is done), and `SivTorchLight` (removes an object after a quest). The Bellwain Island scripts that gate its quests, `BellsieWineTrigger`, the item-gated torch action of `PlayerControl`, and the Bellwain group of `AngelScript`, get their effects recorded the same way (task 3.4).
- The missing references of classified types that the guide's inactive-placement audit found: the wards of `FernallaPortalBoss`, the Bellwains of `AngelScript`, and the portal identities of `PlanningTable`.

### D3. Hierarchy activity

An object is available when it is active in the scene file or an activation effect enables it, it has not been disabled, and its parent is available. A subject is available when its object is. A controller's effects need its host to be available. Disable effects keep their inverse conditions.

This rule replaces `UiItemSourceListener`'s separate activation export (`UiItemAccessActivations`) and the processor path that reads it, because the Box of Portals inherits `PlanningDesk`'s activation like the portals do. A placement that starts inactive, itself or through an ancestor, and that no effect enables gets a gate that never holds. This is task 4.2 of `model-guide-gates`, with the guide's audit of 45 copies as input.

### D4. Barriers

A barrier is an object that blocks access until its mechanism opens it:

| Kind | Opening condition | Example |
|---|---|---|
| `door` | the key, held or on the keyring | the door into Fallen Braxonia |
| `removed` | the quest, death, or effect that disables the object | `BreakWall` after She Sees You, quest-listener removals in Blooming Sepulcher and Vitheo's Rest, `SpawnIfAlive` objects while their boss lives |
| `moved` | the condition under which a script moves the object away | the angel statue after Stand, Angel! |
| `guardians` | the condition under which a trigger does not call its guardians | the Wards of Piety until A Pious Guest |

A `guardians` barrier is advisory, as the guide's requirement "Transient activation stays advice" already states for `PietyTrigger`. The trigger stops calling its guardians once the quest is done, but guardians that it already called stay, so the need tells a player what to do first and does not claim that the game removes them.

The opening condition comes from the export and code facts, never from the review. `barriers.toml` records, for each barrier, its key, kind, guarded targets, a reason, and the in-game check that confirmed the targets. Keyed door entries move to this form in the same commit. Each gate that a barrier causes is named by the barrier's key, as door gates already are, so readers can treat a barrier as one thing.

The clean build fails on a barrier without a record, on a record whose barrier or target the build lacks, and on a record whose kind no longer matches the mechanism. A barrier that guards nothing a player needs has an empty target list and a reason.

### D5. Travel

`travel_routes` records each way between zones: its mechanism (`zone_line`, `teleport`, or `spell`), source zone, destination zone, the source key (the zone line, the teleport item, or the spell), and the gate key of its conditions. A zone line keeps its own gates. A spell route needs the spell, and the requirement graph finds the items that cast or teach it through `items.item_effect_on_click_stable_key` and `items.teach_spell_stable_key`. A saved-return line from `zone_line_destination_contexts` gets no fixed destination.

A code fact extracts the scene switches of `SpellVessel`'s spell switch: the spell name and each pair of scenes. A changed set fails the run.

Zone line usability lands here as well: `is_usable` and `unusable_reason` from the component and collider state and from reviewed `zoneline:` rules in `mapping.json`, with the map and wiki readers excluding unusable lines (task 5.2 of `model-guide-gates`, with the guide's usability proposal as input).

### D6. World state

The export records each `WeatherTrend` with its scene and limits. Code facts pin the rain rules: the start threshold and the sun condition in `AtmosphereColors.Update`, the clamp and the pull of `WeatherTrend`, and the weather effects of Invoke Storm and Dissipate Storm in `SpellVessel`. From these the clean build derives, for each scene, whether natural rain can start: the scene uses the sun and its cap, if any, is not below the start threshold.

A new gate atom kind `world_state` names a state and its scene, such as rain in Braxonian Desert. Its producers are the weather spells and, where it can start, natural weather. A release with the state `raining` needs that atom.

Only a cap below the start threshold counts as a hard limit. A scene where rain can start naturally keeps natural weather as a way, even if rain is rare there.

### D7. Rule-specific branches retire

When a general rule covers a branch of `_scripted_gates`, the branch goes in the same slice: `shivering_angel` with D4 and the host part of the planning portals with D3. A literal quest key in Python goes when its code fact delivers it. Each slice compares the rebuilt clean database with the previous build through `extract changes`, and every changed gate must be an intended one.

### D8. Coordination with `model-guide-gates` and the Adventure Guide tab

Behaviour coverage (D1) touches only the code-facts tool and starts at once. Everything else starts after a handoff that the maintainer confirms with both tabs:

1. The guide tab lands its consumer branch. Tasks 4.1, 4.2, 5.1, 5.2, and 6.1 of `model-guide-gates` move here with their requirements. The guide tab keeps navigation, its runtime budgets, and its UI.
2. The guide tab hands over its inactive-placement audit and inventory, its scene proofs, its proposals for inactive placements, zone line usability, and activation damage, and its door reviews. Its uncommitted producer edits are reviewed and re-applied here, one unit per commit, not merged as they are.
3. The game stays with the guide tab. Each in-game check here starts after the guide tab hands over the runtime slot, and ends with the normal shutdown and cleanup.
4. After each mechanism lands, a guide change deletes the override that it covers and regenerates `quest-guide.json` in the guide tab.
5. When `model-guide-gates` archives, the shared requirements of `guide-gate-data` move into `progression-mechanics`, so the shared data has one spec.

### D9. In-game checks

Each mechanism kind gets one check through HotRepl that sets its trigger and observes its effect: a barrier closed and open, a controller's host disabled and enabled, the Dimensional Rift switching scenes, and Invoke Storm starting rain in Braxonian Desert while Evadne the Corrupted becomes vulnerable. Each barrier record gets a containment check: a NavMesh path from each entrance landing to each guarded target fails while the barrier stands and succeeds after it opens, as the door reviews did. Checks run on a dedicated character slot, with sound off, leave the player's saves unchanged, and end with the normal shutdown. Their evidence stays in the variant's storage.

### D10. Owners, failure handling, grouping, and rollback

| Artifact | Owner | Written by |
|---|---|---|
| Export listeners, catalogs, and field coverage | repository | `extract export` reads them, reviewed commits change them |
| Behaviour catalog and code facts | repository | `extract code-facts` checks them |
| `barriers.toml`, `mapping.json` | repository | reviewed commits, checked by `extract build` |
| `gate_conditions`, `travel_routes`, the world state tables | clean build | `extract build` |
| Gates in `quest_guides/graph_overrides.toml` | Adventure Guide tab | guide changes remove them |

The export fails with status 3 on an unclassified field, the code-facts run on an unclassified behaviour, and the clean build on a barrier, travel, or world state contract violation, each naming the type, barrier, or target. A failed step leaves the published clean database unchanged.

Each mechanism is one slice: its export or code facts, its processor rule, its tests, its in-game check, and a review of the requirement graph's raid chains, then the guide's override removal. A slice rolls back by reverting its commits and rebuilding. The backup keeps the previous clean database.

## Risks / Trade-offs

- The API set could miss a gate. The requirement graph's chain reviews and the guide's runtime checks find misses, and each miss widens the set with its evidence.
- Containment checks take time. They reuse the guide's door review method, and a barrier that guards nothing needs no path check.
- The handoff could stall. The requirement graph and the wiki view proceed meanwhile against the current facts, and nothing is published while a raid chain is known to be wrong.
- Weather is random. Only a cap below the start threshold is a hard limit.
- Uncommitted guide edits may diverge from this plan. They are inputs reviewed unit by unit, not merged wholesale.

## Migration Plan

1. Handoff (D8).
2. Behaviour coverage (D1): classify the listed types and record the list of mechanisms that need work.
3. Hierarchy activity (D3), barriers (D4), travel and usability (D5), and world state (D6), each with its slice of D2 and D7, its in-game check, and a review of the raid chains.
4. The guide removes its covered overrides, and the specs are reconciled.

Rollback follows D10.
