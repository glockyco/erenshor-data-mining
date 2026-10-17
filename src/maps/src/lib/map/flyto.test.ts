import { describe, expect, it, vi } from 'vitest';
import type { LinearInterpolator } from '@deck.gl/core';
import { flyTo, flyToBounds, resetView } from './flyto';
import { INITIAL_VIEW_STATE } from './config';

interface TransitionView {
    target: number[];
    zoom: number;
    zoomX: number;
    zoomY: number;
    transitionInterpolator: LinearInterpolator;
}

describe('orthographic camera transitions', () => {
    it('supplies both zoom axes for point, bounds and reset transitions, including interrupted flights', () => {
        const setProps = vi.fn((properties: { initialViewState: TransitionView }) => properties);
        const deck = { width: 1000, height: 800, setProps };
        flyTo(deck, 20, 30, { zoom: 0 });
        flyToBounds(deck, { minX: 0, minY: 0, maxX: 300, maxY: 200 });
        resetView(deck);
        let previous: Pick<TransitionView, 'target' | 'zoom' | 'zoomX' | 'zoomY'> = { ...INITIAL_VIEW_STATE };
        expect(previous.zoomX).toBe(previous.zoom);
        expect(previous.zoomY).toBe(previous.zoom);
        expect(setProps).toHaveBeenCalledTimes(3);
        for (const [{ initialViewState: next }] of setProps.mock.calls) {
            expect(next.zoomX).toBe(next.zoom);
            expect(next.zoomY).toBe(next.zoom);
            const endpoints = next.transitionInterpolator.initializeProps(previous, next);
            const intermediate = next.transitionInterpolator.interpolateProps(endpoints.start, endpoints.end, 0.5);
            expect(intermediate.zoomX).toBeCloseTo((previous.zoomX + next.zoomX) / 2);
            expect(intermediate.zoomY).toBeCloseTo((previous.zoomY + next.zoomY) / 2);
            previous = { target: intermediate.target, zoom: intermediate.zoomX,
                zoomX: intermediate.zoomX, zoomY: intermediate.zoomY };
        }
    });
});
