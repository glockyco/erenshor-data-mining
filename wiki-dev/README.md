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
ParserFunctions
Scribunto
TemplateSandbox
Vector
```

The live wiki is MediaWiki 1.43.6 with Classic Vector, Scribunto,
TemplateSandbox, Gadgets/DataTables, and LIBRARIAN 4.21.0. Local upstream
Cargo is close enough for parser/render/storage integration, but not a
substitute for final live TemplateSandbox validation.

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

## Sync live interface pages

Local CSS and JavaScript preview depends on the live `MediaWiki:` interface
pages. Sync the current live versions before importing local pages:

```bash
uv run erenshor wiki sync-interface
```

The command writes gitignored mirrors under `wiki-dev/interface/MediaWiki/`
and `wiki-dev/images/`. It prints unified diffs for interface page changes
against any existing local mirror before overwriting, and it downloads image
assets referenced by synced CSS so `/images/...` URLs resolve locally.
The committed `wiki-dev/interface/theme-shim.css` and
`wiki-dev/interface/theme-shim.js` files are authored local glue. The CSS
provides fallback wiki.gg custom properties, and the JavaScript adds the same
dark theme classes that wiki.gg applies on live pages. Import prepends these
shims to `MediaWiki:Common.css` and `MediaWiki:Common.js`; sync never
overwrites them.


## Import local pages

From the repository root:

```bash
uv run python wiki-dev/import_pages.py --dry-run
uv run python wiki-dev/import_pages.py
```

Mappings:

```text
wiki-dev/interface/MediaWiki/Common.css          -> MediaWiki:Common.css
wiki-dev/interface/MediaWiki/Gadget-foo.js       -> MediaWiki:Gadget-foo.js
wiki/modules/Erenshor/Item.lua                   -> Module:Erenshor/Item
wiki-dev/fixtures/modules/Erenshor/Data/Items.lua -> Module:Erenshor/Data/Items
wiki/templates/Item.wiki                         -> Template:Item
wiki-dev/fixtures/pages/Foo.wiki                 -> Foo
```

## Run smoke tests

From the repository root:

```bash
python wiki-dev/smoke_test.py
```

The default `wiki-dev/fixtures/smoke.tsv` renders `Smoke Page` through `action=parse` and verifies text returned by `Module:Erenshor/Smoke` through `Template:Smoke`.

## Reset local state

This deletes the local wiki database, generated settings, and uploaded files:

```bash
cd wiki-dev
docker compose down -v
rm -rf db images runtime
```
