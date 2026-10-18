# Spec Delta

## Purpose

Defines how the pipeline records when zone lines, placed characters, spawn points, and item sources are available to the player, from the shipped game data through the clean database to the quest guide data that AdventureGuide embeds.

## ADDED Requirements

### Requirement: Gates are conditions over a closed set of atoms

The pipeline SHALL express gates as OR groups of AND-ed typed atoms. A subject without a condition SHALL always be available, and a condition without groups SHALL never hold. Observable atoms SHALL cover quests, inventory, keys, furnished rooms, exact stored planning-slot items and supported account state. Advisory encounter atoms SHALL retain actual member identities and counts. Account atoms SHALL carry actor, reference, boolean value, phase and actual location scope. Boolean strings SHALL be exactly `true` or `false`. Missing or unknown references, actors, phases, states or slots SHALL fail generation and contract loading. Only observable availability-phase predicates SHALL enter current-state conjunctions.

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

Entries SHALL use either `doors` or `objects`, never both, with mandatory guards and reason. Positive removal triggers SHALL gate passage, not inverse object-presence conditions. Alternative removal triggers SHALL be OR alternatives, while independent obstructions SHALL remain AND requirements. Unsupported inverse/item-state semantics SHALL fail explicitly. Supported scripted obstructions SHALL also require exact reviewed guards or none.

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

Inactive placements SHALL retain exact per-copy activation provenance from supported exported rules. Verified positive paths with unobservable transient state SHALL remain potentially available with advice and actual live-entity withholding, not fabricated persistent predicates. A never-condition cutover SHALL require the full inactive audit and hierarchy/private-field reference coverage. Unexplained placements SHALL fail the audit rather than silently become never. Serialized references, including denied SetActive fields, SHALL remain classified. Deduplication SHALL NOT transfer one copy's activation or disabled state to unrelated copies.

#### Scenario: An unused copy

- **WHEN** a placed character is inactive at scene start and nothing activates it
- **THEN** its placement is never available

#### Scenario: A new activator script

- **WHEN** a new build adds a script field that activates a character
- **THEN** the export fails and names the unclassified script and field

### Requirement: Zone line usability is recorded and respected

The export SHALL record component enabled state, trigger-collider capability and enabled trigger callback. Missing physical input SHALL fail. The clean database SHALL publish nonnull `is_usable` and nullable `unusable_reason` with precedence: reviewed exclusion, component_disabled, no_trigger_collider, trigger_collider_disabled, otherwise usable. Mapping SHALL accept only reviewed `zoneline:` exclusions with a nonempty reason and SHALL reject stale identities, unknown keys and forced usability. Initial inactivity SHALL NOT itself establish incapability. SetActive SHALL NOT repair disabled capability unless an exported pinned effect explicitly restores it. The raw capability view SHALL remain raw. Guide, map, legacy wiki and shared zone providers SHALL require common usability and preserve destination contexts.

#### Scenario: A quest activates a disabled component

- **WHEN** the clean build runs on the current main build
- **THEN** the Shivering Step zone line to Hidden Hills is unusable even after A Way To Erenshor

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

The guide SHALL preserve common `encounter_placements`, `encounter_conditions`, `encounter_completions` and `encounter_event_conditions`, including exact root/member keys, roles, `context_kind`, `post_completion_role` and every guard/effect field. The Reliquary root and four supports SHALL remain distinct placements even when character templates deduplicate. Persistent account claims SHALL remain distinct from transient encounter advice and character completion.

#### Scenario: A restored god

- **WHEN** the clean build runs on the current main build
- **THEN** restored Fernalla's placement has a condition with an encounter atom for Fernalla

### Requirement: Quest guide data carries the conditions

`quest-guide.json` SHALL use schema 8 and carry conditions and subject references, gate-item metadata, common encounter rows, canonical source facts and destination contexts. Python emission, C# validation/DTOs, real fixtures and generated data SHALL migrate atomically without a schema-7 shim. Missing common tables or invalid references SHALL fail rather than become empty defaults. The compiler SHALL combine gates once and omit none. Guide commands SHALL write no output besides `quest-guide.json`. Production regeneration SHALL wait for coherent refreshed common data.

#### Scenario: A door gate reaches the mod

- **WHEN** `erenshor guide export-mod` runs on the current main build
- **THEN** Founder's placement references a condition with the Dockhouse Key atom
- **AND** the data lists the Dockhouse Key's game item ID and sources

#### Scenario: No gate is lost

- **WHEN** the contract test compares the clean database's conditions with `quest-guide.json`
- **THEN** every gated subject in the database has the same condition in `quest-guide.json`

### Requirement: Requirement chains are acyclic

The compiler SHALL check that following unmet observable atoms from any gated subject to the subjects that satisfy them never returns to the starting subject through required atoms alone. It SHALL fail and name the cycle otherwise. An alternative group that leads back SHALL NOT count as a cycle when another group of the same condition does not.

