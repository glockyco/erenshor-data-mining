import type { EntityData } from './map/live/types';
import type { ItemAcquisition, ItemDisposition } from './item-provenance';
import type { ZoneLineDestinationContext } from './zone-line-destinations';

/** Character tiers in display order, most notable first. */
export const ENCOUNTER_TIER_ORDER = {
    boss: 0,
    elite: 1,
    enemy: 2,
    chest: 3,
    npc: 4
} as const;

export type EncounterTier = keyof typeof ENCOUNTER_TIER_ORDER;
export type EnemyTier = Exclude<EncounterTier, 'npc'>;

/** Inclusive encounter ranges overlap the slider, including either boundary. */
export function levelsOverlap(
    levelMin: number,
    levelMax: number,
    filter: [number, number]
): boolean {
    return levelMin <= filter[1] && levelMax >= filter[0];
}

export function compareEncounterTier(a: EncounterTier, b: EncounterTier): number {
    return ENCOUNTER_TIER_ORDER[a] - ENCOUNTER_TIER_ORDER[b];
}

export function mostNotableEnemyTier(
    characters: readonly { encounterTier: EncounterTier }[]
): EnemyTier {
    let best: EnemyTier | null = null;
    for (const { encounterTier } of characters) {
        if (encounterTier === 'npc') continue;
        if (!best || compareEncounterTier(encounterTier, best) < 0) best = encounterTier;
    }
    if (!best) throw new Error('Encounter marker has no non-NPC characters');
    return best;
}

/** Index stored tiers once, retaining the highest tier for names shared by characters. */
export function buildEncounterTierByName(
    markers: readonly { characters: readonly SpawnCharacter[] }[],
    unlocated: readonly UnlocatedEnemy[]
): Map<string, EnemyTier> {
    const tiers = new Map<string, EnemyTier>();
    const addTier = (name: string, tier: EncounterTier) => {
        if (tier === 'npc') return;
        const previous = tiers.get(name);
        if (!previous || compareEncounterTier(tier, previous) < 0) tiers.set(name, tier);
    };
    for (const marker of markers) {
        for (const character of marker.characters) addTier(character.name, character.encounterTier);
    }
    for (const enemy of unlocated) addTier(enemy.name, enemy.encounterTier);
    return tiers;
}

/** Use the mod's BossXp classification only when no stored tier matches the name. */
export function resolveLiveEncounterTier(
    entity: EntityData,
    tiers: ReadonlyMap<string, EnemyTier>
): EnemyTier {
    return (
        tiers.get(entity.name) ??
        (entity.rarity === 'boss' ? 'boss' : entity.rarity === 'rare' ? 'elite' : 'enemy')
    );
}

export type BaseMarker = {
    stableKey: string;
    position: { x: number; y: number };
    popup?: string;
};

export type UnlocatedEnemy = {
    stableKey: string;
    name: string;
    wikiPageName: string | null;
    portraitHash: string | null;
    level: number;
    levelMax: number;
    encounterTier: EnemyTier;
};

/** A furniture set of the Reliquary's planning table, with its wiki page. */
export type FurnitureSet = {
    name: string;
    wikiPageName: string | null;
};

// Character info for spawn points (characters that can spawn at a location)
export type SpawnCharacter = {
    name: string;
    wikiPageName: string | null;
    portraitHash: string | null;
    stableKey: string;
    /** Minimum prefab level among the represented copies. */
    level: number;
    levelMax: number;
    /** The game sets the level from the player's level, as for training dummies below level 42. */
    levelScalesWithPlayer: boolean;
    spawnChance: number | null;
    sourceScript: string | null;
    eventPosition: { x: number; y: number; z: number } | null;
    encounterTier: EncounterTier;
    isInvulnerable: boolean;
    /** Potential combat eligibility, independent of initial immunity. */
    canBeDamaged: boolean;
    isVendor: boolean;
    hasDialog: boolean;
    /** The furniture set whose placement in a room of the Reliquary's planning table turns this character on. */
    furniture: FurnitureSet | null;
};

/**
 * Whether the planning table explains why every character of a spawn starts disabled: each is
 * a furnishing that stands in a Reliquary room only while the room holds its furniture set.
 */
export function isFurnishingSpawn(
    characters: readonly Pick<SpawnCharacter, 'furniture'>[]
): boolean {
    return characters.length > 0 && characters.every((c) => c.furniture !== null);
}

/** The level of spawn characters as players read it: "Level 5", "Level 3–8", or that it scales. */
export function formatSpawnLevels(
    characters: Pick<SpawnCharacter, 'level' | 'levelMax' | 'levelScalesWithPlayer'>[]
): string {
    const fixed = characters.filter((c) => !c.levelScalesWithPlayer);
    if (fixed.length === 0) return "Scales with the player's level";
    const min = Math.min(...fixed.map((c) => c.level));
    const max = Math.max(...fixed.map((c) => c.levelMax));
    const range = min === max ? `Level ${min}` : `Level ${min}–${max}`;
    return fixed.length < characters.length ? `${range}, or scales with the player's level` : range;
}

