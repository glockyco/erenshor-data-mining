import { describe, expect, it } from 'vitest';
import {
    compareFreshness,
    isNotablyStale,
    parseLatestPatch,
    type PatchAnnouncement
} from './steam-news';

// Shape and content taken from the live feed for app 2382520.
const FEED = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>2382520 RSS Feed</title>
    <item>
      <title>7/24/26 - Patch Notes &amp; Demo Update</title>
      <link><![CDATA[https://store.steampowered.com/news/app/2382520/view/3]]></link>
      <pubDate>Fri, 24 Jul 2026 17:31:36 +0000</pubDate>
    </item>
    <item>
      <title>7/26/26 - Patch Notes</title>
      <link><![CDATA[https://store.steampowered.com/news/app/2382520/view/1]]></link>
      <pubDate>Mon, 27 Jul 2026 03:13:30 +0000</pubDate>
    </item>
    <item>
      <title>7/24/26 - Hotfix</title>
      <link><![CDATA[https://store.steampowered.com/news/app/2382520/view/2]]></link>
      <pubDate>Sat, 25 Jul 2026 03:34:45 +0000</pubDate>
    </item>
  </channel>
</rss>`;

function feedOf(...items: string[]): string {
    return `<rss><channel>${items.join('')}</channel></rss>`;
}

function itemOf(title: string, pubDate: string): string {
    return `<item><title>${title}</title><link>https://example.test/p</link><pubDate>${pubDate}</pubDate></item>`;
}

function patchAt(iso: string): PatchAnnouncement {
    return {
        title: `patch ${iso}`,
        publishedAt: Date.parse(iso) / 1000,
        url: 'https://example.test/p'
    };
}

describe('parseLatestPatch', () => {
    it('returns the newest patch by date rather than by feed order', () => {
        // The newest entry is deliberately second in the document.
        expect(parseLatestPatch(FEED)).toEqual({
            title: '7/26/26 - Patch Notes',
            publishedAt: Date.parse('Mon, 27 Jul 2026 03:13:30 +0000') / 1000,
            url: 'https://store.steampowered.com/news/app/2382520/view/1'
        });
    });

    it('decodes entities and unwraps CDATA links', () => {
        const latest = parseLatestPatch(
            feedOf(
                itemOf('7/24/26 - Patch Notes &amp; Demo Update', 'Fri, 24 Jul 2026 17:31:36 +0000')
            )
        );
        expect(latest?.title).toBe('7/24/26 - Patch Notes & Demo Update');
        expect(parseLatestPatch(FEED)?.url.startsWith('https://')).toBe(true);
    });

    it('ignores announcements that are not patch notes', () => {
        // A sale post must never be read as a game update, or the site would
        // claim to be stale whenever Steam runs a promotion.
        const feed = feedOf(
            itemOf('Summer Sale is live!', 'Tue, 28 Jul 2026 10:00:00 +0000'),
            itemOf('7/26/26 - Patch Notes', 'Mon, 27 Jul 2026 03:13:30 +0000')
        );
        expect(parseLatestPatch(feed)?.title).toBe('7/26/26 - Patch Notes');
    });

    it('returns null when no item follows the patch-title convention', () => {
        expect(
            parseLatestPatch(feedOf(itemOf('Wishlist us!', 'Tue, 28 Jul 2026 10:00:00 +0000')))
        ).toBeNull();
    });

    it('skips items with an unparseable date instead of failing the whole feed', () => {
        const feed = feedOf(
            itemOf('7/28/26 - Patch Notes', 'not a date'),
            itemOf('7/26/26 - Patch Notes', 'Mon, 27 Jul 2026 03:13:30 +0000')
        );
        expect(parseLatestPatch(feed)?.title).toBe('7/26/26 - Patch Notes');
    });

    it.each([null, undefined, '', '<html>404</html>'])(
        'returns null for unusable input %p',
        (input) => {
            expect(parseLatestPatch(input)).toBeNull();
        }
    );
});

describe('compareFreshness', () => {
    // The real state of the site on 2026-07-30: build 24362350 downloaded on the
    // 24th, with the newest announcement published on the 27th.
    const build = '2026-07-24T05:24:35+00:00';
    const latest = patchAt('2026-07-27T03:13:30Z');
    const now = Date.parse('2026-07-30T12:00:00Z');

    it('ages the data against now, not against the newest patch', () => {
        // Six days elapsed, while the newest patch is only three days newer than
        // the build. Staleness is the question the reader is asking.
        expect(compareFreshness(build, latest, now)).toMatchObject({
            state: 'behind',
            daysOld: 6,
            latest
        });
    });

    it('drops the announcement when nothing supersedes the build', () => {
        // Nothing to link to, and nothing to imply, so the caller cannot show a
        // patch link beside a claim of currency.
        expect(compareFreshness('2026-07-28T00:00:00Z', latest, now)).toEqual({
            state: 'current',
            daysOld: 2,
            latest: null
        });
    });

    it('keeps ageing data that no patch has superseded', () => {
        // A quiet game does not make correct data wrong, so age alone is never
        // promoted to `behind`, but the reader still gets to see the age.
        const result = compareFreshness(
            '2026-07-28T00:00:00Z',
            latest,
            Date.parse('2026-10-01T00:00:00Z')
        );
		expect(result).toMatchObject({ state: 'current', daysOld: 65 });
    });

    it('treats a build at the exact patch time as current', () => {
        // Boundary: zero drift is not behind, or a same-second export would flap
        // between states purely on rounding.
        expect(compareFreshness('2026-07-27T03:13:30Z', latest, now)?.state).toBe('current');
    });

    it('calls a build behind when an announcement follows it by an hour', () => {
        // That announcement may well be this build's own notes, since notes lag
        // their build and the recorded time is a local download. Saying the game
        // patched costs one click to disprove; claiming currency the data may not
        // have is the error this signal exists to prevent.
        expect(compareFreshness('2026-07-27T02:13:30Z', latest, now)?.state).toBe('behind');
    });

    it('treats a clock behind the recorded build as brand new rather than negative', () => {
        expect(compareFreshness(build, latest, Date.parse('2026-07-20T00:00:00Z'))?.daysOld).toBe(
            0
        );
    });

    it.each([
        ['an unknown build', null, latest],
        ['an unparseable build date', 'sometime in July', latest],
        ['an unavailable feed', build, null]
    ])('returns null for %s', (_case, buildUpdatedAt, announcement) => {
        expect(compareFreshness(buildUpdatedAt, announcement, now)).toBeNull();
    });
});

describe('isNotablyStale', () => {
    const latest = patchAt('2026-07-27T03:13:30Z');
    const now = Date.parse('2026-07-30T12:00:00Z');

    function freshnessOf(buildUpdatedAt: string) {
        const result = compareFreshness(buildUpdatedAt, latest, now);
        if (!result) throw new Error('fixture produced no comparison');
        return result;
    }

    it('stays quiet while trailing the game is still ordinary refresh latency', () => {
        // Erenshor patches most days, so highlighting this would highlight always.
        expect(isNotablyStale(freshnessOf('2026-07-26T00:00:00Z'))).toBe(false);
    });

    it('highlights a build the game has left a fortnight behind', () => {
        expect(isNotablyStale(freshnessOf('2026-07-10T00:00:00Z'))).toBe(true);
    });

    it('never highlights data that no patch has superseded', () => {
        // Old but not wrong: the game published nothing after this build.
        const current = compareFreshness(
            '2026-08-01T00:00:00Z',
            latest,
            Date.parse('2026-10-01T00:00:00Z')
        );
        expect(current).toMatchObject({ state: 'current' });
        expect(isNotablyStale(current!)).toBe(false);
    });
});
