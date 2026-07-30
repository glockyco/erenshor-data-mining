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
 * its date ("7/26/26 - Patch Notes", "7/24/26 - Hotfix"), so the newest such
 * announcement tells a reader whether the game has moved on since the site's
 * data was captured, with no credentials needed.
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
    /** Whole days from the build to now, which is what a reader means by stale. */
    daysOld: number;
    /** The announcement the build predates, or null when it predates none. */
    latest: PatchAnnouncement | null;
}

const DAY_SECONDS = 86400;

/**
 * Erenshor patches most days: eleven announcements in the twelve days to
 * 2026-07-27. Trailing the game by a patch or two is therefore the normal state
 * of any dataset refreshed weekly, and highlighting it would mean highlighting
 * permanently, which trains readers to stop seeing the line. This bound marks
 * where the gap stops looking like ordinary refresh latency.
 */
const NOTABLE_DAYS = 14;

/**
 * Date the exported build against the live game.
 *
 * Deliberately reports only whether the game has moved on, never by how many
 * patches. The recorded build time is when this project's install downloaded the
 * build, not when Steam published it, and announcements lag their builds by
 * hours: build 24362350 landed locally at 2026-07-24 05:24 UTC with candidate
 * notes published both 12 and 22 hours later. No rule over those timestamps
 * pairs a build with its own announcement reliably, so any count would be off by
 * one about as often as not. A count is also the wrong question -- the reader
 * wants to know whether to trust the page and how old it is, and both survive
 * the ambiguity intact.
 *
 * Returns null when either side is unknown, so callers omit the indicator rather
 * than implying currency that was never established.
 */
export function compareFreshness(
    buildUpdatedAt: string | null | undefined,
    latest: PatchAnnouncement | null,
    now: number = Date.now()
): Freshness | null {
    if (!buildUpdatedAt || !latest) return null;

    const buildAt = Date.parse(buildUpdatedAt);
    if (Number.isNaN(buildAt)) return null;

    const buildSeconds = Math.floor(buildAt / 1000);
    // A clock behind the recorded build time reads as brand new, never negative.
    const daysOld = Math.max(0, Math.floor((Math.floor(now / 1000) - buildSeconds) / DAY_SECONDS));

    // Ties and near-ties resolve to `behind`. When an announcement within hours
    // of the build might be its own notes, saying the game has patched costs a
    // reader one click to discover otherwise, whereas claiming currency the data
    // may not have is the one error this whole signal exists to avoid.
    if (latest.publishedAt <= buildSeconds) return { state: 'current', daysOld, latest: null };
    return { state: 'behind', daysOld, latest };
}

/** Whether staleness has crossed from routine latency into worth highlighting. */
export function isNotablyStale(freshness: Freshness): boolean {
    return freshness.state === 'behind' && freshness.daysOld >= NOTABLE_DAYS;
}
