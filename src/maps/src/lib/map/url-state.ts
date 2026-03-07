/**
 * URL state management for shareable map links.
 *
 * Uses a unified `sel` param for all selection types:
 * - `sel=marker:<stableKey>` — clicked a specific spawn point / marker
 * - `sel=zone:<zoneKey>` — clicked or searched a zone
 * - `sel=enemy:<name>` — searched an enemy name (all spawn locations)
 * - `sel=npc:<name>` — searched an NPC name (all spawn locations)
 *
 * URL manager pattern:
 * - pushSelection() — adds to browser history (back/forward works)
 * - syncViewState() — debounced replace (no history spam during pan/zoom)
 * - syncPreferences() — immediate replace for layers/zone focus
 * - Passive mode — prevents URL updates during popstate restoration
 */

import { browser } from '$app/environment';
import { pushState, replaceState } from '$app/navigation';
import { DEFAULT_LAYER_VISIBILITY, type LayerVisibility } from '$lib/types/world-map';

// ============================================================================
// Types
// ============================================================================

/**
 * Complete state needed to build a URL.
 * All fields required — no optionals, no partial updates.
 */
export interface UrlStateParams {
    viewState: { x: number; y: number; zoom: number };
    layers: LayerVisibility;
    sel: string | null;
    focusedZoneId: string | null;
    debug: boolean;
    levelFilter: [number, number];
    levelRange: { min: number; max: number };
}

/**
 * Parsed URL state (what we read FROM the URL).
 */
export interface ParsedUrlState {
    x: number;
    y: number;
    zoom: number;
    layers: string | null;
    sel: string | null;
    zone: string | null;
    debug: boolean;
    levelFilter: [number, number] | null;
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

let lastSel: string | null = null;
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

function layersMatchDefaults(layers: LayerVisibility): boolean {
    for (const key of Object.keys(DEFAULT_LAYER_VISIBILITY) as (keyof LayerVisibility)[]) {
        if (layers[key] !== DEFAULT_LAYER_VISIBILITY[key]) {
            return false;
        }
    }
    return true;
}

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

    if (disabledDefaults.length > 0) {
        return disabledDefaults.map((k) => `-${k}`).join(',');
    }

    return enabledNonDefaults.join(',');
}

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
 * Get normalized URL search string.
 * Fixes HTML entity encoding from forum posts where & becomes &amp;
 */
export function getNormalizedSearch(): string {
    let search = window.location.search;
    if (search.includes('&amp;')) {
        search = search.replaceAll('&amp;', '&');
        const cleanUrl = window.location.pathname + search + window.location.hash;
        window.history.replaceState(null, '', cleanUrl);
    }
    return search;
}

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

    const { viewState, layers, sel, focusedZoneId, debug, levelFilter, levelRange } = params;

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

    // Unified selection
    if (sel) {
        searchParams.set('sel', sel);
    }

    // Zone focus (filtering)
    if (focusedZoneId) {
        searchParams.set('zone', focusedZoneId);
    }

    // Layers (only if non-default)
    const layerStr = serializeLayers(layers);
    if (layerStr) {
        searchParams.set('layers', layerStr);
    }

    // Level filter (only if not matching full range)
    if (levelFilter[0] !== levelRange.min || levelFilter[1] !== levelRange.max) {
        searchParams.set('lvl', `${levelFilter[0]}-${levelFilter[1]}`);
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

    const params = new URLSearchParams(getNormalizedSearch());

    const hasMapParams =
        params.has('x') ||
        params.has('y') ||
        params.has('z') ||
        params.has('sel') ||
        params.has('zone') ||
        params.has('layers') ||
        params.has('lvl') ||
        params.has('debug');

    if (!hasMapParams) {
        return null;
    }

    let levelFilter: [number, number] | null = null;
    const lvl = params.get('lvl');
    if (lvl) {
        const parts = lvl.split('-').map(Number);
        if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
            levelFilter = [parts[0], parts[1]];
        }
    }

    return {
        x: parseFloat(params.get('x') ?? String(DEFAULT_X)),
        y: parseFloat(params.get('y') ?? String(DEFAULT_Y)),
        zoom: parseFloat(params.get('z') ?? String(DEFAULT_ZOOM)),
        layers: params.get('layers'),
        sel: params.get('sel'),
        zone: params.get('zone'),
        debug: params.get('debug') === 'true',
        levelFilter
    };
}

/**
 * Parse layer visibility from URL string.
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
 * | Search selection    | pushSelection   | Push (back/forward works)        |
 * | Close popup         | pushSelection   | Push (can go back to selection)  |
 * | Browser back/forward| Passive mode    | Restore state, no URL update     |
 */
export const urlManager = {
    enterPassiveMode(): void {
        isPassiveMode = true;
        cancelViewSync();
    },

    exitPassiveMode(): void {
        isPassiveMode = false;
    },

    isPassive(): boolean {
        return isPassiveMode;
    },

    /**
     * Sync internal tracking after URL restore.
     */
    setLastSel(sel: string | null): void {
        lastSel = sel;
    },

    /**
     * Debounced view state sync (pan/zoom).
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
     */
    syncPreferences(params: UrlStateParams): void {
        if (!browser || isPassiveMode) return;

        cancelViewSync();
        replaceState(buildUrl(params), {});
    },

    /**
     * Push selection change to history.
     * Deduplicates to prevent duplicate entries.
     */
    pushSelection(params: UrlStateParams): void {
        if (!browser || isPassiveMode) return;

        const { sel } = params;

        if (sel === lastSel) {
            return;
        }

        cancelViewSync();
        pushState(buildUrl(params), {});
        lastSel = sel;
    }
};
