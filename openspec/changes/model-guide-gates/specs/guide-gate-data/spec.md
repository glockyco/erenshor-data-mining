# Spec Delta

## Purpose

Defines how the pipeline records when zone lines, placed characters, spawn points, and item sources are available to the player, from the shipped game data through the clean database to the quest guide data that AdventureGuide embeds.

## ADDED Requirements

### Requirement: Gates are conditions over a closed set of atoms

The pipeline SHALL express gates as OR groups of AND-ed typed atoms. A subject without a condition SHALL always be available, and a condition without groups SHALL never hold. Only observable availability-phase predicates SHALL enter current-state conjunctions.

#### Scenario: Alternative unlocks

- **WHEN** the Duskenlight Coast zone line to the Jaws of Sivakaya opens either with the Nighthollow Candle or after She Sees You
- **THEN** its condition has one group with the candle atom and one group with the quest atom

### Requirement: Gate atoms retain typed domain metadata

Observable atoms SHALL cover quests, inventory, keys, furnished rooms, exact stored planning-slot items and supported account state. Advisory encounter atoms SHALL retain actual member identities and counts. Account atoms SHALL carry actor, reference, boolean value, phase and actual location scope. Boolean strings SHALL be exactly `true` or `false`.

#### Scenario: A false account predicate

- **WHEN** an account predicate with false availability is emitted
- **THEN** it retains its actor, reference, phase and actual location scope with the exact boolean string `false`

### Requirement: Gate contracts reject unknown references

Missing or unknown references, actors, phases, states or slots SHALL fail generation and contract loading.

#### Scenario: A dangling reference

- **WHEN** a gate names a quest that the clean database does not contain
- **THEN** the build fails and names the gate and the quest

### Requirement: Every availability rule is a condition

The pipeline SHALL express every rule that decides whether a zone line, a placement, a spawn point, an item source, a vendor offer, or an item bag is available as a condition, and SHALL keep no other representation of these rules. Conditions SHALL attach to placements and spawn points, not to characters, so that copies of one character can differ.

#### Scenario: Two copies of one character

- **WHEN** the clean build runs on the current main build
- **THEN** the two Kio the Light Keeper placements in Shivering Step have different conditions

#### Scenario: A Reliquary furnishing

- **WHEN** a character stands in the Reliquary only when a room holds its furniture set
- **THEN** each of its room placements has a condition with the furnishing atom for that room and set

#### Scenario: No quest-only tables remain

- **WHEN** the clean build runs
- **THEN** the clean database has no `zone_line_quest_unlocks` or `character_quest_unlocks` table, and `gate_conditions` holds their gates

### Requirement: Conditions cover every supported availability mechanism

Availability conditions SHALL include quest listener effects, keyed doors, removed barriers, scripted activators, quest-started and quest-stopped spawn points, Reliquary furnishings, vendor stock unlocks, item bag unlocks, and encounter prerequisites.

#### Scenario: Stock and bag unlocks

- **WHEN** vendor stock or an item bag has an unlock rule
- **THEN** the pipeline represents that rule as an availability condition

### Requirement: Keyed doors and removed barriers gate what they guard

A keyed door SHALL add a key atom for its key item to the condition of every target it guards. An object that a quest script removes SHALL add the atoms of its removal to the condition of every target it guards. A target SHALL be a zone line, a placement, an item bag, or a spawn point. A double door SHALL count as one gate. A door without a key SHALL NOT be a gate.

#### Scenario: A quest giver behind a door

- **WHEN** the clean build runs on the current main build
- **THEN** Ghost of Wyland Sercher's placement has a condition with the Ghostly Key atom

#### Scenario: A zone line behind a door

- **WHEN** the clean build runs on the current main build
- **THEN** the Stowaway's Step zone line to the Island Tomb at the lighthouse has a condition with the Stowaway's Step Lighthouse Key atom

### Requirement: Reviewed barriers cover current objects

The reviewed file `barriers.toml` SHALL state, for each keyed door and each removed object of the current build, the targets it guards or that it guards none, with a reason. The clean build SHALL fail when a keyed door or a removed object has no entry, and when an entry names an object that the build does not contain.

#### Scenario: A game update adds a locked door

