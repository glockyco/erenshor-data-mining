import { describe, expect, it } from 'vitest';
import type {
    LayerVisibility,
    WorldEnemy,
    ZoneConfig,
    ZoneWorldPosition
} from '$lib/types/world-map';
import { DEFAULT_LAYER_VISIBILITY } from '$lib/types/world-map';
import type { EntityData } from '$lib/map/live/types';
import { adjustMarkerPosition } from '$lib/map/debug/position-service';
import { transformEntityToWorld } from '$lib/map/coordinate-transform';
import {
    BACKDROP_HEIGHT,
    BACKDROP_WIDTH,
    computeBackdropBounds,
    computeWorldBounds,
    createLayers,
    type CreateLayersParams,
    type DeckLayerModules,
    type LayerData
} from './layers';

// --- Fakes -----------------------------------------------------------------
// Each deck.gl layer/extension is replaced with a recorder that keeps the props
// object verbatim, so tests can inspect ids, ordering, update triggers, and
// invoke accessor callbacks (getPosition, getFilterValue, ...).

class FakeLayer {
    props: Record<string, unknown>;
    constructor(props: Record<string, unknown>) {
        this.props = props;
    }
}

const modules = {
    IconLayer: FakeLayer,
    PolygonLayer: FakeLayer,
    TextLayer: FakeLayer,
    BitmapLayer: FakeLayer,
    LineLayer: FakeLayer,
    ScatterplotLayer: FakeLayer,
    TileLayer: FakeLayer,
    Tileset2D: class {},
    DataFilterExtension: FakeLayer
} as unknown as DeckLayerModules;

// --- Fixtures --------------------------------------------------------------

const zoneConfig: ZoneConfig = {
    zoneName: 'Test Zone',
    tileUrl: '/tiles/Test/{z}/{x}/{y}.webp',
    baseTilesX: 2,
    baseTilesY: 1,
    tileSize: 100,
    zoom: 0,
    minZoom: -1,
    maxZoom: 2,
    originX: -40,
    originY: 120,
    northBearing: 135
};

const zone: ZoneWorldPosition = {
    key: 'Test',
    name: 'Test Zone',
    worldX: 100,
    worldY: 200,
    bounds: { minX: 0, minY: 0, maxX: 100, maxY: 200 },
    polygon: [
        [0, 0],
        [100, 0],
        [100, 200],
        [0, 200]
    ],
    centroid: [50, 100]
};

function makeEnemy(overrides: Partial<WorldEnemy> = {}): WorldEnemy {
    return {
        category: 'enemy',
        stableKey: 'enemy-1',
        zone: 'Test',
        zoneName: 'Test Zone',
        worldPosition: [50, 60],
        worldPatrolWaypoints: null,
        levelMin: 5,
        levelMax: 10,
        isEnabled: true,
        isUnique: false,
        isRare: false,
        characters: [],
        ...overrides
    } as unknown as WorldEnemy;
}

const emptyMarkers: LayerData['markers'] = {
    achievementTriggers: [],
    doors: [],
    enemiesCommon: [],
    enemiesRare: [],
    enemiesUnique: [],
    forges: [],
    itemBags: [],
    miningNodes: [],
    npcs: [],
    secretPassages: [],
    teleports: [],
    treasureLocs: [],
    wishingWells: [],
    zoneLines: []
};

function baseParams(overrides: Partial<CreateLayersParams> = {}): CreateLayersParams {
    return {
        atlas: { atlas: {} as HTMLCanvasElement, mapping: {} },
        modules,
        data: {
            markers: { ...emptyMarkers },
            zones: [zone],
            zoneConfigs: { Test: zoneConfig }
        },
        effectiveZones: [zone],
        overrides: {},
        draggingZone: null,
        backdrop: { enabled: false, x: 0, y: 0, scale: 1 },
        layerVisibility: { ...DEFAULT_LAYER_VISIBILITY },
        levelFilter: [1, 20],
        selection: null,
        searchHighlightPositions: [],
        hoveredSpawnKeys: null,
        live: { connectionState: 'disconnected', zone: null, entities: [] },
        ...overrides
    };
}

function ids(layers: unknown[]): string[] {
    return (layers as FakeLayer[]).map((l) => l.props.id as string);
}

function byId(layers: unknown[], id: string): FakeLayer {
    const found = (layers as FakeLayer[]).find((l) => l.props.id === id);
    if (!found) throw new Error(`layer not found: ${id}`);
    return found;
}

// --- Bounds ----------------------------------------------------------------

