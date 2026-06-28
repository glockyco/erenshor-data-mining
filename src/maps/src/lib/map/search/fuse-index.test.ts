import { describe, it, expect } from 'vitest';
import type { IndexEntry } from './types';
import { searchTiered } from './fuse-index';

function enemy(name: string): IndexEntry {
    return {
        searchText: name.toLowerCase(),
        result: { type: 'enemy', name, effectiveRarity: 2, spawnCount: 1, zoneCount: 1 }
    };
}
function item(name: string): IndexEntry {
    return {
        searchText: name.toLowerCase(),
        result: {
            type: 'item',
            itemStableKey: `item:${name}`,
            itemName: name,
            iconName: null,
            wikiPageName: null,
            dropperCount: 1,
            zoneCount: 1
        }
    };
}

const entries: IndexEntry[] = [
    enemy('Goblin'),
    enemy('Luminstone Guardian'),
    item('Luminstone'),
    item('Golden Luminstone Ring'),
    enemy('Orc')
];

describe('searchTiered', () => {
    it('returns prefix matches first with matchRange', () => {
        const matches = searchTiered('lumin', entries, 20);
        expect(matches.length).toBeGreaterThan(0);
        const first = matches[0];
        expect(first.matchRange).not.toBeNull();
        expect(first.matchRange).toEqual([0, 5]);
    });

    it('returns substring matches after prefix matches', () => {
        const matches = searchTiered('stone', entries, 20);
        expect(matches.length).toBeGreaterThan(0);
        for (const m of matches) {
            expect(m.matchRange).not.toBeNull();
        }
    });

    it('falls back to fuzzy matching for typos', () => {
        const matches = searchTiered('lumsten', entries, 20);
        expect(matches.length).toBeGreaterThan(0);
        const hasFuzzy = matches.some((m) => m.matchRange === null);
        expect(hasFuzzy).toBe(true);
    });

    it('does not pad results with fuzzy matches when exact matches exist', () => {
        // 'lumin' has exact prefix/substring matches; fuzzy should NOT fire
        const matches = searchTiered('lumin', entries, 20);
        const hasFuzzy = matches.some((m) => m.matchRange === null);
        expect(hasFuzzy).toBe(false);
    });

    it('returns empty array for queries shorter than 2 chars', () => {
        expect(searchTiered('l', entries, 20)).toEqual([]);
        expect(searchTiered('', entries, 20)).toEqual([]);
    });

    it('prefix matches rank above substring matches', () => {
        const matches = searchTiered('lumin', entries, 20);
        const luminstoneIdx = matches.findIndex(
            (m) => m.result.type === 'item' && m.result.itemName === 'Luminstone'
        );
        const goldenIdx = matches.findIndex(
            (m) => m.result.type === 'item' && m.result.itemName === 'Golden Luminstone Ring'
        );
        expect(luminstoneIdx).toBeLessThan(goldenIdx);
    });
});
