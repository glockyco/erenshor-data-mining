import { FLY_TO_CONFIG, INITIAL_VIEW_STATE } from './config';
import { LinearInterpolator } from '@deck.gl/core';
import { cubicInOut } from 'svelte/easing';

export interface FlyToOptions {
    duration?: number;
    zoom?: number;
}

export interface Bounds {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
}

export interface FlyToBoundsOptions {
    duration?: number;
    padding?: number;
    maxZoom?: number;
}

/**
 * Animate the map view to a target position.
 * Creates a new LinearInterpolator each time to ensure
 * deck.gl recognizes repeated calls as new transitions.
 */
export function flyTo(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    deckInstance: any,
    targetX: number,
    targetY: number,
    options: FlyToOptions = {}
): void {
    if (!deckInstance) return;

    const { duration = FLY_TO_CONFIG.duration, zoom = 0 } = options;

    deckInstance.setProps({
        initialViewState: {
            target: [targetX, targetY, 0],
            zoom,
            minZoom: INITIAL_VIEW_STATE.minZoom,
            maxZoom: INITIAL_VIEW_STATE.maxZoom,
            transitionDuration: duration,
            transitionEasing: cubicInOut,
            transitionInterpolator: new LinearInterpolator(['target', 'zoom'])
        }
    });
}

/**
 * Reset the map view to the initial position.
 */
export function resetView(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    deckInstance: any,
    options: { duration?: number } = {}
): void {
    if (!deckInstance) return;

    const { duration = FLY_TO_CONFIG.duration } = options;

    deckInstance.setProps({
        initialViewState: {
            ...INITIAL_VIEW_STATE,
            transitionDuration: duration,
            transitionEasing: cubicInOut,
            transitionInterpolator: new LinearInterpolator(['target', 'zoom'])
        }
    });
}

/**
 * Fly to fit a bounding box in the viewport.
 * Calculates appropriate zoom level to show all content with padding.
 */
export function flyToBounds(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    deckInstance: any,
    bounds: Bounds,
    options: FlyToBoundsOptions = {}
): void {
    if (!deckInstance) return;

    const {
        duration = FLY_TO_CONFIG.duration,
        padding = FLY_TO_CONFIG.padding,
        maxZoom = FLY_TO_CONFIG.maxZoom
    } = options;

    // Get viewport dimensions from deck instance
    const viewportWidth = deckInstance.width || 1000;
    const viewportHeight = deckInstance.height || 800;

    // Calculate center
    const centerX = (bounds.minX + bounds.maxX) / 2;
    const centerY = (bounds.minY + bounds.maxY) / 2;

    // Calculate bounds size with padding
    const boundsWidth = (bounds.maxX - bounds.minX) * padding;
    const boundsHeight = (bounds.maxY - bounds.minY) * padding;

    // Calculate zoom to fit bounds in viewport
    // In OrthographicView at zoom=0, 1 world unit = 1 pixel
    // At zoom=n, 1 world unit = 2^n pixels
    const zoomX = boundsWidth > 0 ? Math.log2(viewportWidth / boundsWidth) : maxZoom;
    const zoomY = boundsHeight > 0 ? Math.log2(viewportHeight / boundsHeight) : maxZoom;

    // Use the smaller zoom to ensure both dimensions fit
    let zoom = Math.min(zoomX, zoomY);

    // Clamp to valid zoom range
    zoom = Math.max(INITIAL_VIEW_STATE.minZoom, Math.min(zoom, maxZoom));

    deckInstance.setProps({
        initialViewState: {
            target: [centerX, centerY, 0],
            zoom,
            minZoom: INITIAL_VIEW_STATE.minZoom,
            maxZoom: INITIAL_VIEW_STATE.maxZoom,
            transitionDuration: duration,
            transitionEasing: cubicInOut,
            transitionInterpolator: new LinearInterpolator(['target', 'zoom'])
        }
    });
}
