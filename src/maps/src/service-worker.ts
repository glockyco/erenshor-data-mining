/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

import { files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;

const DB_CACHE_NAME = `db-cache-${version}`;
const TILES_CACHE_NAME = `tiles-cache-${version}`;

// Zoom levels to pre-cache for offline map overview
const PRECACHE_ZOOM_LEVELS = ['-4', '-3', '-2', '-1'];

interface TilesManifest {
    zoom_levels: Record<
        string,
        {
            count: number;
            tiles: string[];
        }
    >;
}

async function precacheDatabase(): Promise<void> {
    const dbFile = files.find((f) => f.endsWith('.sqlite'));
    if (!dbFile) return;

    try {
        const cache = await caches.open(DB_CACHE_NAME);
        const response = await fetch(dbFile);
        if (response.ok) {
            await cache.put(dbFile, response);
        }
    } catch {
        // DB fetch failed, skip silently
    }
}

async function precacheEssentialTiles(): Promise<void> {
    try {
        const response = await fetch('/tiles/tiles-manifest.json');
        if (!response.ok) return;

        const manifest: TilesManifest = await response.json();
        const cache = await caches.open(TILES_CACHE_NAME);

        const tilesToCache: string[] = [];
        for (const zoom of PRECACHE_ZOOM_LEVELS) {
            const zoomData = manifest.zoom_levels[zoom];
            if (zoomData) {
                tilesToCache.push(...zoomData.tiles);
            }
        }

        // Fetch tiles in batches to avoid overwhelming network
        const batchSize = 20;
        for (let i = 0; i < tilesToCache.length; i += batchSize) {
            const batch = tilesToCache.slice(i, i + batchSize);
            await Promise.all(
                batch.map(async (url) => {
                    try {
                        const tileResponse = await fetch(url);
                        if (tileResponse.ok) {
                            await cache.put(url, tileResponse);
                        }
                    } catch {
                        // Tile fetch failed, skip silently
                    }
                })
            );
        }
    } catch {
        // Manifest fetch failed, skip tile pre-caching
    }
}

sw.addEventListener('install', (event) => {
    event.waitUntil(
        (async () => {
            await Promise.all([precacheDatabase(), precacheEssentialTiles()]);
            await sw.skipWaiting();
        })()
    );
});

sw.addEventListener('activate', (event) => {
    event.waitUntil(
        (async () => {
            const keys = await caches.keys();
            await Promise.all(
                keys
                    .filter((key) => key !== DB_CACHE_NAME && key !== TILES_CACHE_NAME)
                    .map((key) => caches.delete(key))
            );
            await sw.clients.claim();
        })()
    );
});

sw.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    if (event.request.method !== 'GET') return;
    if (url.origin !== sw.location.origin) return;

    // Database: cache-first
    if (url.pathname.endsWith('.sqlite')) {
        event.respondWith(
            (async () => {
                const cache = await caches.open(DB_CACHE_NAME);
                const cached = await cache.match(event.request);
                if (cached) return cached;

                const response = await fetch(event.request);
                if (response.ok) {
                    cache.put(event.request, response.clone());
                }
                return response;
            })()
        );
        return;
    }

    // Tiles and world map image: cache-first
    if (
        (url.pathname.startsWith('/tiles/') && url.pathname.endsWith('.webp')) ||
        url.pathname === '/erenshor-world-map.webp'
    ) {
        event.respondWith(
            (async () => {
                const cached = await caches.match(event.request);
                if (cached) return cached;

                const response = await fetch(event.request);
                if (response.ok) {
                    const cache = await caches.open(TILES_CACHE_NAME);
                    cache.put(event.request, response.clone());
                }
                return response;
            })()
        );
        return;
    }

    // Everything else: let browser handle normally
});

sw.addEventListener('message', (event) => {
    if (event.data?.type === 'SKIP_WAITING') {
        sw.skipWaiting();
    }

    if (event.data?.type === 'GET_VERSION') {
        event.ports[0]?.postMessage({ version });
    }
});
