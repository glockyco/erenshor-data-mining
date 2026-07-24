import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import { createMapDatabaseFixture } from './src/lib/testing/map-database.js';

const MAPS_DATABASE_PATH_ENV = 'ERENSHOR_MAPS_DATABASE_PATH';

export default async function setup() {
	const fixtureDirectory = await mkdtemp(path.join(tmpdir(), 'erenshor-maps-'));
	let databasePath: string;
	try {
		databasePath = await createMapDatabaseFixture(fixtureDirectory);
	} catch (error) {
		await rm(fixtureDirectory, { recursive: true, force: true });
		throw error;
	}

	const previousDatabasePath = process.env[MAPS_DATABASE_PATH_ENV];
	process.env[MAPS_DATABASE_PATH_ENV] = databasePath;

	return async () => {
		if (previousDatabasePath === undefined) {
			delete process.env[MAPS_DATABASE_PATH_ENV];
		} else {
			process.env[MAPS_DATABASE_PATH_ENV] = previousDatabasePath;
		}
		await rm(fixtureDirectory, { recursive: true, force: true });
	};
}
