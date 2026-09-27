import type { EntityData } from './map/live/types';

/** Character tiers in display order, most notable first. */
export const ENCOUNTER_TIER_ORDER = {
    boss: 0,
    elite: 1,
    enemy: 2,
    npc: 3
} as const;

export type EncounterTier = keyof typeof ENCOUNTER_TIER_ORDER;
export type EnemyTier = Exclude<EncounterTier, 'npc'>;

export function compareEncounterTier(a: EncounterTier, b: EncounterTier): number {
    return ENCOUNTER_TIER_ORDER[a] - ENCOUNTER_TIER_ORDER[b];
}

export function mostNotableEnemyTier(characters: readonly { encounterTier: EncounterTier }[]): EnemyTier {
    let best: EnemyTier | null = null;
    for (const { encounterTier } of characters) {
        if (encounterTier === 'npc') continue;
        if (!best || compareEncounterTier(encounterTier, best) < 0) best = encounterTier;
    }
    if (!best) throw new Error('Enemy marker has no hostile characters');
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
    return tiers.get(entity.name) ??
        (entity.rarity === 'boss' ? 'boss' : entity.rarity === 'rare' ? 'elite' : 'enemy');
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
    level: number;
    encounterTier: EnemyTier;
};

// Character info for spawn points (characters that can spawn at a location)
export type SpawnCharacter = {
    name: string;
    wikiPageName: string | null;
    stableKey: string;
    level: number;
    spawnChance: number | null;
    sourceScript: string | null;
    eventPosition: { x: number; y: number; z: number } | null;
    encounterTier: EncounterTier;
    isFriendly: boolean;
    isInvulnerable: boolean;
    isVendor: boolean;
    hasDialog: boolean;
};

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
};

// Character loot drop info (for popups)
export type CharacterDrop = {
    itemName: string;
    dropProbability: number;
};

// Item → acquisition-source rows (preloaded for the map item search)
export type ItemSourceItemMeta = {
    itemStableKey: string;
    displayName: string;
    wikiPageName: string | null;
    iconName: string | null;
};

export type ItemDropSource = ItemSourceItemMeta & {
    kind: 'drop';
    characterStableKey: string;
    npcName: string;
    encounterTier: EncounterTier;
    dropProbability: number; // 0–100
};

export type ItemVendorSource = ItemSourceItemMeta & {
    kind: 'vendor';
    characterStableKey: string;
    npcName: string;
    price: number; // items.item_value, same figure SpawnPointPopupContent shows
};

export type ItemMiningSource = ItemSourceItemMeta & {
    kind: 'mining';
    nodeStableKey: string;
    dropChance: number; // 0–100
};

export type ItemFishingSource = ItemSourceItemMeta & {
    kind: 'fishing';
    waterStableKey: string;
    period: 'day' | 'night';
    dropChance: number; // 0–100
};

export type ItemBagSource = ItemSourceItemMeta & {
    kind: 'bag';
    bagStableKey: string;
};

export type ItemSourceRow =
    | ItemDropSource
    | ItemVendorSource
    | ItemMiningSource
    | ItemFishingSource
    | ItemBagSource;

// Vendor item info (for popups)
export type VendorItem = {
    name: string;
    price: number;
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

export type TreasureLocMarker = BaseMarker & {
    category: 'treasure-loc';
};

export type WaterMarker = BaseMarker & {
    category: 'water';
    width: number;
    height: number;
    daytimeItems: { name: string; wikiPageName: string | null; dropChance: number }[];
    nighttimeItems: { name: string; wikiPageName: string | null; dropChance: number }[];
};

export type WishingWellMarker = BaseMarker & {
    category: 'wishing-well';
};

export type ZoneLineMarker = BaseMarker & {
    category: 'zone-line';
    destinationZone: string;
    destinationZoneName: string;
    landingPosition: { x: number; y: number; z: number };
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
