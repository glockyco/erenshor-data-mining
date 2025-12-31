<script lang="ts">
    import { browser } from '$app/environment';
    import { tick } from 'svelte';
    import {
        INITIAL_VIEW_STATE,
        ICON_SIZE,
        BACKGROUND_COLOR,
        LAYER_COLORS,
        HIGHLIGHT_COLORS,
        MOVEMENT_COLORS
    } from '$lib/map/config';
    import { flyTo, flyToBounds } from '$lib/map/flyto';
    import {
        createZoneTileset2D,
        getTileWorldCorners,
        type ZoneTileIndex
    } from '$lib/map/zone-tileset';
    import {
        createIconAtlas,
        getZoneLineIconType,
        getEnemyIconType,
        getNpcIconType,
        type IconAtlasResult
    } from '$lib/map/icons';
    import {
        createDebugStore,
        getEffectiveZones,
        adjustMarkerPosition,
        DragController,
        loadOverrides,
        saveOverrides,
        clearOverrides,
        loadBackdropSettings,
        saveBackdropSettings,
        exportToJson,
        copyToClipboard,
        downloadJson,
        type DragInfo,
        type BackdropSettings
    } from '$lib/map/debug';
    import { urlManager, parseUrlState, parseLayerVisibility } from '$lib/map/url-state';
    import {
        DEFAULT_LAYER_VISIBILITY,
        type LayerVisibility,
        type AnyWorldMarker,
        type ZoneWorldPosition,
        type WorldEnemy,
        type WorldNpc
    } from '$lib/types/world-map';
    import MapSidebar from '$lib/components/map/MapSidebar.svelte';
    import MapTooltip from '$lib/components/map/MapTooltip.svelte';
    import ZoneTooltip from '$lib/components/map/ZoneTooltip.svelte';
    import MapPopup from '$lib/components/map/MapPopup.svelte';
    import ZonePopup from '$lib/components/map/ZonePopup.svelte';
    import type { PageData } from './$types';

    let { data }: { data: PageData } = $props();

    // Layer visibility state
    let layerVisibility = $state<LayerVisibility>({ ...DEFAULT_LAYER_VISIBILITY });

    // Zone focus state (null = world view)
    let focusedZone = $state<string | null>(null);

    // Debug mode state (derived from URL or initial parse)
    let isDebugMode = $state(false);

    // Sidebar state (persisted to localStorage)
    let sidebarCollapsed = $state(false);
    const SIDEBAR_COLLAPSED_KEY = 'erenshor-map-sidebar-collapsed';

    // Tooltip state
    let hoveredMarker = $state<AnyWorldMarker | null>(null);
    let hoveredZone = $state<ZoneWorldPosition | null>(null);
    let hoverPosition = $state<{ x: number; y: number }>({ x: 0, y: 0 });

    // Selection state (for popups)
    let selectedMarker = $state<AnyWorldMarker | null>(null);
    let selectedMarkerZoneName = $state<string>('');
    let selectedZone = $state<ZoneWorldPosition | null>(null);

    // Desktop detection (tooltips only on desktop)
    let isDesktop = $state(false);
    $effect(() => {
        if (!browser) return;
        const mediaQuery = window.matchMedia('(min-width: 768px)');
        isDesktop = mediaQuery.matches;
        const handler = (e: MediaQueryListEvent) => (isDesktop = e.matches);
        mediaQuery.addEventListener('change', handler);
        return () => mediaQuery.removeEventListener('change', handler);
    });

    // Get zone display name from zone key
    function getZoneName(zoneKey: string): string {
        const zone = data.zones.find((z) => z.key === zoneKey);
        return zone?.name ?? zoneKey;
    }

    // Find marker by coordinateId and category
    function findMarkerByIdAndType(id: number, type: string): AnyWorldMarker | null {
        const allMarkers: AnyWorldMarker[] = [
            ...data.markers.achievementTriggers,
            ...data.markers.doors,
            ...data.markers.enemiesCommon,
            ...data.markers.enemiesRare,
            ...data.markers.enemiesUnique,
            ...data.markers.forges,
            ...data.markers.itemBags,
            ...data.markers.miningNodes,
            ...data.markers.npcs,
            ...data.markers.secretPassages,
            ...data.markers.teleports,
            ...data.markers.treasureLocs,
            ...data.markers.water,
            ...data.markers.wishingWells,
            ...data.markers.zoneLines
        ];
        return allMarkers.find((m) => m.coordinateId === id && m.category === type) ?? null;
    }

    // Find zone by key
    function findZoneByKey(key: string): ZoneWorldPosition | null {
        return data.zones.find((z) => z.key === key) ?? null;
    }

    /**
     * Build complete URL params from current state.
     * Called by all URL sync operations.
     */
    function buildUrlParams() {
        return {
            viewState: currentViewState,
            layers: layerVisibility,
            entityId: selectedMarker ? String(selectedMarker.coordinateId) : null,
            entityType: selectedMarker?.category ?? null,
            selectedZoneKey: selectedZone?.key ?? null,
            focusedZoneId: focusedZone,
            debug: isDebugMode
        };
    }

    /**
     * Apply selection state. Single point for all selection changes.
     * @param marker - Marker to select, or null to clear
     * @param skipUrlUpdate - True when restoring from URL
     */
    function applySelection(marker: AnyWorldMarker | null, skipUrlUpdate = false): void {
        selectedMarker = marker;
        selectedMarkerZoneName = marker ? getZoneName(marker.zone) : '';
        selectedZone = null; // Close zone popup when selecting a marker

        if (!skipUrlUpdate) {
            urlManager.pushSelection(buildUrlParams());
        }
        updateLayers();
    }

    /**
     * Close popup.
     */
    function closePopup(): void {
        if (selectedMarker) {
            applySelection(null);
        } else if (selectedZone) {
            selectZone(null);
        }
    }

    /**
     * Select a zone (for zone popups), or null to close.
     * Matches applySelection pattern with skipUrlUpdate parameter.
     */
    function selectZone(zone: ZoneWorldPosition | null, skipUrlUpdate = false): void {
        selectedZone = zone;
        selectedMarker = null;
        selectedMarkerZoneName = '';

        if (!skipUrlUpdate) {
            urlManager.pushSelection(buildUrlParams());
        }
        updateLayers();
    }

    // Focus on marker (fly to position, adjusted for zone overrides)
    function focusMarker(marker: AnyWorldMarker): void {
        const position = adjustMarkerPosition(
            marker.worldPosition,
            marker.zone,
            data.zones,
            debugStore.overrides
        );
        flyTo(deckInstance, position[0], position[1], { zoom: 0 });
    }

    // Focus on zone (fly to show full zone bounds)
    function focusZone(zone: ZoneWorldPosition): void {
        flyToBounds(deckInstance, zone.bounds);
    }

    // Load sidebar state from localStorage
    $effect(() => {
        if (browser) {
            const stored = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
            if (stored !== null) {
                sidebarCollapsed = stored === 'true';
            }
        }
    });

    // Save sidebar state to localStorage
    function toggleSidebar() {
        sidebarCollapsed = !sidebarCollapsed;
        if (browser) {
            localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(sidebarCollapsed));
        }
    }

    // Handle layer visibility change
    function handleLayerVisibilityChange(key: keyof LayerVisibility, value: boolean) {
        layerVisibility = { ...layerVisibility, [key]: value };
        urlManager.syncPreferences(buildUrlParams());
        updateLayers();
    }

    // Keyboard shortcuts
    function handleKeydown(event: KeyboardEvent) {
        // Ignore if typing in an input
        if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) {
            return;
        }

        // ESC closes popup
        if (event.key === 'Escape' && (selectedMarker || selectedZone)) {
            closePopup();
            return;
        }

        // B toggles sidebar
        if (event.key === 'b' || event.key === 'B') {
            toggleSidebar();
        }
    }

    // Debug store: centralized state management
    const debugStore = createDebugStore(
        browser ? loadOverrides() : {},
        browser ? loadBackdropSettings() : undefined
    );

    // Effective zones with overrides applied
    const effectiveZones = $derived(
        getEffectiveZones(data.zones, data.zoneConfigs, debugStore.overrides)
    );

    // Drag controller: manages drag interactions
    const dragController = new DragController(
        (zoneKey, offset) => {
            debugStore.setOverride(zoneKey, offset);
            debugStore.setDraggingZone(zoneKey);
            updateLayers();
        },
        () => {
            saveOverrides(debugStore.overrides);
            debugStore.setDraggingZone(null);
        }
    );

    // Enable debug store when debug mode is active
    $effect(() => {
        if (isDebugMode) {
            debugStore.enable();
        } else {
            debugStore.disable();
        }
    });

    /**
     * Restore state from URL. Called on mount and popstate.
     * Uses passive mode to prevent URL updates during restoration.
     */
    async function restoreFromUrl(): Promise<void> {
        urlManager.enterPassiveMode();

        try {
            const urlState = parseUrlState();

            if (urlState) {
                // Restore debug mode
                isDebugMode = urlState.debug;

                // Restore layer visibility
                layerVisibility = parseLayerVisibility(urlState.layers);

                // Restore zone focus
                focusedZone = urlState.zone;

                // Restore view state
                currentViewState = {
                    x: urlState.x,
                    y: urlState.y,
                    zoom: urlState.zoom
                };

                // Restore view state if deck is initialized
                if (deckInstance) {
                    deckInstance.setProps({
                        initialViewState: {
                            target: [urlState.x, urlState.y, 0] as [number, number, number],
                            zoom: urlState.zoom,
                            minZoom: INITIAL_VIEW_STATE.minZoom,
                            maxZoom: INITIAL_VIEW_STATE.maxZoom
                        }
                    });
                }

                // Restore selection (marker or zone)
                if (urlState.entity && urlState.etype) {
                    const marker = findMarkerByIdAndType(parseInt(urlState.entity), urlState.etype);
                    if (marker) {
                        applySelection(marker, true);
                    } else {
                        console.warn(`Marker not found: ${urlState.etype}:${urlState.entity}`);
                        applySelection(null, true);
                    }
                } else if (urlState.selectedZone) {
                    const zone = findZoneByKey(urlState.selectedZone);
                    if (zone) {
                        selectZone(zone, true);
                    } else {
                        console.warn(`Zone not found: ${urlState.selectedZone}`);
                        selectedZone = null;
                    }
                } else {
                    applySelection(null, true);
                    selectedZone = null;
                }

                // Sync deduplication tracking
                urlManager.setLastSelection(urlState.entity, urlState.etype, urlState.selectedZone);
            } else {
                // No URL state - use defaults
                isDebugMode = false;
                layerVisibility = { ...DEFAULT_LAYER_VISIBILITY };
                focusedZone = null;
                applySelection(null, true);
            }

            await tick();
        } finally {
            urlManager.exitPassiveMode();
        }
    }

    // Handle browser back/forward navigation
    async function handlePopstate(): Promise<void> {
        await restoreFromUrl();
        updateLayers();
    }

    // deck.gl instance and modules
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let deckInstance: any = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let deckModules: any = null;
    let iconAtlas: IconAtlasResult | null = null;

    // Loading state
    let isLoading = $state(true);
    let loadError = $state<string | null>(null);

    // View state
    let currentViewState = $state<{ x: number; y: number; zoom: number }>({
        x: 0,
        y: 0,
        zoom: INITIAL_VIEW_STATE.zoom
    });

    // Backdrop image constants
    const BACKDROP_IMAGE = '/erenshor-world-map.webp';
    const BACKDROP_WIDTH = 1604;
    const BACKDROP_HEIGHT = 2048;

    // Compute backdrop bounds from settings
    // deck.gl BitmapLayer bounds: [left, bottom, right, top]
    // Y axis increases upward, so swap Y values to flip image correctly
    function computeBackdropBounds(settings: BackdropSettings): [number, number, number, number] {
        const width = BACKDROP_WIDTH * settings.scale;
        const height = BACKDROP_HEIGHT * settings.scale;
        return [
            settings.x - width / 2,
            settings.y + height / 2,
            settings.x + width / 2,
            settings.y - height / 2
        ];
    }

    // Persist backdrop settings when changed
    $effect(() => {
        if (browser) {
            saveBackdropSettings(debugStore.backdrop);
        }
    });

    // Container ref
    let container: HTMLDivElement;

    // Drag event handlers (delegate to DragController)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    function handleDragStart(info: any, event: any) {
        if (!debugStore.enabled) return false;
        return dragController.tryStartDrag(info as DragInfo, event?.srcEvent?.shiftKey ?? false);
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    function handleDrag(info: any, event: any) {
        return dragController.handleDrag(
            info.coordinate as [number, number],
            event?.srcEvent?.shiftKey ?? false
        );
    }

    function handleDragEnd() {
        dragController.handleDragEnd();
    }

    // Update deck.gl layers
    function updateLayers() {
        if (deckInstance && iconAtlas) {
            const layers = createLayers(iconAtlas);
            deckInstance.setProps({ layers });
        }
    }

    // Debug UI handlers
    async function handleCopyToClipboard() {
        const exportData = exportToJson(debugStore.overrides, data.zones);
        await copyToClipboard(exportData);
        alert('Zone positions copied to clipboard!');
    }

    function handleDownloadJson() {
        const exportData = exportToJson(debugStore.overrides, data.zones);
        downloadJson(exportData);
    }

    function handleResetOverrides() {
        if (confirm('Reset all zone positions to defaults?')) {
            clearOverrides();
            debugStore.reset();
            updateLayers();
        }
    }

    // Track whether URL has explicit view state (x, y, z params)
    let hasUrlViewState = false;

    // Calculate zoom level to fit bounds in viewport
    function calculateFitZoom(
        bounds: { minX: number; minY: number; maxX: number; maxY: number },
        viewportWidth: number,
        viewportHeight: number,
        padding: number = 50
    ): number {
        const boundsWidth = bounds.maxX - bounds.minX;
        const boundsHeight = bounds.maxY - bounds.minY;

        // Account for padding
        const availableWidth = viewportWidth - padding * 2;
        const availableHeight = viewportHeight - padding * 2;

        // Calculate zoom to fit (deck.gl zoom is log2 scale)
        const zoomX = Math.log2(availableWidth / boundsWidth);
        const zoomY = Math.log2(availableHeight / boundsHeight);

        // Use the smaller zoom to ensure both dimensions fit
        return Math.min(zoomX, zoomY);
    }

    // Initialize deck.gl when component mounts
    $effect(() => {
        if (!browser || !container) return;

        // Check if URL has explicit view state params
        const params = new URLSearchParams(window.location.search);
        hasUrlViewState = params.has('x') || params.has('y') || params.has('z');

        // Parse initial URL state (passive mode is handled in restoreFromUrl)
        urlManager.enterPassiveMode();
        try {
            const urlState = parseUrlState();

            if (urlState) {
                isDebugMode = urlState.debug;
                layerVisibility = parseLayerVisibility(urlState.layers);
                focusedZone = urlState.zone;

                if (hasUrlViewState) {
                    currentViewState = {
                        x: urlState.x,
                        y: urlState.y,
                        zoom: urlState.zoom
                    };
                }

                // Restore selection from URL (marker or zone)
                if (urlState.entity && urlState.etype) {
                    const marker = findMarkerByIdAndType(parseInt(urlState.entity), urlState.etype);
                    if (marker) {
                        applySelection(marker, true);
                    }
                } else if (urlState.selectedZone) {
                    const zone = findZoneByKey(urlState.selectedZone);
                    if (zone) {
                        selectZone(zone, true);
                    }
                }

                urlManager.setLastSelection(urlState.entity, urlState.etype, urlState.selectedZone);
            }
        } finally {
            urlManager.exitPassiveMode();
        }

        initializeDeck();

        // Add popstate listener for back/forward navigation
        window.addEventListener('popstate', handlePopstate);

        return () => {
            window.removeEventListener('popstate', handlePopstate);
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

            // Determine initial view state
            let initialX: number;
            let initialY: number;
            let initialZoom: number;

            if (hasUrlViewState) {
                // Use URL-specified view state
                initialX = currentViewState.x;
                initialY = currentViewState.y;
                initialZoom = currentViewState.zoom;
            } else {
                // Fit to world map bounds (show full map)
                // Use backdrop bounds as the authoritative world extent
                const backdropSettings = debugStore.backdrop;
                const backdropWidth = BACKDROP_WIDTH * backdropSettings.scale;
                const backdropHeight = BACKDROP_HEIGHT * backdropSettings.scale;

                const worldBounds = {
                    minX: backdropSettings.x - backdropWidth / 2,
                    maxX: backdropSettings.x + backdropWidth / 2,
                    minY: backdropSettings.y - backdropHeight / 2,
                    maxY: backdropSettings.y + backdropHeight / 2
                };

                initialX = backdropSettings.x;
                initialY = backdropSettings.y;
                initialZoom = calculateFitZoom(
                    worldBounds,
                    container.clientWidth,
                    container.clientHeight,
                    40 // padding
                );

                // Clamp to allowed zoom range
                initialZoom = Math.max(
                    INITIAL_VIEW_STATE.minZoom,
                    Math.min(INITIAL_VIEW_STATE.maxZoom, initialZoom)
                );

                // Update current view state to match
                currentViewState = { x: initialX, y: initialY, zoom: initialZoom };
            }

            // Create layers
            const layers = createLayers(iconAtlas);

            // Initialize deck.gl
            deckInstance = new deckModules.Deck({
                parent: container,
                views: new deckModules.OrthographicView({}),
                initialViewState: {
                    target: [initialX, initialY, 0] as [number, number, number],
                    zoom: initialZoom,
                    minZoom: INITIAL_VIEW_STATE.minZoom,
                    maxZoom: INITIAL_VIEW_STATE.maxZoom
                },
                controller: { inertia: 500 },
                layers,
                getCursor: ({
                    isHovering,
                    isDragging
                }: {
                    isHovering: boolean;
                    isDragging: boolean;
                }) => {
                    if (isDragging) return 'grabbing';
                    if (debugStore.enabled && isHovering) return 'move';
                    return isHovering ? 'pointer' : 'grab';
                },
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

                        // Sync view state to URL (debounced)
                        urlManager.syncViewState(buildUrlParams());
                    }
                },
                onHover: (info: {
                    object?: AnyWorldMarker | ZoneWorldPosition;
                    x: number;
                    y: number;
                }) => {
                    if (info.object) {
                        hoverPosition = { x: info.x, y: info.y };
                        // Check if it's a zone or a marker
                        if ('category' in info.object) {
                            hoveredMarker = info.object as AnyWorldMarker;
                            hoveredZone = null;
                        } else if ('key' in info.object && 'polygon' in info.object) {
                            hoveredZone = info.object as ZoneWorldPosition;
                            hoveredMarker = null;
                        }
                    } else {
                        hoveredMarker = null;
                        hoveredZone = null;
                    }
                },
                onClick: (info: { object?: AnyWorldMarker | ZoneWorldPosition }) => {
                    if (info.object) {
                        // Check if it's a zone (has 'key' and 'polygon') or a marker (has 'category')
                        if ('category' in info.object) {
                            applySelection(info.object as AnyWorldMarker);
                        } else if ('key' in info.object && 'polygon' in info.object) {
                            selectZone(info.object as ZoneWorldPosition);
                        }
                    }
                    // Don't close on click-away - use close button or ESC instead
                },
                onDragStart: handleDragStart,
                onDrag: handleDrag,
                onDragEnd: handleDragEnd
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

        // Use effective zones (with overrides applied)
        const zones = effectiveZones;
        const overrides = debugStore.overrides;
        const draggingZone = debugStore.draggingZone;

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
            const getIconFn =
                typeof iconTypeOrFn === 'function' ? iconTypeOrFn : () => iconTypeOrFn;
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
        if (debugStore.backdrop.enabled) {
            const [bLeft, bBottom, bRight, bTop] = computeBackdropBounds(debugStore.backdrop);
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
                  bounds: computeBackdropBounds(debugStore.backdrop),
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
                d.isEnabled
                    ? [...LAYER_COLORS['zone-line'], 180]
                    : [...LAYER_COLORS['disabled'], 120],
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
                d.isEnabled
                    ? [...LAYER_COLORS['zone-line'], 200]
                    : [...LAYER_COLORS['disabled'], 150],
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

        // Enemy layers (by rarity, with disabled state support)
        const enemiesCommonLayer = createIconLayer(
            'enemies-common',
            data.markers.enemiesCommon,
            getEnemyIconType
        );
        const enemiesRareLayer = createIconLayer(
            'enemies-rare',
            data.markers.enemiesRare,
            getEnemyIconType
        );
        const enemiesUniqueLayer = createIconLayer(
            'enemies-unique',
            data.markers.enemiesUnique,
            getEnemyIconType
        );

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

        // Zone selection highlight (yellow border around selected zone)
        const zoneSelectionLayer = selectedZone
            ? new PolygonLayer({
                  id: 'zone-selection-highlight',
                  data: [selectedZone],
                  getPolygon: (d: ZoneWorldPosition) => d.polygon,
                  getFillColor: HIGHLIGHT_COLORS.primaryFill,
                  getLineColor: HIGHLIGHT_COLORS.primaryRing,
                  getLineWidth: 4,
                  lineWidthUnits: 'pixels',
                  stroked: true,
                  filled: true,
                  pickable: false
              })
            : null;

        // Marker selection highlight (yellow ring around selected marker)
        // Size based on ICON_SIZE with slight reduction to create ring effect
        const highlightSize = {
            base: ICON_SIZE.base * 0.6,
            min: ICON_SIZE.min * 0.65,
            max: ICON_SIZE.max * 0.7
        };
        const markerSelectionLayer = selectedMarker
            ? new ScatterplotLayer({
                  id: 'marker-selection-highlight',
                  data: [selectedMarker],
                  getPosition: (d: AnyWorldMarker) => getMarkerPosition(d),
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
                      getPosition: [overrides]
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
            if (!selectedMarker) return null;
            if (selectedMarker.category !== 'enemy' && selectedMarker.category !== 'npc')
                return null;
            const marker = selectedMarker as WorldEnemy | WorldNpc;
            if (!marker.movement && !marker.worldPatrolWaypoints) return null;
            return {
                position: getMarkerPosition(marker),
                wanderRange: marker.movement?.wanderRange ?? null,
                worldWaypoints: marker.worldPatrolWaypoints,
                loopPatrol: marker.movement?.loopPatrol ?? false
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
                          getPosition: [overrides, selectedMarker]
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
            // Movement visualization (below selection highlight)
            wanderRangeLayer,
            patrolSpawnLineLayer,
            patrolPathLayer,
            patrolWaypointsLayer,
            // Selection highlights (on top of everything)
            zoneSelectionLayer,
            markerSelectionLayer
        ]
            .flat()
            .filter(Boolean);
    }
</script>

<svelte:window onkeydown={handleKeydown} />

<svelte:head>
    <title>World Map | Erenshor Maps</title>
</svelte:head>

<div class="relative h-screen w-full bg-zinc-900">
    <!-- Sidebar -->
    <MapSidebar
        visibility={layerVisibility}
        collapsed={sidebarCollapsed}
        onVisibilityChange={handleLayerVisibilityChange}
        onToggleCollapse={toggleSidebar}
    />

    <!-- Map container -->
    <div bind:this={container} class="absolute inset-0"></div>

    <!-- Loading overlay -->
    {#if isLoading}
        <div
            class="loading-overlay absolute inset-0 z-50 flex items-center justify-center bg-zinc-900"
        >
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

    <!-- Tooltip (desktop only) -->
    {#if hoveredMarker && isDesktop}
        <MapTooltip
            marker={hoveredMarker}
            x={hoverPosition.x}
            y={hoverPosition.y}
            zoneName={getZoneName(hoveredMarker.zone)}
        />
    {:else if hoveredZone && isDesktop}
        <ZoneTooltip zone={hoveredZone} x={hoverPosition.x} y={hoverPosition.y} />
    {/if}

    <!-- Popup (selected marker details) -->
    {#if selectedMarker}
        {@const marker = selectedMarker}
        <MapPopup
            {marker}
            zoneName={selectedMarkerZoneName}
            onClose={closePopup}
            onFocus={() => focusMarker(marker)}
        />
    {/if}

    <!-- Popup (selected zone details) -->
    {#if selectedZone}
        {@const zone = selectedZone}
        <ZonePopup {zone} onClose={closePopup} onFocus={() => focusZone(zone)} />
    {/if}

    <!-- Debug mode panel -->
    {#if debugStore.enabled}
        <div class="fixed right-4 top-4 z-50 rounded-lg bg-zinc-800/95 p-4 shadow-lg">
            <h3 class="mb-3 text-sm font-semibold text-white">Debug Mode</h3>
            <p class="mb-3 text-xs text-zinc-400">
                Shift+drag zones to reposition. Overrides: {Object.keys(debugStore.overrides)
                    .length} zones
            </p>
            {#if debugStore.draggingZone}
                <p class="mb-3 text-xs text-yellow-400">
                    Dragging: {debugStore.draggingZone}
                </p>
            {/if}
            <div class="flex flex-col gap-2">
                <button
                    onclick={handleCopyToClipboard}
                    class="rounded bg-zinc-700 px-3 py-1.5 text-xs text-white transition-colors hover:bg-zinc-600"
                >
                    Copy to Clipboard
                </button>
                <button
                    onclick={handleDownloadJson}
                    class="rounded bg-zinc-700 px-3 py-1.5 text-xs text-white transition-colors hover:bg-zinc-600"
                >
                    Download JSON
                </button>
                <button
                    onclick={handleResetOverrides}
                    class="rounded bg-red-900/50 px-3 py-1.5 text-xs text-red-300 transition-colors hover:bg-red-900/70"
                >
                    Reset All
                </button>
            </div>

            <!-- Backdrop controls -->
            <div class="mt-4 border-t border-zinc-700 pt-3">
                <h4 class="mb-2 text-xs font-semibold text-zinc-300">Backdrop Image</h4>
                <label class="flex items-center gap-2 text-xs text-zinc-400">
                    <input
                        type="checkbox"
                        checked={debugStore.backdrop.enabled}
                        onchange={(e) => {
                            debugStore.setBackdrop({ enabled: e.currentTarget.checked });
                            updateLayers();
                        }}
                    />
                    Show backdrop
                </label>
                {#if debugStore.backdrop.enabled}
                    <div class="mt-2 grid grid-cols-3 gap-2">
                        <label class="text-xs text-zinc-400">
                            X
                            <input
                                type="number"
                                value={debugStore.backdrop.x}
                                onchange={(e) => {
                                    debugStore.setBackdrop({ x: Number(e.currentTarget.value) });
                                    updateLayers();
                                }}
                                class="mt-1 w-full rounded bg-zinc-700 px-2 py-1 text-white"
                            />
                        </label>
                        <label class="text-xs text-zinc-400">
                            Y
                            <input
                                type="number"
                                value={debugStore.backdrop.y}
                                onchange={(e) => {
                                    debugStore.setBackdrop({ y: Number(e.currentTarget.value) });
                                    updateLayers();
                                }}
                                class="mt-1 w-full rounded bg-zinc-700 px-2 py-1 text-white"
                            />
                        </label>
                        <label class="text-xs text-zinc-400">
                            Scale
                            <input
                                type="number"
                                step="0.1"
                                value={debugStore.backdrop.scale}
                                onchange={(e) => {
                                    debugStore.setBackdrop({
                                        scale: Number(e.currentTarget.value)
                                    });
                                    updateLayers();
                                }}
                                class="mt-1 w-full rounded bg-zinc-700 px-2 py-1 text-white"
                            />
                        </label>
                    </div>
                {/if}
            </div>
        </div>
    {/if}
</div>
