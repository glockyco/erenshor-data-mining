/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

import { version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;

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
            await precacheEssentialTiles();
            await sw.skipWaiting();
        })()
    );
});

sw.addEventListener('activate', (event) => {
    event.waitUntil(
        (async () => {
            // Delete every other cache, including the database caches that
            // earlier versions of this worker created.
            const keys = await caches.keys();
            await Promise.all(
                keys.filter((key) => key !== TILES_CACHE_NAME).map((key) => caches.delete(key))
            );
            await sw.clients.claim();
        })()
    );
});

sw.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    if (event.request.method !== 'GET') return;
    if (url.origin !== sw.location.origin) return;

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
