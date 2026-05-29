# Wiki Lua/Cargo Development Environment

**Date**: 2026-05-29  
**Status**: Research-backed dev environment design  
**Scope**: Safe local and staged testing for the proposed Lua data module + LIBRARIAN/Cargo wiki architecture.

---

## Goal

We need to make large wiki-side changes without experimenting on the live wiki. The
dev environment must let us validate, before deployment:

1. Generated Lua data modules are syntactically valid and match the SQLite data.
2. Lua display modules render infoboxes, tier tables, tooltips, vendor inventories,
   and overview pages correctly.
3. Manual template parameter overrides win over data-module defaults.
4. LIBRARIAN/Cargo tables are declared, populated, queried, and refreshed correctly.
5. The null-edit refresh path works after data module updates.
6. Live wiki deployment is a final promotion step, not the first place we discover bugs.

---

## What comparable projects and platform docs recommend

### Use a real MediaWiki instance for integration tests

MediaWiki's official docs provide **MediaWiki-Docker** as the development environment
for local experimentation and testing. It is explicitly intended for development and
not production hosting.

Source: https://www.mediawiki.org/wiki/Docker

For us this means: do not rely only on Python unit tests or a standalone Lua runner.
Scribunto, Cargo/LIBRARIAN, parser functions, template expansion, and page caching are
MediaWiki behaviours. They need a real MediaWiki process.

### Use TemplateSandbox for live final validation

The TemplateSandbox extension exists specifically to preview pages with sandboxed
versions of templates and modules. Its docs explicitly state that it also works with
Scribunto modules.

Source: https://www.mediawiki.org/wiki/Extension:TemplateSandbox

The Erenshor wiki has TemplateSandbox installed. The correct live-wiki staging pattern
is therefore:

- develop locally first;
- deploy candidate templates/modules under `User:<name>/sandbox/...` or `/sandbox`
  pages;
- use `Special:TemplateSandbox` to render representative production pages with those
  sandboxed templates/modules;
- only then promote sandbox pages to production names.

### Use ScribuntoUnit for wiki-side Lua tests

ScribuntoUnit is the standard MediaWiki-side test module pattern. A module under
`Module:Foo/testcases` imports `Module:Foo`, creates a test suite, and exposes tests
that run through either the Lua console or `{{#invoke:Foo/testcases|run}}`.

Source: https://www.mediawiki.org/wiki/Module:ScribuntoUnit

This matters because some behaviour cannot be faithfully tested outside MediaWiki:
`mw.html`, `mw.title`, `frame:getParent().args`, parser expansion, strip markers,
Cargo calls, and Scribunto's exact Lua sandbox rules.

### Cargo can be used from Lua, but cache refresh is real

Cargo's docs state that `#cargo_query`, `#cargo_declare`, and `#cargo_store` can be
called from Scribunto Lua modules via `mw.ext.cargo`. They also document that Cargo
query pages may need cache purges after data changes.

Source: https://www.mediawiki.org/wiki/Extension:Cargo/Other_features

wiki.gg's null-edit docs add the key operational lesson for our chosen architecture:
when a page reads from Lua and stores to Cargo, updating the Lua data module is not
enough to update stored Cargo rows. The affected article pages need null-edits so the
store calls run again.

Source: https://support.wiki.gg/wiki/Null_edit

### Local parity cannot be perfect, so use layered confidence

The live Erenshor wiki reports:

- MediaWiki `1.43.6`
- PHP `8.1.33`
- MySQL `8.0.44`
- Scribunto installed
- LIBRARIAN `4.21.0` installed (wiki.gg Cargo fork)
- TemplateSandbox installed

Confirmed via:
`https://erenshor.wiki.gg/api.php?action=query&meta=siteinfo&siprop=general|extensions&format=json`

A local dev stack can match MediaWiki, PHP, MySQL/MariaDB, Scribunto, TemplateSandbox,
and upstream Cargo closely. It may not match wiki.gg's LIBRARIAN fork exactly unless
wiki.gg publishes installable sources. Therefore the robust workflow is layered:

