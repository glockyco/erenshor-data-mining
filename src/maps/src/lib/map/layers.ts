/**
 * Pure deck.gl layer construction for the world map.
 *
 * This module owns everything that turns a snapshot of route state + data into
 * an ordered array of deck.gl layers: world/backdrop bounds math, the local
 * icon-layer helper, and the full `createLayers` builder. It is intentionally
 * free of Svelte runes, lifecycle, and reactivity — the route (`+page.svelte`)
 * keeps all of that and passes explicit state, data, deck constructors, and the
 * icon atlas in through {@link CreateLayersParams}.
 *
 * Keeping this logic pure makes layer ordering, visibility filtering, update
 * triggers, and positioning independently testable without a browser or a live
 * deck.gl instance.
 */

import { ICON_SIZE, BACKGROUND_COLOR, LAYER_COLORS, HIGHLIGHT_COLORS, MOVEMENT_COLORS } from './config';
import { createZoneTileset2D, getTileWorldCorners, type ZoneTileIndex } from './zone-tileset';
import {
    getZoneLineIconType,
    getEnemyIconType,
    getNpcIconType,
    type IconAtlasResult,
    type MarkerIconType
} from './icons';
import { transformEntityToWorld, transformRotationToMap } from './coordinate-transform';
import { adjustMarkerPosition } from './debug/position-service';
import type { PositionOverrides } from './debug/persistence';
import type { BackdropSettings } from './debug/backdrop-persistence';
import { getSelectionPosition, type Selection } from '../types/selection';
import type { EntityData, ConnectionState } from './live/types';
import type {
    LayerVisibility,
    MapMarkerData,
    WorldEnemy,
    WorldNpc,
    ZoneWorldPosition,
    ZoneConfig
} from '../types/world-map';

// =============================================================================
// Backdrop constants
// =============================================================================

/** Low-res world overview image drawn behind the zone tiles. */
export const BACKDROP_IMAGE = '/erenshor-world-map.webp';
/** Intrinsic pixel width of {@link BACKDROP_IMAGE}. */
export const BACKDROP_WIDTH = 1604;
/** Intrinsic pixel height of {@link BACKDROP_IMAGE}. */
export const BACKDROP_HEIGHT = 2048;

// =============================================================================
// Deck constructor interface (narrow view of the dynamically imported modules)
// =============================================================================

/**
 * Minimal constructor shape for a deck.gl layer/extension. The concrete deck.gl
 * types are only available after the dynamic `import('@deck.gl/*')` calls, so we
 * describe just what layer construction needs: `new Klass(props)` returning an
 * opaque instance.
 */
export type DeckLayerConstructor = new (props: Record<string, unknown>) => unknown;

/**
 * The subset of dynamically imported deck.gl exports required to build layers.
 * `Tileset2D` is passed straight through to {@link createZoneTileset2D}, which
 * subclasses it, so it is left opaque here.
 */
export interface DeckLayerModules {
    IconLayer: DeckLayerConstructor;
    PolygonLayer: DeckLayerConstructor;
    TextLayer: DeckLayerConstructor;
    BitmapLayer: DeckLayerConstructor;
    LineLayer: DeckLayerConstructor;
    ScatterplotLayer: DeckLayerConstructor;
    TileLayer: DeckLayerConstructor;
    Tileset2D: unknown;
    DataFilterExtension: DeckLayerConstructor;
}

// =============================================================================
// Input snapshots
// =============================================================================

/**
 * The route data fields read during layer construction. A structural subset of
 * the server world-data payload — marker arrays, zone positions, and per-zone
 * tile configs.
 */
export interface LayerData {
    markers: Pick<
        MapMarkerData,
        | 'achievementTriggers'
        | 'doors'
        | 'enemiesCommon'
        | 'enemiesRare'
        | 'enemiesUnique'
        | 'forges'
        | 'itemBags'
        | 'miningNodes'
        | 'npcs'
        | 'secretPassages'
        | 'teleports'
        | 'treasureLocs'
        | 'wishingWells'
        | 'zoneLines'
    >;
    zones: ZoneWorldPosition[];
    zoneConfigs: Record<string, ZoneConfig>;
}

/** Immutable snapshot of the live-entity store needed for live layers. */
export interface LiveStateSnapshot {
    connectionState: ConnectionState;
    zone: string | null;
    entities: EntityData[];
}

/** A resolved search-highlight position keyed by its originating spawn point. */
export interface SearchHighlightPosition {
    position: [number, number];
    stableKey: string;
}

