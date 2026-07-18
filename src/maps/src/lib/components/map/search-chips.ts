import type { SearchCategory, SearchResponse } from '$lib/map/search';

export type Category = 'all' | 'live' | SearchCategory;

export interface ChipCount {
    visible: number;
    total: number;
    hasMore: boolean;
}

export function formatChipCount(count: ChipCount): string {
    return `${count.visible}${count.hasMore ? '+' : ''}`;
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
    const staticCategories: SearchCategory[] = ['item', 'enemy', 'npc', 'zone'];
    const staticVisible = staticCategories.reduce(
        (sum, category) => sum + response.categories[category].matches.length,
        0
    );
    const staticHasMore = staticCategories.some(
        (category) => response.categories[category].hasMore
    );

    counts.set('all', {
        visible: staticVisible + liveCount,
        total: response.total + liveTotal,
        hasMore: staticHasMore || liveTotal > liveCount
    });

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

export function getAvailableCategories(counts: Map<string, ChipCount>): Category[] {
    return CHIP_CONFIG.filter((chip) => {
        if (chip.key === 'all') return true;
        if (chip.key === 'live') return counts.has('live');
        return (counts.get(chip.key)?.total ?? 0) > 0;
    }).map((chip) => chip.key);
}

/** Chip display config: order + label. */
export const CHIP_CONFIG: { key: Category; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'live', label: 'Live' },
    { key: 'item', label: 'Items' },
    { key: 'enemy', label: 'Enemies' },
    { key: 'npc', label: 'NPCs' },
    { key: 'zone', label: 'Zones' }
];
