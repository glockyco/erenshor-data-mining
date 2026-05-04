import type { Load } from '@sveltejs/kit';
import { MAPS } from '$lib/maps';

/**
 * Prerendered per-zone pages. The zone slugs come from the same MAPS
 * registry the world map and sitemap use, so this stays in sync as zones
 * are added or removed. Search-param state (e.g. ?coordinateId=...) is
 * applied client-side and does not affect the prerendered HTML.
 */
export const prerender = true;

export function entries() {
    return Object.keys(MAPS).map((mapName) => ({ mapName }));
}

export const load: Load = ({ params }) => {
    return {
        mapName: params.mapName
    };
};
