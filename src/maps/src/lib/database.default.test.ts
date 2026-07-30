import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('sql.js/dist/sql-wasm.js', () => ({
	default: vi.fn(async () => ({
		Database: class {
			close() {}
		}
	}))
}));

import { Repository } from './database.default';

afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
});

describe('browser Repository', () => {
	it('loads the database from the site root on nested routes', async () => {
		const fetchMock = vi.fn(async () => new Response(new Uint8Array([1])));
		vi.stubGlobal('fetch', fetchMock);
		vi.stubGlobal('process', undefined);

		const repository = new Repository();
		await repository.init();

		expect(fetchMock).toHaveBeenCalledOnce();
		expect(fetchMock).toHaveBeenCalledWith('/db/erenshor.sqlite');
	});
});
