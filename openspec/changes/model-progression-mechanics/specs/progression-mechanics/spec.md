## Purpose

Records what makes each zone, placement, source, and route of the game available, from the shipped scripts, their serialized fields, code facts, and reviewed spatial facts, and fails when a game script that gates progression is not modeled.

## ADDED Requirements

### Requirement: Every script that reads or changes progression state is classified

The code-facts run SHALL list every script type of the shipped assembly that reads quest, item, account, or weather state, or that changes scenes, quests, invulnerability, or weather. It SHALL fail when a listed type is neither classified by the component that models it nor excluded with a reason, or when a catalog entry names a type that the assembly lacks.

#### Scenario: An unclassified script

- **WHEN** a game update adds a script type that reads quest state and no catalog entry classifies it
- **THEN** `extract code-facts` fails and names the type and the state it reads

#### Scenario: The Jaws statue

- **WHEN** the run lists `JawsStatueStartup`
- **THEN** its catalog entry names the export adapter that records its effect

### Requirement: Hand-coded literals come from code facts

A quest, item, scene, or spell name that a classified script hard-codes SHALL reach the clean build only from a code fact that extracts it from the shipped assembly. The clean build SHALL fail when that fact fails.

#### Scenario: A changed literal

- **WHEN** `ShiveringAngel` checks another quest in a new game build
- **THEN** the code-facts run fails and names the fact

### Requirement: An object's activation reaches what it contains and hosts

A subject SHALL be available only while its object and every ancestor are active, and a controller's effect only while the controller's host is active. The characters that a controller spawns SHALL be such effects. Initial activity SHALL come from the export. An activation effect on an object SHALL apply to its whole subtree. A subject that starts inactive without a recorded activation SHALL be unavailable, whether it is a spawn point or a placed copy.

#### Scenario: The planning portals

- **WHEN** reading the zone line that the planning table opens for Rune of Elements
- **THEN** it needs Claiming the Reliquary done as well as the rune in its slot

#### Scenario: The last phase of a fight

- **WHEN** reading the Fallen Fernalla that drops the Inert Rune of Fernalla
- **THEN** it needs Twisted Fernalla's spawn point, and so A Dying Wish, Part 4

#### Scenario: An inactive placement

- **WHEN** a spawn point or a character copy starts inactive and no effect activates it
- **THEN** its placement has a gate that never holds

### Requirement: Effects that follow deaths need those deaths

A spawn or an activation that a controller performs once a set of characters is dead SHALL need a defeat of each character of that set. The export SHALL record the set with the effect.

#### Scenario: Astra, Rogue of the Stars

- **WHEN** reading the ways to Heart of Astra
- **THEN** Astra, Rogue of the Stars needs every Stardust defeated

#### Scenario: The Azynthian Keeper

- **WHEN** reading the ways to Eldrich Crystal
- **THEN** the Azynthian Keeper needs the four Shadows of Secluded Sanctuary defeated

### Requirement: Spawns that a round or a summoner releases need what releases them

A character that an arena round spawns SHALL need that round's coin, once for each round it fights in. A round's award chest SHALL need the round's coin and a defeat of each fighter of the round. A character that another character summons SHALL need its summoner as the summoning script decides: a summon during a fight needs any one of its summoners, a summon after deaths needs the death of each summoner, and a summon by dialog needs the summoner's spawning dialog and the quest that the dialog requires. An add that a fight spawns SHALL join no death set, because a fight that ends before its adds spawn still releases its reward.

#### Scenario: The round 8 chest

- **WHEN** reading the ways to Vithean Chest (Round 8)
- **THEN** it needs Vithean Arena Fee (8) and Vitheo the Tactician defeated

#### Scenario: A summoned add

- **WHEN** reading the ways to a character that Honsus summons
- **THEN** the way through Honsus's summon needs Honsus

#### Scenario: The bridge chest

- **WHEN** reading the ways to the Braxonian Chest on the bridge of the Plane of Elements
- **THEN** its one way needs both Frost and Inferno defeated

#### Scenario: A round's adds

- **WHEN** reading the ways to Vithean Chest (Round 7)
- **THEN** it needs Honsus defeated and no Vithean Executioner

### Requirement: Barriers take their opening condition from their mechanism

