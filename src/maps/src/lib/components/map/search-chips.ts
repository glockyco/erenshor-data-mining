import type { SearchCategory, SearchResponse } from '$lib/map/search';

export type Category = 'all' | 'live' | SearchCategory;

export interface ChipCount {
    visible: number;
    total: number;
    hasMore: boolean;
}

/**
 * Count visible and total matches by category for chip display. Static category
 * counts come from their capped result lists; All aggregates static and live
 * projections, while live has a separate cap.
 */
export function computeChipCounts(
    response: SearchResponse,
    liveCount: number,
    liveTotal = liveCount
): Map<string, ChipCount> {
    const counts = new Map<string, ChipCount>();
    counts.set('all', {
        visible: response.matches.length + liveCount,
        total: response.total + liveTotal,
        hasMore: response.hasMore || liveTotal > liveCount
    });
    const staticCategories: SearchCategory[] = ['item', 'enemy', 'npc', 'zone'];
    for (const category of staticCategories) {
        const categoryResult = response.categories[category];
        counts.set(category, {
            visible: categoryResult.matches.length,
            total: categoryResult.total,
            hasMore: categoryResult.hasMore
        });
    }

    if (liveCount > 0) {
        counts.set('live', {
            visible: liveCount,
            total: liveTotal,
            hasMore: liveTotal > liveCount
        });
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
