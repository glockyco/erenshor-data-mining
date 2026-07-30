import { describe, expect, it } from 'vitest';
import { compareFreshness, parseLatestPatch, type PatchAnnouncement } from './steam-news';

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
			feedOf(itemOf('7/24/26 - Patch Notes &amp; Demo Update', 'Fri, 24 Jul 2026 17:31:36 +0000'))
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
		expect(parseLatestPatch(feedOf(itemOf('Wishlist us!', 'Tue, 28 Jul 2026 10:00:00 +0000')))).toBeNull();
	});

	it('skips items with an unparseable date instead of failing the whole feed', () => {
		const feed = feedOf(
			itemOf('7/28/26 - Patch Notes', 'not a date'),
			itemOf('7/26/26 - Patch Notes', 'Mon, 27 Jul 2026 03:13:30 +0000')
		);
		expect(parseLatestPatch(feed)?.title).toBe('7/26/26 - Patch Notes');
	});

	it.each([null, undefined, '', '<html>404</html>'])('returns null for unusable input %p', (input) => {
		expect(parseLatestPatch(input)).toBeNull();
	});
});

describe('compareFreshness', () => {
	const latest: PatchAnnouncement = {
		title: '7/26/26 - Patch Notes',
		publishedAt: Date.parse('2026-07-27T03:13:30Z') / 1000,
		url: 'https://example.test/p'
	};

	it('reports how far a stale export lags the newest patch', () => {
		const result = compareFreshness('2026-07-24T05:24:35+00:00', latest);
		expect(result).toMatchObject({ state: 'behind', daysBehind: 2 });
	});

	it('reports current when the export postdates the newest patch', () => {
		expect(compareFreshness('2026-07-28T00:00:00Z', latest)?.state).toBe('current');
	});

	it('treats an export at the exact patch time as current', () => {
		// Boundary: drift of zero is not "behind", or a same-minute export would
		// flap between states purely on rounding.
		expect(compareFreshness('2026-07-27T03:13:30Z', latest)?.state).toBe('current');
	});

	it('floors a partial day rather than rounding a stale export up to current', () => {
		const result = compareFreshness('2026-07-26T15:13:30Z', latest);
		expect(result).toMatchObject({ state: 'behind', daysBehind: 0 });
	});

	it('returns null when either side is unknown', () => {
		expect(compareFreshness(null, latest)).toBeNull();
		expect(compareFreshness('2026-07-24T05:24:35Z', null)).toBeNull();
		expect(compareFreshness('not a date', latest)).toBeNull();
	});
});
