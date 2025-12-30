<script lang="ts">
    import { browser } from '$app/environment';
    import { INITIAL_VIEW_STATE, ICON_SIZE, BACKGROUND_COLOR, LAYER_COLORS } from '$lib/map/config';
    import {
        createZoneTileset2D,
        getTileWorldCorners,
        type ZoneTileIndex
    } from '$lib/map/zone-tileset';
    import { createIconAtlas, getZoneLineIconType, type IconAtlasResult } from '$lib/map/icons';
    import type { PageData } from './$types';

    let { data }: { data: PageData } = $props();

    // deck.gl instance and modules
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let deckInstance: any = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let deckModules: any = null;
    // Icon atlas for marker layers
    let iconAtlas: IconAtlasResult | null = null;

    // Loading state
    let isLoading = $state(true);
    let loadError = $state<string | null>(null);

    // View state
    let currentViewState = $state({
        x: 0,
        y: 0,
        zoom: INITIAL_VIEW_STATE.zoom
    });

    // Container ref
    let container: HTMLDivElement;

    // Initialize deck.gl when component mounts
    $effect(() => {
        if (!browser || !container) return;

        initializeDeck();

        return () => {
            if (deckInstance) {
                deckInstance.finalize();
                deckInstance = null;
            }
        };
    });

    async function initializeDeck() {
        try {
            // Dynamic imports for deck.gl (SSR safety)
            const [deckCore, deckLayers, deckGeoLayers] = await Promise.all([
                import('@deck.gl/core'),
                import('@deck.gl/layers'),
                import('@deck.gl/geo-layers')
            ]);

            const { Deck, OrthographicView } = deckCore;
            const { IconLayer, PolygonLayer, TextLayer, BitmapLayer, LineLayer, ScatterplotLayer } =
                deckLayers;
            const { TileLayer, _Tileset2D: Tileset2D } = deckGeoLayers;

            deckModules = {
                Deck,
                OrthographicView,
                IconLayer,
                PolygonLayer,
                TextLayer,
                BitmapLayer,
                LineLayer,
                ScatterplotLayer,
                TileLayer,
                Tileset2D
            };

            // Create icon atlas for marker layers
            iconAtlas = await createIconAtlas();

            // Use world center from server
            const [centerX, centerY] = data.worldCenter;

            // Create layers
            const layers = createLayers(iconAtlas);

            // Initialize deck.gl
            deckInstance = new deckModules.Deck({
                parent: container,
                views: new deckModules.OrthographicView({}),
                initialViewState: {
                    target: [centerX, centerY, 0] as [number, number, number],
                    zoom: INITIAL_VIEW_STATE.zoom,
                    minZoom: INITIAL_VIEW_STATE.minZoom,
                    maxZoom: INITIAL_VIEW_STATE.maxZoom
                },
                controller: { inertia: 500 },
                layers,
                getCursor: ({ isHovering }: { isHovering: boolean }) =>
                    isHovering ? 'pointer' : 'grab',
                onViewStateChange: ({
                    viewState
                }: {
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    viewState: any;
                }) => {
                    if (viewState.target) {
                        currentViewState = {
                            x: viewState.target[0],
                            y: viewState.target[1],
                            zoom: viewState.zoom
                        };
                    }
                },
                onHover: () => {
                    // TODO: Implement tooltip on hover
                },
                onClick: () => {
                    // TODO: Implement popup on click
                }
            });

            isLoading = false;
        } catch (err) {
            console.error('Failed to initialize deck.gl:', err);
            loadError = err instanceof Error ? err.message : 'Failed to load map';
            isLoading = false;
        }
    }

    function createLayers(atlas: IconAtlasResult) {
        if (!deckModules) return [];

        const {
            IconLayer,
            PolygonLayer,
            TextLayer,
            BitmapLayer,
            TileLayer,
            Tileset2D,
            LineLayer,
            ScatterplotLayer
        } = deckModules;

        // Helper for creating icon layers
        const createIconLayer = (
            id: string,
            markerData: { worldPosition: [number, number] }[],
            iconType: string
        ) => {
            return new IconLayer({
                id,
                data: markerData,
                iconAtlas: atlas.atlas,
                iconMapping: atlas.mapping,
                getPosition: (d: { worldPosition: [number, number] }) => d.worldPosition,
                getIcon: () => iconType,
                getSize: ICON_SIZE.base,
                sizeUnits: 'pixels',
                sizeMinPixels: ICON_SIZE.min,
                sizeMaxPixels: ICON_SIZE.max,
                pickable: true
            });
        };

        // === WORLD BOUNDS ===
        let minX = Infinity,
            minY = Infinity,
            maxX = -Infinity,
            maxY = -Infinity;
        for (const zone of data.zones) {
            minX = Math.min(minX, zone.bounds.minX);
            minY = Math.min(minY, zone.bounds.minY);
            maxX = Math.max(maxX, zone.bounds.maxX);
            maxY = Math.max(maxY, zone.bounds.maxY);
        }
        const padding = 500;
        minX -= padding;
        minY -= padding;
        maxX += padding;
        maxY += padding;

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

        // Tile layers for each zone
        const tileLayers = data.zones.map((zone) => {
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

        // Zone boundaries
        const zoneBoundsLayer = new PolygonLayer({
            id: 'zone-bounds',
            data: data.zones,
            getPolygon: (d: { polygon: [number, number][] }) => d.polygon,
            getFillColor: [100, 116, 139, 30],
            getLineColor: [100, 116, 139, 150],
            getLineWidth: 2,
            lineWidthUnits: 'pixels',
            pickable: true
        });

        // Zone labels
        const zoneLabelsLayer = new TextLayer({
            id: 'zone-labels',
            data: data.zones,
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
            getSourcePosition: (d: { worldPosition: [number, number] }) => [
                d.worldPosition[0],
                d.worldPosition[1],
                0
            ],
            getTargetPosition: (d: { destinationWorldPosition: [number, number] }) => [
                d.destinationWorldPosition[0],
                d.destinationWorldPosition[1],
                0
            ],
            getColor: (d: { isEnabled: boolean }) =>
                d.isEnabled
                    ? [...LAYER_COLORS['zone-line'], 180]
                    : [...LAYER_COLORS['disabled'], 120],
            getWidth: 3,
            widthUnits: 'pixels',
            pickable: false
        });
        const zoneLineDestinationsLayer = new ScatterplotLayer({
            id: 'zone-line-destinations',
            data: zoneLinesWithDest,
            getPosition: (d: { destinationWorldPosition: [number, number] }) =>
                d.destinationWorldPosition,
            getRadius: 4,
            getFillColor: (d: { isEnabled: boolean }) =>
                d.isEnabled
                    ? [...LAYER_COLORS['zone-line'], 200]
                    : [...LAYER_COLORS['disabled'], 150],
            radiusUnits: 'pixels',
            pickable: false
        });

        // Zone line icons
        const zoneLineIconsLayer = new IconLayer({
            id: 'zone-lines',
            data: data.markers.zoneLines,
            iconAtlas: atlas.atlas,
            iconMapping: atlas.mapping,
            getPosition: (d: { worldPosition: [number, number] }) => d.worldPosition,
            getIcon: (d: { isEnabled?: boolean }) => getZoneLineIconType(d),
            getSize: ICON_SIZE.base,
            sizeUnits: 'pixels',
            sizeMinPixels: ICON_SIZE.min,
            sizeMaxPixels: ICON_SIZE.max,
            pickable: true
        });

        // Enemy layers (by rarity)
        const enemiesCommonLayer = createIconLayer(
            'enemies-common',
            data.markers.enemiesCommon,
            'enemy'
        );
        const enemiesRareLayer = createIconLayer(
            'enemies-rare',
            data.markers.enemiesRare,
            'enemy-rare'
        );
        const enemiesUniqueLayer = createIconLayer(
            'enemies-unique',
            data.markers.enemiesUnique,
            'enemy-unique'
        );

        // NPC layer
        const npcsLayer = createIconLayer('npcs', data.markers.npcs, 'npc');

        // Resource layers
        const waterLayer = createIconLayer('water', data.markers.water, 'water');
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

        // === LAYER ORDER ===
        // Later in array = rendered on top (higher priority)
        return [
            // Base layers
            backgroundLayer,
            ...tileLayers,
            zoneBoundsLayer,
            zoneLabelsLayer,
            // Zone line connections (below icons)
            zoneLineConnectionsLayer,
            zoneLineDestinationsLayer,
            // Enemies (common at bottom)
            enemiesCommonLayer,
            // NPCs
            npcsLayer,
            // Enemies (rare)
            enemiesRareLayer,
            // Resources
            waterLayer,
            miningNodesLayer,
            itemBagsLayer,
            treasureLocsLayer,
            // Collectibles
            achievementTriggersLayer,
            // Interactables
            doorsLayer,
            secretPassagesLayer,
            // Utilities
            forgesLayer,
            wishingWellsLayer,
            teleportsLayer,
            // Zone lines (navigation critical)
            zoneLineIconsLayer,
            // Bosses (always on top)
            enemiesUniqueLayer
            // TODO: Player marker (always on top of everything)
        ];
    }
</script>

<svelte:head>
    <title>World Map | Erenshor Maps</title>
</svelte:head>

<div class="relative h-screen w-full">
    <!-- Map container -->
    <div bind:this={container} class="absolute inset-0"></div>

    <!-- Loading overlay -->
    {#if isLoading}
        <div class="loading-overlay absolute inset-0 flex items-center justify-center bg-zinc-900">
            <div class="text-center">
                <div
                    class="mb-4 h-8 w-8 animate-spin rounded-full border-4 border-zinc-600 border-t-white"
                ></div>
                <p class="text-zinc-400">Loading map...</p>
            </div>
        </div>
    {/if}

    <!-- Error message -->
    {#if loadError}
        <div class="absolute inset-0 flex items-center justify-center bg-zinc-900">
            <div class="text-center">
                <p class="text-red-500">Error: {loadError}</p>
            </div>
        </div>
    {/if}

    <!-- Debug info -->
    <div class="absolute bottom-4 left-4 rounded bg-zinc-800/80 p-2 text-xs text-zinc-400">
        <p>X: {currentViewState.x.toFixed(0)}</p>
        <p>Y: {currentViewState.y.toFixed(0)}</p>
        <p>Zoom: {currentViewState.zoom.toFixed(2)}</p>
        <p>Zones: {data.zones.length}</p>
        <p>
            Enemies: {data.markers.enemiesCommon.length +
                data.markers.enemiesRare.length +
                data.markers.enemiesUnique.length}
        </p>
        <p>NPCs: {data.markers.npcs.length}</p>
        <p>Zone Lines: {data.markers.zoneLines.length}</p>
    </div>
</div>
