# Design

## Context

See proposal.md for the motivation. Three things exist today that this design changes:

- Eight separately hand-written classes each reimplement an overlapping subset of the MediaWiki client's read and write surface for tests: `RecordingWikiClient` and `RecordingRollbackClient` (`tests/unit/application/wiki_deploy/test_pages.py`, `test_rollback.py`), `_Wiki` and `Wiki` (`test_page_edits.py`, `test_render_check.py`), `FakeClient` (`test_link_audit_service.py`), `FakeWiki` in two different files with two different shapes (`test_articles.py`, `tests/unit/application/services/test_image_publication.py`), and `FakeInterfaceClient` (`tests/unit/application/wiki_interface/test_deploy.py`). Between them they cover `get_page_snapshots`, `safe_edit_page`, `safe_create_page`, `list_files`, `list_file_pages`, `move_page`, `delete_page`, `undelete_page`, `download`, `upload_file`, `confirm_upload`, `get_file_versions`, `is_file_used`, and `purge_pages`, no two files quite the same way.
- Each CLI command module builds its own collaborators through its own private, module-level factory function: `create_readonly_mediawiki_client` (shared, in `cli/mediawiki.py`), `_create_sheets_service` (`commands/sheets.py`), `_bot_client` and `_administrator_client` (`commands/images.py`), and five more in `commands/wiki.py` including `_create_wiki_composition`, which already bundles one command's repositories, storage, and `GeneratorContext` the way this design wants every command's collaborators bundled. A test replaces one of these by patching its exact dotted path with `@patch` or `monkeypatch.setattr`.
- `wiki-dev/smoke_test.py` reads `wiki-dev/fixtures/smoke.tsv`, a 264-row table of (page title, literal substring), and asserts the substring appears in that page's raw rendered HTML.

## Goals / Non-Goals

**Goals:**

- One fake replaces all eight; its surface is the union above, so every existing test that uses any of the eight can be rewritten against it without losing the scenario it covered.
- Every command's existing composition function keeps its name and keeps building the real collaborator by default; a test supplies a fake by passing it to that same function, not by patching it.
- The smoke check keeps covering every page `smoke.tsv` covers today, by structure instead of by substring.
- Each migrated area (one fake call site, one command's composition function, or the smoke rework) lands as its own commit with its own passing suite, per this repository's one-subject-per-commit policy; nothing here requires one all-at-once rewrite.

**Non-Goals:**

- No change to any command's production behavior. A command that builds a real `MediaWikiClient` today still builds the same real `MediaWikiClient` the same way; only the seam a test uses to replace it changes.
- Hypothesis, the ruff `unittest.mock` ban, and mutation testing are explicitly deferred (see proposal.md).
- Not a rewrite of every assertion in the suite. Only the three named anti-patterns move: duplicate fakes, patch-by-path collaborator substitution, and mock-echo or exact-shape pins. A normal unit test that already asserts a return value or a database row is untouched.

## Decisions

**The fake lives at `tests/fakes/mediawiki.py` as one stateful class.** It holds an in-memory table of pages and file versions (title, text, revision, uploader, deleted/redirect state) and implements the full union of methods the eight existing fakes cover, closely modeled on the richest of the two `FakeWiki` implementations (`tests/unit/application/services/test_image_publication.py`), which already simulates file history, redirects, and the administrator/bot account split. Each of the eight call sites is migrated to construct this one class instead of its own, one file at a time; a file whose scenario needs a setup helper the shared fake does not yet have gets that helper added to the shared fake, not a local subclass.

**The fake is contract-tested against the local Docker wiki, not against MediaWiki's documentation.** `wiki-dev/` already runs a local MediaWiki instance for `import_pages.py`, `null_edit.py`, and `smoke_test.py`. A new contract test suite runs a curated set of representative operations (create a page, edit it twice and read its revision history, upload a file, move a file over a redirect, delete and undelete a page) against both the fake and that local wiki, and asserts the two produce the same observable result for each. This is the boundary that keeps the fake honest: it does not aim for full MediaWiki parity, only for agreement on the operations the production code actually performs, so a change to the fake that disagrees with the real server's behavior fails here before it can mask a real bug in a consumer test.

**A command's existing composition function gains a keyword-only override, not a new mechanism.** `_create_wiki_composition(cli_ctx, *, with_client)` and its siblings each gain a parameter such as `wiki_client: MediaWikiClient | None = None` (or, for `sheets.py`, `service: SheetsService | None = None`) that, when given, is used in place of building the real collaborator. A test calls the command's Typer entry point with a `CLIContext` as today, but reaches the fake through this parameter on the composition function rather than through `@patch`. Each command module keeps its own composition function and its own collaborator shape; this is not a single shared container across sheets, wiki, and images, because their needs (one service, one client, or a client plus four repositories and a `GeneratorContext`) are not the same shape, and forcing them into one would be the kind of generic abstraction this project avoids. `commands/wiki.py`'s existing `_create_wiki_composition` is the closest current example of the pattern the other modules move to.

**Mock-echo and exact-shape tests are deleted, not weakened.** A test that only asserts a collaborator method was called with certain arguments is replaced by a test that runs the command against the fake and asserts the fake's resulting state (the page the fake now holds, its new revision, the file now at a given title) or the command's own output. Where an existing test's assertion already checks a real outcome alongside a brittle pin (most of the `test_mods_leaf_uses_each_exact_native_project_argv_and_repository_cwd`-style cases), only the brittle part is removed.

**Rendered-text assertions move to the nearest structural equivalent, not to a single new abstraction.** A CLI test that checks rendered console output moves to asserting on the underlying typed result the command already returns or raises, where one exists; only a test that has no such value to check (because the behavior genuinely is what the console shows) takes an `inline-snapshot` baseline. `wiki-dev/smoke_test.py` moves from a substring in `smoke.tsv` to a per-page selector (a heading, an infobox field, a category link) checked against the parsed DOM; `smoke.tsv`'s existing rows are converted one for one so no currently-checked page loses coverage.

## Risks / Trade-offs

- **Migration lands over several commits, so both patterns coexist for a time.** A new test must use the new patterns; an untouched existing test keeps its old fake and its old patch until its own area is migrated. This is accepted in exchange for reviewable, revertible commits (see Goals); the last task in this change's task list is a repository-wide check that no old fake class and no `@patch("erenshor...")` call site remains.
- **The contract test suite adds a dependency on the local Docker wiki being available**, same as `wiki-dev`'s existing tests already depend on it; no new infrastructure requirement.
- **`inline-snapshot` is a new third-party dependency.** It is dev-only (never imported by shipped code), and it replaces hand-maintained multi-line string literals that are already a maintenance cost; the trade-off is one more pinned package for less brittle assertions.
- **The composition function's override parameter is reachable from production code too**, since it is a normal keyword argument, not a test-only hook. This is accepted because it is also how `with_client` already works on `_create_wiki_composition` today: a literal, typed override a caller can supply deliberately, not a backdoor.
