import { MAPS } from '$lib/maps';
import { parseLatestPatch } from '$lib/steam-news';

export interface AssetsBinding {
    fetch(request: Request): Promise<Response>;
}

export interface Env {
    ASSETS: AssetsBinding;
}

export const LEGACY_HOST = 'erenshor-maps.wowmuch1.workers.dev';
export const CANONICAL_HOST = 'erenshor.compendiums.org';
export const GAME_VERSION_PATH = '/api/game-version';
const GSC_TOKEN_PATH = '/google279cf61d0b725839.html';
const GSC_TOKEN_BODY = 'google-site-verification: google279cf61d0b725839.html\n';
const STEAM_NEWS_RSS = 'https://store.steampowered.com/feeds/news/app/2382520/?cc=US&l=en';

// The site is prerendered, so the live patch check cannot run at render time.
// This endpoint is the one dynamic seam. Both TTLs are ten minutes: the colo
// caches the Steam response so traffic volume never translates into upstream
// hits, and browsers reuse their copy for the same window.
const PATCH_CACHE_SECONDS = 600;

/**
 * Report the newest Erenshor patch announcement so a client can tell whether
 * the exported data predates it.
 *
 * Upstream failures answer 503 with a short cache window rather than a fake
 * result: the freshness indicator is omitted client-side when this is
 * unavailable, which is honest, whereas a fabricated "current" is not.
 */
async function handleGameVersion(): Promise<Response> {
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

function redirectToCanonical(url: URL, pathname = url.pathname): Response {
    return new Response(null, {
        status: 301,
        headers: {
            Location: `https://${CANONICAL_HOST}${pathname}${url.search}`
        }
    });
}

function isHtmlDocument(response: Response): boolean {
    return response.ok && response.headers.get('content-type')?.toLowerCase().startsWith('text/html') === true;
}

export async function handleRequest(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // Served from every host: the prerendered pages that consume it exist on
    // both, and it carries no host-specific content.
    if (url.pathname === GAME_VERSION_PATH) {
        return handleGameVersion();
    }

    // The canonical host is a transparent view of the one shared asset set.
    if (url.hostname === CANONICAL_HOST) {
        return env.ASSETS.fetch(request);
    }
    if (url.hostname !== LEGACY_HOST) {
        return env.ASSETS.fetch(request);
    }

    const { pathname } = url;

    // Companion overlays require these documents and all of their runtime
    // requests to remain on their original same-origin workers.dev host.
    if (pathname === GSC_TOKEN_PATH) {
        return new Response(GSC_TOKEN_BODY, {
            headers: { 'content-type': 'text/html; charset=utf-8' }
        });
    }
    if (pathname === '/map' || pathname === '/map/') {
        return env.ASSETS.fetch(request);
    }

    if (pathname === '/sitemap.xml') {
        return redirectToCanonical(url);
    }

    // Root map links are an exact, case-sensitive registry lookup. No
    // decoding, lowercasing, or trailing-slash normalization is intentional.
    if (pathname.startsWith('/') && !pathname.slice(1).includes('/')) {
        const mapKey = pathname.slice(1);
        if (Object.hasOwn(MAPS, mapKey)) {
            return redirectToCanonical(url, `/maps/${mapKey}`);
        }
    }

    const response = await env.ASSETS.fetch(request);
    return isHtmlDocument(response) ? redirectToCanonical(url) : response;
}

export default {
    fetch(request: Request, env: Env): Promise<Response> {
        return handleRequest(request, env);
    }
};
