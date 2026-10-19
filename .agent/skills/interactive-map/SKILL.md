---
name: interactive-map
description: Build, verify, deploy, or debug the interactive map. Use when changing src/maps/, map markers, zone pages, or renderer dependencies.
---

# Interactive map

## Build and deploy

1. Select the variant with `-V` before `maps` when it is not the default.
2. Run `uv run erenshor maps dev` for local changes.
   Use `--port` if port 5173 is occupied.
3. Run `uv run erenshor maps build` after changing data, tiles, or site code.
   This command runs lint, Svelte diagnostics, and fixture-backed Vitest tests before building.
4. Run `uv run erenshor maps preview`.
   Inspect `/map` and a zone page in a browser.
5. Run `uv run erenshor test maps` for the fixture-backed Playwright smoke test.
   Install Chromium with `pnpm --dir src/maps exec playwright install chromium` if its preflight requests it.
   `pnpm --dir src/maps run test:e2e` runs only that smoke test.
6. Deploy the fresh build with `uv run erenshor maps deploy`.
   The canonical service deploys first, then the legacy service.
   If the second deploy fails, resume with `uv run erenshor maps deploy --target legacy`.

For a coordinated publication, use the prepared `publish` workflow instead of
chaining wiki, map, and Sheets deploy commands. Select map targets explicitly in
the selection file. Preparation runs the checked maps build and freezes its
Worker bundles, assets, database route, and native provenance for review.
Review the complete artifact manifests and captured Cloudflare account,
service, deployment, and version identities before approving the plan digest.
Apply and resume never rebuild under that approval.

Map deployment uses a preflight-and-postflight guard, not an atomic provider
revision guard. Another writer can race the deployment. Resume verifies the
recorded active version, its upload annotation, pinned artifact evidence, and
the database body before skipping a completed target. After canonical success,
resume only the remaining legacy operation through the same plan. A lost or
unknown provider receipt requires reconciliation, not a blind redeploy.
Provider recovery is a separately reviewed action using the recorded previous
deployment/version IDs. It is not an automatic or cross-service rollback.

Production analytics uses the tracked public configuration in `src/maps/.env.production`.
Do not require a machine-local token to publish the normal site.
Development leaves analytics off so local browsing does not count as site traffic.
Prepared publication rejects private dotenv overrides and non-public dotenv
assignments, so credentials never become approval fingerprints. Keep public
production build inputs in the maintained production environment file.

Use the CLI rather than `pnpm dev` or `pnpm build`.
It sets `ERENSHOR_MAPS_DATABASE_PATH` to the selected clean database.
The Node-side `sql.js` repository reads that database during prerender and dev-server loads.
Browser pages use prerendered data, not a browser database download.
The prerendered `src/maps/src/routes/db/erenshor.sqlite/+server.ts` route still publishes unchanged bytes at `/db/erenshor.sqlite`.
Keep this route for shipped companions and other database consumers.
Remove any `.sqlite` under `src/maps/static/` if `maps dev` or `maps build` rejects a conflicting static file.
Rebuild when `maps preview` or `maps deploy` reports stale inputs.

`maps dev` and `maps build` generate catalog-backed WebP sets incrementally:
item icons under `static/items` (20 px search, 48 px item popup) and approved
character portraits under `static/characters` (96 px and 192 px for 1x/2x).
Portraits sit centred above the text in character popups and spawn cards, leaving
the narrow popup's full width for details. Files use the catalog pixel hash,
shared pictures share files, and stale files are removed. A character with no
portrait leaves no image slot; the map never uses wiki pictures as a fallback.

The smoke test covers `/`, `/map`, `/maps/Stowaway`, marker popups, legacy `layers` query state, and the published database.
It fails on site-initiated `.sqlite` requests.
Extend it when changing a companion-facing URL or database contract.

## Renderer dependency updates

1. Change map dependencies in `src/maps/package.json`.
   Update the root `pnpm-lock.yaml` with `pnpm install --lockfile-only` from the repository root.
2. Keep deck.gl updates separate from routine dependencies.
   The current deck.gl packages use 9.3.11.
   Root `package.json` pins luma.gl to 9.3.6, and `renovate.json` excludes 9.4.
   Do not lift that restriction until the in-game check passes.
3. Run `uv run erenshor maps build`, then start `uv run erenshor maps preview`.
   In a browser, check `/map?layers=-wm` from fitted view to full zoom-out.
   Zone tiles must remain visible.
4. Capture the loading frames.
   The spinner must lead directly to the fitted view, without a wrong-scale frame.
5. Click a marker and check that its popup appears promptly.
   Search for an enemy and watch the scale bar through the fly-to.
   The zoom must animate throughout, not jump on the first frame.
