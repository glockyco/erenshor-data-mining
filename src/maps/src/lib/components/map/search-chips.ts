import type { SearchMatch } from '$lib/map/search';

export type Category = 'all' | 'live' | 'item' | 'enemy' | 'npc' | 'zone';

/**
 * Count results by category for chip display. Includes a 'live' key only
 * when liveCount > 0 (companion mod connected); static types are always
 * present (0 count if no matches).
 */
export function computeChipCounts(
    matches: SearchMatch[],
    liveCount: number
): Map<string, number> {
    const counts = new Map<string, number>([
        ['item', 0],
        ['enemy', 0],
        ['npc', 0],
        ['zone', 0]
    ]);
    if (liveCount > 0) counts.set('live', liveCount);
    for (const m of matches) {
        const type = m.result.type;
        counts.set(type, (counts.get(type) ?? 0) + 1);
    }
    return counts;
}

/** Chip display config: order + label. */
export const CHIP_CONFIG: { key: Category; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'live', label: 'Live' },
    { key: 'item', label: 'Drops' },
    { key: 'enemy', label: 'Enemies' },
    { key: 'npc', label: 'NPCs' },
    { key: 'zone', label: 'Zones' }
];
