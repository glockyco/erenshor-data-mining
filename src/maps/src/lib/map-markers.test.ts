import { describe, expect, it } from 'vitest';
import { formatSpawnLevels } from './map-markers';

describe('formatSpawnLevels', () => {
    it('says that a level following the player scales, whatever the prefab level', () => {
        expect(formatSpawnLevels([{ level: 1, levelScalesWithPlayer: true }])).toBe(
            "Scales with the player's level"
        );
    });

    it('gives the range of fixed levels', () => {
        expect(
            formatSpawnLevels([
                { level: 8, levelScalesWithPlayer: false },
                { level: 3, levelScalesWithPlayer: false }
            ])
        ).toBe('Level 3–8');
        expect(formatSpawnLevels([{ level: 42, levelScalesWithPlayer: false }])).toBe('Level 42');
    });

    it('leaves scaling prefab levels out of a mixed range', () => {
        expect(
            formatSpawnLevels([
                { level: 42, levelScalesWithPlayer: false },
                { level: 1, levelScalesWithPlayer: true }
            ])
        ).toBe("Level 42, or scales with the player's level");
    });
});
