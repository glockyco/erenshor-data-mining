# Design

## Context

See `proposal.md` — Why. This is planning only. The audit below was performed on the current tree and `variants/main/erenshor-main.sqlite`; it is not an in-game observation. Implementation must attach runtime and browser evidence before claiming end-to-end correctness.

### Legacy-plan audit

The removed plan was read with `git show 47bda266:docs/plans/2026-08-05-live-npc-identity.md`. Its goal remains the issue's goal; its following premises and prescribed paths must not be copied uncritically.

| Legacy premise | Current finding and evidence |
| --- | --- |
| The payload identifies NPCs only by display name. | Still no provenance: `src/mods/InteractiveMapCompanion/src/Entities/EntityData.cs:8-39`. More precisely, extraction sends `Stats.MyName` with a live-name fallback (`src/mods/InteractiveMapCompanion/src/Entities/EntityExtractor.cs:10-23`), not the site's curated display name. |
| 39 map-visible shared display names; 22 with differing loot; 52 affected characters (43 prefab, 9 placed). | Changed. The current name-index representative rule is `MIN(member_stable_key)` per map-visible dedup group (`src/maps/src/lib/database.base.ts:1455-1470`). Applied to `variants/main/erenshor-main.sqlite`, ordered full `(item_stable_key, drop_probability)` signatures give **37 shared names, 21 differing-loot names, 50 characters: 42 prefab-style and 8 placed**. These are audit counts, not thresholds or completeness promises. The old 39/22 figures remain in comments in `database.base.ts:1447-1449`, `src/maps/src/lib/map/live/drop-variants.ts:4-8`, `src/maps/src/lib/database.test.ts:117-118`, and `src/maps/tests/fixtures/map-database.sql:370-373`; update those comments rather than treating them as behavior. |
| All 878 prefab rows have unsuffixed keys; duplicate suffixes need no handling. | The 878 simple-key rows still exist, but they are **not all prefab-style rows**. Current database has 893 rows with `scene IS NULL`, including 15 suffixed rows, e.g. `character:annabelle swisher:1` with object `Annabelle Swisher` (`variants/main/erenshor-main.sqlite`, `characters`). The exporter explicitly appends `:{variantIndex}` (`src/Assets/Editor/StableKeyGenerator.cs:162-183`). Runtime origin is not sufficient to invent an exact suffix; collisions must remain ambiguous. |
| `MySpawnPoint` → `NextSpawn` gives the chosen prefab, retained indefinitely. | The fields and the selection-before-instantiation part still exist (`variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/NPC.cs:60-66,1466-1477`, `variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/SpawnPoint.cs:176-219`). **Retention is false in current code:** `ResetSpawnPoint` clears `NextSpawn` at line 229. This proposal does not read either private field. |
| `NPC.HomePos` identifies scene-placed characters. | The field still exists and is initialized to position in `NPC.Start` (`variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/NPC.cs:60,462`). Position alone omits object identity; the legacy `<0.01` per-axis lookup is replaced by captured object + scene + original placement, using a 2 m spherical tolerance (existing policy: `src/mods/AdventureGuide/src/Navigation/DirectPlacementPolicy.cs:20-27`). |
| 376 placed characters occupy 357 positions. | Changed to **361 placed rows at 357 distinct `(scene,x,y,z)` placements**, querying `variants/main/erenshor-main.sqlite`, `characters`. Export still writes placed names, scene and two-decimal coordinates (`src/Assets/Editor/StableKeyGenerator.cs:173-179,425-436`). |
| `NPC.Start` renames the object at line 467 and assigns `Stats.MyName = NPCName` at 518. | Both still true in the current decompilation (`variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/NPC.cs:462-467,517-518`). |
| 34 characters have curated/runtime-name differences; Reaver/Assassin is an example. | Changed to **41 rows** with `display_name <> npc_name` in `variants/main/erenshor-main.sqlite`, `characters`; `character:reaver of sivakaya` remains display `Reaver of Sivakaya`, runtime `Assassin of Sivakaya`. The mismatch remains relevant because the current index still selects `c.display_name` (`src/maps/src/lib/database.base.ts:1463`). |
| `getCharactersByName(name, scene)` and popup `loadData()` are browser SQL paths; popup is the only production caller. | Obsolete API shape and architecture. `getCharactersByName()` now builds the whole index in the Node-side prerender flow (`src/maps/src/lib/database.base.ts:1452-1490`, `src/maps/src/lib/map-world-data.server.ts:568-608`). `/map` indexes that supplied data (`src/maps/src/routes/map/+page.svelte:140-143`); live popup is reactive and makes no SQL calls (`src/maps/src/lib/components/map/popups/LiveNpcPopupContent.svelte:15-24`). Do not add the legacy asynchronous `getCharacterByKey` or home-position browser queries. |
| Scene preference, range formatting and shared-name note already exist. | Still true, now in pure `resolveLiveCandidates` plus reactive popup code (`src/maps/src/lib/map/character-details.ts:64-71`, `src/maps/src/lib/components/map/popups/LiveNpcPopupContent.svelte:28-33,62-67`). Aggregation with one list gives equal endpoints (`src/maps/src/lib/map/live/drop-variants.ts:32-55`). |
| Fixture lacks placement columns and its runtime/display names are equal. | Still true in the relevant rows (`src/maps/tests/fixtures/map-database.sql:29-42,363-374`); implementation must add origin-catalog columns and differentiated names. The fixture's spawn table already has coordinates (`src/maps/tests/fixtures/map-database.sql:55-73`). |
| JSON is camelCase and nulls disappear; shared source reaches both loaders with Harmony. | Still true: Newtonsoft settings are in `src/mods/InteractiveMapCompanion/src/Protocol/MessageSerializer.cs:1-25`; loader entrypoint selection and Harmony refs in `src/mods/InteractiveMapCompanion/InteractiveMapCompanion.csproj:34-46,101-123`. The site header's claim that the mod uses System.Text.Json is false (`src/maps/src/lib/map/live/types.ts:1-6`) and must be corrected. |
| Protocol is 0.2.0 on both ends, mismatch warns without blocking, entities capability only. | Still true (`src/mods/InteractiveMapCompanion/src/Protocol/ProtocolVersion.cs:9`, `src/maps/src/lib/map/live/connection.ts:19,129-145`, `src/mods/InteractiveMapCompanion/src/Config/ModConfig.cs:53`). The site stores capabilities and has a helper (`src/maps/src/lib/map/live/stores.svelte.ts:50-53,101-104`); a search of `src/maps/src` found no caller of that helper. No new capability is needed. |
| Serializer tests are the only mod test surface; no Unity host. | No Unity-host identity tests currently, but “only serialization coverage” is too restrictive. The test project links pure production files, tracker and broadcast loop, without a game reference (`src/mods/InteractiveMapCompanion/tests/InteractiveMapCompanion.Tests/InteractiveMapCompanion.Tests.csproj:23-36`). Put pure origin parsing/normalization policy under that same pattern; use game validation for patch timing/Unity lifecycle. |
| Braxonian has the two archaeologist prefabs with 11/12 drops; four exist globally. | Still true in `variants/main/erenshor-main.sqlite`: `characters`, `loot_drops`, `map_character_spawns` give `character:molorai archaelogist` (11) and `character:molorai archaelogist 1` (12) in `Braxonian`, and two further rows in `Duskenlight` (5 each). Counts are full database loot rows; expected popup contents must apply current item visibility (`src/maps/src/lib/database.base.ts:1237-1251`). The spelling is the exported asset spelling, not invented content. |
| Thunderstore is BepInEx, Vault is Lunaris/manual; headings differ; versions come from release commands; changelog changes require repackaging. | Still true (`src/mods/InteractiveMapCompanion/README.md:3-7,21-34`, `src/mods/InteractiveMapCompanion/thunderstore/CHANGELOG.md:1`, `src/mods/InteractiveMapCompanion/vault/CHANGELOG.md:3`, `src/erenshor/application/mods/release.py:365-405,428-465,562-598,612-614`). **Legacy dry-run spelling is wrong:** use root `--dry-run` before `mod`, since `src/erenshor/cli/commands/mod.py:335-375` reads `cli_ctx.dry_run` and declares no command-local dry-run option. Publication is not authorized by this proposal. |
| `test ci` runs static gates and five leaves. | Current `ci` dependencies are six named leaves: dependency-state, static, unit, contract, maps, mods (`src/erenshor/cli/commands/test.py:95-109`). Name the command, not an obsolete leaf count. |
| Missing exports, old mods, or unreliable placement should fall back. | Retained as proposed behavior, not asserted as complete coverage. Identity existence comes from the catalog, not from presence of drops; empty loot is distinct from unknown identity. Current item sources may have no row for a known character (`src/maps/src/lib/map/character-details.ts:35-44`); that cannot prove absence from the export. |

