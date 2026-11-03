import { expect, test as base, type Page } from '@playwright/test';

/**
 * Captured map tiles are outside the deterministic fixture.
 * Item icons and character portraits are generated alongside its database.
 */
const ASSETS_OUTSIDE_THE_FIXTURE = /^\/tiles\//;

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

async function gotoAfterFonts(page: Page, url: string) {
    // Hydration can start fonts after load. Replacing the document cancels them.
    await page.evaluate(() => document.fonts.ready);
    await page.goto(url);
}

test('home page renders fixture statistics and provenance', async ({ page }) => {
    await page.goto('/');

    // The fixture has two playable classes and the Default template class.
    await expect(page.getByText('two classes')).toBeVisible();
    // The footer provenance is a server load. A missing table fails every page
    // in the (app) group, so assert the rendered date.
    await expect(page.getByText('January 1, 2020')).toBeVisible();
});

test('home page keeps its FAQ visible without FAQ rich-result markup', async ({ page }) => {
    await page.goto('/');

    const types = await page.locator('script[type="application/ld+json"]').evaluateAll((scripts) =>
        scripts.map((script) => JSON.parse(script.textContent ?? '{}')['@type'])
    );
    expect(types).toEqual(['WebSite', 'WebApplication', 'VideoGame']);
    await expect(page.getByText('Where do I find a specific enemy, NPC, or vendor?', { exact: true })).toBeVisible();
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
    await expect(page.getByText('Fixture Relic', { exact: true })).toHaveCount(0);
    await expect(page.getByText('Requires Fixture Key', { exact: true })).toBeVisible();
    await expect(page.getByText(/^Only if you don't have/)).toHaveCount(0);
});

test('enemy search does not expose common-world swaps as character drops', async ({ page }) => {
    await page.goto('/map?sel=enemy:Fixture%20Enemy');
    await expect(page.getByRole('button', { name: 'Show all 2 spawn points', exact: true })).toBeVisible();
    await expect(page.getByText('Fixture Relic', { exact: true })).toHaveCount(0);
});

test('shared character portraits use density variants in search and spawn popups', async ({ page, request }) => {
    await page.goto('/map?sel=enemy:Fixture%20Enemy');
    const portrait = page.locator('img[src="/characters/fixture_enemy.w96.webp"]');
    await expect(portrait).toHaveCount(1);
    await expect(portrait).toHaveAttribute('srcset', '/characters/fixture_enemy.w96.webp 1x, /characters/fixture_enemy.w192.webp 2x');
    for (const size of [96, 192]) {
        const response = await request.get(`/characters/fixture_enemy.w${size}.webp`);
        expect(response.status()).toBe(200);
        expect(response.headers()['content-type']).toContain('image/webp');
    }
    await expect.poll(() => portrait.evaluate((image) => image instanceof HTMLImageElement && image.complete && image.naturalWidth > 0)).toBe(true);
    await gotoAfterFonts(page, '/map?sel=marker:spawn:stowaway-enemy');
    await expect(portrait).toHaveCount(1);
});

test('a character without a portrait leaves no image slot or wiki fallback', async ({ page }) => {
    await page.goto('/map?sel=npc:Breena%20Carpenter');
    await expect(page.getByRole('link', { name: 'Wiki', exact: true })).toHaveAttribute('href', 'https://erenshor.wiki.gg/wiki/Breena%20Carpenter');
    await expect(page.locator('img[src*="/characters/"], img[src*="wiki.gg"]')).toHaveCount(0);
    await gotoAfterFonts(page, '/map?sel=marker:spawn:stowaway-breena');
    await expect(page.getByText('Fixture Key', { exact: true })).toBeVisible();
    await expect(page.locator('img[src*="/characters/"], img[src*="wiki.gg"]')).toHaveCount(0);
});


test('vendor popup lists direct and quest-unlocked stock', async ({ page }) => {
    await page.goto('/map?sel=marker:spawn:stowaway-breena');

    await expect(page.getByText('Fixture Key', { exact: true })).toBeVisible();
    await expect(page.getByText('Enchanted Smithy', { exact: true })).toBeVisible();
    await expect(page.getByText('Requires Fixture Quest', { exact: true })).toHaveCount(1);
});

test('an item lists world drops alongside quest, crafting, use and starting sources', async ({ page }) => {
    await page.goto(`/map?sel=${encodeURIComponent('item:item:fixture relic')}`);

    await expect(page.getByText('Any enemy above level 30')).toBeVisible();
    await expect(page.getByText('0.05% per kill')).toBeVisible();
    const swapSource = page.getByText('Any enemy with common drops (0.9–8.1% per kill)', { exact: true });
    await expect(swapSource).toHaveCount(1);
    await expect(swapSource).toBeVisible();
    await expect(page.getByRole('button', { name: /Any enemy with common drops/ })).toHaveCount(0);
    await expect(page.getByText('Reward from', { exact: true })).toBeVisible();
    await expect(page.getByText('Crafting recipe', { exact: true })).toBeVisible();
    await expect(page.getByText('Obtained by using', { exact: true })).toBeVisible();
    await expect(page.getByText('Starting item of', { exact: true })).toBeVisible();
    await expect(page.getByText(/^All classes/)).toBeVisible();
    await expect(page.getByText('in Braxonian Desert', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: "Turn in to Breena Carpenter · Stowaway's Step" })).toBeVisible();
    const room = page.locator(`[data-source-keys='["ui:fixture"]']`);
    await expect(room.getByText('Requires the Wood Training Set in its room', { exact: true })).toBeVisible();
    await expect(room.getByText('Only before claiming your Reliquary', { exact: true })).toBeVisible();
    await expect(room.getByText('Requires Fixture Quest or the Paladin class', { exact: true })).toBeVisible();
    await expect(room.getByText('Requires level 10–35', { exact: true })).toBeVisible();
    await expect(room.getByRole('button', { name: /Enter from/ })).toBeVisible();
    await expect(room).not.toContainText('account_state');
    await expect(room).not.toContainText('reliquary_claimed');
    await expect(page.locator('[data-source-keys*="unconfirmed:fixture"], [data-source-keys*="internal:fixture"], [data-source-keys*="impossible:fixture"]')).toHaveCount(0);
    await expect(page.getByText('The map has no data on how to obtain this item.')).toHaveCount(0);
});

test('Auction House listings link both broker locations and retain an unlocated broker', async ({ page }) => {
    await page.goto(`/map?sel=${encodeURIComponent('item:item:fixture bag')}`);
    const auction = page.locator('[data-source-keys*="auction:"]').locator('..');
    await expect(auction).toContainText('Auction House');
    await expect(auction.locator('a[href="https://erenshor.wiki.gg/wiki/Auction%20House"]')).toHaveCount(1);
    // Overlapping simulated player windows of two routes read as one.
    await expect(auction.getByText('May be listed by simulated players of level 1–30, or while you are level 5–35', { exact: true })).toBeVisible();
    await expect(auction.getByText('Stock is random.', { exact: true })).toBeVisible();
    await expect(auction.getByText('Breena Carpenter')).toBeVisible();
    await expect(auction.getByText('Fixture Dummy')).toBeVisible();
    await expect(auction.getByText('Runtime Enemy')).toBeVisible();
    await expect(auction.getByText('Location unknown', { exact: true })).toHaveCount(1);
    await expect(auction).not.toContainText('gold');
    await expect(auction).not.toContainText('%');
    const locations = auction.getByRole('button', { name: "Stowaway's Step · 1 location", exact: true });
    await expect(locations).toHaveCount(2);
    for (let index = 0; index < 2; index++) {
        await locations.nth(index).hover();
        await locations.nth(index).click();
        await expect(page.locator('canvas').first()).toBeVisible();
    }
    await expect(page.getByText('The map has no data on how to obtain this item.')).toHaveCount(0);
});

test('dialog givers show their required quest and focus their location', async ({ page }) => {
    await page.goto(`/map?sel=${encodeURIComponent('item:item:fixture key')}`);
    await expect(page.getByText('Given by', { exact: true })).toBeVisible();
    await expect(page.getByText(/^Requires Fixture Quest/)).toBeVisible();
    const giver = page.getByRole('button', { name: 'Breena Carpenter · 1 location' });
    await expect(giver).toBeVisible();
    await giver.hover();
    await giver.click();
    await expect(page.locator('canvas').first()).toBeVisible();
});

test('item search shows possible treasure hunts and focuses their sites', async ({ page }) => {
    await page.goto(`/map?sel=${encodeURIComponent('item:item:fixture treasure')}`);
    await expect(page.getByText('Possible hunt locations, not chests present at every site.')).toBeVisible();
    // One heading per chest, with a row per zone below it.
    const tierLinks = page.locator('a[href="https://erenshor.wiki.gg/wiki/Lost%20Treasure%20(20-30)"]');
    await expect(tierLinks).toHaveCount(1);
    await expect(tierLinks.first().locator('..')).toContainText('Lost Treasure (20-30)');
    const site = page.getByRole('button', { name: /Stowaway's Step · level 21–29/ });
    await expect(site).toBeVisible();
    await site.click();
    const all = page.getByRole('button', { name: 'Show all 3 locations', exact: true });
    await expect(all).toBeVisible();
    await all.click();
    await expect(page.locator('canvas').first()).toBeVisible();
});

test('unlocated droppers and vendors retain wiki links but no focus buttons', async ({ page }) => {
    await page.goto(`/map?sel=${encodeURIComponent('item:item:fixture runtime')}`);
    await expect(page.getByText('Dropped by', { exact: true })).toBeVisible();
    await expect(page.getByText('Sold by', { exact: true })).toBeVisible();
    await expect(page.getByText(/Location unknown/)).toHaveCount(2);
    await expect(page.locator('a[href="https://erenshor.wiki.gg/wiki/Runtime%20Enemy"]')).toHaveCount(2);
    await expect(page.getByRole('button', { name: /^Show all/ })).toHaveCount(0);
    await expect(page.getByText('The map has no data on how to obtain this item.')).toHaveCount(0);
});

test('a representative scroll lists vendors of both item variants', async ({ page }) => {
    await page.goto(`/map?sel=${encodeURIComponent('item:item:fixture meditate')}`);
    await expect(page.getByText('Spell Scroll: Meditative Trance', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: /Breena Carpenter/ })).toBeVisible();
    const vendorWiki = page.locator('a[href="https://erenshor.wiki.gg/wiki/Runtime%20Enemy"]');
    await expect(vendorWiki).toBeVisible();
    await expect(vendorWiki.locator('..')).toContainText('Runtime Enemy');
    await expect(page.getByText('10 gold · Location unknown')).toBeVisible();
});

test('pure global catches appear once as Any water without masking enhanced local fishing rates', async ({ page }) => {
    await page.goto(`/map?sel=${encodeURIComponent('item:item:fixture fish')}`);
    const global = page.locator(`[data-source-keys='["fishing:bonus"]']`);
    await expect(global).toHaveCount(1);
    await expect(global).toContainText('Any water');
    await expect(global).toContainText('1% chance');
    await expect(global.getByRole('button')).toHaveCount(0);
    await expect(global).not.toContainText('Location unknown');
    const local = page.getByRole('button').filter({ hasText: '1 spot' });
    await expect(local).toContainText('7%–8% chance');
    expect(JSON.parse((await local.getAttribute('data-source-keys'))!).sort()).toEqual(['fishing:1', 'fishing:overlap-night']);
    await expect(page.getByText('Fishing bonus', { exact: true })).toHaveCount(0);
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
    await expect(page.getByText(/\bany level\b/)).toBeVisible();
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
    await expect(page.getByText(/at level 31 or higher/)).toBeVisible();
    await expect(page.getByRole('link', { name: 'Lost Treasure (30+)', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Lost Treasure (1-10)', exact: true })).toHaveCount(0);
    await expect(page.getByText('Level 27–36', { exact: false })).toHaveCount(3);
});

test('guardian links resolve every treasure site', async ({ page }) => {
    await page.goto('/map?sel=enemy:Ancient%20Horror');
    await expect(page.locator('canvas').first()).toBeVisible({ timeout: 20_000 });
    const all = page.getByRole('button', { name: 'Show all 3 dig sites', exact: true });
    await expect(all).toBeVisible();
    await all.click();
    await expect(page.locator('canvas').first()).toBeVisible();
});

test('the legacy zone popup includes the treasure encounter', async ({ page }) => {
    await page.goto('/maps/Stowaway?marker=treasure:stowaway-fixture');
    await expect(page.locator('.leaflet-popup-content')).toContainText('level 21 or higher');
    await expect(page.locator('.leaflet-popup-content')).toContainText('21–29: Lost Treasure (20-30)');
    await expect(page.locator('.leaflet-popup-content')).toContainText('Ancient Demon: Level 17–36');
});

test('stored return portals have no serialized Hidden destination in either map interface', async ({ page }) => {
    await page.goto(`/map?sel=${encodeURIComponent('marker:zone-line:reliquary-return')}`);
    const destination = page.getByText('Destination', { exact: true }).locator('..');
    await expect(destination).toContainText('Return to where you teleported from');
    await expect(destination).not.toContainText('Hidden');
    await expect(page.getByText('Enemy Levels', { exact: true })).toHaveCount(0);
    await expect(page.locator('a[href="/Hidden"], a[href="/maps/Hidden"]')).toHaveCount(0);
    await gotoAfterFonts(page, '/maps/Reliquary?marker=zone-line:reliquary-return');
    const popup = page.locator('.leaflet-popup-content');
    await expect(popup).toContainText('Return to where you teleported from');
    await expect(popup).not.toContainText('Hidden');
    await expect(popup.locator('a[href*="Hidden"]')).toHaveCount(0);
});

test("the overlay's live=1 connects to the mod on this PC and leaves the address clean", async ({ page }) => {
    const sockets: string[] = [];
    page.on('websocket', (socket) => sockets.push(socket.url()));

    await page.goto('/map?live=1');

    await expect.poll(() => sockets.some((url) => url.startsWith('ws://localhost:18585'))).toBe(true);
    await expect.poll(() => new URL(page.url()).search).toBe('');
    expect(await page.evaluate(() => localStorage.getItem('erenshor-map-live-mode'))).toBe('true');
});

test('a pairing link pairs this device and takes the pairing values out of the address', async ({ page }) => {
    const sockets: string[] = [];
    page.on('websocket', (socket) => sockets.push(socket.url()));
    // TEST-NET-1 address: the connection attempt never reaches a game.
    const pairing = `192.0.2.10:18586.ufrag1234.password12345678901234.${'ab'.repeat(32)}`;

    await page.goto(`/map#live=${pairing}`);

    await expect.poll(() => page.evaluate(() => localStorage.getItem('erenshor-map-live-pairing'))).toBe(pairing);
    expect(new URL(page.url()).hash).toBe('');
    await page.getByRole('button', { name: 'Live' }).click();
    await expect(page.getByTestId('live-panel')).toBeVisible();
    expect(sockets).toEqual([]);
});
