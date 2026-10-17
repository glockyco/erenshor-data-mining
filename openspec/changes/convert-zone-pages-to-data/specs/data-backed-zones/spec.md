# Spec Delta

## Purpose

Define data-backed zone infoboxes that share authoritative zone facts while preserving editor content and safe, reversible article conversion.

## ADDED Requirements

### Requirement: Zone infobox facts have one authoritative producer

The data-backed zone infobox SHALL obtain classification, combat-eligible fixed enemy level bounds and median, player-scaling state, and usable directed connections with their conditions from the same Python/clean-database producer as the zone overview. It SHALL NOT infer Raid from raid persistence, select another hostile population, or compute these facts through Lua queries or article overrides. Classification corrections SHALL reach the common producer with a reason.

#### Scenario: A raid-capable guild hall

- **WHEN** a zone permits raid persistence but is not classified Raid by the shared zone producer
- **THEN** its infobox does not classify it Raid
- **AND** its classification agrees with the overview

#### Scenario: A vulnerable copy shares a page with an ineligible copy

- **WHEN** only the actual ineligible copy is placed in a zone
- **THEN** a vulnerable copy elsewhere does not cause that zone's level summary to include it

#### Scenario: Level variance and scaling

- **WHEN** eligible fixed encounters have spawn modifiers, initialization variance or group-encounter rules and other eligible encounters scale with the player
- **THEN** the infobox uses the shared fixed bounds and nominal median and separately identifies scaling
- **AND** it does not substitute base levels, spawn-weighted medians or medians of scene medians

### Requirement: One infobox represents a declared grouped zone page

A page shared by zone scenes SHALL render one ZoneData infobox through an explicit stable identity and a generated same-page membership relation. Every current member SHALL be represented. Differing scene summaries and map targets SHALL retain their scene meaning. The renderer SHALL NOT discover membership through name guessing or independently classify or select records.

#### Scenario: Three portal scenes share one article

- **WHEN** three mapped portal scenes share a page and have different enemy summaries
- **THEN** one infobox presents their separately labeled summaries and all valid maps
- **AND** it does not create three infoboxes or one fabricated aggregate median

#### Scenario: Two disconnected tomb sections

- **WHEN** two scenes on a shared tomb article represent disconnected entrances
- **THEN** the infobox preserves their distinct map labels and does not imply that the sections connect

#### Scenario: Invalid group data

- **WHEN** a group contains a key from another article or omits a currently mapped scene
- **THEN** data generation fails with the offending identities before publication

### Requirement: Missing data and unsupported parameters are visible

A ZoneData call SHALL require a valid zone stable identity. Missing, unknown, wrong-kind or ambiguous identities, missing required generated records and unsupported parameters SHALL produce documented diagnostics and tracking categories. Unsupported parameters SHALL NOT override canonical facts. Known absence of fixed hostile encounters SHALL be distinguished from missing export data and player-scaled encounters without inventing zero-valued levels. The infobox SHALL identify its data build through maintained shared presentation.

#### Scenario: An article supplies a factual override

- **WHEN** a ZoneData call supplies a legacy type or numeric level parameter as a factual override
- **THEN** canonical facts remain unchanged
- **AND** the page identifies that unsupported input for review

#### Scenario: Event puzzles without fixed hostile encounters

- **WHEN** complete source data records no eligible fixed hostile encounters for an event zone
- **THEN** the infobox communicates that state instead of fabricating a numeric range or reporting missing data

### Requirement: Editor content survives with its actual meaning

Conversion SHALL account for every populated legacy field and SHALL preserve exact image and caption value bytes and all editor text outside the converted infobox. Existing level, type, map and connection values SHALL have individually reviewed dispositions grounded in current shared facts, page context and relevant access behavior. Conversion SHALL NOT silently relabel a value as advice, invent an access requirement, discard a note, or introduce contradictory competing classifications or numeric level rows. Unresolved material meanings SHALL block the conversion batch and leave original articles unchanged.

Confirmed advice MAY become a concise editor-owned contextual note. Confirmed classification belongs in the common producer, not a factual article override. Notes retained as editor input SHALL remain separate from authoritative navigation and combat facts.

#### Scenario: A level field could describe a one-time encounter

- **WHEN** a guild hall says `16+`, its entry path establishes a key requirement rather than a player-level check, and the meaning of the level value is unresolved
- **THEN** the batch is blocked pending an approved disposition
- **AND** the value is not automatically changed into Minimum level or Recommended level

#### Scenario: An incomplete old range

- **WHEN** an old field says `5-?` and source data contains lower-level eligible enemies
- **THEN** the disagreement is reviewed explicitly
- **AND** conversion does not hide it by adding a contradictory recommendation row

#### Scenario: Editor pictures and surrounding rosters

- **WHEN** a zone root contains nested image markup and a caption and the page also contains rosters, prose, map pictures, comments, a navbox and placed view calls
- **THEN** the image and caption value bytes survive
- **AND** all content outside the replaced root is byte-identical
- **AND** no roster or view table is added or duplicated

### Requirement: Zone map targets remain complete and compatible

Generated map targets SHALL use validated case-sensitive scene identities present in the actual map-position input and the existing public map URL and selector contract. Every independently mapped member of a grouped page SHALL be available. Editor map presentation SHALL be retained only with a reviewed complete target set, without duplicate rows or misleading destinations. Missing or malformed required map input SHALL fail generation. This conversion SHALL NOT change the published database URL or companion protocol or URLs.

