# Proposal

## Why

Zone infoboxes still copy facts into articles, while their current refresh deliberately preserves every non-title field. Converting them needs a clear boundary between shared zone facts and editors' level guidance, pictures, map labels and route notes so an update can refresh data without erasing useful information.

## What Changes

- Introduce `Template:ZoneData` and `Module:Erenshor/ZoneData` to replace the existing zone infobox only. Keep legacy `Zone` and `MapLink` compatible, parameter-only and free of Lua.
- Reuse the common `zones.zone_type`, actual-copy combat-eligible level summaries and usable directed connection producer from the overview slice. Reuse its immutable `Data/Zones` module when complete. Add only the narrow page-membership/map-presentation relation needed by grouped zone pages.
- Preserve exact editor image, caption and unresolved level, classification, map and connection content. Require reviewed dispositions for conflicting classifications and ambiguous level values instead of silently converting them into facts or recommendations.
- Keep one infobox on a page shared by several scenes. Show scene-specific summaries and map links without averaging medians or selecting only the first map.
- Extend the existing native guarded conversion, production comparison, limit and rollback machinery with a zone policy. Do not build a separate HTTP writer or migration engine.
- After approved full conversion and rollback acceptance, generate compact zone stubs and reconcile membership only. Remove zone-specific legacy article generation, not shared code still needed by other types.

Goals are data-only factual refreshes, complete preservation and a reviewed cutover. This change does not replace hand-written rosters, add overview/view tables, convert other entity types, redesign the map, change database publication or companion URLs, or authorize implementation or live writes.

## Capabilities

### New Capabilities

- `data-backed-zones`: Zone infobox rendering, editor ownership, scene grouping, map and route semantics, and guarded conversion acceptance.

### Modified Capabilities

- `wiki-article-refresh`: Scope legacy zone merging to unconverted pages and require membership-only reconciliation after cutover.
- `wiki-publishing`: Permit a grouped zone infobox to represent its declared scene identities without duplicating infoboxes.

## Impact

The implementation will touch zone serialization and generation orchestration, the new zone renderer/template and documentation, narrow page relations, semantic validation and the existing guarded migration interfaces. The overview slice owns the shared selectors and `zone_type` producer. Editors keep article prose, tables, notes, pictures and captions. Repository code owns renderers and templates, and generation owns data modules.

Conversion follows item integration and the shared zone overview producer. No live module changes structure in place. New data and readers publish before a separately approved canary, demonstrated rollback and separately approved broad conversion. Full production text parses, measured limits and local browser screenshots are gates, not inferred from fixture success.

The `wiki-publishing` delta modifies the requirements currently introduced by `adopt-data-backed-wiki`. Apply or archive that parent spec before this delta is synced or archived. Reconcile its type-specific ownership wording with the item and other conversion deltas rather than replacing their newer contracts.
