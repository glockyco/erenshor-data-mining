/**
 * URL state management for shareable map links.
 *
 * Uses explicit urlManager object pattern with:
 * - pushSelection() - adds to browser history (back/forward works)
 * - syncViewState() - debounced replace (no history spam during pan/zoom)
 * - syncPreferences() - immediate replace for layers/zone focus
 * - Passive mode - prevents URL updates during popstate restoration
 *
 * Key pattern: All sync methods take COMPLETE UrlStateParams (no optionals).
 * This eliminates merging bugs - the caller is responsible for providing full state.
 */

import { browser } from '$app/environment';
import { pushState, replaceState } from '$app/navigation';
import { DEFAULT_LAYER_VISIBILITY, type LayerVisibility } from '$lib/types/world-map';

// ============================================================================
// Types
// ============================================================================

/**
 * Selection state for URL tracking and deduplication.
 */
export interface SelectionState {
    entityId: string | null;
    entityType: string | null;
}

/**
 * Complete state needed to build a URL.
 * All fields required - no optionals, no partial updates.
 */
export interface UrlStateParams {
    viewState: { x: number; y: number; zoom: number };
    layers: LayerVisibility;
    entityId: string | null;
    entityType: string | null;
    focusedZoneId: string | null;
    debug: boolean;
}

/**
 * Parsed URL state (what we read FROM the URL).
 */
