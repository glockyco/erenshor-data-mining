"""Durable recovery artifacts around native wiki mutations."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Callable
from dataclasses import replace
from os.path import relpath
from pathlib import Path
from typing import Any, Literal

import pytest
from tests.fakes.mediawiki import MediaWikiFake

from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.application.wiki_deploy.articles import deploy_articles, plan_article_deploy
from erenshor.application.wiki_deploy.guarded_edits import GuardedPageEdit, apply_guarded_edits
from erenshor.application.wiki_deploy.manifest import (
    RepoWikiPageManifest,
    RepoWikiPageManifestEntry,
    durable_write_text,
    read_repo_page_manifest,
    write_repo_page_manifest,
)
from erenshor.application.wiki_deploy.pages import deploy_repo_pages
from erenshor.application.wiki_deploy.rollback import rollback_repo_pages
from erenshor.infrastructure.wiki import MediaWikiEditConflictError, MediaWikiNetworkError
from erenshor.infrastructure.wiki.client import MediaWikiEditVerificationError

Engine = Literal["repo", "article", "prose"]
Event = tuple[str, Any]
_OLD = "Editor text"
_NEW = "return 'approved $RUN/example and $REPO/example'"


def _observe_durability(monkeypatch: pytest.MonkeyPatch, events: list[Event]) -> None:
    original_open = os.open
    original_fsync = os.fsync
    original_replace = os.replace
    directories: dict[int, Path] = {}

    def observe_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        descriptor = original_open(path, flags, *args, **kwargs)
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            directories[descriptor] = Path(path).resolve()
        return descriptor

    def observe_fsync(descriptor: int) -> None:
        original_fsync(descriptor)
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            events.append(("directory_fsync", directories[descriptor]))
        else:
            events.append(("file_fsync", os.pread(descriptor, os.fstat(descriptor).st_size, 0)))

    def observe_replace(source: Any, destination: Any, *args: Any, **kwargs: Any) -> None:
        original_replace(source, destination, *args, **kwargs)
        events.append(("replace", Path(destination).resolve()))

    monkeypatch.setattr(os, "open", observe_open)
    monkeypatch.setattr(os, "fsync", observe_fsync)
    monkeypatch.setattr(os, "replace", observe_replace)


def _engine(engine: Engine, tmp_path: Path, events: list[Event]) -> tuple[Callable[[], Any], MediaWikiFake, Path]:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    external = tmp_path / "external-storage"
    external.mkdir()
    run = external / "run"
    manifest_path = run / "manifest.json"
    wiki = MediaWikiFake()
    title = "Module:Example" if engine == "repo" else "Alpha"
    wiki.put_page(title, _OLD)
    edit = wiki.safe_edit_page

    def mutate(*args: Any, **kwargs: Any) -> int:
        native = read_repo_page_manifest(manifest_path)
        [entry] = native.entries
        assert entry.new_revision_id is None
        assert entry.pending_mutation
        assert entry.pending_operation == "deploy"
        assert entry.pending_base_revision_id == 1
        assert entry.rollback_text_source is not None
        assert entry.rollback_content_model == entry.content_model
        assert not Path(entry.source_path).is_absolute()
        assert not Path(entry.rollback_text_source).is_absolute()
        assert (repo_root / entry.source_path).read_text(encoding="utf-8") == _NEW
        assert (repo_root / entry.rollback_text_source).read_text(encoding="utf-8") == _OLD
        events.append(("provider_mutation", None))
        return edit(*args, **kwargs)

    wiki.safe_edit_page = mutate

    def checkpoint(manifest: RepoWikiPageManifest) -> None:
        write_repo_page_manifest(manifest, manifest_path)
        events.append(("checkpoint", manifest.entries[0].new_revision_id))

    if engine == "repo":
        source = external / "source.lua"
        source.write_text(_NEW, encoding="utf-8")

        manifest = RepoWikiPageManifest(
            entries=(
                RepoWikiPageManifestEntry(
                    title=title,
                    source_path=relpath(source, repo_root),
                    source_sha256=hashlib.sha256(_NEW.encode("utf-8")).hexdigest(),
                    ownership_class="lua_module",
                    upload_stage="lua_module",
                    content_model="Scribunto",
                ),
            )
        )

        def invoke() -> Any:
            return deploy_repo_pages(
                manifest=manifest,
                repo_root=repo_root,
                client=wiki,
                summary="Publish approved text",
                assertion="bot",
                assert_user=wiki.edit_account,
                rollback_root=run / "rollback",
                checkpoint=checkpoint,
            )

    elif engine == "article":
        storage = WikiStorage(external / "articles")
        storage.save_fetched_by_title(title, ["item:alpha"], _OLD, 1)
        storage.save_generated_by_title(title, ["item:alpha"], _NEW)
        plan = plan_article_deploy(storage)

        def invoke() -> Any:
            return deploy_articles(
                plan,
                client=wiki,
                storage=storage,
                repo_root=repo_root,
                rollback_root=run / "rollback",
                summary="Publish approved text",
                assert_user=wiki.edit_account,
                checkpoint=checkpoint,
            )

    else:
        revision = wiki.get_page_snapshots([title])[title].revision
        assert revision is not None

        def invoke() -> Any:
            return apply_guarded_edits(
                [GuardedPageEdit(title, "Publish approved text", _NEW, _OLD, revision)],
                repo_root=repo_root,
                run_dir=run,
                client=wiki,
                assert_user=wiki.edit_account,
                checkpoint=checkpoint,
            )

    return invoke, wiki, manifest_path


def _assert_durable_replace(events: list[Event], path: Path, content: bytes) -> None:
    replacement = events.index(("replace", path.resolve()))
    assert ("file_fsync", content) in events[:replacement]
    assert ("directory_fsync", path.parent.resolve()) in events[replacement + 1 :]


def test_manifest_replacement_fsyncs_bytes_then_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "manifest.json"
    events: list[Event] = []
    _observe_durability(monkeypatch, events)

    write_repo_page_manifest(RepoWikiPageManifest(entries=()), path)

    assert events[:2] == [
        (
            "file_fsync",
            b'{\n  "api_url": null,\n  "entries": [],\n  "variant": null,\n  "wiki_root": null\n}\n',
        ),
        ("replace", path.resolve()),
    ]
    assert events[2:] == [("directory_fsync", directory.resolve()) for directory in (path.parent, *path.parent.parents)]
    assert read_repo_page_manifest(path).entries == ()


def test_durable_text_persists_new_parent_directory_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[Event] = []
    _observe_durability(monkeypatch, events)
    path = tmp_path / "run" / "planned" / "page.wiki"

    durable_write_text(path, _NEW)

    assert events[:2] == [
        ("file_fsync", _NEW.encode("utf-8")),
        ("replace", path.resolve()),
    ]
    assert events[2:] == [("directory_fsync", directory.resolve()) for directory in (path.parent, *path.parent.parents)]


@pytest.mark.parametrize("engine", ["repo", "article", "prose"])
def test_native_mutation_follows_durable_artifacts_and_precedes_final_checkpoint(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[Event] = []
    invoke, _, manifest_path = _engine(engine, tmp_path, events)
    _observe_durability(monkeypatch, events)

    invoke()
    events.append(("returned", None))

    mutation = events.index(("provider_mutation", None))
    before = events[:mutation]
    planned_manifest = next(content for kind, content in before if kind == "file_fsync" and content.startswith(b"{"))
    [entry] = json.loads(planned_manifest)["entries"]
    repo_root = tmp_path / "repo"
    if engine == "prose":
        _assert_durable_replace(before, repo_root / entry["source_path"], _NEW.encode("utf-8"))
    _assert_durable_replace(before, repo_root / entry["rollback_text_source"], _OLD.encode("utf-8"))
    _assert_durable_replace(before, manifest_path, planned_manifest)
    assert before[-1] == ("checkpoint", None)
    after = events[mutation + 1 :]
    final_manifest = next(content for kind, content in after if kind == "file_fsync" and content.startswith(b"{"))
    assert json.loads(final_manifest)["entries"][0]["new_revision_id"] == 2
    _assert_durable_replace(after, manifest_path, final_manifest)
    assert after[-2:] == [("checkpoint", 2), ("returned", None)]
    assert read_repo_page_manifest(manifest_path).entries[0].new_revision_id == 2


@pytest.mark.parametrize(
    ("engine", "artifact"),
    [
        ("repo", "rollback"),
        ("repo", "manifest"),
        ("article", "rollback"),
        ("article", "manifest"),
        ("prose", "source"),
        ("prose", "rollback"),
        ("prose", "manifest"),
    ],
)
@pytest.mark.parametrize("boundary", ["file", "directory"])
def test_native_durability_failure_prevents_provider_mutation(
    engine: Engine,
    artifact: str,
    boundary: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[Event] = []
    invoke, wiki, _ = _engine(engine, tmp_path, events)
    original_fsync = os.fsync
    original_replace = os.replace
    last_artifact: str | None = None
    failed = False

    def classify(content: bytes) -> str:
        if content == _NEW.encode("utf-8"):
            return "source"
        if content == _OLD.encode("utf-8"):
            return "rollback"
        assert "entries" in json.loads(content)
        return "manifest"

    def remember_replace(source: Any, destination: Any, *args: Any, **kwargs: Any) -> None:
        nonlocal last_artifact
        last_artifact = classify(Path(source).read_bytes())
        original_replace(source, destination, *args, **kwargs)

    def fail_fsync(descriptor: int) -> None:
        nonlocal failed
        is_directory = stat.S_ISDIR(os.fstat(descriptor).st_mode)
        current = last_artifact if is_directory else classify(os.pread(descriptor, os.fstat(descriptor).st_size, 0))
        if current == artifact and is_directory == (boundary == "directory"):
            failed = True
            raise OSError("injected durability failure")
        original_fsync(descriptor)

    monkeypatch.setattr(os, "replace", remember_replace)
    monkeypatch.setattr(os, "fsync", fail_fsync)

    with pytest.raises(OSError, match="injected durability failure"):
        invoke()

    assert failed
    assert ("provider_mutation", None) not in events
    assert set(wiki.revisions.values()) == {1}


@pytest.mark.parametrize("engine", ["repo", "article", "prose"])
@pytest.mark.parametrize("boundary", ["file", "directory"])
def test_final_manifest_durability_failure_does_not_return_success(
    engine: Engine, boundary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[Event] = []
    invoke, wiki, _ = _engine(engine, tmp_path, events)
    original_fsync = os.fsync
    completed_manifest = False

    def fail_completed_manifest(descriptor: int) -> None:
        nonlocal completed_manifest
        is_directory = stat.S_ISDIR(os.fstat(descriptor).st_mode)
        if not is_directory:
            content = os.pread(descriptor, os.fstat(descriptor).st_size, 0)
            completed_manifest = (
                content.startswith(b"{") and json.loads(content)["entries"][0]["new_revision_id"] is not None
            )
        if completed_manifest and is_directory == (boundary == "directory"):
            raise OSError("injected final checkpoint failure")
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fail_completed_manifest)

    with pytest.raises(OSError, match="injected final checkpoint failure"):
        invoke()

    assert ("provider_mutation", None) in events
    assert ("checkpoint", 2) not in events
    assert set(wiki.revisions.values()) == {2}


def test_failed_manifest_file_fsync_keeps_previous_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "manifest.json"
    original = '{"entries": []}\n'
    path.write_text(original, encoding="utf-8")

    def fail_fsync(descriptor: int) -> None:
        raise OSError("injected manifest file failure")

    monkeypatch.setattr(os, "fsync", fail_fsync)

    with pytest.raises(OSError, match="injected manifest file failure"):
        write_repo_page_manifest(RepoWikiPageManifest(entries=()), path)

    assert path.read_text(encoding="utf-8") == original
    assert set(tmp_path.iterdir()) == {path}


def test_guarded_edit_keeps_account_and_checkpoint_optional(tmp_path: Path) -> None:
    wiki = MediaWikiFake()
    wiki.put_page("Alpha", _OLD)
    revision = wiki.get_page_snapshots(["Alpha"])["Alpha"].revision
    assert revision is not None
    run = tmp_path / "external-storage" / "run"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    result = apply_guarded_edits(
        [GuardedPageEdit("Alpha", "Publish approved text", _NEW, _OLD, revision)],
        repo_root=repo_root,
        run_dir=run,
        client=wiki,
    )

    assert not result.failed
    assert result.edited == ("Alpha",)
    [entry] = read_repo_page_manifest(result.manifest_path).entries
    assert entry.new_revision_id == 2
    assert entry.rollback_text_source is not None
    assert (repo_root / entry.rollback_text_source).read_text(encoding="utf-8") == _OLD


@pytest.mark.parametrize("engine", ["repo", "article", "prose"])
@pytest.mark.parametrize("failure", [MediaWikiNetworkError, KeyboardInterrupt])
def test_lost_write_response_stays_pending_and_can_be_recovered(
    engine: Engine, failure: type[BaseException], tmp_path: Path
) -> None:
    events: list[Event] = []
    invoke, wiki, manifest_path = _engine(engine, tmp_path, events)
    edit = wiki.safe_edit_page

    def lose_response(*args: Any, **kwargs: Any) -> int:
        edit(*args, **kwargs)
        raise failure("lost response after remote commit")

    wiki.safe_edit_page = lose_response
    if engine == "repo" or failure is KeyboardInterrupt:
        with pytest.raises(failure):
            invoke()
    else:
        result = invoke()
        assert result.failed
    native = read_repo_page_manifest(manifest_path)
    [entry] = native.entries
    assert entry.pending_mutation
    assert entry.new_revision_id is None
    assert entry.deploy_action != "unchanged"
    assert set(wiki.revisions.values()) == {2}

    # The forward-only durability observer expects no receipt, so remove it.
    wiki.safe_edit_page = MediaWikiFake.safe_edit_page.__get__(wiki)
    rollback_repo_pages(
        manifest=native,
        repo_root=tmp_path / "repo",
        client=wiki,
        summary="Restore reviewed preimage",
        assertion="bot",
        checkpoint=lambda manifest: write_repo_page_manifest(manifest, manifest_path),
    )
    [recovered] = read_repo_page_manifest(manifest_path).entries
    assert recovered.new_revision_id == 2
    assert recovered.rollback_revision_id == 3
    assert not recovered.pending_mutation
    assert set(wiki.pages.values()) == {_OLD}


@pytest.mark.parametrize("engine", ["repo", "article", "prose"])
def test_explicit_rejection_clears_pending_without_a_receipt(engine: Engine, tmp_path: Path) -> None:
    events: list[Event] = []
    invoke, wiki, manifest_path = _engine(engine, tmp_path, events)

    def reject(*args: Any, **kwargs: Any) -> int:
        assert read_repo_page_manifest(manifest_path).entries[0].pending_mutation
        raise MediaWikiEditConflictError("explicit edit conflict")

    wiki.safe_edit_page = reject
    if engine == "repo":
        with pytest.raises(MediaWikiEditConflictError):
            invoke()
    else:
        assert invoke().failed
    [entry] = read_repo_page_manifest(manifest_path).entries
    assert not entry.pending_mutation
    assert entry.new_revision_id is None
    assert set(wiki.revisions.values()) == {1}


@pytest.mark.parametrize("engine", ["repo", "article", "prose"])
def test_unchanged_base_does_not_settle_an_unknown_request(engine: Engine, tmp_path: Path) -> None:
    invoke, wiki, manifest_path = _engine(engine, tmp_path, [])
    edit = wiki.safe_edit_page

    def fail_before_commit(*args: Any, **kwargs: Any) -> int:
        raise MediaWikiNetworkError("lost request")

    wiki.safe_edit_page = fail_before_commit
    if engine == "repo":
        with pytest.raises(MediaWikiNetworkError):
            invoke()
    else:
        assert invoke().failed
    assert read_repo_page_manifest(manifest_path).entries[0].pending_mutation
    with pytest.raises(ValueError, match="unchanged base"):
        rollback_repo_pages(
            manifest=read_repo_page_manifest(manifest_path),
            repo_root=tmp_path / "repo",
            client=wiki,
            summary="Restore",
            assertion="bot",
            checkpoint=lambda manifest: write_repo_page_manifest(manifest, manifest_path),
        )
    pending = read_repo_page_manifest(manifest_path).entries[0]
    assert pending.pending_mutation
    assert pending.new_revision_id is None
    assert set(wiki.revisions.values()) == {1}
    source = (tmp_path / "repo" / pending.source_path).read_bytes().decode("utf-8")
    base = wiki.get_page_revision_metadata(pending.title)
    revision_id = edit(pending.title, source, base)
    assert wiki.revisions[pending.title] == revision_id
    assert read_repo_page_manifest(manifest_path).entries[0].pending_mutation


def test_article_receipt_is_checkpointed_before_local_storage_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invoke, wiki, manifest_path = _engine("article", tmp_path, [])

    def fail_storage(*args: Any, **kwargs: Any) -> None:
        raise OSError("local storage unavailable")

    monkeypatch.setattr(WikiStorage, "record_deployed", fail_storage)
    with pytest.raises(OSError, match="local storage unavailable"):
        invoke()
    native = read_repo_page_manifest(manifest_path)
    assert native.entries[0].new_revision_id == 2
    assert not native.entries[0].pending_mutation
    wiki.safe_edit_page = MediaWikiFake.safe_edit_page.__get__(wiki)
    rollback_repo_pages(manifest=native, repo_root=tmp_path / "repo", client=wiki, summary="Restore", assertion="bot")
    assert set(wiki.pages.values()) == {_OLD}


def test_guarded_manifest_binds_actual_endpoint_and_variant_root(tmp_path: Path) -> None:
    wiki = MediaWikiFake()
    wiki.api_url = "https://wiki.example/api.php"
    wiki.put_page("Alpha", _OLD)
    revision = wiki.get_page_snapshots(["Alpha"])["Alpha"].revision
    assert revision is not None
    wiki_root = tmp_path / "variants" / "canary" / "wiki"
    result = apply_guarded_edits(
        [GuardedPageEdit("Alpha", "Publish approved text", _NEW, _OLD, revision)],
        repo_root=tmp_path,
        run_dir=wiki_root / "run",
        client=wiki,
        variant="canary",
        wiki_root=wiki_root,
    )
    native = read_repo_page_manifest(result.manifest_path)
    assert native.api_url == wiki.api_url
    assert native.variant == "canary"
    assert native.wiki_root == str(wiki_root.resolve())


@pytest.mark.parametrize("proof_gap", ["missing_parent", "intervening_revision", "legacy_intent"])
def test_pending_forward_receipt_requires_exact_request_ancestry(tmp_path: Path, proof_gap: str) -> None:
    invoke, wiki, manifest_path = _engine("repo", tmp_path, [])
    edit = wiki.safe_edit_page

    def lose_response(*args: Any, **kwargs: Any) -> int:
        edit(*args, **kwargs)
        raise MediaWikiNetworkError("lost receipt")

    wiki.safe_edit_page = lose_response
    with pytest.raises(MediaWikiNetworkError):
        invoke()
    native = read_repo_page_manifest(manifest_path)
    [entry] = native.entries
    assert entry.pending_operation == "deploy"
    assert entry.pending_base_revision_id == 1
    wiki.safe_edit_page = MediaWikiFake.safe_edit_page.__get__(wiki)
    if proof_gap == "missing_parent":
        wiki.page_parents.pop(entry.title)
    elif proof_gap == "intervening_revision":
        wiki.put_page(entry.title, "intervening editor text", user="Editor")
        wiki.put_page(entry.title, _NEW)
    else:
        native = replace(native, entries=(replace(entry, pending_operation=None, pending_base_revision_id=None),))
        write_repo_page_manifest(native, manifest_path)
    saved = manifest_path.read_bytes()
    revisions = wiki.revisions.copy()
    with pytest.raises(ValueError, match="Cannot reconcile pending remote mutation"):
        rollback_repo_pages(
            manifest=native,
            repo_root=tmp_path / "repo",
            client=wiki,
            summary="Restore",
            assertion="bot",
            force=True,
            checkpoint=lambda manifest: write_repo_page_manifest(manifest, manifest_path),
        )
    assert wiki.revisions == revisions
    assert manifest_path.read_bytes() == saved


def test_guarded_edit_forwards_user_assertion_and_exact_account(tmp_path: Path) -> None:
    wiki = MediaWikiFake(edit_account="WikiSysop", is_bot=False)
    title = "User:WikiSysop/Native acceptance"
    wiki.put_page(title, _OLD)
    revision = wiki.get_page_snapshots([title])[title].revision
    assert revision is not None
    edit = wiki.safe_edit_page
    observed: list[tuple[str, str]] = []

    def observe_assertion(*args: Any, **kwargs: Any) -> int:
        observed.append((kwargs["assertion"], kwargs["assert_user"]))
        return edit(*args, **kwargs)

    wiki.safe_edit_page = observe_assertion
    result = apply_guarded_edits(
        [GuardedPageEdit(title, "Publish approved text", _NEW, _OLD, revision)],
        repo_root=tmp_path,
        run_dir=tmp_path / "run",
        client=wiki,
        assertion="user",
        assert_user="WikiSysop",
    )

    assert not result.failed
    assert result.edited == (title,)
    assert observed == [("user", "WikiSysop")]
    assert wiki.pages[title] == _NEW
    assert wiki.page_users[title] == "WikiSysop"


def _merged_engine(
    engine: Engine,
    tmp_path: Path,
    *,
    parent_available: bool = True,
    parent_model_available: bool = True,
    written_model: str | None = None,
) -> tuple[Callable[[], Any], MediaWikiFake, Path, list[Path]]:
    invoke, wiki, manifest_path = _engine(engine, tmp_path, [])
    preimages: list[Path] = []

    def merged_write(*args: Any, **kwargs: Any) -> int:
        [entry] = read_repo_page_manifest(manifest_path).entries
        assert entry.pending_mutation
        assert entry.rollback_text_source is not None
        preimages.append(tmp_path / "repo" / entry.rollback_text_source)
        title = kwargs["title"]
        wiki.put_page(title, "later editor change", user="Editor")
        parent = wiki.get_page_snapshots([title])[title]
        if not parent_model_available:
            parent = replace(parent, content_model=None)
        wiki.put_page(title, _NEW + "\nlater editor change", content_model=written_model)
        written = wiki.get_page_snapshots([title])[title]
        assert written.revision is not None
        raise MediaWikiEditVerificationError(
            "Acknowledged write did not match the reviewed revision",
            new_revision_id=written.revision.revision_id,
            written_snapshot=written,
            actual_parent_snapshot=parent if parent_available else None,
        )

    wiki.safe_edit_page = merged_write
    return invoke, wiki, manifest_path, preimages


@pytest.mark.parametrize("engine", ["repo", "article", "prose"])
def test_merged_write_keeps_receipt_and_actual_editor_preimage(engine: Engine, tmp_path: Path) -> None:
    invoke, wiki, manifest_path, preimages = _merged_engine(engine, tmp_path)
    if engine == "repo":
        with pytest.raises(MediaWikiEditVerificationError):
            invoke()
    else:
        assert invoke().failed
    native = read_repo_page_manifest(manifest_path)
    [entry] = native.entries
    assert entry.pending_acknowledged_revision_id == 3
    assert entry.new_revision_id == 3
    assert entry.old_revision_id == 2
    assert entry.requires_rollback
    assert not entry.pending_mutation
    assert preimages[0].read_bytes() == _OLD.encode("utf-8")
    assert entry.rollback_text_source is not None
    actual_preimage = tmp_path / "repo" / entry.rollback_text_source
    assert actual_preimage != preimages[0]
    assert actual_preimage.read_bytes() == b"later editor change"

    wiki.safe_edit_page = MediaWikiFake.safe_edit_page.__get__(wiki)
    rollback_repo_pages(
        manifest=native,
        repo_root=tmp_path / "repo",
        client=wiki,
        summary="Restore actual parent",
        assertion="bot",
        checkpoint=lambda manifest: write_repo_page_manifest(manifest, manifest_path),
    )
    [restored] = read_repo_page_manifest(manifest_path).entries
    assert restored.new_revision_id == 3
    assert restored.rollback_revision_id == 4
    assert not restored.requires_rollback
    assert set(wiki.pages.values()) == {"later editor change"}
    assert preimages[0].read_bytes() == _OLD.encode("utf-8")


@pytest.mark.parametrize("engine", ["repo", "article", "prose"])
def test_merged_write_without_actual_parent_stays_uncertain(engine: Engine, tmp_path: Path) -> None:
    invoke, wiki, manifest_path, _ = _merged_engine(engine, tmp_path, parent_available=False)
    if engine == "repo":
        with pytest.raises(MediaWikiEditVerificationError):
            invoke()
    else:
        assert invoke().failed
    native = read_repo_page_manifest(manifest_path)
    [entry] = native.entries
    assert entry.pending_mutation
    assert entry.requires_rollback
    assert entry.pending_acknowledged_revision_id == 3
    assert entry.new_revision_id == 3
    assert entry.old_revision_id == 1
    with pytest.raises(ValueError, match="Cannot reconcile pending remote mutation"):
        rollback_repo_pages(
            manifest=native, repo_root=tmp_path / "repo", client=wiki, summary="Restore", assertion="bot", force=True
        )
    assert set(wiki.revisions.values()) == {3}


@pytest.mark.parametrize("engine", ["repo", "article", "prose"])
def test_merged_receipt_is_saved_before_actual_preimage_failure(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from erenshor.application.wiki_deploy import pages

    invoke, wiki, manifest_path, preimages = _merged_engine(engine, tmp_path)
    original_write = pages.durable_write_text

    def fail_actual_parent(path: Path, text: str) -> None:
        if ".parent-" in path.name:
            raise OSError("actual parent sidecar unavailable")
        original_write(path, text)

    monkeypatch.setattr(pages, "durable_write_text", fail_actual_parent)
    with pytest.raises(OSError, match="actual parent sidecar unavailable"):
        invoke()
    [entry] = read_repo_page_manifest(manifest_path).entries
    assert entry.pending_mutation
    assert entry.requires_rollback
    assert entry.pending_acknowledged_revision_id == 3
    assert entry.new_revision_id == 3
    assert preimages[0].read_bytes() == _OLD.encode("utf-8")
    assert set(wiki.revisions.values()) == {3}


@pytest.mark.parametrize("engine", ["repo", "article", "prose"])
def test_pending_same_text_and_parent_with_wrong_model_is_not_adopted(engine: Engine, tmp_path: Path) -> None:
    invoke, wiki, manifest_path = _engine(engine, tmp_path, [])
    edit = wiki.safe_edit_page

    def lose_wrong_model_receipt(*args: Any, **kwargs: Any) -> int:
        kwargs["content_model"] = "wikitext" if engine == "repo" else "Scribunto"
        edit(*args, **kwargs)
        raise MediaWikiNetworkError("wrong-model response lost")

    wiki.safe_edit_page = lose_wrong_model_receipt
    if engine == "repo":
        with pytest.raises(MediaWikiNetworkError):
            invoke()
    else:
        assert invoke().failed
    native = read_repo_page_manifest(manifest_path)
    [entry] = native.entries
    assert entry.pending_mutation
    assert wiki.pages[entry.title] == _NEW
    assert wiki.content_models[entry.title] != entry.content_model
    with pytest.raises(ValueError, match="Cannot reconcile pending remote mutation"):
        rollback_repo_pages(
            manifest=native, repo_root=tmp_path / "repo", client=wiki, summary="Restore", assertion="bot", force=True
        )
    assert wiki.revisions[entry.title] == 2


@pytest.mark.parametrize("engine", ["repo", "article", "prose"])
def test_verified_mismatch_without_actual_parent_model_stays_pending(engine: Engine, tmp_path: Path) -> None:
    invoke, _, manifest_path, preimages = _merged_engine(engine, tmp_path, parent_model_available=False)
    if engine == "repo":
        with pytest.raises(MediaWikiEditVerificationError):
            invoke()
    else:
        assert invoke().failed
    [entry] = read_repo_page_manifest(manifest_path).entries
    assert entry.pending_mutation
    assert entry.requires_rollback
    assert entry.pending_acknowledged_revision_id == 3
    assert entry.old_revision_id == 1
    assert preimages[0].read_bytes() == _OLD.encode("utf-8")


@pytest.mark.parametrize("engine", ["repo", "article", "prose"])
def test_verified_wrong_model_restores_actual_parent_model_and_text(engine: Engine, tmp_path: Path) -> None:
    invoke, wiki, manifest_path, _ = _merged_engine(engine, tmp_path, written_model="json")
    if engine == "repo":
        with pytest.raises(MediaWikiEditVerificationError):
            invoke()
    else:
        assert invoke().failed
    native = read_repo_page_manifest(manifest_path)
    [entry] = native.entries
    expected_model = "Scribunto" if engine == "repo" else "wikitext"
    assert not entry.pending_mutation
    assert entry.requires_rollback
    assert entry.rollback_content_model == expected_model
    assert wiki.content_models[entry.title] == "json"
    wiki.safe_edit_page = MediaWikiFake.safe_edit_page.__get__(wiki)

    rollback_repo_pages(
        manifest=native,
        repo_root=tmp_path / "repo",
        client=wiki,
        summary="Restore actual parent",
        assertion="bot",
        checkpoint=lambda manifest: write_repo_page_manifest(manifest, manifest_path),
    )

    assert wiki.pages[entry.title] == "later editor change"
    assert wiki.content_models[entry.title] == expected_model
    [restored] = read_repo_page_manifest(manifest_path).entries
    assert not restored.requires_rollback
    assert restored.rollback_revision_id == 4


def test_guarded_explicit_model_is_forwarded_and_recorded_for_rollback(tmp_path: Path) -> None:
    wiki = MediaWikiFake()
    title = "Module:NativeModel"
    wiki.put_page(title, _OLD, content_model="Scribunto")
    revision = wiki.get_page_snapshots([title])[title].revision
    assert revision is not None
    result = apply_guarded_edits(
        [GuardedPageEdit(title, "Publish approved text", _NEW, _OLD, revision, content_model="Scribunto")],
        repo_root=tmp_path,
        run_dir=tmp_path / "run",
        client=wiki,
    )
    assert not result.failed
    [entry] = read_repo_page_manifest(result.manifest_path).entries
    assert entry.content_model == "Scribunto"
    assert entry.rollback_content_model == "Scribunto"
    assert wiki.content_models[title] == "Scribunto"


@pytest.mark.parametrize("force", [False, True])
def test_missing_page_does_not_settle_a_pending_creation(tmp_path: Path, force: bool) -> None:
    source = tmp_path / "candidate.wiki"
    source.write_bytes(b"Candidate source")
    wiki = MediaWikiFake()
    manifest = RepoWikiPageManifest(
        entries=(
            RepoWikiPageManifestEntry(
                title="New Candidate",
                source_path="candidate.wiki",
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                ownership_class="article",
                upload_stage="article",
                content_model="wikitext",
                pending_mutation=True,
                pending_operation="deploy",
                pending_base_revision_id=0,
            ),
        ),
        api_url=wiki.api_url,
    )
    manifest_path = tmp_path / "manifest.json"
    write_repo_page_manifest(manifest, manifest_path)
    with pytest.raises(ValueError, match="unchanged base"):
        rollback_repo_pages(
            manifest=manifest,
            repo_root=tmp_path,
            client=wiki,
            summary="Restore",
            assertion="bot",
            force=force,
            checkpoint=lambda updated: write_repo_page_manifest(updated, manifest_path),
        )
    assert not wiki.pages
    assert read_repo_page_manifest(manifest_path).entries[0].pending_mutation
