/**
 * URL state management for shareable map links.
 *
 * Uses explicit urlManager object pattern (not reactive effects) with:
 * - pushSelection() - adds to browser history (back/forward works)
 * - syncViewState() - debounced replace (no history spam during pan/zoom)
 * - syncPreferences() - immediate replace for layers/filters
 * - Passive mode - prevents URL updates during popstate restoration
 */

import { browser } from '$app/environment';
import { DEFAULT_LAYER_VISIBILITY, type LayerVisibility } from '$lib/types/map';

/**
 * URL state interface for Erenshor maps
 */
export interface UrlState {
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
    /** Focused zone key */
    zone: string | null;
    /** Comma-separated visible layers (null = defaults) */
    layers: string | null;
    /** Debug mode */
    debug: boolean;
}

/**
 * Parameters for URL state updates (all optional for partial updates)
 */
export interface UrlStateParams {
    x?: number;
    y?: number;
    z?: number;
    marker?: string | null;
    mtype?: string | null;
    zone?: string | null;
    layers?: LayerVisibility | null;
    debug?: boolean;
}

// Default view state values
const DEFAULT_X = 0;
const DEFAULT_Y = 0;
const DEFAULT_Z = -2;

// Debounce timer for view state sync
let viewStateDebounceTimer: ReturnType<typeof setTimeout> | null = null;
const VIEW_STATE_DEBOUNCE_MS = 150;

// Passive mode state
let isPassive = false;

// Last selection for deduplication
let lastMarker: string | null = null;
let lastMtype: string | null = null;

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
 * Check if layer visibility matches defaults
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

    // Find layers that are ON but shouldn't be (compared to defaults)
    const enabledNonDefaults: string[] = [];
    // Find layers that are OFF but should be ON (compared to defaults)
    const disabledDefaults: string[] = [];

    for (const key of Object.keys(DEFAULT_LAYER_VISIBILITY) as (keyof LayerVisibility)[]) {
        const isOn = layers[key];
        const defaultOn = DEFAULT_LAYER_VISIBILITY[key];

        if (isOn && !defaultOn) {
            enabledNonDefaults.push(LAYER_KEYS[key]);
        } else if (!isOn && defaultOn) {
            disabledDefaults.push(LAYER_KEYS[key]);
        }
    }

    // Use whichever representation is shorter:
    // - If more layers are disabled than enabled, list disabled with "-" prefix
    // - Otherwise list enabled layers
    if (disabledDefaults.length === 0 && enabledNonDefaults.length === 0) {
        return null;
    }

    // Format: enabled layers OR -disabled layers (whichever is shorter)
    // For simplicity, just list the disabled layers with "-" prefix
    if (disabledDefaults.length > 0) {
        return disabledDefaults.map((k) => `-${k}`).join(',');
    }

    return enabledNonDefaults.join(',');
}

/**
 * Parse layer visibility from URL string.
 * Returns null if string is null/empty (use defaults).
 */
function parseLayers(layerStr: string | null): LayerVisibility | null {
    if (!layerStr) {
        return null;
    }

    // Start with defaults
    const layers = { ...DEFAULT_LAYER_VISIBILITY };

    const parts = layerStr.split(',').filter(Boolean);

    for (const part of parts) {
        if (part.startsWith('-')) {
            // Disabled layer
            const key = part.slice(1);
            const layerKey = LAYER_KEYS_REVERSE[key];
            if (layerKey) {
                layers[layerKey] = false;
            }
        } else {
            // Enabled layer (non-default)
            const layerKey = LAYER_KEYS_REVERSE[part];
            if (layerKey) {
                layers[layerKey] = true;
            }
        }
    }

    return layers;
}

/**
 * Build URL search params from state.
 * Omits default values for compact URLs.
 */
