# Design

## Context

See proposal.md for motivation. This change adds coordination, not new publication ownership.

### Inspected contracts

- `src/erenshor/cli/commands/wiki.py:916-1040` generates and validates merged articles from the clean database and fetched text. Its dry run does not materialize generated files.
- `wiki.py:1257-1515` explicitly selects generated data, templates, and maintained content. Generated data requires exact titles. Repository deploy checks dependencies and drift, hashes sources, checkpoints rollback manifests, and uses revision-guarded edits.
- `wiki.py:862-913` replans exact prose replacements against the live snapshot on every invocation. An ordinary later invocation is not bound to a previous dry run.
- `wiki.py:1677-1817` binds article edits to fetched revisions, checks the live semantic-link catalog, requires a summary, and writes article rollback manifests. `src/erenshor/application/wiki_deploy/guarded_edits.py:38-99` already carries reviewed text and a base revision.
- `src/erenshor/cli/commands/maps.py:289-465` builds from the selected variant, records input provenance, checks freshness before deploy, and publishes canonical before legacy. Its deploy dry run prints commands, not an asset manifest or remote base.
- `src/erenshor/application/maps/build_info.py:82-117` hashes code, database, and a tile summary. That is useful freshness evidence, not a digest of every deployable byte. The plan must also hash actual artifacts and assets. It must not claim that the current tile summary detects same-size byte changes.
- `src/maps/src/routes/db/erenshor.sqlite/+server.ts:1-14` prerenders unchanged selected database bytes. Keep this route and its URL.
- `src/erenshor/cli/commands/sheets.py:146-213` requires explicit tab selection or explicit all-tabs. `src/erenshor/application/sheets/service.py:172-294` formats and publishes each tab and continues after an individual failure. Its dry run formats rows but never inspects live tables. `src/erenshor/infrastructure/publishers/sheets.py:150-255,313-425,427-577` requires an existing table and can write values, resize it, insert rows, and delete rows. A row count alone is not an exact preview.
- `openspec/specs/command-failure-semantics/spec.md:8-30` allows batch failure collection while requiring a failed final result. Plan-level fail-fast execution is a stricter coordination policy, not a change to standalone Sheets batching.

### Operational evidence

The observed failures establish the ordering and recovery cases. They were not re-exercised for planning:

- `bg_233` used a semicolon-separated shell chain. Article deploy stopped because the live semantic-link catalog differed, but Sheets and both map Workers still deployed.
- `bg_240` later completed 973 article writes and prose corrections, then maps deploy rejected a build because source had changed after building.
- Revision invalidation was a known hazard avoided by refetching and regenerating the two prose pages after their edits. It was not an observed failed deploy. The revision-conflict behavior is represented in `tests/unit/application/wiki_deploy/test_articles.py:50-102`.

The individual catalog and stale-build guards worked. The missing boundary was approval and failure propagation across commands.

## Goals / Non-Goals

Goals:

- Make the complete selected write set reviewable before any live mutation.
- Retain existing guards while binding every operation to one approved input and base-state snapshot.
- Explain and recover partial success without pretending cross-service atomicity.

Non-goals:

- Another deployment engine, generalized workflow language, automatic retries, automatic rollback, or automatic approval.
- Exporting or rebuilding the clean database, publishing images or gadgets, deleting wiki pages, or releasing mods.
- Inferring prose corrections, copying people's articles into repository sources, or changing data-backed wiki conversion policy.

## Decisions

### D1. CLI shape and explicit selection

Add `publish` to the existing Typer root. Variant selection remains root `-V`. Root `--dry-run` remains the only dry-run option.

```text
uv run erenshor -V main publish prepare --selection /tmp/publish-selection.toml --output <variant-local-run-dir>
uv run erenshor -V main --dry-run publish apply <run-dir>/plan.json
uv run erenshor -V main publish apply <run-dir>/plan.json --approval sha256:<digest>
uv run erenshor -V main publish status <run-dir>/plan.json
uv run erenshor -V main --dry-run publish resume <run-dir>/plan.json
uv run erenshor -V main publish resume <run-dir>/plan.json --approval sha256:<digest>
```