#### Reproducing the data audit

All SQL below reads `variants/main/erenshor-main.sqlite`. It uses the current name-index representative rule in `src/maps/src/lib/database.base.ts:1455-1470`. Full ordered loot signatures intentionally include hidden items; they measure the legacy data claim, not the new popup's displayed-item count.

```sql
SELECT COUNT(*) AS characters,
       SUM(scene IS NULL) AS prefab_style,
       SUM(scene IS NULL AND stable_key = 'character:' || lower(trim(object_name))) AS simple_prefab_keys,
       SUM(scene IS NULL AND stable_key <> 'character:' || lower(trim(object_name))) AS suffixed_prefab_keys,
       SUM(scene IS NOT NULL) AS placed,
       SUM(display_name <> npc_name) AS renamed
FROM characters;
-- Observed: 1254, 893, 878, 15, 361, 41.
SELECT COUNT(*) FROM (SELECT DISTINCT scene,x,y,z FROM characters WHERE scene IS NOT NULL);
-- Observed: 357.
WITH reps AS (
  SELECT group_key, MIN(member_stable_key) AS stable_key
  FROM character_deduplications WHERE is_map_visible=1 GROUP BY group_key
), signatures AS (
  SELECT c.stable_key,c.display_name,c.scene,
    (SELECT group_concat(sig,'|') FROM (
      SELECT item_stable_key || '=' || COALESCE(drop_probability,'NULL') AS sig
      FROM loot_drops WHERE character_stable_key=c.stable_key ORDER BY item_stable_key
    )) AS loot
  FROM reps r JOIN characters c USING(stable_key)
), shared AS (
  SELECT display_name,COUNT(*) AS n,COUNT(DISTINCT COALESCE(loot,'')) AS loot_n
  FROM signatures GROUP BY display_name HAVING COUNT(*)>1
)
SELECT COUNT(*),SUM(loot_n>1),SUM(CASE WHEN loot_n>1 THEN n ELSE 0 END) FROM shared;
-- Observed: 37, 21, 50. Filtering signatures to these differing-loot names gives 42 prefab-style / 8 placed.
```

