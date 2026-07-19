import { describe, it, expect } from 'vitest';
import type { IndexEntry } from './types';
import { searchTiered, searchTieredWithTotal } from './fuse-index';

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

const entries: IndexEntry[] = [
    enemy('Goblin'),
    enemy('Luminstone Guardian'),
    item('Luminstone'),
    item('Golden Luminstone Ring'),
    enemy('Orc')
];

describe('searchTiered', () => {
    it('matches punctuation-delimited names without requiring punctuation', () => {
        const matches = searchTiered('Brax', [enemy('Brax, God of Elements')], 20);

        expect(matches).toHaveLength(1);
        expect(matches[0].result).toMatchObject({ name: 'Brax, God of Elements' });
        expect(matches[0].matchRange).toEqual([0, 4]);
    });

    it('normalizes punctuation in multi-word queries', () => {
        const matches = searchTiered('Brax, God', [enemy('Brax, God of Elements')], 20);

        expect(matches).toHaveLength(1);
        expect(matches[0].matchRange).toEqual([0, 9]);
    });
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

    it('reports fuzzy suggestions as candidate totals', () => {
        const result = searchTieredWithTotal('lumsten', entries, 1);

        expect(result.matches).toHaveLength(1);
        expect(result.matches[0].matchRange).toBeNull();
        expect(result.total).toBeGreaterThanOrEqual(result.matches.length);
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