`prepare` writes only local preparation artifacts. It performs read-only remote inspection and prints its exact local output paths before preparation. With root dry run it computes and reports preparation actions without durable artifacts or live writes. `apply` and `resume` dry runs print the complete prepared write set, conflicts, dependencies, and recovery limits, with no live mutations and no approval sidecar. They require no approval token for review. Only the non-dry-run apply/resume paths accept explicit human approval after review. The digest argument records the operator's approval declaration, not a cryptographic identity or a mechanism for an agent to approve itself.

The selection TOML is a fixed schema, not an executable command list:

```toml
schema_version = 1
summary = "Refresh selected item sources"

[wiki]
article_titles = ["Selected article"]
repo_titles = ["Module:Erenshor/Link"]
data_titles = ["Module:Erenshor/Data/Links"]
include_templates = false
include_content_pages = false
render_check = true
accept_drift = []
# Optional. Keep editor text outside tracked source.
page_edits_file = "/absolute/variant-local/reviewed-edits.toml"
prose_review_sha256 = "<digest from the separately reviewed exact edit file>"

[maps]
targets = ["canonical", "legacy"]

[sheets]
tabs = ["items"]
```

Absent sections select nothing. Empty total selection fails. Exact titles and tab names are mandatory for selected wiki and sheets surfaces. Maps targets are explicit. Reject unknown keys, duplicate ownership, optional pages without opt-in, and unknown targets. There is no `--all`, implicit all-pages, or all-surfaces default. Selection order does not control execution order.

A required dependency outside the selection is reported with its reason. Preparation does not silently add live writes. The operator explicitly amends selection and prepares again. An already-live dependency can satisfy an edge only if its revision and required content are captured and later rechecked.

### D2. Artifact ownership and approval boundary

| Artifact or destination | Owner | Write boundary |
|---|---|---|
| Selection, exact prose-edit file, prose review declaration | operator | explicit selection and separate prose review |
| Clean database, mapping, lifecycle data, image catalog, maintained sources | existing pipeline or maintainers | read-only to publishing |
| Local plan, frozen payloads, preparation report | publish planner | new variant-local run directory, no tracked article copies |
| Local journal and existing deploy manifests | coordinator and existing operation owners | durable intent before mutation and receipt after mutation |
| Bot data pages | generators and existing repo-page deploy | approved source hashes and live bases |
| Repository modules/templates/content | maintained sources and repo-page deploy | opt-ins, drift, dependencies, render and revision guards |
| Article roots/tables | existing generator and article deploy | approved generated bytes and fetched base |
| People's prose | editors | separately reviewed exact replacements only |
| Map assets and database route | maps build/deploy | fresh build, approved artifact hashes and selected service |
| Selected spreadsheet tables and provider-managed reference effects | Sheets publisher | exact approved atomic requests against a complete stable workbook preimage |

Store `plan.json`, content-addressed payloads, reports, and the append-only execution journal under one new run directory resolved through variant configuration. Never place prose payloads in tracked `wiki/`. Canonical JSON with a schema version produces the SHA-256 approval digest. Exclude the digest field itself and mutable execution receipts from that digest. Include every payload hash and expected transition in the immutable plan. The application validates the serialized digest, rather than trusting file permissions.

Represent declared payload and output path fields relative to the run directory in the immutable digest. Never relocate opaque page text, summaries, diffs, SQL, cell values, or serialized provider request bytes. Keep absolute run location, preparation time, and execution timestamps in nondigested metadata so equivalent preparations do not differ only because their run directories differ.

The native terminal review is a bounded metadata view, not an inline dump of workbook cells. Preparation retains a readable summary beside the complete review and content-addressed payloads. Every compacted inventory has an exact artifact pointer, digest and count. Structural request fields remain visible while typed cell matrices remain in their exact sidecars. The Sheets wire-body sidecar contains the original UTF-8 request bytes and is itself an approved input. This keeps practical human review separate from payload availability without weakening the approval boundary.

