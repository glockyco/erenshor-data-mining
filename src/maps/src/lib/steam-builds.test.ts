import { describe, expect, it } from 'vitest';
import {
    compareFreshness,
    isNotablyStale,
    parseBuildFeed,
    type BuildProvenance,
    type GameBuild
} from './steam-builds';

function itemOf(buildId: string, pubDate: string, notes?: string): string {
    const description = notes ? `${notes} (SteamDB Build ${buildId})` : `SteamDB Build ${buildId}`;
    return (
        `<item><guid isPermaLink="false">build#${buildId}</guid>` +
        `<title>Erenshor update</title>` +
        `<link>https://steamdb.info/patchnotes/${buildId}/?utm_source=rss&amp;utm_medium=rss</link>` +
        `<description>${description}</description>` +
        `<pubDate>${pubDate}</pubDate>` +
        `<media:thumbnail width="1200" height="630" url="https://steamdb.info/patchnotes/${buildId}.png"/></item>`
    );
}

function feedOf(...items: string[]): string {
    return `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>SteamDB Builds for Erenshor</title>${items.join('')}</channel></rss>`;
}

// The real window on 2026-07-30, taken from the live feed for app 2382520. Build
// 24362350 is the exported one and shipped without notes; 24361753 is one of the
// four rebuilds Erenshor published on 23 July.
const OURS = '24362350';
const FEED = feedOf(
    itemOf('24405256', 'Mon, 27 Jul 2026 03:08:59 +0000', '7/26/26 - Patch Notes'),
    itemOf('24385406', 'Sat, 25 Jul 2026 03:33:04 +0000', '7/24/26 - Hotfix'),
    itemOf(
        '24378601',
        'Fri, 24 Jul 2026 17:19:15 +0000',
        '7/24/26 - Patch Notes &amp; Demo Update'
    ),
    itemOf(OURS, 'Thu, 23 Jul 2026 21:53:44 +0000'),
    itemOf('24362007', 'Thu, 23 Jul 2026 21:26:36 +0000', '7/23/26 - Patch Notes'),
    itemOf('24361753', 'Thu, 23 Jul 2026 21:09:17 +0000')
);

const PROVENANCE: BuildProvenance = {
    gameBuildId: OURS,
    buildPublishedAt: '2026-07-23T21:53:44+00:00'
};
const NOW = Date.parse('2026-07-30T12:00:00Z');

describe('parseBuildFeed', () => {
    it('reads the build id from the guid rather than from any prose', () => {
        expect(parseBuildFeed(FEED).map((build) => build.buildId)).toEqual([
            '24405256',
            '24385406',
            '24378601',
            OURS,
            '24362007',
            '24361753'
        ]);
    });

    it('reports a build with its publish time, notes title, and page', () => {
        expect(parseBuildFeed(FEED)[0]).toEqual({
            buildId: '24405256',
            publishedAt: Date.parse('Mon, 27 Jul 2026 03:08:59 +0000') / 1000,
            notesTitle: '7/26/26 - Patch Notes',
            url: 'https://steamdb.info/patchnotes/24405256/?utm_source=rss&utm_medium=rss'
        });
    });

    it('distinguishes an unannounced rebuild from an announced patch', () => {
        // The description degrades to the bare build label, which must not be
        // mistaken for a patch title, or silent rebuilds would count as patches.
        const builds = parseBuildFeed(FEED);
        expect(builds.find((build) => build.buildId === OURS)?.notesTitle).toBeNull();
        expect(builds.find((build) => build.buildId === '24385406')?.notesTitle).toBe(
            '7/24/26 - Hotfix'
        );
    });

    it('orders the window newest first rather than trusting feed order', () => {
        const scrambled = feedOf(
            itemOf('2', 'Thu, 23 Jul 2026 21:00:00 +0000', 'older'),
            itemOf('3', 'Mon, 27 Jul 2026 03:00:00 +0000', 'newest'),
            itemOf('1', 'Fri, 24 Jul 2026 17:00:00 +0000', 'middle')
        );
        expect(parseBuildFeed(scrambled).map((build) => build.notesTitle)).toEqual([
            'newest',
            'middle',
            'older'
        ]);
    });

    it('skips an unusable entry instead of discarding the whole window', () => {
        const feed = feedOf(
            '<item><guid isPermaLink="false">news#900</guid><link>https://x.test/</link><pubDate>Mon, 27 Jul 2026 03:00:00 +0000</pubDate></item>',
            itemOf('24405256', 'not a date', 'unparseable'),
            itemOf('24385406', 'Sat, 25 Jul 2026 03:33:04 +0000', 'kept')
        );
        expect(parseBuildFeed(feed).map((build) => build.notesTitle)).toEqual(['kept']);
    });

    it.each([null, undefined, '', '<html>403 Forbidden</html>'])(
        'returns nothing for unusable input %p',
        (input) => {
            expect(parseBuildFeed(input)).toEqual([]);
        }
    );
});