describe('computeBackdropBounds', () => {
    it('returns [left, bottom, right, top] with the Y axis flipped for the image', () => {
        expect(computeBackdropBounds({ enabled: true, x: 0, y: 0, scale: 1 })).toEqual([
            -BACKDROP_WIDTH / 2,
            BACKDROP_HEIGHT / 2,
            BACKDROP_WIDTH / 2,
            -BACKDROP_HEIGHT / 2
        ]);
    });
});

describe('computeWorldBounds', () => {
    it('spans zone bounds padded by 500 when the backdrop is disabled', () => {
        expect(computeWorldBounds([zone], { enabled: false, x: 0, y: 0, scale: 1 })).toEqual({
            minX: -500,
            minY: -500,
            maxX: 600,
            maxY: 700
        });
    });

    it('expands to include the backdrop footprint when enabled', () => {
        // backdrop at origin, scale 1 → half-extent 802 x 1024; still padded by 500.
        expect(computeWorldBounds([zone], { enabled: true, x: 0, y: 0, scale: 1 })).toEqual({
            minX: -BACKDROP_WIDTH / 2 - 500,
            minY: -BACKDROP_HEIGHT / 2 - 500,
            maxX: BACKDROP_WIDTH / 2 + 500,
            maxY: BACKDROP_HEIGHT / 2 + 500
        });
    });

    it('drives the background polygon corners in createLayers', () => {
        const layers = createLayers(baseParams());
        const bg = byId(layers, 'background');
        const datum = (bg.props.data as { polygon: [number, number][] }[])[0];
        expect(datum.polygon).toEqual([
            [-500, -500],
            [600, -500],
            [600, 700],
            [-500, 700]
        ]);
    });
});

// --- Ordering & visibility -------------------------------------------------

describe('createLayers ordering', () => {
    it('emits the core layer stack in a fixed paint order', () => {
        const layers = createLayers(baseParams());
        expect(ids(layers)).toEqual([
            'background',
            'world-map',
            'tiles-Test',
            'zone-labels',
            'zone-line-connections',
            'zone-line-destinations',
            'enemies-common',
            'npcs',
            'enemies-rare',
            'mining-nodes',
            'item-bags',
            'treasure-locs',
            'achievement-triggers',
            'doors',
            'secret-passages',
            'forges',
            'wishing-wells',
            'teleports',
            'zone-lines',
            'enemies-unique'
        ]);
    });

    it('keeps rare and unique enemies above common/NPC layers', () => {
        const list = ids(createLayers(baseParams()));
        expect(list.indexOf('enemies-common')).toBeLessThan(list.indexOf('enemies-rare'));
        expect(list.indexOf('npcs')).toBeLessThan(list.indexOf('enemies-rare'));
        expect(list.indexOf('enemies-rare')).toBeLessThan(list.indexOf('enemies-unique'));
    });
});

describe('createLayers visibility filtering', () => {
    it('omits terrain layers when their toggles are off', () => {
        const vis: LayerVisibility = {
            ...DEFAULT_LAYER_VISIBILITY,
            worldMap: false,
            tiles: false,
            zoneBounds: false,
            zoneLabels: false
        };
        const list = ids(createLayers(baseParams({ layerVisibility: vis })));
        expect(list).not.toContain('world-map');
        expect(list).not.toContain('tiles-Test');
        expect(list).not.toContain('zone-bounds');
        expect(list).not.toContain('zone-labels');
        expect(list[0]).toBe('background'); // background is unconditional
    });

    it('removes every spawn layer independently', () => {
        const vis: LayerVisibility = {
            ...DEFAULT_LAYER_VISIBILITY,
            spawnPoints: false,
            spawnPointsRare: false,
            spawnPointsUnique: false,
            characters: false
        };
        const list = ids(createLayers(baseParams({ layerVisibility: vis })));
        expect(list).not.toContain('enemies-common');
        expect(list).not.toContain('enemies-rare');
        expect(list).not.toContain('enemies-unique');
        expect(list).not.toContain('npcs');
    });

    it('drops all three zone-line layers when zoneLines is off', () => {
        const list = ids(
            createLayers(
                baseParams({ layerVisibility: { ...DEFAULT_LAYER_VISIBILITY, zoneLines: false } })
            )
        );
        expect(list).not.toContain('zone-line-connections');
        expect(list).not.toContain('zone-line-destinations');
        expect(list).not.toContain('zone-lines');
    });
});

// --- Update triggers -------------------------------------------------------

