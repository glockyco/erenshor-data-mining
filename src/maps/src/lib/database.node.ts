import path from 'path';
import fs from 'fs/promises';
import { RepositoryBase } from '$lib/database.base';
import initSqlJs from 'sql.js/dist/sql-wasm.js';

export class Repository extends RepositoryBase {
	async init(dbPath = 'static/db/erenshor.sqlite') {
		if (!this.SQL) {
			this.SQL = await initSqlJs({
				locateFile: () => path.resolve('node_modules/sql.js/dist/sql-wasm.wasm')
			});
		}

		const dbFilePath = path.resolve(dbPath);
		const buffer = await fs.readFile(dbFilePath);

		this.db = new this.SQL.Database(new Uint8Array(buffer));
	}

	close() {
		this.db?.close();
		this.db = null;
	}
}
