import { describe, expect, it } from 'vitest';
import { formatSpawnLevels } from './map-markers';

describe('formatSpawnLevels', () => {
    it('says that a level following the player scales, whatever the prefab level', () => {
        const text = formatSpawnLevels([{ level: 1, levelMax: 1, levelScalesWithPlayer: true }]);
        expect(text).toMatch(/scales/i);
        expect(text).not.toMatch(/\d/);
    });

    it('gives the range of fixed levels', () => {
        expect(
            formatSpawnLevels([
                { level: 8, levelMax: 8, levelScalesWithPlayer: false },
                { level: 3, levelMax: 3, levelScalesWithPlayer: false }
            ])
        ).toBe('Level 3–8');
        expect(formatSpawnLevels([{ level: 42, levelMax: 42, levelScalesWithPlayer: false }])).toBe('Level 42');
    });

    it('leaves scaling prefab levels out of a mixed range', () => {
        const text = formatSpawnLevels([
            { level: 42, levelMax: 42, levelScalesWithPlayer: false },
            { level: 1, levelMax: 1, levelScalesWithPlayer: true }
        ]);
        expect(text).toMatch(/^Level 42\b/);
        expect(text).toMatch(/scales/i);
        expect(text).not.toMatch(/\b1\b/);
    });
});
