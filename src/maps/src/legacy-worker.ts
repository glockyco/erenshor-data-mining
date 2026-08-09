/**
 * Compatibility Worker for `erenshor-maps.wowmuch1.workers.dev`.
 *
 * Shipped companion overlays hardcode the legacy `/map` document and refuse to
 * navigate to another host, so this Worker keeps that document and every
 * runtime resource it loads same-origin. It runs ahead of asset serving
 * (`run_worker_first: true`) because its routing decisions depend on the
 * request hostname, which asset rules cannot express.
 *
 * The canonical host is served by `site-worker.ts`. The canonical branch below
 * is therefore normally unreachable, and is retained deliberately: it keeps
 * this Worker a valid rollback target if the Custom Domain has to be reattached
 * to `erenshor-maps`.
 */
import { GAME_VERSION_PATH, handleGameVersion } from '$lib/game-version';
import { MAPS } from '$lib/maps';

export { GAME_VERSION_PATH };

export interface AssetsBinding {
    fetch(request: Request): Promise<Response>;
}

export interface Env {
    ASSETS: AssetsBinding;
}

export const LEGACY_HOST = 'erenshor-maps.wowmuch1.workers.dev';
export const CANONICAL_HOST = 'erenshor.compendiums.org';
const GSC_TOKEN_PATH = '/google279cf61d0b725839.html';
const GSC_TOKEN_BODY = 'google-site-verification: google279cf61d0b725839.html\n';

function redirectToCanonical(url: URL, pathname = url.pathname): Response {
    return new Response(null, {
        status: 301,
        headers: {
            Location: `https://${CANONICAL_HOST}${pathname}${url.search}`
        }
    });
}

function isHtmlDocument(response: Response): boolean {
    return (
        response.ok &&
        response.headers.get('content-type')?.toLowerCase().startsWith('text/html') === true
    );
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