Each object that blocks access SHALL be a barrier whose opening condition comes from its mechanism: a keyed door, an object that a quest listener or another classified script removes or moves, or guardians that a trigger calls. Each gate that a barrier causes SHALL be named by the barrier's key.

#### Scenario: The angel statue

- **WHEN** reading the zone line into Shivering Tomb (2)
- **THEN** it is behind the angel statue, which opens when Stand, Angel! is done

#### Scenario: Vessel Siraethe

- **WHEN** reading Vessel Siraethe
- **THEN** she is behind the gaze wall of Jaws of Sivakaya, which opens when She Sees You is done
- **AND** behind the Wards of Piety, which stay away once A Pious Guest is done

#### Scenario: A keyed door

- **WHEN** reading the zone line into Fallen Braxonia
- **THEN** it is behind the door that the Ancient Braxonian Key opens

### Requirement: Every barrier has a reviewed record of what it guards

`barriers.toml` SHALL list for each barrier the targets it guards, a reason, and the in-game check that confirmed them. The clean build SHALL fail when a barrier has no record, when a record names a barrier or a target that the build lacks, or when a barrier's mechanism no longer matches its record.

#### Scenario: A new barrier

- **WHEN** a game update adds a keyed door or a classified barrier without a record
- **THEN** `extract build` fails and names the barrier

#### Scenario: A removed target

- **WHEN** a record names a spawn point that the build lacks
- **THEN** `extract build` fails and names the record and the spawn point

### Requirement: Travel is one set of facts

The clean database SHALL record each way to move between zones, whether a zone line, a teleport item, or a scene switch by spell, with its source zone, its destination, its conditions, and its mechanism. A destination that comes from saved state SHALL NOT be a fixed destination.

#### Scenario: The Dimensional Rift

- **WHEN** reading travel into Azynthi's Garden (Dimensional Rift)
- **THEN** one entry starts in Azynthi's Garden and needs the Dimensional Rift spell, which the Azynthian Riftstone casts

#### Scenario: A saved return

- **WHEN** reading the Reliquary Hall exit to the zone a player came from
- **THEN** it has no fixed destination

### Requirement: Gates can need a world state

The clean database SHALL record each scene's limits on natural weather and each spell that changes the weather, and a gate SHALL be able to need a world state in a scene. Rain in a scene SHALL need a weather spell when the scene's limit keeps natural rain from starting.

#### Scenario: Rain in Braxonian Desert

- **WHEN** reading what makes it rain in Braxonian Desert
- **THEN** it needs Invoke Storm cast there, which Tempestalia, Ring of Storms casts and Spell Scroll: Invoke Storm teaches
- **AND** natural weather is not a way

#### Scenario: The raid planes become reachable

- **WHEN** the clean build runs with the weather facts recorded
- **THEN** each of the four raid planes has a playthrough tier in the requirement graph

### Requirement: Item actions preserve their class and learning level requirements

A teaching way SHALL need an allowed learner class through a class node and SHALL record the spell's required learning level on its teaching need. Item use and equip needs SHALL preserve the corresponding item-class restrictions. An action that admits every playable class SHALL remain unrestricted. Required level SHALL NOT change the playthrough tier.

#### Scenario: Learning Invoke Storm

- **WHEN** reading the ways to Invoke Storm
- **THEN** Spell Scroll: Invoke Storm needs Druid and records required level 8
- **AND** Tempestalia, Ring of Storms remains usable by every playable class


### Requirement: Gates can need a faction standing

The clean database SHALL record the rules by which a world faction's standing blocks an NPC's dialog, and a gate SHALL be able to need a standing with a faction. A dialog route or relation with an NPC SHALL need the standing that those rules require, and the standing SHALL need a recorded source that produces it.

#### Scenario: The Loss Stone

- **WHEN** reading the ways to the Loss Stone
- **THEN** the Arcane Headmaster's dialog needs the Pupil's Pin equipped

#### Scenario: A faction that starts below zero

- **WHEN** an NPC's faction starts below zero and the rules block its dialog
- **THEN** its dialog routes need a standing that a recorded quest or kill raises

### Requirement: Consumers add no gates of their own

Every gate that a consumer applies SHALL come from the clean database. The Adventure Guide's overrides SHALL hold only wording.

#### Scenario: The guide overrides

- **WHEN** reading `quest_guides/graph_overrides.toml`
- **THEN** it holds no gate