The plan contains selected variant and configured destination identities, game build ID, clean database bytes digest, source and relevant configuration hashes, exact generator selections, fetched bases, per-operation payload hashes, content models, summaries, account assertions, accepted drift titles, dependency edges, and every local output or remote write. Hash credentials' destination/account identity, never credentials or secrets. Bind map source, both deployment configs, lockfile, tiles, image inputs, build sidecar, and every deployable asset byte. Bind SQL query sources, map link base, typed frozen sheet rows, live table IDs/ranges and structural operations.

Map image pins are the catalog pixel files selected by the native item and character visibility queries, not capture archives or wiki publication images. Full source, static assets including tiles, deployment configurations, selected database, and frozen output byte manifests remain required. During one execution, the coordinator's launch-verified file evidence can supply map manifests while metadata seals remain unchanged. The map adapter shares native freshness evidence across the two targets in that guarded execution and always rechecks each target's remote base and deployment receipt. Standalone adapter calls read and compare local bytes without that runtime proof.

Both native map deployment and prepared publication resolve destinations through one authority using the selected variant's map origins and Wrangler configurations. A Custom Domain must be declared in the selected configuration and currently bound to that account's selected production service. A workers.dev origin must match the selected service and account subdomain and be enabled remotely. Distinct targets cannot share one postflight origin.

The hostname inspection seam uses `wrangler auth token --json` to select the same native environment or local OAuth credential in memory, then sends GET requests only. Credentials never enter payloads, fingerprints, reports or logs. The read contracts are Cloudflare's [account subdomain](https://developers.cloudflare.com/api/resources/workers/subresources/subdomains/methods/get/), [script subdomain](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/subdomain/methods/get/) and [Custom Domain association](https://developers.cloudflare.com/api/resources/workers/subresources/domains/methods/list/) APIs. No additional mutation transport or login path is introduced.

A process lock prevents two local executors from applying the same run. It is not a distributed lock. A source, selection, destination, payload, or relevant live-base change invalidates approval. Do not repair the old plan. Prepare and review a new plan for remaining work.

The trusted CLI loads one immutable plan and frozen payload set for an execution. It hashes each unique pinned file once at launch and derives directory manifests from that evidence. Before an affected operation it rechecks the relevant file and directory kernel seals, including device, inode, type, size, nanosecond modification/change times, and symlink identity. Any seal change invalidates the run even if the bytes were restored. This local guard window is not a sandbox for untrusted code or a distributed filesystem lock. Explicit resume establishes fresh byte proofs. Preparation deduplicates shared fingerprints within each pre/post guard window.

Completed wiki receipts are reconciled in one batched snapshot pass on explicit resume or inspection. Normal wiki apply checks the current page and its actual dependency snapshots, not every unrelated completed page. Before each map or spreadsheet consumer, the coordinator batches its declared wiki prerequisites and rechecks relevant map receipts using shared local byte proof. The closed two-map-target and one-spreadsheet boundary keeps these additional passes linear rather than repeating them before every wiki page. Exact predecessor receipt hashes still bind approved transitions. Run storage and every native output path are revalidated before opening locks, journals, manifests, or attempt directories.

### D3. Reuse application services with explicit prepared inputs

Proposed application API:

```text
prepare_publish(selection, context) -> PreparedPublishPlan
inspect_publish(plan, context, journal=None) -> PublishReview
apply_publish(plan, approval_digest, context) -> PublishRunResult
resume_publish(plan, approval_digest, context, journal) -> PublishRunResult
```

Use a closed set of typed operation records for wiki data/repo deployment, guarded prose edits, article generation/deploy, map build/deploy, and one atomic group of explicitly selected tabs per spreadsheet. Dispatch these through fixed code branches to existing application functions or CLI-owned subprocess helpers with argument vectors and checked exit status. There is no pluggable registry, arbitrary command field, user-authored dependency graph, or extensible workflow language. Stage status is `pending`, `running`, `succeeded`, `failed`, `blocked`, or `uncertain`.

Reuse existing snapshots and manifests rather than defining a competing per-surface source ledger:

