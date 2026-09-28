import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
	resolve: {
		alias: {
			$lib: path.resolve(__dirname, 'src/lib'),
		},
	},
	test: {
		// Playwright owns tests/e2e.
		include: ['src/**/*.test.ts'],
		globalSetup: ['./vitest.setup.ts'],
	},
});
