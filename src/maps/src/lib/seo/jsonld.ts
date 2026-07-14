/**
 * Schema.org JSON-LD builders for Erenshor Community Tools.
 *
 * Each builder returns a plain object that the `Seo` component serializes
 * into a `<script type="application/ld+json">` tag. Shapes are kept small
 * and explicit per page type — `WebSite`/`WebApplication` for the site,
 * `VideoGame` to anchor the subject, `BreadcrumbList` for crumbs.
 *
 * The `VideoGame` entity is what lets Google associate the site with the
 * game itself, which matters for queries like "erenshor map" — the game
 * is the topic, the site is one resource about it.
 */
import { SITE_NAME, SITE_URL, canonicalUrl } from './site';

export interface BreadcrumbItem {
    name: string;
    path: string;
}

const ERENSHOR_GAME_ID = `${SITE_URL}/#game`;
const SITE_ID = `${SITE_URL}/#website`;
const APP_ID = `${SITE_URL}/#webapp`;

/** schema.org/VideoGame — the subject the site documents. Stable @id so
 *  WebApplication/CreativeWork entities can reference it via `about`. */
export function videoGameJsonLd() {
    return {
        '@context': 'https://schema.org',
        '@type': 'VideoGame',
        '@id': ERENSHOR_GAME_ID,
        name: 'Erenshor',
        url: 'https://store.steampowered.com/app/2382520/Erenshor/',
        genre: ['Single-player RPG', 'Adventure', 'Role-playing game'],
        gamePlatform: 'PC',
        applicationCategory: 'Game',
        publisher: { '@type': 'Organization', name: 'Burgee Media' },
        sameAs: [
            'https://store.steampowered.com/app/2382520/Erenshor/',
            'https://erenshor.com/',
            'https://erenshor.wiki.gg/',
            'https://discord.gg/erenshor'
        ]
    };
}

/** schema.org/WebSite for the site as a whole. */
export function websiteJsonLd() {
    return {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        '@id': SITE_ID,
        name: SITE_NAME,
        url: SITE_URL,
        inLanguage: 'en',
        about: { '@id': ERENSHOR_GAME_ID }
    };
}

/** schema.org/WebApplication for the interactive map app on the home page. */
export function webApplicationJsonLd() {
    return {
        '@context': 'https://schema.org',
        '@type': 'WebApplication',
        '@id': APP_ID,
        name: SITE_NAME,
        url: canonicalUrl('/map'),
        applicationCategory: 'BrowserApplication',
        operatingSystem: 'Any',
        browserRequirements: 'Requires JavaScript',
        offers: {
            '@type': 'Offer',
            price: '0',
            priceCurrency: 'USD'
        },
        about: { '@id': ERENSHOR_GAME_ID },
        isPartOf: { '@id': SITE_ID }
    };
}

/** schema.org/CreativeWork for a zone-specific map page. */
export interface ZoneMapInput {
    zoneKey: string;
    zoneName: string;
}

export function zoneMapJsonLd({ zoneKey, zoneName }: ZoneMapInput) {
    return {
        '@context': 'https://schema.org',
        '@type': 'CreativeWork',
        name: `${zoneName} – Erenshor Zone Map`,
        url: canonicalUrl(`/maps/${zoneKey}`),
        about: { '@id': ERENSHOR_GAME_ID },
        isPartOf: { '@id': SITE_ID },
        keywords: ['erenshor', 'zone map', zoneName, 'interactive map']
    };
}

/** schema.org/BreadcrumbList for nested pages. */
export function breadcrumbJsonLd(items: BreadcrumbItem[]) {
    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: items.map((item, idx) => ({
            '@type': 'ListItem',
            position: idx + 1,
            name: item.name,
            item: canonicalUrl(item.path)
        }))
    };
}

/** schema.org/FAQPage. Answers arrive already flattened to plain text. */
export function faqPageJsonLd(items: { question: string; answer: string }[]) {
    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: items.map((item) => ({
            '@type': 'Question',
            name: item.question,
            acceptedAnswer: {
                '@type': 'Answer',
                text: item.answer
            }
        }))
    };
}
