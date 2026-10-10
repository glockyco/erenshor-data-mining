# Tasks

## 1. Shared fake and its contract test

- [x] 1.1 Write `tests/fakes/mediawiki.py`: one stateful class covering the full union of methods the eleven existing fakes implement (`get_page_snapshots`, `get_page_revision_metadata`, `get_page`, `get_pages`, `get_page_categories`, `get_embeddedin_pages`, `get_category_members`, `get_linking_pages_by_title`, `get_wanted_pages`, `get_title_statuses`, `parse_wikitext`, `get_current_user_rights`, `login`, `safe_edit_page`, `safe_create_page`, `list_files`, `list_file_pages`, `move_page`, `delete_page`, `undelete_page`, `download`, `raw_page`, `media_file`, `media_file_by_path`, `upload_file`, `confirm_upload`, `get_file_versions`, `is_file_used`, `purge_pages`, `close`), built from the richest existing implementation (`tests/unit/application/services/test_image_publication.py`'s `FakeWiki`) and cross-checked against the narrow `Protocol` each application module already declares for its own slice of this surface (`WikiPageDeployClient`, `ArticleDeployClient`, `WikiRollbackClient`, `_AuditClient`, `WikiEmbeddedRefreshClient`, `PageEditClient`, `InterfaceDeployClient`, `InterfaceClient`). Per-scenario data a test needs to control (a `parse_wikitext` result, `get_embeddedin_pages`, category or link membership) is held as settable per-title state on the fake, not reimplemented with per-file logic. Verify: a throwaway script constructs it and exercises create, move over a redirect, delete, and undelete without error.
- [x] 1.2 Add a contract test suite that runs create-a-page, edit-twice-and-read-revision-history, upload-a-file, move-a-file-over-a-redirect, and delete-then-undelete against both the shared fake and the local Docker wiki, and asserts the same observable outcome from each. Verify: the contract suite passes against both targets with the local wiki running (`wiki-dev/compose.yml`).

## 2. Composition-root overrides, one command module at a time

- [x] 2.1 Add an optional collaborator-override parameter to `cli/mediawiki.py`'s `create_readonly_mediawiki_client`, defaulting to building the real client as today. Verify: a throwaway script calls it with an override and gets that exact object back; calling it without one is unchanged.
- [ ] 2.2 Add the same override to `commands/sheets.py`'s `_create_sheets_service`, and migrate every `@patch("erenshor.cli.commands.sheets._create_sheets_service")` test in `tests/unit/cli/commands/test_sheets.py` to supply the shared fake (or a `SheetsService` test double) through the override instead, deleting any assertion that only checks the collaborator was called. Verify: `test_sheets.py` passes with zero `@patch` call sites remaining in the file.
- [ ] 2.3 Add the same override to `commands/images.py`'s `_bot_client` and `_administrator_client`. Verify: a throwaway script builds an `images publish` run with the shared fake supplied through the override and confirms no network call is made.
- [ ] 2.4 Add the same override to each of `commands/wiki.py`'s five collaborator factories (`_create_wiki_composition`, `_create_mediawiki_client`, `_create_normal_bot_mediawiki_client`, `_create_interface_mediawiki_client`, `_create_lua_repositories`), and migrate `test_wiki.py`'s patch-by-path and setattr-by-name tests for those factories to the override, replacing the file's own `FakeDeployClient` with the shared fake where it stands in for the MediaWiki client. Verify: `test_wiki.py` passes with zero `@patch(` or `monkeypatch.setattr(wiki_command, ...)` call sites remaining for those five names; its other `monkeypatch.setattr` call sites (orchestration functions such as `deploy_repo_pages`, and classes such as `WikiStorage`) are a separate, legitimate CLI-isolation pattern and stay out of scope.

## 3. Retire the eleven duplicate fakes

- [ ] 3.1 Migrate `tests/unit/application/wiki_deploy/test_pages.py`'s `RecordingWikiClient` to the shared fake, deleting the local class. Verify: the file's suite passes unchanged in scenario coverage.
- [ ] 3.2 Migrate `tests/unit/application/wiki_deploy/test_rollback.py`'s `RecordingRollbackClient` the same way. Same verification.
- [ ] 3.3 Migrate `tests/unit/application/wiki_deploy/test_page_edits.py`'s `_Wiki` the same way. Same verification.
- [ ] 3.4 Migrate `tests/unit/application/wiki_deploy/test_render_check.py`'s `Wiki` the same way. Same verification.
- [ ] 3.5 Migrate `tests/unit/application/wiki_deploy/test_link_audit_service.py`'s `FakeClient` the same way. Same verification.
- [ ] 3.6 Migrate `tests/unit/application/wiki_deploy/test_articles.py`'s `FakeWiki` the same way. Same verification.
- [ ] 3.7 Migrate `tests/unit/application/services/test_image_publication.py`'s `FakeWiki` to import the now-shared class instead of defining its own (this file's version is the one the shared fake was built from). Same verification.
- [ ] 3.8 Migrate `tests/unit/application/wiki_interface/test_deploy.py`'s `FakeInterfaceClient` the same way. Same verification.
- [ ] 3.9 Migrate `tests/unit/application/wiki_deploy/test_refresh.py`'s `RecordingRefreshClient` the same way. Same verification.
- [ ] 3.10 Migrate `tests/unit/application/wiki_interface/test_sync.py`'s `FakeInterfaceClient` the same way. Same verification.

## 4. Replace rendering pins

- [ ] 4.1 Add `inline-snapshot` to the Python dev dependencies and lock it. Verify: `uv lock --check` passes and the package imports in a throwaway script.
- [ ] 4.2 Replace every CLI test that compares a multi-line substring against rendered console output with an assertion on the command's typed result, where the command already returns or raises one; take an `inline-snapshot` baseline only where no such value exists. Verify: no test file under `tests/unit/cli` compares a multi-line string literal against `result.output` or `capsys.readouterr()` with `in`.
- [ ] 4.3 Rework `wiki-dev/smoke_test.py` to select each checked page by a structural selector (a heading, an infobox field, a category link) instead of a literal substring, converting every row of `wiki-dev/fixtures/smoke.tsv` one for one. Verify: `uv run python wiki-dev/smoke_test.py` reports at least the same 55 PASS against the local wiki, with no row dropped.

## 5. Close out

- [ ] 5.1 Confirm no duplicate MediaWiki test double remains outside `tests/fakes/` and no `@patch("erenshor...")` call site remains anywhere in `tests/`. Verify: `grep -rn "@patch(\"erenshor\." tests/` and a search for the eleven retired class names both return nothing, and `uv run erenshor test ci` passes.
