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

Use the CLI rather than `pnpm dev` or `pnpm build`.
It sets `ERENSHOR_MAPS_DATABASE_PATH` to the selected clean database.
The Node-side `sql.js` repository reads that database during prerender and dev-server loads.
Browser pages use prerendered data, not a browser database download.
The prerendered `src/maps/src/routes/db/erenshor.sqlite/+server.ts` route still publishes unchanged bytes at `/db/erenshor.sqlite`.
Keep this route for shipped companions and other database consumers.
Remove any `.sqlite` under `src/maps/static/` if `maps dev` or `maps build` rejects a conflicting static file.
Rebuild when `maps preview` or `maps deploy` reports stale inputs.

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
   If the slider range is wrong, inspect `hasVulnerable` in `src/maps/src/lib/map-world-data.server.ts`.
   All-invulnerable markers get clamped to the vulnerable level maximum for filtering.
5. Check `src/maps/src/routes/maps/[mapName]/+page.server.ts` for a zone-page marker.
   Do not debug the world-map deck.gl layer for a zone-page issue.

The canonical `wrangler.jsonc` serves assets directly except `/api/game-version`.
The legacy `wrangler.legacy.jsonc` keeps the `erenshor-maps` service and same-origin `/map` resources for shipped overlays.
Do not rename that service.
