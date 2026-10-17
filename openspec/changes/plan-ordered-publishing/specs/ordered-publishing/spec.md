# Spec Delta

## Purpose

Define reviewable, explicitly selected publication across wiki, maps, and sheets while retaining each surface's guarded operations and honest partial-failure recovery.

## ADDED Requirements

### Requirement: Publishing requires explicit bounded selection

The publisher SHALL require a nonempty explicit selection of exact wiki page titles, map service targets, or sheet tabs. It SHALL NOT default to all surfaces or silently expand the live write set to satisfy dependencies. Optional wiki page classes SHALL retain their existing opt-ins. The variant SHALL be selected through the root CLI option.

#### Scenario: No surface is selected
- **WHEN** preparation receives an absent or empty surface selection
- **THEN** it fails without live writes
- **AND** it names the required explicit selection

#### Scenario: A dependency is outside the selection
- **WHEN** a selected reader needs data that is neither correctly live nor explicitly selected
- **THEN** preparation names the missing dependency and its reader
- **AND** it requires amended selection instead of silently adding a live write

#### Scenario: Only maps are selected
- **WHEN** the operator selects only the canonical map service
- **THEN** no wiki, Sheets, or legacy map writes are planned or attempted

### Requirement: A prepared plan identifies exact writes

Preparation SHALL produce a deterministic immutable plan and review artifacts containing every selected operation, dependency, local output, remote destination, exact payload hash, expected base, expected post-state, and recovery limit. The complete payloads SHALL be available for review. No live mutation SHALL occur during preparation or dry run. Counts, command strings, or provisional render checks SHALL NOT substitute for exact payloads.

#### Scenario: Preview contains wiki, map, and sheet operations
- **WHEN** an operator dry-runs a prepared plan
- **THEN** the report provides complete wiki diffs, map artifact manifests, and typed sheet row payloads
- **AND** it includes sheet table resizing, clearing, inserted or deleted rows, shifted content, and all affected ranges
- **AND** it records fixed bases or explicit predecessor-receipt references
- **AND** no live write occurs

#### Scenario: A selected sheet lacks its required table
- **WHEN** preparation inspects a selected tab and finds no table required by the existing publisher
- **THEN** preparation fails before approval and names that tab
- **AND** a successful SQL preview is not treated as deployability evidence

#### Scenario: Equivalent selections use different input order
- **WHEN** two preparations use identical selected inputs, live bases, and payload bytes with differently ordered selections
- **THEN** their ordered operation graph and immutable plan digest are identical

### Requirement: One human approval binds immutable inputs and live bases

A live apply or resume SHALL require an explicit human approval declaration naming the reviewed plan digest. It SHALL verify all payloads, selected source and configuration inputs, destination identities, and relevant live bases before the first live mutation and before each affected operation. It SHALL NOT automatically approve, replan, widen drift acceptance, or replace prepared text under that approval. Secrets SHALL NOT be included in review artifacts.

#### Scenario: The plan is not approved
- **WHEN** live apply is invoked without the reviewed digest
- **THEN** it fails before any live write
- **AND** dry-run inspection remains available without approval

#### Scenario: A local source or target changes after review
- **WHEN** SQL, wiki source, database bytes, deployment configuration, selected target, or prepared payload changes after approval
- **THEN** apply refuses the old plan before the affected write
- **AND** it requires preparation and review of a new plan

#### Scenario: A live page revision changes after preparation
- **WHEN** an editor changes a selected page or required wiki dependency after its base was captured
- **THEN** the affected operation fails its revision check
- **AND** remaining operations stop without refetching and silently reapproving the changed page

#### Scenario: A planned predecessor advances a base
- **WHEN** an approved prose operation writes exactly its reviewed text and returns a new revision
- **THEN** the subsequent article operation may use that receipt's revision as its base
- **AND** no unrelated revision advancement is accepted

#### Scenario: The provider lacks atomic revision guards
- **WHEN** a map or Sheets operation uses a provider without demonstrated conditional writes
- **THEN** review names the snapshot-based guard and concurrent-writer limitation
- **AND** execution compares the approved base before mutation and checks the resulting state afterward
- **AND** unknown or mismatched state stops the run instead of being reported as atomic protection

### Requirement: Data and the shared link catalog precede readers

The plan SHALL deterministically order selected data and shared link-catalog writes before selected readers. It SHALL retain the existing repository dependency checks, content-model rules, opt-ins, source checks, drift checks, render checks, and revision guards. The article operation SHALL verify the live catalog digest before article writes. A provisional prepublication render result SHALL NOT disable the direct pre-write checks.

#### Scenario: The live link catalog is stale
- **WHEN** articles need a catalog different from the live catalog
- **THEN** a plan with the explicitly selected catalog deploy places it before those articles
- **AND** a plan without that selected prerequisite fails preparation
- **AND** articles are not written until the approved catalog is live

#### Scenario: Catalog publication fails
- **WHEN** the catalog operation fails or has an uncertain result
- **THEN** article and later map or sheet operations remain blocked
- **AND** the plan returns failure even if later surfaces could otherwise run

#### Scenario: A dependency check is provisional in dry run
- **WHEN** a selected new dependency cannot be loaded by a live sandbox before publication
- **THEN** review labels the check provisional without changing the frozen payload
- **AND** execution reruns the existing direct check after predecessors complete
- **AND** a check failure stops rather than rewriting content under the old approval