describe('compareFreshness', () => {
    const builds = parseBuildFeed(FEED);

    it('counts the announced builds published after the exported one', () => {
        // Three builds are newer and all three were announced. The exported build
        // is found by ID, so this is a count rather than a timestamp comparison.
        expect(compareFreshness(PROVENANCE, builds, NOW)).toMatchObject({
            state: 'behind',
            patchesBehind: 3,
            saturated: false,
            latest: { buildId: '24405256', notesTitle: '7/26/26 - Patch Notes' }
        });
    });

    it('excludes unannounced rebuilds from the count', () => {
        // From 24361753 five builds are newer, but 24362350 shipped without notes,
        // and a player counts patches, not depot uploads.
        const stamp = { gameBuildId: '24361753', buildPublishedAt: '2026-07-23T21:09:17+00:00' };
        expect(compareFreshness(stamp, builds, NOW)).toMatchObject({
            state: 'behind',
            patchesBehind: 4
        });
    });

    it('ages the data from the build publication, not from the newest patch', () => {
        // Valve published the exported build on 23 July, so it is six days old on
        // the 30th even though the newest patch is only three days newer than it.
        expect(compareFreshness(PROVENANCE, builds, NOW)?.daysOld).toBe(6);
    });

    it('reports current when nothing announced followed the exported build', () => {
        const stamp = { gameBuildId: '24405256', buildPublishedAt: '2026-07-27T03:08:59+00:00' };
        expect(compareFreshness(stamp, builds, NOW)).toEqual({
            state: 'current',
            patchesBehind: 0,
            saturated: false,
            daysOld: 3,
            latest: null
        });
    });

    it('treats a build that only precedes rebuilds as current', () => {
        // 24362007 is followed by 24362350, which shipped without notes. Nothing a
        // player would call a patch has landed, so nothing is claimed.
        const stamp = { gameBuildId: '24362007', buildPublishedAt: '2026-07-23T21:26:36+00:00' };
        const window = builds.filter(
            (build) => build.publishedAt <= Date.parse('2026-07-23T22:00:00Z') / 1000
        );
        expect(compareFreshness(stamp, window, NOW)?.state).toBe('current');
    });

    it('falls back to publish time and marks the count a floor past the window', () => {
        // An export older than the feed window has no ID left to match, but every
        // build in the window still provably postdates it.
        const stamp = { gameBuildId: '24200000', buildPublishedAt: '2026-07-01T00:00:00Z' };
        expect(compareFreshness(stamp, builds, NOW)).toMatchObject({
            state: 'behind',
            patchesBehind: 4,
            saturated: true
        });
    });

    it('treats a clock behind the build publication as brand new, never negative', () => {
        expect(
            compareFreshness(PROVENANCE, builds, Date.parse('2026-07-20T00:00:00Z'))?.daysOld
        ).toBe(0);
    });

    it.each([
        ['unknown provenance', null, builds],
        ['an unparseable publish time', { gameBuildId: OURS, buildPublishedAt: 'in July' }, builds],
        ['an unavailable feed', PROVENANCE, null],
        ['an empty window', PROVENANCE, []]
    ])('returns null for %s', (_case, stamp, window) => {
        expect(
            compareFreshness(stamp as BuildProvenance | null, window as GameBuild[] | null, NOW)
        ).toBeNull();
    });
});

describe('isNotablyStale', () => {
    const builds = parseBuildFeed(FEED);

    it('stays quiet while trailing the game is still ordinary refresh latency', () => {
        // Erenshor patches most days, so highlighting three would highlight always.
        const result = compareFreshness(PROVENANCE, builds, NOW);
        expect(result).toMatchObject({ patchesBehind: 3, daysOld: 6 });
        expect(isNotablyStale(result!)).toBe(false);
    });

    it('highlights an export the game has left many patches behind', () => {
        // Five announced builds in three days: a busy period, not a stale week.
        const busy = parseBuildFeed(
            feedOf(
                ...[1, 2, 3, 4, 5].map((n) =>
                    itemOf(`2450000${n}`, `Mon, 2${n} Jul 2026 03:00:00 +0000`, `patch ${n}`)
                )
            )
        );
        const stamp = { gameBuildId: '24200000', buildPublishedAt: '2026-07-20T00:00:00Z' };
        const result = compareFreshness(stamp, busy, NOW);
        expect(result).toMatchObject({ patchesBehind: 5, daysOld: 10 });
        expect(isNotablyStale(result!)).toBe(true);
    });

    it('highlights a long-stale export even when few patches shipped', () => {
        // A quiet fortnight still means the data went unrefreshed for one.
        const result = compareFreshness(PROVENANCE, builds, Date.parse('2026-08-20T00:00:00Z'));
        expect(result).toMatchObject({ patchesBehind: 3 });
        expect(isNotablyStale(result!)).toBe(true);
    });

    it('never highlights data that no announced build has superseded', () => {
        const stamp = { gameBuildId: '24405256', buildPublishedAt: '2026-07-27T03:08:59+00:00' };
        const current = compareFreshness(stamp, builds, Date.parse('2026-10-01T00:00:00Z'));
        expect(current).toMatchObject({ state: 'current' });
        expect(isNotablyStale(current!)).toBe(false);
    });
});
