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
			items: 6,
			quests: 2
		});
	});
});
