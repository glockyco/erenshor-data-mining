import { describe, expect, it } from 'vitest';
import { computeScaleBarState, formatScaleLabel } from './scale-bar';

describe('computeScaleBarState', () => {
    it('chooses the largest readable Erenshor-unit distance that fits the measured pixels', () => {
        expect(computeScaleBarState({ measuredUnits: 312, maxWidthPx: 120 })).toEqual({
            units: 250,
            widthPx: 96.15,
            label: '250 units'
        });

        expect(computeScaleBarState({ measuredUnits: 118, maxWidthPx: 120 })).toEqual({
            units: 100,
            widthPx: 101.69,
            label: '100 units'
        });
    });

    it('uses decimal units when zoomed in past one coordinate unit', () => {
        expect(computeScaleBarState({ measuredUnits: 0.78, maxWidthPx: 120 })).toEqual({
            units: 0.5,
            widthPx: 76.92,
            label: '0.5 units'
        });
    });

    it('returns null for invalid measurements instead of showing stale scale data', () => {
        for (const measuredUnits of [0, -1, Number.NaN, Number.POSITIVE_INFINITY]) {
            expect(computeScaleBarState({ measuredUnits, maxWidthPx: 120 })).toBeNull();
        }

        expect(computeScaleBarState({ measuredUnits: 100, maxWidthPx: 0 })).toBeNull();
    });
});

describe('formatScaleLabel', () => {
    it('formats labels only in Erenshor coordinate units', () => {
        expect(formatScaleLabel(1000)).toBe('1,000 units');
        expect(formatScaleLabel(2.5)).toBe('2.5 units');
    });
});
