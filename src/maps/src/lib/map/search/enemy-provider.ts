/**
 * Enemy search provider.
 *
 * Groups all enemy spawn points by character name. A single search result
 * represents ALL spawn points across all zones where that character can appear.
 */

import { Rarity } from '$lib/map-markers';
import type { UnlocatedEnemy } from '$lib/map-markers';
import type { WorldEnemy } from '$lib/types/world-map';
import type {
    SearchProvider,
    IndexEntry,
    ResolvedHighlight,
    SearchResult,
    EnemySearchResult
} from './types';

export class EnemySearchProvider implements SearchProvider {
    readonly categoryLabel = 'Enemies';
    readonly categoryOrder = 0;

    /** Name → all WorldEnemy markers that contain a character with that name */
    readonly enemyByName: Map<string, WorldEnemy[]>;
    /** Name → map-visible enemies whose spawn point is runtime-selected. */
    readonly unlocatedByName: Map<string, UnlocatedEnemy[]>;

    constructor(
        enemiesCommon: WorldEnemy[],
        enemiesRare: WorldEnemy[],
        enemiesUnique: WorldEnemy[],
        unlocatedEnemies: UnlocatedEnemy[]
    ) {
        this.enemyByName = new Map();
        this.unlocatedByName = new Map();

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

        for (const enemy of unlocatedEnemies) {
            const existing = this.unlocatedByName.get(enemy.name);
            if (existing) existing.push(enemy);
            else this.unlocatedByName.set(enemy.name, [enemy]);
        }
    }

    getResult(name: string): EnemySearchResult | null {
        const markers = this.enemyByName.get(name) ?? [];
        if (markers.length > 0) {
            const zones = new Set(markers.map((marker) => marker.zone));
            const characters = markers.flatMap((marker) =>
                marker.characters.filter((character) => character.name === name)
            );
            const effectiveRarity = characters.some(
                (character) => character.effectiveRarity === Rarity.unique
            )
                ? Rarity.unique
                : characters.some((character) => character.effectiveRarity === Rarity.rare)
                  ? Rarity.rare
                  : Rarity.common;
            return {
                type: 'enemy',
                name,
                effectiveRarity,
                spawnCount: markers.length,
                zoneCount: zones.size
            };
        }

        const unlocated = this.unlocatedByName.get(name) ?? [];
        if (unlocated.length === 0) return null;
        const effectiveRarity = unlocated.some((enemy) => enemy.effectiveRarity === Rarity.unique)
            ? Rarity.unique
            : unlocated.some((enemy) => enemy.effectiveRarity === Rarity.rare)
              ? Rarity.rare
              : Rarity.common;
        return {
            type: 'enemy',
            name,
            effectiveRarity,
            spawnCount: 0,
            zoneCount: 0
        };
    }

    buildIndex(): IndexEntry[] {
        const entries: IndexEntry[] = [];
        const names = new Set([...this.enemyByName.keys(), ...this.unlocatedByName.keys()]);

        for (const name of names) {
            const result = this.getResult(name);
            if (!result) continue;
            entries.push({ searchText: name.toLowerCase(), result });
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

    getUnlocated(name: string): UnlocatedEnemy[] {
        return this.unlocatedByName.get(name) ?? [];
    }

    /** Get all enemy markers for a given character name (for popup rendering) */
    getMarkers(name: string): WorldEnemy[] {
        return this.enemyByName.get(name) ?? [];
    }
}
