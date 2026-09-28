import { defineConfig, devices } from '@playwright/test';

const PORT = 4179;

/**
 * Browser smoke test of the fixture site. `scripts/serve-fixture-site.mjs`
 * builds the site from the deterministic map fixture and serves the build.
 */
export default defineConfig({
    testDir: 'tests/e2e',
    forbidOnly: Boolean(process.env.CI),
    reporter: 'list',
    use: {
        baseURL: `http://127.0.0.1:${PORT}`,
        trace: 'retain-on-failure'
    },
    projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
    webServer: {
        command: `node scripts/serve-fixture-site.mjs ${PORT}`,
        url: `http://127.0.0.1:${PORT}/`,
        reuseExistingServer: false,
        timeout: 300_000,
        gracefulShutdown: { signal: 'SIGTERM', timeout: 10_000 },
        stdout: 'pipe'
    }
});
