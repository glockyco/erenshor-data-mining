import { MAPS } from '$lib/maps';
import { SITE_URL } from '$lib/seo/site';

export const prerender = true;

const staticRoutes = ['/', '/map', '/zone-maps', '/adventure-guide', '/mod', '/spreadsheet'];

export function GET() {
    const zoneRoutes = Object.keys(MAPS).map((key) => `/${key}`);
    const urls = [...staticRoutes, ...zoneRoutes];

    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((url) => `    <url><loc>${SITE_URL}${url}</loc></url>`).join('\n')}
</urlset>`;

    return new Response(xml, {
        headers: { 'Content-Type': 'application/xml' }
    });
}
