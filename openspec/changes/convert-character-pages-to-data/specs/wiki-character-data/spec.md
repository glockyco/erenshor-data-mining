# Spec Delta

## Purpose

Provide complete, bounded character article rendering from canonical game data while preserving editor text and proving identity continuity before automated migration.

## ADDED Requirements

### Requirement: Character calls resolve stable identities without factual overrides

The system SHALL render a data-backed character root from its stable character key. It SHALL retain distinct roots on a shared page and SHALL NOT resolve unknown identities by display name. Article parameters SHALL NOT override canonical facts. The legacy Character template SHALL remain a compatible parameter-only renderer without Lua.

#### Scenario: Shared character page

- **WHEN** two generated character identities share an article
- **THEN** each has its own data-backed call and editor values, and both render without selecting one by name

#### Scenario: Invalid or unsupported call

- **WHEN** a call has a missing, unknown or wrong-kind key, or unsupported factual parameters
- **THEN** invalid identity is diagnosed visibly, unsupported parameters do not replace data, and the appropriate documented tracking category identifies the problem

### Requirement: Character rendering exposes the complete required stat surface

Character rendering SHALL show known mana, all seven primary attributes, initialized health and AC, four resistance ranges, class, base level, actual level bounds, base experience and effective XP multiplier. It SHALL distinguish base exported attributes from initialized effective stats without a repeated explanatory disclaimer. Known zero values SHALL remain zero. Null values SHALL NOT become invented zero values.

#### Scenario: Previously hidden character stats

- **WHEN** an ordinary character has exported mana, Strength, Endurance, Dexterity, Agility, Intelligence, Wisdom and Charisma
- **THEN** all eight values are available in the rendered stat surface, along with the known class and XP rows

### Requirement: Copy-dependent character facts retain their source scope

Copy-dependent facts SHALL remain scoped to the copies or conditions that support them.

#### Scenario: Different classes within a deduplication group

- **WHEN** relevant copies in one character group have different class values
- **THEN** the page does not claim that the representative's class applies to every copy, and any shown variant retains its source conditions

### Requirement: Derived character stats come from Python and clean data

Python and clean data SHALL own derived character facts, not Lua formulas.

#### Scenario: Level boundaries and reward multipliers

- **WHEN** placement modifiers, group encounters or initialization change level around 1, 34, 35 or 40
- **THEN** displayed bounds and stats follow the shared initialization rules, the floor is respected, and XP uses its actual reward multiplier without changing encounter tier from that multiplier

#### Scenario: Base experience is not a random range

- **WHEN** raw data includes a base XP value and a higher endpoint representing a player-level bonus
- **THEN** the renderer identifies the actual base initialization XP separately and does not present the endpoints as a random XP roll or promise a fixed final payout

### Requirement: Treasure and summon characters retain their actual acquisition and scaling behavior

The renderer SHALL show source-backed summons and unplaced conditional characters without fabricating fixed locations. Scaling treasure guardians SHALL use the existing complete player-level scaling data. Treasure chests SHALL NOT show combat stat or XP blocks.

#### Scenario: Unplaced summon

- **WHEN** an exported character is summoned by an ability and has no fixed placement
- **THEN** its page shows that ability, does not invent coordinates or respawn, and has no map link based only on its name

#### Scenario: Treasure guardian and chest

- **WHEN** a treasure guardian and its chest are rendered
- **THEN** the guardian shows player-level scaling once, the chest has no combat stats, and possible hunt zones are not presented as fixed prefab positions

### Requirement: Character loot and spawn conditions use canonical relations

Character rendering SHALL consume the shared canonical item relations and shared spawn/combat-eligibility projection. It SHALL preserve copy identity, chances and probability semantics, quantities, guaranteed roll count, visible-equipment guarantees, unique-held restrictions, quest, time, furnishing and release conditions. It SHALL NOT independently select item sources or infer eligibility from initial invulnerability.

#### Scenario: Common-world source

- **WHEN** an item is available through a common-world-item replacement or generic global roll
- **THEN** the page does not invent an ordinary or guaranteed per-enemy drop edge for that source

#### Scenario: Conditional mapped placement

- **WHEN** an actual placement requires night, a completed quest, release of a protector, a trigger item or a furnished Reliquary room
- **THEN** its real location and actionable condition remain visible, and a map link is emitted only for a supported mapped placement

#### Scenario: Multiple placements

- **WHEN** a character has multiple usable locations with different spawn chances or respawns
- **THEN** the page retains their conditions and meaningful values instead of omitting the locations or inventing one universal chance

### Requirement: Editor fields and complete galleries survive conversion

Conversion SHALL preserve exact image captions, landmark descriptions, editor fallback zones, coordinates and respawn values, and unproven additional render/screenshot file titles. Canonical data SHALL take precedence over fallback fields without deleting their text. All prose, galleries, per-file captions and other editor markup outside proven generated regions SHALL remain byte-for-byte unchanged. Only checkpoint-proven bot picture/category/companion contributions MAY be removed automatically.

#### Scenario: Data covers a location fallback

- **WHEN** a preserved location fallback field is nonempty and canonical data supplies that field
- **THEN** data is shown, the original fallback value remains intact, and a documented category requests editorial review

#### Scenario: Pictures and captions

- **WHEN** canonical render and screenshot files and an editor's additional existing picture are available
- **THEN** the gallery includes them without duplicate titles, renders the canonical render first, preserves captions, and does not create broken-file gallery links for missing files

#### Scenario: Unknown companion ownership