## Goals / Non-Goals

**Goals:** provenance must be captured before rename, remain immutable after movement, be independent of component Start ordering, and identify exactly one raw export row before claiming exactness. Preserve name-based operation for every legacy payload and resolve curated-name mismatches.

**Non-Goals:** private-field reflection, an AdventureGuide runtime dependency, guessing export variant suffixes, choosing the nearest of multiple valid placements, runtime SQL/downloads, or changing the existing loot computation/visibility policy. No backfill that labels an already-renamed live name as a prefab name.

## Decisions

### 1. Capture provenance once in the companion's shared runtime

Add companion-owned origin storage and an `NPC.Start` prefix under `src/mods/InteractiveMapCompanion/src/Entities/` and `src/mods/InteractiveMapCompanion/src/Patches/`. Follow the weak-key technique, terminal `(Clone)` removal, and pre-rename position capture in `src/mods/AdventureGuide/src/Navigation/NpcOrigins.cs:30-78`. Extend the placed record to capture `npc.gameObject.scene.name` at the same time, rather than assume whichever scene is active later. The companion does not need AdventureGuide installed and does not reuse its static registry.

Initialize patch dependencies before `PatchAll` in `src/mods/InteractiveMapCompanion/src/InteractiveMapRuntime.cs:49-76`. At extraction, obtain the `NPC` with `GetComponent<NPC>()` rather than depending on `Character.MyNPC` initialization; the game sets that reference inside `NPC.Start` (`variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/NPC.cs:517`). Read cached provenance only for `npc_enemy` and `npc_friendly`; players, SimPlayers, and pets send none. Do not infer provenance from statistics, `NPCName`, spawn tables, current position, or post-rename object names.