1. repo unit tests;
2. local MediaWiki integration tests;
3. live TemplateSandbox validation;
4. production promotion.

No single layer is enough.

---

## Recommended environment: four layers

### Layer 1 — Repo-level fast tests

Purpose: catch mistakes before MediaWiki starts.

Run locally in the Python project:

- Generate Lua data modules from a fixture database.
- Validate generated Lua syntax.
- Validate data schema: required fields, stable keys, duplicate page names, bad UTF-8,
  unsupported Lua literal values.
- Golden-test representative generated modules.
- Unit-test pure Lua helpers with a normal Lua runtime where possible.

Recommended repo layout:

```text
src/erenshor/application/wiki_lua/
  serializers.py                 # SQLite/domain objects -> Lua table text
  deploy.py                      # upload modules + null-edit affected pages

wiki/
  modules/
    Erenshor/
      Item.lua                   # source of Module:Erenshor/Item
      Character.lua
      Tables.lua
      Data/
        Items.lua.generated      # generated, not hand-edited
  templates/
    Item.wiki                    # source of Template:Item
    Character.wiki
  tests/
    pages/
      item_sword_of_flames.wiki
      npc_vendor.wiki
    expected/
      item_sword_of_flames.html
      weapons_overview.html
```

Fast tests should not require Docker. They answer: "did we generate valid, sane code?"
not "does MediaWiki render it?"

### Layer 2 — Local MediaWiki integration stack

Purpose: exercise the real parser, Scribunto, Cargo, and template expansion.

Use Docker Compose with:

- MediaWiki `1.43.x`
- PHP `8.1.x` if practical
- MySQL 8 or MariaDB
- Scribunto
- ParserFunctions
- TemplateSandbox
- Cargo upstream (or LIBRARIAN if wiki.gg provides an installable package)
- CodeEditor/TemplateData optional but useful for local parity

The local stack is not production. It is a disposable test appliance.

Minimal acceptance tests for this layer:

1. Import/update local pages:
   - `Module:Erenshor/Data/Items`
   - `Module:Erenshor/Item`
   - `Template:Item`
   - `Module:Erenshor/Tables`
   - fixture article pages like `Sword of Flames`
2. Call MediaWiki `action=parse` on representative pages.
3. Assert the rendered HTML contains expected values.
4. Run ScribuntoUnit pages like `Module:Erenshor/Item/testcases`.
5. Query Cargo tables via `cargoquery` API or `mw.ext.cargo.query` test pages.
6. Modify a data module, run the null-edit command, assert Cargo rows update.

This catches the classes of bugs that Python tests cannot catch: broken parser
function syntax, Lua sandbox errors, Cargo schema mismatches, bad template expansion,
strip marker weirdness, and cache refresh failures.

### Layer 3 — Live wiki sandbox validation

Purpose: catch wiki.gg-specific differences before production pages change.

Use TemplateSandbox on erenshor.wiki.gg:

1. Upload candidate code to sandbox pages, for example:
   - `User:<name>/sandbox/Module:Erenshor/Item`
   - `User:<name>/sandbox/Module:Erenshor/Data/Items`
   - `User:<name>/sandbox/Template:Item`
2. Go to `Special:TemplateSandbox`.
3. Render real production pages through the sandbox prefix.
4. Compare output against current production output and expected changes.

TemplateSandbox supports a prefix search path, so a sandbox can override only the pages
being changed while falling back to production templates/modules for everything else.
This is exactly the safe test surface we need for sweeping Lua/template changes.

Representative live validation pages should include:

- one plain item;
- one weapon with 3 quality tiers;
- one armor item with 3 quality tiers;
- one aura item;
- one spell scroll;
- one skill book;
- one multi-entity page;
- one vendor NPC page;
- Weapons overview;
- Armor overview;
- one class page;
- one zone page.

### Layer 4 — Production deploy with rollback

Purpose: promote only after evidence exists.

Production deploy should be a command, not manual copy/paste:

```bash
uv run erenshor wiki-lua deploy --dry-run
uv run erenshor wiki-lua deploy
uv run erenshor wiki-lua null-edit --changed-only
```

