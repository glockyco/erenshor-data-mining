import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { Repository } from './database.node';

let db: Repository;

beforeAll(async () => {
    db = new Repository();
    await db.init();
});

afterAll(() => {
    db.close();
});

describe('getWorldStats', () => {
    it('returns positive integer counts for each world table', () => {
        const stats = db.getWorldStats();
        for (const key of ['zones', 'classes', 'items', 'quests'] as const) {
            expect(Number.isInteger(stats[key])).toBe(true);
            expect(stats[key]).toBeGreaterThan(0);
        }
    });

    // Stable cross-field invariants that catch a wrong-table bug without
    // coupling to volatile exact counts (which change every game patch).
    it('counts the intended tables', () => {
        const stats = db.getWorldStats();
        expect(stats.items).toBeGreaterThan(stats.zones);
        expect(stats.quests).toBeGreaterThan(stats.classes);
    });
});
