/**
 * The site's one dynamic endpoint: the newest Erenshor patch announcement.
 *
 * Lives here rather than in the Worker because the Worker only runs in
 * production. The prerendered pages fetch this path in every environment, so
 * `vite dev` and `vite preview` serve the same handler through a middleware in
 * `vite.config.ts`. Only relative imports are allowed in this file: the Vite
 * config is bundled without SvelteKit's `$lib` alias.
 */
import { parseLatestPatch } from './steam-news';

export const GAME_VERSION_PATH = '/api/game-version';

const STEAM_NEWS_RSS = 'https://store.steampowered.com/feeds/news/app/2382520/?cc=US&l=en';

// The site is prerendered, so the live patch check cannot run at render time.
// Both TTLs are ten minutes: the colo caches the Steam response so traffic
// volume never translates into upstream hits, and browsers reuse their copy for
// the same window.
const PATCH_CACHE_SECONDS = 600;

/**
 * Report the newest Erenshor patch announcement so a client can tell whether
 * the exported data predates it.
 *
 * Upstream failures answer 503 with a short cache window rather than a fake
 * result: the freshness indicator is omitted client-side when this is
 * unavailable, which is honest, whereas a fabricated "current" is not.
 */
export async function handleGameVersion(): Promise<Response> {
    let latest = null;
    try {
        const upstream = await fetch(STEAM_NEWS_RSS, {
            cf: { cacheTtl: PATCH_CACHE_SECONDS, cacheEverything: true }
        } as RequestInit);
        if (upstream.ok) latest = parseLatestPatch(await upstream.text());
    } catch {
        latest = null;
    }

    if (!latest) {
        return new Response(JSON.stringify({ error: 'upstream unavailable' }), {
            status: 503,
            headers: {
                'content-type': 'application/json; charset=utf-8',
                'cache-control': 'public, max-age=60'
            }
        });
    }

    return new Response(JSON.stringify(latest), {
        headers: {
            'content-type': 'application/json; charset=utf-8',
            'cache-control': `public, max-age=${PATCH_CACHE_SECONDS}, s-maxage=${PATCH_CACHE_SECONDS}`
        }
    });
}
