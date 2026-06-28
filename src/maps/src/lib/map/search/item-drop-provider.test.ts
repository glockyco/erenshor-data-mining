import { describe, it, expect } from 'vitest';
import type { ItemDropperRow } from '$lib/map-markers';
import type { WorldEnemy, WorldNpc } from '$lib/types/world-map';
import { Rarity } from '$lib/map-markers';
import { ItemSearchProvider } from './item-drop-provider';
import type { ItemSearchResult } from './types';

/** Type guard: narrows SearchResult to the item variant. */
function isItemResult(
    result: { type: string }
): result is ItemSearchResult {
    return result.type === 'item';
}

// Minimal marker factory: only fields the provider touches are populated.
function makeEnemy(
    stableKey: string,
    zone: string,
    zoneName: string,
    charStableKey: string,
    charName: string
): WorldEnemy {
    return {
        stableKey,
        zone,
        zoneName,
        worldPosition: [0, 0],
        characters: [
            {
                name: charName,
                wikiPageName: null,
                stableKey: charStableKey,
                level: 10,
                spawnChance: 100,
                isCommon: true,
                isRare: false,
                isUnique: false,
                effectiveRarity: Rarity.common,
                isFriendly: false,
                isInvulnerable: false,
                isVendor: false,
                hasDialog: false
            }
        ]
    } as unknown as WorldEnemy;
}

function makeNpc(
    stableKey: string,
    zone: string,
    zoneName: string,
    charStableKey: string,
    charName: string
): WorldNpc {
    return {
        stableKey,
        zone,
        zoneName,
        worldPosition: [1, 1],
        characters: [
            {
                name: charName,
                wikiPageName: null,
                stableKey: charStableKey,
                level: 5,
                spawnChance: 100,
                isCommon: true,
                isRare: false,
                isUnique: false,
                effectiveRarity: Rarity.common,
                isFriendly: true,
                isInvulnerable: false,
                isVendor: false,
                hasDialog: false
            }
        ]
    } as unknown as WorldNpc;
}

function row(
    itemStableKey: string,
    displayName: string,
    charStableKey: string,
    npcName: string,
    dropProbability: number,
    opts: Partial<ItemDropperRow> = {}
): ItemDropperRow {
    return {
        itemStableKey,
        displayName,
        wikiPageName: null,
        iconName: null,
        characterStableKey: charStableKey,
        npcName,
        isFriendly: false,
        isRare: false,
        isUnique: false,
        dropProbability,
        ...opts
    };
}

