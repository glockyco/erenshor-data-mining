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
| The Inert Rune of Fernalla needs A Dying Wish, Part 4 | `FernallaFightEvent` runs the fight on Twisted Fernalla's spawn point, which spawns only after A Dying Wish, Part 4. Its last phase spawns the Fallen Fernalla that drops the rune (`FernallaFightEvent.cs`, lines 204 to 283). The export records the phase spawn without its host. | Hierarchy activity |
| The Azynthian Keeper needs the four Shadows | `StowawayPortal` enables `KeeperSpawn`, the Keeper's spawn point, which starts disabled, once the four Shadows that check in through `SkeletonCheckin` are dead (`StowawayPortal.cs`, lines 146 to 207). The spawn catalog denies `KeeperSpawn` as a position marker. The clean build ignores that a spawn point starts disabled, as it does for 117 other spawn points that start disabled. | Hierarchy activity, death triggers |
| Astra and the Freed Spirit of Raval need deaths | `AstraListener` spawns its prefab once the NPCs of all its `StarSpawns` are dead: Astra, Rogue of the Stars after the Stardust, the Freed Spirit of Raval after Raval, and Ancient Canine in Azynthi's Garden (`AstraListener.cs`, lines 40 to 107). The export records each spawn without its trigger, and the inventory missed the type, because `SpawnPoint.MyNPCAlive` was not in its API set. | Death triggers, behaviour coverage |
| The Loss Stone needs the Pupil's Pin | The Arcane Headmaster belongs to `AncientSchool`, which `Inventory` sets to 10 while the Pupil's Pin is in the charm slot and to -10 otherwise (`Inventory.cs`, lines 756 to 762). A hail gets "..." below zero (`NPCDialogManager.cs`, line 133). An NPC at zero or below aggroes the player (`NPCAggroArea.cs`, line 166), and an NPC with an aggro target answers no keyword (`NPCDialogManager.cs`, line 191). Eight world factions start below zero, and the 11 Aquilimar NPCs all have dialog. | Faction standing |

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

`CodeFacts` gains an inventory mode. It decompiles every type of `Assembly-CSharp` and lists each type whose code reads `GameData.IsQuestDone`, `GameData.CompletedQuests`, `GameData.HasQuest`, `Inventory.HasItem`, `Inventory.HasCosmetic`, `GameData.AccountClaimedReliquary`, `AtmosphereColors.isRaining`, `SpawnPoint.MyNPCAlive`, or `WorldFaction.FactionValue`, or writes through `SceneChange.ChangeScene`, `SceneChange.ChangeSceneSafe`, `GameData.FinishQuest`, `GameData.AssignQuest`, `Character.Invulnerable`, `AtmosphereColors.WeightGoal`, `AtmosphereColors.SinceRain`, or `NPCFaction.Value`. It resolves symbols through the decompiler's type system, not text.

A catalog in `src/tools/CodeFacts/specs/` holds one entry for each listed type: `adapter` with the export adapter or processor rule that models it, `core` with the component of the pipeline that models it, `excluded` with a reason, such as a tutorial popup, or `pending` with the task of this change that will model it. Each entry records the state APIs that the type uses. The run fails on an unlisted type, on a stale entry, on a `pending` entry without a task, and on a type whose set of state APIs changed, because a new read or write can be a new gate. A `pending` entry is a visible, tracked gap, not an exception: the change cannot archive while one remains.

The API set is a starting set. When a review finds a gate that the inventory missed, the API that reveals it joins the set in the same commit, with the miss as evidence.

Alternatives considered:

- Extend the export's field catalog. Rejected: a script can gate progression with no serialized field of interest, as `ShiveringAngel` does with a literal quest key.
- Review scripts by hand after each update. Rejected: nothing would fail when a review is skipped.

### D2. Export adapters and the object hierarchy

The export keeps its contracts and adds:

