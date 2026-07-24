import { describe, expect, it } from 'vitest';
import { serializeSelection, deserializeSelection } from './selection';
import { Rarity } from '$lib/map-markers';
import { buildSearchIndex } from '$lib/map/search';

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
            enemiesCommon: [],
            enemiesRare: [],
            enemiesUnique: [],
            unlocatedEnemies: [],
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
                    iconName: null
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
            enemiesCommon: [],
            enemiesRare: [],
            enemiesUnique: [],
            unlocatedEnemies: [
                {
                    stableKey: 'character:runtime enemy',
                    name: 'Runtime Enemy',
                    wikiPageName: 'Runtime Enemy',
                    level: 12,
                    effectiveRarity: Rarity.rare
                }
            ],
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
                effectiveRarity: Rarity.rare,
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
});
