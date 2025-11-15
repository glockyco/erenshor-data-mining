import initSqlJs from 'sql.js/dist/sql-wasm.js';
import wasmUrl from 'sql.js/dist/sql-wasm.wasm?url';

import { RepositoryBase } from '$lib/database.base';

export class Repository extends RepositoryBase {
	async init(dbPath = 'db/erenshor.sqlite') {
		if (!this.SQL) {
			this.SQL = await initSqlJs({
				locateFile: () => wasmUrl
			});
		}

		let buffer: ArrayBuffer | Uint8Array;

		const isNode = typeof process !== 'undefined' && process.versions?.node;

		if (isNode) {
			throw new Error('Node.js logic not available in browser build. Use test helper for Node.');
		} else {
			const response = await fetch(dbPath);
			buffer = await response.arrayBuffer();
		}

		this.db = new this.SQL.Database(new Uint8Array(buffer));
	}

	close() {
		this.db?.close();
		this.db = null;
	}
}
