/**
 * Calculate tooltip position with screen edge detection.
 * Flips position when tooltip would overflow viewport edges.
 */
export function calculateTooltipPosition(
    mouseX: number,
    mouseY: number,
    tooltipWidth: number,
    tooltipHeight: number,
    offset = 12,
    edgePadding = 8
): { left: number; top: number } {
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // Default: bottom-right of cursor
    let left = mouseX + offset;
    let top = mouseY + offset;

    // Flip horizontal if would overflow right edge
    if (left + tooltipWidth + edgePadding > viewportWidth) {
        left = mouseX - tooltipWidth - offset;
    }

    // Flip vertical if would overflow bottom edge
    if (top + tooltipHeight + edgePadding > viewportHeight) {
        top = mouseY - tooltipHeight - offset;
    }

    // Ensure doesn't go past left edge
    if (left < edgePadding) {
        left = edgePadding;
    }

    // Ensure doesn't go past top edge
    if (top < edgePadding) {
        top = edgePadding;
    }

    return { left, top };
}