- **WHEN** a new build adds a door with a required key that `barriers.toml` does not list
- **THEN** the clean build fails and names the door, its scene, and its key

#### Scenario: A game update removes a listed door

- **WHEN** `barriers.toml` lists a door that the new build no longer contains
- **THEN** the clean build fails and names the stale entry

### Requirement: Barrier entries declare one guarded object family

Entries SHALL use either `doors` or `objects`, never both, with mandatory guards and reason. Supported scripted obstructions SHALL also require exact reviewed guards or none.

#### Scenario: A scripted obstruction is reviewed

- **WHEN** a supported scripted obstruction is mapped
- **THEN** its entry uses exactly one object family and declares exact guards or none with a reason

### Requirement: Barrier removal conditions preserve trigger logic

Positive removal triggers SHALL gate passage, not inverse object-presence conditions. Alternative removal triggers SHALL be OR alternatives, while independent obstructions SHALL remain AND requirements. Unsupported inverse/item-state semantics SHALL fail explicitly.

#### Scenario: Alternative removal triggers and independent obstructions

- **WHEN** a passage has alternative positive removal triggers and another independent obstruction
- **THEN** removal triggers form OR alternatives and the independent obstruction remains required
- **AND** unsupported inverse or item-state semantics fail explicitly

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

Inactive placements SHALL retain exact per-copy activation provenance from supported exported rules. Verified positive paths with unobservable transient state SHALL remain potentially available with advice and actual live-entity withholding, not fabricated persistent predicates. Deduplication SHALL NOT transfer one copy's activation or disabled state to unrelated copies.

#### Scenario: An unused copy

- **WHEN** a placed character is inactive at scene start and nothing activates it
- **THEN** its placement is never available

### Requirement: Inactive placement audits cover serialized references

A never-condition cutover SHALL require the full inactive audit and hierarchy/private-field reference coverage. Unexplained placements SHALL fail the audit rather than silently become never. Serialized references, including denied SetActive fields, SHALL remain classified.

#### Scenario: A new activator script

- **WHEN** a new build adds a script field that activates a character
- **THEN** the export fails and names the unclassified script and field

### Requirement: Zone line usability is recorded and respected

The export SHALL record component enabled state, trigger-collider capability and enabled trigger callback. Missing physical input SHALL fail. The clean database SHALL publish nonnull `is_usable` and nullable `unusable_reason` with precedence: reviewed exclusion, component_disabled, no_trigger_collider, trigger_collider_disabled, otherwise usable.

#### Scenario: A disabled trigger collider

- **WHEN** a zone line has no reviewed exclusion and an enabled component but a disabled trigger collider
- **THEN** its published usability is false with reason `trigger_collider_disabled`

### Requirement: Zone-line exclusions are reviewed and exact

Mapping SHALL accept only reviewed `zoneline:` exclusions with a nonempty reason and SHALL reject stale identities, unknown keys and forced usability.

#### Scenario: A forced usability mapping

- **WHEN** a zone-line mapping attempts to force usability or names a stale identity or unknown key
- **THEN** mapping fails instead of overriding capability

### Requirement: Activation does not invent zone-line capability

Initial inactivity SHALL NOT itself establish incapability. SetActive SHALL NOT repair disabled capability unless an exported pinned effect explicitly restores it. The raw capability view SHALL remain raw.

#### Scenario: A quest activates a disabled component

- **WHEN** the clean build runs on the current main build
- **THEN** the Shivering Step zone line to Hidden Hills is unusable even after A Way To Erenshor

### Requirement: Zone consumers preserve common usability and destinations

Guide, map, legacy wiki and shared zone providers SHALL require common usability and preserve destination contexts.

#### Scenario: Issue 298

- **WHEN** the clean build runs on the current main build
- **THEN** every Shivering Step and Shivering Tomb zone line that players cannot reach is unusable with its reason
- **AND** neither the map nor the generated wiki zone connections list it

### Requirement: Scripted activators follow pinned rules

For each game script whose activation logic the pipeline encodes, the export SHALL record the scene objects its serialized fields reference, and code facts SHALL pin the logic the pipeline encodes. The scripts SHALL include `ShiverEvent`, `ShiveringAngel`, `ShiveringPhantomWardListener`, the planar fight scripts that reveal restored gods, `MemorySphere`, `SivTorchLight`, `PlanningTable`, `ReliqPortalListener` and the key rule of `Door`.

