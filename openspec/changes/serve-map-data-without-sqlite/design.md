## Context

See `proposal.md` for the motivation. The current data flow is:

- `RepositoryBase` (`src/maps/src/lib/database.base.ts`) holds every SQL query. `database.node.ts` runs it in Node during the build. `database.default.ts` runs it in the browser after it fetches `/db/erenshor.sqlite`.
- `/map` is prerendered. `map-world-data.server.ts` builds all markers, search inputs, and item sources in Node. Only two popup components use the browser repository: `SpawnPointPopupContent` (`getDropsForCharacters`, `getVendorItems`) and `LiveNpcPopupContent` (`getCharactersByName`, `getDropsForCharacters`).
- `/maps/[mapName]` is prerendered as an empty shell. Its `+page.ts` returns only `mapName`. The browser then calls `getZoneNorthBearing` and the twelve zone marker queries.
- `src/maps/src/service-worker.ts` precaches the database at install, serves it cache-first, and keeps it in `db-cache-${version}`.
- `maps dev` and `maps build` link the variant database to `src/maps/static/db/erenshor.sqlite` through `DatabaseLinkTransaction`. `maps build` also sets `ERENSHOR_MAPS_DATABASE_PATH`, which `database-path.server.ts` reads. Its default is the linked static path.
- The maps leaf runs `pnpm run lint`, `pnpm run check`, `pnpm run test`, and `node scripts/test-prerender.mjs` in parallel. The prerender script builds the site from `tests/fixtures/map-database.sql` into a temporary directory and checks HTML text. `@playwright/test` 1.62.1 is locked, but no browser test exists.

Row counts in the current main database: 5,111 `loot_drops`, 662 `character_vendor_items`, and 1,086 map-visible `character_deduplications` members.

## Goals / Non-Goals

**Goals:**

- The browser downloads no database, and `sql.js` leaves the client bundle.
- The spawn popup, the live-entity popup, and the zone pages show the same data as before.
- A browser test protects the change before and after the cutover.

**Non-Goals:**

- Reducing the prerendered `/map` marker payload. It is 508 KB with brotli.
- Changing the tile precache, the companion WebSocket protocols, or the Worker topology.
- Offline use of the popup details. The old service worker made the database available offline. The new popup document follows normal HTTP caching.

## Decisions

### D1. Remove the browser database from every route

The service worker downloads the database for every visitor on every page. Removing it only from `/map` would leave that download in place. The change therefore removes all three browser consumers, the service worker precache, and the published file.

Alternative: keep the database for the zone pages and stop the precache only. This leaves a 9.7 MB uncompressed download on every zone page and keeps two data paths. Rejected.

### D2. Zone pages load their markers in a prerendered server load

Replace `routes/maps/[mapName]/+page.ts` with a `+page.server.ts` that keeps `entries()` and `prerender = true`. It opens the Node repository and returns the north bearing and the twelve marker arrays that the page requests today. The page reads them from `data` and keeps its Leaflet code unchanged.

The existing repository methods already return the local-coordinate objects that Leaflet uses. Reusing them keeps the zone pages identical and needs no new query.

Alternative: derive zone markers from the `/map` world data. The world markers use transformed world coordinates and different shapes. Mapping back would add a second marker model. Rejected.

### D3. One prerendered popup-detail document

Add `routes/map/popup-details.json/+server.ts` with `prerender = true`. It returns one JSON document:

- `characters`: for each map-visible character stable key with drops or vendor stock, the drops (item name and drop probability) and the vendor stock (item name and price).
- `names`: for each display name, the map-visible characters with that name, each with the scenes where a member of its deduplication group is placed.

The document keeps the current SQL semantics. Drops are ordered by probability descending and then by item name. Vendor stock is the union of `character_vendor_items` and the quest-unlocked items, ordered by item name. The name index uses the same representative rule as `getCharactersByName`. A pure function `resolveLiveCandidates(names, name, scene)` replaces the in-scene query and keeps the fallback to all matches.

A module-level loader in `src/maps/src/lib/map/popup-details.ts` fetches the document once and shares the promise. A failed fetch clears the promise, so that the next popup retries.

