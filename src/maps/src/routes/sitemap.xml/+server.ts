import { MAPS } from '$lib/maps';
import { SITE_URL } from '$lib/seo/site';

export const prerender = true;

// Frozen at prerender/build time (the whole static site rebuilds together), so
// this is the consistently-accurate lastmod Google uses to schedule recrawls.
const BUILD_TIME = new Date().toISOString();

const staticRoutes = ['/', '/map', '/zone-maps', '/adventure-guide', '/mod', '/spreadsheet'];

export function GET() {
    const zoneRoutes = Object.keys(MAPS).map((key) => `/${key}`);
    const urls = [...staticRoutes, ...zoneRoutes];

    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((url) => `    <url><loc>${SITE_URL}${url}</loc><lastmod>${BUILD_TIME}</lastmod></url>`).join('\n')}
</urlset>`;

    return new Response(xml, {
        headers: { 'Content-Type': 'application/xml' }
    });
}