#### Scenario: A game update changes the Shivering Step event

- **WHEN** a new build changes a quest that `ShiverEvent` checks, assigns, or finishes
- **THEN** `extract code-facts` fails and names the fact

#### Scenario: The event references a new object

- **WHEN** a new build adds a character to a `ShiverEvent` field
- **THEN** the clean build gives that character the condition of its field without a code change

### Requirement: The Shivering Step event is modeled from its rules

The guide SHALL model Meet Shivering Step as acquired on entering Shivering Step and completed by The Curator, The Gatekeeper, The Harbinger, and The Bridgekeeper.

#### Scenario: Before the keepers

- **WHEN** a player enters Shivering Step for the first time
- **THEN** Meet Shivering Step lists the four keeper conversations as its steps
- **AND** Find The Hider is not actionable

### Requirement: Shivering Step keepers and Kio follow quest progression

The first Kio SHALL be available until all four keeper quests are complete. The second Kio SHALL be available once all four are complete and until Changing the Lighthouse is complete. The four keepers SHALL be unavailable once all four are complete.

#### Scenario: Completing all keeper quests

- **WHEN** all four keeper quests are complete and Changing the Lighthouse is incomplete
- **THEN** the first Kio and the keepers are unavailable and the second Kio is available

### Requirement: Shivering Step torch unlocks event placements

The Hider SHALL be available once The Shivering Torch is complete and until Warming the Isle is complete. The characters of the ten event spawn triggers SHALL be available once The Shivering Torch is complete, at their trigger sites.

#### Scenario: After the torch

- **WHEN** The Shivering Torch is complete and Warming the Isle is not
- **THEN** The Hider is available and the four keepers are not

### Requirement: Shivering Step delays remain visible

A delay that the Shivering Step event imposes SHALL appear as a note on the affected step.

#### Scenario: A delayed event step

- **WHEN** the event imposes a delay on a step
- **THEN** the affected step displays a note about the delay

### Requirement: Encounter prerequisites are recorded as advisory atoms

The pipeline SHALL record, as encounter atoms, the deaths that reveal a character, remove an invulnerability, or open a barrier: the planar bosses before their restored gods, both Phantom's Wards before Warded Shadow is vulnerable, the four Reliquary Wards before the Reliquary Fiend, Eldoth Molorai before A Strange Hermit answers, and the bosses before their plane barriers.

#### Scenario: Recording encounter deaths

- **WHEN** a death reveals a character, removes invulnerability or opens a barrier
- **THEN** the pipeline records the corresponding advisory encounter atom

### Requirement: Common encounter rows preserve exact identities

The guide SHALL preserve common `encounter_placements`, `encounter_conditions`, `encounter_completions` and `encounter_event_conditions`, including exact root/member keys, roles, `context_kind`, `post_completion_role` and every guard/effect field. The Reliquary root and four supports SHALL remain distinct placements even when character templates deduplicate. Persistent account claims SHALL remain distinct from transient encounter advice and character completion.

#### Scenario: Deduplicated Reliquary templates

- **WHEN** character templates deduplicate across the Reliquary root and supports
- **THEN** common encounter rows retain the exact root and four support placement identities, roles, context and guard/effect fields
- **AND** persistent claims remain distinct from advice and character completion

#### Scenario: A restored god

- **WHEN** the clean build runs on the current main build
- **THEN** restored Fernalla's placement has a condition with an encounter atom for Fernalla

### Requirement: Quest guide data carries the conditions

`quest-guide.json` SHALL carry the schema version that the mod reads, and conditions and subject references, gate-item metadata, common encounter rows, canonical source facts, the way rank of each acquisition, and destination contexts. The compiler SHALL combine gates once and omit none.

#### Scenario: A door gate reaches the mod

- **WHEN** `erenshor guide export-mod` runs on the current main build
- **THEN** Founder's placement references a condition with the Dockhouse Key atom
- **AND** the data lists the Dockhouse Key's game item ID and sources

#### Scenario: No gate is lost

- **WHEN** the contract test compares the clean database's conditions with `quest-guide.json`
- **THEN** every gated subject in the database has the same condition in `quest-guide.json`