export interface ParsedUrlState {
    x: number;
    y: number;
    zoom: number;
    layers: string | null;
    entity: string | null;
    etype: string | null;
    zone: string | null;
    debug: boolean;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_X = 0;
const DEFAULT_Y = 0;
const DEFAULT_ZOOM = -2;
const VIEW_SYNC_DEBOUNCE_MS = 150;

// ============================================================================
// Module State
// ============================================================================

let lastSelection: SelectionState = { entityId: null, entityType: null };
let isPassiveMode = false;
let viewSyncTimer: ReturnType<typeof setTimeout> | null = null;

// ============================================================================
// Layer Serialization
// ============================================================================

/**
 * Layer key mappings for URL serialization.
 * Short keys for compact URLs.
 */
const LAYER_KEYS: Record<keyof LayerVisibility, string> = {
    // Terrain
    tiles: 'tile',
    worldMap: 'wm',
    zoneBounds: 'zb',
    zoneLabels: 'zlbl',
    // Enemies
    spawnPoints: 'sp',
    spawnPointsRare: 'spr',
    spawnPointsUnique: 'spu',
    // NPCs
    characters: 'npc',
    // Zone connections
    zoneLines: 'zl',
    teleports: 'tp',
    // Utilities
    forges: 'forge',
    wishingWells: 'well',
    // Resources
    miningNodes: 'mine',
    water: 'fish',
    itemBags: 'bag',
    treasureLocs: 'tr',
    // Secrets
    doors: 'door',
    secretPassages: 'sec',
    achievementTriggers: 'ach'
};

const LAYER_KEYS_REVERSE: Record<string, keyof LayerVisibility> = Object.fromEntries(
    Object.entries(LAYER_KEYS).map(([k, v]) => [v, k as keyof LayerVisibility])
);

/**
 * Check if layer visibility matches defaults.
 */
function layersMatchDefaults(layers: LayerVisibility): boolean {
    for (const key of Object.keys(DEFAULT_LAYER_VISIBILITY) as (keyof LayerVisibility)[]) {
        if (layers[key] !== DEFAULT_LAYER_VISIBILITY[key]) {
            return false;
        }
    }
    return true;
}

/**
 * Serialize layer visibility to URL string.
 * Only includes layers that differ from defaults.
 * Returns null if all layers match defaults.
 */
function serializeLayers(layers: LayerVisibility): string | null {
    if (layersMatchDefaults(layers)) {
        return null;
    }

    const disabledDefaults: string[] = [];
    const enabledNonDefaults: string[] = [];

    for (const key of Object.keys(DEFAULT_LAYER_VISIBILITY) as (keyof LayerVisibility)[]) {
        const isOn = layers[key];
        const defaultOn = DEFAULT_LAYER_VISIBILITY[key];

        if (isOn && !defaultOn) {
            enabledNonDefaults.push(LAYER_KEYS[key]);
        } else if (!isOn && defaultOn) {
            disabledDefaults.push(LAYER_KEYS[key]);
        }
    }

    if (disabledDefaults.length === 0 && enabledNonDefaults.length === 0) {
        return null;
    }

    // List disabled layers with "-" prefix
    if (disabledDefaults.length > 0) {
        return disabledDefaults.map((k) => `-${k}`).join(',');
    }

    return enabledNonDefaults.join(',');
}

/**
 * Parse layer visibility from URL string.
 */
function parseLayers(layerStr: string | null): LayerVisibility {
    if (!layerStr) {
        return { ...DEFAULT_LAYER_VISIBILITY };
    }

    const layers = { ...DEFAULT_LAYER_VISIBILITY };
    const parts = layerStr.split(',').filter(Boolean);

    for (const part of parts) {
        if (part.startsWith('-')) {
            const key = part.slice(1);
            const layerKey = LAYER_KEYS_REVERSE[key];
            if (layerKey) {
                layers[layerKey] = false;
            }
        } else {
            const layerKey = LAYER_KEYS_REVERSE[part];
            if (layerKey) {
                layers[layerKey] = true;
            }
        }
    }

    return layers;
}

// ============================================================================
// Core Functions
// ============================================================================

/**
 * Cancel any pending debounced view sync.
 */
function cancelViewSync(): void {
    if (viewSyncTimer) {
        clearTimeout(viewSyncTimer);
        viewSyncTimer = null;
    }
}

/**
 * Build URL string from complete params.
 * Omits default values for compact URLs.
 */
export function buildUrl(params: UrlStateParams): string {
    const searchParams = new URLSearchParams();

    const { viewState, layers, entityId, entityType, focusedZoneId, debug } = params;

    // View state (omit if defaults)
    if (Math.abs(viewState.x - DEFAULT_X) > 0.1) {
        searchParams.set('x', viewState.x.toFixed(1));
    }
    if (Math.abs(viewState.y - DEFAULT_Y) > 0.1) {
        searchParams.set('y', viewState.y.toFixed(1));
    }
    if (Math.abs(viewState.zoom - DEFAULT_ZOOM) > 0.01) {
        searchParams.set('z', viewState.zoom.toFixed(2));
    }

    // Selection
    if (entityId) {
        searchParams.set('entity', entityId);
    }
    if (entityType) {
        searchParams.set('etype', entityType);
    }

    // Zone focus
    if (focusedZoneId) {
        searchParams.set('zone', focusedZoneId);
    }

    // Layers (only if non-default)
    const layerStr = serializeLayers(layers);
    if (layerStr) {
        searchParams.set('layers', layerStr);
    }

    // Debug mode
    if (debug) {
        searchParams.set('debug', 'true');
    }

    const queryStr = searchParams.toString();
    const basePath = browser ? window.location.pathname : '/map';
    return queryStr ? `${basePath}?${queryStr}` : basePath;
}

/**
 * Parse URL state from current location.
 * Returns null if no map params are present.
 */
export function parseUrlState(): ParsedUrlState | null {
    if (!browser) return null;

    const params = new URLSearchParams(window.location.search);

    // Check if any map params exist
    const hasMapParams =
        params.has('x') ||
        params.has('y') ||
        params.has('z') ||
        params.has('entity') ||
        params.has('zone') ||
        params.has('layers') ||
        params.has('debug');

    if (!hasMapParams) {
        return null;
    }

    return {
        x: parseFloat(params.get('x') ?? String(DEFAULT_X)),
        y: parseFloat(params.get('y') ?? String(DEFAULT_Y)),
        zoom: parseFloat(params.get('z') ?? String(DEFAULT_ZOOM)),
        layers: params.get('layers'),
        entity: params.get('entity'),
        etype: params.get('etype'),
        zone: params.get('zone'),
        debug: params.get('debug') === 'true'
    };
}

/**
 * Parse layer visibility from URL string.
 * Returns default visibility if no layers param.
 */
export function parseLayerVisibility(layerStr: string | null): LayerVisibility {
    return parseLayers(layerStr);
}

// ============================================================================
// URL Manager
// ============================================================================

/**
 * URL manager for map state synchronization.
 *
 * History Management Rules:
 * | Action              | Method          | Effect                          |
 * |---------------------|-----------------|----------------------------------|
 * | Pan/zoom map        | syncViewState   | Replace (debounced 150ms)        |
 * | Toggle layer        | syncPreferences | Replace (immediate)              |
 * | Change zone focus   | syncPreferences | Replace (immediate)              |
 * | Click marker        | pushSelection   | Push (back/forward works)        |
 * | Close popup         | pushSelection   | Push (can go back to selection)  |
 * | Browser back/forward| Passive mode    | Restore state, no URL update     |
 */
export const urlManager = {
    /**
     * Enter passive mode. Use try/finally to ensure exit.
     * While passive, no URL updates are made.
     */
    enterPassiveMode(): void {
        isPassiveMode = true;
        cancelViewSync();
    },

    /**
     * Exit passive mode.
     */
    exitPassiveMode(): void {
        isPassiveMode = false;
    },

    /**
     * Check if currently in passive mode.
     */
    isPassive(): boolean {
        return isPassiveMode;
    },

    /**
     * Sync internal tracking after URL restore.
     * Prevents duplicate history entries when user clicks same marker again.
     */
    setLastSelection(entityId: string | null, entityType: string | null): void {
        lastSelection = { entityId, entityType };
    },

    /**
     * Debounced view state sync (pan/zoom).
     * Uses replaceState - no history entry.
     */
    syncViewState(params: UrlStateParams): void {
        if (!browser || isPassiveMode) return;

        cancelViewSync();
        viewSyncTimer = setTimeout(() => {
            replaceState(buildUrl(params), {});
            viewSyncTimer = null;
        }, VIEW_SYNC_DEBOUNCE_MS);
    },

    /**
     * Immediate preference sync (layers, zone focus).
     * Uses replaceState - no history entry.
     */
    syncPreferences(params: UrlStateParams): void {
        if (!browser || isPassiveMode) return;

        cancelViewSync();
        replaceState(buildUrl(params), {});
    },

    /**
     * Push selection change to history.
     * Deduplicates to prevent duplicate entries when clicking same marker.
     */
    pushSelection(params: UrlStateParams): void {
        if (!browser || isPassiveMode) return;

        const { entityId, entityType } = params;

        // Deduplicate
        if (entityId === lastSelection.entityId && entityType === lastSelection.entityType) {
            return;
        }

        cancelViewSync();
        pushState(buildUrl(params), {});
        lastSelection = { entityId, entityType };
    }
};
