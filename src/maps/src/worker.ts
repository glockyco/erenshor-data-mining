import { MAPS } from '$lib/maps';

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
    return response.ok && response.headers.get('content-type')?.toLowerCase().startsWith('text/html') === true;
}

export async function handleRequest(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

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
