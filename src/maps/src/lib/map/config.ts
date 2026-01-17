/**
 * Initial view state for deck.gl (world map view)
 */
export const INITIAL_VIEW_STATE = {
    target: [0, 0, 0] as [number, number, number],
    zoom: -2,
    minZoom: -6,
    maxZoom: 4
} as const;

/**
 * Sidebar dimensions (matches Tailwind classes in MapSidebar.svelte)
 */
export const SIDEBAR_WIDTH = {
    expanded: 256, // w-64 (16rem * 16px)
    collapsed: 56 // w-14 (3.5rem * 16px)
} as const;

/**
 * Layer colors by marker category (Tailwind colors as RGB)
 */
export const LAYER_COLORS = {
    // Enemies (static spawn points - muted warm colors)
    enemy: [217, 119, 6] as [number, number, number], // amber-600 (common spawn)
    'enemy-rare': [225, 29, 72] as [number, number, number], // rose-600 (rare spawn)
    'enemy-unique': [109, 40, 217] as [number, number, number], // violet-700 (unique spawn)
    // NPCs (friendly characters)
    npc: [34, 197, 94] as [number, number, number], // green-500
    // Zone connections
    'zone-line': [168, 85, 247] as [number, number, number], // purple-500
    // Utilities
    forge: [249, 115, 22] as [number, number, number], // orange-500
    'wishing-well': [6, 182, 212] as [number, number, number], // cyan-500
    teleport: [139, 92, 246] as [number, number, number], // violet-500
    // Resources
    'mining-node': [156, 163, 175] as [number, number, number], // gray-400
    'treasure-loc': [250, 204, 21] as [number, number, number], // yellow-400
    'item-bag': [234, 179, 8] as [number, number, number], // yellow-500
    // Interactables
    door: [180, 83, 9] as [number, number, number], // amber-700
    'secret-passage': [168, 85, 247] as [number, number, number], // purple-500 (hidden passage)
    'achievement-trigger': [244, 63, 94] as [number, number, number], // rose-500
    water: [56, 189, 248] as [number, number, number], // sky-400
    // Disabled state (for any marker type)
    disabled: [107, 114, 128] as [number, number, number], // gray-500
    // Live entities (bright, prominent colors)
    'player-live': [132, 204, 22] as [number, number, number], // lime-500 - YOU
    'simplayer-live': [6, 182, 212] as [number, number, number], // cyan-500 - ALLY
    'pet-live': [217, 70, 239] as [number, number, number], // fuchsia-500 - COMPANION
    'npc-friendly-live': [16, 185, 129] as [number, number, number], // emerald-500 - FRIENDLY
    'enemy-common-live': [249, 115, 22] as [number, number, number], // orange-500 - THREAT
    'enemy-rare-live': [239, 68, 68] as [number, number, number], // red-500 - HIGH THREAT
    'enemy-boss-live': [24, 24, 27] as [number, number, number] // zinc-900 - BOSS (iconic black)
} as const;

/**
 * Icon size for IconLayer (uniform for all marker types)
 */
export const ICON_SIZE = { base: 20, min: 18, max: 44 } as const;

/**
 * Background color for the map (dark)
 */
export const BACKGROUND_COLOR = [24, 24, 27, 255] as const; // zinc-900

/**
 * Zone boundary colors
 */
export const ZONE_COLORS = {
    bounds: {
        fill: [100, 116, 139, 20] as [number, number, number, number], // slate-500 low alpha
        stroke: [100, 116, 139, 120] as [number, number, number, number]
    },
    selected: {
        fill: [250, 204, 21, 15] as [number, number, number, number], // yellow-400 very low alpha
        stroke: [250, 204, 21, 200] as [number, number, number, number]
    },
    label: [255, 255, 255, 200] as [number, number, number, number]
} as const;

/**
 * Selection highlight colors
 */