6. Check markers, rotation, and a popup at `/maps/Stowaway`.
7. On Windows with a hardware GPU, open `/map` in the companion mod's Steam overlay.
   Check tiles and markers, then check `Steam/logs/cef_log.txt` for `GPU process exited unexpectedly`.
   A desktop browser does not cover this check.

A TileLayer without `extent` can hide tiles below its `minZoom`.
A fly-to that interpolates only `zoom` snaps because the orthographic controller uses `zoomX` and `zoomY`.
Keep both orthographic axes in initial, restored and instant camera updates,
because later transitions use those raw values as their starting state.
Wrap DOM focus callbacks so browser events cannot become camera padding.
The overlay has crashed with deck.gl 9.4.0 and luma.gl 9.4.2 on Direct3D 11.

## Add or debug a zone

1. Add capture bounds and tile geometry to `src/maps/src/lib/data/zone-capture-config.json`.
   Use the `tile-capture` skill for tile capture.
2. Add `worldX` and `worldY` to `src/maps/src/lib/data/zone-positions.json`.
   A missing entry fails world-map prerender with `Missing zone position`.
3. Add the display name in `src/maps/src/lib/maps.ts`.
   Check the clean database for the zone's north bearing.
   `buildZoneConfigs` fails with `Missing northBearing for zone` otherwise.
4. Build and open `/map` and the zone page.
   Account for rotated bounds when placing the zone on the world overview.

## Debug missing markers

Item acquisition and popup loot come only from the persisted provenance contract.
Regenerate the clean database when its schema version is missing or unsupported.
Inspect the acquisition, typed condition, location and evidence records together.
The map keeps native-pool chances separate from final acquisition probabilities.
Common world drops use the chance range stored in canonical acquisition facts.
They do not create named droppers or enemy markers.
Map builds write offline provenance coverage outside the published site.
Use its origin IDs and reviewed lifecycle records when diagnosing omitted sources.
Historical ownership selection and static operands stay out of current prerequisite
copy because they are not current player-state tests. Their full conditions and
presentation reasons remain in the offline coverage artifact.
One-time claim conditions use account state rather than a quest proxy because the
claim is shared across characters.
Saved-return portals are conditional destinations, not fixed zone links, because
their saved origin belongs to the character. Keep serialized defaults in offline
coverage rather than using them to guess a return marker or connection.
Portal markers show `zone_line_connections`: lines that players can use
(`zone_lines.is_usable`, which adds the reviewed exclusions of `mapping.json` to
the raw zoning capability) and that no gate shuts for good. Initial inactivity
does not make a line unusable.
Pure global fishing replacements share one Any water source without markers.
Higher local catch rates retain their water and time restrictions.
The grouped source keeps every originating acquisition for offline coverage.

Treasure-hunt drops use possible treasure sites and their eligible player levels.
Every source remains listed when no marker locates it. Coordinates are never
inferred from the source character. Conditional room rewards require the stated
furnishing. Only reviewed current items with verified final acquisitions and
satisfiable conditions appear as public sources.
For functionally identical variants sharing a wiki page, keep one map-visible
representative in `mapping.json`. Hidden variants then share that result while
retaining their originating item, copy, variant and acquisition identities.
Pages with multiple visible variants keep separate results.

1. Inspect `map_character_spawns` and `characters` in the clean database.
   `getSpawnPointMarkers` in `src/maps/src/lib/database.base.ts` requires
   `character_deduplications.is_map_visible = 1` and a non-null spawn point.
   It also requires positive `spawn_chance` or non-null `source_script`.
2. Check the returned marker's tier.
   A spawn point is an NPC marker only if every character has tier `npc`.
   Other points use their most notable enemy tier in `enemiesEnemy`, `enemiesElite`, or `enemiesBoss`.
3. On `/map`, inspect `window.__mapDebug.findEnemy('Name')`,
   `window.__mapDebug.findNpc('Name')`, `window.__mapDebug.layerVisibility`,
   and `window.__mapDebug.levelFilter` in a dev session.
   This hook is not available in production.
4. If a marker exists but is hidden, check layer visibility and level overlap.
   Inspect actual-copy combat eligibility before deduplication or level aggregation.
   Initial immunity and the representative's level cannot replace that result, because
   a proven scripted or quest release can make an initially immune enemy fightable.
5. Check `src/maps/src/routes/maps/[mapName]/+page.server.ts` for a zone-page marker.
   Do not debug the world-map deck.gl layer for a zone-page issue.

The canonical `wrangler.jsonc` serves assets directly except `/api/game-version`.
The legacy `wrangler.legacy.jsonc` keeps the `erenshor-maps` service and same-origin `/map` resources for shipped overlays.
Do not rename that service.