| Surface | Reused authoritative inputs and results | Genuinely new seam |
|---|---|---|
| Wiki repository pages | `RepoWikiPageManifestEntry` source hashes, content models, native ordering, old/new revisions, rollback sources, drift and dependency checks | accept the prepared snapshot and expected bases instead of rebuilding a new approval boundary |
| Wiki articles and prose | fetched revision metadata, `PlannedArticle`, `GuardedPageEdit`, generation validation, native deploy and rollback manifests | projected fetched-storage overlay, byte-equality gate after real refetch/regeneration, predecessor receipt references |
| Maps | existing input sidecar, checked build helper, deploy target/config selection, native Wrangler invocation and failure handling | complete artifact/input byte manifest, approved build selection, and remote deployment receipt inspection |
| Sheets | existing SQL formatter, `GoogleSheetsPublisher` table detection, native table-aware request construction and owning Google transport | group exact selected tabs into one atomic `spreadsheets.batchUpdate`, retain a complete stable preimage, and reconcile the observed stable workbook receipt |

The combined plan references native evidence and adds only cross-operation selection, digest binding, dependency edges, and execution state. If native evidence already carries a hash or revision, reference it and verify its integrity rather than recalculate it in a second format.

Refactor only the listed seams. In particular, do not call `apply-page-edits` again in a way that silently reads and approves a new live base. Pass its frozen review into `apply_guarded_edits`. Do not add a parallel map publisher, Sheets client, table-resizing implementation, or HTTP mutation path in the coordinating code. Improvements to request preparation and outcome reporting belong in the existing owning publisher and remain available to its standalone command.

### D4. Deterministic dependencies and preparation

Use a stable topological order. For otherwise independent operations use fixed surface/stage rank followed by normalized title, tab, or target. Detect cycles and incompatible reader removals before approval. Explicit prerequisites are:

1. Snapshot selected inputs and remote bases. Run existing preconditions before local build or preparation side effects.
2. Generate selected Lua data locally. Include the shared link catalog and required shards explicitly when they differ. The existing repository manifest and dependency ordering place data before readers, modules before templates, styles before their templates, and maintained content after its dependencies.
3. Capture separately reviewed prose-file bytes once, verify their declared hash, and parse exactly that capture. Recheck the same digest before finalizing preparation. Compute exact projected post-edit text locally. Generate candidate articles using that projected fetched corpus, not the old prose. Traversal uses each selected page's approved stage projection and actual prose/article receipt IDs, including an approved intermediate prose revision before its article successor. Run semantic validation and report exact resulting article bytes.
4. Build selected maps from pinned inputs during local preparation using the existing checked build path. Freeze its deployable output and asset manifest before approval. Deployment must use this same build. A fresh successful build is required, not an assumption from an older build directory.
5. Format selected sheet tabs once and inspect the complete stable workbook, including unselected sheets, named ranges, chips, explicit formatting, charts, groups, and connected-data definitions. Missing regular tables and actual overwrites or deletions of unsupported connected/pivot anchors block preparation. Unrelated objects on the same tab remain supported. Unexposed dynamic-output extents are delegated to Google's atomic validation, not an invented spill rectangle. Freeze exact native structural and typed value-only cell requests as one atomic batch. Detect destructive non-owned full-row shrink and width-growth overlaps before approval. Expose exact request-body bytes and size without silent chunking.
6. Produce a complete offline dry-run report over the projected predecessor states. Where the existing live render sandbox cannot model several not-yet-live dependencies, mark the check provisional and retain the mandatory direct pre-write check. Provisional render coverage is not an unspecified payload. A check failure stops execution and cannot authorize changed text.

Live execution follows these edges:

- Selected data and link catalog deploy before repository readers, prose templates that need them, and generated articles that use them. Verify the deployed catalog digest before articles.
- Reviewed prose edit precedes a real refetch of exactly those pages, then regeneration and validation, then article deploy. Verify refetched text equals the approved projection and its revision equals the edit receipt. Verify regenerated bytes equal the reviewed candidate bytes. Generation differences invalidate approval before article writes.
- Map build precedes canonical deploy, which precedes legacy when both were selected. Revalidate source and artifact hashes immediately before each deploy. Maps deploy alone still uses the existing freshness guard.
- The selected spreadsheet group depends on any selected article/map operations that establish its generated link targets. Existing unchanged external targets are inspected prerequisites, not silently selected deploys. Distinct selected tabs keep their native internal request order inside one atomic batch, avoiding plan-owned cross-tab rebasing that would invalidate a later tab's separately captured base.

