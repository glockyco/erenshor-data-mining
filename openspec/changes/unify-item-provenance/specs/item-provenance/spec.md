# Spec Delta

## Purpose

Provide one complete, typed item acquisition and use contract so maintained outputs cannot silently disagree about how an item is obtained, consumed, located, or retired.

## ADDED Requirements

### Requirement: One selection for every maintained output

The system SHALL select item acquisition and use facts once from exported, code-fact and reviewed inputs. All maintained wiki, map, guide and Sheets acquisition and obtainability outputs SHALL consume that selection rather than select independently from producer tables. Display formatting and ranking MAY differ.

#### Scenario: A new source kind is populated

- WHEN a supported input family contributes a new acquisition kind
- THEN the shared contract includes it and every consumer either represents it or fails with an explicit unsupported-kind error
- AND no consumer silently falls back to an older source query

### Requirement: Player access is distinct from internal existence

The contract SHALL model UI grants and non-world mechanic transfers as source kinds in their own right. It SHALL distinguish verified player access, unconfirmed player transfer, internal-only use and non-acquirable outcomes. Internally generated or UI-seeded items SHALL NOT become verified player acquisitions without transfer evidence. Access uncertainty SHALL NOT determine lifecycle.

#### Scenario: An unlimited cosmetic token is replenished by the UI

- WHEN a cosmetic panel provides and replenishes an item token through a verified player path
- THEN the contract represents the UI grant directly with its replenishment semantics
- AND does not invent a vendor or dialog source

#### Scenario: A portal box is seeded but transfer is unconfirmed

- WHEN evidence establishes a PlanningTable Portal item but player transfer still needs confirmation
- THEN the candidate mechanic source remains unconfirmed and auditable
- AND navigation and affirmative obtainability do not advertise it as a verified acquisition

#### Scenario: An item is generated for simulated-player equipment

- WHEN internal item generation is established but no player-transfer path is confirmed
- THEN internal use and the unresolved transfer state remain distinct from verified player access
- AND the item is not marked removed or unobtainable solely for lacking a confirmed player source

### Requirement: Stable identity and complete alternatives

The contract SHALL retain originating item keys, source identities, encountered character copy identities, group identities, recipe slots, quest variants, and mechanism routes. Grouping SHALL preserve the identities of every member and SHALL NOT replace differing outcomes with one maximum value.

#### Scenario: A representative differs from its encountered copy

- WHEN the display representative has stock or loot absent from the encountered copy
- THEN only the encountered copy contributes that fact
- AND the displayed representative remains a link identity rather than a fact source

#### Scenario: Item variants share a page

- WHEN hidden item variants share exactly one visible map representative
- THEN map grouping retains each originating item and acquisition identity
- AND multiple visible variants remain separate results

### Requirement: Numeric semantics survive projection

The contract and its output adapters SHALL distinguish exact, bounded, zero, unknown and inapplicable probabilities. They SHALL retain probability basis, quantities, guaranteed-pool semantics, expected counts and count distributions when available. Unknown values SHALL NOT become guaranteed, zero, or one by default.

#### Scenario: Guaranteed pool contains several items

- WHEN a source guarantees a pool roll but not a particular item
- THEN its output retains the roll guarantee separately from the item's acquisition chance

#### Scenario: Day and night have different chances

- WHEN one water yields an item at different day and night rates
- THEN both rates and their time conditions survive every acquisition projection
- AND no output presents only the maximum as an unconditional chance

#### Scenario: Global fishing replacement is already included in a rate

- WHEN a per-water final acquisition chance includes a global replacement mechanism
- THEN the contract identifies the final rate and its native mechanism evidence separately
- AND consumers do not add the global replacement chance to that final rate again

### Requirement: Conditional and unlocated sources stay factual

The contract SHALL retain typed condition alternatives, location relations and entry restrictions independently from coordinates or wiki visibility. A lack of coordinates or a wiki page SHALL NOT remove a real source or manufacture a marker.

#### Scenario: Reliquary furnishing provides a source

- WHEN a vendor or completion interaction exists only after a room slot is furnished
- THEN the source retains the room slot and furnishing condition at its placement
- AND an output does not describe it as unconditionally present

