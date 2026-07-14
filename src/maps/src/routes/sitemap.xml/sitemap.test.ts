import { describe, it, expect } from 'vitest';
import { GET } from './+server';
import { MAPS } from '$lib/maps';
import { SITE_URL } from '$lib/seo/site';

const staticRoutes = ['/', '/map', '/zone-maps', '/adventure-guide', '/mod', '/spreadsheet'];

describe('sitemap.xml', () => {
    it('preserves every static route and exposes exactly the MAPS zones under /maps/', async () => {
        const xml = await GET().text();
        const locations = [...xml.matchAll(/<loc>(.*?)<\/loc>/g)].map(([, location]) => location);
        const expectedStaticLocations = staticRoutes.map((route) => `${SITE_URL}${route}`);
        const expectedZoneLocations = Object.keys(MAPS).map((key) => `${SITE_URL}/maps/${key}`);
        const mapLocations = locations.filter((location) => location.startsWith(`${SITE_URL}/maps/`));

        for (const location of expectedStaticLocations) expect(locations).toContain(location);
        expect(new Set(mapLocations)).toEqual(new Set(expectedZoneLocations));
    });

    it('emits unique absolute locations, excludes legacy root-zone URLs, and parseable lastmods', async () => {
        const xml = await GET().text();
        const locations = [...xml.matchAll(/<loc>(.*?)<\/loc>/g)].map(([, location]) => location);
        const lastmods = [...xml.matchAll(/<lastmod>(.*?)<\/lastmod>/g)].map(([, lastmod]) => lastmod);

        expect(locations.length).toBeGreaterThan(0);
        expect(new Set(locations).size).toBe(locations.length);
        expect(lastmods.length).toBe(locations.length);
        for (const location of locations) expect(location.startsWith(`${SITE_URL}/`)).toBe(true);
        for (const key of Object.keys(MAPS)) expect(locations).not.toContain(`${SITE_URL}/${key}`);
        for (const lastmod of lastmods) expect(Number.isNaN(Date.parse(lastmod))).toBe(false);
    });
});
