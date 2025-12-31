export type BaseMarker = {
    coordinateId: number;
    position: { x: number; y: number };
    popup?: string;
};

// Character info for spawn points (enemies that can spawn at a location)
export type SpawnCharacter = {
    name: string;
    spawnChance: number;
    isCommon: boolean;
    isRare: boolean;
    isUnique: boolean;
    isFriendly: boolean;
};

// Item drop info for mining nodes
export type MiningNodeItem = {
    name: string;
    dropChance: number;
};

export type AchievementTriggerMarker = BaseMarker & {
    category: 'achievement-trigger';
    achievementName: string;
};

export type NpcMarker = BaseMarker & {
    category: 'npc';
    name: string;
    isEnabled: boolean;
    spawnDelay: number | null;
    isNightSpawn: boolean;
};

export type DoorMarker = BaseMarker & {
    category: 'door';
    keyItemName: string;
};

export type ForgeMarker = BaseMarker & {
    category: 'forge';
};

export type ItemBagMarker = BaseMarker & {
    category: 'item-bag';
    itemName: string;
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
    isUnique: boolean;
    isRare: boolean;
};

export type TeleportMarker = BaseMarker & {
    category: 'teleport';
    teleportItemName: string;
};

export type TreasureLocMarker = BaseMarker & {
    category: 'treasure-loc';
};

export type WaterMarker = BaseMarker & {
    category: 'water';
    width: number;
    height: number;
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
