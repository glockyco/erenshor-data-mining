import initSqlJs from 'sql.js/dist/sql-wasm.js';
import wasmUrl from 'sql.js/dist/sql-wasm.wasm?url';

import { RepositoryBase } from '$lib/database.base';

const DATABASE_URL = '/db/erenshor.sqlite';

class Repository extends RepositoryBase {
	async init(dbPath = DATABASE_URL) {
		if (!this.SQL) {
			this.SQL = await initSqlJs({
				locateFile: () => wasmUrl
			});
		}

		const isNode = typeof process !== 'undefined' && process.versions?.node;
		if (isNode) {
			throw new Error('Node.js logic not available in browser build. Use test helper for Node.');
		}

		const response = await fetch(dbPath);
		if (!response.ok) {
			throw new Error(`Map database request ${dbPath} failed with HTTP ${response.status}`);
		}
		this.db = new this.SQL.Database(new Uint8Array(await response.arrayBuffer()));
	}
}

let sharedRepository: Promise<RepositoryBase> | null = null;

/**
 * Returns the repository that every browser consumer on the page shares.
 *
 * The first call downloads and opens the database. Later calls reuse it, so a
 * popup does not download and parse the whole file again. A failed load is
 * not cached, and the next call tries again.
 */
export function getBrowserRepository(): Promise<RepositoryBase> {
	if (!sharedRepository) {
		const repository = new Repository();
		sharedRepository = repository.init().then(
			() => repository,
			(error: unknown) => {
				sharedRepository = null;
				throw error;
			}
		);
	}
	return sharedRepository;
}