### Requirement: Guide schema changes cut over atomically

The mod SHALL reject any other schema version. A schema change SHALL migrate Python emission, C# validation/DTOs, real fixtures and generated data atomically, without a shim for the previous version. Missing common tables or invalid references SHALL fail rather than become empty defaults.

#### Scenario: An incompatible guide contract

- **WHEN** a guide contract has another schema version, missing common tables or invalid references
- **THEN** loading or generation fails without a compatibility shim or empty defaults

### Requirement: Guide generation writes only coherent output

Guide commands SHALL write no output besides `quest-guide.json`. Production regeneration SHALL wait for coherent refreshed common data.

#### Scenario: Common refresh is incomplete

- **WHEN** refreshed common data is not coherent
- **THEN** production regeneration waits rather than replacing guide output
- **AND** guide commands produce no auxiliary output files

### Requirement: Requirement chains are acyclic

The compiler SHALL check that following unmet observable atoms from any gated subject to the subjects that satisfy them never returns to the starting subject through required atoms alone. It SHALL fail and name the cycle otherwise. An alternative group that leads back SHALL NOT count as a cycle when another group of the same condition does not.

#### Scenario: A key behind its own door

- **WHEN** the only source of a key is behind the door that the key opens
- **THEN** the compile fails and names the door, the key, and the source

### Requirement: Workflow traversal preserves intentional cycles and repeats

The requirement-chain cycle check SHALL apply to mandatory availability dependencies, not reject intentional canonical acquisition workflows or the explicit positive account/character implication cycle. Workflow traversal SHALL protect the current visited path without globally suppressing valid repeated sources.

#### Scenario: An intentional workflow revisits a source

- **WHEN** canonical acquisition traversal has an intentional workflow cycle or a valid repeated source
- **THEN** traversal protects the current visited path without globally suppressing the source
- **AND** the mandatory availability cycle check does not reject intentional workflows or the explicit positive account/character implication cycle

### Requirement: Resource probabilities retain their local conditions

Fishing sources SHALL retain distinct day and night probabilities through graph construction, compilation and serialization. An absent phase SHALL have zero probability. A source with different phase probabilities SHALL NOT expose their maximum as an unconditional chance. Fishing probabilities SHALL identify their denominator as a successful catch.

#### Scenario: A fish has different day and night odds

- **WHEN** one water has a 5.9375 percent daytime chance and a 19 percent nighttime chance for a fish
- **THEN** the serialized source retains both values and has no unconditional 19 percent chance

### Requirement: Local probabilities preserve precision

Local mining and drop probabilities SHALL survive serialization without integer quantization. Unknown probabilities SHALL remain distinct from zero.

#### Scenario: A source has tiny positive odds

- **WHEN** a local source has a positive probability below the display precision
- **THEN** the serialized probability remains positive and the UI does not round it to zero

### Requirement: Zero-probability paths are not obtainable sources

Known zero-probability acquisition paths SHALL NOT be presented as obtainable sources.

#### Scenario: A known impossible acquisition

- **WHEN** an acquisition path has known zero probability
- **THEN** it is not presented as an obtainable source

### Requirement: Potential damageability is derived per actual copy

The clean database SHALL distinguish characters that can eventually become vulnerable from permanently invulnerable characters. Initial vulnerability or an enabled, feasible release branch SHALL establish potential damageability. Release provenance SHALL retain the actual controller, holder, quest variant, protector or ward dependencies. A release on one copy SHALL NOT establish eligibility for another deduplicated copy.

#### Scenario: Initial immunity has a proven release

- **WHEN** an initially invulnerable character has an actual enabled trade, protector or ward release
- **THEN** it remains eligible for combat-level aggregation and retains the release conditions as provenance

#### Scenario: A permanently invulnerable character

- **WHEN** an initially invulnerable copy has no feasible release
- **THEN** it does not contribute to combat-level ranges


### Requirement: Potential damageability does not prove current vulnerability

Potential damageability SHALL NOT be used as proof that a character is presently vulnerable or that its loot has no preparation requirement.

#### Scenario: A release has not happened yet

- **WHEN** a potentially damageable character still requires a release action
- **THEN** potential damageability does not establish current vulnerability or remove loot preparation

### Requirement: Ten portal gates read typed stored planning slots

