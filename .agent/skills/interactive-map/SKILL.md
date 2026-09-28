---
name: interactive-map
description: Interactive map system architecture and debugging. Use when working on src/maps/ or troubleshooting map markers.
---

# Debugging Map Issues

The map uses SvelteKit (prerendered) + deck.gl. Bugs can live anywhere
in the pipeline: DB → `map-world-data.server.ts` → `data.markers.*` → deck.gl layer.
The server-only world-data builder owns repository initialization and cleanup,
queries, coordinate transforms, normalization, sorting, and item preloading. The
`+page.server.ts` route only delegates to that builder.

## Dependency updates

The map is part of the root pnpm workspace. Add or change map dependencies only
in `src/maps/package.json`, then regenerate the root lockfile from the repository
root:

```bash
pnpm install --lockfile-only
erenshor test dependency-state
```

Never create a lockfile under `src/maps/` and never run an updater only from that
directory. Renovate owns routine map updates and groups compatible pnpm patch
and minor releases. Review major updates through the Dependency Dashboard.

### Renderer updates (deck.gl, luma.gl, Leaflet)

Minor renderer releases change behavior that the unit tests cannot see,
because they use stand-in layers and the fixture site has no tiles. deck.gl
9.4 hid zone tiles below their `minZoom` when a TileLayer had no `extent`, and
it drew one frame before it measured the canvas. Before you merge a renderer
update, run `maps build` and `maps preview` and check these in a browser:

1. On `/map` with `layers=-wm`, zoom from the fitted view to full zoom out.
   Every zone keeps its tiles.
2. Capture the load frames (a CDP screencast). The spinner is followed
   directly by the fitted view, with no frame at a different scale.
3. Click a marker and time pointerup to popup. It stays well under 50 ms.
4. Search an enemy and sample the scale bar during the fly-to. The zoom
   changes over the whole transition instead of jumping on the first frame.
   deck.gl 9.4 made the orthographic controller interpolate `zoomX` and
   `zoomY`, so a transition that lists only `zoom` snaps.
5. Open a zone page (`/maps/Stowaway`) and check its markers, rotation, and a
   popup.

## Hosting topology

Two Worker services, one build, deployed canonical first by `maps deploy`:

- `wrangler.jsonc` → `erenshor-maps-site` → `erenshor.compendiums.org`. Assets
  are served without invoking the Worker. `src/maps/src/site-worker.ts` handles only
  `/api/game-version`, which `assets.run_worker_first` routes to it. Listing
  that path is required: with plain asset-first routing a static file at that
  path would shadow the endpoint and serve stale JSON.
- `wrangler.legacy.jsonc` → `erenshor-maps` → `erenshor-maps.wowmuch1.workers.dev`.
  `src/maps/src/legacy-worker.ts` runs before assets because it routes on hostname, and
  keeps the legacy `/map` document plus its runtime resources same-origin for
  shipped companion overlays. Never rename this service.

Trailing-slash HTML paths (`/map/`, `/maps/{key}/`) answer with a same-origin
relative `307` from the asset layer's `auto-trailing-slash` handling on both
hosts. That is expected, not a bug.

`src/maps/src/worker-config.test.ts` asserts this split, so a config that merges the two
services back together fails the suite rather than production.

## Architecture facts

- Database: `maps dev` and `maps build` pass the selected variant's clean DB to the site through `ERENSHOR_MAPS_DATABASE_PATH`. Server loads and prebuild scripts read it from there, and the build fails when the variable is unset. Vitest and `test maps` use a temporary fixture database.
- `src/maps/src/routes/db/erenshor.sqlite/+server.ts` publishes the clean DB unchanged at `/db/erenshor.sqlite`. Shipped companion overlays and unknown outside consumers may request it, so it stays published. No page and no service worker downloads it, and the smoke test fails on any `.sqlite` request. Both commands refuse to run while a `.sqlite` file remains under `src/maps/static/`.
- Zone pages get their markers and north bearing from the prerendered `routes/maps/[mapName]/+page.server.ts`. `/map` popups index `data.itemSources` and `data.charactersByName` with `indexCharacterDetails` (`src/maps/src/lib/map/character-details.ts`), so they show exactly the items that the item search shows.
- `maps thumbnails` requires a running `maps dev` or `maps preview` server and a local Playwright Chromium installation (`pnpm exec playwright install chromium`, once per machine). Pass the actual server URL with `--url`; use `maps dev` when generating thumbnails from variant data.
- `erenshor test maps` runs the Playwright smoke test in `src/maps/tests/e2e/` against a fixture build that `src/maps/scripts/serve-fixture-site.mjs` serves. It needs the Chromium build of the locked Playwright version (`pnpm --dir src/maps exec playwright install chromium`, once per machine), and its preflight names that command when Chromium does not launch. Extend the smoke test when a change touches a companion-facing interface: the `/map` query parameters, the WebSocket protocols, or `/db/erenshor.sqlite`.
- `+page.server.ts` has `export const prerender = true` and delegates to the
  server-only world-data builder — server code also runs during `uv run erenshor maps build` (stdout visible in build output)
