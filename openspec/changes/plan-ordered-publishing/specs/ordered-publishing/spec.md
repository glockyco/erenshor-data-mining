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

Preparation SHALL produce a deterministic immutable plan and review artifacts listing every selected operation, dependency, local output, remote destination, exact payload hash, expected base, expected owned post-state and recovery limit. Complete payloads SHALL be available for review. Counts, command strings or provisional render checks SHALL NOT substitute for exact payloads. No live mutation SHALL occur during preparation or dry run.

#### Scenario: Preview contains wiki, map, and sheet operations
- **WHEN** an operator dry-runs a prepared plan
- **THEN** the report provides complete wiki diffs, map artifact manifests, and typed sheet row payloads
- **AND** it includes exact atomic Sheets body bytes and size, the complete stable workbook preimage, typed owned values and final table ranges, and structural effects on surrounding content
- **AND** it records fixed bases or explicit predecessor-receipt references
- **AND** no live write occurs

### Requirement: Prepared spreadsheet operations preserve the exact native batch

Selected tabs for one spreadsheet SHALL form one native atomic operation with a complete stable workbook preimage and exact request-body bytes. Provider-managed reference rebasing SHALL NOT be represented as a locally predicted formula postimage.

#### Scenario: A workbook payload is too large for terminal review
- **WHEN** preparation or dry-run inspection includes a large stable workbook or typed row payload
- **THEN** the native CLI presents a bounded summary containing every operation, base, dependency, destination and recovery limit
- **AND** each omitted inventory or value set has an exact artifact pointer, hash and size or count
- **AND** complete immutable payloads and exact Sheets wire-body bytes remain available as sidecars under the same approval boundary

#### Scenario: Opaque content resembles a path token
- **WHEN** approved prose, a cell value, SQL or a summary contains literal `$RUN` or `$REPO` text
- **THEN** serialization and execution preserve that content exactly
- **AND** only declared filesystem path fields are relocated

#### Scenario: A resize would destroy non-owned content
- **WHEN** table shrink would delete beside-table content or metadata, or width growth would overwrite an occupied outside column
- **THEN** preparation identifies the destructive overlap and fails before approval
- **AND** it does not silently erase that content

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
- **WHEN** a selected wiki edit, map or Sheets operation uses a provider without demonstrated conditional writes
- **THEN** review names the snapshot-based guard and concurrent-writer limitation
- **AND** execution compares the approved base before mutation and checks the resulting state afterward
- **AND** unknown or mismatched state stops the run instead of being reported as atomic protection

#### Scenario: MediaWiki merges a racing editor change
- **WHEN** MediaWiki acknowledges an edit whose actual historical parent or saved source differs from the approved transition
- **THEN** the native writer retains the acknowledged write and the actual editor-parent snapshot before reporting failure
- **AND** the reviewed preimage remains preserved separately from the actual-parent rollback preimage
- **AND** every downstream operation stops without automatic rollback or an atomic compare-and-set claim

#### Scenario: Acknowledged wiki source cannot be inspected
- **WHEN** the edit acknowledgement identifies a new revision but historical source or parent inspection fails
- **THEN** the native manifest retains that acknowledged revision and unresolved recovery state
- **AND** neither rollback nor resume treats the operation as zero writes

#### Scenario: A chip target changes without changing its placeholder
- **WHEN** a smart-chip target changes after the stable workbook preimage was captured
- **THEN** the spreadsheet operation rejects the changed preimage before mutation
- **AND** the review and retained preimage include the original chip identity

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

The publisher SHALL preserve people's prose except for exact one-time replacements supplied in a separately reviewed variant-local edit file. It SHALL NOT infer prose edits, copy those texts into tracked repository content, or treat general publish approval as permission to invent prose changes. Affected article deploys SHALL follow the reviewed prose edits, refetch, regeneration, and validation.

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

### Requirement: Prose review binds the same captured file bytes

Preparation SHALL capture and hash the prose edit file's bytes once, parse that same capture, and require the source still to match the separate review digest before finalizing preparation. It SHALL bind that file and its review declaration to the plan.

#### Scenario: The prose file changes during preparation
- **WHEN** a file replacement occurs after its separate review digest was checked
- **THEN** preparation never parses the replacement under the earlier declaration
- **AND** a changed final source digest prevents plan finalization

