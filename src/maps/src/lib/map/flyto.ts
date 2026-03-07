import { FLY_TO_CONFIG, INITIAL_VIEW_STATE } from './config';
import { LinearInterpolator } from '@deck.gl/core';
import { cubicInOut } from 'svelte/easing';

// =============================================================================
// Types
// =============================================================================

export interface Bounds {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
}

export interface ComputedView {
    x: number;
    y: number;
    zoom: number;
}

export interface FlyToOptions {
    duration?: number;
    zoom?: number;
    /**
     * Pixels obscured on the right (e.g., popup width).
     * The left sidebar is handled by deck.gl's OrthographicView.padding.left
     * and needs no compensation here.
     */
    rightPadding?: number;
}

export interface FlyToBoundsOptions {
    duration?: number;
    padding?: number;
    maxZoom?: number;
    /**
     * Pixels obscured on the left (e.g., sidebar width).
     * Used to compute effective viewport width for zoom fitting.
     * NOT used for center offset — deck.gl's OrthographicView.padding.left
     * already handles that.
     */
    leftPadding?: number;
    /**
     * Pixels obscured on the right (e.g., popup width).
     * Used for both zoom fitting and center offset.
     */
    rightPadding?: number;
}

// =============================================================================
// Pure view computation (no deck.gl instance needed)
// =============================================================================

/**
 * Compute view center and zoom to fit bounds within a viewport.
 * Accounts for asymmetric padding (sidebar on left, popup on right).
 *
 * Left padding reduces effective width for zoom fitting but does NOT
 * offset the center — deck.gl's OrthographicView.padding.left handles that.
 * Right padding reduces effective width AND offsets the center.
 */
export function computeBoundsView(
    bounds: Bounds,
    viewportWidth: number,
    viewportHeight: number,
    options: {
        padding?: number;
        maxZoom?: number;
        leftPadding?: number;
        rightPadding?: number;
    } = {}
): ComputedView {
    const {
        padding = FLY_TO_CONFIG.padding,
        maxZoom = FLY_TO_CONFIG.maxZoom,
        leftPadding = 0,
        rightPadding = 0
    } = options;

    // Effective viewport width excluding obscured areas (clamped to avoid NaN zoom)
    const effectiveWidth = Math.max(1, viewportWidth - leftPadding - rightPadding);

    // Calculate center
    let centerX = (bounds.minX + bounds.maxX) / 2;
    const centerY = (bounds.minY + bounds.maxY) / 2;

    // Calculate bounds size with padding multiplier
    const boundsWidth = (bounds.maxX - bounds.minX) * padding;
    const boundsHeight = (bounds.maxY - bounds.minY) * padding;

    // Calculate zoom to fit bounds in effective viewport
    // In OrthographicView at zoom=0, 1 world unit = 1 pixel
    // At zoom=n, 1 world unit = 2^n pixels
    const zoomX = boundsWidth > 0 ? Math.log2(effectiveWidth / boundsWidth) : maxZoom;
    const zoomY = boundsHeight > 0 ? Math.log2(viewportHeight / boundsHeight) : maxZoom;

    // Use the smaller zoom to ensure both dimensions fit
    let zoom = Math.min(zoomX, zoomY);

    // Clamp to valid zoom range
    zoom = Math.max(INITIAL_VIEW_STATE.minZoom, Math.min(zoom, maxZoom));

    // Only the right popup needs center compensation.
    // At zoom Z, 1 pixel = 1/2^Z world units.
    if (rightPadding > 0) {
        centerX += rightPadding / 2 / Math.pow(2, zoom);
    }

    return { x: centerX, y: centerY, zoom };
}

/**
 * Compute view center for a single point with optional right-padding offset.
 *
 * Left padding is NOT compensated — deck.gl's OrthographicView.padding.left
 * handles that. Right padding shifts the center to keep the point visually
 * centered in the unobscured area.
 */
export function computePointView(
    targetX: number,
    targetY: number,
    options: { zoom?: number; rightPadding?: number } = {}
): ComputedView {
    const { zoom = 0, rightPadding = 0 } = options;

    let adjustedX = targetX;
    if (rightPadding > 0) {
        adjustedX += rightPadding / 2 / Math.pow(2, zoom);
    }

    return { x: adjustedX, y: targetY, zoom };
}

// =============================================================================
// Animated transitions (require deck.gl instance)
// =============================================================================

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

    const { duration = FLY_TO_CONFIG.duration, ...rest } = options;
    const view = computePointView(targetX, targetY, rest);

    deckInstance.setProps({
        initialViewState: {
            target: [view.x, view.y, 0],
            zoom: view.zoom,
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

    const { duration = FLY_TO_CONFIG.duration, ...rest } = options;

    const viewportWidth = deckInstance.width || 1000;
    const viewportHeight = deckInstance.height || 800;

    const view = computeBoundsView(bounds, viewportWidth, viewportHeight, rest);

    deckInstance.setProps({
        initialViewState: {
            target: [view.x, view.y, 0],
            zoom: view.zoom,
            minZoom: INITIAL_VIEW_STATE.minZoom,
            maxZoom: INITIAL_VIEW_STATE.maxZoom,
            transitionDuration: duration,
            transitionEasing: cubicInOut,
            transitionInterpolator: new LinearInterpolator(['target', 'zoom'])
        }
    });
}
