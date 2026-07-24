<script lang="ts">
    import { browser } from '$app/environment';
    import Seo from '$lib/components/Seo.svelte';
    import { breadcrumbJsonLd, videoGameJsonLd, webApplicationJsonLd } from '$lib/seo/jsonld';
    import { tick, untrack } from 'svelte';
    import {
        INITIAL_VIEW_STATE,
        ICON_SIZE,
        SIDEBAR_WIDTH
    } from '$lib/map/config';
    import {
        flyTo,
        flyToBounds,
        computeBoundsView,
        computePointView,
        type ComputedView
    } from '$lib/map/flyto';
    import {
        createIconAtlas,
        type IconAtlasResult
    } from '$lib/map/icons';
    import { transformEntityToWorld } from '$lib/map/coordinate-transform';
    import {
        createLayers,
        BACKDROP_WIDTH,
        BACKDROP_HEIGHT,
        type CreateLayersParams
    } from '$lib/map/layers';
    import ScaleBar from '$lib/components/map/ScaleBar.svelte';
    import CoordinateReadout from '$lib/components/map/CoordinateReadout.svelte';
    import { computeScaleBarState, type ScaleBarState } from '$lib/map/scale-bar';
    import {
        findWorldCursorCoordinates,
        type CursorCoordinates
    } from '$lib/map/cursor-coordinates';
    import { liveConnection, liveState, type EntityData } from '$lib/map/live';
    import {
        createDebugStore,
        getEffectiveZones,
        DragController,
        loadOverrides,
        saveOverrides,
        clearOverrides,
        loadBackdropSettings,
        saveBackdropSettings,
        exportToJson,
        copyToClipboard,
        downloadJson,
        type DragInfo
    } from '$lib/map/debug';
    import {
        urlManager,
        parseUrlState,
        parseLayerVisibility,
        getNormalizedSearch,
        type UrlStateParams
    } from '$lib/map/url-state';
    import {
        DEFAULT_LAYER_VISIBILITY,
        type LayerVisibility,
        type AnyWorldMarker,
        type ZoneWorldPosition,
        type WorldEnemy,
        type WorldNpc
    } from '$lib/types/world-map';
    import type { Selection } from '$lib/types/selection';
    import {
        getSelectionPosition,
        getSelectionZone,
        serializeSelection,
        deserializeSelection
    } from '$lib/types/selection';
    import { buildSearchIndex, resolveHighlight, type SearchResult } from '$lib/map/search';
    import * as Drawer from '$lib/components/ui/drawer';
    import MapSidebar from '$lib/components/map/MapSidebar.svelte';
    import MapTooltip from '$lib/components/map/MapTooltip.svelte';
    import MapPopup from '$lib/components/map/MapPopup.svelte';
    import MapSearch from '$lib/components/map/MapSearch.svelte';
    import Eye from '@lucide/svelte/icons/eye';
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

    // Live mode state (persisted to localStorage)
    let liveEnabled = $state(false);
    const LIVE_MODE_KEY = 'erenshor-map-live-mode';

    // Auto-follow state (persisted to localStorage)
    let autoFollowEnabled = $state(false);
    const AUTO_FOLLOW_KEY = 'erenshor-map-auto-follow';

    // Level filter state (enemies only)
    // Use untrack() to explicitly capture initial value without creating reactive dependency
    let levelFilter = $state<[number, number]>(
        untrack(() => [data.levelRange.min, data.levelRange.max])
    );

    // Tooltip state
    let hoveredSelection = $state<Selection>(null);
    let hoverPosition = $state<{ x: number; y: number }>({ x: 0, y: 0 });

    // Selection state (for popups)
    let selection = $state<Selection>(null);

    // Search state
    let searchOpen = $state(false);
    let searchInitialQuery = $state('');
    let searchHighlightPositions = $state<{ position: [number, number]; stableKey: string }[]>([]);
    // Set of hovered spawn point stable keys (brighter rings). Single-key
    // hover (enemy/NPC popups) passes one string; item hover passes multiple.
    let hoveredSpawnKeys = $state<Set<string> | null>(null);

    // Scale bar state
    let scaleBarState = $state<ScaleBarState | null>(null);

    // Cursor coordinate readout state
    let cursorCoordinates = $state<CursorCoordinates | null>(null);

    // Search index (built once from static data)
    const searchIndex = $derived(
        buildSearchIndex({
            enemiesCommon: data.markers.enemiesCommon,
            enemiesRare: data.markers.enemiesRare,
            enemiesUnique: data.markers.enemiesUnique,
            unlocatedEnemies: data.unlocatedEnemies,
            npcs: data.markers.npcs,
            zones: data.zones,
            miningNodes: data.markers.miningNodes,
            water: data.markers.water,
            itemBags: data.markers.itemBags,
            itemSources: data.itemSources,
            allItems: data.allItems
        })
    );

    // Desktop detection (layout, tooltips, drawers)
    let isDesktop = $state(false);
    // Debug hook: exposes internal state for Playwright / devtools inspection.
    // Only active in dev mode (import.meta.env.DEV); zero cost in production.
    $effect(() => {
        if (!browser || !import.meta.env.DEV) return;
        (window as unknown as Record<string, unknown>).__mapDebug = {
            get markers() {
                return data.markers;
            },
            get zones() {
                return data.zones;
            },
            get levelFilter() {
                return levelFilter;
            },
            get levelRange() {
                return data.levelRange;
            },
            get layerVisibility() {
                return layerVisibility;
            },
            get searchHighlightPositions() {
                return searchHighlightPositions;
            },
            get searchIndex() {
                return searchIndex;
            },
            get itemSources() {
                return data.itemSources;
            },
            findEnemy: (name: string) =>
                (
                    [
                        ...data.markers.enemiesCommon,
                        ...data.markers.enemiesRare,
                        ...data.markers.enemiesUnique
                    ] as WorldEnemy[]
                ).filter((m) => m.characters.some((c) => c.name === name)),
            findNpc: (name: string) =>
                (data.markers.npcs as WorldNpc[]).filter((m) =>
                    m.characters.some((c) => c.name === name)
                )
        };
    });

    $effect(() => {
        if (!browser) return;
        const mediaQuery = window.matchMedia('(min-width: 768px)');
        isDesktop = mediaQuery.matches;
        const handler = (e: MediaQueryListEvent) => (isDesktop = e.matches);
        mediaQuery.addEventListener('change', handler);
        return () => mediaQuery.removeEventListener('change', handler);
    });


    // Mobile popup drawer state (separate from selection so drawer can be
    // dismissed without clearing selection — highlights stay on the map)
    let mobilePopupOpen = $state(false);

    // Get zone display name from zone key
    function getZoneName(zoneKey: string): string {
        const zone = data.zones.find((z) => z.key === zoneKey);
        return zone?.name ?? zoneKey;
    }

    // Find marker by coordinateId and category
    function findMarkerByStableKey(stableKey: string): AnyWorldMarker | null {
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
        return allMarkers.find((m) => m.stableKey === stableKey) ?? null;
    }

    // Find zone by key
    function findZoneByKey(key: string): ZoneWorldPosition | null {
        return data.zones.find((z) => z.key === key) ?? null;
    }

    /**
     * Build complete URL params from current state.
     * Called by all URL sync operations.
     */
    function buildUrlParams(): UrlStateParams {
        return {
            viewState: currentViewState,
            layers: layerVisibility,
            sel: serializeSelection(selection),
            focusedZoneId: focusedZone,
            debug: isDebugMode,
            levelFilter,
            levelRange: data.levelRange
        };
    }

    /** In-flight highlight resolution promise (for awaiting by callers) */
    let highlightReady: Promise<void> = Promise.resolve();

    /**
     * Apply selection state. Single point for all selection changes.
     * @param newSelection - Selection to apply, or null to clear
     * @param skipUrlUpdate - True when restoring from URL
     */
    function applySelection(newSelection: Selection, skipUrlUpdate = false): void {
        selection = newSelection;
        hoveredSpawnKeys = null;

        // Resolve search highlights
        if (newSelection?.type === 'search') {
            highlightReady = resolveAndApplyHighlight(newSelection.result);
        } else {
            searchHighlightPositions = [];
            highlightReady = Promise.resolve();
        }

        // Auto-open/close mobile popup drawer
        if (!isDesktop) {
            mobilePopupOpen = newSelection !== null;
        }

        if (!skipUrlUpdate) {
            urlManager.pushSelection(buildUrlParams());
        }
        updateLayers();
    }

    /**
     * Resolve a search result to map highlight positions.
     */
    async function resolveAndApplyHighlight(result: SearchResult): Promise<void> {
        const highlight = await resolveHighlight(result, searchIndex);
        if (highlight.type === 'positions') {
            searchHighlightPositions = highlight.positions.map((pos, i) => ({
                position: pos,
                stableKey: highlight.stableKeys[i]
            }));
        } else {
            searchHighlightPositions = [];
        }
        updateLayers();
    }

    /**
     * Close popup.
     */
    function closeSelection(): void {
        applySelection(null);
    }

    /**
     * Handle search result selection from command palette.
     * Zone results become zone selections; enemy/npc become search selections.
     */
    async function handleSearchSelect(result: SearchResult): Promise<void> {
        if (result.type === 'zone') {
            const zone = findZoneByKey(result.key);
            if (zone) {
                applySelection({ type: 'zone', zone });
                focusSelection({ type: 'zone', zone });
            }
        } else {
            applySelection({ type: 'search', result });
            // Wait for highlights to resolve before flying.
            // On desktop, pass POPUP_WIDTH explicitly since the popup just opened
            // but flyPadding.right hasn't updated yet in the current tick.
            // On mobile, popup is a drawer overlay so no right padding needed.
            await highlightReady;
            handleFocusAll(isDesktop ? POPUP_WIDTH : 0);
        }
    }

    /**
     * Handle live entity selection from the search command palette.
     * Selects the live marker directly and flies to it — same as clicking the marker.
     */
    function handleLiveSearchSelect(entity: EntityData, zone: string): void {
        const sel: Selection = { type: 'live', entity, zone };
        applySelection(sel);
        focusSelection(sel);
    }

    /**
     * Close the popup and open search with a pre-filled query.
     * Used by the "not found" popup to let users search for alternatives.
     */
    function handleSearchAlternative(query: string): void {
        closeSelection();
        searchInitialQuery = query;
        searchOpen = true;
    }

    /**
     * Hover spawn point(s) in a search popup. Accepts a single stable key
     * (enemy/NPC popups) or multiple (item popup narrows to a dropper's
     * spawns). Null clears the hover.
     */
    function handleHoverSpawn(stableKey: string | string[] | null): void {
        if (stableKey === null) {
            hoveredSpawnKeys = null;
        } else if (Array.isArray(stableKey)) {
            hoveredSpawnKeys = new Set(stableKey);
        } else {
            hoveredSpawnKeys = new Set([stableKey]);
        }
        updateLayers();
    }

    /**
     * Focus (fly to) a specific spawn point from the search popup.
     */
    function handleFocusSpawn(stableKey: string): void {
        const marker = findMarkerByStableKey(stableKey);
        if (!marker) return;
        const position = getSelectionPosition(
            { type: 'marker', marker },
            data.zones,
            data.zoneConfigs,
            debugStore.overrides,
            liveState.entities
        );
        if (position) {
            flyTo(deckInstance, position[0], position[1], {
                zoom: 0,
                rightPadding: flyPadding.right
            });
        }
    }

    function handleSelectSpawn(stableKey: string): void {
        const marker = findMarkerByStableKey(stableKey);
        if (!marker || (marker.category !== 'enemy' && marker.category !== 'npc')) return;
        applySelection({ type: 'marker', marker });
    }

    /**
     * Focus all spawn points — fit bounds around all search highlight positions.
     * Accepts optional padding override for when the popup is about to open
     * but flyPadding hasn't updated yet.
     */
    function handleFocusAll(rightPaddingOverride?: number): void {
        if (searchHighlightPositions.length === 0) return;

        const positions = searchHighlightPositions.map((p) => p.position);
        let minX = Infinity,
            minY = Infinity,
            maxX = -Infinity,
            maxY = -Infinity;
        for (const [x, y] of positions) {
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x);
            maxY = Math.max(maxY, y);
        }
        flyToBounds(
            deckInstance,
            { minX, minY, maxX, maxY },
            {
                leftPadding: flyPadding.left,
                rightPadding: rightPaddingOverride ?? flyPadding.right
            }
        );
    }

    // Focus on selection (fly to position or bounds)
    function focusSelection(sel: Selection): void {
        if (!sel) return;

        if (sel.type === 'zone') {
            flyToBounds(deckInstance, sel.zone.bounds, {
                leftPadding: flyPadding.left,
                rightPadding: flyPadding.right
            });
        } else if (sel.type === 'search') {
            handleFocusAll();
        } else {
            const position = getSelectionPosition(
                sel,
                data.zones,
                data.zoneConfigs,
                debugStore.overrides,
                liveState.entities
            );
            if (position) {
                flyTo(deckInstance, position[0], position[1], {
                    zoom: 0,
                    rightPadding: flyPadding.right
                });
            }
        }
    }

    /**
     * Compute the initial view for a URL-restored selection.
     * Returns null if there's no selection or no valid position,
     * in which case the caller should fall back to the world overview.
     */
    function computeInitialSelectionView(
        viewportWidth: number,
        viewportHeight: number,
        sidebarWidth: number
    ): ComputedView | null {
        if (!selection) return null;

        // Not-found selections have no position to fly to
        if (selection.type === 'search-not-found') return null;

        if (selection.type === 'search' && searchHighlightPositions.length > 0) {
            const positions = searchHighlightPositions.map((p) => p.position);
            let minX = Infinity,
                minY = Infinity,
                maxX = -Infinity,
                maxY = -Infinity;
            for (const [x, y] of positions) {
                minX = Math.min(minX, x);
                minY = Math.min(minY, y);
                maxX = Math.max(maxX, x);
                maxY = Math.max(maxY, y);
            }
            return computeBoundsView({ minX, minY, maxX, maxY }, viewportWidth, viewportHeight, {
                leftPadding: sidebarWidth,
                rightPadding: POPUP_WIDTH
            });
        }

        if (selection.type === 'zone') {
            return computeBoundsView(selection.zone.bounds, viewportWidth, viewportHeight, {
                leftPadding: sidebarWidth,
                rightPadding: POPUP_WIDTH
            });
        }

        if (selection.type === 'marker') {
            const position = getSelectionPosition(
                selection,
                data.zones,
                data.zoneConfigs,
                debugStore.overrides,
                liveState.entities
            );
            if (position) {
                return computePointView(position[0], position[1], {
                    zoom: 0,
                    rightPadding: POPUP_WIDTH
                });
            }
        }

        return null;
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

    // Load live mode state from localStorage
    $effect(() => {
        if (browser) {
            const stored = localStorage.getItem(LIVE_MODE_KEY);
            if (stored !== null) {
                liveEnabled = stored === 'true';
            }
        }
    });

    // Load auto-follow state from localStorage
    $effect(() => {
        if (browser) {
            const stored = localStorage.getItem(AUTO_FOLLOW_KEY);
            if (stored !== null) {
                autoFollowEnabled = stored === 'true';
            }
        }
    });

    // Connect/disconnect live mode based on toggle
    $effect(() => {
        if (liveEnabled) {
            liveConnection.connect();
        } else {
            liveConnection.disconnect();
        }
    });

    /**
     * Update camera to center on target coordinates with instant transition.
     * Used for auto-follow tracking and re-centering after sidebar toggle.
     */
    function updateCameraTarget(targetX: number, targetY: number) {
        if (!deckInstance) return;

        deckInstance.setProps({
            initialViewState: {
                target: [targetX, targetY, 0],
                zoom: currentViewState.zoom,
                minZoom: INITIAL_VIEW_STATE.minZoom,
                maxZoom: INITIAL_VIEW_STATE.maxZoom,
                transitionDuration: 0
            }
        });
    }

    /**
     * Update camera position to instantly follow player (lock-on mode).
     * Called from layer update effect at 10 Hz (every 100ms).
     */
    function updateAutoFollow() {
        if (!autoFollowEnabled || !liveState.player || !liveState.zone) return;
        if (!deckInstance || !browser) return;

        const playerPos = transformEntityToWorld(
            { ...liveState.player, zone: liveState.zone },
            data.zones,
            data.zoneConfigs,
            debugStore.overrides
        );

        // Skip if in unmapped zone, but keep auto-follow enabled
        if (!playerPos) return;

        updateCameraTarget(playerPos[0], playerPos[1]);
    }

    // Watch for live state changes and update layers
    $effect(() => {
        // Access reactive properties to track dependencies (mark as used with void)
        void liveState.entities;
        void liveState.connectionState;
        void liveState.zone;
        void liveState.lastUpdate;

        // Trigger layer update when live state changes
        if (browser && deckInstance) {
            updateLayers();
            updateAutoFollow();
        }
    });

    // Popup sidebar width (matches PopupContainer w-80 = 320px)
    const POPUP_WIDTH = 320;
    const MAP_CHROME_GAP = 16;
    const SCALE_BAR_GAP = 24;
    const SCALE_BAR_BOTTOM = 22;
    const SCALE_BAR_MAX_WIDTH = 120;
    const KOFI_URL = 'https://ko-fi.com/wowmuch';

    const kofiButtonRight = $derived(
        isDesktop && selection ? `${POPUP_WIDTH + MAP_CHROME_GAP}px` : `${MAP_CHROME_GAP}px`
    );

    const scaleBarLeftPx = $derived(
        isDesktop
            ? (sidebarCollapsed ? SIDEBAR_WIDTH.collapsed : SIDEBAR_WIDTH.expanded) + SCALE_BAR_GAP
            : SCALE_BAR_GAP
    );

    function updateScaleBar(retries = 0) {
        if (!container || !deckInstance) {
            scaleBarState = null;
            return;
        }

        const viewport = deckInstance.getViewports?.()[0];
        if (!viewport?.unproject) {
            scaleBarState = null;
            if (retries > 0) {
                scheduleScaleBarUpdate(retries - 1);
            }
            return;
        }

        const sampleY = container.clientHeight - SCALE_BAR_BOTTOM - 8;
        const left = scaleBarLeftPx;
        const right = left + SCALE_BAR_MAX_WIDTH;

        const from = viewport.unproject([left, sampleY]);
        const to = viewport.unproject([right, sampleY]);
        const measuredUnits = Math.hypot(to[0] - from[0], to[1] - from[1]);

        const nextState = computeScaleBarState({
            measuredUnits,
            maxWidthPx: SCALE_BAR_MAX_WIDTH
        });
        scaleBarState = nextState;
        if (nextState == null && retries > 0) {
            scheduleScaleBarUpdate(retries - 1);
        }
    }

    function scheduleScaleBarUpdate(retries = 6) {
        if (!browser) {
            updateScaleBar();
            return;
        }
        requestAnimationFrame(() => updateScaleBar(retries));
    }

    function updateWorldCursorCoordinates(screenX: number, screenY: number) {
        const viewport = deckInstance?.getViewports?.()[0];
        if (!viewport?.unproject) {
            cursorCoordinates = null;
            return;
        }

        const [worldX, worldY] = viewport.unproject([
            screenX - (viewport.x ?? 0),
            screenY - (viewport.y ?? 0)
        ]);
        cursorCoordinates = findWorldCursorCoordinates(
            [worldX, worldY],
            effectiveZones,
            data.zoneConfigs
        );
    }

    function handleWorldPointerMove(event: PointerEvent) {
        const rect = container.getBoundingClientRect();
        updateWorldCursorCoordinates(event.clientX - rect.left, event.clientY - rect.top);
    }

    function handleWorldPointerLeave() {
        cursorCoordinates = null;
        hoveredSelection = null;
    }

    // Padding for flyTo/flyToBounds — accounts for obscured areas.
    // On mobile, sidebar and popup are drawers/overlays, so no padding needed.
    const flyPadding = $derived(
        isDesktop
            ? {
                  left: sidebarCollapsed ? SIDEBAR_WIDTH.collapsed : SIDEBAR_WIDTH.expanded,
                  right: selection !== null ? POPUP_WIDTH : 0
              }
            : { left: 0, right: 0 }
    );

    // Update deck.gl view padding when sidebar toggles or screen size changes
    $effect(() => {
        // IMPORTANT: Access sidebarCollapsed and isDesktop outside the guard to
        // ensure Svelte 5 tracks them as dependencies.
        const collapsed = sidebarCollapsed;
        const desktop = isDesktop;

        if (!deckInstance || !deckModules) return;

        // On mobile, sidebar is a drawer overlay — no persistent view padding.
        // On desktop, left sidebar uses persistent view padding (always visible).
        // Right popup is just an overlay — flyTo/flyToBounds account for it
        // per-operation to avoid shifting the viewport center on open/close.
        const leftPadding = desktop
            ? collapsed
                ? SIDEBAR_WIDTH.collapsed
                : SIDEBAR_WIDTH.expanded
            : 0;
        deckInstance.setProps({
            views: new deckModules.OrthographicView({
                padding: {
                    left: leftPadding,
                    right: 0,
                    top: 0,
                    bottom: 0
                }
            })
        });

        // Re-center camera if auto-follow is active
        if (autoFollowEnabled && liveState.player && liveState.zone) {
            const playerPos = transformEntityToWorld(
                { ...liveState.player, zone: liveState.zone },
                data.zones,
                data.zoneConfigs,
                debugStore.overrides
            );

            if (playerPos) {
                updateCameraTarget(playerPos[0], playerPos[1]);
            }
        }
        scheduleScaleBarUpdate();
    });

    $effect(() => {
        const left = scaleBarLeftPx;
        void left;

        if (!browser) return;

        scheduleScaleBarUpdate();

        const handleResize = () => scheduleScaleBarUpdate();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
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

    function handleLevelFilterChange(newFilter: [number, number]) {
        levelFilter = newFilter;
        urlManager.syncPreferences(buildUrlParams());
        updateLayers();
    }

    function handleLiveModeChange(enabled: boolean) {
        liveEnabled = enabled;
        if (browser) {
            localStorage.setItem(LIVE_MODE_KEY, String(enabled));
        }
    }

    function handleAutoFollowChange(enabled: boolean) {
        autoFollowEnabled = enabled;
        if (browser) {
            localStorage.setItem(AUTO_FOLLOW_KEY, String(enabled));
        }
    }

    // Keyboard shortcuts
    function handleKeydown(event: KeyboardEvent) {
        // Ctrl/Cmd+K opens search (always, even in inputs)
        if (event.key === 'k' && (event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            searchOpen = true;
            return;
        }

        // ESC closes search first, then popup
        if (event.key === 'Escape') {
            if (searchOpen) {
                searchOpen = false;
                return;
            }
            if (selection) {
                closeSelection();
                return;
            }
        }

        // Ignore if typing in an input
        if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) {
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

                // Restore level filter
                if (urlState.levelFilter) {
                    levelFilter = urlState.levelFilter;
                } else {
                    levelFilter = [data.levelRange.min, data.levelRange.max];
                }

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

                // Restore selection from unified `sel` param
                if (urlState.sel) {
                    const restored = deserializeSelection(urlState.sel, {
                        findMarkerByStableKey,
                        findZoneByKey,
                        searchIndex
                    });
                    applySelection(restored, true);
                } else {
                    applySelection(null, true);
                }

                urlManager.setLastSel(urlState.sel);
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
    const SPAWN_MARKER_LAYER_IDS = ['enemies-common', 'enemies-rare', 'enemies-unique', 'npcs'];

    function isSpawnMarker(object: unknown): object is WorldEnemy | WorldNpc {
        if (!object || typeof object !== 'object') return false;
        const category = (object as { category?: unknown }).category;
        return category === 'enemy' || category === 'npc';
    }

    function getPickedSpawnMarkers(info: {
        x: number;
        y: number;
    }): (WorldEnemy | WorldNpc)[] {
        if (!deckInstance?.pickMultipleObjects) return [];
        const picked = deckInstance.pickMultipleObjects({
            x: info.x,
            y: info.y,
            radius: Math.max(2, ICON_SIZE.base / 2),
            depth: 20,
            layerIds: SPAWN_MARKER_LAYER_IDS
        }) as Array<{ object?: unknown }>;
        const markers = picked
            .map((pick) => pick.object)
            .filter(isSpawnMarker);
        const unique = new Map(markers.map((marker) => [marker.stableKey, marker]));
        return [...unique.values()].sort((a, b) => {
            const aName = a.characters.map((character) => character.name).join(', ');
            const bName = b.characters.map((character) => character.name).join(', ');
            return `${a.category}:${aName}:${a.stableKey}`.localeCompare(
                `${b.category}:${bName}:${b.stableKey}`
            );
        });
    }
    /**
     * Assemble the pure-layer-builder inputs from current route state.
     * Snapshots reactive Svelte state, deck constructors, and the live store
     * into the explicit contract consumed by `createLayers`.
     */
    function buildLayerParams(atlas: IconAtlasResult): CreateLayersParams {
        return {
            atlas,
            modules: deckModules,
            data: {
                markers: data.markers,
                zones: data.zones,
                zoneConfigs: data.zoneConfigs
            },
            effectiveZones,
            overrides: debugStore.overrides,
            draggingZone: debugStore.draggingZone,
            backdrop: debugStore.backdrop,
            layerVisibility,
            levelFilter,
            selection,
            searchHighlightPositions,
            hoveredSpawnKeys,
            live: {
                connectionState: liveState.connectionState,
                zone: liveState.zone,
                entities: liveState.entities
            }
        };
    }

    function updateLayers() {
        if (deckInstance && iconAtlas && deckModules) {
            const layers = createLayers(buildLayerParams(iconAtlas));
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

    // Initialize deck.gl when component mounts
    $effect(() => {
        if (!browser || !container) return;

        // Check if URL has explicit view state params
        // Use getNormalizedSearch to fix HTML-encoded ampersands from forum posts
        const params = new URLSearchParams(getNormalizedSearch());
        hasUrlViewState = params.has('x') || params.has('y') || params.has('z');

        // Parse initial URL state (passive mode is handled in restoreFromUrl)
        urlManager.enterPassiveMode();
        try {
            const urlState = parseUrlState();

            if (urlState) {
                isDebugMode = urlState.debug;
                layerVisibility = parseLayerVisibility(urlState.layers);
                focusedZone = urlState.zone;

                // Restore level filter
                if (urlState.levelFilter) {
                    levelFilter = urlState.levelFilter;
                }

                if (hasUrlViewState) {
                    currentViewState = {
                        x: urlState.x,
                        y: urlState.y,
                        zoom: urlState.zoom
                    };
                }

                // Restore selection from unified `sel` param
                if (urlState.sel) {
                    const restored = deserializeSelection(urlState.sel, {
                        findMarkerByStableKey,
                        findZoneByKey,
                        searchIndex
                    });
                    applySelection(restored, true);
                }

                urlManager.setLastSel(urlState.sel);
            }
        } finally {
            urlManager.exitPassiveMode();
        }

        initializeDeck();

        // Add popstate listener for back/forward navigation
        window.addEventListener('popstate', handlePopstate);

        return () => {
            window.removeEventListener('popstate', handlePopstate);
            container?.removeEventListener('pointermove', handleWorldPointerMove, true);
            container?.removeEventListener('pointerleave', handleWorldPointerLeave, true);
            if (deckInstance) {
                deckInstance.finalize();
                deckInstance = null;
            }
        };
    });

    async function initializeDeck() {
        try {
            // Dynamic imports for deck.gl (SSR safety)
            const [deckCore, deckLayers, deckGeoLayers, deckExtensions] = await Promise.all([
                import('@deck.gl/core'),
                import('@deck.gl/layers'),
                import('@deck.gl/geo-layers'),
                import('@deck.gl/extensions')
            ]);

            const { Deck, OrthographicView } = deckCore;
            const { IconLayer, PolygonLayer, TextLayer, BitmapLayer, LineLayer, ScatterplotLayer } =
                deckLayers;
            const { DataFilterExtension } = deckExtensions;
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
                Tileset2D,
                DataFilterExtension
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
                // No explicit view coordinates — compute initial view from
                // the restored selection, or fall back to full world map.
                const sidebarWidth = isDesktop
                    ? sidebarCollapsed
                        ? SIDEBAR_WIDTH.collapsed
                        : SIDEBAR_WIDTH.expanded
                    : 0;
                const selectionView = computeInitialSelectionView(
                    container.clientWidth,
                    container.clientHeight,
                    sidebarWidth
                );

                if (selectionView) {
                    initialX = selectionView.x;
                    initialY = selectionView.y;
                    initialZoom = selectionView.zoom;
                } else {
                    // No selection — fit to world map bounds
                    const backdropSettings = debugStore.backdrop;
                    const backdropWidth = BACKDROP_WIDTH * backdropSettings.scale;
                    const backdropHeight = BACKDROP_HEIGHT * backdropSettings.scale;
                    const view = computeBoundsView(
                        {
                            minX: backdropSettings.x - backdropWidth / 2,
                            maxX: backdropSettings.x + backdropWidth / 2,
                            minY: backdropSettings.y - backdropHeight / 2,
                            maxY: backdropSettings.y + backdropHeight / 2
                        },
                        container.clientWidth,
                        container.clientHeight,
                        { leftPadding: sidebarWidth }
                    );
                    initialX = view.x;
                    initialY = view.y;
                    initialZoom = view.zoom;
                }

                currentViewState = { x: initialX, y: initialY, zoom: initialZoom };
            }

            // Create layers
            const layers = createLayers(buildLayerParams(iconAtlas));

            // Initialize deck.gl
            deckInstance = new deckModules.Deck({
                parent: container,
                views: new deckModules.OrthographicView({
                    padding: {
                        left: isDesktop
                            ? sidebarCollapsed
                                ? SIDEBAR_WIDTH.collapsed
                                : SIDEBAR_WIDTH.expanded
                            : 0,
                        right: 0,
                        top: 0,
                        bottom: 0
                    }
                }),
                initialViewState: {
                    target: [initialX, initialY, 0] as [number, number, number],
                    zoom: initialZoom,
                    minZoom: INITIAL_VIEW_STATE.minZoom,
                    maxZoom: INITIAL_VIEW_STATE.maxZoom
                },
                controller: { inertia: 500 },
                layers,
                onAfterRender: () => scheduleScaleBarUpdate(0),
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
                    viewState,
                    interactionState
                }: {
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    viewState: any;
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    interactionState?: any;
                }) => {
                    // If user manually panned/zoomed, disable auto-follow
                    if (autoFollowEnabled && interactionState?.isPanning) {
                        autoFollowEnabled = false;
                        if (browser) {
                            localStorage.setItem(AUTO_FOLLOW_KEY, 'false');
                        }
                    }

                    if (viewState.target) {
                        currentViewState = {
                            x: viewState.target[0],
                            y: viewState.target[1],
                            zoom: viewState.zoom
                        };

                        // Sync view state to URL (debounced)
                        urlManager.syncViewState(buildUrlParams());
                        scheduleScaleBarUpdate();
                    }
                },
                onHover: (info: {
                    object?: AnyWorldMarker | ZoneWorldPosition | EntityData;
                    x: number;
                    y: number;
                }) => {
                    hoverPosition = { x: info.x, y: info.y };
                    if (!info.object) {
                        hoveredSelection = null;
                        return;
                    }

                    // Type discrimination: create Selection from info.object
                    if ('category' in info.object) {
                        // Static marker
                        hoveredSelection = {
                            type: 'marker',
                            marker: info.object as AnyWorldMarker
                        };
                    } else if ('id' in info.object && 'entityType' in info.object) {
                        // Live entity (has unique id + entityType)
                        const entity = info.object as EntityData;
                        hoveredSelection = { type: 'live', entity, zone: liveState.zone ?? '' };
                    } else if ('key' in info.object && 'polygon' in info.object) {
                        // Zone
                        hoveredSelection = {
                            type: 'zone',
                            zone: info.object as ZoneWorldPosition
                        };
                    }
                },
                onClick: (info: {
                    object?: AnyWorldMarker | ZoneWorldPosition | EntityData;
                    x: number;
                    y: number;
                }) => {
                    if (info.object) {
                        // Type discrimination: create Selection from info.object
                        if ('category' in info.object) {
                            // Static marker
                            const spawnMarkers =
                                info.object.category === 'enemy' || info.object.category === 'npc'
                                    ? getPickedSpawnMarkers(info)
                                    : [];
                            if (spawnMarkers.length > 1) {
                                applySelection({ type: 'marker-group', markers: spawnMarkers });
                                return;
                            }
                            applySelection({
                                type: 'marker',
                                marker: info.object as AnyWorldMarker
                            });
                        } else if ('id' in info.object && 'entityType' in info.object) {
                            // Live entity
                            const entity = info.object as EntityData;
                            applySelection({ type: 'live', entity, zone: liveState.zone ?? '' });
                            // Note: Auto-follow remains enabled when clicking entities
                        } else if ('key' in info.object && 'polygon' in info.object) {
                            // Zone
                            applySelection({
                                type: 'zone',
                                zone: info.object as ZoneWorldPosition
                            });
                        }
                    }
                    // Don't close on click-away - use close button or ESC instead
                },
                onDragStart: handleDragStart,
                onDrag: handleDrag,
                onDragEnd: handleDragEnd
            });

            scheduleScaleBarUpdate();
            container.addEventListener('pointermove', handleWorldPointerMove, { capture: true });
            container.addEventListener('pointerleave', handleWorldPointerLeave, { capture: true });

            isLoading = false;
        } catch (err) {
            console.error('Failed to initialize deck.gl:', err);
            loadError = err instanceof Error ? err.message : 'Failed to load map';
            isLoading = false;
        }
    }

</script>

<svelte:window onkeydown={handleKeydown} />

<Seo
    path="/map"
    title="Erenshor Interactive Map – Spawns & Item Sources"
    description="Find any enemy, NPC, or item on Erenshor's full world map — spawns, drop and vendor sources, and resource nodes. Filter by level and track your character live."
    jsonLd={[
        webApplicationJsonLd(),
        videoGameJsonLd(),
        breadcrumbJsonLd([
            { name: 'Home', path: '/' },
            { name: 'World Map', path: '/map' }
        ])
    ]}
/>

<div class="relative h-screen w-full bg-zinc-900">
    <h1 class="sr-only">Erenshor Interactive World Map</h1>
    <!-- Sidebar -->
    <MapSidebar
        visibility={layerVisibility}
        collapsed={sidebarCollapsed}
        {isDesktop}
        onVisibilityChange={handleLayerVisibilityChange}
        onToggleCollapse={toggleSidebar}
        levelRange={data.levelRange}
        {levelFilter}
        onLevelFilterChange={handleLevelFilterChange}
        {liveEnabled}
        connectionState={liveState.connectionState}
        onLiveModeChange={handleLiveModeChange}
        {autoFollowEnabled}
        onAutoFollowChange={handleAutoFollowChange}
        onSearchOpen={() => (searchOpen = true)}
    />

    <!-- Map container -->
    <div bind:this={container} class="absolute inset-0"></div>

    <CoordinateReadout coordinates={cursorCoordinates} leftPx={scaleBarLeftPx} />
    <ScaleBar state={scaleBarState} leftPx={scaleBarLeftPx} />

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

    {#if !debugStore.enabled}
        <a
            href={KOFI_URL}
            aria-label="Support on Ko-fi"
            title="Support on Ko-fi"
            style:right={kofiButtonRight}
            class="fixed top-4 z-30 flex h-12 w-12 cursor-pointer items-center justify-center rounded-full
                   bg-zinc-800/95 shadow-lg backdrop-blur text-pink-300 transition-all
                   hover:bg-zinc-700/95 hover:text-pink-100"
        >
            <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
                class="h-6 w-6 translate-x-px"
                aria-hidden="true"
            >
                <path
                    d="M23.881 8.948c-.773-4.085-4.859-4.593-4.859-4.593H.723c-.604 0-.679.798-.679.798s-.082 7.324-.022 11.822c.164 2.424 2.586 2.672 2.586 2.672s8.267-.023 11.966-.049c2.438-.426 2.683-2.566 2.658-3.734 4.352.24 7.422-2.831 6.649-6.916zm-11.062 3.511c-1.246 1.453-4.011 3.976-4.011 3.976s-.121.119-.31.023c-.076-.057-.108-.09-.108-.09-.443-.441-3.368-3.049-4.034-3.954-.709-.965-1.041-2.7-.091-3.71.951-1.01 3.005-1.086 4.363.407 0 0 1.565-1.782 3.468-.963 1.904.82 1.832 3.011.723 4.311zm6.173.478c-.928.116-1.682.028-1.682.028V7.284h1.77s1.971.551 1.971 2.638c0 1.913-.985 2.667-2.059 3.015z"
                />
            </svg>
        </a>
    {/if}

    <!-- Tooltip (desktop only) -->
    {#if hoveredSelection && isDesktop}
        {@const zoneKey = getSelectionZone(hoveredSelection)}
        {@const zoneName = zoneKey ? getZoneName(zoneKey) : 'Unknown'}
        <MapTooltip
            selection={hoveredSelection}
            x={hoverPosition.x}
            y={hoverPosition.y}
            {zoneName}
        />
    {/if}

    <!-- Popup (selected marker, live entity, zone, or search result) -->
    {#if selection}
        {@const zoneKey = getSelectionZone(selection)}
        {@const zoneName = zoneKey ? getZoneName(zoneKey) : 'Unknown'}
        {#if isDesktop}
            <MapPopup
                {selection}
                {zoneName}
                {searchIndex}
                onClose={closeSelection}
                onFocus={() => focusSelection(selection)}
                onHoverSpawn={handleHoverSpawn}
                onFocusSpawn={handleFocusSpawn}
                onSelectSpawn={handleSelectSpawn}
                onFocusAll={handleFocusAll}
                onSearchAlternative={handleSearchAlternative}
            />
        {:else}
            <Drawer.Root bind:open={mobilePopupOpen} shouldScaleBackground={false}>
                <Drawer.Content>
                    <Drawer.Header class="sr-only">
                        <Drawer.Title>Details</Drawer.Title>
                    </Drawer.Header>
                    <div class="overflow-y-auto pb-4">
                        <MapPopup
                            {selection}
                            {zoneName}
                            {searchIndex}
                            mode="drawer"
                            onClose={() => {
                                mobilePopupOpen = false;
                                closeSelection();
                            }}
                            onFocus={() => {
                                mobilePopupOpen = false;
                                focusSelection(selection);
                            }}
                            onHoverSpawn={handleHoverSpawn}
                            onFocusSpawn={handleFocusSpawn}
                            onSelectSpawn={handleSelectSpawn}
                            onFocusAll={handleFocusAll}
                            onSearchAlternative={(query) => {
                                mobilePopupOpen = false;
                                handleSearchAlternative(query);
                            }}
                        />
                    </div>
                </Drawer.Content>
            </Drawer.Root>
        {/if}
    {/if}

    <!-- Mobile: floating button to reopen popup when drawer was dismissed -->
    {#if !isDesktop && selection && !mobilePopupOpen}
        <button
            type="button"
            onclick={() => (mobilePopupOpen = true)}
            class="fixed bottom-4 right-4 z-20 flex h-12 w-12 cursor-pointer items-center
                   justify-center rounded-full bg-zinc-800/95 shadow-lg backdrop-blur
                   text-zinc-300 hover:text-white transition-colors"
            title="Show details"
        >
            <Eye class="h-5 w-5" />
        </button>
    {/if}

    <!-- Search command palette -->
    <MapSearch
        bind:open={searchOpen}
        {isDesktop}
        bind:initialQuery={searchInitialQuery}
        index={searchIndex.entries}
        liveEntities={liveState.entities}
        liveZone={liveState.zone}
        onselect={handleSearchSelect}
        onliveselect={handleLiveSearchSelect}
        onclose={() => {}}
    />

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