This check SHALL apply to mandatory availability dependencies, not reject intentional canonical acquisition workflows or the explicit positive account/character implication cycle. Workflow traversal SHALL protect the current visited path without globally suppressing valid repeated sources.

#### Scenario: A key behind its own door

- **WHEN** the only source of a key is behind the door that the key opens
- **THEN** the compile fails and names the door, the key, and the source

### Requirement: Resource probabilities retain their local conditions

Fishing sources SHALL retain distinct day and night probabilities through graph construction, compilation and serialization. An absent phase SHALL have zero probability. A source with different phase probabilities SHALL NOT expose their maximum as an unconditional chance. Fishing probabilities SHALL identify their denominator as a successful catch. Local mining and drop probabilities SHALL survive serialization without integer quantization. Unknown probabilities SHALL remain distinct from zero. Known zero-probability acquisition paths SHALL NOT be presented as obtainable sources.

#### Scenario: A fish has different day and night odds

- **WHEN** one water has a 5.9375 percent daytime chance and a 19 percent nighttime chance for a fish
- **THEN** the serialized source retains both values and has no unconditional 19 percent chance

#### Scenario: A source has tiny positive odds

- **WHEN** a local source has a positive probability below the display precision
- **THEN** the serialized probability remains positive and the UI does not round it to zero

### Requirement: Potential damageability is derived per actual copy

The clean database SHALL distinguish characters that can eventually become vulnerable from permanently invulnerable characters. Initial vulnerability or an enabled, feasible release branch SHALL establish potential damageability. Release provenance SHALL retain the actual controller, holder, quest variant, protector or ward dependencies. A release on one copy SHALL NOT establish eligibility for another deduplicated copy. This property SHALL NOT be used as proof that a character is presently vulnerable or that its loot has no preparation requirement.

#### Scenario: Initial immunity has a proven release

- **WHEN** an initially invulnerable character has an actual enabled trade, protector or ward release
- **THEN** it remains eligible for combat-level aggregation and retains the release conditions as provenance

#### Scenario: A permanently invulnerable character

- **WHEN** an initially invulnerable copy has no feasible release
- **THEN** it does not contribute to combat-level ranges


### Requirement: Ten portal gates read typed stored planning slots

One immutable `PlanningPortalSelection` SHALL carry `line`, `slot`, `slot_kind`, `item_stable_key` and `destination_zone_stable_key`. Gate rows and common `planning_portal_slots(zone_line_stable_key,slot,slot_kind)` metadata SHALL project from that single selection. The helper's line SHALL map to the database's existing zone_line_stable_key column, while a wire field named line SHALL be normal serialization, not a second database column or compatibility alias. Roles SHALL be exactly `dedicated` or `rune`. Four dedicated portals SHALL each require their exact Planar slot. Six ordinary portals SHALL each accept their correct item in any of Rune1 through Rune6, yielding four dedicated and 36 rune metadata rows. Items, actual child-line references and actual destination-zone keys SHALL resolve uniquely or fail. Unrelated same-destination copies SHALL remain unchanged. Stored-slot checks SHALL supersede quest-enable bypasses, retaining initialization provenance. Inventory or completed quests SHALL NOT satisfy stored state. Removal/replacement SHALL invalidate availability through the shared slot observation path.

Planning atoms SHALL carry required instruction text derived from common role rows and actual destination metadata. Dedicated text SHALL be `Place <item> in the planning-table slot for <destination>.` Rune text SHALL be `Place <item> in a rune slot on your planning table.` Missing text or unknown roles SHALL fail. Native consumers SHALL NOT maintain slot-name destination maps.

#### Scenario: The stone is carried but not installed

- **WHEN** the player holds the correct portal stone but its stored planar slot is empty
- **THEN** the raid portal condition does not hold
- **AND** the guide leads to the planning table rather than pretending the portal is open

#### Scenario: Stored portal state changes

- **WHEN** the correct item enters its exact planar slot
- **THEN** the condition holds

#### Scenario: The stored item is removed or replaced

- **WHEN** a dedicated item is removed, replaced or stored in a different slot
- **THEN** its condition does not hold

#### Scenario: Six interchangeable rune slots

- **WHEN** an ordinary portal's correct rune occupies any one of the six rune slots
- **THEN** its exact referenced line satisfies one of six OR alternatives
- **AND** wrong runes, empty slots, inventory-only possession and completed rune quests do not satisfy it
- **AND** presentation deduplicates the six identical actions without merging gate identities

### Requirement: Physical routes come from actual zone-line behavior

Physical connections SHALL retain stable actual line identities and proven initialization. Common `zone_line_destination_contexts` SHALL bind a stored return to `character_state:reliquary_return_zone` and `character_state:reliquary_return_landing`, retaining source key and fixed physical position. The producer SHALL require the actual portal-to-line binding and exported `$portal_active_self=false` from configured ReliqPort.activeSelf, not activeInHierarchy or component state. Missing scalar/binding SHALL fail. Spells, dead-player warps and prose SHALL NOT establish physical exits. Offline map/wiki consumers SHALL describe stored return generically, never emit Hidden as a fixed connection.

