# Spec Delta

## Purpose

Define how the live map companion supplies immutable NPC origin information so a map can distinguish exact exported character identity from honest name-based fallback without breaking existing companion clients.

## Evidence

Current entity/wire contract: `src/mods/InteractiveMapCompanion/src/Entities/EntityData.cs:8-39`, `src/mods/InteractiveMapCompanion/src/Protocol/MessageSerializer.cs:12-20`, `src/mods/InteractiveMapCompanion/src/Protocol/ProtocolVersion.cs:9`. Original object names are lost at startup: `variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/NPC.cs:462-467`. The capture precedent is `src/mods/AdventureGuide/src/Navigation/NpcOrigins.cs:30-78`, `src/mods/AdventureGuide/src/Patches/NpcStartPatch.cs:21-29`. Export identity and duplicate suffixes: `src/Assets/Editor/StableKeyGenerator.cs:155-183`. Non-fatal client negotiation: `src/maps/src/lib/map/live/connection.ts:129-145`. The requirements below specify proposed behavior, not already-implemented behavior.

## ADDED Requirements

### Requirement: NPC origin survives name changes and movement

For friendly and enemy NPCs whose startup is observed, the companion SHALL report their original prefab object name, or their original scene object name, scene and starting position. That origin SHALL remain unchanged by runtime renaming or movement, and SHALL NOT be derived from display names or current positions.

#### Scenario: A spawned prefab is renamed

- **WHEN** an enemy or friendly NPC starts from a prefab clone and the game changes its object name to its runtime NPC name
- **THEN** subsequent snapshots report the original prefab object name without the terminal clone suffix
- **AND** changing the NPC's position does not change its reported origin

#### Scenario: A placed NPC walks away

- **WHEN** an NPC placed in a scene starts and later walks away from its starting position
- **THEN** its origin retains the pre-rename scene object name, captured scene and original scene-local Unity `[x,y,z]` position
- **AND** its normal entity position continues to report its current position

#### Scenario: Character startup precedes NPC startup

- **WHEN** a prefab's character component starts before its NPC component
- **THEN** the NPC's origin is captured when NPC startup is observed
- **AND** later entity snapshots do not depend on the character component having initialized an NPC reference first

### Requirement: Identity enrichment is optional and additive

The companion SHALL advertise protocol `0.3.0` and add optional `characterOrigin` to entity snapshots without changing existing required fields or message types. Prefab origins SHALL contain `kind: "prefab"` and normalized `objectName`; placed origins SHALL contain `kind: "placed"`, normalized `objectName` and `scene`, and finite three-number `position`. Names SHALL be trimmed and invariant-lowercased. Absent origins SHALL be omitted; capabilities SHALL remain `["entities"]`.

#### Scenario: A snapshot contains captured NPC origins

- **WHEN** protocol `0.3.0` sends NPCs with captured origins
- **THEN** each NPC carries its applicable camelCase `characterOrigin` object
- **AND** every existing entity field and its meaning remain unchanged

#### Scenario: Non-NPC entities are broadcast

- **WHEN** a snapshot includes a player, SimPlayer or pet
- **THEN** those entities have no `characterOrigin` field

#### Scenario: An old site receives a new snapshot

- **WHEN** a name-only site consumer receives the additive identity payload
- **THEN** the existing entity name, position, rotation, classification and conditional fields remain usable without understanding `characterOrigin`

### Requirement: Missing origins remain explicitly unknown

The companion SHALL omit origin when it did not observe the NPC's pre-rename startup. The map SHALL treat missing, unsupported or malformed origin as unresolved identity without rejecting an otherwise usable entity snapshot or inventing an exact character key.

#### Scenario: The mod loads after an NPC started

- **WHEN** an already-started NPC is first found after companion activation or reload
- **THEN** that NPC has no claimed origin derived from its renamed object name
- **AND** the live map continues using its name-based fallback

#### Scenario: An origin descriptor cannot be interpreted

- **WHEN** an entity has an unknown origin kind, an incomplete placed origin or non-finite placement coordinates
- **THEN** identity resolution falls back to name-based candidates
- **AND** the entity remains visible and other valid entities in the snapshot continue working

### Requirement: Origin state respects NPC and mod lifetimes

Captured origin SHALL belong to the NPC object that produced it. Destroyed NPCs SHALL NOT be kept alive by origin storage, and unloading the companion SHALL remove its capture hooks and stored origins. A replacement NPC SHALL NOT inherit an origin solely because an instance ID was reused.

#### Scenario: A destroyed NPC is replaced

- **WHEN** an NPC is destroyed and another NPC appears
- **THEN** the replacement's origin comes only from its own observed startup
- **AND** no old origin is selected by reused numeric instance ID

#### Scenario: A companion is unloaded and reloaded

- **WHEN** the companion unloads and then activates again in the same game session
- **THEN** no duplicate capture hooks or stale origins remain from the prior activation
- **AND** already-started NPCs remain unknown until their startup can be observed anew