describe('createLayers update triggers', () => {
    it('binds the enemy level filter range and its update trigger to levelFilter', () => {
        const levelFilter: [number, number] = [3, 8];
        const layers = createLayers(baseParams({ levelFilter }));
        const common = byId(layers, 'enemies-common');

        expect(common.props.filterRange).toEqual([
            [-Infinity, 8],
            [3, Infinity]
        ]);
        const triggers = common.props.updateTriggers as { filterRange: unknown };
        expect(triggers.filterRange).toBe(levelFilter);
    });

    it('recomputes marker positions when overrides change', () => {
        const overrides = { Test: { worldX: 110, worldY: 190 } };
        const layers = createLayers(baseParams({ overrides }));
        const common = byId(layers, 'enemies-common');
        const triggers = common.props.updateTriggers as { getPosition: unknown[] };
        expect(triggers.getPosition).toContain(overrides);
    });
});

// --- Positioning -----------------------------------------------------------

describe('createLayers positioning', () => {
    it('places static markers via adjustMarkerPosition (with overrides applied)', () => {
        const overrides = { Test: { worldX: 110, worldY: 190 } };
        const enemy = makeEnemy();
        const layers = createLayers(
            baseParams({
                overrides,
                data: {
                    markers: { ...emptyMarkers, enemiesCommon: [enemy] },
                    zones: [zone],
                    zoneConfigs: { Test: zoneConfig }
                }
            })
        );
        const common = byId(layers, 'enemies-common');
        const getPosition = common.props.getPosition as (d: WorldEnemy) => [number, number];
        expect(getPosition(enemy)).toEqual(
            adjustMarkerPosition(enemy.worldPosition, enemy.zone, [zone], overrides)
        );
        // Sanity: override shifts the zone by (+10, -10)
        expect(getPosition(enemy)).toEqual([60, 50]);
    });

    it('places live entities via transformEntityToWorld', () => {
        const player: EntityData = {
            id: 1,
            entityType: 'player',
            name: 'Hero',
            position: [30, 0, 180],
            rotation: 0
        };
        const layers = createLayers(
            baseParams({
                live: { connectionState: 'connected', zone: 'Test', entities: [player] }
            })
        );
        const playerLayer = byId(layers, 'live-player');
        const getPosition = playerLayer.props.getPosition as (d: EntityData) => [number, number];
        expect(getPosition(player)).toEqual(
            transformEntityToWorld({ ...player, zone: 'Test' }, [zone], { Test: zoneConfig }, {})
        );
    });

    it('omits live layers when disconnected', () => {
        const player: EntityData = {
            id: 1,
            entityType: 'player',
            name: 'Hero',
            position: [30, 0, 180],
            rotation: 0
        };
        const list = ids(
            createLayers(
                baseParams({
                    live: { connectionState: 'disconnected', zone: 'Test', entities: [player] }
                })
            )
        );
        expect(list).not.toContain('live-player');
    });
});

// --- Selection & search overlay precedence ---------------------------------

describe('createLayers overlay precedence', () => {
    it('paints the point selection highlight above search highlights', () => {
        const enemy = makeEnemy();
        const list = ids(
            createLayers(
                baseParams({
                    selection: { type: 'marker', marker: enemy },
                    searchHighlightPositions: [{ position: [1, 2], stableKey: 'k' }],
                    hoveredSpawnKeys: new Set(['k'])
                })
            )
        );
        expect(list).toContain('search-highlight-all');
        expect(list).toContain('search-highlight-hover');
        expect(list.indexOf('search-highlight-all')).toBeLessThan(
            list.indexOf('search-highlight-hover')
        );
        expect(list.indexOf('search-highlight-hover')).toBeLessThan(
            list.indexOf('selection-highlight')
        );
        // Single-point selection is the topmost layer.
        expect(list[list.length - 1]).toBe('selection-highlight');
    });

    it('paints the zone selection outline last for a zone selection', () => {
        const list = ids(createLayers(baseParams({ selection: { type: 'zone', zone } })));
        expect(list[list.length - 1]).toBe('zone-selection-highlight');
        // A zone selection has no single-point highlight.
        expect(list).not.toContain('selection-highlight');
    });

    it('narrows the hover highlight to hovered spawn keys only', () => {
        const layers = createLayers(
            baseParams({
                searchHighlightPositions: [
                    { position: [1, 2], stableKey: 'a' },
                    { position: [3, 4], stableKey: 'b' }
                ],
                hoveredSpawnKeys: new Set(['b'])
            })
        );
        const hover = byId(layers, 'search-highlight-hover');
        expect(hover.props.data).toEqual([{ position: [3, 4], stableKey: 'b' }]);
    });
});