#### Scenario: Another selected article transcludes a prose-edited page
- **WHEN** article A transcludes page B and B has an approved prose predecessor
- **THEN** A's dependency uses B's approved projected text and actual predecessor receipt
- **AND** an approved intermediate prose revision is accepted before B's selected article successor
- **AND** an unrelated editor revision is refused

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

The coordinator SHALL execute operations through checked calls, not a shell chain that masks earlier failures. The first failed, partial, interrupted, blocked or uncertain operation SHALL make the plan fail and stop progression to every not-yet-started operation, including independent surfaces. Existing operation-level partial results SHALL remain visible. Standalone multi-tab failure collection SHALL NOT continue a coordinated plan.

#### Scenario: A middle command fails in the historical shell-chain order
- **WHEN** wiki article deploy fails after earlier wiki work succeeded and sheets and maps are later in the plan
- **THEN** no later sheet or map publication starts
- **AND** the result reports the original failing command and known earlier writes
- **AND** a successful final subprocess cannot mask the failure

### Requirement: Selected spreadsheet tabs execute as one atomic batch

Explicitly selected tabs for one spreadsheet SHALL execute through one provider-atomic batch, preserving each tab's native request order.

#### Scenario: A selected spreadsheet batch is rejected
- **WHEN** Google rejects one request in the approved atomic batch before applying it
- **THEN** no selected tab is reported as partially published
- **AND** the spreadsheet operation fails and later plan operations remain blocked

#### Scenario: A selected spreadsheet response is lost
- **WHEN** the atomic batch may have been applied but its acknowledgement is unavailable
- **THEN** the whole spreadsheet operation is uncertain
- **AND** no automatic retry or fictional per-tab success receipt is produced

### Requirement: Resume reconciles partial success and native recovery

Resume SHALL be explicit, reconcile completed results and remaining bases, skip verified successful writes, and refuse unknown outcomes or invalidated approval. It SHALL NOT automatically retry uncertain mutations, roll back later editor work, or promise unsupported cross-service rollback.

#### Scenario: A wiki deploy is partially successful
- **WHEN** a native wiki deploy writes some planned pages and then stops
- **THEN** status names the exact known pages, native manifest, blocked operations, and guarded rollback command
- **AND** resume reconciles individual native results before attempting remaining pages
- **AND** pages created during the run are reported with the existing manual deletion limitation

#### Scenario: A remote write succeeds but its receipt is lost
- **WHEN** a process stops after mutation and before recording its response
- **THEN** the operation is uncertain until uniquely reconciled with provider evidence
- **AND** it is not blindly repeated or described as successful

### Requirement: Publication persists native intent and recovery before mutation

The coordinator SHALL persist operation intent before mutation and durable receipts afterward. Existing wiki manifests SHALL remain the authority for wiki rollback. Planned wiki source text, rollback preimages and manifest replacements SHALL be durable before provider mutation.

#### Scenario: A standalone wiki edit loses its acknowledgement
- **WHEN** the native writer persists its request intent and the provider commits before a timeout or process interruption
- **THEN** its native manifest retains an unresolved per-page mutation rather than reporting zero writes
- **AND** rollback and conversion recovery refuse to skip or blindly repeat that page
- **AND** rollback submits the preserved original preimage bytes and verifies stored text using MediaWiki's saved-text normalization

### Requirement: Resume checks observed spreadsheet receipts

The spreadsheet receipt SHALL retain the complete observed stable postimage after exact owned output and preservation checks. Resume SHALL compare that observed state, not a fabricated formula projection.

#### Scenario: A provider rebases spreadsheet references

- **WHEN** an atomic spreadsheet operation completes with provider-managed reference rebasing
- **THEN** its receipt retains the complete observed stable postimage after owned-output and preservation checks
- **AND** resume compares that observed state rather than a locally predicted formula result

### Requirement: Resume refuses drift and unsupported recovery promises

Resume SHALL refuse to overwrite later editor work and SHALL NOT promise unsupported cross-service rollback.

#### Scenario: Completed work is changed before resume
- **WHEN** a completed destination no longer matches its recorded receipt and expected content
- **THEN** resume fails without overwriting it
- **AND** the operator must reconcile and review a new continuation plan

#### Scenario: A selected surface lacks transactional rollback
- **WHEN** the dry run includes map or sheet writes with only provider-specific recovery
- **THEN** review names that limitation and the evidence retained for recovery
- **AND** failure reporting does not offer a nonexistent universal rollback command