A record is keyed by the NPC object, not only a Unity instance ID. On stop/unload unpatch and replace/clear the cache and patch references; destroyed NPCs must not be kept alive. Existing cleanup is owned by `InteractiveMapRuntime.Stop` (`src/mods/InteractiveMapCompanion/src/InteractiveMapRuntime.cs:114-137`). NPCs started before patch installation remain unknown until a fresh start/scene entry; hot reload is not allowed to fabricate their origin. Zone transitions retain no stale entity selection or old-zone matching (`src/maps/src/lib/map/live/stores.svelte.ts:56-65`).

**Alternative rejected:** poll `MySpawnPoint.NextSpawn`/`HomePos`, as in the legacy plan. `NextSpawn` is mutable and cleared; it misses direct encounter instantiation. The prefix records the actual instance's origin before the game's rename and avoids repeated reflection or normalization per snapshot. Do not replicate AdventureGuide's name-based recovery path (`src/mods/AdventureGuide/src/Navigation/EntityRegistry.cs:349-374`) as exact provenance.

### 2. Transmit origin, not an unverified exact key

Proposed optional JSON field:

```json
{"characterOrigin":{"kind":"prefab","objectName":"molorai archaelogist 1"}}
```

```json
{"characterOrigin":{"kind":"placed","objectName":"catnip (1)","scene":"ripperportal","position":[339.547,0.17,757.537]}}
```

Examples derive from the `characters` table of `variants/main/erenshor-main.sqlite`; the field and shape are new design, not current wire output. `objectName` and placed `scene` are trimmed/invariant-lowercased once, matching `src/Assets/Editor/StableKeyGenerator.cs:434-436`; strip only the terminal `(Clone)` before normalization. Placed `position` is scene-local Unity `[x,y,z]` captured at Start, not the moving `EntityData.position` and not a promised editor-exact/home location.

The site owns export resolution. The mod cannot truthfully send an exact `characterKey` when export suffixes or runtime/export drift prevent uniqueness. An origin descriptor accommodates both prefab and placed origins without redundant top-level key/home fields.

Set both version constants to `0.3.0`. Keep message types, transport, required entity fields and `capabilities: ["entities"]` unchanged; extend Newtonsoft's current camelCase/null-omission model (`src/mods/InteractiveMapCompanion/src/Protocol/MessageSerializer.cs:12-20`). Correct the version comment's general expectation of breaking changes (`src/mods/InteractiveMapCompanion/src/Protocol/ProtocolVersion.cs:3-5`) to document that this change is additive. The site's current non-fatal mismatch warning remains (`src/maps/src/lib/map/live/connection.ts:129-145`). Neither versions nor capability flags gate whether a present supported origin can resolve; absent/unsupported/malformed origin falls back without rejecting an otherwise usable state update.

### 3. Prerender a raw-character catalog, index locally, never collapse suffixes

Extend the repository/world-data output with a lightweight row for **every exported character**: raw `stableKey`, `objectName`, nullable `scene` and nullable placement `[x,y,z]`. Keep it separate from the fallback's map-visible dedup representative index. Existing `itemSources` already associates map-visible items with raw character stable keys (`src/maps/src/lib/database.base.ts:1237-1265`); use those exact keys for loot. Catalog membership establishes known identity even when the character has no visible drops.

