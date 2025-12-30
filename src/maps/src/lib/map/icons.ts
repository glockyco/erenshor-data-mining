/**
 * Generate icon atlas from Lucide icons for deck.gl IconLayer.
 * Creates colored circle backgrounds with white icons overlaid.
 */

import {
    Skull,
    User,
    CircleDot,
    Flame,
    Droplet,
    Compass,
    Pickaxe,
    Map,
    Package,
    KeyRound,
    CircleHelp,
    Trophy,
    Fish,
    type IconNode
} from 'lucide';
import { LAYER_COLORS } from './config';

// Icon size in the atlas (pixels)
const ICON_SIZE = 64;
// Padding between icon circle edge and atlas cell edge (prevents clipping)
const CIRCLE_PADDING = 2;

/** Convert RGB array to hex string */
function rgbToHex(rgb: readonly [number, number, number]): string {
    return `#${rgb.map((c) => c.toString(16).padStart(2, '0')).join('')}`;
}

// Marker type configurations: icon + color key
// Colors are derived from LAYER_COLORS (single source of truth)
const MARKER_ICONS: Record<string, { icon: IconNode; colorKey: keyof typeof LAYER_COLORS }> = {
    // Enemies - differentiated by rarity
    enemy: { icon: Skull, colorKey: 'enemy' },
    'enemy-rare': { icon: Skull, colorKey: 'enemy-rare' },
    'enemy-unique': { icon: Skull, colorKey: 'enemy-unique' },
    // NPCs (friendly characters)
    npc: { icon: User, colorKey: 'npc' },
    // Zone connections (portals)
    'zone-line': { icon: CircleDot, colorKey: 'zone-line' },
    'zone-line-disabled': { icon: CircleDot, colorKey: 'disabled' },
    // Utilities
    forge: { icon: Flame, colorKey: 'forge' },
    'wishing-well': { icon: Droplet, colorKey: 'wishing-well' },
    teleport: { icon: Compass, colorKey: 'teleport' },
    // Resources
    'mining-node': { icon: Pickaxe, colorKey: 'mining-node' },
    'treasure-loc': { icon: Map, colorKey: 'treasure-loc' },
    'item-bag': { icon: Package, colorKey: 'item-bag' },
    // Interactables
    door: { icon: KeyRound, colorKey: 'door' },
    'secret-passage': { icon: CircleHelp, colorKey: 'secret-passage' },
    'achievement-trigger': { icon: Trophy, colorKey: 'achievement-trigger' },
    water: { icon: Fish, colorKey: 'water' }
};

export type MarkerIconType = keyof typeof MARKER_ICONS;

/**
 * Convert Lucide IconNode to SVG string.
 */
function iconNodeToSvg(iconNode: IconNode, color: string): string {
    let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">`;

    for (const [tag, attrs] of iconNode) {
        const attrStr = Object.entries(attrs || {})
            .map(([k, v]) => `${k}="${v}"`)
            .join(' ');
        svg += `<${tag} ${attrStr}/>`;
    }

    svg += '</svg>';
    return svg;
}

/**
 * Load an SVG string as an Image
 */
function loadSvgAsImage(svgString: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = 'data:image/svg+xml,' + encodeURIComponent(svgString);
    });
}

export interface IconAtlasResult {
    atlas: HTMLCanvasElement;
    mapping: Record<string, { x: number; y: number; width: number; height: number; mask: boolean }>;
}

/**
 * Create icon atlas canvas and mapping for deck.gl IconLayer.
 * Each icon is a colored circle with a white icon overlay.
 */
export async function createIconAtlas(): Promise<IconAtlasResult> {
    const markerTypes = Object.keys(MARKER_ICONS);
    const atlasWidth = ICON_SIZE * markerTypes.length;
    const atlasHeight = ICON_SIZE;

    const canvas = document.createElement('canvas');
    canvas.width = atlasWidth;
    canvas.height = atlasHeight;

    const ctx = canvas.getContext('2d');
    if (!ctx) {
        throw new Error('Could not get canvas 2d context');
    }

    const mapping: IconAtlasResult['mapping'] = {};

    // Load all icon images first
    const iconImages = await Promise.all(
        markerTypes.map(async (markerType) => {
            const { icon } = MARKER_ICONS[markerType];
            const svgString = iconNodeToSvg(icon, '#ffffff');
            return loadSvgAsImage(svgString);
        })
    );

    // Draw each icon with colored circle background
    markerTypes.forEach((markerType, index) => {
        const { colorKey } = MARKER_ICONS[markerType];
        const bgColor = rgbToHex(LAYER_COLORS[colorKey]);
        const img = iconImages[index];

        const x = index * ICON_SIZE;
        const y = 0;
        const centerX = x + ICON_SIZE / 2;
        const centerY = ICON_SIZE / 2;
        const radius = ICON_SIZE / 2 - CIRCLE_PADDING;

        // Draw colored circle background
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.fillStyle = bgColor;
        ctx.fill();

        // Add dark outline for better definition on bright backgrounds
        ctx.strokeStyle = 'rgba(0, 0, 0, 0.4)';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Draw white icon centered (scaled to fit inside circle)
        // Add dark drop shadow for visibility on bright backgrounds
        const iconSize = ICON_SIZE * 0.55;
        const iconOffset = (ICON_SIZE - iconSize) / 2;

        ctx.filter = 'drop-shadow(0 0 1px black) drop-shadow(0 0 1px black)';
        ctx.drawImage(img, x + iconOffset, y + iconOffset, iconSize, iconSize);
        ctx.filter = 'none';

        // Add to mapping
        mapping[markerType] = {
            x,
            y,
            width: ICON_SIZE,
            height: ICON_SIZE,
            mask: false
        };
    });

    return { atlas: canvas, mapping };
}

/**
 * Get the icon type key for an enemy marker based on its rarity.
 */
export function getEnemyIconType(marker: { isUnique?: boolean; isRare?: boolean }): MarkerIconType {
    if (marker.isUnique) {
        return 'enemy-unique';
    }
    if (marker.isRare) {
        return 'enemy-rare';
    }
    return 'enemy';
}

/**
 * Get the icon type key for a zone line marker based on its enabled state.
 */
export function getZoneLineIconType(marker: { isEnabled?: boolean }): MarkerIconType {
    return marker.isEnabled === false ? 'zone-line-disabled' : 'zone-line';
}
