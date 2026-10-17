# Spec Delta

## Purpose

Render stance articles from exact game identities and generated relations while preserving editorial presentation and reversible publication.

## ADDED Requirements

### Requirement: Stance articles resolve exact identities

The wiki SHALL provide StanceData with an explicit stance stable key. It SHALL render game facts from bot-owned data without factual article overrides. Legacy Stance SHALL remain a compatible parameter-only renderer.

#### Scenario: Known stance key

- WHEN a page calls StanceData with a known stance key
- THEN it renders the canonical stance name, icon, description, switch message, modifiers and regeneration state
- AND no copied factual parameters are required

#### Scenario: Missing or wrong identity

- WHEN a call lacks a key or names an unknown or wrong-kind key
- THEN the page shows an identity diagnostic and invalid-identity tracking category
- AND it does not resolve by page name or another root

### Requirement: Activating skill relations are generated once

Stance acquisition SHALL show every visible activating skill from generated typed relations. Wiki rendering SHALL NOT reconstruct activation relations by scanning skills. A skill tooltip presentation SHALL be used only when the activating identity is uniquely proven.

#### Scenario: Several skills activate a stance

- WHEN a stance has multiple activating skills
- THEN all appear with their exact identities
- AND the tooltip renders stance-native facts instead of choosing an arbitrary first skill

#### Scenario: No current activating skill

- WHEN a known stance has no activating skill
- THEN its activation relation is explicitly empty and the tooltip still shows the stance's native facts
- AND lack of a skill alone does not mark it removed

### Requirement: Native stance units retain their meaning

Rendering SHALL distinguish multipliers, percent-of-health self damage, native per-cast damage and regeneration booleans. Baseline, zero and absent values SHALL NOT be conflated.

#### Scenario: Native multiplier and special effects

- WHEN a stance has a damage multiplier of 1.4, self damage per attack of 4 and disabled regeneration
- THEN the presentation shows a 40 percent increase, 4 percent maximum-health damage per attack and regeneration disabled
- AND a baseline multiplier is not shown as a 100 percent increase

### Requirement: Editorial presentation survives conversion

StanceData SHALL support an editor-owned imagecaption and preserve prose outside proven generated spans byte for byte. Unsupported parameters SHALL NOT override data and SHALL be tracked. A notice placement control SHALL change presentation only, not lifecycle facts.

#### Scenario: Editor changes a caption and adds strategy

- WHEN a stance root has a custom caption and surrounding strategy text
- THEN conversion retains the exact caption value and strategy bytes
- AND later data updates do not rewrite them

#### Scenario: Unexpected factual parameter

- WHEN a conversion finds an unrecognized nonempty field or an unresolved editor change to a data-owned field
- THEN it blocks that page and reports the raw value for review rather than silently deleting it

### Requirement: Stance lifecycle and category remain accurate

Converted stance pages SHALL retain reviewed lifecycle notices and the Stances category in article namespace. Historical status SHALL come from recorded facts, not article eligibility or missing activation. Existing external notice text SHALL be preserved without adding a duplicate notice.

#### Scenario: Recorded removed stance remains in exported data

- WHEN a known excluded stance has a recorded removed state and an existing notice
- THEN its converted page remains readable and historical with one notice
- AND conversion does not make it eligible for new active stubs

### Requirement: Stance hover keeps exact identity

Each converted root SHALL render exactly one inline ability tooltip carrying the stance kind and root stable key. Hover and focus consumers SHALL keep selecting that exact card, including shared pages. Ordinary navigation SHALL remain available without a new right-click details interaction.

#### Scenario: A skill supplies a unique tooltip presentation

- WHEN a unique activating skill supplies the stance tooltip presentation
- THEN the tooltip retains the stance identity rather than the skill identity
- AND a keyed stance link selects that card

### Requirement: Live data structures remain compatible

Existing live entity data structures SHALL remain unchanged by conversion. New relations and lifecycle metadata SHALL use narrow separately published supplements or a separately named version. Existing public tooltip consumers SHALL remain usable throughout publication and rollback.

#### Scenario: One relation is missing from existing stance data

- WHEN activation relations are added for stance articles
- THEN existing Stances readers retain their current record structure
- AND the new relation is available without copying the complete entity schema

### Requirement: Complete comparisons and limits gate broad conversion

Broad conversion SHALL require production text parses of legacy and candidate text for every inventory page, reviewed differences and complete root dispositions. Generated full-scale data and the heaviest pages SHALL leave at least 25 percent headroom under observed enforcing page, Lua and parser limits. Missing metrics or unchecked dependencies SHALL NOT be presented as passing evidence.

#### Scenario: Fixture parsing succeeds but real data is unmeasured

- WHEN only local fixture parses are available
- THEN broad conversion remains blocked
- AND the report names the missing real-data limits and production comparisons

### Requirement: Stance conversion is guarded and reversible

Every write SHALL require a complete reviewed dry run and explicit approval, guard the fetched live revision and save rollback bytes before writing. Broad writes SHALL require separate approval after a demonstrated canary rollback. Companion removal SHALL require exact identity and checkpointed bot ownership, not proximity.

#### Scenario: A manual tooltip follows a generated root

- WHEN no checkpointed bot publication proves ownership of that tooltip
- THEN conversion preserves it or blocks for review
- AND never deletes it merely because it follows the root

#### Scenario: An editor changes a canary after publication

- WHEN rollback finds a revision newer than the deployed canary revision
- THEN rollback refuses to overwrite it
- AND reports the conflict

### Requirement: Converted stance updates change data not article facts

After verified cutover, new stance pages SHALL use compact stable-key stubs and existing pages SHALL reconcile only entity membership. Unchanged membership SHALL preserve original article bytes. Removed identities SHALL go through the lifecycle workflow. Type-specific legacy generation SHALL be removed only after full eligible coverage and rollback acceptance.

#### Scenario: A modifier changes in a game update

- WHEN an existing stance's modifier changes and page membership does not
- THEN deploying data changes the rendered modifier without an article edit

#### Scenario: A shared page contains another entity kind

- WHEN stance membership is reconciled on a shared page
- THEN unrelated roots, editorial content and their identities remain unchanged
