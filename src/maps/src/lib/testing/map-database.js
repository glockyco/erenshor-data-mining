import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import initSqlJs from 'sql.js/dist/sql-wasm.js';
import sharp from 'sharp';

const SCHEMA_PATH = fileURLToPath(
	new URL('../../../tests/fixtures/map-database.sql', import.meta.url)
);

/**
 * Build the deterministic fixture database and matching item and portrait assets.
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
        database.run(await readFile(new URL('../../../tests/fixtures/item-provenance.sql', import.meta.url), 'utf8'));
		await writeFile(databasePath, database.export());
        const fixtureImage = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192"><defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#334155"/><stop offset="1" stop-color="#0f172a"/></linearGradient></defs><rect width="192" height="192" fill="url(#bg)"/><circle cx="96" cy="68" r="32" fill="#94a3b8"/><path d="M40 176c0-60 112-60 112 0" fill="#94a3b8"/></svg>');
        for (const { table, sizes } of [{ table: 'items', sizes: [20, 48] }, { table: 'characters', sizes: [96, 192] }]) {
            const imageDirectory = path.join(directory, 'assets', table);
            await mkdir(imageDirectory, { recursive: true });
            const statement = database.prepare(`SELECT DISTINCT image_hash FROM ${table} WHERE image_hash IS NOT NULL`);
            try {
                while (statement.step()) {
                    const hash = statement.getAsObject().image_hash;
                    if (typeof hash !== 'string') throw new Error('Fixture image hash must be text');
                    await Promise.all(sizes.map((size) => sharp(fixtureImage).resize(size, size).webp()
                        .toFile(path.join(imageDirectory, `${hash}.w${size}.webp`))));
                }
            } finally {
                statement.free();
            }
        }
	} finally {
		database.close();
	}
	return databasePath;
}
