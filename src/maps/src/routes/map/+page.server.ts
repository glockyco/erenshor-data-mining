import { buildMapWorldData } from '$lib/map-world-data.server';
import { serializeItemSourcePageData } from '$lib/item-source-page-data';

export const prerender = true;

export const load = async () => {
    const data = await buildMapWorldData();
    return { ...data, ...serializeItemSourcePageData(data.itemSources, data.markers, data.allItems) };
};
