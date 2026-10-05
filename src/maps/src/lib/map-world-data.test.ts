import { describe, expect, it, vi } from 'vitest';

import { Repository } from './database.node';
import { buildEncounterTierByName } from './map-markers';
import { buildMapWorldData } from './map-world-data.server';

const markerKeys = [
    'achievementTriggers',
    'doors',
    'enemiesEnemy',
    'enemiesElite',
    'enemiesBoss',
    'enemiesChest',
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
        expect(data.markers.enemiesEnemy).toEqual([]);
        expect(data.markers.enemiesElite).toEqual([]);
        expect(data.markers.enemiesBoss.map((marker) => marker.stableKey)).toEqual([
            'spawn:stowaway-enemy',
            'spawn:portal-enemy'
        ]);
        expect(data.markers.enemiesChest.map((marker) => marker.stableKey)).toEqual([
            'spawn:stowaway-chest'
        ]);
        expect(data.markers.enemiesChest[0].encounterTier).toBe('chest');
        expect(data.markers.enemiesBoss[0]).toMatchObject({
            levelMin: 7,
            levelMax: 7,
            zone: 'Stowaway',
            zoneName: "Stowaway's Step"
        });
        expect(data.levelRange).toEqual({ min: 2, max: 36 });
        expect(data.markers.treasureLocs.map((site) => [site.zone, site.minReadingLevel, site.levelMin, site.levelMax])).toEqual(expect.arrayContaining([
            ['Hidden', 1, 2, 36],
            ['Blight', 31, 27, 36],
            ['Stowaway', 21, 17, 36]
        ]));
        expect(data.unlocatedEnemies).toEqual([
            expect.objectContaining({
                stableKey: 'character:runtime enemy',
                name: 'Runtime Enemy',
                level: 12
            })
        ]);
        const tiers = buildEncounterTierByName(
            [
                ...data.markers.enemiesEnemy,
                ...data.markers.enemiesElite,
                ...data.markers.enemiesBoss,
                ...data.markers.enemiesChest,
                ...data.markers.npcs
            ],
            data.unlocatedEnemies
        );
        expect(tiers.get('Fixture Enemy')).toBe('boss');
        expect(tiers.get('Runtime Enemy')).toBe('elite');
        expect(tiers.get('Fixture Chest')).toBe('chest');
        expect(tiers.has('Breena Carpenter')).toBe(false);
        expect(data.allItems).toHaveLength(7);
        expect([...new Set(data.itemSources.map((source) => source.kind))].sort()).toEqual([
            'bag',
            'drop',
            'fishing',
            'mining',
            'vendor',
            'world'
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