- An `ObjectHierarchy` record for each object that is a subject, hosts a classified controller, or is an ancestor of one: its key, its parent, its scene, and whether it is active in the scene file. Subject records name their object, and each dynamic spawn names the object of the controller that spawns it.
- Adapters, or rules for exported ones, for the types that D1 classifies and nothing models: `JawsStatueStartup` (enables a controller after a quest), `PietyTrigger` (calls guardians unless a quest is done), and `SivTorchLight` (removes an object after a quest). The Bellwain Island scripts that gate its quests, `BellsieWineTrigger`, the item-gated torch action of `PlayerControl`, and the Bellwain group of `AngelScript`, get their effects recorded the same way (task 3.4). A reference to another classified controller, such as `JawsStatueStartup.Vision`, is exported as that controller's source key, and a serialized identifier, such as `BellsieWineTrigger.IDtoActivate`, as its string for the clean build to resolve.
- Scripted quest completions come from their controllers, not from a list in the export: a code fact names the quest that a classified script finishes, and the controller's instance says where it acts (`scripted_events`). Each becomes a completion route in its zone that needs what the controller and its rule need, such as The Guardian Awakens for She Sees You and the Rainbow Flint for Bellwain Isle.
- The missing references of classified types that the guide's inactive-placement audit found: the wards of `FernallaPortalBoss`, the Bellwains of `AngelScript`, and the portal identities of `PlanningTable`.
- The trigger sets of the effects that follow deaths: the `StarSpawns` of `AstraListener`, and the characters that check in to `StowawayPortal` through `SkeletonCheckin` with the `KeeperSpawn` that their deaths enable.

### D3. Hierarchy activity

An object is available when it is active in the scene file or an activation effect enables it, it has not been disabled, and its parent is available. A subject is available when its object is. A controller's effects need its host to be available, and the characters that a controller spawns are such effects: the last phase of the Fallen Fernalla fight needs Twisted Fernalla's spawn point. Disable effects keep their inverse conditions.

This rule replaces `UiItemSourceListener`'s separate activation export (`UiItemAccessActivations`) and the processor path that reads it, because the Box of Portals inherits `PlanningDesk`'s activation like the portals do. A placement that starts inactive, itself or through an ancestor, and that no effect enables gets a gate that never holds. This covers spawn points as well as placed copies: the guide's audit of 45 copies is one input, and the 118 spawn points that start disabled, 26 by their component and 92 by an inactive object or ancestor are audited the same way. Each audited placement gets its activator exported or the gate that never holds. This is task 4.2 of `model-guide-gates`, widened to spawn points.

An effect can follow deaths. `AstraListener` spawns its prefab once the NPCs of all its `StarSpawns` are dead, and `StowawayPortal` enables `KeeperSpawn` once the characters that check in through `SkeletonCheckin` are dead. The export records each such trigger set with the effect, and the clean build gives the spawned or enabled subject a `defeated` need for each character of the set. The dynamic spawn catalog classifies `KeeperSpawn` as an activation, not a position marker.

A death set retains the number of distinct triggering placements for each character. Its `defeated` need requires all those copies to be dead together, not repeated kills of one copy. The graph includes the release needs of every distinct copy, so consumptive items such as Lost Faith multiply by the number of copies. Persistent quest and world-state conditions do not multiply.

The guide retains the same defeat count in its condition payload and canonical source guidance. A missing quantity in older guide data means one defeat. Both views say "Defeat Raval" for one copy and "Defeat all 9 Stardust" for a set. Defeats remain advisory because the guide does not track kills.

### D4. Barriers

A barrier is an object that blocks access until its mechanism opens it:

| Kind | Opening condition | Example |
|---|---|---|
| `door` | the key, held or on the keyring | the door into Fallen Braxonia |
| `removed` | the quest, death, or effect that disables the object | `BreakWall` after She Sees You, quest-listener removals in Blooming Sepulcher and Vitheo's Rest, `SpawnIfAlive` objects while their boss lives |
| `moved` | the condition under which a script moves the object away | the angel statue after Stand, Angel! |
| `guardians` | the condition under which a trigger does not call its guardians | the Wards of Piety until A Pious Guest |

A `guardians` barrier opens when the trigger's quest is done. The trigger stops calling its guardians once the quest is done, but guardians that it already called stay, as the guide's requirement "Transient activation stays advice" states for `PietyTrigger`. So the need tells a player what to do first and does not claim that the game removes them.

The opening condition comes from the exported mechanism, never from the review. A mechanism needs its controller: a quest listener's host must be active, and a script must be able to run, which a behaviour that starts disabled can only once another controller enables it. A door that a quest listener also removes opens with its key or the quest. `barriers.toml` records, for each barrier, its kind, a player-facing name, its objects, the first of which names the barrier, the guarded targets, a reason, and the check that confirmed the targets: `navmesh` or `render`, or `unconfirmed` until an in-game check confirms them. Each gate that a barrier causes is named by the barrier's key, and the clean `barriers` table gives the graph its kind and name, so readers can treat a barrier as one thing.

The clean build fails on an object that a mechanism opens without a record, on a record whose object or target the build lacks, on a record whose kind no longer matches the mechanism, and on a record that joins objects that open differently. A placement's own object is its availability, not a barrier. A barrier that guards nothing a player needs has an empty target list and a reason.

### D5. Travel

