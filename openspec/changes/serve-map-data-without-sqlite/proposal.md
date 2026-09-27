## Why

Every first visit to the map site downloads the complete clean database. SvelteKit registers the service worker on every page, and the service worker precaches `/db/erenshor.sqlite` at install. In production that file is 9,662,464 bytes, served without compression and with `max-age=0`. The per-zone pages also load the database eagerly, and the `/map` popups load it on first use. The prerendered `/map` data is not the problem: it is 7.1 MB raw but 508 KB with brotli.

The browser uses the database for only three things: the per-zone marker queries, the spawn-point popup details (drops and vendor stock), and the live-entity popup (name resolution and drops). The build can compute all of these ahead of time.

No test opens the site in a browser today. The maps CI leaf checks prerendered HTML text only. It cannot detect a runtime request, a broken popup, or a page error. The cutover must not ship without that check.

## What Changes

- Add a browser smoke test to the `test maps` leaf. It serves the fixture-prerendered build and loads `/`, `/map` and `/maps/Stowaway` in Chromium. It checks rendered content, a spawn popup, and page errors. It lands first and passes on the current code.
- Prerender the per-zone marker data and the zone north bearing into each `/maps/[mapName]` page. The page stops querying a database in the browser.
- Prerender one popup-detail document for `/map`: drops and vendor stock for each map-visible character, and a display-name index for the live-entity popup. The popups fetch it once, on first use.
- **BREAKING** Stop publishing `/db/erenshor.sqlite`. The build output contains no database file. The service worker stops precaching it and deletes the old database cache.
- **BREAKING** `maps dev` and `maps build` stop linking the clean database into `src/maps/static/db/`. They pass the database path to the build through `ERENSHOR_MAPS_DATABASE_PATH`. The `maps.database_dir` configuration key is removed.
- Remove the browser database loader and the browser `sql.js` bundle. The build keeps `sql.js` in Node.
- After the cutover, the smoke test also fails when any page requests a `.sqlite` file.

## Capabilities

### New Capabilities

- `map-site-data`: How the map site delivers game data to the browser. It covers prerendered route data, the popup-detail document, the absence of a published database, and the build input path.
- `map-browser-verification`: The browser smoke test in the maps CI leaf, its fixture, its assertions, and its Chromium precondition.

### Modified Capabilities

- `refresh-session-lifecycle`: The requirement "Commands restore mutable state that they replace" is removed. Its only subject was the `maps dev` database link, which this change deletes.

## Impact

- Map site: `src/maps/src/routes/maps/[mapName]/`, `src/maps/src/routes/map/`, `src/maps/src/lib/components/map/popups/SpawnPointPopupContent.svelte`, `src/maps/src/lib/components/map/popups/LiveNpcPopupContent.svelte`, `src/maps/src/lib/database.default.ts` (removed), `src/maps/src/lib/database.node.ts`, `src/maps/src/lib/database-path.server.ts`, `src/maps/src/service-worker.ts`, `src/maps/src/legacy-worker.test.ts`, `src/maps/scripts/generate-item-icons.mjs`, `src/maps/scripts/test-prerender.mjs`, `src/maps/README.md`, `src/maps/.gitignore`.
- CLI and configuration: `src/erenshor/cli/commands/maps.py` (`DatabaseLinkTransaction` removed), `src/erenshor/cli/commands/test.py` (maps preflight and leaf), `src/erenshor/cli/preconditions/decorator.py`, `src/erenshor/infrastructure/config/schema.py`, `config.toml`, and the related unit and contract tests.
- CI: `.github/workflows/ci.yml` installs Playwright Chromium for the maps job.
- Documentation: the `interactive-map` and `refreshing-game-data` skills and the incident log.
- Hosting: the next `maps deploy` deletes `/db/erenshor.sqlite` from both Worker services. The companion mod is not affected. It loads `/map` and receives live data over WebSocket.
- Non-goals: the size of the prerendered `/map` markers, the tile precache, and the WebSocket protocols.
