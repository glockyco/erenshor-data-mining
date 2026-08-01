# Local wiki development stack

This directory contains the local MediaWiki stack used to test the Lua data-module and Cargo migration before touching the live wiki.

## What this stack is for

- Rendering repo-owned templates and Scribunto modules through real MediaWiki.
- Running local smoke tests with `action=parse`.
- Exercising Cargo storage/query behaviour.
- Proving null-edit refresh behaviour before production deployment.

It is not a production wiki and it is not intended to exactly reproduce wiki.gg's LIBRARIAN fork. It builds upstream Cargo as a close local compatibility layer. Final pre-production validation still happens with live TemplateSandbox on erenshor.wiki.gg.

## Included skins and extensions

The Dockerfile installs MediaWiki 1.43-compatible branches for the local
runtime surface used by production pages:

```text
Cargo
Gadgets
InputBox
ParserFunctions
PortableInfobox
Scribunto
TemplateSandbox
TemplateStyles
TemplateStylesExtender
Vector
```

`TemplateStyles` is paired with `TemplateStylesExtender` because the live wiki
runs both. The Extender is what permits CSS custom properties and `var()`, so
pages that adapt to the night and day themes through the skin's Codex tokens
only sanitize correctly when it is loaded. `wikimedia/css-sanitizer` ships in
the base image, so neither extension needs composer.

The local stack does not provide `__NOTITLE__`, which the live wiki supports.
Pages that use it render the literal magic word locally. That is a known
preview gap, not a page defect.

The live wiki is MediaWiki 1.43.6 with Classic Vector, Scribunto,
TemplateSandbox, Gadgets/DataTables, PortableInfobox, and LIBRARIAN 4.21.0
(wiki.gg's fork of Cargo, which registers the same `#cargo_*` parser
functions). Local upstream Cargo is the documented compatibility layer for
LIBRARIAN, and local PortableInfobox is the same `Universal-Omega/PortableInfobox`
build the live wiki runs. Neither is a substitute for final live
TemplateSandbox validation.

## Bootstrap the stack

From the repository root:

```bash
wiki-dev/bootstrap.sh
```

The bootstrap script starts the Docker Compose stack, runs first-time MediaWiki installation when needed, copies the generated `LocalSettings.php` into `wiki-dev/runtime/`, includes `LocalSettings.extra.php`, and runs `maintenance/run.php update --quick`.

Local admin credentials:

```text
username: WikiSysop
password: DevWikiPassword-2026
```

The helper scripts default to those credentials.

## Deploy bot account

`bootstrap.sh` also provisions a local bot account used by the wiki deploy
pipeline and the deploy integration tests. It is in the `bot` group, so
`assert=bot` safe edits succeed against it:

```text
username: ErenshorBot
password: BotDevPassword-2026
```

Override with `BOT_USER` / `BOT_PASSWORD` when running `bootstrap.sh`. The
account is local-only and never mirrors a production credential.

## Sync live interface pages

Local CSS and JavaScript preview depends on the live `MediaWiki:` interface
pages. Sync the current live versions before importing local pages:

```bash
uv run erenshor wiki sync-interface
```

The command writes gitignored mirrors under `wiki-dev/interface/MediaWiki/`
and `wiki-dev/images/`. It prints unified diffs for interface page changes
against any existing local mirror before overwriting. It downloads fixed skin
assets such as `Site-logo.png` plus image assets referenced by synced CSS so
`/images/...` URLs resolve locally.
The committed `wiki-dev/interface/theme-shim.css` and
`wiki-dev/interface/theme-shim.js` files are authored local glue. The CSS
provides fallback wiki.gg/platform custom properties and local compatibility
for live platform ResourceLoader styles that are not installed in the dev
container, including `ext.PortableInfobox.styles`. The JavaScript adds the
same dark-theme and wiki.gg Vector classes that live pages use. Import prepends
these shims to `MediaWiki:Common.css` and `MediaWiki:Common.js`; sync never
overwrites them.

Repo-owned gadgets are declared in `wiki/gadgets/gadgets.toml`. That file is
the authoritative allowlist, source order, and `MediaWiki:Gadgets-definition`
registration for local preview and production. During local import, declared
files under `wiki/gadgets/` replace any same-title live mirror and the importer
reconciles only the declared gadget lines, preserving unrelated live gadgets.

Production interface deployment uses a dedicated account rather than the
content bot. Set `interface_username` and `interface_password` under
`[global.mediawiki]` in `.erenshor/config.local.toml`, then use:

```bash
uv run erenshor --dry-run wiki deploy-interface
uv run erenshor wiki deploy-interface
uv run erenshor wiki rollback-interface
```

Deployment snapshots every target in one batch, writes revision-guarded edits,
and checkpoints a manifest plus rollback sidecars under
`output/wiki-interface/`. Rollback restores edited pages only when their
revision still matches the deployment; pages created by the deployment are
reported and deliberately left in place. The ordinary content-bot deployment
cannot discover or edit `MediaWiki:` interface pages.


