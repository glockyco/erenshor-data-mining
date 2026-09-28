## 1. Browser smoke test (commit: `test(maps): run the fixture site in a browser`)

- [ ] 1.1 Add one `character_vendor_items` row for `character:breena carpenter` to `src/maps/tests/fixtures/map-database.sql`. Verify that `tests/contract/test_maps_fixture_schema.py` passes and that the fixture database lists the row.
- [ ] 1.2 Add `src/maps/playwright.config.ts`, `scripts/serve-fixture-site.mjs`, and specs under `tests/e2e/` as design D6 describes, without the `.sqlite` request check. Include the legacy overlay query check. Move the HTML assertions of `scripts/test-prerender.mjs` into the specs and delete that script. Add a `test:e2e` package script. Verify that `pnpm --dir src/maps run test:e2e` passes on the current code, and that it fails and names the content when a fixture drop name is changed temporarily.
- [ ] 1.3 Replace `PRERENDER_SMOKE_COMMAND` in `src/erenshor/cli/commands/maps.py` with the `test:e2e` command, and update the maps preflight in `src/erenshor/cli/commands/test.py`. Add the Chromium preflight from design D6. Update the affected tests in `tests/unit/cli/commands/test_test.py`. Verify that `uv run erenshor test maps` passes, and that the preflight names the install command when `PLAYWRIGHT_BROWSERS_PATH` points at an empty directory.
- [ ] 1.4 Add the Playwright Chromium install step to the `test-maps` job in `.github/workflows/ci.yml`. Update `src/maps/README.md` and the `interactive-map` skill. Verify that the CI maps job passes on the pull request.

## 2. Prerendered zone pages (commit: `feat(maps): prerender zone page markers`)

- [ ] 2.1 Replace `src/maps/src/routes/maps/[mapName]/+page.ts` with a `+page.server.ts` that keeps `entries()` and `prerender = true` and returns the north bearing and the twelve marker arrays, as design D2 describes. Change `+page.svelte` to read them from `data` and remove its `getBrowserRepository` call. Verify that `pnpm run check` passes and that the smoke test still passes.
- [ ] 2.2 Build the real site with `uv run erenshor maps build` and compare `/maps/Stowaway` and one rotated zone against production in a browser: the same marker count, the same popups, and the same compass bearing.

## 3. Popups from page data (commit: `feat(maps): build map popups from prerendered data`)

- [ ] 3.1 Add `src/maps/src/lib/map/character-details.ts` with the drop and vendor indexes from design D3. Add Vitest tests against the fixture item sources that prove the drop order, the vendor union with quest-unlocked items, and the exclusion of an item that the mapping hides.
- [ ] 3.2 Add the `charactersByName` query to the repository and the field to `buildMapWorldData`. Add `resolveLiveCandidates`. Add Vitest tests that prove the two `Fixture Enemy` entries and their scenes, the in-scene preference, and the fallback to all matches.
- [ ] 3.3 Change `SpawnPointPopupContent.svelte` and `LiveNpcPopupContent.svelte` to use the indexes and remove their loading and error states. Verify that the smoke test still passes, and that in the real build the A Golden Spirit popup no longer lists "A Golden Ticket (1)".
- [ ] 3.4 Record the raw and brotli size of the real `build/map/__data.json` before and after the change in the commit body.

## 4. Publish the database from a route (commit: `feat(maps): stop downloading the database in the browser`)

- [ ] 4.1 Add `src/maps/src/routes/db/erenshor.sqlite/+server.ts` as design D1 describes. Add the published-database check to the smoke test. Verify that the fixture build serves the fixture database at `/db/erenshor.sqlite`.
- [ ] 4.2 Delete `src/maps/src/lib/database.default.ts` and its test. Remove the database precache, the `.sqlite` fetch branch, and `DB_CACHE_NAME` from `src/maps/src/service-worker.ts`. Verify that `pnpm run check` and `pnpm run test` pass, and that no client chunk in the build contains `sql-wasm`.
- [ ] 4.3 Add the `.sqlite` request check to the smoke test. Verify that it fails when the old precache is restored temporarily, and passes without it.
- [ ] 4.4 Remove the default path from `src/maps/src/lib/database-path.server.ts` and from `database.node.ts`. Make `generate-item-icons.mjs` read `ERENSHOR_MAPS_DATABASE_PATH`. Verify that a build without the variable fails with a message that names it.
- [ ] 4.5 Remove `DatabaseLinkTransaction`, `_get_maps_db_path`, and the link handling from `maps dev` and `maps build`. Pass `ERENSHOR_MAPS_DATABASE_PATH` to `maps dev`. Add the precondition that rejects a `.sqlite` file or link under `src/maps/static`. Update `tests/unit/cli/commands/test_maps.py`: delete the link-transaction tests and add a test for the precondition. Verify that `uv run pytest tests/unit/cli/commands/test_maps.py` passes.
- [ ] 4.6 Remove `maps.database_dir` from `config.toml`, `src/erenshor/infrastructure/config/schema.py`, `src/erenshor/cli/preconditions/decorator.py`, and their tests. Remove `static/db` from `src/maps/.gitignore` and `tests/contract/test_document_paths.py`. Verify that `uv run pytest` passes.
- [ ] 4.7 Update `src/maps/README.md`, the `interactive-map` and `refreshing-game-data` skills, the refresh incident log, and `docs/architecture.md` where they describe the database link or the browser database. Verify with a search that no maintained file refers to `static/db` or `getBrowserRepository`.

## 5. Release

- [ ] 5.1 Delete the local `src/maps/static/db` link. Run `uv run erenshor test ci` and `uv run erenshor maps build`. Verify that `build/db/erenshor.sqlite` has the same SHA-256 as `variants/main/erenshor-main.sqlite`, and that the build contains no other `.sqlite` file.
- [ ] 5.2 Check `maps preview` in a browser with a fresh profile: no `.sqlite` request on `/`, `/map`, and a zone page, working spawn and vendor popups, and working zone markers.
- [ ] 5.3 Run `uv run erenshor maps deploy`. Verify on both hosts that `/db/erenshor.sqlite` returns 200 with a SQLite body, that a spawn popup shows drops, and that the page makes no `.sqlite` request.
- [ ] 5.4 Archive the change with `openspec archive serve-map-data-without-sqlite --yes`, and replace any placeholder Purpose in the new main specs.