Roles SHALL be exactly `dedicated` or `rune`. Four dedicated portals SHALL each require their exact Planar slot. Six ordinary portals SHALL each accept their correct item in any of Rune1 through Rune6, yielding four dedicated and 36 rune metadata rows.

#### Scenario: Stored portal state changes

- **WHEN** the correct item enters its exact planar slot
- **THEN** the condition holds

#### Scenario: Six interchangeable rune slots

- **WHEN** an ordinary portal's correct rune occupies any one of the six rune slots
- **THEN** its exact referenced line satisfies one of six OR alternatives
- **AND** wrong runes, empty slots, inventory-only possession and completed rune quests do not satisfy it
- **AND** presentation deduplicates the six identical actions without merging gate identities

### Requirement: Portal metadata projects one immutable selection

One immutable `PlanningPortalSelection` SHALL carry `line`, `slot`, `slot_kind`, `item_stable_key` and `destination_zone_stable_key`. Gate rows and common `planning_portal_slots(zone_line_stable_key,slot,slot_kind)` metadata SHALL project from that single selection.

#### Scenario: Projecting selected portal metadata

- **WHEN** a planning portal selection is emitted
- **THEN** gate rows and common slot metadata project from the same immutable selection

### Requirement: Portal line serialization uses the existing database column

The helper's line SHALL map to the database's existing zone_line_stable_key column, while a wire field named line SHALL be normal serialization, not a second database column or compatibility alias.

#### Scenario: Serializing a portal line

- **WHEN** the selection's line is serialized as a wire field
- **THEN** it maps to the existing zone_line_stable_key database column without another column or compatibility alias

### Requirement: Portal selections resolve exact referenced identities

Items, actual child-line references and actual destination-zone keys SHALL resolve uniquely or fail. Unrelated same-destination copies SHALL remain unchanged.

#### Scenario: Ambiguous child-line references

- **WHEN** a selected portal's child line cannot resolve uniquely
- **THEN** generation fails rather than selecting another same-destination copy

### Requirement: Stored portal checks replace quest bypasses

Stored-slot checks SHALL supersede quest-enable bypasses, retaining initialization provenance. Inventory or completed quests SHALL NOT satisfy stored state.

#### Scenario: The stone is carried but not installed

- **WHEN** the player holds the correct portal stone but its stored planar slot is empty
- **THEN** the raid portal condition does not hold
- **AND** the guide leads to the planning table rather than pretending the portal is open

### Requirement: Stored portal changes invalidate availability

Removal/replacement SHALL invalidate availability through the shared slot observation path.

#### Scenario: The stored item is removed or replaced

- **WHEN** a dedicated item is removed, replaced or stored in a different slot
- **THEN** its condition does not hold

### Requirement: Planning instructions use common typed destination metadata

Planning atoms SHALL carry required instruction text derived from common role rows and actual destination metadata. Dedicated text SHALL be `Place <item> in the planning-table slot for <destination>.` Rune text SHALL be `Place <item> in a rune slot on your planning table.` Missing text or unknown roles SHALL fail. Native consumers SHALL NOT maintain slot-name destination maps.

#### Scenario: Generating a dedicated portal instruction

- **WHEN** a dedicated planning atom is generated
- **THEN** its instruction names the item and actual destination using common role metadata
- **AND** missing text or an unknown role fails without a native slot-name destination map

### Requirement: Physical routes come from actual zone-line behavior

Physical connections SHALL retain stable actual line identities and proven initialization. Spells, dead-player warps and prose SHALL NOT establish physical exits.

#### Scenario: Copied prose claims a return route

- **WHEN** prose names a plane return but the actual physical zone line does not lead there
- **THEN** shared route data does not invent that physical exit
- **AND** spells and dead-player warps remain separate mechanisms

### Requirement: Stored-return contexts retain physical bindings

Common `zone_line_destination_contexts` SHALL bind a stored return to `character_state:reliquary_return_zone` and `character_state:reliquary_return_landing`, retaining source key and fixed physical position.

#### Scenario: Emitting a stored return context

- **WHEN** common data emits a stored-return destination context
- **THEN** it retains the typed zone and landing bindings, source key and fixed physical position

### Requirement: Portal startup guards require actual exported self state

