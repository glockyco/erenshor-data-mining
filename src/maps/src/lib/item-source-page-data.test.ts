import { describe, expect, it } from 'vitest';
import { buildMapWorldData } from './map-world-data.server';
import { hydrateItemSourcePageData, serializeItemSourcePageData, type SerializedItemSourcePageData } from './item-source-page-data';

describe('public item page data', () => {
    it('round trips the map presentation through keyed sources and place sets', async () => {
        const data = await buildMapWorldData();
        const serialized = serializeItemSourcePageData(data.itemSources, data.markers);
        const hydrated = hydrateItemSourcePageData(JSON.parse(JSON.stringify(serialized)) as SerializedItemSourcePageData);
        expect(hydrated.itemSources).toEqual(data.itemSources);
        expect(data.markers).toMatchObject(hydrated.markers);
        const markers = Object.values(hydrated.markers).flat();
        expect(markers.length).toBeGreaterThan(0);
        for (const marker of markers) expect(marker).not.toHaveProperty('popup');
        expect(serialized.itemSources.every((row) => typeof row[0] === 'string')).toBe(true);
        for (const marker of hydrated.markers.miningNodes) {
            for (const item of marker.items) {
                const source = hydrated.itemSources.find((row) => row.acquisitionKey === item.provenance.source_key);
                if (source) expect(item.provenance).toBe(source.provenance);
            }
        }
        const placeSets = new Map<string, object>();
        for (const source of hydrated.itemSources) {
            const fact = source.provenance;
            if (!fact.place_set_key) continue;
            if (placeSets.has(fact.place_set_key)) expect(fact.locations).toBe(placeSets.get(fact.place_set_key));
            else placeSets.set(fact.place_set_key, fact.locations);
        }
        expect(placeSets.size).toBeGreaterThan(0);
        expect(Object.keys(serialized.itemPlaces)).toEqual(expect.arrayContaining([...placeSets.keys()]));
    });
});
