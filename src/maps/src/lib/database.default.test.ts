import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('sql.js/dist/sql-wasm.js', () => ({
	default: vi.fn(async () => ({
		Database: class {
			close() {}
		}
	}))
}));

import { getBrowserRepository } from './database.default';

afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
});

describe('getBrowserRepository', () => {
	it('reports a failed download, then shares one download with every later consumer', async () => {
		const fetchMock = vi
			.fn()
			.mockResolvedValueOnce(new Response('Not Found', { status: 404 }))
			.mockResolvedValueOnce(new Response(new Uint8Array([1])));
		vi.stubGlobal('fetch', fetchMock);
		vi.stubGlobal('process', undefined);

		await expect(getBrowserRepository()).rejects.toThrow('/db/erenshor.sqlite failed with HTTP 404');

		const [first, second] = await Promise.all([getBrowserRepository(), getBrowserRepository()]);
		expect(second).toBe(first);
		expect(await getBrowserRepository()).toBe(first);
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(fetchMock).toHaveBeenLastCalledWith('/db/erenshor.sqlite');
	});
});
