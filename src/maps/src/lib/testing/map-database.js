import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import initSqlJs from 'sql.js/dist/sql-wasm.js';

const SCHEMA_PATH = fileURLToPath(
	new URL('../../../tests/fixtures/map-database.sql', import.meta.url)
);

/**
 * Build the deterministic map fixture database inside a caller-owned directory.
 *
 * @param {string} directory
 * @returns {Promise<string>}
 */
export async function createMapDatabaseFixture(directory) {
	const databasePath = path.join(directory, 'map-database.sqlite');
	const SQL = await initSqlJs({
		locateFile: () => fileURLToPath(new URL('../../../node_modules/sql.js/dist/sql-wasm.wasm', import.meta.url))
	});
	const database = new SQL.Database();
	try {
		database.run(await readFile(SCHEMA_PATH, 'utf8'));
		await writeFile(databasePath, database.export());
	} finally {
		database.close();
	}
	return databasePath;
}