The producer SHALL require the actual portal-to-line binding and exported `$portal_active_self=false` from configured ReliqPort.activeSelf, not activeInHierarchy or component state. Missing scalar/binding SHALL fail.

#### Scenario: A missing startup scalar

- **WHEN** the actual portal-to-line binding or configured activeSelf scalar is missing
- **THEN** production fails instead of substituting hierarchy or component state

### Requirement: Offline consumers describe stored returns generically

Offline map/wiki consumers SHALL describe stored return generically, never emit Hidden as a fixed connection.

#### Scenario: An offline stored-return connection

- **WHEN** map or wiki output describes a stored-return line
- **THEN** it describes a generic stored return rather than a fixed Hidden connection


### Requirement: Account initialization and outcomes remain phaseful

Account claims SHALL use `account_state:reliquary_claimed`, actor `account` and actual location scope. False `availability` and true host-death `operation_outcome` SHALL coexist. Character CLAIMRELIQUARY completion SHALL remain separate. Account and item outcomes SHALL retain the existing `operation_outcome` vocabulary without a new phase spelling or alias. Initialization and outcome annotations SHALL survive coverage and serialization outside current-state `_conditions`.

#### Scenario: False account serialization

- **WHEN** common data contains false account availability and true host-death outcome
- **THEN** actual Python serialization and C# loading preserve both boolean values, phases, scopes and four support identities
- **AND** the outcome does not become a current requirement

#### Scenario: Loaded account entry contract

- **WHEN** the supported account live binding is emitted
- **THEN** successful code-fact assertions prove exactly one direct LoadReliquary statement precedes exactly one direct world-entry statement in both Play and PlayAlternate
- **AND** missing, duplicate, conditional-only or reversed statements fail

#### Scenario: Active child under inactive parent

- **WHEN** the configured portal has activeSelf true under an inactive parent
- **THEN** its exported scalar is true and does not satisfy the false-self startup guard

### Requirement: Canonical acquisitions and uses own source selection

The guide SHALL use the shared provenance repository, typed records and actionable/player-access semantics without legacy source-selection SQL fallback. Trees SHALL reference acquisition and actual location keys. Full evidence and coverage SHALL remain offline.

#### Scenario: Canonical coverage and identity

- **WHEN** the adapter consumes acquisitions and uses
- **THEN** an offline receipt accounts for every input as represented or explicitly excluded by shared policy
- **AND** source choice and prerequisite traversal retain acquisition and actual placement identity

### Requirement: Canonical source facts use public typed fields

`_source_facts` SHALL use canonical dataclass field names/types, omitting evidence and internal build metadata.

#### Scenario: Serializing source facts

- **WHEN** canonical source facts are serialized
- **THEN** their fields use canonical dataclass names and types without evidence or internal build metadata

### Requirement: Canonical source contracts reject unsupported references

Missing references and unknown actionable kinds SHALL fail, using `unsupported canonical acquisition kind: <kind>` for unsupported verified-player kinds.

#### Scenario: An unsupported verified-player kind

- **WHEN** a verified-player acquisition has an unsupported kind
- **THEN** generation fails with `unsupported canonical acquisition kind: <kind>`

### Requirement: Canonical access semantics do not invent player routes

No-location facts SHALL NOT gain fabricated characters or positions. Internal/non-acquirable facts SHALL NOT become player routes.

#### Scenario: A non-acquirable or unlocated fact

- **WHEN** canonical data contains an internal, non-acquirable or unlocated fact
- **THEN** it does not acquire a fabricated location or an unsupported player route

### Requirement: Canonical mapping retains source locality

Canonical mapping SHALL retain drops, vendors, dialog, crafting, rewards, gathering, pickups and item-use input children. Common-world, special-world and fishing-bonus facts SHALL remain nonlocal. Starting-class and unlocated UI actions SHALL remain explanatory. Located UI grants SHALL use actual locations.

#### Scenario: Located and unlocated UI grants

- **WHEN** canonical mapping consumes located and unlocated UI grants
- **THEN** located grants use actual locations and unlocated grants remain explanatory
- **AND** common-world, special-world and fishing-bonus facts remain nonlocal

### Requirement: Auction House stock is excluded from sources

Auction House listings SHALL be excluded with a recorded reason and never become a source, because simulated players list random stock.

