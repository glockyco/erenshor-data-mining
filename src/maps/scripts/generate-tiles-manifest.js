#!/usr/bin/env node

import { readdir, writeFile } from 'fs/promises';
import { join } from 'path';

const TILES_DIR = 'static/tiles';
const OUTPUT_FILE = 'static/tiles/tiles-manifest.json';
const PRECACHE_ZOOM_LEVELS = ['-4', '-3', '-2', '-1'];

async function findTiles(dir, tiles = []) {
    const entries = await readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
        const fullPath = join(dir, entry.name);
        if (entry.isDirectory()) {
            await findTiles(fullPath, tiles);
        } else if (entry.name.endsWith('.webp')) {
            // Convert to URL path: static/tiles/Zone/-1/0/-1.webp -> /tiles/Zone/-1/0/-1.webp
            // Also handles: static/tiles/Zone/clear/-1/0/-1.webp -> /tiles/Zone/clear/-1/0/-1.webp
            tiles.push('/' + fullPath.replace(/^static\//, ''));
        }
    }

    return tiles;
}

async function main() {
    const allTiles = await findTiles(TILES_DIR);

    // Group by zoom level
    const zoomLevels = {};
    for (const tile of allTiles) {
        // Extract zoom level from path: /tiles/Zone/{zoom}/x/y.webp or /tiles/Zone/{variant}/{zoom}/x/y.webp
        const match = tile.match(/\/tiles\/[^/]+\/(?:(?:clear|open)\/)?(-?\d+)\//);
        if (match) {
            const zoom = match[1];
            if (PRECACHE_ZOOM_LEVELS.includes(zoom)) {
                if (!zoomLevels[zoom]) {
                    zoomLevels[zoom] = { tiles: [] };
                }
                zoomLevels[zoom].tiles.push(tile);
            }
        }
    }

    // Add counts
    for (const zoom of Object.keys(zoomLevels)) {
        zoomLevels[zoom].count = zoomLevels[zoom].tiles.length;
    }

    const manifest = { zoom_levels: zoomLevels };

    await writeFile(OUTPUT_FILE, JSON.stringify(manifest, null, 2));

    const totalTiles = Object.values(zoomLevels).reduce((sum, z) => sum + z.count, 0);
    console.log(
        `Generated ${OUTPUT_FILE}: ${totalTiles} tiles across ${Object.keys(zoomLevels).length} zoom levels`
    );
}

main().catch(console.error);
