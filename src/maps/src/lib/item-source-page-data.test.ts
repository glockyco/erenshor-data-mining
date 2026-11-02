import { describe, expect, it } from 'vitest';
import { buildMapWorldData } from './map-world-data.server';
import { hydrateItemSourcePageData, serializeItemSourcePageData } from './item-source-page-data';
import { conditionPhrases } from './item-provenance';
import { ItemSearchProvider } from './map/search/item-source-provider';
import { presentItemSources, type PresentedItemSource } from './map/search/item-source-presentation';
import { indexCharacterDetails } from './map/character-details';

const SHOWN_FACT_FIELDS = ['probability_kind', 'probability_min', 'probability_basis', 'quantity_kind', 'quantity_min', 'quantity_max',
    'expected_quantity', 'guaranteed'] as const;

/** What the item panel shows of a presented row, with markers by key. */
function shown(row: PresentedItemSource) {
    return { ...row, markers: 'markers' in row ? row.markers.map((marker) => marker.stableKey) : undefined,
        marker: 'marker' in row ? row.marker.stableKey : undefined,
        brokers: 'brokers' in row ? row.brokers.map((broker) => [broker.row, broker.markers.map((marker) => marker.stableKey)]) : undefined,
        entries: 'entries' in row ? row.entries.map((entry) => entry.stableKey) : undefined };
}