#### Scenario: A shared page previously linked only its first scene

- **WHEN** a three-scene article's old map field links one scene but all three have published map targets
- **THEN** its converted infobox exposes all three correct targets
- **AND** any editor labels and surrounding notes have approved preserved dispositions

#### Scenario: Scene selector encoding

- **WHEN** a map target is rendered
- **THEN** its selector uses the map's original case-sensitive scene name and the complete selector is safely encoded as one query value

### Requirement: Directed connection conditions remain intact

The infobox SHALL render only the shared producer's usable outgoing connections. It SHALL retain each line's distinct activation/access conditions, conjunctions, alternative groups and direction. It SHALL NOT infer a reverse route, restore an unusable raw line, or require a gated entrance's condition for a separate free entrance. Supplemental editor connection notes SHALL NOT mutate the canonical route graph.

#### Scenario: A disabled portal can activate

- **WHEN** an initially disabled route has a satisfiable exported activation gate
- **THEN** the infobox retains the route with its conditions
- **AND** it does not claim that the route is always active

#### Scenario: A copied unusable exit and a gated alternative

- **WHEN** a raw export has an unusable copied exit and a different usable quest-gated line
- **THEN** the copied exit is absent and the usable line retains its own quest gate

#### Scenario: Free and locked entrances reach the same destination

- **WHEN** one outgoing entrance is free and another requires a key
- **THEN** the display preserves those alternatives rather than requiring the key for both

### Requirement: Data structure changes preserve existing readers

ZoneData SHALL reuse complete immutable published data modules. Additional page membership or validated map targets SHALL use a narrow relation when needed. An incompatible structure SHALL publish under a new title with readers migrated before old data is retired. Existing overview, link, editor-module and rollback readers SHALL remain usable.

#### Scenario: The overview data module is already live

- **WHEN** zone conversion needs page grouping not represented in its published shape
- **THEN** grouping is added without changing the live module's structure in place or duplicating all zone facts

### Requirement: Full host comparisons and limits gate conversion

Before article conversion, every actual current zone page SHALL have a complete production legacy-text versus candidate-text parse comparison against available real dependencies. All visible text, category, image/caption, map, link, gate and scene-summary differences SHALL be reviewed. Local browser inspection and screenshots SHALL precede live approval. Actual production-scale data and enforcing host limits SHALL establish at least 25 percent headroom for exposed parser and Lua limits. Unavailable metrics SHALL be stated rather than fabricated. A failed limit SHALL NOT be solved by dropping members, gates or editor content.

#### Scenario: A dependency is missing in a sandbox

- **WHEN** a candidate parse cannot load a required new dependency
- **THEN** the result is provisional and cannot approve article conversion

#### Scenario: The largest grouped page exceeds its budget

- **WHEN** the real candidate's heaviest page fails a measured limit or headroom budget
- **THEN** conversion is blocked until loading or sharding is corrected and comparisons are rerun

### Requirement: Zone conversion is guarded and reversible through the native path

Zone conversion SHALL use the existing native guarded article/deployment/manifest/rollback machinery rather than a separate writer or duplicated migration engine. Its complete inventory SHALL include current generated membership and all live zone roots. Ambiguous roots, duplicate group calls, unknown fields, incomplete membership or unresolved field dispositions SHALL block the batch. Each write SHALL be guarded by its reviewed base revision. The manifest SHALL exist before the first write and checkpoint successful new revisions. Rollback SHALL restore exact original article bytes and refuse later edits. A canary rollback SHALL be demonstrated before separately approved broad conversion.

#### Scenario: A page changes after comparison

- **WHEN** an editor changes or deletes the article before its planned write
- **THEN** the native path reports a conflict without overwriting the new state

#### Scenario: An interrupted canary

- **WHEN** a canary stops after writing only some pages
- **THEN** its manifest identifies every successful write and its original bytes
- **AND** those pages can be restored without overwriting later editor revisions

### Requirement: Cutover leaves facts in data and preserves legacy compatibility

After complete approved group coverage and rollback acceptance, refresh SHALL create compact ZoneData stubs for new zone pages and SHALL return existing article bytes unchanged when article membership is unchanged. A new member under a valid existing page anchor SHALL update the generated relation without requiring an article edit. True membership or lifecycle changes SHALL use guarded reconciliation. Zone-specific full-article generation SHALL be removed only after those gates. Shared machinery still used by other types, native guarded deployment/rollback and compatible parameter-only legacy Zone, MapLink and navbox templates SHALL remain available.

#### Scenario: An existing zone's enemy median changes

- **WHEN** a game update changes its shared enemy summary without changing article membership
- **THEN** only data publication changes the rendered summary
- **AND** the article source remains byte-identical

#### Scenario: Another scene joins a grouped article

- **WHEN** a new mapped scene joins an existing group whose root anchor remains valid
- **THEN** the page relation adds that member and the existing infobox renders it without rewriting editor content

#### Scenario: Another type still needs the merge engine

- **WHEN** zone conversion passes its deletion gate but character conversion is incomplete
- **THEN** only obsolete zone-specific full-article paths are removed
- **AND** native rollback and shared unconverted-type generation remain usable
