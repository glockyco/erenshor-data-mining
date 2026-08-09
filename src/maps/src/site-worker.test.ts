import { afterEach, describe, expect, it, vi } from 'vitest';
import { GAME_VERSION_PATH } from '$lib/game-version';
import worker, { type AssetsBinding, type Env } from './site-worker';

const CANONICAL_HOST = 'erenshor.compendiums.org';

function createAssets() {
    const calls: string[] = [];
    const assets = {
        fetch(request: Request) {
            calls.push(request.url);
            return Promise.resolve(new Response('missing', { status: 404 }));
        }
    };
    return { assets, calls };
}

function envWith(assets: AssetsBinding): Env {
    return { ASSETS: assets };
}

function request(path: string): Request {
    return new Request(`https://${CANONICAL_HOST}${path}`);
}

describe('canonical Worker routing', () => {
    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('answers the game-version endpoint without consulting static assets', async () => {
        const { assets, calls } = createAssets();
        vi.stubGlobal(
            'fetch',
            vi.fn(() =>
                Promise.resolve(
                    new Response(
                        `<rss><channel><item>
                            <guid isPermaLink="false">build#24405256</guid>
                            <link>https://steamdb.info/patchnotes/24405256/</link>
                            <description>7/26/26 - Patch Notes (SteamDB Build 24405256)</description>
                            <pubDate>Mon, 27 Jul 2026 03:08:59 +0000</pubDate>
                        </item></channel></rss>`
                    )
                )
            )
        );

        const response = await worker.fetch(request(GAME_VERSION_PATH), envWith(assets));

        expect(response.status).toBe(200);
        expect(await response.json()).toHaveProperty('builds');
        expect(calls).toEqual([]);
    });

    it('delegates an asset miss unchanged so the deliberate 404 survives', async () => {
        const { assets, calls } = createAssets();

        const response = await worker.fetch(request('/unknown-zone?from=test'), envWith(assets));

        expect(response.status).toBe(404);
        expect(response.headers.get('location')).toBeNull();
        expect(calls).toEqual([`https://${CANONICAL_HOST}/unknown-zone?from=test`]);
    });

    it.each(['/FernallaField', '/map', '/service-worker.js'])(
        'never redirects %s, because the canonical host owns no host-aware routing',
        async (path) => {
            const { assets } = createAssets();

            const response = await worker.fetch(request(path), envWith(assets));

            expect(response.status).toBe(404);
            expect(response.headers.get('location')).toBeNull();
        }
    );
});
