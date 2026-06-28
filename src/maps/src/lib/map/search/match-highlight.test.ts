import { describe, it, expect } from 'vitest';
import { splitByMatchRange } from './match-highlight';

describe('splitByMatchRange', () => {
    it('splits a name into before/match/after segments', () => {
        const result = splitByMatchRange('Luminstone', [0, 5]);
        expect(result).toEqual([
            { text: 'Lumin', highlighted: true },
            { text: 'stone', highlighted: false }
        ]);
    });

    it('handles substring match in the middle', () => {
        const result = splitByMatchRange('Golden Luminstone Ring', [7, 17]);
        expect(result).toEqual([
            { text: 'Golden ', highlighted: false },
            { text: 'Luminstone', highlighted: true },
            { text: ' Ring', highlighted: false }
        ]);
    });

    it('returns single unhighlighted segment when range is null', () => {
        const result = splitByMatchRange('Luminstone', null);
        expect(result).toEqual([{ text: 'Luminstone', highlighted: false }]);
    });

    it('handles match at the end', () => {
        const result = splitByMatchRange('Luminstone', [5, 10]);
        expect(result).toEqual([
            { text: 'Lumin', highlighted: false },
            { text: 'stone', highlighted: true }
        ]);
    });

    it('returns full string highlighted when range covers all', () => {
        const result = splitByMatchRange('Lum', [0, 3]);
        expect(result).toEqual([{ text: 'Lum', highlighted: true }]);
    });
});