Production deploy rules:

- Use `basetimestamp`/`baserevid` on every edit.
- Include game build number and bot version in edit summary.
- Upload data modules first, then display modules/templates if changed.
- Recreate Cargo tables only when schema changed.
- Null-edit only affected article pages when possible.
- Keep previous module text locally so rollback is one command.

---

## Local Docker stack design

Do not build this as a fragile one-off machine setup. Put the dev wiki definition in
the repo so anyone can rebuild it.

Recommended files:

```text
wiki-dev/
  compose.yml
  LocalSettings.extra.php
  extensions/
    README.md                    # how to install/update extensions
  import_pages.py                # push local wiki/modules + templates into dev wiki
  smoke_test.py                  # parse pages, query Cargo, run testcases
  fixtures/
    pages.txt                    # production page titles to mirror locally
```

### Compose services

```yaml
services:
  mediawiki:
    image: mediawiki:1.43
    ports:
      - "8088:80"
    volumes:
      - ./LocalSettings.php:/var/www/html/LocalSettings.php
      - ../wiki:/workspace/wiki:ro
      - ./images:/var/www/html/images
      - ./extensions/Cargo:/var/www/html/extensions/Cargo
      - ./extensions/TemplateSandbox:/var/www/html/extensions/TemplateSandbox
      - ./extensions/Scribunto:/var/www/html/extensions/Scribunto
    depends_on:
      - db

  db:
    image: mysql:8.0
    environment:
      MYSQL_DATABASE: mediawiki
      MYSQL_USER: wiki
      MYSQL_PASSWORD: wiki
      MYSQL_ROOT_PASSWORD: root
    volumes:
      - ./db:/var/lib/mysql
```

This is illustrative, not final. The implementation should prefer the official
MediaWiki-Docker dev environment if it fits better, but the repo needs a repeatable
entry point either way.

### Required LocalSettings flags

```php
wfLoadExtension( 'Scribunto' );
wfLoadExtension( 'ParserFunctions' );
wfLoadExtension( 'Cargo' );
wfLoadExtension( 'TemplateSandbox' );

$wgScribuntoDefaultEngine = 'luastandalone';
$wgCargoDBtype = 'mysql';
$wgCargoDBserver = $wgDBserver;
$wgCargoDBname = $wgDBname;
$wgCargoDBuser = $wgDBuser;
$wgCargoDBpassword = $wgDBpassword;
```

If upstream Cargo behaves differently from wiki.gg LIBRARIAN, capture that difference
in a compatibility note and cover it with live TemplateSandbox validation.

---

## Test matrix

### Lua data generation tests

- Generated modules parse as Lua.
- Generated modules contain only strings, numbers, booleans, and tables (required by
  `mw.loadData`).
- No generated key duplicates.
- No article title exceeds MediaWiki title constraints.
- No module exceeds a configured byte budget without an explicit split.
- Golden diff for a small stable fixture database.

### Lua display module tests

Use ScribuntoUnit for wiki-native tests:

```lua
-- Module:Erenshor/Item/testcases
local Item = require('Module:Erenshor/Item')
local ScribuntoUnit = require('Module:ScribuntoUnit')
local suite = ScribuntoUnit:new()

function suite:testExplicitImageOverrideWins()
    local rendered = Item._renderForTest({
        name = 'Sword of Flames',
        image = 'Custom sword.png',
    })
    self:assertStringContains('Custom sword.png', rendered, true)
end

return suite
```

Expose test-friendly pure functions like `_resolveForTest(args)` and `_renderForTest(args)`
that do not require a full frame object. The public `p.render(frame)` function should be
thin.

### Template tests

For each wrapper template:

- default article call uses page title;
- `|name=` points to a different entity;
- every documented override parameter wins;
- empty override means "intentionally blank" when needed;
- missing data gives a loud error category, not silently empty output.

### Cargo tests

- Table declaration exists and matches the generated schema.
- `mw.ext.cargo.store()` stores resolved values, not raw game values.
- Overrides appear in Cargo after a null-edit.
- Overview query pages render expected rows.
- Schema changes fail the test suite until recreate-table steps are acknowledged.

