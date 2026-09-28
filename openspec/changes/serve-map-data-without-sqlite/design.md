## Context

See `proposal.md` for the motivation. The current data flow is:

- `RepositoryBase` (`src/maps/src/lib/database.base.ts`) holds every SQL query. `database.node.ts` runs it in Node during the build. `database.default.ts` runs it in the browser after it fetches `/db/erenshor.sqlite`.
- `/map` is prerendered. `map-world-data.server.ts` builds all markers, search inputs, and item sources in Node. Only two popup components use the browser repository: `SpawnPointPopupContent` (`getDropsForCharacters`, `getVendorItems`) and `LiveNpcPopupContent` (`getCharactersByName`, `getDropsForCharacters`).
- `getItemSources` already returns every drop row and every vendor row (including the quest-unlock union) for items with `items.is_map_visible = 1`, for all characters. `/map` ships these rows as `data.itemSources` for the item search.
- `/maps/[mapName]` is prerendered as an empty shell. Its `+page.ts` returns only `mapName`. The browser then calls `getZoneNorthBearing` and the twelve zone marker queries.
- `src/maps/src/service-worker.ts` precaches the database at install, serves it cache-first, and keeps it in `db-cache-${version}`.
- `maps dev` and `maps build` link the variant database to `src/maps/static/db/erenshor.sqlite` through `DatabaseLinkTransaction`. adapter-static copies it into the build, which is how the file is published today. `maps build` also sets `ERENSHOR_MAPS_DATABASE_PATH`, which `database-path.server.ts` reads.
- The maps leaf runs `pnpm run lint`, `pnpm run check`, `pnpm run test`, and `node scripts/test-prerender.mjs` in parallel. The prerender script builds the site from `tests/fixtures/map-database.sql` and checks HTML text. `@playwright/test` 1.62.1 is locked, but no browser test exists.
- `robots.txt` and `sitemap.xml` are prerendered `+server.ts` routes.

Measurements from the current main database:

- Of the 4,058 drop rows and 446 vendor rows for map-visible representative characters, 2 involve items that `mapping.json` hides from the map: "A Golden Ticket (1)" (A Golden Spirit) and "Spell Scroll: Meditative Trance (2)" (Tiver Banes).
- A display-name index of the 930 map-visible representatives (881 names, 38 shared) is 63 KB raw and 13.8 KB with brotli.

## Goals / Non-Goals

**Goals:**

- No page downloads the database, and `sql.js` leaves the client bundle.
- The database stays published at the same URL for consumers outside the site.
- The spawn popup, the live-entity popup, and the zone pages show the same data as before, except for the items that the mapping hides.
- A browser test protects the change before and after the cutover.
- Every interface that shipped companion mods use keeps working: the `/map` document on both hosts, its `layers` and `sel` parameters with all keys that earlier versions wrote, the WebSocket protocols on ports 18584 and 18585, and `/db/erenshor.sqlite`. Commit `f08efcc4` restored the `spr` and `spu` layer keys after the encounter tier change had dropped them.

**Non-Goals:**

- Reducing the prerendered `/map` marker payload.
- Compressing or removing the published database.
- Changing the tile precache, the companion WebSocket protocols, or the Worker topology.

## Decisions

### D1. Publish the database from a prerendered route, and stop all browser use of it

Add `src/maps/src/routes/db/erenshor.sqlite/+server.ts` with `prerender = true`. Its `GET` handler returns the bytes of the file at `ERENSHOR_MAPS_DATABASE_PATH` with the `application/vnd.sqlite3` content type. SvelteKit's prerenderer writes the response body unchanged, so the build contains the exact file. `maps dev` serves the same route from the live file.

The three browser consumers, the service worker precache, and the service worker `.sqlite` branch are removed.

Alternatives:

- Keep the static symlink for publication. This is the smallest change, but the commands keep mutating the source tree during a build. Rejected.
- Copy the file into the build directory after the SvelteKit build. `vite preview` and `maps dev` would not serve it, so the local and deployed sites would differ. Rejected.
- Stop only the service worker precache. The zone pages would still download 9.7 MB each. Rejected.

### D2. Zone pages load their markers in a prerendered server load

Replace `routes/maps/[mapName]/+page.ts` with a `+page.server.ts` that keeps `entries()` and `prerender = true`. It opens the Node repository, returns the north bearing and the twelve marker arrays that the page requests today, and closes the repository, as the other server loads do. The page reads them from `data` and keeps its Leaflet code unchanged.

The existing repository methods already return the local-coordinate objects that Leaflet uses. Reusing them keeps the zone pages identical and needs no new query.

Alternative: derive zone markers from the `/map` world data. The world markers use transformed world coordinates and different shapes. Rejected.

### D3. Popups use the item-source data that `/map` already ships

A pure module `src/maps/src/lib/map/character-details.ts` builds two indexes once from `data.itemSources`: drops by character stable key, ordered by probability descending and then by item name, and vendor stock by character stable key, ordered by item name. The spawn popup reads them synchronously.

`buildMapWorldData` adds one field, `charactersByName`: for each display name, the map-visible representative characters with that name and the scenes where a member of their deduplication group is placed. The query uses the same representative rule as `getCharactersByName`. A pure function `resolveLiveCandidates(charactersByName, name, scene)` keeps the preference for characters placed in the live scene and the fallback to all matches.

