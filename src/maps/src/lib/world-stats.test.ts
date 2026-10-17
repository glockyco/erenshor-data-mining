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
			// The fixture's Default template class is not a playable class.
			classes: 2,
            // Fourteen fixture item rows plus twelve loot-table fillers.
			// Stats count every item, not just the visible search representatives.
            items: 26,
			quests: 2
		});
	});
});
