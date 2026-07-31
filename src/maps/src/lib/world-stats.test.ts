import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { getMapsDatabasePath } from './database-path.server';
import { Repository } from './database.node';
import { MAPS } from './maps';

let db: Repository;

beforeAll(async () => {
	db = new Repository();
	await db.init(getMapsDatabasePath());
});

afterAll(() => {
	db.close();
});

describe('getWorldStats', () => {
	it('counts the intended fixture tables', () => {
		expect(db.getWorldStats()).toEqual({
			zones: Object.keys(MAPS).length,
			classes: 2,
			// Six wiki-backed items plus the twelve loot-table fillers that exercise
			// an uncapped drop list and a name shared by two characters. This counts
			// every item row, not just searchable ones, so the fillers show up here
			// and nowhere else.
			items: 18,
			quests: 2
		});
	});
});
