import { describe, expect, it } from 'vitest';
import { serializeSelection, deserializeSelection, getSelectionBorderColor } from './selection';
import { buildSearchIndex } from '$lib/map/search';
import type { WorldEnemy } from './world-map';

describe('serializeSelection', () => {
    it('preserves not-found search URLs', () => {
        expect(
            serializeSelection({ type: 'search-not-found', searchType: 'enemy', name: 'Missing' })
        ).toBe('enemy:Missing');
        expect(
            serializeSelection({ type: 'search-not-found', searchType: 'zone', name: 'Unknown Zone' })
        ).toBe('zone:Unknown Zone');
    });


    it('restores wiki items without map sources as search results', () => {
        const searchIndex = buildSearchIndex({
            enemiesEnemy: [],
            enemiesElite: [],
            enemiesBoss: [],
            enemiesChest: [],
            unlocatedEnemies: [],
            treasureLocs: [],
            npcs: [],
            zones: [],
            miningNodes: [],
            water: [],
            itemBags: [],
            itemSources: [],
            allItems: [
                {
                    itemStableKey: 'item:quest-only',
                    displayName: 'Quest Reward',
                    wikiPageName: 'Quest Reward',
                    iconHash: null
                }
            ]
        });

        const selection = deserializeSelection('item:item:quest-only', {
            findMarkerByStableKey: () => null,
            findZoneByKey: () => null,
            searchIndex
        });

        expect(selection).toMatchObject({
            type: 'search',
            result: {
                type: 'item',
                itemStableKey: 'item:quest-only',
                hasKnownSource: false
            }
        });
    });

    it('restores map-visible enemies without spawn markers', () => {
        const searchIndex = buildSearchIndex({
            enemiesEnemy: [],
            enemiesElite: [],
            enemiesBoss: [],
            enemiesChest: [],
            unlocatedEnemies: [
                {
                    stableKey: 'character:runtime enemy',
                    name: 'Runtime Enemy',
                    wikiPageName: 'Runtime Enemy',
                    portraitHash: null,
                    level: 12,
                    encounterTier: 'elite'
                }
            ],
            treasureLocs: [],
            npcs: [],
            zones: [],
            miningNodes: [],
            water: [],
            itemBags: [],
            itemSources: [],
            allItems: []
        });

        const selection = deserializeSelection('enemy:Runtime Enemy', {
            findMarkerByStableKey: () => null,
            findZoneByKey: () => null,
            searchIndex
        });

        expect(selection).toEqual({
            type: 'search',
            result: {
                type: 'enemy',
                name: 'Runtime Enemy',
                encounterTier: 'elite',
                spawnCount: 0,
                zoneCount: 0
            }
        });
        expect(
            searchIndex.enemyProvider.resolveHighlight(
                searchIndex.enemyProvider.getResult('Runtime Enemy')!
            )
        ).toEqual({ type: 'none' });
    });
    it('restores chest search and spawn URLs without changing their enemy prefixes', () => {
        const chest = {
            category: 'enemy',
            stableKey: 'spawn:stowaway-chest',
            zone: 'Stowaway',
            characters: [{ name: 'Fixture Chest', encounterTier: 'chest' }],
            encounterTier: 'chest'
        } as WorldEnemy;
        const searchIndex = buildSearchIndex({
            enemiesEnemy: [],
            enemiesElite: [],
            enemiesBoss: [],
            enemiesChest: [chest],
            unlocatedEnemies: [],
            treasureLocs: [],
            npcs: [],
            zones: [],
            miningNodes: [],
            water: [],
            itemBags: [],
            itemSources: [],
            allItems: []
        });
        const context = {
            findMarkerByStableKey: (key: string) => key === chest.stableKey ? chest : null,
            findZoneByKey: () => null,
            searchIndex
        };
        const searched = deserializeSelection('enemy:Fixture Chest', context);
        const spawned = deserializeSelection('marker:spawn:stowaway-chest', context);
        expect(searched).toMatchObject({ type: 'search', result: { encounterTier: 'chest' } });
        expect(spawned).toEqual({ type: 'marker', marker: chest });
        expect(serializeSelection(searched)).toBe('enemy:Fixture Chest');
        expect(serializeSelection(spawned)).toBe('marker:spawn:stowaway-chest');
        expect(getSelectionBorderColor(searched, new Map())).toBe('border-l-teal-600');
        expect(getSelectionBorderColor(spawned, new Map())).toBe('border-l-teal-600');
    });

});
