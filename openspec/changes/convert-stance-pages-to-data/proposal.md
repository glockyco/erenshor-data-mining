# Proposal

## Why

Stance infoboxes still copy game facts into article parameters even though live data already carries those facts. Convert them after items so game updates change data rather than repeatedly editing articles.

## What Changes

- Add `Template:StanceData` under a new name. Keep `Template:Stance` compatible and parameter-only.
- Reuse the live `Data/Stances` schema. Add a narrow Python-built stance relation module for activating skills and a separate lifecycle supplement rather than cloning the entity schema.
- Preserve `imagecaption` and every byte of editor prose. Reject factual overrides with a tracking category instead of applying them.
- Convert all eligible stable-key roots, including the recorded historical stance, using the shared guarded conversion, comparison and rollback machinery established for items.
- Preserve stance tooltip and semantic hover identities. Remove the existing Lua reverse scan of skills in favor of generated relations.
- After verified conversion, create compact new stubs and reconcile membership only. Remove stance-specific full-article generation after the rollback acceptance window.

## Capabilities

### New Capabilities

- `data-backed-stances`: Stable-key stance articles with preserved editorial presentation, generated activation relations, compatible tooltips and guarded conversion.

### Modified Capabilities

None. Legacy refresh requirements continue to apply to legacy roots. Existing lifecycle dispositions and write guards remain in force.

## Impact

Changes stance Lua generation and its composition, the stance renderer and tooltip resolver, local Scribunto fixtures and smoke coverage, and the stance branch of entity article generation. The parent conversion owner supplies shared neutral conversion primitives. This change does not create a type-specific writer, select item provenance, change live module structure, or alter other entity conversions. Planning alone authorizes no live writes.
