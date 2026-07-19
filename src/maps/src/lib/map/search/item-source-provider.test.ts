import { describe, it, expect } from 'vitest';
import type {
    ItemDropSource,
    ItemVendorSource,
    ItemMiningSource,
    ItemFishingSource,
    ItemBagSource,
    ItemSourceItemMeta
} from '$lib/map-markers';
import type {
    WorldEnemy,
    WorldNpc,
    WorldMiningNode,
    WorldWater,
    WorldItemBag
} from '$lib/types/world-map';
import { Rarity } from '$lib/map-markers';
import { ItemSearchProvider } from './item-source-provider';
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
                sourceScript: null,
                eventPosition: null,
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
                sourceScript: null,
                eventPosition: null,
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
    opts: Partial<ItemDropSource> = {}
): ItemDropSource {
    return {
        kind: 'drop',
        itemStableKey,
        displayName,
        wikiPageName: displayName,
        iconName: null,
        characterStableKey: charStableKey,
        npcName,
        isRare: false,
        isUnique: false,
        dropProbability,
        ...opts
    };
}

function vendorRow(
    itemStableKey: string,
    displayName: string,
    charStableKey: string,
    npcName: string,
    price: number,
    opts: Partial<ItemVendorSource> = {}
): ItemVendorSource {
    return {
        kind: 'vendor',
        itemStableKey,
        displayName,
        wikiPageName: displayName,
        iconName: null,
        characterStableKey: charStableKey,
        npcName,
        price,
        ...opts
    };
}

function miningRow(
    itemStableKey: string,
    displayName: string,
    nodeStableKey: string,
    dropChance: number,
    opts: Partial<ItemMiningSource> = {}
): ItemMiningSource {
    return {
        kind: 'mining',
        itemStableKey,
        displayName,
        wikiPageName: displayName,
        iconName: null,
        nodeStableKey,
        dropChance,
        ...opts
    };
}

function fishingRow(
    itemStableKey: string,
    displayName: string,
    waterStableKey: string,
    period: 'day' | 'night',
    dropChance: number,
    opts: Partial<ItemFishingSource> = {}
): ItemFishingSource {
    return {
        kind: 'fishing',
        itemStableKey,
        displayName,
        wikiPageName: displayName,
        iconName: null,
        waterStableKey,
        period,
        dropChance,
        ...opts
    };
}

function bagRow(
    itemStableKey: string,
    displayName: string,
    bagStableKey: string,
    opts: Partial<ItemBagSource> = {}
): ItemBagSource {
    return {
        kind: 'bag',
        itemStableKey,
        displayName,
        wikiPageName: displayName,
        iconName: null,
        bagStableKey,
        ...opts
    };
}

function makeMiningNode(
    stableKey: string,
    zone: string,
    zoneName: string,
    worldPosition: [number, number] = [2, 2]
): WorldMiningNode {
    return {
        stableKey,
        category: 'mining-node',
        position: { x: worldPosition[0], y: worldPosition[1] },
        items: [],
        respawnTime: 0,
        zone,
        zoneName,
        worldPosition
    } as WorldMiningNode;
}

function makeWater(
    stableKey: string,
    zone: string,
    zoneName: string,
    worldPosition: [number, number] = [3, 3]
): WorldWater {
    return {
        stableKey,
        category: 'water',
        position: { x: worldPosition[0], y: worldPosition[1] },
        width: 1,
        height: 1,
        daytimeItems: [],
        nighttimeItems: [],
        worldPolygon: [],
        zone,
        zoneName,
        worldPosition
    };
}

function makeBag(
    stableKey: string,
    zone: string,
    zoneName: string,
    worldPosition: [number, number] = [4, 4]
): WorldItemBag {
    return {
        stableKey,
        category: 'item-bag',
        position: { x: worldPosition[0], y: worldPosition[1] },
        itemName: 'Bag Item',
        itemWikiPageName: null,
        respawnTimer: 0,
        respawns: true,
        zone,
        zoneName,
        worldPosition
    };
}