`travel_routes` records each way between zones: its mechanism (`zone_line`, `teleport`, or `spell`), source zone, destination zone, the source key (the zone line, the teleport item, or the spell), and the gate key of its conditions. A zone line keeps its own gates. A spell route needs the spell, and the requirement graph finds the items that cast or teach it through `items.item_effect_on_click_stable_key` and `items.teach_spell_stable_key`. A saved-return line from `zone_line_destination_contexts` gets no fixed destination.

A code fact extracts the scene switches of `SpellVessel`'s spell switch: the spell name and each pair of scenes. A changed set fails the run.

Zone line usability lands here as well: `is_usable` and `unusable_reason` from the component and collider state and from reviewed `zoneline:` rules in `mapping.json`, with the map and wiki readers excluding unusable lines (task 5.2 of `model-guide-gates`, with the guide's usability proposal as input).

### D6. World state

The export records each `WeatherTrend` with its scene and limits. Code facts pin the rain rules: the start threshold and the sun condition in `AtmosphereColors.Update`, the clamp and the pull of `WeatherTrend`, and the weather effects of Invoke Storm and Dissipate Storm in `SpellVessel`. From these the clean build derives, for each scene, whether natural rain can start: the scene uses the sun and its cap, if any, is not below the start threshold.

A new gate atom kind `world_state` names a state and its scene, such as rain in Braxonian Desert. Its producers are the weather spells and, where it can start, natural weather. A release with the state `raining` needs that atom.

Only a cap below the start threshold counts as a hard limit. A scene where rain can start naturally keeps natural weather as a way, even if rain is rare there.

Sun use comes from the serialized zone-line transition flag, not the zone's dungeon label. Conflicting incoming flags fail the build. A scene without an incoming flag has no weather producer until its travel mechanism supplies that evidence. A nonpositive limit is not a persistent cap, because `WeatherTrend.Update` does not pull toward it.

Item actions keep the class and level checks that make them executable. Teaching needs the learner's class from `ItemClasses`, with one way per allowed class through the existing class nodes, and records the spell's required learning level on the teaching need. Click use and equip needs use the corresponding `ItemClasses` rule. An action that admits every playable class adds no class restriction. `ItemIcon.OnPointerUp` supplies the pinned teaching and click-use rules. Level is a need attribute, not a tier, because the graph does not model level progression.

### D7. Rule-specific branches retire

When a general rule covers a branch of `_scripted_gates`, the branch goes in the same slice: `shivering_angel` with D4 and the host part of the planning portals with D3. A literal quest key in Python goes when its code fact delivers it. Each slice compares the rebuilt clean database with the previous build through `extract changes`, and every changed gate must be an intended one.

### D8. Coordination with `model-guide-gates`

The guide session ended, and its consumer branch landed on main in `e8ff3731b`. Tasks 4.1, 4.2, 5.1, 5.2, and 6.1 of `model-guide-gates` moved here with their requirements (task 0.1). Its inactive-placement audit and inventory, scene proofs, proposals, and door reviews were inputs, reviewed one unit per commit and not merged as they were. `model-guide-gates` keeps navigation, its runtime budgets, and its UI.

1. This change's work, the guide changes it needs, and the in-game checks run on main in one session.
2. After each mechanism lands, a guide change deletes the override that it covers and regenerates `quest-guide.json`.
3. When `model-guide-gates` archives, the shared requirements of `guide-gate-data` move into `progression-mechanics`, so the shared data has one spec.

### D9. In-game checks

Each mechanism kind gets one check through HotRepl that sets its trigger and observes its effect: a barrier closed and open, a controller's host disabled and enabled, a spawn that follows deaths, the Dimensional Rift switching scenes, Invoke Storm starting rain in Braxonian Desert while Evadne the Corrupted becomes vulnerable, and the Arcane Headmaster's dialog with and without the Pupil's Pin. Each barrier record gets a containment check: a NavMesh path from each entrance landing to each guarded target fails while the barrier stands and succeeds after it opens, as the door reviews did. Checks run on a dedicated character slot, with sound off, leave the player's saves unchanged, and end with the normal shutdown. Their evidence stays in the variant's storage.

### D10. Owners, failure handling, grouping, and rollback

| Artifact | Owner | Written by |
|---|---|---|
| Export listeners, catalogs, and field coverage | repository | `extract export` reads them, reviewed commits change them |
| Behaviour catalog and code facts | repository | `extract code-facts` checks them |
| `barriers.toml`, `mapping.json` | repository | reviewed commits, checked by `extract build` |
| `gate_conditions`, `travel_routes`, the world state tables | clean build | `extract build` |
| Gates in `quest_guides/graph_overrides.toml` | `model-guide-gates` | guide changes remove them |

The export fails with status 3 on an unclassified field, the code-facts run on an unclassified behaviour, and the clean build on a barrier, travel, or world state contract violation, each naming the type, barrier, or target. A failed step leaves the published clean database unchanged.

Each mechanism is one slice: its export or code facts, its processor rule, its tests, its in-game check, and a review of the requirement graph's raid chains, then the guide's override removal. A slice rolls back by reverting its commits and rebuilding. The backup keeps the previous clean database.

### D11. Faction standing

A world faction's standing decides whether its NPCs talk. A hail gets "..." below zero (`NPCDialogManager.GenericHail`). An NPC at zero or below aggroes the player (`NPCAggroArea`), and an NPC with an aggro target answers no keyword (`NPCDialogManager.ParseText`). Standings start at each faction's default, and quest rewards and kill modifiers change them, which the export already records (`factions`, `quest_faction_affects`, `character_faction_modifiers`). `Inventory` overrides `AncientSchool` from the charm slot: 10 while the Pupil's Pin is equipped, -10 otherwise.

Code facts pin the hail threshold, the aggro threshold, the keyword rule, and the Pupil's Pin rule with its item and values. A new gate atom kind names a standing with a faction that the rules require, such as `faction_standing:ancientschool:non_negative`. Its producers are the repeatable sources that raise the faction from its default and, for `AncientSchool`, the equipped Pupil's Pin. A dialog route or relation with an NPC of a world faction needs the standing that the rules require for that interaction. Which interactions a standing blocks comes from the in-game check (D9) before the rule lands, because `never_aggro` and aggro range decide whether keyword dialog is reachable at all.

### D12. Spawns that rounds and summoners release

`VithArena` runs eight rounds. Entering its trigger consumes the first coin the player carries, from `Coin1` to `Coin8`, and spawns that round's fight list (`CheckForGamepiece`, `SpawnPiece`). Once every fighter it spawned is dead, together with every add that Honsus or the Vitheo fight reports through `ReportNewSpawn`, `Update` instantiates the round's award chest. The export records the rounds in `arena_rounds` and `arena_round_enemies`. A fighter needs the coin of each round it fights in, as one way per round, and an award chest needs its round's coin and a defeat of each fighter of the round, counted as a death set (D3). The coin pins the round, because fighters such as the Expert Gladiator fight in two rounds.

A character that another character summons is present only while its summoner is. `character_chained_spawns` records each summoner and its child, and the clean build expands the child's placements from the summoner's. The child's way needs its summoner, and the adds that a round waits for join the round's death set. Each summoning script is read before its children get the need, and a summon with further conditions gets those too.

### D13. Way ranks for consumers

The build already orders every way when it computes tiers: a way's tier is the highest tier of its needs, plus one at a milestone, and its depth is one more than the deepest of its needs. A node's first way is its way of lowest tier and depth, and first-way depths strictly decrease, so following first ways never returns to a node. The build stores each usable way's tier and depth, and the clean facts that produced the way, such as an item's acquisition key.

A consumer that has to choose among ways whose needs are not yet met ranks them by this order instead of searching at run time. The guide gives each item source the lowest rank among the ways of its acquisition, and prefers the lower rank among sources that need something first. Vithean Arena Fee (1) then leads to the Planar Stone trade of An Arena Token, not to the round 8 chest. That chest is a real way, through a fished Vithean Arena Fee (5) and rounds 5 to 8, but a later one. The buy-back of a fee ranks after the quest that turns the fee in, so it never comes first for a player who lacks the fee.

## Risks / Trade-offs

- The API set could miss a gate. The requirement graph's chain reviews and the guide's runtime checks find misses, and each miss widens the set with its evidence.
- Containment checks take time. They reuse the guide's door review method, and a barrier that guards nothing needs no path check.
- The handoff could stall. The requirement graph and the wiki view proceed meanwhile against the current facts, and nothing is published while a raid chain is known to be wrong.
- Weather is random. Only a cap below the start threshold is a hard limit.
- Uncommitted guide edits may diverge from this plan. They are inputs reviewed unit by unit, not merged wholesale.

## Migration Plan

1. Handoff (D8).
2. Behaviour coverage (D1): classify the listed types and record the list of mechanisms that need work.
3. Hierarchy activity and death triggers (D3), barriers (D4), travel and usability (D5), world state (D6), and faction standing (D11), each with its slice of D2 and D7, its in-game check, and a review of the raid chains.
4. The guide removes its covered overrides, and the specs are reconciled.

Rollback follows D10.