describe('ItemSearchProvider', () => {
    it('indexes items keyed by stable key, not display name', () => {
        // Two items share the same display name but have different stable keys
        const rows = [
            row('item:a', 'Shared Name', 'char:1', 'Goblin', 10),
            row('item:b', 'Shared Name', 'char:2', 'Orc', 20)
        ];
        const provider = new ItemSearchProvider(rows, [
            makeEnemy('sp:1', 'Duskenlight', 'Duskenlight', 'char:1', 'Goblin'),
            makeEnemy('sp:2', 'Braxonian', 'Braxonian', 'char:2', 'Orc')
        ]);
        const entries = provider.buildIndex();

        expect(entries).toHaveLength(2);
        const keys = entries
            .map((e) => e.result)
            .filter(isItemResult)
            .map((r) => r.itemStableKey);
        expect(keys).toContain('item:a');
        expect(keys).toContain('item:b');
    });

    it('excludes items whose droppers have no resolvable spawn point', () => {
        const rows = [
            row('item:has-spawn', 'Dropped Sword', 'char:spawn', 'Goblin', 10),
            row('item:no-spawn', 'Vendor Only', 'char:none', 'Merchant', 50)
        ];
        const provider = new ItemSearchProvider(rows, [
            makeEnemy('sp:1', 'Duskenlight', 'Duskenlight', 'char:spawn', 'Goblin')
            // No marker for char:none — merchant never spawns on the map
        ]);
        const entries = provider.buildIndex();

        expect(entries).toHaveLength(1);
        const result = entries[0].result;
        expect(isItemResult(result)).toBe(true);
        if (isItemResult(result)) {
            expect(result.itemStableKey).toBe('item:has-spawn');
        }
    });

    it('resolves highlight to positions of all dropper spawns', () => {
        const rows = [row('item:1', 'Gem', 'char:1', 'Goblin', 5)];
        const enemy1 = makeEnemy('sp:1', 'Duskenlight', 'Duskenlight', 'char:1', 'Goblin');
        const enemy2 = makeEnemy('sp:2', 'Braxonian', 'Braxonian', 'char:1', 'Goblin');
        const provider = new ItemSearchProvider(rows, [enemy1, enemy2]);

        const result = provider.resolveHighlight({
            type: 'item',
            itemStableKey: 'item:1',
            itemName: 'Gem',
            wikiPageName: null,
            dropperCount: 1,
            zoneCount: 2
        });

        expect(result.type).toBe('positions');
        if (result.type === 'positions') {
            expect(result.positions).toHaveLength(2);
            expect(result.stableKeys).toContain('sp:1');
            expect(result.stableKeys).toContain('sp:2');
        }
    });

    it('getMarkersForItem and getDropRowsForItem return data for the item', () => {
        const rows = [
            row('item:1', 'Gem', 'char:1', 'Goblin', 5, { isRare: true }),
            row('item:1', 'Gem', 'char:2', 'Orc', 30, { isUnique: true })
        ];
        const provider = new ItemSearchProvider(rows, [
            makeEnemy('sp:1', 'Duskenlight', 'Duskenlight', 'char:1', 'Goblin'),
            makeEnemy('sp:2', 'Duskenlight', 'Duskenlight', 'char:2', 'Orc')
        ]);

        const markers = provider.getMarkersForItem('item:1');
        expect(markers).toHaveLength(2);

        const dropRows = provider.getDropRowsForItem('item:1');
        expect(dropRows).toHaveLength(2);
        // Sorted by drop probability descending
        expect(dropRows[0].dropProbability).toBe(30);
        expect(dropRows[1].dropProbability).toBe(5);
    });

    it('getResult returns the cached result for URL restore', () => {
        const rows = [row('item:1', 'Gem', 'char:1', 'Goblin', 5)];
        const provider = new ItemSearchProvider(rows, [
            makeEnemy('sp:1', 'Duskenlight', 'Duskenlight', 'char:1', 'Goblin')
        ]);

        const result = provider.getResult('item:1');
        expect(result).not.toBeNull();
        expect(result?.itemStableKey).toBe('item:1');
        expect(result?.itemName).toBe('Gem');
        expect(result?.dropperCount).toBe(1);
        expect(result?.zoneCount).toBe(1);

        // Unknown key returns null
        expect(provider.getResult('item:missing')).toBeNull();
    });

    it('counts unique dropper characters and zones across enemy and npc markers', () => {
        const rows = [
            row('item:1', 'Gem', 'char:e', 'Goblin', 5),
            row('item:1', 'Gem', 'char:n', 'Merchant', 10)
        ];
        const provider = new ItemSearchProvider(rows, [
            makeEnemy('sp:1', 'Duskenlight', 'Duskenlight', 'char:e', 'Goblin'),
            makeNpc('sp:2', 'Braxonian', 'Braxonian', 'char:n', 'Merchant')
        ]);
        const entries = provider.buildIndex();

        expect(entries).toHaveLength(1);
        const result = entries[0].result;
        expect(isItemResult(result)).toBe(true);
        if (isItemResult(result)) {
            expect(result.dropperCount).toBe(2); // one enemy + one npc character
            expect(result.zoneCount).toBe(2); // Duskenlight + Braxonian
        }
    });
});
