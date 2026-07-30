/**
 * Date the site's exported data against Erenshor's live build history.
 *
 * Erenshor has no usable version numbers: the store reports "0.7" across
 * unnumbered patches, and `ISteamApps/UpToDateCheck` rejects the app outright.
 * Valve's own PICS data exposes only the build that is *currently* public, so it
 * can say what the game is on but never how far behind anything else is.
 *
 * SteamDB's build feed can, and exactly. Every entry carries the Steam build ID
 * as its GUID, Valve's publish time, and the developer's own patch-notes title
 * when that build was announced. Locating the exported build by ID makes the
 * comparison an identity match rather than a timestamp guess: the count of newer
 * announced builds is the true number of patches the data is missing, with no
 * clock on this machine or any other involved.
 */

/** One published Steam build of the game. */
export interface GameBuild {
    buildId: string;
    /** Valve's publish time, in Unix seconds. */
    publishedAt: number;
    /** The developer's announcement title, or null for an unannounced rebuild. */
    notesTitle: string | null;
    /** SteamDB's patch-notes page for this build. */
    url: string;
}

/** Payload of the game-version endpoint. */
export interface BuildFeed {
    /** Recent builds, newest first. Never empty. */
    builds: GameBuild[];
}

function readTag(item: string, tag: string): string | null {
    const match = item.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`));
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
 * Strip the `SteamDB Build <id>` label every description carries.
 *
 * An announced build parenthesises the label after the developer's title
 * (`7/26/26 - Patch Notes (SteamDB Build 24405256)`); a build that shipped
 * without notes carries the bare label alone. What remains is therefore the
 * announcement title, or nothing at all. Those unannounced rebuilds are real
 * builds and are common -- Erenshor shipped four on 2026-07-23 -- but they are
 * not what a player means by a patch, so they must stay distinguishable.
 */
function readNotesTitle(item: string, buildId: string): string | null {
    const description = readTag(item, 'description');
    if (!description) return null;
    // The id is digits, so it needs no escaping here.
    const title = description.replace(new RegExp(`\\(?SteamDB Build ${buildId}\\)?$`), '').trim();
    return title || null;
}

/**
 * Return the builds in the feed window, newest first, or an empty list when the
 * feed is unparseable or contains none.
 *
 * Items are ordered by publish time rather than trusting feed order, and one
 * malformed entry is skipped rather than discarding the whole window.
 */
export function parseBuildFeed(rss: string | null | undefined): GameBuild[] {
    if (!rss) return [];

    const builds: GameBuild[] = [];
    for (const [, item] of rss.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
        const buildId = readTag(item, 'guid')?.match(/^build#(\d+)$/)?.[1];
        const pubDate = readTag(item, 'pubDate');
        const url = readTag(item, 'link');
        if (!buildId || !pubDate || !url) continue;

        const parsed = Date.parse(pubDate);
        if (Number.isNaN(parsed)) continue;

        builds.push({
            buildId,
            publishedAt: Math.floor(parsed / 1000),
            notesTitle: readNotesTitle(item, buildId),
            url
        });
    }
    return builds.sort((a, b) => b.publishedAt - a.publishedAt);
}

/** How the site's exported data compares to the live game. */
export type FreshnessState = 'current' | 'behind';

export interface Freshness {
    state: FreshnessState;
    /** Announced builds published after the exported one. Exact unless saturated. */
    patchesBehind: number;
    /** Whether the exported build predates the window, making the count a floor. */
    saturated: boolean;
    /** Whole days from the build's publication to now. */
    daysOld: number;
    /** Newest announced build the data is missing, or null when there is none. */
    latest: GameBuild | null;
}

/** Provenance stamp of the build the site's data was exported from. */
export interface BuildProvenance {
    gameBuildId: string;
    buildPublishedAt: string;
}

const DAY_SECONDS = 86400;

/**
 * Erenshor patches most days: eleven announced builds in the twelve days to
 * 2026-07-27. Trailing the game by a patch or two is therefore the normal state
 * of any dataset refreshed weekly, and highlighting that would mean highlighting
 * permanently, which trains readers to stop seeing the line. These bounds mark
 * where the gap stops looking like ordinary refresh latency, counted in patches
 * for busy periods and in days for quiet ones.
 */
const NOTABLE_PATCHES = 5;
const NOTABLE_DAYS = 14;

/**
 * Compare the exported build against the live build history.
 *
 * The exported build is located by ID, so `patchesBehind` is a true count of the
 * announced builds the data is missing rather than a comparison of timestamps.
 * When the build predates the feed window the count becomes a floor, which is
 * still sound: every build in the window postdates it.
 *
 * Returns null when either side is unknown, so callers omit the indicator rather
 * than implying currency that was never established.
 */
export function compareFreshness(
    provenance: BuildProvenance | null | undefined,
    builds: GameBuild[] | null | undefined,
    now: number = Date.now()
): Freshness | null {
    if (!provenance || !builds?.length) return null;

    const publishedAt = Date.parse(provenance.buildPublishedAt);
    if (Number.isNaN(publishedAt)) return null;

    const buildSeconds = Math.floor(publishedAt / 1000);
    // A clock behind the build's publication reads as brand new, never negative.
    const daysOld = Math.max(0, Math.floor((Math.floor(now / 1000) - buildSeconds) / DAY_SECONDS));

    const ours = builds.findIndex((build) => build.buildId === provenance.gameBuildId);
    // Absent from the window means every build in it is newer, so the count is a
    // floor rather than unknown. Publish time decides only this saturated case,
    // where there is no ID left to match against.
    const newer =
        ours === -1
            ? builds.filter((build) => build.publishedAt > buildSeconds)
            : builds.slice(0, ours);
    const announced = newer.filter((build) => build.notesTitle !== null);

    if (!announced.length) {
        return { state: 'current', patchesBehind: 0, saturated: false, daysOld, latest: null };
    }

    return {
        state: 'behind',
        patchesBehind: announced.length,
        saturated: ours === -1,
        daysOld,
        latest: announced[0]
    };
}

/** Whether staleness has crossed from routine latency into worth highlighting. */
export function isNotablyStale(freshness: Freshness): boolean {
    return (
        freshness.state === 'behind' &&
        (freshness.patchesBehind >= NOTABLE_PATCHES || freshness.daysOld >= NOTABLE_DAYS)
    );
}
