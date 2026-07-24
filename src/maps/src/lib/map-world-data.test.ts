import { describe, expect, it, vi } from 'vitest';

import { Repository } from './database.node';
import { buildMapWorldData } from './map-world-data.server';

const markerKeys = [
    'achievementTriggers',
    'doors',
    'enemiesCommon',
    'enemiesRare',
    'enemiesUnique',
    'forges',
    'itemBags',
    'miningNodes',
    'npcs',
    'secretPassages',
    'teleports',
    'treasureLocs',
    'water',
    'wishingWells',
    'zoneLines'
];

describe('buildMapWorldData', () => {
    it('builds deterministic marker categories, levels, and bounds from the fixture repository', async () => {
        const repository = new Repository();
        const close = vi.spyOn(repository, 'close');
        const data = await buildMapWorldData({ repository });

        expect(Object.keys(data.markers)).toEqual(markerKeys);
        expect(data.markers.npcs.map((marker) => marker.stableKey)).toEqual(['spawn:stowaway-breena']);
        expect(data.markers.enemiesCommon).toEqual([]);
        expect(data.markers.enemiesRare).toEqual([]);
        expect(data.markers.enemiesUnique.map((marker) => marker.stableKey)).toEqual([
            'spawn:stowaway-enemy'
        ]);
        expect(data.markers.enemiesUnique[0]).toMatchObject({
            levelMin: 7,
            levelMax: 7,
            zone: 'Stowaway',
            zoneName: "Stowaway's Step"
        });
        expect(data.levelRange).toEqual({ min: 7, max: 7 });
        expect(data.allItems).toHaveLength(6);
        expect(data.itemSources.map((source) => source.kind).sort()).toEqual([
            'bag',
            'drop',
            'fishing',
            'mining',
            'vendor'
        ]);
        expect(close).toHaveBeenCalledTimes(1);

        expect(data.markers.water).toHaveLength(1);
        expect(data.markers.water[0].worldPolygon).toHaveLength(4);
        expect(data.markers.water[0].worldPosition).toEqual([
            (data.markers.water[0].worldPolygon[0][0] + data.markers.water[0].worldPolygon[2][0]) / 2,
            (data.markers.water[0].worldPolygon[0][1] + data.markers.water[0].worldPolygon[2][1]) / 2
        ]);

        const zoneBounds = data.zones.map((zone) => zone.bounds);
        expect(data.worldBounds).toEqual({
            minX: Math.min(...zoneBounds.map((bounds) => bounds.minX)),
            minY: Math.min(...zoneBounds.map((bounds) => bounds.minY)),
            maxX: Math.max(...zoneBounds.map((bounds) => bounds.maxX)),
            maxY: Math.max(...zoneBounds.map((bounds) => bounds.maxY))
        });
    });

    it('closes the repository when initialization fails', async () => {
        const repository = new Repository();
        const close = vi.spyOn(repository, 'close');
        vi.spyOn(repository, 'init').mockRejectedValue(new Error('fixture init failed'));

        await expect(buildMapWorldData({ repository })).rejects.toThrow('fixture init failed');
        expect(close).toHaveBeenCalledTimes(1);
    });

    it('closes the repository after a failed world-data query', async () => {
        const repository = new Repository();
        const close = vi.spyOn(repository, 'close');
        vi.spyOn(repository, 'getAllZoneNorthBearings').mockRejectedValue(new Error('fixture query failed'));

        await expect(buildMapWorldData({ repository })).rejects.toThrow('fixture query failed');
        expect(close).toHaveBeenCalledTimes(1);
    });
});
