import { describe, expect, it } from 'vitest';
import worker, { CANONICAL_HOST, LEGACY_HOST, handleRequest, type Env } from './worker';

const html = '<!doctype html><html><body>page</body></html>';
const resources = [
    ['/service-worker.js', 'application/javascript'],
    ['/_app/immutable/entry/start.js', 'application/javascript'],
    ['/_app/data/default.json', 'application/json'],
    ['/db/erenshor.sqlite', 'application/vnd.sqlite3'],
    ['/tiles/Abyssal/0/0/0.webp', 'image/webp']
] as const;

function createAssets() {
    const calls: string[] = [];
    const assets = {
        fetch(request: Request) {
            calls.push(request.url);
            const url = new URL(request.url);
            if (
                url.pathname === '/' ||
                url.pathname === '/map' ||
                url.pathname === '/map/' ||
                url.pathname === '/zone-maps' ||
                url.pathname === '/maps/Abyssal' ||
                url.pathname === '/google279cf61d0b725839.html'
            ) {
                return Promise.resolve(new Response(html, { headers: { 'content-type': 'text/html; charset=utf-8' } }));
            }
            const resource = resources.find(([path]) => path === url.pathname);
            if (resource) {
                return Promise.resolve(new Response(resource[0], { headers: { 'content-type': resource[1] } }));
            }
            return Promise.resolve(new Response('missing', { status: 404 }));
        }
    };
    return { assets, calls };
}

function envWith(assets: ReturnType<typeof createAssets>['assets']): Env {
    return { ASSETS: assets };
}

function request(host: string, path: string): Request {
    return new Request(`https://${host}${path}`);
}

describe('dual-host Worker routing', () => {
    it('delegates canonical-host requests unchanged to the assets binding', async () => {
        const { assets, calls } = createAssets();
        const response = await handleRequest(request(CANONICAL_HOST, '/zone-maps?from=test'), envWith(assets));

        expect(response.status).toBe(200);
        expect(await response.text()).toBe(html);
        expect(calls).toEqual([`https://${CANONICAL_HOST}/zone-maps?from=test`]);
    });

    it.each(['/map?sel=enemy%3AEvadne+the+Corrupted', '/map/?sel=enemy%3AEvadne+the+Corrupted'])(
        'serves legacy overlay document %s directly with its query',
        async (path) => {
            const { assets, calls } = createAssets();
            const response = await handleRequest(request(LEGACY_HOST, path), envWith(assets));

            expect(response.status).toBe(200);
            expect(response.headers.get('location')).toBeNull();
            expect(calls).toEqual([`https://${LEGACY_HOST}${path}`]);
        }
    );

    it.each(resources.flatMap(([path]) => [
        [CANONICAL_HOST, path],
        [LEGACY_HOST, path]
    ] as const))('keeps runtime resource %s on %s unchanged', async (host, path) => {
        const { assets, calls } = createAssets();
        const response = await handleRequest(request(host, path), envWith(assets));

        expect(response.status).toBe(200);
        expect(response.headers.get('location')).toBeNull();
        expect(await response.text()).toBe(path);
        expect(calls).toEqual([`https://${host}${path}`]);
    });

    it('serves the legacy GSC token directly', async () => {
        const { assets } = createAssets();
        const response = await handleRequest(
            request(LEGACY_HOST, '/google279cf61d0b725839.html'),
            envWith(assets)
        );

        expect(response.status).toBe(200);
        expect(response.headers.get('location')).toBeNull();
        expect(response.headers.get('content-type')).toContain('text/html');
        expect(await response.text()).toBe(html);
    });

    it('redirects an exact mixed-case root map key', async () => {
        const { assets, calls } = createAssets();
        const response = await handleRequest(
            request(LEGACY_HOST, '/FernallaField?marker=Spawn%2FOne'),
            envWith(assets)
        );

        expect(response.status).toBe(301);
        expect(response.headers.get('location')).toBe(
            `https://${CANONICAL_HOST}/maps/FernallaField?marker=Spawn%2FOne`
        );
        expect(calls).toEqual([]);
    });

    it.each(['/fernallafield', '/FernallaField/', '/unknown-zone', '/zones/Abyssal'])(
        'preserves asset 404 for wrong-case, unknown, or reserved path %s',
        async (path) => {
            const { assets } = createAssets();
            const response = await handleRequest(request(LEGACY_HOST, path), envWith(assets));

            expect(response.status).toBe(404);
            expect(response.headers.get('location')).toBeNull();
        }
    );

    it('redirects a successful legacy HTML document to the same canonical path', async () => {
        const { assets } = createAssets();
        const response = await handleRequest(
            request(LEGACY_HOST, '/zone-maps?tab=zones%2Frare'),
            envWith(assets)
        );

        expect(response.status).toBe(301);
        expect(response.headers.get('location')).toBe(
            `https://${CANONICAL_HOST}/zone-maps?tab=zones%2Frare`
        );
    });

    it('redirects sitemap requests while preserving their query', async () => {
        const { assets, calls } = createAssets();
        const response = await handleRequest(
            request(LEGACY_HOST, '/sitemap.xml?format=xml%2Bgzip'),
            envWith(assets)
        );

        expect(response.status).toBe(301);
        expect(response.headers.get('location')).toBe(
            `https://${CANONICAL_HOST}/sitemap.xml?format=xml%2Bgzip`
        );
        expect(calls).toEqual([]);
    });

    it('uses the default export as the same request handler', async () => {
        const { assets } = createAssets();
        const response = await worker.fetch(request(LEGACY_HOST, '/map'), envWith(assets));
        expect(response.status).toBe(200);
    });
});
