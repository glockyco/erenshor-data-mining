# Tasks

These tasks describe future implementation. This design-only assignment performs none of them.

## 1. test(wiki): Define the item conversion contract

- [ ] 1.1 Complete `unify-item-provenance` coverage and reconcile guide gating through the persistent guide owner before conversion implementation relies on its schema. Confirm views and semantic links retain their existing readers.
- [ ] 1.2 Inventory every current item identity, page, legacy root and companion from current clean data and fetched live pages. Include all multi-root pages and unmatched roots. Do not use an estimated page count as acceptance.
- [ ] 1.3 Inventory every item field and companion detail actually rendered today against Lua data. Add fixtures for omitted fields including item database index, approved renders, quality/effect behavior and lifecycle.
- [ ] 1.4 Add conversion tests for all four editor fields, existing merged values, differing link syntax, nested notes, preserved prose/companions, unkeyed/ambiguous roots, multiple identities, revision conflicts and interrupted/rollback manifests.

## 2. feat(wiki): Render complete identity-based items

- [ ] 2.1 Generate `Data/ItemsV2` and versioned shards with canonical provenance IDs and full item details. Keep live data module structures unchanged and document schemas for editor-written readers.
- [ ] 2.2 Add `Template:ItemData`, its stylesheet and `Module:Erenshor/ItemData` with explicit `render(frame)` and missing-identity diagnostics. Centralize labels and mechanic wording in repository renderers rather than Python or articles.
- [ ] 2.3 Implement the exact additive owned-field allowlist, unsupported-parameter and covered-note tracking, `ItemData/SourceNote`, and category explanations. Never permit factual overrides.
- [ ] 2.4 Reuse/refactor details formatting while keeping legacy parameter entry points compatible. Preserve all quality, hover and effect-details DOM selectors and multi-root card identity. Add no right-click-for-details behavior.
- [ ] 2.5 Extend Lua testcases, item module tests, canonical rendered-source coverage and browser hover/layout tests. Update the existing data guide and its owned-field contract test, template documentation and tracking-category instructions in place.
- [ ] 2.6 Measure generated production-scale bytes and actual host Lua/parser limits on the heaviest source, effect, quality, multi-root and many-link corpus. Record cold/repeated parses and unavailable metrics honestly. Reshard until every enforcing limit has at least 25 percent headroom without dropping facts.
- [ ] 2.7 Run narrow tests once after implementation, then `uv run erenshor test ci`. Import only approved local candidates through the established wiki workflow, inspect actual browser behavior and capture screenshots for review. Local service writes require their own dry-run/approval boundary.

## 3. feat(wiki): Convert items through guarded identity edits

- [ ] 3.1 Extend existing guarded article services and semantic validation to migrate one compact call per item identity, preserving exact editor fields and prose and removing only proven owned companions. Keep all unresolved pages blocking until reviewed.
- [ ] 3.2 Add compact new-item stub generation and membership-only reconciliation for converted pages. Demonstrate a fact-only data update changes the render with no article write.
- [ ] 3.3 Build complete text-parse comparison reports for every production item page, not only selected canaries. Include identity/fact coverage, preserved editorial values, links/categories, images, all details and measured limits.
- [ ] 3.4 Run and review the complete repository-page dry run. Obtain approval for the first pass of new versioned data and reader/template dependencies. Publish in dependency order without changing legacy article text.
- [ ] 3.5 Finish production dependency and full-data limit checks once new dependencies exist. Run a separate guarded canary article dry run, obtain approval, publish and verify canaries. Exercise manifest rollback and then separately approve any canary reapplication.
- [ ] 3.6 Fetch fresh revisions, run the full item conversion dry run, review every parse difference and obtain explicit broad-conversion approval. Preserve planned base revisions/rollback text before the first write and record each successful write. Stop on conflicts or failures and resolve partial runs before another pass.
- [ ] 3.7 Verify every item identity/page has a disposition, canonical provenance coverage is complete, browser hover/details behavior is preserved and data-only refresh does not rewrite articles. Record evidence in this change, not permanent documentation.

## 4. refactor(wiki): Remove obsolete item article generation after the gate

- [ ] 4.1 Search every item generator, companion, formatter and preservation-rule caller. After complete conversion and usable rollback manifests, delete item-specific full-article assembly, section generation, `item.jinja2`, Item-only merge branches and unreferenced scaffolding. Keep other entity generators and shared merge code.
- [ ] 4.2 Keep legacy `Template:Item` parameter-only and compatible for remaining hand-written uses. Retain shared tooltip APIs and every dependency needed by the rollback window.
- [ ] 4.3 Keep manifest rollback operational without rebuilding legacy articles. Demonstrate its conflict protection and matching data dependency retention. Run final changed-path checks and CI once for this cleanup unit.
- [ ] 4.4 Update existing operating documentation to the compact stub/data-only workflow. After the rollback window is explicitly closed, produce the administrator-only obsolete-page deletion list with no-live-reader checks and seek separate dry-run review/approval for any live cleanup.