function buildSearchParams(state: UrlStateParams): URLSearchParams {
    const params = new URLSearchParams();

    // View state (omit if defaults)
    if (state.x !== undefined && Math.abs(state.x - DEFAULT_X) > 0.1) {
        params.set('x', state.x.toFixed(1));
    }
    if (state.y !== undefined && Math.abs(state.y - DEFAULT_Y) > 0.1) {
        params.set('y', state.y.toFixed(1));
    }
    if (state.z !== undefined && Math.abs(state.z - DEFAULT_Z) > 0.01) {
        params.set('z', state.z.toFixed(2));
    }

    // Selection
    if (state.marker) {
        params.set('marker', state.marker);
    }
    if (state.mtype) {
        params.set('mtype', state.mtype);
    }

    // Zone focus
    if (state.zone) {
        params.set('zone', state.zone);
    }

    // Layers (only if non-default)
    if (state.layers) {
        const layerStr = serializeLayers(state.layers);
        if (layerStr) {
            params.set('layers', layerStr);
        }
    }

    // Debug mode
    if (state.debug) {
        params.set('debug', 'true');
    }

    return params;
}

/**
 * Update URL with new params using replaceState (no history entry)
 */
function replaceUrl(params: URLSearchParams): void {
    if (!browser || isPassive) return;

    const url = new URL(window.location.href);
    url.search = params.toString();
    window.history.replaceState(null, '', url.toString());
}

/**
 * Update URL with new params using pushState (creates history entry)
 */
function pushUrl(params: URLSearchParams): void {
    if (!browser || isPassive) return;

    const url = new URL(window.location.href);
    url.search = params.toString();
    window.history.pushState(null, '', url.toString());
}

/**
 * URL manager for map state synchronization.
 *
 * History Management Rules:
 * | Action | Method | Effect |
 * |--------|--------|--------|
 * | Pan/zoom map | syncViewState | Replace (debounced 150ms) |
 * | Toggle layer | syncPreferences | Replace (immediate) |
 * | Change zone focus | syncPreferences | Replace (immediate) |
 * | Click marker | pushSelection | Push (back/forward works) |
 * | Close popup | pushSelection | Push (can go back to selection) |
 * | Browser back/forward | Passive mode | Restore state, no URL update |
 */
