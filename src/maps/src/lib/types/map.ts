/**
 * Marker category types
 * Note: 'enemy' and 'npc' are the actual categories from the database
 */
export type MarkerCategory =
    | 'achievement-trigger'
    | 'door'
    | 'enemy'
    | 'forge'
    | 'item-bag'
    | 'mining-node'
    | 'npc'
    | 'secret-passage'
    | 'teleport'
    | 'treasure-loc'
    | 'water'
    | 'wishing-well'
    | 'zone-line';

/**
 * Base interface for all map markers
 */
export interface MapMarker {
    coordinateId: number;
    category: MarkerCategory;
    position: [number, number]; // [x, y] in local zone coordinates
    zone: string; // Zone key (e.g., "Soluna", "Silkengrass")
    popup?: string; // HTML popup content
}

/**
 * Achievement trigger marker
 */
export interface AchievementTriggerMarker extends MapMarker {
    category: 'achievement-trigger';
    achievementName: string;
}

/**
 * Friendly NPC marker
 */
export interface NpcMarker extends MapMarker {
    category: 'npc';
    name: string;
    isEnabled: boolean;
    spawnDelay: number | null;
    isNightSpawn: boolean;
}

/**
 * Locked door marker
 */
export interface DoorMarker extends MapMarker {
    category: 'door';
    keyItemName: string;
}

/**
 * Crafting forge marker
 */
export interface ForgeMarker extends MapMarker {
    category: 'forge';
}

/**
 * Item bag/container marker
 */
export interface ItemBagMarker extends MapMarker {
    category: 'item-bag';
    itemName: string;
    respawnTimer: number;
}

/**
 * Mining node marker
 */
export interface MiningNodeMarker extends MapMarker {
    category: 'mining-node';
    items: { name: string; dropChance: number }[];
    respawnTime: number;
}

/**
 * Secret passage marker (hidden doors, illusory walls)
 */
export interface SecretPassageMarker extends MapMarker {
    category: 'secret-passage';
    passageType: 'HiddenDoor' | 'IllusoryWall' | 'InvisibleFloor';
}

/**
 * Character info for enemy spawn points
 */
export interface SpawnCharacter {
    name: string;
    spawnChance: number;
    isCommon: boolean;
    isRare: boolean;
    isUnique: boolean;
    isFriendly: boolean;
}

/**
 * Enemy spawn point marker
 */
export interface EnemyMarker extends MapMarker {
    category: 'enemy';
    characters: SpawnCharacter[];
    spawnDelay: number | null;
    isEnabled: boolean;
    isNightSpawn: boolean;
    isUnique: boolean;
    isRare: boolean;
}

/**
 * Teleport destination marker
 */
export interface TeleportMarker extends MapMarker {
    category: 'teleport';
    teleportItemName: string;
}

/**
 * Treasure hunting location marker
 */
export interface TreasureLocMarker extends MapMarker {
    category: 'treasure-loc';
}

/**
 * Fishable water marker
 */
export interface WaterMarker extends MapMarker {
    category: 'water';
    daytimeItems: { name: string; dropChance: number }[];
    nighttimeItems: { name: string; dropChance: number }[];
}

/**
 * Wishing well (respawn point) marker
 */
export interface WishingWellMarker extends MapMarker {
    category: 'wishing-well';
}

/**
 * Zone connection portal marker
 */
export interface ZoneLineMarker extends MapMarker {
    category: 'zone-line';
    destinationZone: string;
    destinationZoneName: string;
    landingPosition: { x: number; y: number; z: number };
    levelRangeLow: number | null;
    levelRangeHigh: number | null;
    isEnabled: boolean;
}

/**
 * Union of all marker types
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

/**
 * Layer visibility toggle state
 */
export interface LayerVisibility {
    // Terrain layers
    tiles: boolean; // Per-zone tile imagery
    worldMap: boolean; // Full world backdrop image
    zoneBounds: boolean; // Zone outline polygons
    zoneLabels: boolean; // Zone name text labels
    // Enemy layers (by rarity)
    spawnPoints: boolean; // Common enemies
    spawnPointsRare: boolean; // Rare enemies
    spawnPointsUnique: boolean; // Unique/boss enemies
    // NPC layers
    characters: boolean; // All NPCs
    // Zone connections
    zoneLines: boolean; // Zone portals
    teleports: boolean; // Teleport destinations
    // Utilities
    forges: boolean;
    wishingWells: boolean;
    // Resources
    miningNodes: boolean;
    water: boolean; // Fishing spots
    itemBags: boolean;
    treasureLocs: boolean;
    // Secrets
    doors: boolean;
    secretPassages: boolean;
    achievementTriggers: boolean;
}

/**
 * Default layer visibility (all ON by default)
 */
export const DEFAULT_LAYER_VISIBILITY: LayerVisibility = {
    // Terrain
    tiles: true,
    worldMap: true,
    zoneBounds: false,
    zoneLabels: true,
    // Enemies
    spawnPoints: true,
    spawnPointsRare: true,
    spawnPointsUnique: true,
    // NPCs
    characters: true,
    // Zone connections
    zoneLines: true,
    teleports: true,
    // Utilities
    forges: true,
    wishingWells: true,
    // Resources
    miningNodes: true,
    water: true,
    itemBags: true,
    treasureLocs: true,
    // Secrets
    doors: true,
    secretPassages: true,
    achievementTriggers: true
};

/**
 * Zone world position for unified map rendering
 */
export interface ZoneWorldPosition {
    /** Zone key (e.g., "Soluna") */
    key: string;
    /** Display name */
    name: string;
    /** World X offset (added to local coordinates) */
    worldX: number;
    /** World Y offset (added to local coordinates) */
    worldY: number;
    /** Zone bounds in world coordinates (axis-aligned bounding box) */
    bounds: {
        minX: number;
        minY: number;
        maxX: number;
        maxY: number;
    };
    /** Actual rotated polygon corners in world coordinates */
    polygon: [number, number][];
    /** Polygon centroid for label positioning */
    centroid: [number, number];
}

/**
 * Zone configuration from existing maps.ts
 */
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
    northBearing: number; // Degrees, for compass alignment
}

/**
 * Pre-filtered marker data (computed once, not on every render)
 */
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

/**
 * All marker data for the map (raw, before filtering)
 */
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

/**
 * URL state for shareable links.
 * @see url-state.ts for parsing and serialization functions.
 */
export interface MapUrlState {
    /** Center X coordinate (1 decimal) */
    x: number;
    /** Center Y coordinate (1 decimal) */
    y: number;
    /** Zoom level (2 decimals) */
    z: number;
    /** Selected marker coordinateId */
    marker: string | null;
    /** Selected marker type (enemy, npc, zone-line, etc.) */
    mtype: string | null;
    /** Focused zone key (filters to single zone) */
    zone: string | null;
    /** Layer visibility (comma-separated, null = defaults) */
    layers: string | null;
    /** Debug mode */
    debug: boolean;
}

/**
 * Live entity from WebSocket
 */
export interface LiveEntity {
    id: string;
    type: 'player' | 'simplayer' | 'npc';
    name: string;
    zone: string;
    position: [number, number];
    rotation: number;
}

/**
 * WebSocket connection state
 */
export type ConnectionState =
    | { status: 'disconnected' }
    | { status: 'connecting'; attempt: number }
    | { status: 'connected' }
    | { status: 'reconnecting'; attempt: number; lastError: string };

/**
 * Zone list item for dropdown selection
 */
export interface ZoneListItem {
    key: string;
    name: string;
}
