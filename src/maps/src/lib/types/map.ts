/**
 * Marker category types
 */
export type MarkerCategory =
    | 'achievement-trigger'
    | 'character'
    | 'door'
    | 'forge'
    | 'item-bag'
    | 'mining-node'
    | 'secret-passage'
    | 'spawn-point'
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
export interface CharacterMarker extends MapMarker {
    category: 'character';
    name: string;
    isEnabled: boolean;
    isUnique: boolean;
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
 * Enemy spawn point marker
 */
export interface SpawnPointMarker extends MapMarker {
    category: 'spawn-point';
    characters: {
        name: string;
        spawnChance: number;
        isCommon: boolean;
        isRare: boolean;
        isUnique: boolean;
    }[];
    spawnDelay: number | null;
    isEnabled: boolean;
    isNightSpawn: boolean;
    hasUnique: boolean;
    hasRare: boolean;
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
    | CharacterMarker
    | DoorMarker
    | ForgeMarker
    | ItemBagMarker
    | MiningNodeMarker
    | SecretPassageMarker
    | SpawnPointMarker
    | TeleportMarker
    | TreasureLocMarker
    | WaterMarker
    | WishingWellMarker
    | ZoneLineMarker;

/**
 * Layer visibility toggle state
 */
export interface LayerVisibility {
    achievementTriggers: boolean;
    characters: boolean;
    doors: boolean;
    forges: boolean;
    itemBags: boolean;
    miningNodes: boolean;
    secretPassages: boolean;
    spawnPoints: boolean;
    spawnPointsUnique: boolean; // Sub-filter for unique spawns
    spawnPointsRare: boolean; // Sub-filter for rare spawns
    teleports: boolean;
    treasureLocs: boolean;
    water: boolean;
    wishingWells: boolean;
    zoneLines: boolean;
    // Zone visualization
    zoneBounds: boolean;
    zoneLabels: boolean;
    tiles: boolean;
}

/**
 * Default layer visibility (all enabled except tiles which depend on zoom)
 */
export const DEFAULT_LAYER_VISIBILITY: LayerVisibility = {
    achievementTriggers: true,
    characters: true,
    doors: true,
    forges: true,
    itemBags: true,
    miningNodes: true,
    secretPassages: true,
    spawnPoints: true,
    spawnPointsUnique: true,
    spawnPointsRare: true,
    teleports: true,
    treasureLocs: true,
    water: true,
    wishingWells: true,
    zoneLines: true,
    zoneBounds: true,
    zoneLabels: true,
    tiles: true
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
    characters: CharacterMarker[];
    doors: DoorMarker[];
    forges: ForgeMarker[];
    itemBags: ItemBagMarker[];
    miningNodes: MiningNodeMarker[];
    secretPassages: SecretPassageMarker[];
    spawnPointsRegular: SpawnPointMarker[];
    spawnPointsUnique: SpawnPointMarker[];
    spawnPointsRare: SpawnPointMarker[];
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
    characters: CharacterMarker[];
    doors: DoorMarker[];
    forges: ForgeMarker[];
    itemBags: ItemBagMarker[];
    miningNodes: MiningNodeMarker[];
    secretPassages: SecretPassageMarker[];
    spawnPoints: SpawnPointMarker[];
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