### Cache/null-edit tests

Local integration should explicitly prove the null-edit workflow:

1. Import data module v1.
2. Render `Sword of Flames`; assert Cargo has v1 damage.
3. Import data module v2 with changed damage.
4. Assert Cargo is still v1 before null-edit.
5. Null-edit `Sword of Flames`.
6. Assert Cargo now has v2 damage.

This test prevents the most dangerous false confidence: thinking module upload alone
refreshes stored query data.

---

## Deployment safety practices

### Treat wiki code as source-controlled code

Lua modules and templates should live in git first, not only on the live wiki. The live
wiki is the deployment target, not the source of truth. Contributors can still improve
wiki-side modules, but those changes should be pulled back into the repo before the next
bot-driven deploy.

### Always deploy with diff and basetimestamp

A deploy command should fetch the current wiki text, show a diff, and edit with
`basetimestamp`/`baserevid`. If someone changed the live module after our last fetch,
the deploy should fail with an edit conflict instead of overwriting them.

### Use small promotion batches

Production promotion order:

1. data modules under sandbox names;
2. display modules under sandbox names;
3. TemplateSandbox validation;
4. production display modules;
5. production templates;
6. production data modules;
7. null-edit affected article pages;
8. smoke-test key overview pages.

### Keep rollback simple

Every deploy writes a local manifest:

```json
{
  "deployed_at": "2026-05-29T06:00:00Z",
  "build": "1.0.52",
  "pages": {
    "Module:Erenshor/Data/Items": {
      "old_revid": 12345,
      "new_revid": 12399,
      "old_sha256": "...",
      "new_sha256": "..."
    }
  }
}
```

Rollback is uploading the previous text from the manifest, then running the same
null-edit refresh.

---

## Why not just use a standalone Lua runner?

A standalone Lua runner is useful, but insufficient. It can test pure functions and
syntax. It cannot fully simulate:

- `mw.html` output quirks;
- `frame:getParent().args` and template argument trimming;
- parser function expansion;
- strip markers for `<ref>`, `<nowiki>`, `<gallery>`;
- Cargo store/query behaviour;
- parser cache and null-edit behaviour;
- TemplateSandbox prefix fallback.

Use standalone Lua tests for speed. Trust local MediaWiki and live TemplateSandbox for
correctness.

---

## Recommended first implementation task

Before changing production templates, build the dev harness:

1. Add `wiki-dev/compose.yml` and LocalSettings for MediaWiki + Scribunto + Cargo +
   TemplateSandbox.
2. Add Python helpers to upload local `wiki/modules` and `wiki/templates` files to the
   local wiki API.
3. Add a smoke test that renders one item page and one overview page via `action=parse`.
4. Add a Cargo refresh test proving null-edit behaviour.
5. Only then begin porting `Template:Item` / `Module:Erenshor/Item`.

This avoids the exact failure mode the current system fell into: designing the pipeline
around live-wiki behaviour that was never reproducibly tested locally.

---

## References

| Topic | URL |
|---|---|
| MediaWiki-Docker official dev environment | https://www.mediawiki.org/wiki/Docker |
| TemplateSandbox extension | https://www.mediawiki.org/wiki/Extension:TemplateSandbox |
| ScribuntoUnit test module pattern | https://www.mediawiki.org/wiki/Module:ScribuntoUnit |
| Cargo Lua API (`query`, `declare`, `store`) | https://www.mediawiki.org/wiki/Extension:Cargo/Other_features |
| wiki.gg null-edit workflow | https://support.wiki.gg/wiki/Null_edit |
| wiki.gg AutoWikiBrowser null-edit workflow | https://support.wiki.gg/wiki/AutoWikiBrowser |
| Scribunto Lua reference (`mw.loadData`) | https://www.mediawiki.org/wiki/Extension:Scribunto/Lua_reference_manual |
| MediaWiki Lua best practices | https://www.mediawiki.org/wiki/Help:Lua/Lua_best_practice |
| MediaWiki API edit / basetimestamp | https://www.mediawiki.org/wiki/API:Edit |