This makes the popups follow `items.is_map_visible`, like the item search. The two affected rows are items that the mapping hides on purpose.

Alternatives:

- A separate prerendered popup document, fetched on first use. It duplicates data that the page already has and adds loading, error, and retry states. Rejected.
- Derive the name index on the client from the marker data. The markers omit unplaced friendly characters and zero-chance placements, so the result would differ from the current query. Rejected.

### D4. The build input is an explicit path

`database-path.server.ts` loses its default and fails when `ERENSHOR_MAPS_DATABASE_PATH` is not set. `maps dev` sets the variable for Vite, as `maps build` already does. `DatabaseLinkTransaction`, `_get_maps_db_path`, the `maps.database_dir` configuration key, and its schema field are removed. `generate-item-icons.mjs` reads the same variable.

`maps build` gets a precondition that fails when `src/maps/static` contains a `.sqlite` file or link. A stale link would shadow the D1 route in `maps dev` and collide with it in the build. The error names the path. The command does not delete the path itself, because commands must not change the source tree.

### D5. The service worker drops the database cache

Remove `DB_CACHE_NAME`, `precacheDatabase`, and the `.sqlite` fetch branch. The `activate` handler already deletes every cache whose name is not in its keep list. With only the tiles cache in that list, it deletes old `db-cache-*` caches.

### D6. The browser smoke test uses the Playwright test runner

Add `src/maps/playwright.config.ts` and specs under `src/maps/tests/e2e/`. The `webServer` option runs `scripts/serve-fixture-site.mjs`, which creates the fixture database, builds the site into temporary directories as `test-prerender.mjs` does today, and starts Vite's `preview()` server. `test-prerender.mjs` is removed, and its HTML assertions move into the specs, so the fixture site builds once. The maps leaf runs `pnpm run test:e2e` in place of the prerender command.

The specs check:

- `/`, `/map`, and `/maps/Stowaway` raise no `pageerror` and have no failed same-origin request. Tiles under `/tiles/` and item icons under `/items/` are captured or generated assets that a CI fixture build does not contain, so they are exempt. Aborted requests are cancellations, not failures. Requests to `ws://localhost:18584` and `:18585` are cross-origin companion sockets.
- `/map` has a canvas with a non-zero size.
- `/map?sel=marker:spawn:stowaway-enemy` shows the fixture enemy's drops, and `/map?sel=marker:spawn:stowaway-breena` shows the fixture vendor stock.
- `/maps/Stowaway?marker=spawn:stowaway-enemy` opens the Leaflet popup of the fixture enemy.
- `/map?layers=-sp,-spr,-spu,-npc`, the query that shipped overlays load, hides the enemy, elite, boss, and NPC layers.
- `/db/erenshor.sqlite` returns a body that starts with `SQLite format 3`.
- After the cutover, a context-level request listener fails the run on any page or service worker request for a URL that ends in `.sqlite`.

Assertions use Playwright's auto-waiting `expect`, not fixed delays. Traces are kept on failure.

The fixture gets one `character_vendor_items` row, so that the vendor check covers vendor stock and the quest-unlock union.

The maps preflight resolves `chromium.executablePath()` from the locked `playwright` package and checks that the file exists. The failure message names `pnpm --dir src/maps exec playwright install chromium`. The Python Playwright preflight is not reused, because the Python package can lock a different browser revision. CI adds one step before the maps leaf: `nix develop --command pnpm --dir src/maps exec playwright install --with-deps chromium`.

## Risks / Trade-offs

- [An open tab from before the deploy still uses the old popup code] → The old code fetches the database, which stays published, so it keeps working until the next navigation.
- [`charactersByName` adds about 14 KB with brotli to `/map`] → This is about 2.7% of the current payload and removes a 9.7 MB download.
- [The Chromium download makes the CI maps job slower and adds a network dependency] → The version is locked by `pnpm-lock.yaml`. A failed download fails the job loudly before the leaf runs.
- [`maps dev` serves server loads from the file at request time] → A restart is not necessary after a database rebuild, but an open page shows the old data until it reloads.
- [A local `src/maps/static/db` link from the old workflow shadows or collides with the database route] → D4's precondition stops the build and names the path.

## Migration Plan

1. Move publication to the D1 route and pass the database path explicitly (D4). The browser keeps fetching `/db/erenshor.sqlite`, now from the route. This comes first because the fixture build in CI has no static database file: only the route lets a fixture build serve its database to the current popups.
2. Land the browser smoke test. It passes on the code of step 1.
3. Land the zone page prerender and the popup data change. Each keeps the page output the same, except for the two hidden items, and the smoke test passes after each.
4. Remove the browser database and the service worker cache. Add the `.sqlite` request check in the same commit.
5. Run `maps build`, check the preview in a browser, and run `maps deploy`.

Rollback: revert the cutover commits, run `maps build`, and run `maps deploy`. No data migration is involved.

## Open Questions

- Does any consumer outside the site use `/db/erenshor.sqlite`? After the cutover the site never requests it, so every request in the Cloudflare analytics for that path comes from an outside consumer. That data can decide later whether to compress, move, or remove the file. The answer does not change this change.