// Movement data for patrol paths and wander ranges
export type MovementData = {
    wanderRange: number | null;
    patrolWaypoints: [number, number][] | null;
    loopPatrol: boolean;
};

// Item drop info for mining nodes
export type MiningNodeItem = {
    name: string;
    wikiPageName: string | null;
    dropChance: number;
    provenance: ItemAcquisition;
};

// Character details retain every acquisition identity, even when item aliases share a label.
export type CharacterDrop = {
    itemName: string;
    dropProbability: number;
    provenance: ItemAcquisition;
};

// Item → acquisition-source rows (preloaded for the map item search)
export type ItemSourceItemMeta = {
    itemStableKey: string;
    displayName: string;
    wikiPageName: string | null;
    iconHash: string | null;
};

export type ItemSourceRow = ItemSourceItemMeta & {
    kind: string;
    acquisitionKey: string;
    originatingItemStableKey: string;
    provenance: ItemAcquisition;
    sourceName: string;
    sourceWikiPageName: string | null;
    characterStableKey: string | null;
    price: number | null;
    referenceNames: Record<string, string>;
    locationSources: Record<string, { name: string; wikiPageName: string | null }>;
    fishingBonus: ItemAcquisition | null;
    originatingDisposition: ItemDisposition;
    displayDisposition: ItemDisposition;
};

// Vendor item info (for popups)
export type VendorItem = {
    name: string;
    price: number;
    provenance: ItemAcquisition;
};

export type AchievementTriggerMarker = BaseMarker & {
    category: 'achievement-trigger';
    achievementName: string;
};

export type NpcMarker = BaseMarker & {
    category: 'npc';
    characters: SpawnCharacter[];
    isEnabled: boolean;
    spawnDelay: number | null;
    isNightSpawn: boolean;
    movement: MovementData | null;
};

export type DoorMarker = BaseMarker & {
    category: 'door';
    keyItemName: string;
    keyItemWikiPageName: string | null;
};

export type ForgeMarker = BaseMarker & {
    category: 'forge';
};

export type ItemBagMarker = BaseMarker & {
    category: 'item-bag';
    itemName: string;
    itemWikiPageName: string | null;
    respawnTimer: number;
    respawns: boolean;
    provenance: ItemAcquisition;
};

export type MiningNodeMarker = BaseMarker & {
    category: 'mining-node';
    items: MiningNodeItem[];
    respawnTime: number;
};

export type SecretPassageMarker = BaseMarker & {
    category: 'secret-passage';
    passageType: string;
};

export type EnemyMarker = BaseMarker & {
    category: 'enemy';
    characters: SpawnCharacter[];
    spawnDelay: number | null;
    isNightSpawn: boolean;
    isEnabled: boolean;
    encounterTier: EnemyTier;
    movement: MovementData | null;
};

export type TeleportMarker = BaseMarker & {
    category: 'teleport';
    teleportItemName: string;
    teleportItemWikiPageName: string | null;
};

export type TreasureCharacter = {
    stableKey: string;
    name: string;
    wikiPageName: string | null;
};

export type TreasureLocMarker = BaseMarker & {
    category: 'treasure-loc';
    minReadingLevel: number;
    chests: (TreasureCharacter & { digLevelMin: number; digLevelMax: number })[];
    guardians: (TreasureCharacter & { levelMin: number; levelMax: number })[];
    levelMin: number;
    levelMax: number;
};

export type WaterMarker = BaseMarker & {
    category: 'water';
    width: number;
    height: number;
    daytimeItems: MiningNodeItem[];
    nighttimeItems: MiningNodeItem[];
};

export type WishingWellMarker = BaseMarker & {
    category: 'wishing-well';
};

export type ZoneLineMarker = BaseMarker & {
    category: 'zone-line';
    destinationZone: string | null;
    destinationZoneName: string;
    landingPosition: { x: number; y: number; z: number } | null;
    destinationContext: ZoneLineDestinationContext | null;
    levelRangeLow: number | null;
    levelRangeHigh: number | null;
    isEnabled: boolean;
};

export type Marker =
    | AchievementTriggerMarker
    | DoorMarker
    | EnemyMarker
    | ForgeMarker
    | ItemBagMarker
    | MiningNodeMarker
    | NpcMarker
    | SecretPassageMarker
    | TeleportMarker
    | TreasureLocMarker
    | WaterMarker
    | WishingWellMarker
    | ZoneLineMarker;
