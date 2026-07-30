/**
 * The site's one dynamic endpoint: Erenshor's recent Steam build history.
 *
 * Lives here rather than in the Worker because the Worker only runs in
 * production. The prerendered pages fetch this path in every environment, so
 * `vite dev` and `vite preview` serve the same handler through a middleware in
 * `vite.config.ts`. Only relative imports are allowed in this file: the Vite
 * config is bundled without SvelteKit's `$lib` alias.
 */
import { parseBuildFeed, type BuildFeed, type GameBuild } from './steam-builds';

export const GAME_VERSION_PATH = '/api/game-version';

/**
 * SteamDB's build feed for the app. Undocumented, but the only source that pairs
 * Steam build IDs with Valve's publish times and the developer's patch notes, and
 * therefore the only way to state exactly how many patches the site's data is
 * missing. See `steam-builds.ts` for why nothing else answers that.
 */
const STEAMDB_BUILD_FEED = 'https://steamdb.info/api/PatchnotesRSS/?appid=2382520';

// SteamDB declares a one-hour TTL on this feed and asks not to be hammered. Both
// TTLs are ten minutes: the colo caches the response so traffic volume never
// translates into upstream hits, and browsers reuse their copy for the same
// window.
const FEED_CACHE_SECONDS = 600;

/**
 * Report Erenshor's recent builds so a client can locate its own build among
 * them and count the patches it is missing.
 *
 * The whole window is returned rather than a precomputed verdict: only the client
 * knows which build its page was rendered from.
 *
 * Upstream failures answer 503 with a short cache window rather than a fake
 * result: the freshness indicator is omitted client-side when this is
 * unavailable, which is honest, whereas a fabricated "current" is not.
 */
export async function handleGameVersion(): Promise<Response> {
    let builds: GameBuild[] = [];
    try {
        const upstream = await fetch(STEAMDB_BUILD_FEED, {
            // A default fetch agent is a plausible block target for a site behind
            // a bot challenge, so present the browser this ultimately serves.
            headers: {
                'user-agent':
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
                accept: 'application/rss+xml, application/xml'
            },
            cf: { cacheTtl: FEED_CACHE_SECONDS, cacheEverything: true }
        } as RequestInit);
        if (upstream.ok) builds = parseBuildFeed(await upstream.text());
    } catch {
        builds = [];
    }

    if (!builds.length) {
        return new Response(JSON.stringify({ error: 'upstream unavailable' }), {
            status: 503,
            headers: {
                'content-type': 'application/json; charset=utf-8',
                'cache-control': 'public, max-age=60'
            }
        });
    }

    const payload: BuildFeed = { builds };
    return new Response(JSON.stringify(payload), {
        headers: {
            'content-type': 'application/json; charset=utf-8',
            'cache-control': `public, max-age=${FEED_CACHE_SECONDS}, s-maxage=${FEED_CACHE_SECONDS}`
        }
    });
}
