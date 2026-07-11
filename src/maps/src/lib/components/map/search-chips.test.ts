import { describe, it, expect } from 'vitest';
import { emptySearchResponse, type SearchMatch, type SearchResponse } from '$lib/map/search';
import { computeChipCounts, formatChipCount } from './search-chips';

function responseFor(matches: SearchMatch[]): SearchResponse {
    const response = emptySearchResponse();
    response.matches = matches;
    response.total = matches.length;
    for (const match of matches) {
        const category = response.categories[match.result.type];
        category.matches.push(match);
        category.total += 1;
    }
    return response;
}

describe('computeChipCounts', () => {
    it('reports visible and total static results by type', () => {
        const matches: SearchMatch[] = [
            { result: { type: 'item', itemStableKey: 'a', itemName: 'A', iconName: null, wikiPageName: null, dropperCount: 1, zoneCount: 1 }, matchRange: null },
            { result: { type: 'item', itemStableKey: 'b', itemName: 'B', iconName: null, wikiPageName: null, dropperCount: 1, zoneCount: 1 }, matchRange: null },
            { result: { type: 'enemy', name: 'Goblin', effectiveRarity: 2, spawnCount: 1, zoneCount: 1 }, matchRange: null }
        ];
        const counts = computeChipCounts(responseFor(matches), 0);
        expect(counts.get('all')).toEqual({ visible: 3, total: 3, hasMore: false });
        expect(counts.get('item')).toEqual({ visible: 2, total: 2, hasMore: false });
        expect(counts.get('enemy')).toEqual({ visible: 1, total: 1, hasMore: false });
        expect(counts.get('npc')).toEqual({ visible: 0, total: 0, hasMore: false });
        expect(counts.get('zone')).toEqual({ visible: 0, total: 0, hasMore: false });
    });

    it('sums category caps for the All pill', () => {
        const response = responseFor([
            {
                result: {
                    type: 'item',
                    itemStableKey: 'item:a',
                    itemName: 'A',
                    iconName: null,
                    wikiPageName: null,
                    dropperCount: 1,
                    zoneCount: 1
                },
                matchRange: null
            },
            {
                result: {
                    type: 'enemy',
                    name: 'Goblin',
                    effectiveRarity: 2,
                    spawnCount: 1,
                    zoneCount: 1
                },
                matchRange: null
            },
            {
                result: {
                    type: 'npc',
                    name: 'Merchant',
                    isVendor: true,
                    spawnCount: 1,
                    zoneCount: 1
                },
                matchRange: null
            },
            { result: { type: 'zone', key: 'zone:a', name: 'Zone A' }, matchRange: null }
        ]);
        const categorySpecs = [
            ['item', 20, 21, true],
            ['enemy', 5, 5, false],
            ['npc', 20, 24, true],
            ['zone', 7, 7, false]
        ] as const;

        for (const [category, visible, total, hasMore] of categorySpecs) {
            const categoryResult = response.categories[category];
            const seed = categoryResult.matches[0]!;
            categoryResult.matches = Array.from({ length: visible }, () => seed);
            categoryResult.total = total;
            categoryResult.hasMore = hasMore;
        }
        response.matches = response.categories.item.matches;
        response.total = 57;

        const counts = computeChipCounts(response, 0);
        expect(counts.get('all')).toEqual({ visible: 52, total: 57, hasMore: true });
        expect(formatChipCount(counts.get('all')!)).toBe('52+');
    });
    it('discloses live totals and aggregates them into All', () => {
        const response = responseFor([
            { result: { type: 'item', itemStableKey: 'a', itemName: 'A', iconName: null, wikiPageName: null, dropperCount: 1, zoneCount: 1 }, matchRange: null }
        ]);
        const counts = computeChipCounts(response, 3, 7);
        expect(counts.get('all')).toEqual({ visible: 4, total: 8, hasMore: true });
        expect(counts.get('live')).toEqual({ visible: 3, total: 7, hasMore: true });
    });

    it('excludes live key when liveCount is 0', () => {
        const counts = computeChipCounts(responseFor([]), 0);
        expect(counts.has('live')).toBe(false);
        expect(counts.get('all')).toEqual({ visible: 0, total: 0, hasMore: false });
    });
});

describe('formatChipCount', () => {
    it('uses a plus sign for capped results', () => {
        expect(formatChipCount({ visible: 20, total: 153, hasMore: true })).toBe('20+');
    });

    it('uses the exact count when the result set fits', () => {
        expect(formatChipCount({ visible: 4, total: 4, hasMore: false })).toBe('4');
    });
});
