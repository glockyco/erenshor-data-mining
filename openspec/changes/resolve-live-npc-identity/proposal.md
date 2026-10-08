# Proposal

## Why

Issue [#290](https://github.com/glockyco/erenshor-data-mining/issues/290) asks the live map to show the actual NPC character's loot rather than merge same-named candidates; today's popup resolves only the transmitted name and scene and aggregates those candidates (`src/maps/src/lib/components/map/popups/LiveNpcPopupContent.svelte:17-33`, `src/maps/src/lib/map/character-details.ts:64-71`). The architectural gap is missing runtime provenance, not missing loot: export keys encode original object names and scene placements, but `NPC.Start` overwrites the live object name (`src/Assets/Editor/StableKeyGenerator.cs:155-183`, `variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/NPC.cs:462-467`).

## What Changes

- Capture an NPC's original prefab name, or scene object name plus scene and starting placement, in a companion-owned Harmony prefix on `NPC.Start`. Adapt Adventure Guide's existing technique without depending on its installation (`src/mods/AdventureGuide/src/Navigation/NpcOrigins.cs:30-78`, `src/mods/AdventureGuide/src/Patches/NpcStartPatch.cs:15-29`).
- Add an optional, discriminated `characterOrigin` entity field and declare protocol `0.3.0`. Preserve the required fields and warn-and-continue negotiation; field presence, not a new capability, enables identity resolution (current contract: `src/mods/InteractiveMapCompanion/src/Entities/EntityData.cs:8-39`, `src/mods/InteractiveMapCompanion/src/Protocol/ProtocolVersion.cs:9`, `src/maps/src/lib/map/live/connection.ts:129-145`).
- Prerender an export identity catalog alongside existing item sources. Resolve a unique exported character locally and use its own drops, producing plain percentages and no shared-name note. Never treat a guessed prefab key or a nearest ambiguous placement as exact (`src/maps/src/lib/map-world-data.server.ts:568-605`, `src/maps/src/lib/map/live/drop-variants.ts`, `src/maps/src/lib/components/map/popups/LiveNpcPopupContent.svelte:28-33,59-77`).
- For absent, unknown, or ambiguous provenance, retain the scene-preferred name-based candidate aggregation and disclose that identity is unresolved. Correct its lookup to the game's `npc_name`, not curated `display_name` (current mismatch: `src/mods/InteractiveMapCompanion/src/Entities/EntityExtractor.cs:16`, `variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/NPC.cs:518`, `src/maps/src/lib/database.base.ts:1455-1470`).
- Extend protocol, fixture-backed resolution, popup/browser, and loader/lifecycle checks; document the optional identity field and both release channels. Correct stale name-only and serializer comments with the implementation (`src/maps/src/lib/map/character-details.ts:57-62`, `src/maps/src/lib/map/live/types.ts:1-6`, `src/mods/InteractiveMapCompanion/README.md:3-7`).

### Goals and non-goals

Goals: exact character loot when provenance uniquely matches export data; honest fallback otherwise; old companion versions keep operating; no browser database download.

Non-goals: implementing this proposal now; changing game content, export key formats, loot probabilities, rarity/tier rules, vendor presentation, transport endpoints, loader adapters' responsibilities, or database publication. Do not create a repository-to-wiki connection.

### Migration boundary

The future implementation changes the shared companion runtime/protocol and the site's build-time catalog/local popup resolution together. No exported database schema migration is needed: `variants/main/erenshor-main.sqlite` already contains character `object_name`, `scene`, `x`, `y`, and `z`. Site-first deployment is additive; existing mods continue on the fallback. Keep `/db/erenshor.sqlite` published byte-for-byte by the existing server route (`src/maps/src/routes/db/erenshor.sqlite/+server.ts:4-13`). Publication requires separate owner authorization.

## Capabilities

### New Capabilities

- `live-npc-identity`: companion provenance capture, additive identity payload, exact/unknown resolution, and lifecycle guarantees.

### Modified Capabilities

- `map-site-data`: replace unconditional same-name merging with exact-character-first resolution while preserving fallback, prerender-only popup data, hidden-item filtering, legacy interfaces, and database publication (`openspec/specs/map-site-data/spec.md:8-10,27-60,72-92`).

## Impact

Future implementation owners are the companion's shared runtime/Entities/Patches/Protocol and tests, the map repository/world-data builder/character-details/live types/popup and tests, and the existing mod README/channel changelogs. Relevant boundaries are `src/mods/InteractiveMapCompanion/src/InteractiveMapRuntime.cs:40-84,114-148`, `src/mods/InteractiveMapCompanion/InteractiveMapCompanion.csproj:34-46,101-123`, and `src/maps/src/routes/map/+page.svelte:140-143`.

`design.md` records the current-tree audit of every legacy planning premise, including the now-cleared `NextSpawn`, changed data counts, duplicate export suffixes, and the removal of browser SQL from popup flows. Those findings supersede the legacy plan's implementation choices, not its goal.
