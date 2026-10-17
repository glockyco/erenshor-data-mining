# Tasks

## 1. feat(publish) add explicit immutable publication plans

- [ ] 1.1 Add internal typed selection and operation models for the closed set of existing publish operations. Do not expose incomplete CLI commands, plugin registration, arbitrary commands, or user-authored workflow graphs.
- [ ] 1.2 Implement the fixed selection schema with exact wiki titles and opt-ins, reviewed prose-file declaration, map targets, and sheet tabs. Reject empty selection, unknown fields, unsupported destinations, duplicate ownership, and missing explicit dependencies.
- [ ] 1.3 Add versioned canonical plan serialization, relative content-addressed payloads, source and destination identity binding, full input hashes, expected base/receipt references, a digest excluding mutable receipts, and variant-local run storage without secrets or tracked editor text.
- [ ] 1.4 Implement stable topological ordering using existing repository dependency information and fixed tie breakers. Retain explicit dependency reasons, reject cycles, and never silently expand live selection.
- [ ] 1.5 Cover schema rejection, maps-only selection, deterministic ordering/digest, destination or source changes, and payload tampering with pure unit tests. Keep approval/execution CLI coverage in the usable orchestration unit.

## 2. feat(wiki) prepare guarded payloads for ordered publication

- [ ] 2.1 Extract narrow prepared-input seams from existing generate, generate-lua, deploy-repo-pages, deploy, and apply-page-edits handlers. Reuse current application services, manifests, snapshots, render checks, account assertions, drift checks, and atomic revision guards. Add no second HTTP writer.
- [ ] 2.2 Reference native source hashes, fetched/live revisions, dependency snapshots, and rollback manifests in the plan rather than adding a competing wiki evidence format. Freeze generated data, exact catalog/shards, repository source text, summaries, content models, and accepted drift. Report required unselected dependencies before approval.
- [ ] 2.3 Prepare separately reviewed prose replacements with existing exact-match rules. Add an isolated fetched-storage overlay to generate and validate the exact projected article corpus without editing live pages or tracked sources.
- [ ] 2.4 Execute prose edits using frozen `GuardedPageEdit` objects, refetch the returned revisions, regenerate affected articles, and compare every byte with the approved projection before article deployment. Resolve future base revisions only from matching predecessor receipts.
- [ ] 2.5 Model data/catalog-before-reader edges, preserve native repository ordering, and expose provisional sandbox coverage without disabling mandatory direct pre-write checks. Keep conversion policy owned by the relevant wiki changes.
- [ ] 2.6 Add tests for stale catalog with and without explicit data selection, dependency changes, editor revision invalidation, prose-before-generation sequencing, projection mismatch, missing separate prose review, preserved prose, and native rollback sidecars after a partial write.

## 3. feat(maps) expose reviewed build evidence through existing operations

- [ ] 3.1 Adapt the existing maps checked build path to prepare from pinned inputs and freeze the deployable output. Keep its freshness sidecar and additionally hash complete assets, tile bytes, image inputs, both service configs, lockfile, and selected database bytes.
- [ ] 3.2 Inspect current Cloudflare service deployment/version identifiers through the existing toolchain. Record explicit target and base receipts, canonical-before-legacy edges, complete artifact manifests, and the provider's actual concurrency guard strength.
- [ ] 3.3 Retain the prerendered database route and verify its built body equals selected clean database bytes at the existing URL for both selected hosts. Do not replace it with a static symlink or remove database distribution.
- [ ] 3.4 Add tests for same-size tile-byte changes, stale source after build, modified output with unchanged sidecar, canonical success/legacy failure, unchanged database route bytes, and uncertain provider outcomes. Keep build/deploy helpers owned by maps and add no parallel publisher.

## 4. feat(publish) land complete wiki and maps orchestration