Build browser indexes once alongside `indexCharacterDetails` (`src/maps/src/routes/map/+page.svelte:140-143`): normalized prefab object name → raw catalog rows with null scene; normalized placed scene + object name → placed rows. Obtain coordinates from exported `characters`, not arbitrary spawn-point coordinates. Change the fallback name index to `npc_name`, with scenes still unioned through the current dedup-member spawn query (`src/maps/src/lib/database.base.ts:1455-1470`). Do not keep a display-name alias for the fallback: display names remain presentation, not runtime identity.

Resolution returns explicit `exact` (one key) or `unresolved` (fallback candidates and a reason):

1. Supported prefab origin: resolve all prefab-style rows matching its normalized original object name. Exactly one raw row is exact. Zero is unknown; multiple rows, including unsuffixed plus `:1`, are ambiguous. Never prefer the unsuffixed row or collapse numeric suffixes.
2. Supported placed origin: require its captured scene to match the live snapshot's zone after normalization. Match original object name and captured scene, then all exported placements with squared 3D distance **<= 4**. Exactly one row is exact. Zero/multiple rows are unresolved. Do not use current entity position or name to choose a winner. This uses AdventureGuide's 2 m tolerance (`src/mods/AdventureGuide/src/Navigation/DirectPlacementPolicy.cs:25-27`) but deliberately does **not** choose nearest among multiple matches as its registry does (`src/mods/AdventureGuide/src/Navigation/EntityRegistry.cs:308-337`); a loot popup must not assert a guessed character.
3. Missing, malformed, unsupported, unmatched, or ambiguous origin: use the NPC-name index, prefer candidates whose known scenes include the live zone, otherwise keep every candidate. Preserve the current `placed.length > 0 ? placed : matches` behavior (`src/maps/src/lib/map/character-details.ts:64-71`). A single fallback candidate remains an inference, not an exact provenance match.

All matching is local against prerendered data. No new endpoint, async popup query, SQLite fetch, or database route change. The existing `/db/erenshor.sqlite` remains published for external consumers (`src/maps/src/routes/db/erenshor.sqlite/+server.ts:4-13`).

### 4. Exact and fallback loot have different certainty

Exact: show only the resolved raw character's existing map-visible drops, with the existing plain one-decimal percentages, descending chance/name ordering, and no shared-name note. A known exact character with an empty visible list explicitly says **“No map-visible drops recorded.”** It must not fall back to a same-named character with loot.

Unresolved: show **“Character identity unresolved; showing name-based candidates.”** If several candidates exist, retain merged items, their existing min/max chance formatting, and an accurate candidate-count note; do not claim every candidate has different loot merely because count exceeds one. If no fallback candidate exists, say **“No matching character data.”** These messages appear even when the drop list is empty, unlike today's drop-gated note (`src/maps/src/lib/components/map/popups/LiveNpcPopupContent.svelte:59-67`). A lone fallback candidate can show plain percentages, but retains the unresolved label so appearance is not proof of exactness.

Keep `aggregateDropVariants` for fallback and existing ordering (`src/maps/src/lib/map/live/drop-variants.ts:32-55`); preserve its semantics, including no zero-probability injection for candidates missing an item. Do not claim ranges are a probability distribution of the current NPC. This change does not add vendor stock, alter wiki-link selection or encounter tier behavior.

### 5. Ownership and write boundaries

