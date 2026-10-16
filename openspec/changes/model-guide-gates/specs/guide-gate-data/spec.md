# Spec Delta

## Purpose

Defines how the pipeline records when zone lines, placed characters, spawn points, and item sources are available to the player, from the shipped game data through the clean database to the quest guide data that AdventureGuide embeds.

## ADDED Requirements

### Requirement: Gates are conditions over a closed set of atoms

The pipeline SHALL express every gate as a condition: a list of groups, where the condition holds when every atom of at least one group holds. A subject without a condition SHALL always be available, and a condition without groups SHALL never hold. The observable atoms SHALL be: a quest is completed, a quest is not completed, an item is in the inventory, a key is on the keyring or in the inventory, and a Reliquary room slot holds a furniture set. The advisory atom SHALL be: an encounter has been won, named by the characters that must die. Each atom SHALL name its quest, item, furniture set, or character by stable key. A condition that names an unknown quest, item, set, or character SHALL fail the build that produces it.

#### Scenario: Alternative unlocks

- **WHEN** the Duskenlight Coast zone line to the Jaws of Sivakaya opens either with the Nighthollow Candle or after She Sees You
- **THEN** its condition has one group with the candle atom and one group with the quest atom

#### Scenario: A dangling reference

- **WHEN** a gate names a quest that the clean database does not contain
- **THEN** the build fails and names the gate and the quest

### Requirement: Every availability rule is a condition

The pipeline SHALL express every rule that decides whether a zone line, a placement, a spawn point, an item source, a vendor offer, or an item bag is available as a condition, and SHALL keep no other representation of these rules. This SHALL include quest listener effects, keyed doors, removed barriers, scripted activators, quest-started and quest-stopped spawn points, Reliquary furnishings, vendor stock unlocks, item bag unlocks, and encounter prerequisites. Conditions SHALL attach to placements and spawn points, not to characters, so that copies of one character can differ.

#### Scenario: Two copies of one character

- **WHEN** the clean build runs on the current main build
- **THEN** the two Kio the Light Keeper placements in Shivering Step have different conditions

#### Scenario: A Reliquary furnishing

- **WHEN** a character stands in the Reliquary only when a room holds its furniture set
- **THEN** each of its room placements has a condition with the furnishing atom for that room and set

#### Scenario: No quest-only tables remain

- **WHEN** the clean build runs
- **THEN** the clean database has no `zone_line_quest_unlocks` or `character_quest_unlocks` table, and `gate_conditions` holds their gates

### Requirement: Keyed doors and removed barriers gate what they guard

A keyed door SHALL add a key atom for its key item to the condition of every target it guards. An object that a quest script removes SHALL add the atoms of its removal to the condition of every target it guards. A target SHALL be a zone line, a placement, an item bag, or a spawn point. A double door SHALL count as one gate. A door without a key SHALL NOT be a gate. The reviewed file `barriers.toml` SHALL state, for each keyed door and each removed object of the current build, the targets it guards or that it guards none, with a reason. The clean build SHALL fail when a keyed door or a removed object has no entry, and when an entry names an object that the build does not contain.

#### Scenario: A quest giver behind a door

- **WHEN** the clean build runs on the current main build
- **THEN** Ghost of Wyland Sercher's placement has a condition with the Ghostly Key atom

#### Scenario: A zone line behind a door

- **WHEN** the clean build runs on the current main build
- **THEN** the Stowaway's Step zone line to the Island Tomb at the lighthouse has a condition with the Stowaway's Step Lighthouse Key atom

#### Scenario: A game update adds a locked door

- **WHEN** a new build adds a door with a required key that `barriers.toml` does not list
- **THEN** the clean build fails and names the door, its scene, and its key

#### Scenario: A game update removes a listed door

- **WHEN** `barriers.toml` lists a door that the new build no longer contains
- **THEN** the clean build fails and names the stale entry

### Requirement: Targets that only some entrances reach name those entrances

When a target stands where only some of the zone lines into its scene lead, `barriers.toml` SHALL name those zone lines with a reason, and the clean build SHALL record them for the target. The clean build SHALL fail when such an entry names a target or zone line that the build does not contain, or a zone line that leads into another scene. `quest-guide.json` SHALL carry the entry lines on the target's placements.

#### Scenario: Occuphage's ledge

- **WHEN** the clean build runs on the current main build
- **THEN** Occuphage's placement in the Island Tomb names the Stowaway's Step lighthouse zone line as its only entrance

### Requirement: Quest listener effects are exported in both directions

The export SHALL record each object that `QuestSpawnListener`, `MultiQuestListener`, or `DynamicContentManager` enables or disables, with the quests or the held item that trigger the effect. The clean build SHALL derive each target's availability from these effects. When the same trigger enables and then disables a target, the target SHALL be unavailable once the trigger holds.

#### Scenario: An item-triggered activation

- **WHEN** a `QuestSpawnListener` enables a target when the player holds an item
- **THEN** the target's condition has a held-item atom for that item

#### Scenario: A contradictory listener

- **WHEN** the clean build runs on the current main build
- **THEN** the copies of Lucian Revald and Revan Gavault that Meet the Fisherman enables and disables are unavailable after Meet the Fisherman
- **AND** their always-active copies remain available

### Requirement: Inactive placements need an exported activator