#### Scenario: A simulated player lists an item

- **WHEN** Auction House stock contains an item
- **THEN** the listing is excluded from sources with its reason recorded

### Requirement: Dialog enrichment retains exact source variants

Dialog enrichment SHALL use exact source copy and numeric variant/dialog index while preserving keywords, not select another giver by name.

#### Scenario: Two dialog givers share a name

- **WHEN** dialog enrichment encounters different giver copies sharing a name
- **THEN** it uses the exact source copy and numeric variant/dialog index and preserves keywords

### Requirement: Canonical operations preserve input and phase meaning

Operation inputs SHALL become timing, preparation or child requirements rather than unconditional inventory blocks. Initialization and outcomes SHALL NOT become current availability.

#### Scenario: An operation has inputs and outcomes

- **WHEN** an operation is mapped into guidance
- **THEN** inputs become timing, preparation or children and initialization and outcomes do not become current availability

### Requirement: Canonical workflow traversal retains slots and variants

Requested output quality SHALL match produced quality. Repeated material/reward slots, operation IDs, variants and intentional workflow cycles SHALL survive visited-path traversal.

#### Scenario: Repeated materials and variant rewards

- **WHEN** an operation repeats a material in distinct slots and offers distinct quest variants
- **THEN** each slot, quantity and variant retains its exact identity
- **AND** output quality does not become an input-quality requirement

### Requirement: Canonical fishing replacement math runs once

Canonical final fishing replacement math SHALL be applied once.

#### Scenario: Adapting final fishing probabilities

- **WHEN** canonical final fishing probabilities are adapted
- **THEN** replacement math is applied once rather than repeated during traversal or serialization

### Requirement: Canonical source merging preserves semantic distinctions

Different phase, actor, location, initialization and quality semantics SHALL NOT be unconditionally merged.

#### Scenario: Sources differ in phase or quality

- **WHEN** canonical sources differ in phase, actor, location, initialization or quality semantics
- **THEN** mapping does not unconditionally merge those distinctions

### Requirement: Native turn-in variants remain complete alternatives

Each native variant SHALL be an AND bundle of its required items. Different variants SHALL be OR alternatives between complete bundles, never between individual slots of mixed bundles. Repeated quantities of one item SHALL sum within its variant only. Canonical slot-level use IDs SHALL remain separate evidence even when the objective presents one combined quantity. Progress, turn-in readiness, needed-item tracking, markers and navigation SHALL consume the same bundle semantics.

#### Scenario: Four repeated Octorunner slots

- **WHEN** one variant requires four copies of the same item
- **THEN** the objective presents one quantity-four collection requirement with all four use IDs
- **AND** inventory counts zero, one and three remain incomplete while four satisfies that bundle

#### Scenario: Impossible mixed partial variants

- **WHEN** one variant requires items A and B and another requires C and D
- **THEN** holding only A and D does not satisfy either variant
- **AND** a completed whole variant suppresses the other alternatives without summing their quantities

#### Scenario: Single-slot alternatives

- **WHEN** each native variant has one required slot
- **THEN** either complete variant satisfies the alternatives
- **AND** unrelated independent requirements remain required

### Requirement: Transient activation stays advice

MorphTrigger entry activation, PietyTrigger activation-time quest guards and FernallaPortalBoss HP phases SHALL retain actual controller/target provenance and preparation advice. PietyTrigger SHALL NOT create a current quest-not-done despawn predicate.

#### Scenario: Guardians already activated

- **WHEN** Guardians are enabled and the PietyTrigger RequiredQuest subsequently completes
- **THEN** the guide does not infer despawn from that completion
- **AND** transient instructions remain distinct from live-entity withholding

### Requirement: AngelScript advice uses exported targets

AngelScript SHALL use its exported Bellwain target group without claiming puzzle workflow implementation.

#### Scenario: Bellwain target advice

- **WHEN** AngelScript advice is generated
- **THEN** it uses the exported Bellwain target group without claiming a puzzle workflow implementation

### Requirement: Activation notes validate actual script provenance

Optional source-note `activation_script` SHALL be mutually exclusive with `mechanism` and validate against actual placement source_script. Multiple unrepresentable controller types SHALL block the affected annotation rather than invent names or eligibility overrides.

