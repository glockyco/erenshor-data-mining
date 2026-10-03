/**
 * The `layers` URL parameter: a compact list of layer keys that differ from
 * the defaults. `-key` hides a default layer, and a bare `key` shows a hidden
 * one.
 */

import { DEFAULT_LAYER_VISIBILITY, type LayerVisibility } from '$lib/types/world-map';

/** Short URL key for each layer. */
const LAYER_KEYS: Record<keyof LayerVisibility, string> = {
    // Terrain
    tiles: 'tile',
    worldMap: 'wm',
    zoneBounds: 'zb',
    zoneLabels: 'zlbl',
    // Enemies
    spawnPoints: 'sp',
    spawnPointsElite: 'spe',
    spawnPointsBoss: 'spb',
    spawnPointsChest: 'spc',
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
    achievementTriggers: 'ach',
    // Movement overlays
    showPatrols: 'pat',
    showWanderRanges: 'wr'
};

/**
 * Keys that earlier site versions wrote, accepted on read only. Shipped
 * companion overlays load `/map?layers=-sp,-spr,-spu,-npc`, so a renamed key
 * must keep its old spelling here for as long as those builds exist.
 */
const LEGACY_LAYER_KEYS: Record<string, keyof LayerVisibility> = {
    spr: 'spawnPointsElite',
    spu: 'spawnPointsBoss'
};

const LAYER_KEYS_REVERSE: Record<string, keyof LayerVisibility> = {
    ...LEGACY_LAYER_KEYS,
    ...Object.fromEntries(Object.entries(LAYER_KEYS).map(([k, v]) => [v, k as keyof LayerVisibility]))
};

const LAYER_NAMES = Object.keys(DEFAULT_LAYER_VISIBILITY) as (keyof LayerVisibility)[];

/** Serialize the layers that differ from the defaults, or `null` when none do. */
export function serializeLayers(layers: LayerVisibility): string | null {
    const disabledDefaults: string[] = [];
    const enabledNonDefaults: string[] = [];

    for (const key of LAYER_NAMES) {
        const isOn = layers[key];
        const defaultOn = DEFAULT_LAYER_VISIBILITY[key];

        if (isOn && !defaultOn) {
            enabledNonDefaults.push(LAYER_KEYS[key]);
        } else if (!isOn && defaultOn) {
            disabledDefaults.push(LAYER_KEYS[key]);
        }
    }

    if (disabledDefaults.length > 0) {
        return disabledDefaults.map((k) => `-${k}`).join(',');
    }
    if (enabledNonDefaults.length > 0) {
        return enabledNonDefaults.join(',');
    }
    return null;
}

/** Parse the `layers` parameter. Unknown keys are ignored. */
export function parseLayerVisibility(layerStr: string | null): LayerVisibility {
    const layers = { ...DEFAULT_LAYER_VISIBILITY };
    if (!layerStr) {
        return layers;
    }

    for (const part of layerStr.split(',').filter(Boolean)) {
        const hidden = part.startsWith('-');
        const layerKey = LAYER_KEYS_REVERSE[hidden ? part.slice(1) : part];
        if (layerKey) {
            layers[layerKey] = !hidden;
        }
    }

    return layers;
}
