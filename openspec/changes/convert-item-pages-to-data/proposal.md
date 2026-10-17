# Proposal

## Why

Item pages still copy game facts and repeated explanatory text into article parameters while the wiki already publishes item data. Converting items first makes updates data-only and gives editorial additions an explicit home without allowing article parameters to override exported facts.

## What Changes

- Add `Template:ItemData` and an item renderer that resolve one stable item identity from versioned Lua data.
- Render identity, stats, qualities, effects, provenance, images, item database index and lifecycle notices from data, with shared wording in repository-owned templates/modules.
- Keep `type`, `questsource`, `relatedquest` and `othersource` as explicit additive editor-owned fields. Preserve edits and prose through a guarded conversion.
- Measure real page-size, Lua memory/CPU and parser limits using generated data and the heaviest pages before rollout.
- Preserve quality tooltips, hover extraction, effect details and layout in the actual wiki host.
- Convert all selected item roots with fetched-revision guards, full parse comparison, canaries and rollback manifests. Remove item-specific full-article generation only after coverage and rollback gates pass.

## Capabilities

### New Capabilities

- `data-backed-items`: Compact identity-based item article calls with data-owned facts, additive editorial fields, complete rendered details and guarded conversion.

### Modified Capabilities

None. This change implements the item slice of the existing wiki-publishing target without weakening its publication or lifecycle requirements.

## Impact

Item Lua generation and versioned shards, maintained item modules/templates, migration/reconciliation and validation, item article generation, field preservation rules, local wiki fixtures and browser tests, hover consumers, and the contributor data guide are affected. Legacy `Template:Item` remains parameter-only and compatible for hand-written uses. No Lua switch is added to it.

## Goals and Non-Goals

Items are the first entity conversion in this change. Other entity types and the shared merge engine stay until their own conversions complete. This does not add Cargo, a generic Lua query engine, repository-owned article copies or a direct repository-to-wiki synchronization connection. Existing guarded CLI publication remains the only publication route.

## Dependencies and Migration Boundary

`unify-item-provenance` must complete its cross-output coverage gate first. The governing `adopt-data-backed-wiki` design remains unchanged by this proposal. `publish-wiki-data-views` owns list views, which must keep working against their documented schemas. The persistent guide session owns guide gating integration and releases are outside this scope. Conversion cannot mask incomplete guide provenance or ship a separate wiki source selector.

No production write is approved by this design. Each publication pass requires a complete dry run and separate explicit approval. Local rendered screenshots must be reviewed before live template or article deployment.