After a failed operation, even unrelated ready operations remain blocked until explicit resume. This deliberately prevents the semicolon-chain failure. The coordinator never uses a shell chain whose final exit status hides an earlier failure.

### D5. Approval binds predecessor states without guessing future revisions

Initial live wiki bases are exact revision IDs or explicit absence for creates. Each later write has either that fixed base or an expected predecessor receipt reference plus the approved predecessor content digest. For prose followed by an article, the expected article base is `receipt:<prose-op>:new_revision`, not an invented revision number. Only the exact recorded plan-owned transition may advance the expected base without new approval.

Before the first live mutation, verify all fixed sources and initial live bases. Before each operation, verify its own base, immutable inputs, and predecessor receipts again. Wiki edits check exact current page/revision identity before posting with `nocreate`, then load the acknowledged historical revision and verify its true parent and saved source. Creates retain `createonly` absence protection and saved-source verification. MediaWiki may merge an edit racing the preflight, so edits are not atomic compare-and-set. Dependency pages are checked too. An editor change to a dependency invalidates remaining readers even when the reader itself is unchanged.

Map bases are active deployment/version identifiers for each service obtained through the existing Cloudflare toolchain. The Sheets base is the canonical digest of the complete stable workbook preimage. Sheets has no atomic compare-and-set revision precondition. Inspect that preimage immediately before sending one provider-atomic batch. Approval binds exact mutation requests, owned typed values, selected table identities and final ranges, not invented provider-computed formula postimages. Google owns documented formula and named-range rebasing. Check owned outputs and stable preservation invariants afterward, then retain the complete observed stable workbook postimage as the exact resume receipt.

For APIs without a demonstrated conditional write, review states the possible concurrent-writer race. Do not claim atomic concurrency protection from snapshots. Unreadable base metadata blocks the stage. A mismatched or uncertain response stops execution. A wiki verification failure durably records its acknowledged write before additional evidence I/O. It retains the actual saved revision and actual editor-parent preimage for native recovery, without replacing the separately preserved reviewed preimage. Missing parent evidence remains unresolved. No automatic rollback is attempted.

### D6. Exact dry run

A prepared plan's dry run lists every operation, dependency, local read/write, destination, action, base or receipt reference, source and payload hash, expected owned post-state, and available recovery. Wiki entries include full text diffs, drift decisions, generated-root preservation warnings, and render findings. Sheets entries include the complete stable workbook preimage, selected typed rows, exact atomic request body and its byte size, structural effects, and the provider-managed reference-rebasing proof boundary. Map entries include service identities, the complete artifact manifest, database route digest, and deployment/configuration actions.

The human-readable report may point to complete sidecars rather than flood the terminal, but never replaces payload review with row counts or command names. No hidden broad selection is permitted. A later dry run that sees changed live bases fails and labels the plan invalid. A live apply cannot silently refresh that preview and continue under the old approval.

### D7. Partial success, resume, and rollback

Persist intent, operation ID, exact payload hash, base, and manifest location before each mutation. Native wiki planned text, rollback preimages and replaced manifests are fsynced with their containing directories before provider mutation. Completed native manifests are durably checkpointed before success receipts. Keep native partial results when an owning operation reports them. Do not claim cross-service atomicity.

Selected Sheets tabs for one spreadsheet are one atomic provider operation, not fictional per-tab successes. The native publisher translates RAW scalars into typed value-only cell requests and retains each tab's structural request order. Google's documented batch validation and ordered atomic application replace resize-then-values partial-write handling. The same builder serves standalone one-tab calls, so standalone multi-tab failure collection remains unchanged. The owning transport timeout covers Google's documented processing window. Unknown or lost responses remain uncertain and are not retried.

