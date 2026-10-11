# Proposal

## Why

The Python test suite has grown eleven separate hand-rolled fakes for the MediaWiki client, 40 `@patch("erenshor...")` decorators that bind a CLI command to a collaborator by its exact dotted import path, and assertions that pin an exact argv list, an exact kwargs dict, or a literal multi-line substring of rendered console or HTML text. None of this fails when the behavior it names breaks (several CLI tests only assert that a mock was called, which is true whether the command works or not), and all of it breaks on an unrelated, correct refactor: a dependency-major migration this session renamed one command-line flag and had to update an exact-argv assertion in three unrelated places to match. The suite already proved its own fragility once; fixing the cause is cheaper than patching each symptom again next time.

## What Changes

- Add a single, stateful `tests/fakes/MediaWikiFake` that implements the read and write surface the eleven existing fakes each reimplement separately, contract-tested against the local Docker wiki so it cannot drift from what the real server actually does.
- Give each CLI command's external-client factory (wiki client, Sheets service, and similar) an override parameter, and make tests pass their double through it, so the production construction path runs and only the client is replaced.
- Replace every CLI test that only asserts a mock was called, or that checks nothing a no-op command would fail, with a test that asserts what the command produces at its boundary: its written state, its exit code, or the arguments it passes to the service it adapts to.
- Replace a multi-line substring assertion against rendered console or HTML text with a structural comparison (parsed fields, or a DOM/element query), or with an `inline-snapshot` baseline where a text comparison is genuinely the right check.
- Rework `wiki-dev/smoke_test.py` to select each checked page by its rendered element or structure instead of a literal HTML substring recorded in `wiki-dev/fixtures/smoke.tsv`.

Out of scope for this change, as smaller follow-ons once the above lands: Hypothesis-based property tests for the suite's pure rule functions, and a ruff `banned-api` rule retiring `unittest.mock` repo-wide (premature before the fake and the composition root exist to replace what it would forbid). Mutation testing (`mutmut`) is a possible later addition, not committed work here.

## Capabilities

### New Capabilities

- `test-infrastructure`: the durable conventions for how this repository's own test suite is built: one maintained fake per external system the suite talks to, one composition root per CLI command for collaborator injection, and a preference for structural or behavioral assertions over incidental rendering or wiring detail.

### Modified Capabilities

(none — this change does not alter the behavior of any shipped system; it governs how that behavior is verified)

## Impact

- Code: `src/erenshor/cli/commands/*.py` (each command's collaborator construction), a new `tests/fakes/` package, the eleven call sites of today's separate MediaWiki fakes (`tests/unit/application/wiki_deploy/test_pages.py`, `test_rollback.py`, `test_page_edits.py`, `test_link_audit_service.py`, `test_render_check.py`, `test_articles.py`, `test_refresh.py`, `tests/unit/application/services/test_image_publication.py`, `tests/unit/application/wiki_interface/test_deploy.py`, `test_sync.py`, `tests/unit/cli/commands/test_wiki.py`'s `FakeDeployClient`), `tests/unit/cli/commands/test_sheets.py` and `test_wiki.py` (44 `@patch(...)` and `monkeypatch.setattr(module, "_create_...")` call sites across the two files that patch a collaborator-constructing factory by name, not counting the separate, out-of-scope `monkeypatch.setattr` call sites in `test_wiki.py` that stub a pure orchestration function or a directly-instantiated class), `wiki-dev/smoke_test.py` and `wiki-dev/fixtures/smoke.tsv`.
- Dependencies: adds `inline-snapshot` to the Python dev dependencies.
- Tests only: no production runtime code, shipped article, or deployed artifact changes as a result of this proposal.