- Enemy markers split into three arrays by encounter tier: `data.markers.enemiesEnemy/Elite/Boss`
- NPC markers: `data.markers.npcs`
- Bucket assignment: `isNpc = characters.every(c => c.encounterTier === 'npc')`; else the marker takes the most notable tier of its characters (boss, then elite, then enemy). The tier comes from `characters.encounter_tier` in the clean DB; see `docs/architecture.md`
- Level filter: `DataFilterExtension` with `getFilterValue: d => [d.levelMin, d.levelMax]`

## window.__mapDebug hook

`+page.svelte` exposes `window.__mapDebug` in DEV mode (zero prod cost):

```js
window.__mapDebug.findEnemy('Name')  // → WorldEnemy[] across all three buckets
window.__mapDebug.findNpc('Name')    // → WorldNpc[]
window.__mapDebug.markers            // → all marker arrays
window.__mapDebug.levelFilter        // → [min, max] current slider state
window.__mapDebug.levelRange         // → {min, max} overall range
window.__mapDebug.layerVisibility    // → {spawnPoints, spawnPointsElite, spawnPointsBoss, ...}
```

## Playwright debug loop

Dev server must be running (`uv run erenshor maps dev`). Write a one-shot script:

```js
// src/maps/debug-markers.js  (delete after use, never commit)
import { chromium } from '@playwright/test';

const page = await (await chromium.launch({ headless: true })).newPage();
page.on('console', msg => { if (msg.type() === 'error') console.log('[err]', msg.text()); });

await page.goto('http://localhost:5175/map?sel=enemy%3AEvadne+the+Corrupted');
await page.waitForFunction(() => window.__mapDebug != null, { timeout: 10_000 });

const result = await page.evaluate(() => {
    const d = window.__mapDebug;
    return {
        levelFilter: d.levelFilter,
        enemies: d.findEnemy('Evadne the Corrupted').map(m => ({
            stableKey: m.stableKey, isEnabled: m.isEnabled,
            encounterTier: m.encounterTier, levelMin: m.levelMin, levelMax: m.levelMax,
        })),
    };
});
console.log(JSON.stringify(result, null, 2));
await browser.close();
```

Run with: `node src/maps/debug-markers.js`

## Adding a new zone — three files, not one

`zone-capture-config.json` is necessary but not sufficient:

1. **`src/maps/src/lib/data/zone-capture-config.json`** — bounds + tile geometry (covered by `skill://tile-capture`).
2. **`src/maps/src/lib/data/zone-positions.json`** — `worldX`/`worldY` placing the zone on the `/map` overview. **Missing this entry crashes `/map` server-side** with `Cannot read properties of null` in `buildZoneWorldPositions`. No autocomputed default.
3. **`DISPLAY_NAMES` in `src/maps/src/lib/maps.ts`** — friendly name keyed by scene name.

`northBearing` in `zone-capture-config.json` is an **override slot**, not the source of truth — `"northBearing": null` means "use the DB value". The render-time bearing comes from `zones.north_bearing` in the variant clean DB (see `buildZoneConfigs` in `src/maps/src/lib/map/zone-config.ts`). When laying out a zone on the overview, account for the actual rotation: a zone with bearing 105° has a rotated AABB different from `baseTilesX * tileSize` × `baseTilesY * tileSize`.

## Common failure modes

**Marker missing from all buckets** → check DB query in `getSpawnPointMarkers`:
- `cs.spawn_chance > 0 OR cs.source_script IS NOT NULL` filters zero-chance entries
  that no script spawns
- only `character_deduplications` rows with `is_map_visible = 1` produce markers
- `isNpc = characters.every(c => c.encounterTier === 'npc')` — a single
  hostile character at a spawn point makes it an enemy marker

**Marker present but invisible** → check:
1. `layerVisibility.spawnPoints/spawnPointsElite/spawnPointsBoss` — layer toggled off
2. Level filter: `levelMin`/`levelMax` must overlap with `levelFilter`
   - `±Infinity` does NOT work as "always pass" in GLSL — `step(Infinity, finiteMax) = 0`
   - Invulnerable-only markers get `levelMax` clamped to `enemyLevelMax` so they always pass

**Marker visible but wrong icon** → `getEnemyIconType` uses the marker-level
`encounterTier`, which is the most notable tier among the marker's characters

**Level slider range distorted** → level-range calculation in
`map-world-data.server.ts` skips markers where all characters are invulnerable;
check the `hasVulnerable` guard

## DB queries for quick spot-checks

```bash
# All data for a character's spawns
sqlite3 variants/main/erenshor-main.sqlite "
SELECT cs.spawn_point_stable_key, cs.is_enabled, cs.scene,
       c.display_name, c.level, c.encounter_tier, c.invulnerable,
       cs.is_rare, cs.spawn_chance, cs.source_script
FROM map_character_spawns cs
JOIN characters c ON c.stable_key = cs.character_stable_key
WHERE c.display_name = 'Evadne the Corrupted';"
```