export const HIGHLIGHT_COLORS = {
    ring: [255, 255, 255, 255] as [number, number, number, number],
    fill: [255, 255, 255, 40] as [number, number, number, number],
    primaryRing: [250, 204, 21, 255] as [number, number, number, number], // yellow-400
    primaryFill: [250, 204, 21, 80] as [number, number, number, number],
    hoverRing: [250, 204, 21, 255] as [number, number, number, number],
    hoverFill: [250, 204, 21, 40] as [number, number, number, number]
} as const;

/**
 * Movement visualization colors (patrol paths, wander range)
 */
export const MOVEMENT_COLORS = {
    wanderCircle: [96, 165, 250, 25] as [number, number, number, number], // blue-400, 10% fill
    wanderStroke: [96, 165, 250, 200] as [number, number, number, number], // blue-400
    patrolLine: [250, 204, 21, 255] as [number, number, number, number], // yellow-400
    patrolDashed: [250, 204, 21, 150] as [number, number, number, number], // yellow-400 faded
    waypoint: [250, 204, 21, 255] as [number, number, number, number] // yellow-400
} as const;

/**
 * Fly-to animation configuration
 */
export const FLY_TO_CONFIG = {
    duration: 800,
    padding: 1.2,
    maxZoom: 2,
    singlePointPadding: 50
} as const;

/**
 * Tailwind border color classes for tooltip by marker category
 */
export const MARKER_BORDER_COLORS: Record<string, string> = {
    'achievement-trigger': 'border-l-pink-500',
    door: 'border-l-amber-700',
    enemy: 'border-l-blue-500',
    'enemy-rare': 'border-l-red-500',
    'enemy-unique': 'border-l-zinc-900',
    forge: 'border-l-orange-500',
    'item-bag': 'border-l-orange-400',
    'mining-node': 'border-l-gray-400',
    npc: 'border-l-green-500',
    'secret-passage': 'border-l-violet-400',
    teleport: 'border-l-violet-500',
    'treasure-loc': 'border-l-yellow-400',
    water: 'border-l-sky-400',
    'wishing-well': 'border-l-cyan-500',
    'zone-line': 'border-l-purple-500'
};

/**
 * Coordinate transformation utilities
 *
 * Game coordinates use:
 * - X: horizontal (east-west)
 * - Y: height (vertical, ignored for 2D map)
 * - Z: depth (north-south)
 *
 * Map coordinates use:
 * - X: horizontal (east on right)
 * - Y: vertical (north at top, negated from game Z)
 *
 * Each zone has a NorthBearing (degrees) indicating which direction
 * is north in game coordinates. We rotate markers to align north with
 * the top of the map (compass-aligned).
 */

/**
 * Transform marker position from game coordinates to compass-aligned map coordinates
 *
 * @param gameX - Game X coordinate
 * @param gameZ - Game Z coordinate (forward/back in game)
 * @param northBearing - Zone's north bearing in degrees
 * @param centerX - Center X for rotation (typically zone center)
 * @param centerY - Center Y for rotation (typically zone center)
 * @returns [mapX, mapY] - Compass-aligned map coordinates
 */
export function transformToMapCoords(
    gameX: number,
    gameZ: number,
    northBearing: number,
    centerX: number = 0,
    centerY: number = 0
): [number, number] {
    // Step 1: Negate Z to flip Y-axis (so north is up)
    const flippedY = -gameZ;

    // Step 2: Rotate around center to align north with top of map
    // NorthBearing tells us where north is in game coords
    // Rotate by (180 - NorthBearing) to bring north to top
    const angleRad = ((180 - northBearing) * Math.PI) / 180;

    const dx = gameX - centerX;
    const dy = flippedY - centerY;

    const rotatedX = centerX + dx * Math.cos(angleRad) - dy * Math.sin(angleRad);
    const rotatedY = centerY + dx * Math.sin(angleRad) + dy * Math.cos(angleRad);

    return [rotatedX, rotatedY];
}