## Import local pages

From the repository root:

```bash
uv run python wiki-dev/import_pages.py --dry-run
uv run python wiki-dev/import_pages.py
```

The importer reconciles only repository-managed titles. It compares current
sources with exact remote content, creates missing pages, updates drifted pages,
and deletes titles only when they were recorded in the previous managed
manifest. Unmanaged wiki pages are never queried or changed. A successful run
atomically refreshes the gitignored manifest at
`wiki-dev/runtime/import_pages.manifest.json`. Re-running an unchanged import
performs no edits, deletes, or purges.

Mappings:

```text
wiki-dev/interface/MediaWiki/Common.css          -> MediaWiki:Common.css
wiki-dev/interface/MediaWiki/Sidebar             -> MediaWiki:Sidebar
wiki-dev/interface/MediaWiki/Gadget-foo.js       -> MediaWiki:Gadget-foo.js
wiki/gadgets/foo.js                              -> MediaWiki:Gadget-foo.js (repo override)
wiki/modules/Erenshor/Item.lua                   -> Module:Erenshor/Item
wiki-dev/fixtures/modules/Erenshor/Data/Items.lua -> Module:Erenshor/Data/Items
wiki/templates/Item.wiki                         -> Template:Item
wiki-dev/fixtures/pages/Foo.wiki                 -> Foo
```

## Run smoke tests

From the repository root:

```bash
uv run python wiki-dev/smoke_test.py
```

The default `wiki-dev/fixtures/smoke.tsv` renders `Smoke Page` through `action=parse` and verifies text returned by `Module:Erenshor/Smoke` through `Template:Smoke`.

## Visual parity gate

The smoke harness proves pages parse and store Cargo rows; it does not prove
they *render* like the live wiki. The parity gate closes that gap. It renders
representative local pages in real Chromium (via Playwright) and asserts their
computed styles and DOM classes against a baseline captured from live parser
output and live ResourceLoader stylesheets.

```bash
# Refresh the baseline from live MediaWiki API output and live CSS.
uv run python wiki-dev/parity_check.py --capture

# Check the local stack against that baseline (routine; headless, offline).
uv run python wiki-dev/parity_check.py
```

The contract (which pages, elements, and properties are checked) lives in
`wiki-dev/parity/contract.py` and is committed. The captured expected values
live in `wiki-dev/parity/baseline.json`, which is **gitignored**: it is derived
from third-party live content and must not be committed. Run `--capture` before
the first check, and again whenever the live wiki's styling changes.

`--capture` does not navigate a browser to live wiki article routes. It fetches
live parser HTML through the MediaWiki API, wraps it in a static Vector page with
live ResourceLoader CSS, and extracts the target styles in Chromium. The routine
check only touches the local stack. Import the local pages (`import_pages.py`)
before checking so the rendered output is current.

## Full local validation sequence

After changing modules, templates, fixtures, or interface shims, run the local
validation in order from the repository root:

```bash
uv run erenshor wiki sync-interface     # refresh gitignored live interface mirror
uv run python wiki-dev/import_pages.py  # import interface, modules, templates, pages
uv run python wiki-dev/smoke_test.py    # parse + Cargo structural checks
uv run python wiki-dev/parity_check.py  # rendered-style parity vs captured live baseline
```

Run `uv run python wiki-dev/parity_check.py --capture` first (and after live
styling changes) to refresh the gitignored baseline the check compares against.

## Isolated clean parity

Use the canonical clean gate to prove that a fresh MediaWiki installation
matches the warm developer wiki:

```bash
uv run erenshor test wiki --clean-parity
```

The command validates the warm wiki first, creates a uniquely named Docker
Compose project on an ephemeral port, imports into fresh database, image, and
runtime volumes, recreates Cargo tables, runs smoke and browser contracts, and
compares deterministic acceptance snapshots. It always removes the isolated
containers and volumes. The warm wiki must have the same managed page hashes,
Cargo fixture rows, smoke outcomes, interface inventory, and browser counters
before and after the run.

`wiki-dev/fixtures/dependencies/templates/` contains include-only copies of the
live legacy item templates still required by the parameterized equipment
renderer. The clean harness imports these with
`--include-clean-dependencies`. Ordinary warm imports do not manage or overwrite
the live-template copies in the developer wiki.

The comparison report is written to
`artifacts/test-reports/wiki-clean-parity.json`. Warm and clean parity each run
three browser contracts: source insertion, VisualEditor replacement, and
combined tooltip success and failure behavior.

On the first browser failure, pytest writes the rendered HTML, screenshot,
console messages, failed requests, page errors, test metadata, and Docker
Compose service logs under
`artifacts/test-reports/wiki-diagnostics/first-failure/`. A new browser test
session clears stale diagnostics, so a passing run cannot leave an old failure
bundle behind.

## Reset local state

This deletes the local wiki database, generated settings, and uploaded files:

```bash
cd wiki-dev
docker compose down -v
rm -rf db images runtime
```
