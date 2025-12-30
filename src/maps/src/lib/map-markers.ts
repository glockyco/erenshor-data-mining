export type BaseMarker = {
    coordinateId: number;
    position: { x: number; y: number };
    popup?: string;
};

export type AchievementTriggerMarker = BaseMarker & {
    category: 'achievement-trigger';
};

export type NpcMarker = BaseMarker & {
    category: 'npc';
    isEnabled: boolean;
};

export type DoorMarker = BaseMarker & {
    category: 'door';
};

export type ForgeMarker = BaseMarker & {
    category: 'forge';
};

export type ItemBagMarker = BaseMarker & {
    category: 'item-bag';
};

export type MiningNodeMarker = BaseMarker & {
    category: 'mining-node';
};

export type SecretPassageMarker = BaseMarker & {
    category: 'secret-passage';
};

export type EnemyMarker = BaseMarker & {
    category: 'enemy';
    isEnabled: boolean;
    isUnique: boolean;
    isRare: boolean;
};

export type TeleportMarker = BaseMarker & {
    category: 'teleport';
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
