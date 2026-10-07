import { expect, test as base } from '@playwright/test';

/**
 * Map tiles, item icons, and character portraits are captured or generated assets
 * that the fixture build does not contain, so a request for one is not a site failure.
 */
const ASSETS_OUTSIDE_THE_FIXTURE = /^\/(tiles|items|characters)\//;

/**
 * Every test fails on an uncaught page error, a failed same-origin request, or
 * any page or service worker request for a database file. The site publishes
 * the database for other consumers but never downloads it itself.
 */
const test = base.extend<{ pageProblems: string[] }>({
    pageProblems: [
        async ({ context, page, baseURL }, use) => {
            const origin = new URL(baseURL!).origin;
            const problems: string[] = [];
            const isChecked = (url: string) => {
                const parsed = new URL(url);
                return parsed.origin === origin && !ASSETS_OUTSIDE_THE_FIXTURE.test(parsed.pathname);
            };

            // The context also reports requests that the service worker makes.
            context.on('request', (request) => {
                if (new URL(request.url()).pathname.endsWith('.sqlite')) {
                    problems.push(`${request.url()}: the site must not download the database`);
                }
            });
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

    // The canvas stays hidden until deck.gl has measured it and drawn the
    // fitted view. A cold WebGL start on a busy machine can exceed the
    // default five seconds.
    const canvas = page.locator('canvas').first();
    await expect(canvas).toBeVisible({ timeout: 20_000 });
    const box = await canvas.boundingBox();
    expect(box?.width).toBeGreaterThan(0);
    expect(box?.height).toBeGreaterThan(0);
});

test('spawn popup lists the fixture drops', async ({ page }) => {
    await page.goto('/map?sel=marker:spawn:stowaway-enemy');

    await expect(page.getByText('Fixture Drop', { exact: true })).toBeVisible();
});

test('shared character portraits use density variants in search and spawn popups', async ({ page }) => {
    await page.goto('/map?sel=enemy:Fixture%20Enemy');
    const portrait = page.locator('img[src="/characters/fixture_enemy.w96.webp"]');
    await expect(portrait).toHaveCount(1);
    await expect(portrait).toHaveAttribute('srcset', '/characters/fixture_enemy.w96.webp 1x, /characters/fixture_enemy.w192.webp 2x');
    await page.goto('/map?sel=marker:spawn:stowaway-enemy');
    await expect(portrait).toHaveCount(1);
});

test('a character without a portrait leaves no image slot or wiki fallback', async ({ page }) => {
    await page.goto('/map?sel=npc:Breena%20Carpenter');
    await expect(page.getByRole('link', { name: 'Wiki', exact: true })).toHaveAttribute('href', 'https://erenshor.wiki.gg/wiki/Breena%20Carpenter');
    await expect(page.locator('img[src*="/characters/"], img[src*="wiki.gg"]')).toHaveCount(0);
    await page.goto('/map?sel=marker:spawn:stowaway-breena');
    await expect(page.getByText('Fixture Key', { exact: true })).toBeVisible();
    await expect(page.locator('img[src*="/characters/"], img[src*="wiki.gg"]')).toHaveCount(0);
});


test('vendor popup lists direct and quest-unlocked stock', async ({ page }) => {
    await page.goto('/map?sel=marker:spawn:stowaway-breena');

    await expect(page.getByText('Fixture Key', { exact: true })).toBeVisible();
    await expect(page.getByText('Enchanted Smithy', { exact: true })).toBeVisible();
});

test('an item that only world drops yield shows its world drop source', async ({ page }) => {
    await page.goto(`/map?sel=${encodeURIComponent('item:item:fixture relic')}`);

    await expect(page.getByText('Any enemy above level 30')).toBeVisible();
    await expect(page.getByText('0.05% per kill')).toBeVisible();
    await expect(page.getByText('The map has no data on how to obtain this item.')).toHaveCount(0);
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

test('a wiki chest link highlights only eligible treasure sites and opens their encounter', async ({ page }) => {
    await page.goto('/map?sel=enemy:Lost%20Treasure%20(1-10)');
    await expect(page.getByRole('button', { name: 'Show all 1 dig site', exact: true })).toBeVisible();
    await expect(page.getByText('Hidden Hills', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Dig site 1 · Guardians 2–36', exact: true }).click();
    await expect(page.getByText('Reading level: any level', { exact: true })).toBeVisible();
    for (const name of ['Lost Treasure (1-10)', 'Lost Treasure (10-20)', 'Lost Treasure (20-30)', 'Lost Treasure (30+)']) {
        await expect(page.getByRole('link', { name, exact: true })).toBeVisible();
    }
    for (const name of ['Ancient Skeleton', 'Ancient Horror', 'Ancient Demon']) {
        await expect(page.getByRole('link', { name, exact: true })).toHaveAttribute('href', `https://erenshor.wiki.gg/wiki/${encodeURIComponent(name)}`);
    }
    await expect(page.getByText('1–9:', { exact: false })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Treasure Hunting', exact: true })).toBeVisible();
});

test('a high-reading-level dig site only offers reachable chests', async ({ page }) => {
    await page.goto('/map?sel=marker:treasure:blight-fixture');
    await expect(page.getByText('Reading level: 31 or higher', { exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Lost Treasure (30+)', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Lost Treasure (1-10)', exact: true })).toHaveCount(0);
    await expect(page.getByText('Level 27–36', { exact: false })).toHaveCount(3);
});

test('guardian links resolve every treasure site', async ({ page }) => {
    await page.goto('/map?sel=enemy:Ancient%20Horror');
    await expect(page.getByRole('button', { name: 'Show all 3 dig sites', exact: true })).toBeVisible();
});

test('the legacy zone popup includes the treasure encounter', async ({ page }) => {
    await page.goto('/maps/Stowaway?marker=treasure:stowaway-fixture');
    await expect(page.locator('.leaflet-popup-content')).toContainText('Reading level: 21 or higher');
    await expect(page.locator('.leaflet-popup-content')).toContainText('21–29: Lost Treasure (20-30)');
    await expect(page.locator('.leaflet-popup-content')).toContainText('Ancient Demon: Level 17–36');
});

test('the clean database is published unchanged', async ({ request }) => {
    const response = await request.get('/db/erenshor.sqlite');

    expect(response.status()).toBe(200);
    const header = new TextDecoder().decode((await response.body()).subarray(0, 16));
    expect(header).toBe('SQLite format 3\0');
});
