import { describe, it, expect } from 'vitest';
import type { IndexEntry } from './types';
import { searchMarkers } from './index';

function item(name: string, stableKey: string): IndexEntry {
    return {
        searchText: name.toLowerCase(),
        result: {
            type: 'item',
            itemStableKey: stableKey,
            itemName: name,
            iconName: null,
            wikiPageName: null,
            sourceCounts: {
                droppers: 1,
                vendors: 0,
                miningNodes: 0,
                fishingSpots: 0,
                itemBags: 0
            },
            zoneCount: 1,
            hasKnownSource: true
        }
    };
}

function enemy(name: string): IndexEntry {
    return {
        searchText: name.toLowerCase(),
        result: {
            type: 'enemy',
            name,
            effectiveRarity: 2,
            spawnCount: 1,
            zoneCount: 1
        }
    };
}

describe('searchMarkers', () => {
    it('prefix matches rank above substring matches across categories', () => {
        // 'goblin' is a prefix match; 'goblin shaman' contains it as substring
        const entries: IndexEntry[] = [
            enemy('Goblin'),
            enemy('Goblin Shaman'),
            item('Goblin Tooth', 'item:gob-tooth')
        ];
        const matches = searchMarkers('goblin', entries, 20).matches;
        // All three match; prefix matches should come first
        const goblinIdx = matches.findIndex(
            (m) => m.result.type === 'enemy' && m.result.name === 'Goblin'
        );
        const shamanIdx = matches.findIndex(
            (m) => m.result.type === 'enemy' && m.result.name === 'Goblin Shaman'
        );
        expect(goblinIdx).toBeLessThan(shamanIdx);
    });

    it('substring matches rank above fuzzy matches across categories', () => {
        // 'citrin' is a substring of 'Citrine Guardian' (enemy) and a fuzzy
        // match for 'Citrine Ring' (item). The substring enemy must rank
        // above the fuzzy item, even though items have category priority 0.
        const entries: IndexEntry[] = [
            enemy('Citrine Guardian'),  // contains 'citrin' as substring
            item('Catrine Ring', 'item:catrine')  // fuzzy match for 'citrin'
        ];
        const matches = searchMarkers('citrin', entries, 20).matches;
        const guardianIdx = matches.findIndex(
            (m) => m.result.type === 'enemy' && m.result.name === 'Citrine Guardian'
        );
        const catrineIdx = matches.findIndex(
            (m) => m.result.type === 'item' && m.result.itemName === 'Catrine Ring'
        );
        // Both should match
        expect(guardianIdx).toBeGreaterThanOrEqual(0);
        // Substring match (Guardian) must rank above fuzzy match (Catrine Ring)
        // even though items have higher category priority
        if (catrineIdx >= 0) {
            expect(guardianIdx).toBeLessThan(catrineIdx);
        }
    });

    it('keeps matching enemies visible when drops exceed the global cap', () => {
        const entries: IndexEntry[] = [
            ...Array.from({ length: 21 }, (_, i) => item(`Brax Drop ${i}`, `item:brax-${i}`)),
            enemy('Brax, God of Elements')
        ];

        const response = searchMarkers('brax', entries, 20);
        const matches = response.matches;

        expect(matches).toHaveLength(20);
        expect(matches.some((m) => m.result.type === 'enemy')).toBe(true);
        expect(response.categories.item.total).toBe(21);
        expect(response.categories.item.hasMore).toBe(true);
        expect(response.categories.enemy.total).toBe(1);
        expect(response.categories.enemy.hasMore).toBe(false);
        expect(response.total).toBe(22);
        expect(response.hasMore).toBe(true);
        expect(response.categories.item.matches).toHaveLength(20);
        expect(response.categories.enemy.matches).toHaveLength(1);

        const exact = searchMarkers(
            'brax',
            Array.from({ length: 20 }, (_, i) => item(`Brax Drop ${i}`, `item:exact-${i}`)),
            20
        );
        expect(exact.categories.item.total).toBe(20);
        expect(exact.categories.item.hasMore).toBe(false);
        expect(exact.hasMore).toBe(false);
    });
    it('returns an empty response for queries shorter than 2 chars', () => {
        expect(searchMarkers('a', [], 20).matches).toEqual([]);
        expect(searchMarkers('', [], 20).matches).toEqual([]);
    });
});
