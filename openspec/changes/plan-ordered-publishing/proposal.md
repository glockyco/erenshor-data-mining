# Proposal

## Why

The guarded publishing commands protect individual operations, but an operator's shell chain can publish later surfaces after an earlier command fails. A selected-surface plan must make ordering, reviewed writes, approval invalidation, and partial recovery explicit without replacing those commands.

## What Changes

- Add an opt-in `erenshor publish` command group that prepares one immutable plan for explicitly selected wiki pages, map targets, or sheet tabs. There is no all-surfaces default.
- Materialize exact payloads and local preparation writes before approval. Record source hashes, live bases, deterministic dependencies, existing guards, and recovery limits.
- Publish wiki data and the shared semantic-link catalog before their readers. Apply only separately reviewed prose replacements, then refetch and regenerate affected articles before their deploy.
- Require a fresh maps build for selected inputs and bind deployment to its artifact digest. Preserve unchanged database bytes at the existing database URL on both map hosts.
- Apply one explicit human approval to one plan digest. Refuse changed inputs, unrelated live revisions, or unreviewed writes rather than silently replanning.
- Stop the plan after the first failed operation. Record partial success and resume only through an explicit command that reconciles existing manifests and remote receipts.
- Reuse wiki deploy and rollback services, maps build/deploy, and the sheet formatter/table-aware publisher. Add narrowly scoped plan inputs and receipts where their current interfaces cannot enforce approved payloads.

## Capabilities

### New Capabilities

- `ordered-publishing`: Explicit selected-surface publish plans, immutable approval, dependency execution, and partial recovery across existing wiki, maps, and sheets operations.

### Modified Capabilities

None. The new orchestration contract composes existing command-failure and map database contracts. Existing command behavior stays available, including standalone multi-tab Sheets failure collection.

## Impact

Implementation will add a Typer group and application-level planning and coordination beside existing commands. Narrow additions will expose prepared wiki edits, generated corpus inputs, frozen sheet rows, remote snapshots, and deployment receipts without another HTTP write implementation. Existing manifests remain authoritative for wiki rollback.

The migration boundary is operator-authored multi-command publish chains, not the underlying pipeline or existing OpenSpec changes. This change does not implement wiki data-backed conversion, change article ownership, deploy anything, publish mods, approve its own writes, or make distributed publishing transactional. People's prose stays outside repository tracking and requires its own reviewed edit file before inclusion.
