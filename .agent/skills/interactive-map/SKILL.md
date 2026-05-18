---
name: interactive-map
description: Interactive map system architecture and debugging. Use when working on src/maps/ or troubleshooting map markers.
---

# Debugging Map Issues

The map uses SvelteKit (prerendered) + deck.gl layers. Bugs can live anywhere
in the pipeline: DB → `+page.server.ts` → `data.markers.*` → deck.gl layer.
Use Playwright to close the debug loop entirely without a browser.

## Architecture facts

- DB used at runtime: `src/maps/static/db/erenshor.sqlite` (symlink to `variants/main/erenshor-main.sqlite`)
- `+page.server.ts` has `export const prerender = true` — server code also
  runs at `pnpm build` time (stdout visible in build output)
- Enemy markers split into three arrays: `data.markers.enemiesCommon/Rare/Unique`
- NPC markers: `data.markers.npcs`
- Bucket assignment: `isNpc = characters.every(c => c.isFriendly)`; else enemy sorted by `isUnique`/`isRare`
- Level filter: `DataFilterExtension` with `getFilterValue: d => [d.levelMin, d.levelMax]`

## window.__mapDebug hook

`+page.svelte` exposes `window.__mapDebug` in DEV mode (zero prod cost):

```js
window.__mapDebug.findEnemy('Name')  // → WorldEnemy[] across all three buckets
window.__mapDebug.findNpc('Name')    // → WorldNpc[]
window.__mapDebug.markers            // → all marker arrays
window.__mapDebug.levelFilter        // → [min, max] current slider state
window.__mapDebug.levelRange         // → {min, max} overall range
window.__mapDebug.layerVisibility    // → {spawnPoints, spawnPointsRare, ...}
```

## Playwright debug loop

Dev server must be running (`pnpm --filter maps dev`). Write a one-shot script:

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
            isUnique: m.isUnique, levelMin: m.levelMin, levelMax: m.levelMax,
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
- `spc.SpawnChance > 0` filters zero-chance entries
- `isNpc = characters.every(c => c.isFriendly)` — a single `IsFriendly=1`
  character at a spawn point makes it an NPC marker

**Marker present but invisible** → check:
1. `layerVisibility.spawnPoints/spawnPointsRare/spawnPointsUnique` — layer toggled off
2. Level filter: `levelMin`/`levelMax` must overlap with `levelFilter`
   - `±Infinity` does NOT work as "always pass" in GLSL — `step(Infinity, finiteMax) = 0`
   - Invulnerable-only markers get `levelMax` clamped to `enemyLevelMax` so they always pass

**Marker visible but wrong icon** → `getEnemyIconType` uses `isUnique`/`isRare` on
`EnemyMarker` (marker-level flags), not `effectiveRarity` on `SpawnCharacter`

**Level slider range distorted** → range calc in `+page.server.ts` skips
markers where all characters are invulnerable; check the `hasVulnerable` guard

## DB queries for quick spot-checks

```bash
# All data for a character's spawns
sqlite3 variants/main/erenshor-main.sqlite "
SELECT sp.StableKey, sp.IsEnabled, sp.Scene,
       c.NPCName, c.Level, c.IsFriendly, c.Invulnerable,
       c.IsCommon, c.IsRare, c.IsUnique, spc.SpawnChance
FROM SpawnPoints sp
JOIN SpawnPointCharacters spc ON spc.SpawnPointStableKey = sp.StableKey
JOIN Characters c ON c.StableKey = spc.CharacterStableKey
WHERE c.NPCName = 'Evadne the Corrupted';"
```
