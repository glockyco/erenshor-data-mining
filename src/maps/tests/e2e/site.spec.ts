import { expect, test as base } from '@playwright/test';

/**
 * Map tiles and item icons are captured or generated assets that the fixture
 * build does not contain, so a request for one is not a site failure.
 */
const ASSETS_OUTSIDE_THE_FIXTURE = /^\/(tiles|items)\//;

/** Every test fails on an uncaught page error or a failed same-origin request. */
const test = base.extend<{ pageProblems: string[] }>({
    pageProblems: [
        async ({ page, baseURL }, use) => {
            const origin = new URL(baseURL!).origin;
            const problems: string[] = [];
            const isChecked = (url: string) => {
                const parsed = new URL(url);
                return parsed.origin === origin && !ASSETS_OUTSIDE_THE_FIXTURE.test(parsed.pathname);
            };

            page.on('pageerror', (error) => problems.push(`${page.url()}: ${error.message}`));
            page.on('requestfailed', (request) => {
                const reason = request.failure()?.errorText;
                // A navigation or a zoom cancels requests. That is not a failure.
                if (reason !== 'net::ERR_ABORTED' && isChecked(request.url())) {
                    problems.push(`${request.url()}: ${reason}`);
                }
            });
            page.on('response', (response) => {
                if (response.status() >= 400 && isChecked(response.url())) {
                    problems.push(`${response.url()}: HTTP ${response.status()}`);
                }
            });

            await use(problems);
            expect(problems).toEqual([]);
        },
        { auto: true }
    ]
});

test('home page renders fixture statistics and provenance', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByText('two classes')).toBeVisible();
    // The footer provenance is a server load. A missing table fails every page
    // in the (app) group, so assert the rendered date.
    await expect(page.getByText('January 1, 2020')).toBeVisible();
});

test('world map draws its canvas from prerendered fixture data', async ({ page, request }) => {
    const html = await (await request.get('/map')).text();
    expect(html).toContain('Fixture Enemy');

    await page.goto('/map');

    const canvas = page.locator('canvas').first();
    await expect(canvas).toBeVisible();
    const box = await canvas.boundingBox();
    expect(box?.width).toBeGreaterThan(0);
    expect(box?.height).toBeGreaterThan(0);
});

test('spawn popup lists the fixture drops', async ({ page }) => {
    await page.goto('/map?sel=marker:spawn:stowaway-enemy');

    await expect(page.getByText('Fixture Drop', { exact: true })).toBeVisible();
});

test('vendor popup lists direct and quest-unlocked stock', async ({ page }) => {
    await page.goto('/map?sel=marker:spawn:stowaway-breena');

    await expect(page.getByText('Fixture Key', { exact: true })).toBeVisible();
    await expect(page.getByText('Enchanted Smithy', { exact: true })).toBeVisible();
});

test('the layers query that shipped overlays load hides every spawn layer', async ({ page }) => {
    await page.goto('/map?layers=-sp%2C-spr%2C-spu%2C-npc');

    for (const layer of ['Enemy', 'Elite', 'Boss', 'NPCs']) {
        await expect(page.getByRole('checkbox', { name: layer, exact: true }), layer).not.toBeChecked();
    }
});

test('zone map shows fixture spawn points', async ({ page, request }) => {
    const html = await (await request.get('/maps/Stowaway')).text();
    expect(html).toContain("Stowaway's Step");

    await page.goto('/maps/Stowaway?marker=spawn:stowaway-enemy');

    await expect(page.locator('.leaflet-popup-content')).toContainText('Fixture Enemy');
});

test('the clean database is published unchanged', async ({ request }) => {
    const response = await request.get('/db/erenshor.sqlite');

    expect(response.status()).toBe(200);
    const header = new TextDecoder().decode((await response.body()).subarray(0, 16));
    expect(header).toBe('SQLite format 3\0');
});
