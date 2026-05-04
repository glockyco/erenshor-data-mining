/**
 * Site-wide SEO config and URL helpers.
 *
 * Single source of truth for the canonical site URL, default Open Graph
 * image, and locale. Other SEO modules (`jsonld.ts`, `Seo.svelte`), the
 * sitemap, and robots.txt all read from here so the public domain and
 * brand metadata stay in sync.
 */

export const SITE_URL = 'https://erenshor-maps.wowmuch1.workers.dev';

export const SITE_NAME = 'Erenshor Interactive Maps';

export const SITE_AUTHOR = 'WoW Much';

export const DEFAULT_TITLE = 'Erenshor Interactive Map – World Map & Zone Maps';

export const DEFAULT_DESCRIPTION =
    'Interactive maps for Erenshor: spawn point locations, NPC markers, zone connections, level filtering, and live player tracking via the companion mod.';

export const OG_LOCALE = 'en_US';

/**
 * Default OG card. The world-map preview is the most recognizable visual
 * for the site as a whole. Per-page Seo can override `image`/`imageAlt`/
 * dimensions to surface a more relevant card (e.g., the Adventure Guide
 * window screenshot for `/adventure-guide`).
 */
export const DEFAULT_OG_IMAGE = '/world-map-preview.webp';
export const DEFAULT_OG_IMAGE_WIDTH = 1920;
export const DEFAULT_OG_IMAGE_HEIGHT = 1347;
export const DEFAULT_OG_IMAGE_ALT =
    'Erenshor world map preview showing zones, NPC markers, and spawn points';

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
