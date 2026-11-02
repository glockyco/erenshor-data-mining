import { buildMapWorldData } from '$lib/map-world-data.server';
import { serializeItemSourcePageData } from '$lib/item-source-page-data';
import { ItemSearchProvider } from '$lib/map/search/item-source-provider';
import { unpresentedSourceKeys } from '$lib/map/search/item-source-presentation';

export const prerender = true;

export const load = async () => {
    const data = await buildMapWorldData();
    const { markers } = data;
    const provider = new ItemSearchProvider(data.itemSources,
        [...markers.npcs, ...markers.enemiesEnemy, ...markers.enemiesElite, ...markers.enemiesBoss, ...markers.enemiesChest],
        markers.miningNodes, markers.water, markers.itemBags, data.allItems, markers.treasureLocs, markers.zoneLines);
    const unpresented = unpresentedSourceKeys(provider);
    if (unpresented.length) throw new Error(`Item panels omit public sources: ${unpresented.join(', ')}`);
    return { ...data, ...serializeItemSourcePageData(data.itemSources, data.markers, data.allItems) };
};
