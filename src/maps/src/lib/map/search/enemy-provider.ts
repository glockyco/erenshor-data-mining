/**
 * Enemy search provider.
 *
 * Groups all enemy spawn points by character name. A single search result
 * represents ALL spawn points across all zones where that character can appear.
 */

import { mostNotableEnemyTier } from '$lib/map-markers';
import type { UnlocatedEnemy } from '$lib/map-markers';
import type { WorldEnemy, WorldTreasureLoc } from '$lib/types/world-map';
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
    readonly treasureByName = new Map<string, WorldTreasureLoc[]>();

    constructor(
        enemiesEnemy: WorldEnemy[],
        enemiesElite: WorldEnemy[],
        enemiesBoss: WorldEnemy[],
        enemiesChest: WorldEnemy[],
        unlocatedEnemies: UnlocatedEnemy[],
        treasureLocs: WorldTreasureLoc[]
    ) {
        this.enemyByName = new Map();
        this.unlocatedByName = new Map();

        for (const enemies of [enemiesEnemy, enemiesElite, enemiesBoss, enemiesChest]) {
            for (const marker of enemies) {
                const seen = new Set<string>();
                for (const char of marker.characters) {
                    if (char.encounterTier === 'npc') continue;
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
        for (const marker of treasureLocs) {
            for (const name of new Set([...marker.chests, ...marker.guardians].map((c) => c.name))) {
                const sites = this.treasureByName.get(name) ?? [];
                sites.push(marker);
                this.treasureByName.set(name, sites);
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
        const sites = this.getTreasureSites(name);
        if (sites.length > 0) {
            return {
                type: 'enemy',
                name,
                encounterTier: sites.some((site) => site.chests.some((c) => c.name === name)) ? 'chest' : 'enemy',
                spawnCount: sites.length,
                locationKind: 'dig-site',
                zoneCount: new Set(sites.map((site) => site.zone)).size
            };
        }
        if (markers.length > 0) {
            const zones = new Set(markers.map((marker) => marker.zone));
            const characters = markers.flatMap((marker) =>
                marker.characters.filter((character) => character.name === name && character.encounterTier !== 'npc')
            );
            const encounterTier = mostNotableEnemyTier(characters);
            return {
                type: 'enemy',
                name,
                encounterTier,
                spawnCount: markers.length,
                zoneCount: zones.size
            };
        }

        const unlocated = this.unlocatedByName.get(name) ?? [];
        if (unlocated.length === 0) return null;
        const encounterTier = mostNotableEnemyTier(unlocated);
        return {
            type: 'enemy',
            name,
            encounterTier,
            spawnCount: 0,
            zoneCount: 0
        };
    }

    buildIndex(): IndexEntry[] {
        const entries: IndexEntry[] = [];
        const names = new Set([...this.enemyByName.keys(), ...this.unlocatedByName.keys(), ...this.treasureByName.keys()]);

        for (const name of names) {
            const result = this.getResult(name);
            if (!result) continue;
            entries.push({ searchText: name.toLowerCase(), result });
        }

        return entries;
    }

    resolveHighlight(result: SearchResult): ResolvedHighlight {
        if (result.type !== 'enemy') return { type: 'none' };

        const markers = this.treasureByName.get(result.name) ?? this.enemyByName.get(result.name);
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

    getTreasureSites(name: string): WorldTreasureLoc[] {
        return this.treasureByName.get(name) ?? [];
    }
}