An exception, nonzero child exit, interrupt, guard finding, or partial operation marks the run failed. Unknown remote outcomes become `uncertain`, never success or an automatic retry. Status reports historical known writes, native manifests, blocked work, uncertain outcomes, and permissible recovery. It does not silently claim that every completed remote destination is still unchanged.

Resume is explicit and uses the same approval only while pinned inputs and remaining bases still match. Reconcile completed entries against their provider receipts and exact expected current content. Skip verified successes. Resume a partially completed wiki operation through its recorded native per-page results, never by blindly rerunning its entire command. Canonical success plus legacy failure resumes legacy alone against the same approved artifact. A completed-but-unacknowledged write can be adopted only when provider evidence uniquely ties it to the recorded operation. Otherwise remain uncertain and require operator reconciliation followed by a new plan if necessary.

No automatic rollback is attempted. Show existing `wiki rollback-repo-pages --manifest ...` commands for known wiki writes, preserving revision guards and the newly-created-page deletion limitation. Rolling back a run is a distinct reviewed action and invalidates resume of its old continuation. For maps record previous deployment IDs and the existing provider recovery route. For Sheets retain the full stable preimage, exact atomic body, acknowledgement or uncertain outcome, and observed postimage. Do not promise a transactional restore command that does not exist. Restoration is separately reviewed through the owning provider. A plan must expose these limits before approval.

### D8. Migration and neighboring changes

Standalone wiki, maps, and sheets commands remain supported. Replace only documented operator multi-command publish chains with this opt-in prepared workflow after its contract tests pass. Remove temporary coordination scripts introduced for this feature. Do not change existing OpenSpec plans.

`unify-item-provenance` supplies future shared source inputs. `convert-item-pages-to-data` consumes them and retains its own conversion and Lua-limit gates. Ordered publishing neither implements nor blocks on these changes. It hashes whichever actual input/output contracts are in use and can carry their explicit selected page sets without taking over conversion policy.

### D9. Minimum coherent landing units

Land internal plan types and pure dependency/digest tests first, then wiki prepared-input seams and maps evidence extensions as independent changes to their existing owners. These units add no incomplete public publishing command.

The first usable orchestration unit combines the fixed executor, approval, status/resume, and complete wiki/maps preparation paths. It can improve the observed catalog and stale-build ordering failures without waiting for exact Sheets request preparation. Until the Sheets extension lands, selection that contains Sheets must fail explicitly before preparation or mutation. Do not skip Sheets, fall back to its count-only preview, or claim this change's full acceptance is complete.

The next unit adds exact Sheets preparation inside the existing publisher and connects one atomic selected-spreadsheet operation to the same fixed executor. It includes cross-surface link dependencies and failure/resume coverage. Documentation for each usable unit states its supported surfaces, and the final migration and acceptance unit covers every surface and scenario. All units remain part of this change. Its scope and archive gate are unchanged.

## Risks / Trade-offs

- No distributed transaction exists. Fail-fast coordination and honest receipts reduce exposure, but remote recovery remains surface-specific.
- Preparing exact projected articles requires a narrow storage overlay and a reproducibility comparison after real prose edits. Skipping that comparison would make the single approval meaningless.
- Existing freshness sidecars are not complete artifact manifests. The plan additionally binds bytes without weakening the native guards.
- Base snapshots cannot create atomic compare-and-set support on APIs that lack it. Reports must distinguish native revision guards from best-effort concurrent-writer detection.
- Complete row/structural snapshots and map asset manifests cost storage. Keep them variant-local with the run until recovery is no longer needed. Never include credentials.

## Implementation evidence

Google's [Sheet schema](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/sheets#Sheet) exposes regular tables through `Sheet.tables`. Its [Table schema](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/sheets#Table) supplies the table ID, range, and column metadata. The publisher captures its existing supported `updateTable`, dimension, and RAW value requests for review. It does not use the nonexistent `Sheet.dataSourceTables` field or an `updateDataSourceTable` request.

