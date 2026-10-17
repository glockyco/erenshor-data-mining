# Spec Delta

## Purpose

Render complete item articles from compact stable-identity calls while preserving editorial contributions, existing details behavior, and reversible revision-guarded conversion.

## ADDED Requirements

### Requirement: New item template resolves data by identity

The wiki SHALL offer `Template:ItemData` with a required stable item key. It SHALL render data-owned item facts from versioned bot-owned data modules and shared repository-owned wording. The legacy Item template SHALL remain parameter-only and SHALL NOT gain a data switch.

#### Scenario: Ordinary converted article

- WHEN an article contains an ItemData call with a valid stable item key
- THEN it renders identity, kind, stats, qualities, effects, sources, uses, pictures, item database index, lifecycle and build information from data
- AND the article does not need copied factual parameters or repeated mechanic explanations

#### Scenario: Invalid identity

- WHEN a call has an unknown, ambiguous or wrong-kind key
- THEN it emits a visible diagnostic and invalid-identity tracking category instead of guessing by name

### Requirement: Editorial fields are additive and explicit

The new item template SHALL preserve `type`, `questsource`, `relatedquest` and `othersource` as additive editor-owned fields. These fields SHALL NOT replace canonical classifications, acquisition, quest relationships or any other data-owned fact. Arbitrary fact parameters SHALL NOT override data and SHALL be tracked as unsupported.

#### Scenario: Edited legacy relationships survive conversion

- WHEN a fetched item root contains editor-added type or quest relationship text
- THEN conversion preserves those values and all prose outside the owned root
- AND canonical kind and quest facts still render independently

#### Scenario: An editor note is now covered by data

- WHEN a source note explicitly identifies the same item, kind and source as canonical data
- THEN it is retained and the page joins the covered-note tracking category for review
- AND freeform notes are not guessed into source identities or silently removed

### Requirement: Canonical provenance remains complete in rendering

The item renderer SHALL consume shared item provenance without independent source selection. It SHALL account for source/copy and variant identities, probability bases/ranges, quantities, conditions, location relations and lifecycle dispositions. Grouping SHALL NOT discard distinct alternatives.

#### Scenario: A conditional or unlocated acquisition is rendered

- WHEN an item source is furniture-gated, treasure-level-dependent, random auction stock or dynamically unlocated
- THEN its rendering retains those semantics and canonical identity coverage
- AND lack of coordinates does not hide the source

#### Scenario: A source is internal or transfer remains unconfirmed

- WHEN canonical evidence records an internal UI/mechanic use without a verified player transfer
- THEN internal evidence and audit coverage preserve that distinction without advertising an unverified player source or adding public research disclaimers
- AND does not claim a verified acquisition or infer an unobtainable lifecycle state

### Requirement: Tooltips and visible details remain compatible

Converted pages SHALL preserve the rendered quality and semantic-link contract used by hover consumers. All quality cards, effect details, class restrictions and image behavior SHALL remain available. A displayed spell tooltip SHALL remain the details surface without an added right-click interaction.

#### Scenario: Quality-specific hover on a converted page

- WHEN a semantic item link requests a supported quality
- THEN the existing hover interaction selects the corresponding rendered card and details from the converted target page
- AND multi-root pages do not return another item's card

#### Scenario: Historical item has effect details

- WHEN a converted historical item has a notice, infobox and effect tooltip
- THEN the notice, infobox and details retain the reviewed layout and centered effect text in a real browser

### Requirement: Production-scale Lua limits gate conversion

Before conversion, generation and parsing SHALL measure actual data page bytes and the target hosts' enforcing Lua/parser limits using generated production-scale data and the heaviest item and multi-root pages. The selected shard/load strategy SHALL leave at least 25 percent headroom under measured enforcing limits. Unavailable metrics SHALL be reported rather than fabricated. Incomplete dependency checks SHALL remain provisional.

#### Scenario: Fixture data fits but generated data exceeds a limit

- WHEN a real-data parse exceeds a byte, memory, CPU or parser budget
- THEN article conversion is blocked until the shard/load strategy is changed and remeasured
- AND no canonical source or detail is dropped to make the parse succeed

### Requirement: Conversion is guarded, complete and reversible

Every item page SHALL have a full legacy-versus-candidate production text parse before broad conversion. Conversion SHALL preserve editor fields and prose, identify every root, remove only proven owned companions, guard live writes by fetched revision and save rollback text before writing. Every write pass SHALL require a reviewed complete dry run and separate approval.

#### Scenario: Multi-root page contains an ambiguous legacy root

- WHEN any root cannot be uniquely matched to an item identity
- THEN the page and conversion batch are blocked until reviewed rather than partially declaring that page converted

#### Scenario: Article changes after fetch

- WHEN the live revision differs from the fetched base revision
- THEN conversion refuses the write and requires fetch/regeneration

#### Scenario: Canary conversion is rolled back

- WHEN a canary manifest is restored without intervening edits
- THEN original roots, owned companions, editorial values and prose are restored
- AND rollback refuses to overwrite later editor revisions

### Requirement: Updates stop rewriting existing item facts

After conversion, item article generation SHALL create identity-based stubs for new entities and reconcile existing pages only when entity membership changes. Data updates SHALL NOT rewrite existing article facts, editor-owned fields or prose. Item-specific full-article generation SHALL be deleted only after complete guarded migration, coverage and demonstrated rollback support.

#### Scenario: A game update changes a drop chance

- WHEN an existing item's canonical chance changes without changing page membership
- THEN publishing data changes its rendered chance without an article edit

#### Scenario: Generator removal would strand a reader

- WHEN a legacy companion or module still has a live reader or is required by an open rollback window
- THEN its removal is blocked
- AND shared non-item generation remains available for unconverted entity types
