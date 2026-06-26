/**
 * Wires the live coordinate readout in the section lens and fills each
 * `.coord-tag` survey mark with its own page coordinates.
 *
 * The cursor's page position drives the lens pill's `.hud-xy` readout; scrolling
 * with a stationary cursor still refreshes it (we keep the last viewport
 * position and re-add scroll). Each survey tag shows its own static page
 * coordinates. Returns a cleanup function — call it from the page's onMount
 * teardown.
 */
export function initCoordinates(): () => void {
    const hudXY = document.querySelector<HTMLElement>('.hud-xy');
    const tags = [...document.querySelectorAll<HTMLElement>('.coord-tag')];

    const placeTags = () => {
        for (const t of tags) {
            const r = t.getBoundingClientRect();
            const x = Math.round(r.left + window.scrollX);
            const y = Math.round(r.top + window.scrollY);
            t.innerHTML = `<b>X</b> ${x} · <b>Y</b> ${y}`;
            t.dataset.surveyY = String(y);
        }
    };

    // Last cursor viewport position, so scroll/resize can recompute page coords.
    let cx: number | null = null;
    let cy: number | null = null;

    const update = () => {
        if (!hudXY || cx === null || cy === null) return;
        hudXY.innerHTML = `<b>X</b> ${Math.round(cx + window.scrollX)} · <b>Y</b> ${Math.round(cy + window.scrollY)}`;
    };

    const onMove = (e: PointerEvent) => {
        cx = e.clientX;
        cy = e.clientY;
        update();
    };
    const onResize = () => {
        placeTags();
        update();
    };

    placeTags();
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', onResize, { passive: true });

    return () => {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('scroll', update);
        window.removeEventListener('resize', onResize);
    };
}