A placement or spawn point that is inactive when its scene starts SHALL be available only under the conditions of the exported effects that activate it. Without such an effect its condition SHALL never hold. Every serialized field of a game script that references a character or a scene object SHALL stay classified in the dynamic spawn catalog as a spawn, an activation, or neither with a reason, so that the export fails on a new activator instead of hiding its targets.

#### Scenario: An unused copy

- **WHEN** a placed character is inactive at scene start and nothing activates it
- **THEN** its placement is never available

#### Scenario: A new activator script

- **WHEN** a new build adds a script field that activates a character
- **THEN** the export fails and names the unclassified script and field

### Requirement: Zone line usability is recorded and respected

The export SHALL record for each zone line whether its component is enabled and whether its collider is a trigger. A zone line whose component is disabled or whose collider is not a trigger SHALL be unusable regardless of any quest that activates its object. A zone line that players cannot reach SHALL be marked unusable in `mapping.json` with a reason. The clean database SHALL record each zone line's usability and the reason when it is unusable. Every reader of zone lines, including the guide, the map, and the wiki's zone connections, SHALL exclude unusable zone lines.

#### Scenario: A quest activates a disabled component

- **WHEN** the clean build runs on the current main build
- **THEN** the Shivering Step zone line to Hidden Hills is unusable even after A Way To Erenshor

#### Scenario: Issue 298

- **WHEN** the clean build runs on the current main build
- **THEN** every Shivering Step and Shivering Tomb zone line that players cannot reach is unusable with its reason
- **AND** neither the map nor the generated wiki zone connections list it

### Requirement: Scripted activators follow pinned rules

For each game script whose activation logic the pipeline encodes, the export SHALL record the scene objects its serialized fields reference, and code facts SHALL pin the logic the pipeline encodes. The scripts SHALL include `ShiverEvent`, `ShiveringAngel`, `ShiveringPhantomWardListener`, the planar fight scripts that reveal restored gods, `MemorySphere`, `SivTorchLight`, and the key rule of `Door`.

#### Scenario: A game update changes the Shivering Step event

- **WHEN** a new build changes a quest that `ShiverEvent` checks, assigns, or finishes
- **THEN** `extract code-facts` fails and names the fact

#### Scenario: The event references a new object

- **WHEN** a new build adds a character to a `ShiverEvent` field
- **THEN** the clean build gives that character the condition of its field without a code change

### Requirement: The Shivering Step event is modeled from its rules

The guide SHALL model Meet Shivering Step as acquired on entering Shivering Step and completed by The Curator, The Gatekeeper, The Harbinger, and The Bridgekeeper. The first Kio SHALL be available until all four are complete. The second Kio SHALL be available once all four are complete and until Changing the Lighthouse is complete. The four keepers SHALL be unavailable once all four are complete. The Hider SHALL be available once The Shivering Torch is complete and until Warming the Isle is complete. The characters of the ten event spawn triggers SHALL be available once The Shivering Torch is complete, at their trigger sites. A delay that the event imposes SHALL appear as a note on the affected step.

#### Scenario: Before the keepers

- **WHEN** a player enters Shivering Step for the first time
- **THEN** Meet Shivering Step lists the four keeper conversations as its steps
- **AND** Find The Hider is not actionable

#### Scenario: After the torch

- **WHEN** The Shivering Torch is complete and Warming the Isle is not
- **THEN** The Hider is available and the four keepers are not

### Requirement: Encounter prerequisites are recorded as advisory atoms

The pipeline SHALL record, as encounter atoms, the deaths that reveal a character, remove an invulnerability, or open a barrier: the planar bosses before their restored gods, both Phantom's Wards before Warded Shadow is vulnerable, the four Reliquary Wards before the Reliquary Fiend, Eldoth Molorai before A Strange Hermit answers, and the bosses before their plane barriers.

#### Scenario: A restored god

- **WHEN** the clean build runs on the current main build
- **THEN** restored Fernalla's placement has a condition with an encounter atom for Fernalla

### Requirement: Quest guide data carries the conditions

`quest-guide.json` SHALL carry a table of conditions and a condition reference on each gated zone line, placement, spawn point, item source, vendor offer, and item bag. It SHALL carry the game item ID and the sources of every item that a condition names. It SHALL carry the usability of each zone line and SHALL omit no gate that the clean database records. The compiler SHALL be the only place that combines a subject's gates into its condition. The guide commands SHALL write no output besides `quest-guide.json`.

#### Scenario: A door gate reaches the mod

- **WHEN** `erenshor guide export-mod` runs on the current main build
- **THEN** Founder's placement references a condition with the Dockhouse Key atom
- **AND** the data lists the Dockhouse Key's game item ID and sources

#### Scenario: No gate is lost

- **WHEN** the contract test compares the clean database's conditions with `quest-guide.json`
- **THEN** every gated subject in the database has the same condition in `quest-guide.json`

### Requirement: Requirement chains are acyclic

The compiler SHALL check that following unmet observable atoms from any gated subject to the subjects that satisfy them never returns to the starting subject through required atoms alone. It SHALL fail and name the cycle otherwise. An alternative group that leads back SHALL NOT count as a cycle when another group of the same condition does not.

#### Scenario: A key behind its own door

- **WHEN** the only source of a key is behind the door that the key opens
- **THEN** the compile fails and names the door, the key, and the source
