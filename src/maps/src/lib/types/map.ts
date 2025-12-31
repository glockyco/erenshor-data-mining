/**
 * Map types for the world map page.
 *
 * This file extends the database layer types from map-markers.ts with
 * world positioning (zone and worldPosition fields).
 */

import type {
    BaseMarker,
    AchievementTriggerMarker as DBAchievementTriggerMarker,
    DoorMarker as DBDoorMarker,
    EnemyMarker as DBEnemyMarker,
    ForgeMarker as DBForgeMarker,
    ItemBagMarker as DBItemBagMarker,
    MiningNodeMarker as DBMiningNodeMarker,
    NpcMarker as DBNpcMarker,
    SecretPassageMarker as DBSecretPassageMarker,
    TeleportMarker as DBTeleportMarker,
    TreasureLocMarker as DBTreasureLocMarker,
    WaterMarker as DBWaterMarker,
    WishingWellMarker as DBWishingWellMarker,
    ZoneLineMarker as DBZoneLineMarker
} from '$lib/map-markers';

// Re-export SpawnCharacter for convenience
export type { SpawnCharacter } from '$lib/map-markers';

// =============================================================================
// World-positioned marker types
// =============================================================================

/**
 * Fields added when transforming database markers to world coordinates
 */
interface WorldPositioning {
    zone: string; // Zone key (e.g., "Soluna", "Silkengrass")
    worldPosition: [number, number]; // World coordinates for rendering
}

/**
 * Utility type to add world positioning to a database marker type
 */
type WithWorldPosition<T extends BaseMarker> = T & WorldPositioning;

// Full marker types with world positioning
export type AchievementTriggerMarker = WithWorldPosition<DBAchievementTriggerMarker>;
export type DoorMarker = WithWorldPosition<DBDoorMarker>;
export type EnemyMarker = WithWorldPosition<DBEnemyMarker>;
export type ForgeMarker = WithWorldPosition<DBForgeMarker>;
export type ItemBagMarker = WithWorldPosition<DBItemBagMarker>;
export type MiningNodeMarker = WithWorldPosition<DBMiningNodeMarker>;
export type NpcMarker = WithWorldPosition<DBNpcMarker>;
export type SecretPassageMarker = WithWorldPosition<DBSecretPassageMarker>;
export type TeleportMarker = WithWorldPosition<DBTeleportMarker>;
export type TreasureLocMarker = WithWorldPosition<DBTreasureLocMarker>;
export type WishingWellMarker = WithWorldPosition<DBWishingWellMarker>;

// Water and ZoneLine have additional world-computed fields
export type WaterMarker = WithWorldPosition<DBWaterMarker> & {
    worldPolygon: [number, number][]; // Clamped polygon corners in world coords
};

export type ZoneLineMarker = WithWorldPosition<DBZoneLineMarker> & {
    destinationWorldPosition: [number, number] | null; // World coords of landing point
};

/**
 * Union of all marker types with world positioning
 */
export type AnyMapMarker =
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

// =============================================================================
// Layer visibility
// =============================================================================

export interface LayerVisibility {
    // Terrain layers
    tiles: boolean;
    worldMap: boolean;
    zoneBounds: boolean;
    zoneLabels: boolean;
    // Enemy layers (by rarity)
    spawnPoints: boolean;
    spawnPointsRare: boolean;
    spawnPointsUnique: boolean;
    // NPC layers
    characters: boolean;
    // Zone connections
    zoneLines: boolean;
    teleports: boolean;
    // Utilities
    forges: boolean;
    wishingWells: boolean;
    // Resources
    miningNodes: boolean;
    water: boolean;
    itemBags: boolean;
    treasureLocs: boolean;
    // Secrets
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
// Zone configuration
// =============================================================================

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
// Map data interfaces
// =============================================================================

export interface FilteredMapData {
    achievementTriggers: AchievementTriggerMarker[];
    npcs: NpcMarker[];
    doors: DoorMarker[];
    forges: ForgeMarker[];
    itemBags: ItemBagMarker[];
    miningNodes: MiningNodeMarker[];
    secretPassages: SecretPassageMarker[];
    enemiesCommon: EnemyMarker[];
    enemiesRare: EnemyMarker[];
    enemiesUnique: EnemyMarker[];
    teleports: TeleportMarker[];
    treasureLocs: TreasureLocMarker[];
    water: WaterMarker[];
    wishingWells: WishingWellMarker[];
    zoneLines: ZoneLineMarker[];
}

export interface MapMarkerData {
    achievementTriggers: AchievementTriggerMarker[];
    npcs: NpcMarker[];
    doors: DoorMarker[];
    enemiesCommon: EnemyMarker[];
    enemiesRare: EnemyMarker[];
    enemiesUnique: EnemyMarker[];
    forges: ForgeMarker[];
    itemBags: ItemBagMarker[];
    miningNodes: MiningNodeMarker[];
    secretPassages: SecretPassageMarker[];
    teleports: TeleportMarker[];
    treasureLocs: TreasureLocMarker[];
    water: WaterMarker[];
    wishingWells: WishingWellMarker[];
    zoneLines: ZoneLineMarker[];
    zones: ZoneWorldPosition[];
}

// =============================================================================
// Live entities (WebSocket)
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
