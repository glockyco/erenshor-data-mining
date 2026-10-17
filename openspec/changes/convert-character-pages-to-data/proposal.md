# Proposal

## Why

Character articles still copy generated facts into article parameters, and their live infobox hides stats the pipeline already exports. Moving the facts into bounded data modules lets updates leave editor text alone while correcting the missing stats, spawn conditions and character identity handling.

## What Changes

- Introduce `Template:CharData` and `Module:Erenshor/CharData` with stable-key character records, concise complete stat presentation, canonical loot relations, conditional spawns, galleries and categories.
- Publish a new sharded character data contract without changing any live data module structure. Reuse existing complete treasure, link and item-relation modules.
- Preserve image captions, landmark descriptions, editor location fallback values and every byte outside proven generated regions. Keep authored dedicated SimPlayer pages outside ordinary NPC conversion and never regenerate random SimPlayer pages.
- Add evidence-bound coordinate-key movement reconciliation using raw GUID/native scene identity, explicit dedup membership lineage and fail-closed unknown cases. Do not use names, nearest locations or fabricated aliases as identity proof.
- Reuse the item conversion's native guarded edits, comparison, limit reports, ownership checkpoints and rollback manifests. After complete acceptance, replace Character full-article generation with compact stubs and membership-only reconciliation.
- Remove obsolete shared merge, Jinja and full-article refresh machinery only when every type cutover has passed its own acceptance and rollback gates. Legacy parameter templates and guarded publishing stay.

## Capabilities

### New Capabilities

- `wiki-character-data`: Stable-key data-backed character rendering, bounded data loading, editorial ownership and evidence-bound identity reconciliation.

### Modified Capabilities

- `wiki-article-refresh`: Converted Character pages use compact stubs and identity reconciliation rather than copied-fact merging. Unconverted types retain existing refresh behavior until their own cutovers.

## Impact

The implementation touches the Character repository projection and domain fields, the existing NPC level/stat and spawn projections, wiki Lua generation, new renderer/templates/styles, native conversion planning and corpus checks, and existing editor guidance. CanonicalSources supplies item relations and conditions. WikiOverviews supplies common spawn/combat eligibility and zone facts, not a second selector.

The migration boundary is a separately approved repository-page publication followed by full production comparisons, a guarded canary with exercised rollback, and a fresh broad conversion approval. This proposal authorizes planning only. It does not implement code, write the wiki, change databases, launch the game or publish a release.
