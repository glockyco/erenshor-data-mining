/**
 * Generate zone map thumbnail images for the zone-maps gallery page.
 *
 * Usage:
 *   node scripts/generate-thumbnails.mjs [ZoneKey ...]
 *
 * Environment:
 *   MAPS_URL  Base URL of the running dev/preview server (default: http://localhost:5174)
 *
 * Output:
 *   src/maps/static/maps/{ZoneKey}.jpg — 800px wide JPEG, cropped to tile content,
 *   aspect ratio preserved.
 *
 * Requirements:
 *   - Dev or preview server must be running at MAPS_URL
 *   - Playwright browsers installed: pnpm exec playwright install chromium
 */

import { chromium } from '@playwright/test';
import sharp from 'sharp';
import { readFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, '..', '..', '..');
const CONFIG_PATH = join(REPO_ROOT, 'src/maps/src/lib/data/zone-capture-config.json');
const OUT_DIR = join(REPO_ROOT, 'src/maps/static/maps');

const BASE_URL = process.env.MAPS_URL ?? 'http://localhost:5174';
const THUMB_WIDTH = 800;
// Large enough that even big zones (6x6 baseTiles) fit at zoom=0.
// At zoom=0, a 6x6 zone = 6*256=1536px wide. So 1800px viewport is safe.
const VIEWPORT = { width: 1800, height: 1400 };
// How long to wait (ms) for all visible tiles to finish loading after fitBounds.
const TILE_SETTLE_MS = 1500;

const zoneConfig = JSON.parse(readFileSync(CONFIG_PATH, 'utf8'));
mkdirSync(OUT_DIR, { recursive: true });

// Zones to process: CLI args, or all zones in config
const requested = process.argv.slice(2);
const zones = requested.length > 0 ? requested : Object.keys(zoneConfig);

let passed = 0;
let failed = 0;

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
    viewport: VIEWPORT,
    // Force coordinate-aligned (north-up) mode before the page initialises.
    storageState: {
        cookies: [],
        origins: [
            {
                origin: BASE_URL,
                localStorage: [{ name: 'mapRotationMode', value: 'coordinates' }],
            },
        ],
    },
});
const page = await context.newPage();

for (const zone of zones) {
    if (!zoneConfig[zone]) {
        console.error(`  SKIP  ${zone} — not in zone-capture-config.json`);
        failed++;
        continue;
    }

    process.stdout.write(`  ${zone} ...`);

    try {
        await page.goto(`${BASE_URL}/${zone}`, { waitUntil: 'domcontentloaded', timeout: 30_000 });

        // Wait for the Leaflet map instance to be exposed and at least one tile to load.
        await page.waitForFunction(() => window.__leafletMap != null, { timeout: 20_000 });
        await page.waitForSelector('.leaflet-tile-loaded', { timeout: 20_000 });

        // Fit map to the full tile bounds so we see the entire zone regardless of
        // whatever default zoom/center was set.
        const { worldSizeX, worldSizeY } = (() => {
            const z = zoneConfig[zone];
            return {
                worldSizeX: z.baseTilesX * z.tileSize,
                worldSizeY: z.baseTilesY * z.tileSize,
            };
        })();

        await page.evaluate(
            ({ wx, wy }) => {
                window.__leafletMap.fitBounds([[0, 0], [wy, wx]], { animate: false, padding: [0, 0] });
            },
            { wx: worldSizeX, wy: worldSizeY },
        );

        // Wait for tiles to finish loading after the view change.
        await page.waitForFunction(
            () => document.querySelectorAll('.leaflet-tile-loading').length === 0,
            { timeout: 20_000 },
        );
        await page.waitForTimeout(TILE_SETTLE_MS);

        // Compute the on-screen bounding box from the world corners via the
        // Leaflet projection — exact and independent of which tiles are loaded.
        // Tiles pre-fetched outside the viewport can inflate the loaded-tile bounding
        // box, causing grey border inclusion; this approach is not affected.
        const clip = await page.evaluate(({ wx, wy }) => {
            const map = window.__leafletMap;
            const sw = map.latLngToContainerPoint([0, 0]);
            const ne = map.latLngToContainerPoint([wy, wx]);
            const vw = map.getContainer().clientWidth;
            const vh = map.getContainer().clientHeight;
            // Clamp to viewport — content may extend beyond it for large zones.
            const x0 = Math.max(0, Math.min(Math.floor(Math.min(sw.x, ne.x)), vw));
            const y0 = Math.max(0, Math.min(Math.floor(Math.min(sw.y, ne.y)), vh));
            const x1 = Math.max(0, Math.min(Math.ceil(Math.max(sw.x, ne.x)), vw));
            const y1 = Math.max(0, Math.min(Math.ceil(Math.max(sw.y, ne.y)), vh));
            return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
        }, { wx: worldSizeX, wy: worldSizeY });

        if (!clip || clip.width <= 0 || clip.height <= 0) {
            throw new Error('could not determine tile bounds');
        }

        // Screenshot just the tile area (no UI chrome, no gray background).
        const png = await page.screenshot({ clip });

        // Resize to standard thumbnail width; keep aspect ratio; save as JPEG.
        const outPath = join(OUT_DIR, `${zone}.jpg`);
        await sharp(png)
            .resize(THUMB_WIDTH, null, { withoutEnlargement: false })
            .jpeg({ quality: 85, mozjpeg: true })
            .toFile(outPath);

        const finalSize = await sharp(outPath).metadata();
        process.stdout.write(` ${finalSize.width}x${finalSize.height} — ok\n`);
        passed++;
    } catch (err) {
        process.stdout.write(` FAILED: ${err.message}\n`);
        failed++;
    }
}

await browser.close();

console.log(`\nDone: ${passed} ok, ${failed} failed`);
if (failed > 0) process.exit(1);