### Requirement: People's prose requires separate review and regeneration

The publisher SHALL preserve people's prose except for exact one-time replacements supplied in a separately reviewed variant-local edit file. It SHALL bind that file and its review declaration to the plan. It SHALL NOT infer prose edits, copy those texts into tracked repository content, or treat general publish approval as permission to invent prose changes. Affected article deploys SHALL follow the reviewed prose edits, refetch, regeneration, and validation.

#### Scenario: Prose changes on a page with a generated root
- **WHEN** a separately reviewed replacement and a generated-root update target the same article
- **THEN** preparation previews the exact prose replacement and the article generated from its projected result
- **AND** execution applies the guarded prose edit first and refetches its returned revision
- **AND** execution regenerates and validates before the article write
- **AND** it deploys only if regenerated bytes equal the reviewed candidate

#### Scenario: Refetch or regeneration differs from the projection
- **WHEN** post-edit refetch includes an unrelated revision or regeneration produces different article bytes
- **THEN** the article operation is blocked
- **AND** the known prose write remains recorded with its native rollback manifest
- **AND** continuation requires a new review rather than automatic approval

#### Scenario: A prose edit is not separately reviewed
- **WHEN** selection includes a prose file without a matching separate review declaration
- **THEN** preparation rejects the prose operation
- **AND** it does not synthesize or apply a replacement

### Requirement: Maps deployment uses the reviewed fresh build

For each selected maps publication, preparation SHALL run the existing build path from pinned inputs, freeze the deployable artifact bytes, and retain native build provenance. Deployment SHALL recheck native freshness and approved artifact hashes. When both targets are selected, canonical SHALL precede legacy. Both hosts SHALL preserve the unchanged selected database bytes at the existing database URL through the prerendered route.

#### Scenario: Source changes after building
- **WHEN** map source, data, configuration, tiles, or image inputs change after the reviewed build
- **THEN** deployment fails as stale or approval-invalid before that service is written
- **AND** it does not rebuild and deploy new bytes under the old approval

#### Scenario: An artifact changes without a source change
- **WHEN** a deployable asset differs from the reviewed artifact manifest
- **THEN** deployment refuses the artifact even if the native input sidecar still matches

#### Scenario: External consumers download the database
- **WHEN** either selected map host serves the established database URL
- **THEN** its response body equals the selected clean database bytes
- **AND** publication does not remove the route because ordinary site pages no longer download SQLite

#### Scenario: Canonical succeeds and legacy fails
- **WHEN** canonical deploy succeeds and legacy deploy fails
- **THEN** status records canonical's receipt and legacy's failure
- **AND** explicit resume publishes only legacy with the same approved build if all remaining guards still pass

### Requirement: A failed operation halts plan progression

The coordinator SHALL execute operations through checked calls, not a shell chain that masks earlier failures. The first failed, partial, interrupted, blocked, or uncertain operation SHALL make the plan fail and stop progression to every not-yet-started operation, including independent surfaces. Existing operation-level partial results SHALL remain visible. Sheets tabs SHALL be separate plan operations so standalone batch failure collection cannot continue the plan.

#### Scenario: A middle command fails in the historical shell-chain order
- **WHEN** wiki article deploy fails after earlier wiki work succeeded and sheets and maps are later in the plan
- **THEN** no later sheet or map publication starts
- **AND** the result reports the original failing command and known earlier writes
- **AND** a successful final subprocess cannot mask the failure

#### Scenario: One sheet tab fails
- **WHEN** the first selected tab fails after some structural requests were written
- **THEN** the plan records those known partial effects and fails
- **AND** the next selected tab is not published
- **AND** status does not imply that the failed tab was unchanged

### Requirement: Resume reconciles partial success and native recovery

The coordinator SHALL persist operation intent before mutation and durable receipts afterward. It SHALL preserve existing wiki manifests as the authority for wiki rollback. Resume SHALL be explicit, reconcile completed results and remaining bases, skip verified successful writes, and refuse unknown outcomes or invalidated approval. It SHALL NOT automatically retry uncertain mutations, roll back later editor work, or promise unsupported cross-service rollback.

#### Scenario: A wiki deploy is partially successful
- **WHEN** a native wiki deploy writes some planned pages and then stops
- **THEN** status names the exact known pages, native manifest, blocked operations, and guarded rollback command
- **AND** resume reconciles individual native results before attempting remaining pages
- **AND** pages created during the run are reported with the existing manual deletion limitation

#### Scenario: A remote write succeeds but its receipt is lost
- **WHEN** a process stops after mutation and before recording its response
- **THEN** the operation is uncertain until uniquely reconciled with provider evidence
- **AND** it is not blindly repeated or described as successful

#### Scenario: Completed work is changed before resume
- **WHEN** a completed destination no longer matches its recorded receipt and expected content
- **THEN** resume fails without overwriting it
- **AND** the operator must reconcile and review a new continuation plan

#### Scenario: A selected surface lacks transactional rollback
- **WHEN** the dry run includes map or sheet writes with only provider-specific recovery
- **THEN** review names that limitation and the evidence retained for recovery
- **AND** failure reporting does not offer a nonexistent universal rollback command