describe('ItemSearchProvider', () => {
    it('indexes wiki items with no map source rows as unknown', () => {
        const allItems: ItemSourceItemMeta[] = [
            {
                itemStableKey: 'item:quest-only',
                displayName: 'Quest Reward',
                wikiPageName: 'Quest Reward',
                iconName: 'quest-reward'
            }
        ];
        const provider = new ItemSearchProvider([], [], [], [], [], allItems);

        expect(provider.getResult('item:quest-only')).toMatchObject({
            itemStableKey: 'item:quest-only',
            itemName: 'Quest Reward',
            hasKnownSource: false,
            sourceCounts: {
                droppers: 0,
                vendors: 0,
                miningNodes: 0,
                fishingSpots: 0,
                itemBags: 0
            },
            zoneCount: 0
        });
        expect(provider.buildIndex()).toHaveLength(1);
    });

    it('indexes items keyed by stable key, not display name', () => {
        // Two items share the same display name but have different stable keys
        const rows = [
            row('item:a', 'Shared Name', 'char:1', 'Goblin', 10),
            row('item:b', 'Shared Name', 'char:2', 'Orc', 20)
        ];
        const provider = new ItemSearchProvider(rows, [
            makeEnemy('sp:1', 'Duskenlight', 'Duskenlight', 'char:1', 'Goblin'),
            makeEnemy('sp:2', 'Braxonian', 'Braxonian', 'char:2', 'Orc')
        ], [], [], []);
        const entries = provider.buildIndex();

        expect(entries).toHaveLength(2);
        const keys = entries
            .map((e) => e.result)
            .filter(isItemResult)
            .map((r) => r.itemStableKey);
        expect(keys).toContain('item:a');
        expect(keys).toContain('item:b');
    });

    it('indexes items whose source locations cannot be resolved', () => {
        const rows = [
            row('item:has-spawn', 'Dropped Sword', 'char:spawn', 'Goblin', 10),
            row('item:no-spawn', 'Vendor Only', 'char:none', 'Merchant', 50)
        ];
        const provider = new ItemSearchProvider(rows, [
            makeEnemy('sp:1', 'Duskenlight', 'Duskenlight', 'char:spawn', 'Goblin')
            // No marker for char:none — merchant never spawns on the map
        ], [], [], []);
        const entries = provider.buildIndex();

        expect(entries).toHaveLength(2);
        const result = entries.find((entry) =>
            isItemResult(entry.result) && entry.result.itemStableKey === 'item:no-spawn'
        )?.result;
        expect(result).toBeDefined();
        if (result && isItemResult(result)) {
            expect(result.hasKnownSource).toBe(false);
            expect(result.sourceCounts).toEqual({
                droppers: 0,
                vendors: 0,
                miningNodes: 0,
                fishingSpots: 0,
                itemBags: 0
            });
        }
    });

    it('indexes a vendor-only item when its vendor spawns', () => {
        const provider = new ItemSearchProvider(
            [vendorRow('item:scroll', 'Vendor Scroll', 'char:merchant', 'Merchant', 125)],
            [makeNpc('sp:merchant', 'Duskenlight', 'Duskenlight', 'char:merchant', 'Merchant')],
            [],
            [],
            []
        );

        const result = provider.getResult('item:scroll');
        expect(result).not.toBeNull();
        expect(result?.sourceCounts).toEqual({
            droppers: 0,
            vendors: 1,
            miningNodes: 0,
            fishingSpots: 0,
            itemBags: 0
        });
    });

    it('resolves fishing-only items and deduplicates day and night rows for one water', () => {
        const water = makeWater('water:1', 'Jaws', 'Jaws', [10, 11]);
        const provider = new ItemSearchProvider(
            [
                fishingRow('item:fish', 'Rare Fish', 'water:1', 'day', 25),
                fishingRow('item:fish', 'Rare Fish', 'water:1', 'night', 40)
            ],
            [],
            [],
            [water],
            []
        );

        const result = provider.getResult('item:fish');
        expect(result?.sourceCounts.fishingSpots).toBe(1);
        expect(provider.getMarkersForItem('item:fish')).toEqual([water]);
        expect(provider.getSourcesForItem('item:fish')).toHaveLength(2);
        expect(provider.getSourcesForItem('item:fish').every((source) => source.kind === 'fishing')).toBe(true);
    });

    it('resolves mining and bag sources by marker key and drops missing markers', () => {
        const mining = makeMiningNode('mining:1', 'Braxonian', 'Braxonian', [20, 21]);
        const bag = makeBag('bag:1', 'Silkengrass', 'Silkengrass', [30, 31]);
        const provider = new ItemSearchProvider(
            [
                miningRow('item:resources', 'Resources', 'mining:1', 50),
                miningRow('item:resources', 'Resources', 'mining:missing', 50),
                bagRow('item:resources', 'Resources', 'bag:1'),
                bagRow('item:resources', 'Resources', 'bag:missing')
            ],
            [],
            [mining],
            [],
            [bag]
        );

        expect(provider.getResult('item:resources')?.sourceCounts).toEqual({
            droppers: 0,
            vendors: 0,
            miningNodes: 1,
            fishingSpots: 0,
            itemBags: 1
        });
        expect(provider.getSourcesForItem('item:resources')).toHaveLength(2);
        expect(provider.getSourcesForItem('item:resources').map((source) => source.kind)).toEqual([
            'mining',
            'bag'
        ]);

        const unresolvable = new ItemSearchProvider(
            [
                miningRow('item:missing', 'Missing', 'mining:none', 1),
                fishingRow('item:missing', 'Missing', 'water:none', 'day', 1),
                bagRow('item:missing', 'Missing', 'bag:none'),
                vendorRow('item:missing', 'Missing', 'char:none', 'Missing', 1),
                row('item:missing', 'Missing', 'char:none', 'Missing', 1)
            ],
            [],
            [],
            [],
            []
        );
        expect(unresolvable.getResult('item:missing')?.hasKnownSource).toBe(false);
        expect(unresolvable.buildIndex()).toHaveLength(1);
    });

    it('returns resource sources and highlights every resource marker position', () => {
        const mining = makeMiningNode('mining:1', 'Braxonian', 'Braxonian', [20, 21]);
        const water = makeWater('water:1', 'Jaws', 'Jaws', [30, 31]);
        const bag = makeBag('bag:1', 'Silkengrass', 'Silkengrass', [40, 41]);
        const provider = new ItemSearchProvider(
            [
                miningRow('item:all', 'All Resources', 'mining:1', 10),
                fishingRow('item:all', 'All Resources', 'water:1', 'day', 20),
                bagRow('item:all', 'All Resources', 'bag:1')
            ],
            [],
            [mining],
            [water],
            [bag]
        );

        const sources = provider.getSourcesForItem('item:all');
        expect(sources.map((source) => source.kind)).toEqual(['mining', 'fishing', 'bag']);
        const result = provider.getResult('item:all');
        expect(result).not.toBeNull();
        if (!result) return;
        const highlight = provider.resolveHighlight(result);
        expect(highlight).toEqual({
            type: 'positions',
            positions: [[20, 21], [30, 31], [40, 41]],
            stableKeys: ['mining:1', 'water:1', 'bag:1']
        });
    });

    it('counts zones contributed by different source kinds', () => {
        const provider = new ItemSearchProvider(
            [
                row('item:mixed', 'Mixed Sources', 'char:dropper', 'Goblin', 10),
                miningRow('item:mixed', 'Mixed Sources', 'mining:1', 20)
            ],
            [makeEnemy('sp:dropper', 'Duskenlight', 'Duskenlight', 'char:dropper', 'Goblin')],
            [makeMiningNode('mining:1', 'Braxonian', 'Braxonian')],
            [],
            []
        );

        expect(provider.getResult('item:mixed')?.zoneCount).toBe(2);
    });
    it('resolves highlight to positions of all dropper spawns', () => {
        const rows = [row('item:1', 'Gem', 'char:1', 'Goblin', 5)];
        const enemy1 = makeEnemy('sp:1', 'Duskenlight', 'Duskenlight', 'char:1', 'Goblin');
        const enemy2 = makeEnemy('sp:2', 'Braxonian', 'Braxonian', 'char:1', 'Goblin');
        const provider = new ItemSearchProvider(rows, [enemy1, enemy2], [], [], []);

        const result = provider.resolveHighlight({
            type: 'item',
            itemStableKey: 'item:1',
            itemName: 'Gem',
            iconName: null,
            wikiPageName: null,
            sourceCounts: {
                droppers: 1,
                vendors: 0,
                miningNodes: 0,
                fishingSpots: 0,
                itemBags: 0
            },
            zoneCount: 2,
            hasKnownSource: true
        });

        expect(result.type).toBe('positions');
        if (result.type === 'positions') {
            expect(result.positions).toHaveLength(2);
            expect(result.stableKeys).toContain('sp:1');
            expect(result.stableKeys).toContain('sp:2');
        }
    });

    it('getMarkersForItem and getSourcesForItem return data for the item', () => {
        const rows = [
            row('item:1', 'Gem', 'char:1', 'Goblin', 5, { isRare: true }),
            row('item:1', 'Gem', 'char:2', 'Orc', 30, { isUnique: true })
        ];
        const provider = new ItemSearchProvider(rows, [
            makeEnemy('sp:1', 'Duskenlight', 'Duskenlight', 'char:1', 'Goblin'),
            makeEnemy('sp:2', 'Duskenlight', 'Duskenlight', 'char:2', 'Orc')
        ], [], [], []);

        const markers = provider.getMarkersForItem('item:1');
        expect(markers).toHaveLength(2);

        const dropSources = provider
            .getSourcesForItem('item:1')
            .filter((source) => source.kind === 'drop');
        expect(dropSources).toHaveLength(2);
        // Sorted by drop probability descending, preserving the old row assertion intent
        const probabilities = dropSources
            .map((source) => source.row.dropProbability)
            .sort((a, b) => b - a);
        expect(probabilities).toEqual([30, 5]);
    });

    it('getResult returns the cached result for URL restore', () => {
        const rows = [row('item:1', 'Gem', 'char:1', 'Goblin', 5)];
        const provider = new ItemSearchProvider(rows, [
            makeEnemy('sp:1', 'Duskenlight', 'Duskenlight', 'char:1', 'Goblin')
        ], [], [], []);

        const result = provider.getResult('item:1');
        expect(result).not.toBeNull();
        expect(result?.itemStableKey).toBe('item:1');
        expect(result?.itemName).toBe('Gem');
        expect(result?.sourceCounts.droppers).toBe(1);
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
        ], [], [], []);
        const entries = provider.buildIndex();

        expect(entries).toHaveLength(1);
        const result = entries[0].result;
        expect(isItemResult(result)).toBe(true);
        if (isItemResult(result)) {
            expect(result.sourceCounts.droppers).toBe(2); // one enemy + one npc character
            expect(result.zoneCount).toBe(2); // Duskenlight + Braxonian
        }
    });
});
