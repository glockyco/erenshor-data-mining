## 1. Browser smoke test (commit: `test(maps): run the fixture site in a browser`)

- [ ] 1.1 Add one `character_vendor_items` row for `character:breena carpenter` to `src/maps/tests/fixtures/map-database.sql`. Verify that `tests/contract/test_maps_fixture_schema.py` passes and that the fixture database lists the row.
- [ ] 1.2 Rename `src/maps/scripts/test-prerender.mjs` to `scripts/test-site.mjs`. After the HTML checks, serve the fixture build with Vite's `preview()` and check `/`, `/map`, `/map?sel=marker:spawn:stowaway-enemy`, `/map?sel=marker:spawn:stowaway-breena`, and `/maps/Stowaway` in headless Chromium, as design D6 describes. Verify that the script passes on the current code, and that it fails with a clear message when a fixture drop name is changed temporarily.
- [ ] 1.3 Point `PRERENDER_SMOKE_COMMAND` in `src/erenshor/cli/commands/maps.py` and the maps preflight in `src/erenshor/cli/commands/test.py` at the new script. Add the Chromium preflight from design D6. Update the affected tests in `tests/unit/cli/commands/test_test.py`. Verify that `uv run erenshor test maps` passes, and that the preflight names the install command when `PLAYWRIGHT_BROWSERS_PATH` points at an empty directory.
- [ ] 1.4 Add the Playwright Chromium install step to the `test-maps` job in `.github/workflows/ci.yml`. Update `src/maps/README.md` and the `interactive-map` skill. Verify that the CI maps job passes on the pull request.

## 2. Prerendered zone pages (commit: `feat(maps): prerender zone page markers`)

- [ ] 2.1 Replace `src/maps/src/routes/maps/[mapName]/+page.ts` with a `+page.server.ts` that keeps `entries()` and `prerender = true` and returns the north bearing and the twelve marker arrays, as design D2 describes. Change `+page.svelte` to read them from `data` and remove its `getBrowserRepository` call. Verify that `pnpm run check` passes and that the smoke test still passes.
- [ ] 2.2 Build the real site with `uv run erenshor maps build` and compare `/maps/Stowaway` and one rotated zone against production in a browser: the same marker count, the same popups, and the same compass bearing.

## 3. Popup-detail document (commit: `feat(maps): prerender map popup details`)

- [ ] 3.1 Add `src/maps/src/routes/map/popup-details.json/+server.ts` and the repository query that builds the document, as design D3 describes. Add a Vitest test against the fixture database that proves the drop order, the vendor union with quest-unlocked items, and the two `Fixture Enemy` name entries with their scenes.
- [ ] 3.2 Add `src/maps/src/lib/map/popup-details.ts` with the shared loader and `resolveLiveCandidates`. Add Vitest tests for the in-scene preference, the fallback to all matches, and the retry after a failed fetch.
- [ ] 3.3 Change `SpawnPointPopupContent.svelte` and `LiveNpcPopupContent.svelte` to use the loader. Verify that the smoke test still passes, and that the Breena popup shows the fixture vendor item.
- [ ] 3.4 Record the raw and brotli size of the real `build/map/popup-details.json` in the commit body.

## 4. Remove the browser database (commit: `feat(maps): stop publishing the clean database`)

- [ ] 4.1 Delete `src/maps/src/lib/database.default.ts` and its test. Remove the database precache, the `.sqlite` fetch branch, and `DB_CACHE_NAME` from `src/maps/src/service-worker.ts`. Remove `/db/erenshor.sqlite` from `src/maps/src/legacy-worker.test.ts`. Verify that `pnpm run check` and `pnpm run test` pass, and that no client chunk in the build contains `sql-wasm`.
- [ ] 4.2 Add the `.sqlite` request check to `scripts/test-site.mjs`. Verify that it fails when the old precache is restored temporarily, and passes without it.
- [ ] 4.3 Remove the default path from `src/maps/src/lib/database-path.server.ts` and from `database.node.ts`. Make `generate-item-icons.mjs` read `ERENSHOR_MAPS_DATABASE_PATH`. Verify that a build without the variable fails with a message that names it.
- [ ] 4.4 Remove `DatabaseLinkTransaction`, `_get_maps_db_path`, and the link handling from `maps dev` and `maps build`. Pass `ERENSHOR_MAPS_DATABASE_PATH` to `maps dev`. Add the precondition that rejects a `.sqlite` file or link under `src/maps/static`. Update `tests/unit/cli/commands/test_maps.py`: delete the link-transaction tests and add a test for the precondition. Verify that `uv run pytest tests/unit/cli/commands/test_maps.py` passes.
- [ ] 4.5 Remove `maps.database_dir` from `config.toml`, `src/erenshor/infrastructure/config/schema.py`, `src/erenshor/cli/preconditions/decorator.py`, and their tests. Remove `static/db` from `src/maps/.gitignore` and `tests/contract/test_document_paths.py`. Verify that `uv run pytest` passes.
- [ ] 4.6 Update `src/maps/README.md`, the `interactive-map` and `refreshing-game-data` skills, the refresh incident log, and `docs/architecture.md` where they describe the database link or the browser database. Verify with a search that no maintained file refers to `static/db` or `getBrowserRepository`.

## 5. Release

- [ ] 5.1 Delete the local `src/maps/static/db` link. Run `uv run erenshor test ci` and `uv run erenshor maps build`. Verify that the build directory contains no `.sqlite` file.
- [ ] 5.2 Check `maps preview` in a browser with a fresh profile: no `.sqlite` request on `/`, `/map`, and a zone page, working spawn and vendor popups, and working zone markers.
- [ ] 5.3 Run `uv run erenshor maps deploy`. Verify on both hosts that `/db/erenshor.sqlite` returns 404, and that a spawn popup shows drops.
- [ ] 5.4 Archive the change with `openspec archive serve-map-data-without-sqlite --yes`, and replace any placeholder Purpose in the new main specs.
