/**
 * World map types - adds positioning to database markers.
 *
 * Import marker types directly from '$lib/map-markers' for the base types.
 * Use WorldMarker<T> or the shorthand types for world-positioned markers.
 */

import type {
    Marker,
    AchievementTriggerMarker,
    DoorMarker,
    EnemyMarker,
    ForgeMarker,
    ItemBagMarker,
    MiningNodeMarker,
    NpcMarker,
    SecretPassageMarker,
    TeleportMarker,
    TreasureLocMarker,
    WaterMarker,
    WishingWellMarker,
    ZoneLineMarker
} from '$lib/map-markers';

// Re-export types for popup generation
export type { SpawnCharacter, MovementData } from '$lib/map-markers';

// =============================================================================
// World Positioning
// =============================================================================

/**
 * World positioning fields added when transforming to world coordinates
 */
export interface WorldPositioning {
    zone: string;
    worldPosition: [number, number];
}

/**
 * Generic type: any marker with world positioning added
 */
export type WorldMarker<T extends Marker = Marker> = T & WorldPositioning;

// =============================================================================
// Shorthand Types
// =============================================================================

export type WorldNpc = WorldMarker<NpcMarker> & {
    worldPatrolWaypoints: [number, number][] | null;
};
export type WorldEnemy = WorldMarker<EnemyMarker> & {
    worldPatrolWaypoints: [number, number][] | null;
    levelMin: number;
    levelMax: number;
};
export type WorldForge = WorldMarker<ForgeMarker>;
export type WorldWishingWell = WorldMarker<WishingWellMarker>;
export type WorldTeleport = WorldMarker<TeleportMarker>;
export type WorldDoor = WorldMarker<DoorMarker>;
export type WorldSecretPassage = WorldMarker<SecretPassageMarker>;
export type WorldMiningNode = WorldMarker<MiningNodeMarker>;
export type WorldItemBag = WorldMarker<ItemBagMarker>;
export type WorldTreasureLoc = WorldMarker<TreasureLocMarker>;
export type WorldAchievementTrigger = WorldMarker<AchievementTriggerMarker>;

// Special cases with extra computed fields
export type WorldWater = WorldMarker<WaterMarker> & {
    worldPolygon: [number, number][];
};

export type WorldZoneLine = WorldMarker<ZoneLineMarker> & {
    destinationWorldPosition: [number, number] | null;
    destinationEnemyInfo: ZoneEnemyInfo;
};

/**
 * Union of all world-positioned marker types
 */
export type AnyWorldMarker =
    | WorldNpc
    | WorldEnemy
    | WorldForge
    | WorldWishingWell
    | WorldTeleport
    | WorldDoor
    | WorldSecretPassage
    | WorldMiningNode
    | WorldItemBag
    | WorldTreasureLoc
    | WorldAchievementTrigger
    | WorldWater
    | WorldZoneLine;

// =============================================================================
// Layer Visibility
// =============================================================================

export interface LayerVisibility {
    tiles: boolean;
    worldMap: boolean;
    zoneBounds: boolean;
    zoneLabels: boolean;
    spawnPoints: boolean;
    spawnPointsRare: boolean;
    spawnPointsUnique: boolean;
    characters: boolean;
    zoneLines: boolean;
    teleports: boolean;
    forges: boolean;
    wishingWells: boolean;
    miningNodes: boolean;
    water: boolean;
    itemBags: boolean;
    treasureLocs: boolean;
    doors: boolean;
    secretPassages: boolean;
    achievementTriggers: boolean;
}

export const DEFAULT_LAYER_VISIBILITY: LayerVisibility = {
    tiles: true,
    worldMap: true,
    zoneBounds: false,
    zoneLabels: true,
    spawnPoints: true,
    spawnPointsRare: true,
    spawnPointsUnique: true,
    characters: true,
    zoneLines: true,
    teleports: true,
    forges: true,
    wishingWells: true,
    miningNodes: true,
    water: true,
    itemBags: true,
    treasureLocs: true,
    doors: true,
    secretPassages: true,
    achievementTriggers: true
};

// =============================================================================
// Zone Configuration
// =============================================================================

export interface ZoneEnemyInfo {
    levelRange: { min: number; max: number } | null;
    uniques: { name: string; level: number }[];
    rares: { name: string; level: number }[];
}

export interface LevelRange {
    min: number;
    max: number;
}

export interface ZoneWorldPosition {
    key: string;
    name: string;
    worldX: number;
    worldY: number;
    bounds: {
        minX: number;
        minY: number;
        maxX: number;
        maxY: number;
    };
    polygon: [number, number][];
    centroid: [number, number];
    enemyInfo?: ZoneEnemyInfo;
}

export interface ZoneConfig {
    zoneName: string;
    tileUrl: string;
    baseTilesX: number;
    baseTilesY: number;
    tileSize: number;
    zoom: number;
    minZoom: number;
    maxZoom: number;
    originX: number;
    originY: number;
    northBearing: number;
}

// =============================================================================
// Map Data Interfaces
// =============================================================================

export interface FilteredMapData {
    achievementTriggers: WorldAchievementTrigger[];
    npcs: WorldNpc[];
    doors: WorldDoor[];
    forges: WorldForge[];
    itemBags: WorldItemBag[];
    miningNodes: WorldMiningNode[];
    secretPassages: WorldSecretPassage[];
    enemiesCommon: WorldEnemy[];
    enemiesRare: WorldEnemy[];
    enemiesUnique: WorldEnemy[];
    teleports: WorldTeleport[];
    treasureLocs: WorldTreasureLoc[];
    water: WorldWater[];
    wishingWells: WorldWishingWell[];
    zoneLines: WorldZoneLine[];
}

export interface MapMarkerData {
    achievementTriggers: WorldAchievementTrigger[];
    npcs: WorldNpc[];
    doors: WorldDoor[];
    enemiesCommon: WorldEnemy[];
    enemiesRare: WorldEnemy[];
    enemiesUnique: WorldEnemy[];
    forges: WorldForge[];
    itemBags: WorldItemBag[];
    miningNodes: WorldMiningNode[];
    secretPassages: WorldSecretPassage[];
    teleports: WorldTeleport[];
    treasureLocs: WorldTreasureLoc[];
    water: WorldWater[];
    wishingWells: WorldWishingWell[];
    zoneLines: WorldZoneLine[];
    zones: ZoneWorldPosition[];
}

// =============================================================================
// Live Entities (WebSocket)
// =============================================================================

export interface LiveEntity {
    id: string;
    type: 'player' | 'simplayer' | 'npc';
    name: string;
    zone: string;
    position: [number, number];
    rotation: number;
}

export type ConnectionState =
    | { status: 'disconnected' }
    | { status: 'connecting'; attempt: number }
    | { status: 'connected' }
    | { status: 'reconnecting'; attempt: number; lastError: string };

export interface ZoneListItem {
    key: string;
    name: string;
}