Alternatives:

- Put the details in the `/map` load data. Every visit would pay for them, also visits that open no popup. Rejected.
- Write one file for each character. That adds about 1,000 assets to a build that already has 7,327 files, and each popup makes its own request. Rejected.

### D4. The build input is an explicit path

`database-path.server.ts` loses its default and fails when `ERENSHOR_MAPS_DATABASE_PATH` is not set. `maps dev` sets the variable for Vite, as `maps build` already does. `DatabaseLinkTransaction`, `_get_maps_db_path`, the `maps.database_dir` configuration key, and its schema field are removed. `generate-item-icons.mjs` reads the same variable. Vitest already uses a temporary fixture path.

`maps build` gets a precondition that fails when `src/maps/static` contains a `.sqlite` file or link, because adapter-static copies every static file into the build. The error names the path. The command does not delete the path itself, because commands must not change the source tree.

### D5. The service worker drops the database cache

Remove `DB_CACHE_NAME`, `precacheDatabase`, and the `.sqlite` fetch branch. The `activate` handler already deletes every cache whose name is not in its keep list. With only the tiles cache in that list, it deletes old `db-cache-*` caches.

### D6. The browser smoke test extends the fixture prerender script

Rename `scripts/test-prerender.mjs` to `scripts/test-site.mjs`. After the existing fixture build and HTML checks, the script starts Vite's programmatic `preview()` server on a free port, then runs `@playwright/test`'s `chromium` in headless mode. One build serves both checks, so the leaf does not build twice.

The browser checks are:

- `/`, `/map`, and `/maps/Stowaway` raise no `pageerror` and have no failed same-origin request. Requests to `ws://localhost:18584` and `:18585` are cross-origin companion sockets. They are not failures.
- `/map` has a canvas with a non-zero size.
- `/map?sel=marker:spawn:stowaway-enemy` shows the fixture enemy's drop item names in the spawn popup.
- `/maps/Stowaway` shows Leaflet markers for the fixture spawn points.
- After the cutover, a context-level request listener fails the run on any URL that ends in `.sqlite`. The listener also sees service worker requests.

The fixture gets one `character_vendor_items` row, so that the popup check covers vendor stock and the quest-unlock union.

The maps preflight resolves `chromium.executablePath()` from the locked `playwright` package and checks that the file exists. The failure message names `pnpm --dir src/maps exec playwright install chromium`. The existing Python Playwright preflight is not reused, because the Python package can lock a different browser revision. CI adds one step before the maps leaf: `nix develop --command pnpm --dir src/maps exec playwright install --with-deps chromium`.

## Risks / Trade-offs

- [An open tab from before the deploy requests `/db/erenshor.sqlite` and receives 404] → Its popups show the load error until the visitor reloads. SvelteKit loads the new client code on the next navigation. This is a one-time, visible, non-destructive failure.
- [The popup document grows with the game data] → The implementation records its raw and brotli size in the commit. The present row counts put it far below the removed 9.7 MB file.
- [The Chromium download makes the CI maps job slower and adds a network dependency] → The version is locked by `pnpm-lock.yaml`. A failed download fails the job loudly before the leaf runs.
- [`maps dev` no longer hot-reloads the database for the browser] → The browser never read a live database in `/map`. Server loads read the file at request time in dev mode. A restart of `maps dev` picks up a rebuilt database in every case.
- [A local `src/maps/static/db` link from the old workflow can leak the database into a build] → D4's precondition stops the build and names the path.

## Migration Plan

1. Land the browser smoke test first. It passes on the current code.
2. Land the zone page prerender and the popup document. Each keeps the page output the same, and the smoke test passes after each.
3. Remove the browser database, the service worker cache, and the static link in one cutover. Add the `.sqlite` request check in the same commit.
4. Delete the local `src/maps/static/db` link. Run `maps build`, check the preview in a browser, and run `maps deploy`. The deploy removes `/db/erenshor.sqlite` from both Worker services.

Rollback: revert the cutover commits, run `maps build`, and run `maps deploy`. No data migration is involved.