### Requirement: Shared native callers retain write attribution and uncertainty

Existing owning native publishers SHALL preserve acknowledged revisions and available saved-source and parent evidence when verification fails. They SHALL persist recoverable intent before a mutation whose outcome may become unknown. A generic exception SHALL NOT turn a possible write into a definite non-write or bypass the native account, endpoint, parent, page, model and source checks. This requirement does not add interface or image operations to coordinated selection.

#### Scenario: A protocol failure follows an edit acknowledgement
- **WHEN** a successful native edit identifies its new revision and later historical verification fails through transport, protocol, parsing or interruption
- **THEN** the acknowledged revision and any gathered saved-source and parent evidence remain available to its owning durable recovery record
- **AND** downstream publication stops rather than reporting zero writes

#### Scenario: Another administrator supplies the planned source
- **WHEN** another administrator writes matching target text before the native caller can perform its approved transition
- **THEN** generic exception reconciliation does not attribute that revision to this deployment or rollback
- **AND** recovery cannot overwrite it using a fabricated own-write receipt

#### Scenario: An image description or redirect outcome is unknown
- **WHEN** a native edit may have committed but neither its acknowledgement nor strong attribution can be obtained
- **THEN** the existing image ledger retains pending or ambiguous intent with its reviewed preimage and intended transition
- **AND** later dependent redirects or deletions stop
- **AND** recovery refuses to ignore that intent or blindly replay it

#### Scenario: Source contains line endings and Unicode whitespace
- **WHEN** a native source comparison handles CR or CRLF line endings and trailing Unicode whitespace
- **THEN** it applies MediaWiki's saved-text normalization consistently rather than Python's unrestricted whitespace trimming
- **AND** the original submitted and rollback preimage bytes remain unchanged

#### Scenario: An interface request commits before its completion checkpoint
- **WHEN** the original manifest still contains pending request intent without a recorded deploy action
- **THEN** recovery attributes every possible pending request before restoring any earlier page
- **AND** missing or ambiguous proof blocks recovery rather than excluding the possible write

#### Scenario: A pending rollback still shows its request base
- **WHEN** an earlier rollback request has no attributable completion and the live revision remains its captured base
- **THEN** recovery retains that unresolved intent and performs no new mutation, even with force
- **AND** only a proven completion or explicit provider rejection permits the next recovery action

#### Scenario: An actual-parent image restore succeeds before later recovery fails
- **WHEN** a page restoration completes but an earlier upload cannot yet be restored
- **THEN** the original publication ledger retains attributable restoration state and its linked recovery evidence
- **AND** another recovery invocation validates that receipt and continues without replaying the page edit

#### Scenario: A known image edit is recovered against another endpoint
- **WHEN** configuration points recovery at another wiki with coincident page IDs, revisions and source
- **THEN** the recorded endpoint mismatch blocks recovery before any earlier mutation is undone
- **AND** matching content does not replace destination attribution

### Requirement: Execution retains the reviewed local storage boundary

Apply and resume SHALL revalidate selected-variant run storage and resolved native output paths before opening them. They SHALL reject copied runs under tracked wiki sources and nested output symlinks escaping the approved run or entering another checkout.

#### Scenario: A native output directory is replaced with a foreign symlink
- **WHEN** a prepared run's manifest or attempt destination resolves outside approved run storage
- **THEN** execution fails before the corresponding provider mutation
- **AND** it leaves the foreign destination unchanged

### Requirement: Guard work remains proportional to actual dependencies

Normal apply SHALL NOT reread every unrelated completed wiki page before each operation. Explicit resume and inspection SHALL reconcile completed wiki pages with batched provider snapshots. Byte proofs MAY be shared only within one execution while relevant file and directory metadata seals remain unchanged. Fresh execution or resume SHALL establish fresh byte proofs.

#### Scenario: Many independent wiki pages are published
- **WHEN** a plan applies many independent wiki pages without a failure
- **THEN** completed-page reconciliation does not grow quadratically
- **AND** each page still checks its current revision and actual dependency bases before writing

#### Scenario: A source changes without changing its size or restored modification time
- **WHEN** a relevant file's kernel change-time or identity seal differs from launch
- **THEN** the affected operation refuses the cached proof before writing
- **AND** explicit preparation and review are required again