/** All inputs required to build the deck.gl layer stack. */
export interface CreateLayersParams {
    /** Icon atlas (canvas + mapping) for icon layers. */
    atlas: IconAtlasResult;
    /** Dynamically imported deck.gl layer constructors. */
    modules: DeckLayerModules;
    /** Route data (markers, zones, zone configs). */
    data: LayerData;
    /** Zones with debug position overrides applied (used for bounds/selection). */
    effectiveZones: ZoneWorldPosition[];
    /** Debug zone position overrides. */
    overrides: PositionOverrides;
    /** Zone currently being dragged in debug mode (or null). */
    draggingZone: string | null;
    /** Backdrop image placement/visibility settings. */
    backdrop: BackdropSettings;
    /** Per-layer visibility toggles. */
    layerVisibility: LayerVisibility;
    /** Active enemy level filter `[min, max]`. */
    levelFilter: [number, number];
    /** Current selection (marker/live/zone/search) or null. */
    selection: Selection;
    /** Resolved positions for the current search highlight. */
    searchHighlightPositions: SearchHighlightPosition[];
    /** Spawn keys hovered in a search popup (brighter ring), or null. */
    hoveredSpawnKeys: Set<string> | null;
    /** Snapshot of live-entity state. */
    live: LiveStateSnapshot;
}

// =============================================================================
// Bounds math
// =============================================================================

/**
 * Compute backdrop image bounds for a deck.gl BitmapLayer.
 * BitmapLayer bounds are `[left, bottom, right, top]`. The Y axis increases
 * upward, so the Y values are swapped to flip the image correctly.
 */
export function computeBackdropBounds(
    settings: BackdropSettings
): [number, number, number, number] {
    const width = BACKDROP_WIDTH * settings.scale;
    const height = BACKDROP_HEIGHT * settings.scale;
    return [
        settings.x - width / 2,
        settings.y + height / 2,
        settings.x + width / 2,
        settings.y - height / 2
    ];
}

/**
 * Compute the padded world bounds spanning every zone (and, when enabled, the
 * backdrop image). Used to size the background polygon behind all content.
 */
export function computeWorldBounds(
    zones: ZoneWorldPosition[],
    backdrop: BackdropSettings
): { minX: number; minY: number; maxX: number; maxY: number } {
    let minX = Infinity,
        minY = Infinity,
        maxX = -Infinity,
        maxY = -Infinity;
    for (const zone of zones) {
        minX = Math.min(minX, zone.bounds.minX);
        minY = Math.min(minY, zone.bounds.minY);
        maxX = Math.max(maxX, zone.bounds.maxX);
        maxY = Math.max(maxY, zone.bounds.maxY);
    }
    // Include backdrop bounds if enabled
    if (backdrop.enabled) {
        const [bLeft, bBottom, bRight, bTop] = computeBackdropBounds(backdrop);
        minX = Math.min(minX, bLeft);
        minY = Math.min(minY, bTop); // bTop is smaller Y value
        maxX = Math.max(maxX, bRight);
        maxY = Math.max(maxY, bBottom); // bBottom is larger Y value
    }
    const padding = 500;
    minX -= padding;
    minY -= padding;
    maxX += padding;
    maxY += padding;
    return { minX, minY, maxX, maxY };
}

// =============================================================================
// Layer construction
// =============================================================================

/**
 * Build the ordered deck.gl layer stack for the world map from a snapshot of
 * route state and data. Pure: it constructs layers via the provided
 * constructors and returns them; it never reads globals or mutates inputs.
 *
 * Layer order and null/visibility filtering are preserved exactly: the returned
 * array is flattened and stripped of falsy entries so the paint order matches
 * the declaration order below.
 */