#### Scenario: Copied prose claims a return route

- **WHEN** prose names a plane return but the actual physical zone line does not lead there
- **THEN** shared route data does not invent that physical exit
- **AND** spells and dead-player warps remain separate mechanisms


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

The guide SHALL use the shared provenance repository, typed records and actionable/player-access semantics without legacy source-selection SQL fallback. `_source_facts` SHALL use canonical dataclass field names/types, omitting evidence and internal build metadata. Trees SHALL reference acquisition and actual location keys. Missing references and unknown actionable kinds SHALL fail, using `unsupported canonical acquisition kind: <kind>` for unsupported verified-player kinds. No-location facts SHALL NOT gain fabricated characters or positions. Internal/non-acquirable facts SHALL NOT become player routes. Full evidence and coverage SHALL remain offline.

Canonical mapping SHALL retain drops, vendors, dialog, crafting, rewards, gathering, pickups and item-use input children. Common-world, special-world and fishing-bonus facts SHALL remain nonlocal. Starting-class and unlocated UI actions SHALL remain explanatory. Located UI grants and auction brokers SHALL use actual locations. Dialog enrichment SHALL use exact source copy and numeric variant/dialog index while preserving keywords, not select another giver by name.

Operation inputs SHALL become timing, preparation or child requirements rather than unconditional inventory blocks. Initialization and outcomes SHALL NOT become current availability. Requested output quality SHALL match produced quality. Repeated material/reward slots, operation IDs, variants and intentional workflow cycles SHALL survive visited-path traversal. Canonical final fishing replacement math SHALL be applied once. Different phase, actor, location, initialization and quality semantics SHALL NOT be unconditionally merged.

#### Scenario: Canonical coverage and identity

- **WHEN** the adapter consumes acquisitions and uses
- **THEN** an offline receipt accounts for every input as represented or explicitly excluded by shared policy
- **AND** source choice and prerequisite traversal retain acquisition and actual placement identity

#### Scenario: Repeated materials and variant rewards

- **WHEN** an operation repeats a material in distinct slots and offers distinct quest variants
- **THEN** each slot, quantity and variant retains its exact identity
- **AND** output quality does not become an input-quality requirement

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

MorphTrigger entry activation, PietyTrigger activation-time quest guards and FernallaPortalBoss HP phases SHALL retain actual controller/target provenance and preparation advice. PietyTrigger SHALL NOT create a current quest-not-done despawn predicate. AngelScript SHALL use its exported Bellwain target group without claiming puzzle workflow implementation. Optional source-note `activation_script` SHALL be mutually exclusive with `mechanism` and validate against actual placement source_script. Multiple unrepresentable controller types SHALL block the affected annotation rather than invent names or eligibility overrides.

#### Scenario: Guardians already activated

- **WHEN** Guardians are enabled and the PietyTrigger RequiredQuest subsequently completes
- **THEN** the guide does not infer despawn from that completion
- **AND** transient instructions remain distinct from live-entity withholding

### Requirement: Common output gates production integration

CanonicalSources SHALL own common DDL and source hooks. ExportBundleIntegrator SHALL own additive native refresh and its frozen receipt. WikiOverviews/DataZones SHALL own generic encounter/navigation projections and the guide SHALL own its consumer. Production cutover SHALL require refreshed activator/suppressor records, startup bool, resolved audited loot bindings and coherent common schema. Source packets or acknowledgements SHALL NOT substitute for exported records. Worktree-owned databases and writable inputs SHALL isolate announced rebuilds from shared main data.

#### Scenario: Missing refreshed binding

- **WHEN** the startup scalar, actual binding or required common relation is absent
- **THEN** production generation fails before replacing the embedded artifact
- **AND** no fake character, fabricated binding, legacy fallback or silently omitted source repairs the gap

#### Scenario: Cross-language common fixture

- **WHEN** a complete isolated fixture is built with common producer APIs
- **THEN** the actual guide writer output loads through the C# parser/evaluator with false availability, true outcome and exact support identities intact
- **AND** handwritten JSON alone does not establish the integration proof

### Requirement: Quest level estimates preserve complete alternatives

The recommended quest level SHALL use the minimum known level within each explicit alternative step group and the maximum across independently required steps and requirements. Native item variants SHALL remain OR alternatives of complete AND bundles. Unknown levels SHALL NOT count as zero. Each alternative SHALL retain its own step estimate and route.

#### Scenario: Alternative destinations have different levels

- **WHEN** The Island Tomb completes by entering either level-4 Island Tomb or level-24 Shivering Tomb (2), with no higher shared requirement
- **THEN** its recommended quest level is 4
- **AND** both destinations retain their own estimates and navigation identities

#### Scenario: A shared requirement is harder than the easier alternative

- **WHEN** either completion alternative is valid but an independent required step has level 12
- **THEN** the quest estimate includes that shared requirement rather than reporting only the easier alternative