export const urlManager = {
    /**
     * Enter passive mode (for popstate handling).
     * While passive, no URL updates are made.
     */
    enterPassiveMode(): void {
        isPassive = true;
    },

    /**
     * Exit passive mode.
     */
    exitPassiveMode(): void {
        isPassive = false;
    },

    /**
     * Check if currently in passive mode.
     */
    isPassive(): boolean {
        return isPassive;
    },

    /**
     * Track last selection for deduplication.
     * Call this when restoring state from URL to prevent duplicate pushes.
     */
    setLastSelection(markerId: string | null, markerType: string | null): void {
        lastMarker = markerId;
        lastMtype = markerType;
    },

    /**
     * Sync view state to URL (debounced, replaceState).
     * Use for pan/zoom operations that shouldn't create history entries.
     */
    syncViewState(state: UrlStateParams): void {
        if (!browser || isPassive) return;

        // Clear existing debounce timer
        if (viewStateDebounceTimer) {
            clearTimeout(viewStateDebounceTimer);
        }

        // Debounce the URL update
        viewStateDebounceTimer = setTimeout(() => {
            const currentParams = new URLSearchParams(window.location.search);

            // Merge with existing params
            const params = buildSearchParams({
                x: state.x,
                y: state.y,
                z: state.z,
                marker: state.marker ?? currentParams.get('marker'),
                mtype: state.mtype ?? currentParams.get('mtype'),
                zone: state.zone ?? currentParams.get('zone'),
                layers: state.layers,
                debug: state.debug ?? currentParams.get('debug') === 'true'
            });

            replaceUrl(params);
        }, VIEW_STATE_DEBOUNCE_MS);
    },

    /**
     * Sync preferences to URL (immediate, replaceState).
     * Use for layer toggles, zone focus changes.
     */
    syncPreferences(state: UrlStateParams): void {
        if (!browser || isPassive) return;

        const currentParams = new URLSearchParams(window.location.search);

        // Merge with existing params
        const params = buildSearchParams({
            x: state.x ?? parseFloat(currentParams.get('x') ?? String(DEFAULT_X)),
            y: state.y ?? parseFloat(currentParams.get('y') ?? String(DEFAULT_Y)),
            z: state.z ?? parseFloat(currentParams.get('z') ?? String(DEFAULT_Z)),
            marker: state.marker ?? currentParams.get('marker'),
            mtype: state.mtype ?? currentParams.get('mtype'),
            zone: state.zone,
            layers: state.layers,
            debug: state.debug ?? currentParams.get('debug') === 'true'
        });

        replaceUrl(params);
    },

    /**
     * Push selection change to URL (pushState for history).
     * Use when user clicks a marker to select it.
     * Creates history entry so back/forward navigation works.
     */
    pushSelection(state: UrlStateParams): void {
        if (!browser || isPassive) return;

        // Deduplicate: don't push if selection hasn't changed
        const newMarker = state.marker ?? null;
        const newMtype = state.mtype ?? null;

        if (newMarker === lastMarker && newMtype === lastMtype) {
            return;
        }

        lastMarker = newMarker;
        lastMtype = newMtype;

        const currentParams = new URLSearchParams(window.location.search);

        // Merge with existing params
        const params = buildSearchParams({
            x: state.x ?? parseFloat(currentParams.get('x') ?? String(DEFAULT_X)),
            y: state.y ?? parseFloat(currentParams.get('y') ?? String(DEFAULT_Y)),
            z: state.z ?? parseFloat(currentParams.get('z') ?? String(DEFAULT_Z)),
            marker: state.marker,
            mtype: state.mtype,
            zone: state.zone ?? currentParams.get('zone'),
            layers: state.layers,
            debug: state.debug ?? currentParams.get('debug') === 'true'
        });

        pushUrl(params);
    },

    /**
     * Clear selection from URL (pushState for history).
     * Use when user closes a popup.
     */
    clearSelection(state?: UrlStateParams): void {
        this.pushSelection({
            ...state,
            marker: null,
            mtype: null
        });
    }
};

/**
 * Parse URL state from current location.
 * Returns null if no map state params are present.
 */
export function parseUrlState(): UrlState | null {
    if (!browser) return null;

    const params = new URLSearchParams(window.location.search);

    // Check if any map params exist
    const hasMapParams =
        params.has('x') ||
        params.has('y') ||
        params.has('z') ||
        params.has('marker') ||
        params.has('zone') ||
        params.has('layers') ||
        params.has('debug');

    if (!hasMapParams) {
        return null;
    }

    return {
        x: parseFloat(params.get('x') ?? String(DEFAULT_X)),
        y: parseFloat(params.get('y') ?? String(DEFAULT_Y)),
        z: parseFloat(params.get('z') ?? String(DEFAULT_Z)),
        marker: params.get('marker'),
        mtype: params.get('mtype'),
        zone: params.get('zone'),
        layers: params.get('layers'),
        debug: params.get('debug') === 'true'
    };
}

/**
 * Parse layer visibility from URL state.
 * Returns default visibility if no layers param.
 */
export function parseLayerVisibility(layerStr: string | null): LayerVisibility {
    const parsed = parseLayers(layerStr);
    return parsed ?? { ...DEFAULT_LAYER_VISIBILITY };
}

/**
 * Build URL string from state params.
 * Useful for generating shareable links.
 */
export function buildUrl(state: UrlStateParams, baseUrl?: string): string {
    const params = buildSearchParams(state);
    const base = baseUrl ?? (browser ? window.location.pathname : '/map');
    const queryStr = params.toString();
    return queryStr ? `${base}?${queryStr}` : base;
}