export function createLayers(params: CreateLayersParams): unknown[] {
    const {
        atlas,
        modules,
        data,
        effectiveZones,
        overrides,
        draggingZone,
        backdrop,
        layerVisibility,
        levelFilter,
        selection,
        searchHighlightPositions,
        hoveredSpawnKeys,
        live
    } = params;

    const {
        IconLayer,
        PolygonLayer,
        TextLayer,
        BitmapLayer,
        TileLayer,
        Tileset2D,
        LineLayer,
        ScatterplotLayer,
        DataFilterExtension
    } = modules;

    // Use effective zones (with overrides applied)
    const zones = effectiveZones;

    // Position adjustment helper
    const getMarkerPosition = (marker: { worldPosition: [number, number]; zone: string }) => {
        return adjustMarkerPosition(marker.worldPosition, marker.zone, data.zones, overrides);
    };

    // Helper for creating icon layers
    type MarkerWithState = {
        worldPosition: [number, number];
        zone: string;
        isEnabled?: boolean;
        isUnique?: boolean;
        isRare?: boolean;
    };
    const createIconLayer = (
        id: string,
        markerData: MarkerWithState[],
        iconTypeOrFn: string | ((d: MarkerWithState) => string)
    ) => {
        const getIconFn = typeof iconTypeOrFn === 'function' ? iconTypeOrFn : () => iconTypeOrFn;
        return new IconLayer({
            id,
            data: markerData,
            iconAtlas: atlas.atlas,
            iconMapping: atlas.mapping,
            getPosition: (d: MarkerWithState) => getMarkerPosition(d),
            getIcon: getIconFn,
            getSize: ICON_SIZE.base,
            sizeUnits: 'pixels',
            sizeMinPixels: ICON_SIZE.min,
            sizeMaxPixels: ICON_SIZE.max,
            pickable: true,
            updateTriggers: {
                getPosition: [overrides]
            }
        });
    };

    // === WORLD BOUNDS ===
    const { minX, minY, maxX, maxY } = computeWorldBounds(zones, backdrop);

    // === LAYER DEFINITIONS ===

    // Background layer
    const backgroundLayer = new PolygonLayer({
        id: 'background',
        data: [
            {
                polygon: [
                    [minX, minY],
                    [maxX, minY],
                    [maxX, maxY],
                    [minX, maxY]
                ]
            }
        ],
        getPolygon: (d: { polygon: [number, number][] }) => d.polygon,
        getFillColor: BACKGROUND_COLOR,
        pickable: false
    });

    // World map backdrop layer (low-res overview image)
    const backdropLayer = layerVisibility.worldMap
        ? new BitmapLayer({
              id: 'world-map',
              image: BACKDROP_IMAGE,
              bounds: computeBackdropBounds(backdrop),
              opacity: 0.5,
              pickable: false
          })
        : null;

    // Tile layers for each zone
    const tileLayers = zones.map((zone) => {
        const config = data.zoneConfigs[zone.key];
        if (!config) throw new Error(`Missing zone config for: ${zone.key}`);
        const ZoneTilesetClass = createZoneTileset2D(config, zone, Tileset2D);
        return new TileLayer({
            id: `tiles-${zone.key}`,
            TilesetClass: ZoneTilesetClass,
            data: config.tileUrl,
            minZoom: config.minZoom,
            maxZoom: config.maxZoom,
            tileSize: config.tileSize,
            renderSubLayers: (
                props: {
                    id: string;
                    data: ImageBitmap | null;
                    tile: { index: ZoneTileIndex };
                } & Record<string, unknown>
            ) => {
                if (!props.data) return null;
                const worldCorners = getTileWorldCorners(props.tile.index, config, zone);
                return new BitmapLayer({
                    ...props,
                    data: undefined,
                    image: props.data,
                    bounds: worldCorners,
                    pickable: false
                });
            }
        });
    });

    // Zone boundaries (with drag highlight)
    const zoneBoundsLayer = new PolygonLayer({
        id: 'zone-bounds',
        data: zones,
        getPolygon: (d: { polygon: [number, number][] }) => d.polygon,
        getFillColor: (d: { key: string }) =>
            draggingZone === d.key
                ? [250, 204, 21, 60] // Yellow highlight when dragging
                : [100, 116, 139, 30],
        getLineColor: (d: { key: string }) =>
            draggingZone === d.key ? [250, 204, 21, 255] : [100, 116, 139, 150],
        getLineWidth: (d: { key: string }) => (draggingZone === d.key ? 3 : 2),
        lineWidthUnits: 'pixels',
        pickable: true,
        updateTriggers: {
            getFillColor: [draggingZone],
            getLineColor: [draggingZone],
            getLineWidth: [draggingZone]
        }
    });

    // Zone labels
    const zoneLabelsLayer = new TextLayer({
        id: 'zone-labels',
        data: zones,
        getPosition: (d: { bounds: { minX: number; maxX: number; maxY: number } }) => [
            (d.bounds.minX + d.bounds.maxX) / 2,
            d.bounds.maxY + 20
        ],
        getText: (d: { name: string }) => d.name,
        getSize: 24,
        sizeUnits: 'common',
        getColor: [255, 255, 255, 220],
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'top',
        fontFamily: 'system-ui, sans-serif',
        fontWeight: 'bold',
        pickable: false
    });

    // Zone line connections and destinations
    const zoneLinesWithDest = data.markers.zoneLines.filter(
        (d: { destinationWorldPosition: [number, number] | null }) =>
            d.destinationWorldPosition !== null
    );
    const zoneLineConnectionsLayer = new LineLayer({
        id: 'zone-line-connections',
        data: zoneLinesWithDest,
        getSourcePosition: (d: { worldPosition: [number, number]; zone: string }) => {
            const pos = getMarkerPosition(d);
            return [pos[0], pos[1], 0];
        },
        getTargetPosition: (d: {
            destinationWorldPosition: [number, number];
            destinationZone: string;
        }) => {
            const pos = adjustMarkerPosition(
                d.destinationWorldPosition,
                d.destinationZone,
                data.zones,
                overrides
            );
            return [pos[0], pos[1], 0];
        },
        getColor: (d: { isEnabled: boolean }) =>
            d.isEnabled ? [...LAYER_COLORS['zone-line'], 180] : [...LAYER_COLORS['disabled'], 120],
        getWidth: 3,
        widthUnits: 'pixels',
        pickable: false,
        updateTriggers: {
            getSourcePosition: [overrides],
            getTargetPosition: [overrides]
        }
    });
    const zoneLineDestinationsLayer = new ScatterplotLayer({
        id: 'zone-line-destinations',
        data: zoneLinesWithDest,
        getPosition: (d: {
            destinationWorldPosition: [number, number];
            destinationZone: string;
        }) =>
            adjustMarkerPosition(
                d.destinationWorldPosition,
                d.destinationZone,
                data.zones,
                overrides
            ),
        getRadius: 4,
        getFillColor: (d: { isEnabled: boolean }) =>
            d.isEnabled ? [...LAYER_COLORS['zone-line'], 200] : [...LAYER_COLORS['disabled'], 150],
        radiusUnits: 'pixels',
        pickable: false,
        updateTriggers: {
            getPosition: [overrides]
        }
    });

    // Zone line icons
    const zoneLineIconsLayer = new IconLayer({
        id: 'zone-lines',
        data: data.markers.zoneLines,
        iconAtlas: atlas.atlas,
        iconMapping: atlas.mapping,
        getPosition: (d: { worldPosition: [number, number]; zone: string }) =>
            getMarkerPosition(d),
        getIcon: (d: { isEnabled?: boolean }) => getZoneLineIconType(d),
        getSize: ICON_SIZE.base,
        sizeUnits: 'pixels',
        sizeMinPixels: ICON_SIZE.min,
        sizeMaxPixels: ICON_SIZE.max,
        pickable: true,
        updateTriggers: {
            getPosition: [overrides]
        }
    });

    // Enemy layers (by rarity, with level filtering via DataFilterExtension)
    // Filter logic: show spawn if levelMin <= filterMax AND levelMax >= filterMin (overlap)
    const levelFilterExt = new DataFilterExtension({ filterSize: 2 });

    const enemiesCommonLayer = new IconLayer({
        id: 'enemies-common',
        data: data.markers.enemiesCommon,
        iconAtlas: atlas.atlas,
        iconMapping: atlas.mapping,
        getPosition: (d: WorldEnemy) => getMarkerPosition(d),
        getIcon: (d: WorldEnemy) => getEnemyIconType(d),
        getSize: ICON_SIZE.base,
        sizeUnits: 'pixels',
        sizeMinPixels: ICON_SIZE.min,
        sizeMaxPixels: ICON_SIZE.max,
        pickable: true,
        extensions: [levelFilterExt],
        getFilterValue: (d: WorldEnemy) => [d.levelMin, d.levelMax],
        filterRange: [
            [-Infinity, levelFilter[1]], // levelMin <= filterMax
            [levelFilter[0], Infinity] // levelMax >= filterMin
        ],
        updateTriggers: {
            getPosition: [overrides],
            filterRange: levelFilter
        }
    });
    const enemiesRareLayer = new IconLayer({
        id: 'enemies-rare',
        data: data.markers.enemiesRare,
        iconAtlas: atlas.atlas,
        iconMapping: atlas.mapping,
        getPosition: (d: WorldEnemy) => getMarkerPosition(d),
        getIcon: (d: WorldEnemy) => getEnemyIconType(d),
        getSize: ICON_SIZE.base,
        sizeUnits: 'pixels',
        sizeMinPixels: ICON_SIZE.min,
        sizeMaxPixels: ICON_SIZE.max,
        pickable: true,
        extensions: [levelFilterExt],
        getFilterValue: (d: WorldEnemy) => [d.levelMin, d.levelMax],
        filterRange: [
            [-Infinity, levelFilter[1]],
            [levelFilter[0], Infinity]
        ],
        updateTriggers: {
            getPosition: [overrides],
            filterRange: levelFilter
        }
    });
    const enemiesUniqueLayer = new IconLayer({
        id: 'enemies-unique',
        data: data.markers.enemiesUnique,
        iconAtlas: atlas.atlas,
        iconMapping: atlas.mapping,
        getPosition: (d: WorldEnemy) => getMarkerPosition(d),
        getIcon: (d: WorldEnemy) => getEnemyIconType(d),
        getSize: ICON_SIZE.base,
        sizeUnits: 'pixels',
        sizeMinPixels: ICON_SIZE.min,
        sizeMaxPixels: ICON_SIZE.max,
        pickable: true,
        extensions: [levelFilterExt],
        getFilterValue: (d: WorldEnemy) => [d.levelMin, d.levelMax],
        filterRange: [
            [-Infinity, levelFilter[1]],
            [levelFilter[0], Infinity]
        ],
        updateTriggers: {
            getPosition: [overrides],
            filterRange: levelFilter
        }
    });

    // Helper functions for live entity rendering
    function getLiveEntityIcon(entity: EntityData): MarkerIconType {
        switch (entity.entityType) {
            case 'player':
                return 'player-live';
            case 'simplayer':
                return 'simplayer-live';
            case 'pet':
                return 'pet-live';
            case 'npc_friendly':
                return 'npc-friendly-live';
            case 'npc_enemy':
                if (entity.rarity === 'boss') return 'enemy-boss-live';
                if (entity.rarity === 'rare') return 'enemy-rare-live';
                return 'enemy-common-live';
            default:
                return 'player-live'; // fallback
        }
    }

    function getLiveEntitySize(entity: EntityData): number {
        switch (entity.entityType) {
            case 'player':
                return ICON_SIZE.base * 1.5; // Largest - most prominent
            case 'simplayer':
                return ICON_SIZE.base * 1.25; // Medium
            case 'pet':
                return ICON_SIZE.base * 1.0; // Normal
            case 'npc_friendly':
                return ICON_SIZE.base * 1.0; // Normal
            case 'npc_enemy':
                if (entity.rarity === 'boss') return ICON_SIZE.base * 1.5; // Boss size
                if (entity.rarity === 'rare') return ICON_SIZE.base * 1.25; // Rare size
                return ICON_SIZE.base * 1.0; // Common size
            default:
                return ICON_SIZE.base;
        }
    }

    /**
     * Create a live entity layer for a specific entity type.
     * Returns null if not connected, no zone, or no entities match the filter.
     */
    function createLiveEntityLayer(id: string, filterFn: (e: EntityData) => boolean) {
        if (
            live.connectionState !== 'connected' ||
            !live.zone ||
            !data.zoneConfigs[live.zone]
        ) {
            return null;
        }

        const filteredEntities = live.entities.filter(filterFn);

        if (filteredEntities.length === 0) return null;

        return new IconLayer({
            id,
            data: filteredEntities,
            iconAtlas: atlas.atlas,
            iconMapping: atlas.mapping,
            getPosition: (d: EntityData) =>
                transformEntityToWorld(
                    { ...d, zone: live.zone! },
                    data.zones,
                    data.zoneConfigs,
                    overrides
                )!,
            getIcon: (d: EntityData) => getLiveEntityIcon(d),
            getSize: (d: EntityData) => getLiveEntitySize(d),
            getAngle: (d: EntityData) => {
                if (!live.zone) return 0;
                return transformRotationToMap(d.rotation, live.zone, data.zoneConfigs) ?? 0;
            },
            sizeUnits: 'pixels',
            sizeMinPixels: ICON_SIZE.min,
            sizeMaxPixels: ICON_SIZE.max * 1.5,
            pickable: true,
            updateTriggers: {
                getPosition: [live.entities, live.zone, overrides],
                getAngle: [live.entities, live.zone],
                getIcon: [live.entities],
                getSize: [live.entities]
            }
        });
    }

    // === LIVE ENTITIES (priority-ordered, bottom to top) ===
    // Split by entity type to ensure important entities render on top.
    // Player is always most visible, followed by threats (boss > rare > common),
    // then allies (simplayers), companions (pets), and background NPCs.

    const liveNpcFriendlyLayer = createLiveEntityLayer(
        'live-npc-friendly',
        (e) => e.entityType === 'npc_friendly'
    );

    const livePetsLayer = createLiveEntityLayer('live-pets', (e) => e.entityType === 'pet');

    const liveSimPlayersLayer = createLiveEntityLayer(
        'live-simplayers',
        (e) => e.entityType === 'simplayer'
    );

    const liveEnemiesCommonLayer = createLiveEntityLayer(
        'live-enemies-common',
        (e) => e.entityType === 'npc_enemy' && (!e.rarity || e.rarity === 'common')
    );

    const liveEnemiesRareLayer = createLiveEntityLayer(
        'live-enemies-rare',
        (e) => e.entityType === 'npc_enemy' && e.rarity === 'rare'
    );

    const liveEnemiesBossLayer = createLiveEntityLayer(
        'live-enemies-boss',
        (e) => e.entityType === 'npc_enemy' && e.rarity === 'boss'
    );

    const livePlayerLayer = createLiveEntityLayer('live-player', (e) => e.entityType === 'player');

    // NPC layer (with disabled state support)
    const npcsLayer = createIconLayer('npcs', data.markers.npcs, getNpcIconType);

    // Resource layers
    const miningNodesLayer = createIconLayer(
        'mining-nodes',
        data.markers.miningNodes,
        'mining-node'
    );
    const itemBagsLayer = createIconLayer('item-bags', data.markers.itemBags, 'item-bag');
    const treasureLocsLayer = createIconLayer(
        'treasure-locs',
        data.markers.treasureLocs,
        'treasure-loc'
    );

    // Collectible layers
    const achievementTriggersLayer = createIconLayer(
        'achievement-triggers',
        data.markers.achievementTriggers,
        'achievement-trigger'
    );

    // Interactable layers
    const doorsLayer = createIconLayer('doors', data.markers.doors, 'door');
    const secretPassagesLayer = createIconLayer(
        'secret-passages',
        data.markers.secretPassages,
        'secret-passage'
    );

    // Utility layers
    const forgesLayer = createIconLayer('forges', data.markers.forges, 'forge');
    const wishingWellsLayer = createIconLayer(
        'wishing-wells',
        data.markers.wishingWells,
        'wishing-well'
    );
    const teleportsLayer = createIconLayer('teleports', data.markers.teleports, 'teleport');

    // === SELECTION HIGHLIGHT LAYERS ===

    // Selection highlight layers (unified for markers, live entities, and zones)
    // Zone selection: yellow outline around polygon
    const zoneSelectionLayer =
        selection?.type === 'zone'
            ? new PolygonLayer({
                  id: 'zone-selection-highlight',
                  data: [selection.zone],
                  getPolygon: (d: ZoneWorldPosition) => d.polygon,
                  getLineColor: HIGHLIGHT_COLORS.primaryRing,
                  getLineWidth: 4,
                  lineWidthUnits: 'pixels',
                  stroked: true,
                  filled: false,
                  pickable: false
              })
            : null;

    // Marker/entity selection: yellow ring around position
    // Size based on ICON_SIZE with slight reduction to create ring effect
    const highlightSize = {
        base: ICON_SIZE.base * 0.6,
        min: ICON_SIZE.min * 0.65,
        max: ICON_SIZE.max * 0.7
    };
    const selectionPosition =
        selection && selection.type !== 'zone'
            ? getSelectionPosition(selection, zones, data.zoneConfigs, overrides, live.entities)
            : null;
    const pointSelectionLayer = selectionPosition
        ? new ScatterplotLayer({
              id: 'selection-highlight',
              data: [{ position: selectionPosition }],
              getPosition: (d: { position: [number, number] }) => d.position,
              getFillColor: HIGHLIGHT_COLORS.primaryFill,
              getLineColor: HIGHLIGHT_COLORS.primaryRing,
              getRadius: highlightSize.base,
              radiusUnits: 'pixels',
              radiusMinPixels: highlightSize.min,
              radiusMaxPixels: highlightSize.max,
              stroked: true,
              lineWidthUnits: 'pixels',
              lineWidthMinPixels: 3,
              lineWidthMaxPixels: 4,
              pickable: false,
              updateTriggers: {
                  getPosition: [overrides, selection, live.entities]
              }
          })
        : null;

    // === MOVEMENT VISUALIZATION LAYERS ===
    // Only show for selected enemy/NPC markers with movement data

    // Helper to get movement data from selected marker
    const getSelectedMovement = (): {
        position: [number, number];
        wanderRange: number | null;
        worldWaypoints: [number, number][] | null;
        loopPatrol: boolean;
    } | null => {
        if (!selection || selection.type !== 'marker') return null;
        const marker = selection.marker;
        if (marker.category !== 'enemy' && marker.category !== 'npc') return null;
        const enemyOrNpc = marker as WorldEnemy | WorldNpc;
        if (!enemyOrNpc.movement && !enemyOrNpc.worldPatrolWaypoints) return null;
        return {
            position: getMarkerPosition(enemyOrNpc),
            wanderRange: enemyOrNpc.movement?.wanderRange ?? null,
            worldWaypoints: enemyOrNpc.worldPatrolWaypoints,
            loopPatrol: enemyOrNpc.movement?.loopPatrol ?? false
        };
    };

    const movementData = getSelectedMovement();

    // Wander range circle (blue, 10% fill)
    const wanderRangeLayer =
        movementData?.wanderRange && movementData.wanderRange > 0
            ? new ScatterplotLayer({
                  id: 'wander-range',
                  data: [{ position: movementData.position, radius: movementData.wanderRange }],
                  getPosition: (d: { position: [number, number] }) => d.position,
                  getRadius: (d: { radius: number }) => d.radius,
                  getFillColor: MOVEMENT_COLORS.wanderCircle,
                  getLineColor: MOVEMENT_COLORS.wanderStroke,
                  stroked: true,
                  lineWidthUnits: 'pixels',
                  lineWidthMinPixels: 1,
                  lineWidthMaxPixels: 2,
                  pickable: false,
                  updateTriggers: {
                      getPosition: [overrides, selection]
                  }
              })
            : null;

    // Patrol path layers
    let patrolSpawnLineLayer = null;
    let patrolPathLayer = null;
    let patrolWaypointsLayer = null;

    if (movementData?.worldWaypoints && movementData.worldWaypoints.length > 0) {
        const waypoints = movementData.worldWaypoints;
        const spawnPos = movementData.position;

        // Dashed line from spawn to first waypoint
        patrolSpawnLineLayer = new LineLayer({
            id: 'patrol-spawn-line',
            data: [{ source: spawnPos, target: waypoints[0] }],
            getSourcePosition: (d: { source: [number, number] }) => d.source,
            getTargetPosition: (d: { target: [number, number] }) => d.target,
            getColor: MOVEMENT_COLORS.patrolDashed,
            getWidth: 2,
            widthUnits: 'pixels',
            pickable: false
        });

        // Solid patrol path through waypoints (close loop if loopPatrol)
        const pathSegments: { source: [number, number]; target: [number, number] }[] = [];
        for (let i = 0; i < waypoints.length - 1; i++) {
            pathSegments.push({ source: waypoints[i], target: waypoints[i + 1] });
        }
        // Close the loop if LoopPatrol is true
        if (movementData.loopPatrol && waypoints.length > 1) {
            pathSegments.push({
                source: waypoints[waypoints.length - 1],
                target: waypoints[0]
            });
        }

        if (pathSegments.length > 0) {
            patrolPathLayer = new LineLayer({
                id: 'patrol-path',
                data: pathSegments,
                getSourcePosition: (d: { source: [number, number] }) => d.source,
                getTargetPosition: (d: { target: [number, number] }) => d.target,
                getColor: MOVEMENT_COLORS.patrolLine,
                getWidth: 2,
                widthUnits: 'pixels',
                pickable: false
            });
        }

        // Waypoint markers (small circles)
        patrolWaypointsLayer = new ScatterplotLayer({
            id: 'patrol-waypoints',
            data: waypoints.map((wp) => ({ position: wp })),
            getPosition: (d: { position: [number, number] }) => d.position,
            getRadius: 4,
            radiusUnits: 'pixels',
            getFillColor: MOVEMENT_COLORS.waypoint,
            pickable: false
        });
    }

    // === GLOBAL MOVEMENT OVERLAY LAYERS ===
    // Shown for all enemies/NPCs when the sidebar toggles are enabled.
    // Uses white/muted colors to stay visually distinct from the yellow/blue selection overlay.
    // Built below the per-selection layers in the stack so the selected entity always paints on top.

    type WanderDatum = { position: [number, number]; radius: number };
    type PatrolSegment = { source: [number, number]; target: [number, number] };

    const allSpawnMarkers = [
        ...data.markers.enemiesCommon,
        ...data.markers.enemiesRare,
        ...data.markers.enemiesUnique,
        ...data.markers.npcs
    ];

    type EventAnchorDatum = {
        source: [number, number];
        target: [number, number];
    };

    const eventAnchorData: EventAnchorDatum[] = allSpawnMarkers.flatMap((marker) =>
        (marker.eventWorldPositions ?? []).map((target) => ({
            source: getMarkerPosition(marker),
            target
        }))
    );
    const eventAnchorLinesLayer =
        eventAnchorData.length > 0
            ? new LineLayer({
                  id: 'dynamic-event-anchor-lines',
                  data: eventAnchorData,
                  getSourcePosition: (d: EventAnchorDatum) => [d.source[0], d.source[1], 0],
                  getTargetPosition: (d: EventAnchorDatum) => [d.target[0], d.target[1], 0],
                  getColor: [245, 158, 11, 180],
                  getWidth: 2,
                  widthUnits: 'pixels',
                  pickable: false
              })
            : null;
    const eventAnchorPointsLayer =
        eventAnchorData.length > 0
            ? new ScatterplotLayer({
                  id: 'dynamic-event-anchor-points',
                  data: eventAnchorData,
                  getPosition: (d: EventAnchorDatum) => d.target,
                  getRadius: 5,
                  radiusUnits: 'pixels',
                  getFillColor: [245, 158, 11, 230],
                  pickable: false
              })
            : null;

    const wanderData: WanderDatum[] = allSpawnMarkers.flatMap((m) =>
        m.movement?.wanderRange && m.movement.wanderRange > 0
            ? [{ position: getMarkerPosition(m), radius: m.movement.wanderRange }]
            : []
    );
    const allWanderRangesLayer =
        layerVisibility.showWanderRanges && wanderData.length > 0
            ? new ScatterplotLayer({
                  id: 'all-wander-ranges',
                  data: wanderData,
                  getPosition: (d: WanderDatum) => d.position,
                  getRadius: (d: WanderDatum) => d.radius,
                  getFillColor: MOVEMENT_COLORS.allWanderCircle,
                  getLineColor: MOVEMENT_COLORS.allWanderStroke,
                  stroked: true,
                  lineWidthUnits: 'pixels',
                  lineWidthMinPixels: 1,
                  lineWidthMaxPixels: 2,
                  pickable: false
              })
            : null;

    // Segments for every marker: spawn→wp0, then wp0→wp1→…→wpN-1,
    // plus wpN-1→wp0 closing segment for loop-patrol routes.
    // Mirrors the three-part logic of the per-selection patrol layers:
    //   patrolSpawnLineLayer (spawn→wp0) + patrolPathLayer (wp0…wpN) + loop close.
    const patrolSegments: PatrolSegment[] = [];
    for (const m of allSpawnMarkers) {
        const wps = m.worldPatrolWaypoints;
        if (!wps || wps.length === 0) continue;
        const spawnPos = getMarkerPosition(m);
        // spawn → first waypoint
        patrolSegments.push({ source: spawnPos, target: wps[0] });
        // consecutive waypoint pairs
        for (let i = 0; i < wps.length - 1; i++) {
            patrolSegments.push({ source: wps[i], target: wps[i + 1] });
        }
        // loop close: last waypoint → first waypoint
        if (m.movement?.loopPatrol && wps.length > 1) {
            patrolSegments.push({ source: wps[wps.length - 1], target: wps[0] });
        }
    }
    const allPatrolPathsLayer =
        layerVisibility.showPatrols && patrolSegments.length > 0
            ? new LineLayer({
                  id: 'all-patrol-paths',
                  data: patrolSegments,
                  getSourcePosition: (d: PatrolSegment) => d.source,
                  getTargetPosition: (d: PatrolSegment) => d.target,
                  getColor: MOVEMENT_COLORS.allPatrolLine,
                  getWidth: 2,
                  widthUnits: 'pixels',
                  pickable: false
              })
            : null;

    // === SEARCH HIGHLIGHT LAYERS ===

    // All spawn positions for a search result (amber rings)
    const searchHighlightAllLayer =
        searchHighlightPositions.length > 0
            ? new ScatterplotLayer({
                  id: 'search-highlight-all',
                  data: searchHighlightPositions,
                  getPosition: (d: { position: [number, number] }) => d.position,
                  getFillColor: HIGHLIGHT_COLORS.fill,
                  getLineColor: HIGHLIGHT_COLORS.ring,
                  getRadius: highlightSize.base,
                  radiusUnits: 'pixels',
                  radiusMinPixels: highlightSize.min,
                  radiusMaxPixels: highlightSize.max,
                  stroked: true,
                  lineWidthUnits: 'pixels',
                  lineWidthMinPixels: 2,
                  lineWidthMaxPixels: 3,
                  pickable: false,
                  updateTriggers: {
                      getPosition: [searchHighlightPositions]
                  }
              })
            : null;

    // Hovered spawn point(s) (brighter ring). Item hover narrows to a
    // dropper's spawns; enemy/NPC hover spotlights a single spawn.
    const hoveredKeys = hoveredSpawnKeys;
    const hoveredHighlightData = hoveredKeys
        ? searchHighlightPositions.filter((p) => hoveredKeys.has(p.stableKey))
        : [];
    const searchHighlightHoverLayer =
        hoveredHighlightData.length > 0
            ? new ScatterplotLayer({
                  id: 'search-highlight-hover',
                  data: hoveredHighlightData,
                  getPosition: (d: { position: [number, number] }) => d.position,
                  getFillColor: HIGHLIGHT_COLORS.primaryFill,
                  getLineColor: HIGHLIGHT_COLORS.primaryRing,
                  getRadius: highlightSize.base,
                  radiusUnits: 'pixels',
                  radiusMinPixels: highlightSize.min,
                  radiusMaxPixels: highlightSize.max,
                  stroked: true,
                  lineWidthUnits: 'pixels',
                  lineWidthMinPixels: 3,
                  lineWidthMaxPixels: 4,
                  pickable: false,
                  updateTriggers: {
                      getPosition: [hoveredSpawnKeys, searchHighlightPositions]
                  }
              })
            : null;

    // === LAYER ORDER (filtered by visibility) ===
    const vis = layerVisibility;
    return [
        // Always show background
        backgroundLayer,
        // Terrain layers
        vis.worldMap && backdropLayer,
        vis.tiles && tileLayers,
        vis.zoneBounds && zoneBoundsLayer,
        vis.zoneLabels && zoneLabelsLayer,
        // Zone connections
        vis.zoneLines && zoneLineConnectionsLayer,
        vis.zoneLines && zoneLineDestinationsLayer,
        // Event connector lines sit beneath spawn icons
        eventAnchorLinesLayer,
        // Common enemies
        vis.spawnPoints && enemiesCommonLayer,
        // NPCs
        vis.characters && npcsLayer,
        // Rare enemies
        vis.spawnPointsRare && enemiesRareLayer,
        // Resources
        vis.miningNodes && miningNodesLayer,
        vis.itemBags && itemBagsLayer,
        vis.treasureLocs && treasureLocsLayer,
        vis.water && null, // TODO: Add water layer when implemented
        // Secrets
        vis.achievementTriggers && achievementTriggersLayer,
        vis.doors && doorsLayer,
        vis.secretPassages && secretPassagesLayer,
        // Utilities
        vis.forges && forgesLayer,
        vis.wishingWells && wishingWellsLayer,
        vis.teleports && teleportsLayer,
        // Zone line icons
        vis.zoneLines && zoneLineIconsLayer,
        // Unique enemies
        vis.spawnPointsUnique && enemiesUniqueLayer,
        // Live entities (above static markers, priority-ordered bottom to top)
        liveNpcFriendlyLayer,
        livePetsLayer,
        liveSimPlayersLayer,
        liveEnemiesCommonLayer,
        liveEnemiesRareLayer,
        liveEnemiesBossLayer,
        livePlayerLayer,
        // Global movement overlays (below per-selection so selection paints on top)
        eventAnchorPointsLayer,
        allWanderRangesLayer,
        allPatrolPathsLayer,
        // Movement visualization for selected entity (yellow/blue, on top of global)
        wanderRangeLayer,
        patrolSpawnLineLayer,
        patrolPathLayer,
        patrolWaypointsLayer,
        // Search highlights (above movement, below single-point selection)
        searchHighlightAllLayer,
        searchHighlightHoverLayer,
        // Selection highlights (on top of everything)
        zoneSelectionLayer,
        pointSelectionLayer
    ]
        .flat()
        .filter(Boolean);
}
