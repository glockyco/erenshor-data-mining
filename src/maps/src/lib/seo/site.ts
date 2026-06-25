/**
 * Site-wide SEO config and URL helpers.
 *
 * Single source of truth for the canonical site URL, default Open Graph
 * image, and locale. Other SEO modules (`jsonld.ts`, `Seo.svelte`), the
 * sitemap, and robots.txt all read from here so the public domain and
 * brand metadata stay in sync.
 */

export const SITE_URL = 'https://erenshor-maps.wowmuch1.workers.dev';

export const SITE_NAME = 'Erenshor Maps';

export const SITE_AUTHOR = 'WoW Much';

export const DEFAULT_TITLE = 'Erenshor Maps – Interactive Maps, Data & Mods';

export const DEFAULT_DESCRIPTION =
    'Interactive maps, reference data, and companion mods for Erenshor, the single-player simulated MMORPG. Spawn points, NPC markers, item drop data, and live in-game tracking, refreshed every patch.';

export const OG_LOCALE = 'en_US';

/**
 * Default OG card. Shared across every page so link previews consistently
 * present the site-wide Erenshor Community Tools brand.
 */
export const DEFAULT_OG_IMAGE = '/og-default.png';
export const DEFAULT_OG_IMAGE_WIDTH = 1200;
export const DEFAULT_OG_IMAGE_HEIGHT = 630;
export const DEFAULT_OG_IMAGE_ALT =
    'Erenshor Maps – interactive maps, data, and companion mods for Erenshor';

/**
 * Compute the absolute canonical URL for a page path.
 *
 * Accepts both `/foo` and `foo`. The site uses default trailingSlash='never'
 * (see `svelte.config.js`), so canonical URLs strip trailing slashes on
 * non-root paths; the root maps to `${SITE_URL}/`.
 */
export function canonicalUrl(path: string): string {
    if (path === '/' || path === '') return `${SITE_URL}/`;
    const normalized = path.startsWith('/') ? path : `/${path}`;
    return `${SITE_URL}${normalized.replace(/\/$/, '')}`;
}

/** Absolute URL for an asset path (typically the OG image). */
export function absoluteUrl(path: string): string {
    if (/^https?:\/\//.test(path)) return path;
    const normalized = path.startsWith('/') ? path : `/${path}`;
    return `${SITE_URL}${normalized}`;
}
