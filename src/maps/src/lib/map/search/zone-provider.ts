/**
 * Zone search provider.
 *
 * Indexes zones by display name. Zone search results resolve to the
 * existing zone selection system (flyToBounds + zone popup), not to
 * point highlights.
 */

import type { ZoneWorldPosition } from '$lib/types/world-map';
import type { SearchProvider, IndexEntry, ResolvedHighlight, SearchResult } from './types';

export class ZoneSearchProvider implements SearchProvider {
    readonly categoryLabel = 'Zones';
    readonly categoryOrder = 2;

    private readonly zoneByKey: Map<string, ZoneWorldPosition>;

    constructor(zones: ZoneWorldPosition[]) {
        this.zoneByKey = new Map();
        for (const zone of zones) {
            this.zoneByKey.set(zone.key, zone);
        }
    }

    buildIndex(): IndexEntry[] {
        const entries: IndexEntry[] = [];

        for (const zone of this.zoneByKey.values()) {
            entries.push({
                searchText: zone.name.toLowerCase(),
                result: {
                    type: 'zone',
                    key: zone.key,
                    name: zone.name
                }
            });
        }

        return entries;
    }

    resolveHighlight(result: SearchResult): ResolvedHighlight {
        if (result.type !== 'zone') return { type: 'none' };

        const zone = this.zoneByKey.get(result.key);
        if (!zone) return { type: 'none' };

        return { type: 'zone', zone };
    }

    /** Get zone by key (for direct lookup during URL restore) */
    getZone(key: string): ZoneWorldPosition | undefined {
        return this.zoneByKey.get(key);
    }
}
