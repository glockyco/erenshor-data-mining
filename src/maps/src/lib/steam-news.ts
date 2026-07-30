/**
 * Detect Erenshor's latest patch from the Steam news feed.
 *
 * Erenshor has no usable version numbers: the store reports "0.7" across
 * unnumbered patches, and `ISteamApps/UpToDateCheck` rejects the app outright.
 * The Steam build ID identifies a build precisely, but Steam only publishes the
 * timestamp of the build that is *currently* public, so a build ID alone cannot
 * tell a reader whether the site's data is stale.
 *
 * The news feed can. Erenshor's developer titles every patch announcement with
 * its date ("7/26/26 - Patch Notes", "7/24/26 - Hotfix"), and the announcement
 * lands within minutes of the build going public. Comparing the newest such
 * announcement against the exported build's date is therefore a reliable
 * staleness signal that needs no credentials.
 */

/** A patch announcement from the Steam news feed. */
export interface PatchAnnouncement {
	title: string;
	/** Publication time in Unix seconds. */
	publishedAt: number;
	url: string;
}

/**
 * Erenshor's patch announcements are titled `M/D/YY - <summary>`. Matching the
 * convention is what distinguishes a patch from a sale or event post. A feed
 * with no conforming item yields null rather than a guess, so a convention
 * change degrades to showing nothing instead of asserting something false.
 */
const PATCH_TITLE = /^\s*\d{1,2}\/\d{1,2}\/\d{2,4}\s*-\s*\S/;

function readTag(item: string, tag: string): string | null {
	const match = item.match(new RegExp(`<${tag}>([\\s\\S]*?)</${tag}>`));
	if (!match) return null;

	const cdata = match[1].match(/^\s*<!\[CDATA\[([\s\S]*?)\]\]>\s*$/);
	// `&amp;` unescapes last so an encoded entity in the source text (`&amp;lt;`)
	// survives as literal `&lt;` instead of decoding twice into a tag.
	return (cdata ? cdata[1] : match[1])
		.trim()
		.replace(/&lt;/g, '<')
		.replace(/&gt;/g, '>')
		.replace(/&quot;/g, '"')
		.replace(/&#0?39;|&apos;/g, "'")
		.replace(/&amp;/g, '&');
}

/**
 * Return the most recently published patch announcement, or null when the feed
 * is unparseable or contains none.
 *
 * Items are compared by publication date rather than trusting feed order.
 */
export function parseLatestPatch(rss: string | null | undefined): PatchAnnouncement | null {
	if (!rss) return null;

	let latest: PatchAnnouncement | null = null;
	for (const [, item] of rss.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
		const title = readTag(item, 'title');
		const pubDate = readTag(item, 'pubDate');
		const url = readTag(item, 'link');
		if (!title || !pubDate || !url || !PATCH_TITLE.test(title)) continue;

		const parsed = Date.parse(pubDate);
		if (Number.isNaN(parsed)) continue;

		const announcement = { title, publishedAt: Math.floor(parsed / 1000), url };
		if (!latest || announcement.publishedAt > latest.publishedAt) latest = announcement;
	}
	return latest;
}

/** How the site's exported data compares to the live game. */
export type FreshnessState = 'current' | 'behind';

export interface Freshness {
	state: FreshnessState;
	/** Whole days between the exported build and the newest patch. */
	daysBehind: number;
	latest: PatchAnnouncement;
}

const DAY_SECONDS = 86400;

/**
 * Compare the exported build's date against the newest patch announcement.
 *
 * Returns null when either side is unknown, so callers omit the indicator
 * rather than implying currency that was never established.
 */
export function compareFreshness(
	buildUpdatedAt: string | null | undefined,
	latest: PatchAnnouncement | null
): Freshness | null {
	if (!buildUpdatedAt || !latest) return null;

	const exportedAt = Date.parse(buildUpdatedAt);
	if (Number.isNaN(exportedAt)) return null;

	const drift = latest.publishedAt - Math.floor(exportedAt / 1000);
	if (drift <= 0) return { state: 'current', daysBehind: 0, latest };
	return { state: 'behind', daysBehind: Math.floor(drift / DAY_SECONDS), latest };
}