| Artifact/file kind | Future owner | Write boundary |
| --- | --- | --- |
| Origin records, prefix, extraction, entity schema and version | InteractiveMapCompanion shared runtime | Its own `src/Entities`, `src/Patches`, `src/Protocol`, runtime lifecycle; no AdventureGuide source changes, game-source changes or loader-specific capture logic. Existing loader selection: `src/mods/InteractiveMapCompanion/InteractiveMapCompanion.csproj:34-46`. |
| Identity catalog and runtime-name index | Node-side map repository and world-data builder | Read selected clean SQLite only; emit prerendered page data, never rewrite the database. Current closure/return boundary: `src/maps/src/lib/map-world-data.server.ts:568-608`. |
| Resolver and popup | `/map` local character-details and live popup | Consume page data/wire origin without requests; change only identity/loot certainty, not icons/portraits/renderer dependencies (`src/maps/src/lib/components/map/popups/LiveNpcPopupContent.svelte:9-24`). |
| Behavioral fixtures/tests | Existing map and companion test suites | Synthetic fixture data stays under `src/maps/tests/fixtures` and test-only pure policy cases in companion tests; no mock claims about game execution (`src/mods/InteractiveMapCompanion/tests/InteractiveMapCompanion.Tests/InteractiveMapCompanion.Tests.csproj:23-36`). |
| User/protocol documentation and release notes | Companion README, existing skill protocol guidance, channel changelogs | Describe current implemented behavior, not duplicate internal protocol documents. Channel ownership: `src/mods/InteractiveMapCompanion/README.md:3-34`. |
| Published site/database | Existing map publishing pipeline/server route | Keep both hosts and `/db/erenshor.sqlite`; no symlink/static replacement (`openspec/specs/map-site-data/spec.md:8-60`, `src/maps/src/routes/db/erenshor.sqlite/+server.ts:4-13`). |

## Risks / Trade-offs

- Runtime/export position drift or origin collisions → 2 m candidate tolerance, unique-match-only exactness, explicit fallback. Validate Kio and Catnip scene placements from `variants/main/erenshor-main.sqlite`; Kio's Stowaway and ShiveringStep rows share `(799.340332,20.069567,585.853455)` while their scene differs, and Catnip's placed object names differ from NPCName.
- Export variant rows lack a runtime discriminator → preserve ambiguity; do not promise exactness for all 893 prefab-style rows. Additional discriminators would require a separate grounded change, not a guess here (`src/Assets/Editor/StableKeyGenerator.cs:182-183`).
- Component Start order and live reload → capture in NPC prefix, read NPC component directly, no Character.Start identity patch, and test encounter clones with Character.Start before NPC.Start. Order is a runtime acceptance check, not something the decompiled method bodies alone prove (`variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/Character.cs:236`, `src/mods/AdventureGuide/src/Patches/NpcStartPatch.cs:21-29`).
- Game update changes names or suppresses capture → unresolved fallback is visible; BepInEx patch-load logs and wire frames distinguish absent provenance from unknown export. Do not silently disable the entire overlay to hide identity failure (`src/mods/InteractiveMapCompanion/src/InteractiveMapRuntime.cs:75-84`).
- Site/mod versions are rolled out independently → additive field, non-fatal negotiation, site-first release; verify both directions with a retained old build and captured legacy frames (`src/maps/src/lib/map/live/connection.ts:129-145`).
- Extra prerender payload → emit only identity columns and pre-index once; no repeated origin allocation/reflection/normalization in the 100 ms extraction path (interval documented in `src/mods/InteractiveMapCompanion/README.md:96-99`).

## Migration Plan

Implement as sequential verified atomic units: (1) catalog/resolver/fallback correctness, (2) origin producer plus protocol version, (3) integration acceptance and release documentation. Update each unit's affected callers/tests/comments together. Runtime coverage precedes public publication.

Deploy the verified site first on the existing canonical and legacy hosts; retained old mods continue resolving by name. Build and validate both mod targets, then prepare both channel artifacts and matching changelogs. Do not publish a Thunderstore upload, Vault upload, site deployment, or git push without separate owner authorization. Current commands/guards: `src/erenshor/cli/commands/mod.py:335-429`; release rechecks immutable input hashes (`src/erenshor/application/mods/release.py:612-614`).

Rollback uses the prior complete site build and each channel's prior loader-correct artifact. New mods remain usable with the old site's name-only consumer because the payload additions do not change old fields; old mods remain usable with the new site. Restore the whole mod artifact, not an identity-only DLL fragment. Recheck the existing database URL and both hosts after either rollback (`openspec/specs/map-site-data/spec.md:8-40`).

## Open Questions

No identity or compatibility decision is deferred. Before publication the owner must decide **when to authorize the site/channel releases**, and **who performs the Lunaris runtime validation if that installation is unavailable to the implementer**. Neither decision changes the specified behavior; unavailable loader evidence must be reported explicitly rather than presented as tested.
