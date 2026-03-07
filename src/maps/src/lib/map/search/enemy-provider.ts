/**
 * Enemy search provider.
 *
 * Groups all enemy spawn points by character name. A single search result
 * represents ALL spawn points across all zones where that character can appear.
 */

import { Rarity } from '$lib/map-markers';
import type { WorldEnemy } from '$lib/types/world-map';
import type { SearchProvider, IndexEntry, ResolvedHighlight, SearchResult } from './types';

export class EnemySearchProvider implements SearchProvider {
    readonly categoryLabel = 'Enemies';
    readonly categoryOrder = 0;

    /** Name → all WorldEnemy markers that contain a character with that name */
    readonly enemyByName: Map<string, WorldEnemy[]>;

    constructor(
        enemiesCommon: WorldEnemy[],
        enemiesRare: WorldEnemy[],
        enemiesUnique: WorldEnemy[]
    ) {
        this.enemyByName = new Map();

        for (const enemies of [enemiesCommon, enemiesRare, enemiesUnique]) {
            for (const marker of enemies) {
                const seen = new Set<string>();
                for (const char of marker.characters) {
                    if (seen.has(char.name)) continue;
                    seen.add(char.name);
                    const existing = this.enemyByName.get(char.name);
                    if (existing) {
                        existing.push(marker);
                    } else {
                        this.enemyByName.set(char.name, [marker]);
                    }
                }
            }
        }
    }

    buildIndex(): IndexEntry[] {
        const entries: IndexEntry[] = [];

        for (const [name, markers] of this.enemyByName) {
            const zones = new Set(markers.map((m) => m.zone));
            // Derive effective rarity from character-level flags. A character
            // with any common spawn is always shown as common regardless of
            // whether it also appears at rare/unique spawn points.
            const chars = markers.flatMap((m) => m.characters.filter((c) => c.name === name));
            const effectiveRarity = chars.some((c) => c.effectiveRarity === Rarity.common)
                ? Rarity.common
                : chars.some((c) => c.effectiveRarity === Rarity.unique)
                  ? Rarity.unique
                  : Rarity.rare;

            entries.push({
                searchText: name.toLowerCase(),
                result: {
                    type: 'enemy',
                    name,
                    effectiveRarity,
                    spawnCount: markers.length,
                    zoneCount: zones.size
                }
            });
        }

        return entries;
    }

    resolveHighlight(result: SearchResult): ResolvedHighlight {
        if (result.type !== 'enemy') return { type: 'none' };

        const markers = this.enemyByName.get(result.name);
        if (!markers || markers.length === 0) return { type: 'none' };

        return {
            type: 'positions',
            positions: markers.map((m) => m.worldPosition),
            stableKeys: markers.map((m) => m.stableKey)
        };
    }

    /** Get all enemy markers for a given character name (for popup rendering) */
    getMarkers(name: string): WorldEnemy[] {
        return this.enemyByName.get(name) ?? [];
    }
}
