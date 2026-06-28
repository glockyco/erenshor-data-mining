import { describe, it, expect } from 'vitest';
import type { SearchMatch } from '$lib/map/search';
import { computeChipCounts } from './search-chips';

describe('computeChipCounts', () => {
    it('counts static results by type', () => {
        const matches: SearchMatch[] = [
            { result: { type: 'item', itemStableKey: 'a', itemName: 'A', iconName: null, wikiPageName: null, dropperCount: 1, zoneCount: 1 }, matchRange: null },
            { result: { type: 'item', itemStableKey: 'b', itemName: 'B', iconName: null, wikiPageName: null, dropperCount: 1, zoneCount: 1 }, matchRange: null },
            { result: { type: 'enemy', name: 'Goblin', effectiveRarity: 2, spawnCount: 1, zoneCount: 1 }, matchRange: null }
        ];
        const counts = computeChipCounts(matches, 0);
        expect(counts.get('item')).toBe(2);
        expect(counts.get('enemy')).toBe(1);
        expect(counts.get('npc')).toBe(0);
        expect(counts.get('zone')).toBe(0);
    });

    it('includes live count when provided', () => {
        const matches: SearchMatch[] = [
            { result: { type: 'item', itemStableKey: 'a', itemName: 'A', iconName: null, wikiPageName: null, dropperCount: 1, zoneCount: 1 }, matchRange: null }
        ];
        const counts = computeChipCounts(matches, 3);
        expect(counts.get('live')).toBe(3);
    });

    it('excludes live key when liveCount is 0', () => {
        const matches: SearchMatch[] = [];
        const counts = computeChipCounts(matches, 0);
        expect(counts.has('live')).toBe(false);
    });
});