#### Scenario: An unrepresentable controller annotation

- **WHEN** multiple controller types cannot be represented by the annotation
- **THEN** the annotation is blocked without invented names or eligibility overrides
- **AND** any activation_script note is checked against actual placement source_script and cannot coexist with mechanism

### Requirement: Native offering controllers are placement activations

The guide SHALL represent each native carried-item offering controller as one activation with its exact identity, scene, exported site, display name, offerings, spawned characters with counts, reward containers and random-outcome flag. Every placement that a controller spawns SHALL reference its offerings and role.

#### Scenario: Arena reward chest

- **WHEN** the clean build has eight arena rounds
- **THEN** each round's chest placement references that round's offering as its reward, with the round's fee and enemies
- **AND** no arena entry appears among the quests

#### Scenario: One feeding site with two offerings

- **WHEN** Odd Malaroth Feed and Malaroth Feed spawn different characters at the Malaroth feeding site
- **THEN** both offerings belong to one activation with one site

#### Scenario: A random chessboard outcome

- **WHEN** The Faceless figurine spawns one of six characters
- **THEN** each of those placements references the same random-outcome offering

### Requirement: Offering controller bindings are unambiguous

Unbound or ambiguous controller placements and controllers without an exported site or display name SHALL fail generation.

#### Scenario: A controller lacks an exported site

- **WHEN** an offering controller has no exported site or display name, or its placements are unbound or ambiguous
- **THEN** generation fails

### Requirement: Offerings do not become quest or gate state

Offerings SHALL NOT become synthetic quests, gate atoms or persisted workflow state. `quest-guide.json` SHALL contain native quests only.

#### Scenario: An arena activation is serialized

- **WHEN** an arena offering activation is serialized
- **THEN** it does not create a synthetic quest, gate atom or persisted workflow state
- **AND** the quest list contains native quests only

### Requirement: Common output gates production integration

Production cutover SHALL require refreshed activator/suppressor records, startup bool, resolved audited loot bindings and coherent common schema. Source packets or acknowledgements SHALL NOT substitute for exported records.

#### Scenario: Missing refreshed binding

- **WHEN** the startup scalar, actual binding or required common relation is absent
- **THEN** production generation fails before replacing the embedded artifact
- **AND** no fake character, fabricated binding, legacy fallback or silently omitted source repairs the gap

#### Scenario: Cross-language common fixture

- **WHEN** a complete isolated fixture is built with common producer APIs
- **THEN** the actual guide writer output loads through the C# parser/evaluator with false availability, true outcome and exact support identities intact
- **AND** handwritten JSON alone does not establish the integration proof

### Requirement: Common integration preserves producer ownership

CanonicalSources SHALL own common DDL and source hooks. ExportBundleIntegrator SHALL own additive native refresh and its frozen receipt. WikiOverviews/DataZones SHALL own generic encounter/navigation projections and the guide SHALL own its consumer.

#### Scenario: Integrating refreshed common output

- **WHEN** refreshed common output is integrated
- **THEN** DDL, source hooks, additive native refresh, generic projections and guide consumption retain their specified owners

### Requirement: Announced rebuilds isolate writable data

Worktree-owned databases and writable inputs SHALL isolate announced rebuilds from shared main data.

#### Scenario: An isolated rebuild

- **WHEN** an announced rebuild runs
- **THEN** its worktree-owned database and writable inputs remain isolated from shared main data

### Requirement: Quest level estimates preserve complete alternatives

The recommended quest level SHALL use the minimum known level within each explicit alternative step group and the maximum across independently required steps and requirements. Native item variants SHALL remain OR alternatives of complete AND bundles. Unknown levels SHALL NOT count as zero. Each alternative SHALL retain its own step estimate and route.

#### Scenario: Alternative destinations have different levels

- **WHEN** The Island Tomb completes by entering either level-4 Island Tomb or level-24 Shivering Tomb (2), with no higher shared requirement
- **THEN** its recommended quest level is 4
- **AND** both destinations retain their own estimates and navigation identities

#### Scenario: A shared requirement is harder than the easier alternative

- **WHEN** either completion alternative is valid but an independent required step has level 12
- **THEN** the quest estimate includes that shared requirement rather than reporting only the easier alternative
