# Tasks

## 1. Shared fake and its contract test

- [ ] 1.1 Write `tests/fakes/mediawiki.py`: one stateful class covering the full union of methods the eight existing fakes implement (`get_page_snapshots`, `safe_edit_page`, `safe_create_page`, `list_files`, `list_file_pages`, `move_page`, `delete_page`, `undelete_page`, `download`, `upload_file`, `confirm_upload`, `get_file_versions`, `is_file_used`, `purge_pages`), built from the richest existing implementation (`tests/unit/application/services/test_image_publication.py`'s `FakeWiki`). Verify: a throwaway script constructs it and exercises create, move over a redirect, delete, and undelete without error.
- [ ] 1.2 Add a contract test suite that runs create-a-page, edit-twice-and-read-revision-history, upload-a-file, move-a-file-over-a-redirect, and delete-then-undelete against both the shared fake and the local Docker wiki, and asserts the same observable outcome from each. Verify: the contract suite passes against both targets with the local wiki running (`wiki-dev/compose.yml`).

## 2. Composition-root overrides, one command module at a time

- [ ] 2.1 Add an optional collaborator-override parameter to `cli/mediawiki.py`'s `create_readonly_mediawiki_client`, defaulting to building the real client as today. Verify: a throwaway script calls it with an override and gets that exact object back; calling it without one is unchanged.
- [ ] 2.2 Add the same override to `commands/sheets.py`'s `_create_sheets_service`, and migrate every `@patch("erenshor.cli.commands.sheets._create_sheets_service")` test in `tests/unit/cli/commands/test_sheets.py` to supply the shared fake (or a `SheetsService` test double) through the override instead, deleting any assertion that only checks the collaborator was called. Verify: `test_sheets.py` passes with zero `@patch` call sites remaining in the file.
- [ ] 2.3 Add the same override to `commands/images.py`'s `_bot_client` and `_administrator_client`. Verify: a throwaway script builds an `images publish` run with the shared fake supplied through the override and confirms no network call is made.
- [ ] 2.4 Add the same override to each of `commands/wiki.py`'s five collaborator factories, including `_create_wiki_composition`, and migrate `test_wiki.py`'s patch-by-path tests for those factories to the override. Verify: `test_wiki.py` passes with zero `@patch("erenshor.cli.commands.wiki.` call sites remaining.

## 3. Retire the eight duplicate fakes

- [ ] 3.1 Migrate `tests/unit/application/wiki_deploy/test_pages.py`'s `RecordingWikiClient` to the shared fake, deleting the local class. Verify: the file's suite passes unchanged in scenario coverage.
- [ ] 3.2 Migrate `tests/unit/application/wiki_deploy/test_rollback.py`'s `RecordingRollbackClient` the same way. Same verification.
- [ ] 3.3 Migrate `tests/unit/application/wiki_deploy/test_page_edits.py`'s `_Wiki` the same way. Same verification.
- [ ] 3.4 Migrate `tests/unit/application/wiki_deploy/test_render_check.py`'s `Wiki` the same way. Same verification.
- [ ] 3.5 Migrate `tests/unit/application/wiki_deploy/test_link_audit_service.py`'s `FakeClient` the same way. Same verification.
- [ ] 3.6 Migrate `tests/unit/application/wiki_deploy/test_articles.py`'s `FakeWiki` the same way. Same verification.
- [ ] 3.7 Migrate `tests/unit/application/services/test_image_publication.py`'s `FakeWiki` to import the now-shared class instead of defining its own (this file's version is the one the shared fake was built from). Same verification.
- [ ] 3.8 Migrate `tests/unit/application/wiki_interface/test_deploy.py`'s `FakeInterfaceClient` the same way. Same verification.

## 4. Replace rendering pins

- [ ] 4.1 Add `inline-snapshot` to the Python dev dependencies and lock it. Verify: `uv lock --check` passes and the package imports in a throwaway script.
- [ ] 4.2 Replace every CLI test that compares a multi-line substring against rendered console output with an assertion on the command's typed result, where the command already returns or raises one; take an `inline-snapshot` baseline only where no such value exists. Verify: no test file under `tests/unit/cli` compares a multi-line string literal against `result.output` or `capsys.readouterr()` with `in`.
- [ ] 4.3 Rework `wiki-dev/smoke_test.py` to select each checked page by a structural selector (a heading, an infobox field, a category link) instead of a literal substring, converting every row of `wiki-dev/fixtures/smoke.tsv` one for one. Verify: `uv run python wiki-dev/smoke_test.py` reports at least the same 55 PASS against the local wiki, with no row dropped.

## 5. Close out

- [ ] 5.1 Confirm no duplicate MediaWiki test double remains outside `tests/fakes/` and no `@patch("erenshor...")` call site remains anywhere in `tests/`. Verify: `grep -rn "@patch(\"erenshor\." tests/` and a search for the eight retired class names both return nothing, and `uv run erenshor test ci` passes.