#### Scenario: Treasure eligibility differs by site

- WHEN a chest has possible treasure sites with different eligible player-level intervals
- THEN the output identifies possible hunts and preserves site-specific player eligibility
- AND chest combat level is not substituted for player level

#### Scenario: Scripted source has no resolved placement

- WHEN reviewed inputs establish a dynamic source but provide no coordinate
- THEN the source remains available as unlocated with its identity and conditions
- AND no output infers coordinates from its display representative

### Requirement: Global and random mechanisms remain distinct

Common-world swap-only outcomes SHALL be one world-like acquisition per item with an evidence-backed range, not individual named droppers. Own-table drops SHALL remain distinct. Special-world pool identities and auction route identities and actor bounds SHALL survive selection. Random auction stock SHALL NOT be described as guaranteed stock, fixed price or a fabricated listing chance.

#### Scenario: Common-world row also has an own-table flag

- WHEN a loot row includes both common-world substitution and an explicit own-table contribution
- THEN the named source remains represented
- AND swap-only rows alone determine the common-world summary range

#### Scenario: Several auction routes permit an item

- WHEN direct, replacement and gear-surplus routes have differing player or simulated-player bounds
- THEN all routes and the actor to which each bound applies remain in the contract and output coverage

### Requirement: Lifecycle is reviewed rather than inferred

Every output SHALL use the same reviewed item lifecycle disposition. Missing acquisition rows SHALL NOT imply removed or unused content. Renamed and split page relations SHALL preserve stable identity. Removed identities MAY lack a current item entity without losing their historical disposition.

#### Scenario: No current source is known

- WHEN an item has no acquisition source and no reviewed retired disposition
- THEN the system reports the unresolved or source-free state without inventing a removed-content fact

### Requirement: Cross-output coverage conserves facts

Build and generation validation SHALL account for every canonical acquisition/use identity and every mandatory dimension on each maintained output. A reversible grouping or explicit surface visibility disposition MAY account for a fact. Missing identities, probabilities, quantities, conditions, location relations or lifecycle dispositions SHALL fail validation. Independent input-to-contract coverage SHALL prevent all consumers agreeing on the same omission.

#### Scenario: A source row remains but a condition disappears

- WHEN an adapter emits a source identity without its mandatory furnishing, quest, actor-level or time condition
- THEN coverage validation fails even though the output contains a nonempty source row

#### Scenario: A populated input family is discarded by the selector

- WHEN an input-to-contract anti-join finds an unexplained acquisition or use record
- THEN database construction fails and names the input identity
- AND positive controls distinguish genuinely empty input from a broken query

### Requirement: Publication and rollback keep a coherent contract

Consumers SHALL reject incompatible provenance schema versions. Rollback SHALL restore matching database and generated output versions. The public SQLite URL SHALL remain available. Low-level relations SHALL remain only where required as producer inputs, and obsolete schema SHALL NOT be retained solely as compatibility tables or views for unknown consumers.

#### Scenario: Reader and database versions differ

- WHEN a maintained reader receives an unsupported provenance version
- THEN it fails explicitly instead of silently reading old selectors or partial facts

### Requirement: Serialized loot requires a lootable host

Canonical loot acquisition SHALL honor the game's actual host predicate before classifying serialized loot as player-accessible. Missing hosts, destroy-on-death hosts and NPCs that leave no corpse SHALL contribute no player loot roll. Their serialized records SHALL remain accounted for as non-acquirable evidence. Summoned status alone SHALL NOT exclude an otherwise eligible host.

#### Scenario: Serialized loot belongs to a host that leaves no corpse

- WHEN the game returns before loot rolls because the host is missing, destroys on death or leaves no corpse
- THEN explicit and world-roll provenance does not advertise that host as a player loot opportunity
- AND completeness validation accounts for the exclusion rather than inventing a missing acquisition

#### Scenario: A summoned host is loot eligible

- WHEN a summoned host exists and both destroy-on-death and no-corpse flags are false
- THEN summon status alone does not suppress its otherwise valid loot acquisition facts
