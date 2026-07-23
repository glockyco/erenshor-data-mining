import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import initSqlJs from 'sql.js/dist/sql-wasm.js';

const MAPS_DATABASE_PATH_ENV = 'ERENSHOR_MAPS_DATABASE_PATH';

export default async function setup() {
	const fixtureDirectory = await mkdtemp(path.join(tmpdir(), 'erenshor-maps-'));
	const databasePath = path.join(fixtureDirectory, 'map-database.sqlite');
	const schemaPath = path.resolve('tests/fixtures/map-database.sql');
	const previousDatabasePath = process.env[MAPS_DATABASE_PATH_ENV];

	try {
		const SQL = await initSqlJs({
			locateFile: () => path.resolve('node_modules/sql.js/dist/sql-wasm.wasm')
		});
		const database = new SQL.Database();
		try {
			database.run(await readFile(schemaPath, 'utf8'));
			await writeFile(databasePath, database.export());
		} finally {
			database.close();
		}
	} catch (error) {
		await rm(fixtureDirectory, { recursive: true, force: true });
		throw error;
	}

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
