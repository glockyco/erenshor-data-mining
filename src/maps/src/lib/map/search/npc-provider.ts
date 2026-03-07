/**
 * NPC search provider.
 *
 * Groups all NPC markers by character name. A single search result represents
 * ALL spawn points across all zones where that character can appear.
 */

import type { WorldNpc } from '$lib/types/world-map';
import type {
    SearchProvider,
    IndexEntry,
    ResolvedHighlight,
    SearchResult,
    NpcSearchResult
} from './types';

export class NpcSearchProvider implements SearchProvider {
    readonly categoryLabel = 'NPCs';
    readonly categoryOrder = 1;

    /** Character name → all WorldNpc markers containing that character */
    readonly npcByName: Map<string, WorldNpc[]>;

    constructor(npcs: WorldNpc[]) {
        this.npcByName = new Map();

        for (const marker of npcs) {
            const seen = new Set<string>();
            for (const char of marker.characters) {
                if (seen.has(char.name)) continue;
                seen.add(char.name);
                const existing = this.npcByName.get(char.name);
                if (existing) {
                    existing.push(marker);
                } else {
                    this.npcByName.set(char.name, [marker]);
                }
            }
        }
    }

    buildIndex(): IndexEntry[] {
        const entries: IndexEntry[] = [];

        for (const [name, markers] of this.npcByName) {
            const zones = new Set(markers.map((m) => m.zone));
            const hasVendor = markers.some((m) =>
                m.characters.some((c) => c.name === name && c.isVendor)
            );

            entries.push({
                searchText: name.toLowerCase(),
                result: {
                    type: 'npc',
                    name,
                    isVendor: hasVendor,
                    spawnCount: markers.length,
                    zoneCount: zones.size
                }
            });
        }

        return entries;
    }

    resolveHighlight(result: SearchResult): ResolvedHighlight {
        if (result.type !== 'npc') return { type: 'none' };

        const markers = this.npcByName.get((result as NpcSearchResult).name);
        if (!markers || markers.length === 0) return { type: 'none' };

        return {
            type: 'positions',
            positions: markers.map((m) => m.worldPosition),
            stableKeys: markers.map((m) => m.stableKey)
        };
    }

    /** Get all NPC markers for a given character name (for popup rendering) */
    getMarkers(name: string): WorldNpc[] {
        return this.npcByName.get(name) ?? [];
    }
}
