import { describe, it, expect } from 'vitest';
import { GET } from './+server';
import { SITE_URL } from '$lib/seo/site';

describe('sitemap.xml', () => {
    it('emits a parseable lastmod and an absolute loc for every url', async () => {
        const xml = await GET().text();
        const locs = [...xml.matchAll(/<loc>(.*?)<\/loc>/g)];
        const lastmods = [...xml.matchAll(/<lastmod>(.*?)<\/lastmod>/g)];

        expect(locs.length).toBeGreaterThan(0);
        expect(lastmods.length).toBe(locs.length);
        for (const [, loc] of locs) expect(loc.startsWith(`${SITE_URL}/`)).toBe(true);
        for (const [, lastmod] of lastmods) expect(Number.isNaN(Date.parse(lastmod))).toBe(false);
    });
});