- **WHEN** a scaling companion or category resembles generated output but has no native publication checkpoint proving ownership
- **THEN** conversion does not delete it by resemblance and blocks any duplicate-output cutover until a reviewed disposition exists

### Requirement: Authored SimPlayer articles remain distinct from generated NPCs

The ordinary character inventory SHALL exclude randomized SimPlayer generation and SHALL explicitly retain authored dedicated SimPlayer pages as manual content. A future dedicated Sim data contract SHALL be distinct from ordinary NPC data and SHALL require authored/fixed asset evidence, not a randomized name list.

#### Scenario: Authored dedicated Sim

- **WHEN** the conversion inventory encounters an authored Sim Character call such as Jethro's
- **THEN** its class, faction, old screenshot, caption and prose remain unchanged and it is not converted into an ordinary NPC record

#### Scenario: Randomized name

- **WHEN** a randomized SimPlayer name has no generated character article
- **THEN** a data update does not create or resurrect a page for that name

### Requirement: Coordinate-key replacement requires native lineage proof

Automatic coordinate-key replacement SHALL require unique native scene object identity in both retained snapshots, verified serialized GameObject/component continuity with a transform-only change, and a one-to-one correspondence of relevant dedup members and article roots. The proof SHALL bind before/after source hashes, builds, keys, transform and publication revisions.

#### Scenario: Proven movement

- **WHEN** retained serialized scene evidence proves only the same object's transform moved, the coordinate key changes and dedup membership still maps one root to one root on the same page
- **THEN** a guarded reconciliation changes only that call's stable key, preserves its editor fields and surrounding bytes, and records the proof in the rollback-capable run

### Requirement: Coordinate-key changes cannot imply identity continuity

The reconciler SHALL distinguish stable-key changes from identity continuity. GUID equality alone, name matching, nearest coordinates and suffix stripping SHALL NOT establish continuity. No permanent alias SHALL conceal a key replacement.

#### Scenario: Recycled or ambiguous native identity

- **WHEN** GUIDs duplicate, a local ID is recycled, source artifacts are unavailable, the object graph changes, or a re-rip has no proven continuity
- **THEN** the old page stays unchanged, automatic reconciliation is blocked for that page, and both candidates require an evidence-based lifecycle disposition without a guessed alias or duplicate root

#### Scenario: Dedup representative changes

- **WHEN** representative selection changes after raw member matching
- **THEN** a one-to-one membership replacement is distinguished from a group split, merge or page move, and non-one-to-one cases require explicit review

### Requirement: Character data loading stays bounded without dropping facts

Generation SHALL enforce the configured UTF-8 module page limit and publish deterministic shards. Rendering a root SHALL load only its necessary entity and relation data. Existing live module structures SHALL remain compatible. Any incompatible structure SHALL use a new title. Actual generated-scale corpus parses SHALL pass actual-host limits with at least 25 percent headroom on measurable enforcing limits before conversion approval. Unavailable measurements SHALL be reported, not invented.

#### Scenario: Heavy shared page

- **WHEN** a page has the largest combination of character roots, loot, locations and conditions in the corpus
- **THEN** its actual-host parse stays within approved page and parser budgets without truncating canonical facts or relying on a fixture-only parse

#### Scenario: New incompatible data structure

- **WHEN** the proposed structure conflicts with a live data module consumer
- **THEN** the new renderer uses an additive or new-version title and leaves the live structure intact until every reader and rollback dependency has migrated

### Requirement: Conversion acceptance covers the full corpus and guarded rollback

Before broad conversion, every eligible ordinary character page SHALL have a final legacy-versus-candidate production text parse and reviewed text, links, images, categories and limit differences. The actual local MediaWiki UI SHALL have browser evidence and reviewed screenshots. Missing staged dependencies SHALL make a comparison provisional.

#### Scenario: Incomplete acceptance corpus

- **WHEN** some generated roots, live legacy users, manual dispositions or actual-host limit results remain unaccounted for
- **THEN** conversion cannot be declared complete and obsolete generation code is not removed

### Requirement: Character conversion reuses guarded native rollback

Conversion SHALL reuse native revision-guarded edits, checkpointed manifests and rollback. A canary rollback SHALL be exercised before a separately approved broad pass.

#### Scenario: Editor saves after planning

- **WHEN** an article's revision changes after its conversion plan is generated
- **THEN** the write is a conflict and does not overwrite the editor's newer text

#### Scenario: Interrupted migration and rollback

- **WHEN** a migration stops after some successful writes
- **THEN** the manifest identifies exactly those writes and rollback restores their original roots, captions, fallback fields, companions and prose only while their deployed revisions still match


### Requirement: Shared refresh removal waits for every type cutover

Character-specific legacy generation SHALL be removed only after accepted Character conversion and rollback. The shared merge engine, article Jinja framework and full-article refresh SHALL be removed only after accepted Item, Stance, Spell, Skill, Zone and Character cutovers and disposition of remaining generated overview or Quest consumers. Native guarded stub/membership deployment and manifest rollback SHALL remain. Legacy parameter templates SHALL remain compatible.

#### Scenario: Character lands before another type

- **WHEN** Character conversion passes but another generated type or overview still needs the shared merge engine
- **THEN** Character-only dead code is removed while shared removal waits for that dependency

#### Scenario: All cutovers accepted

- **WHEN** every generated type and remaining full-article consumer has passed its cutover and rollback gate
- **THEN** obsolete merge/Jinja/full-article machinery and its callers are removed together without removing guarded publishing, rollback or manually used legacy templates