The prepared Sheets snapshot retains all returned stable workbook and cell content, including chip identities. It excludes documented calculated cell values/formats, scoped execution status, scheduled next-run data, filtered-row visibility, and threaded comments. Exact owned outputs, table ranges/settings, retained cell content and explicit dimensions are postflight invariants. Non-owned formula text, pivot source ranges and reference-bearing metadata remain provider-managed effects, not locally predicted semantics. The complete observed stable workbook is retained for later exact reconciliation.

The worker tool inventory did not expose `xd://lsp`. Exported seams were searched across source, tests, and new untracked files. The integration owner receives exact worktree paths and symbols for language-server reference checks before integration.

Google documents ordered, validated atomic application for [`spreadsheets.batchUpdate`](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate). [`UpdateCells`](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/request#UpdateCellsRequest) uses `start`, not an oversized range, so omitted ragged cells are not cleared. A `userEnteredValue` field mask preserves notes and formatting while explicit typed values retain RAW semantics. The [API limits](https://developers.google.com/workspace/sheets/api/limits) describe the recommended request size and processing deadline. No unsupported retry/chunking settings or formula parser are presented as controls.

The atomic spreadsheet boundary replaces the proposed per-tab operations because a selected tab's row changes can rebase formulas on another tab. A locally predicted formula postimage was both unnecessary and unsound. The review boundary is the exact native batch plus stable preimage and owned postconditions. It is not an assertion that arbitrary observed formulas prove their own correctness.

The running MediaWiki accepted a stale-base edit by merging an intervening editor paragraph. Read-only inspection of its `ApiEditPage` parameter declarations and `EditPage` conflict path confirmed there is no disable-merge parameter. The response's `oldrevid` is captured before the save attempt and cannot establish the merged parent. The [native edit API](https://www.mediawiki.org/wiki/API:Edit) exposes base revisions, timestamps and create controls, not strict edit compare-and-set. The approved boundary is checked native edits with actual historical parent/source verification, durable mismatch receipts and separately reviewed recovery.

### Verification record

The isolated implementation exercised actual CLI help for the command group and all four commands. Fresh preparation captured the approved two-page local wiki edit, built and froze both selected map targets, and prepared one atomic items/spells spreadsheet batch. Native dry-run apply returned valid with no conflicts, approval, execution journal or publication writes. Its readable summary links complete payloads and exact wire-body bytes. Complete prepare, dry-run and help transcripts were retained. No game was launched.

The final integrated CI run passed dependency-state checks, all static checks, 2,863 Python unit tests, 197 maps tests, 20 fixture-backed Playwright cases, 39 native contract tests and 610 mod tests. Python contracts passed 90 of 91 cases. The sole failure was the tracked-document-path gate, because this worker cannot stage the new publication source. The integration owner must stage the complete unit before its final full suite.

The first CI run exposed a real dependency-state race: locked pnpm installation replaced packages while map consumers were starting. A separate integration patch now completes dependency-state before parallel consumers and blocks them on dependency failure. Regression tests cover both aggregate tasks, consumer concurrency, original failure reports, unchanged standalone maps behavior, foreign-checkout `node_modules` refusal, and global-store acceptance. No native-library signature bypass was used.

The pnpm guard uses native effective workspace configuration, including YAML and environment settings, and native importer discovery. Matched pnpm source resolves configured relative virtual stores against `lockfileDir`. Global mode defaults to `storeDir/links` only without an explicit virtual-store setting. The internal `.pnpm`, private hoisted `node_modules`, and bin destinations are checked separately. The relevant owners are [`readProjectsContext`](https://raw.githubusercontent.com/pnpm/pnpm/v10.34.0/pkg-manager/read-projects-context/src/index.ts), [`getContext`](https://raw.githubusercontent.com/pnpm/pnpm/v10.34.0/pkg-manager/get-context/src/index.ts), and [`extendInstallOptions`](https://raw.githubusercontent.com/pnpm/pnpm/v10.34.0/pkg-manager/core/src/install/extendInstallOptions.ts).

Regression cases cover stage boundaries, exact requests, lost responses, tampering, stale inputs, editor conflicts, captured-byte prose parsing, path-only relocation, projected receipt transitions, bounded proofs, complete workbook snapshots and provider-atomic Sheets grouping. Final native rereview found no remaining issues after transport acknowledgement retention, MediaWiki-specific normalization, attempted-request attribution, unknown rollback replay refusal and durable resumable image recovery were covered. The change remains unarchived pending the complete acceptance matrix, including forced failures at every stage boundary and native rollback compatibility. No production publication occurred. Retired fixture approvals do not approve a re-prepared plan.

Approved disposable execution wrote the two reviewed local wiki revisions and activated the canonical fixture. Postflight then stopped on Cloudflare 1010 because its public database GET used urllib's default browser signature. An explicit honest application User-Agent fixed the owning native read without changing authentication, WAF settings, Worker bytes or mutation transport. The actual database digest matched the selected database and the acknowledged version remained unchanged across inspection. Cloudflare documents this as [browser-signature blocking](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/). The original journal remains aborted with its actual receipts. Further publication uses a separately reviewed continuation and never replays the completed wiki edits.

Main integration passed dependency-state, static checks, 2,933 Python unit tests, 93 Python contracts, 39 native contracts and 610 mod tests. The map browser prerequisite required installing the locked Chromium revision. A subsequent browser run exposed a separate fixture-isolation defect. Every worktree uses the same readiness port, so another worktree's fixture can answer while the selected fixture is still building. Its foreign source UI and later connection refusal invalidate that run. Map acceptance requires an exclusively owned server until per-run endpoint isolation is implemented.

The exclusive Main map run passed lint, Svelte checks, all 197 Vitest cases and all 20 browser cases. No test expectation changed. This supplies the remaining CI leaf after the Chromium prerequisite repair. The shared-port defect remains recorded rather than treated as a passing concurrent-worktree guarantee.

The separately approved continuation used digest `sha256:9362c84570b5829a75ddbaf61b5519a1afa2aaf4ed0170adcfbc08e5af9d6b2d`. Both disposable map deployments succeeded and served the exact selected database digest. The spreadsheet account's Viewer role then rejected the one atomic batch with HTTP 403. The durable journal classified the rejection as safe to resume. After the operator restored Editor and separately approved resume, fresh dry-run inspection returned no conflicts. Resume verified and skipped both completed map operations, then applied the original spreadsheet body once. The journal contains exactly two map write attempts and one acknowledged spreadsheet success.

The 24,577,095-byte batch populated 7,264 item rows and 349 spell rows. Actual postflight retained the real file chip's identity, all 16 non-owned cells, and both table identities. Google's named range below the items table moved from row index 11 to 7,271. The complete observed stable workbook snapshot contains 523,146 nonempty cells and remains with the native receipt. Relay browser inspection showed the populated item table, retained chip and notes, deployed world map and Island Tomb zone map. The provider's structured-reference parse error remains a fixture limitation, not a claimed rebasing success.

Approved cleanup deleted both exact disposable Workers through Wrangler, moved only the test workbook to trash through its owner's browser UI, and deleted the two local user pages through the native client. Local page identity, bot ownership and latest revisions were checked before each deletion. Readback found both pages absent after two present preimages. The original journals, hashes, native receipts and operational proof remain retained. No production destination, account scope or unrelated resource changed.

### Real-provider feasibility

Approved fixture bootstrap created two temporary metadata-only Workers, an operator-owned restricted spreadsheet shared with the existing service account, and two local user pages. Native readback verified their exact identities. The Sheets-scoped account read the real file chip's URI and type. A separately approved same-title chip-to-plain-text editor change left `userEnteredValue` equal but made preflight refuse the changed stable snapshot with zero publication writes. The operator restored the chip before final preparation.

The complete native Sheets body remains one batch without chunking or retry. Its structured-reference fixture produced a provider formula parse error, which is a limitation rather than evidence of successful rebasing. Drive API access was unavailable and was not enabled. The approved real-provider execution and resource cleanup are recorded above. Any new publication requires its own exact dry run and explicit human approval.