- [ ] 4.1 Register usable `prepare`, `apply`, `status`, and `resume` commands with root variant/dry-run behavior and declared preconditions. Implement complete wiki/maps dry-run inspection with payload sidecars, all writes, bases or receipt references, render findings, account assertions, and recovery limits. Explicitly reject selections containing Sheets before any preparation or mutation until group 5 lands.
- [ ] 4.2 Require one explicit human approval declaration matching the immutable digest for live apply/resume. Revalidate all initial bases before first mutation and relevant fixed inputs and predecessor receipts before each operation. No agent-generated approval or silent replan is allowed.
- [ ] 4.3 Add a local run lock and durable intent/receipt journal. Invoke existing operations through checked calls or argument vectors, stop all plan progression on the first failure or partial result, and preserve the original error and native manifest.
- [ ] 4.4 Implement read-only status and explicit resume reconciliation. Skip verified successes, narrow partial wiki continuation from native per-page results, resume legacy alone after canonical success, and keep unacknowledged outcomes uncertain until uniquely reconciled.
- [ ] 4.5 Expose existing guarded wiki rollback commands and new-page deletion limits. Record provider-specific map recovery identifiers. Update existing guidance for the supported wiki/maps workflow and state that Sheets selection is not supported yet. Never claim full change completion or offer a universal restore operation.
- [ ] 4.6 Verify this usable unit through CLI help and end-to-end tests for missing approval, precondition failure, the observed failed-shell-chain order, stale catalog stopping later maps, stale map build after successful article work, interrupts, lost receipts, dependency edits before resume, changed completed writes, and rollback invalidating continuation.

## 5. feat(sheets) connect exact existing table operations to publishing

- [ ] 5.1 Split current Sheets table-aware publication only at preparation/execution seams inside its existing publisher. Freeze formatter output and expose exact existing RAW value and structural requests, table IDs, metadata, affected cells, surrounding shifted rows, preimages, and post-state expectations. Add no parallel Sheets client or table-resizing implementation.
- [ ] 5.2 Inspect required live tables and capture canonical synthetic base snapshots without claiming nonexistent atomic revisions. Execute frozen requests through the same publisher, record per-request outcomes, and retain standalone batch behavior.
- [ ] 5.3 Enable explicit Sheets selections in the fixed executor as one tab per operation. Bind cross-surface link dependencies, approval, fail-fast behavior, status, and recovery evidence using the same plan/journal contract. Do not add a second execution engine.
- [ ] 5.4 Add tests for missing tables, exact row/type preservation, table growth/shrink effects, changed snapshots, uncertain results, first-tab failure blocking later tabs, partial structural writes, and stale catalog blocking later Sheets/maps. Update existing Sheets guidance for exact review and recovery limits.

## 6. docs(publish) migrate operator workflow and verify full acceptance

- [ ] 6.1 Update existing publishing guidance and relevant CLI/wiki/maps/sheets skills in place to explain all selected surfaces, separate prose review, exact dry-run review, one digest-bound approval, guarded partial recovery, and provider concurrency limits. Point to command/schema declarations rather than duplicating option inventories.
- [ ] 6.2 Replace documented multi-command publishing shell chains with the prepared workflow. Keep standalone commands and existing OpenSpec plans unchanged. Remove any feature-only temporary scripts or obsolete duplicate preparation paths.
- [ ] 6.3 Run CLI help checks and all new unit/contract tests, existing wiki deployment tests, maps provenance tests, and Sheets formatter/publisher tests once after integration. Run `uv run erenshor test ci` before publication as required by repository configuration.
- [ ] 6.4 Exercise the complete prepared-plan workflow in disposable wiki/Sheets/Cloudflare fixtures or isolated test destinations. Force a failure at every stage boundary and confirm exact writes, stop behavior, durable receipts, resume narrowing, and native rollback compatibility. No production write is authorized by this planning change.
- [ ] 6.5 In a browser inspect the built selected map, a zone page, and the unchanged database endpoint using the existing fixture-backed smoke contract. Verify rendered wiki changes through local MediaWiki. Any later production writes require a separate reviewed dry run and explicit user approval.
- [ ] 6.6 Run strict validation of this change and retain the operational failure cases as regression evidence in its change record. Confirm every surface and acceptance scenario is implemented before archive. The earlier wiki/maps unit does not narrow this change's completion gate.