describe('public item page data', () => {
    it('preserves every source identity and its displayed facts without duplicate source records', async () => {
        const data = await buildMapWorldData();
        const serialized = serializeItemSourcePageData(data.itemSources, data.markers, data.allItems);
        const hydrated = hydrateItemSourcePageData({ ...data, ...JSON.parse(JSON.stringify(serialized)) as typeof serialized });
        expect(serialized).not.toHaveProperty('itemFacts');
        expect(Object.keys(serialized.itemSources)).toEqual(expect.arrayContaining(data.itemSources.map((row) => row.acquisitionKey)));
        expect(hydrated.itemSources).toHaveLength(data.itemSources.length);
        for (const [index, row] of data.itemSources.entries()) {
            const restored = hydrated.itemSources[index];
            const { provenance, referenceNames, locationSources, ...presentation } = row;
            expect(restored).toMatchObject(presentation);
            expect(restored.referenceNames).toMatchObject(referenceNames);
            expect(restored.locationSources).toMatchObject(locationSources);
            for (const field of SHOWN_FACT_FIELDS) expect(restored.provenance[field]).toBe(provenance[field]);
            expect(conditionPhrases([restored.provenance.conditions], restored.referenceNames)).toEqual(conditionPhrases([provenance.conditions], referenceNames));
            expect(restored.provenance.source_key).toBe(provenance.source_key);
            expect(restored.provenance.item_stable_key).toBe(provenance.item_stable_key);
            expect(restored.provenance.source_group_key).toBe(provenance.source_group_key);
            expect(restored.provenance.probability_max).toBe(provenance.probability_max);
            expect(restored.provenance.locations).toHaveLength(provenance.locations.length);
            expect(new Set(restored.provenance.locations.map((place) => place.place_key)).size).toBe(provenance.locations.length);
            for (const [placeIndex, place] of provenance.locations.entries()) {
                const actual = restored.provenance.locations[placeIndex];
                expect(actual).toMatchObject({ relation: place.relation, scene: place.scene,
                    marker_stable_key: place.marker_stable_key, source_copy_stable_key: place.source_copy_stable_key,
                    player_level_min: place.player_level_min, player_level_max: place.player_level_max,
                    entry_zone_line_keys: place.entry_zone_line_keys });
                if (!place.marker_stable_key) expect(actual).toMatchObject({ x: place.x, z: place.z, zone_stable_key: place.zone_stable_key });
                expect(conditionPhrases([actual.conditions], restored.referenceNames)).toEqual(conditionPhrases([place.conditions], referenceNames));
            }
        }
        const [originalProvider, restoredProvider] = [data, hydrated].map((page) => new ItemSearchProvider(page.itemSources,
            [...page.markers.npcs, ...page.markers.enemiesEnemy, ...page.markers.enemiesElite, ...page.markers.enemiesBoss, ...page.markers.enemiesChest],
            page.markers.miningNodes, page.markers.water, page.markers.itemBags, page.allItems, page.markers.treasureLocs, page.markers.zoneLines));
        expect(restoredProvider.buildIndex()).toEqual(originalProvider.buildIndex());
        for (const item of data.allItems) {
            expect(restoredProvider.getMarkersForItem(item.itemStableKey)).toEqual(expect.arrayContaining(
                originalProvider.getMarkersForItem(item.itemStableKey).map((marker) => expect.objectContaining({ stableKey: marker.stableKey }))));
        }
        for (const item of data.allItems) {
            expect(presentItemSources(restoredProvider.getSourcesForItem(item.itemStableKey), restoredProvider.startingClassCount).map(shown))
                .toEqual(presentItemSources(originalProvider.getSourcesForItem(item.itemStableKey), originalProvider.startingClassCount).map(shown));
        }
        const originalDetails = indexCharacterDetails(data.itemSources, data.charactersByName);
        const restoredDetails = indexCharacterDetails(hydrated.itemSources, data.charactersByName);
        for (const [key, drops] of originalDetails.drops) {
            expect(restoredDetails.drops.get(key)?.map((drop) => [drop.itemName, drop.dropProbability, drop.provenance.source_key]))
                .toEqual(drops.map((drop) => [drop.itemName, drop.dropProbability, drop.provenance.source_key]));
        }
        for (const [key, stock] of originalDetails.vendorItems) {
            expect(restoredDetails.vendorItems.get(key)?.map((item) => [item.name, item.price, item.provenance.source_key]))
                .toEqual(stock.map((item) => [item.name, item.price, item.provenance.source_key]));
        }
        const markers = Object.values(hydrated.markers).flat();
        expect(markers.length).toBeGreaterThan(0);
        for (const marker of markers) expect(marker).not.toHaveProperty('popup');
        for (const marker of hydrated.markers.miningNodes) {
            for (const item of marker.items) {
                const source = hydrated.itemSources.find((row) => row.acquisitionKey === item.provenance.source_key);
                if (source) expect(item.provenance).toBe(source.provenance);
            }
        }
        const placeSets = new Map<string, object>();
        for (const source of hydrated.itemSources) {
            const fact = source.provenance;
            if (fact.place_set_key === null) continue;
            if (placeSets.has(fact.place_set_key)) expect(fact.locations).toBe(placeSets.get(fact.place_set_key));
            else placeSets.set(fact.place_set_key, fact.locations);
        }
        expect(placeSets.size).toBeGreaterThan(0);
        expect(serialized.itemPlaces.length).toBeGreaterThanOrEqual(placeSets.size);
    });

    it('retains explicit missing wiki links and distinct presentation labels', async () => {
        const data = await buildMapWorldData();
        const row = data.itemSources.find((row) => row.characterStableKey && row.sourceWikiPageName)!;
        row.sourceWikiPageName = null;
        row.sourceName = 'Distinct source label';
        const serialized = serializeItemSourcePageData(data.itemSources, data.markers, data.allItems);
        const hydrated = hydrateItemSourcePageData({ ...data, ...serialized });
        expect(hydrated.itemSources.find((source) => source.acquisitionKey === row.acquisitionKey)).toMatchObject({
            sourceName: row.sourceName, sourceWikiPageName: null
        });
    });

    it('keeps explicit place values that differ from the marker defaults', async () => {
        const data = await buildMapWorldData();
        const row = data.itemSources.find((row) => row.provenance.locations.some((place) => place.marker_stable_key))!;
        const place = row.provenance.locations.find((place) => place.marker_stable_key)!;
        Object.assign(place, { relation: 'unlocated', scene: null, x: null, z: 123, source_copy_stable_key: null });
        const serialized = serializeItemSourcePageData(data.itemSources, data.markers, data.allItems);
        const hydrated = hydrateItemSourcePageData({ ...data, ...serialized });
        const restored = hydrated.itemSources.find((source) => source.acquisitionKey === row.acquisitionKey)!;
        expect(restored.provenance.locations).toContainEqual(expect.objectContaining({
            relation: 'unlocated', scene: null, x: null, z: 123, zone_stable_key: place.zone_stable_key, source_copy_stable_key: null
        }));
    });

    it('does not replace explicit nulls with another field default', async () => {
        const data = await buildMapWorldData();
        const row = data.itemSources.find((row) => row.provenance.source_stable_key)!;
        row.characterStableKey = null;
        Object.assign(row.provenance, { source_group_key: null, probability_kind: 'bounded', probability_min: 5, probability_max: null });
        const serialized = serializeItemSourcePageData(data.itemSources, data.markers, data.allItems);
        const hydrated = hydrateItemSourcePageData({ ...data, ...JSON.parse(JSON.stringify(serialized)) as typeof serialized });
        expect(hydrated.itemSources.find((source) => source.acquisitionKey === row.acquisitionKey)).toMatchObject({
            characterStableKey: null, provenance: { source_group_key: null, probability_min: 5, probability_max: null }
        });
    });
});
