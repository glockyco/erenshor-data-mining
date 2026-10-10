from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from tests.fakes.mediawiki import MediaWikiFake

from erenshor.application.wiki_interface.deploy import (
    InterfaceDeployError,
    InterfaceMutationError,
    InterfacePermissionError,
    InterfaceRevisionConflictError,
    deploy_interface_pages,
    plan_interface_pages,
    rollback_interface_pages,
)
from erenshor.application.wiki_interface.manifest import (
    InterfaceDeployManifest,
    InterfacePageManifestEntry,
    read_interface_deploy_manifest,
    write_interface_deploy_manifest,
)


def _repo(tmp_path: Path, *, css: bytes = b"body { color: red; }\n", js: bytes = b"console.log('x');\n") -> None:
    root = tmp_path / "wiki" / "gadgets"
    root.mkdir(parents=True)
    (root / "gadgets.toml").write_text(
        """owned_names = ["first", "second"]
[[gadgets]]
name = "first"
options = ["ResourceLoader"]
sources = ["first.css"]
[[gadgets]]
name = "second"
options = ["ResourceLoader"]
sources = ["second.js"]
""",
        encoding="utf-8",
    )
    (root / "first.css").write_bytes(css)
    (root / "second.js").write_bytes(js)


def _pages(definition: str) -> dict[str, str]:
    return {
        "MediaWiki:Gadget-first.css": "old css\n",
        "MediaWiki:Gadget-second.js": "old js\n",
        "MediaWiki:Gadgets-definition": definition,
    }


def test_rights_failure_happens_before_any_wiki_or_sidecar_write(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake(rights=frozenset())
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    initial_pages = client.pages.copy()
    initial_revisions = client.revisions.copy()
    plan = plan_interface_pages(tmp_path, client)

    with pytest.raises(InterfacePermissionError):
        deploy_interface_pages(
            plan,
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=lambda _manifest: None,
        )
    assert client.pages == initial_pages
    assert client.revisions == initial_revisions
    assert not (tmp_path / "rollback").exists()


def test_deploy_requires_checkpoint_before_sidecar_or_wiki_writes(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    initial_pages = client.pages.copy()
    initial_revisions = client.revisions.copy()
    plan = plan_interface_pages(tmp_path, client)

    with pytest.raises(TypeError, match="checkpoint must be callable"):
        deploy_interface_pages(
            plan,
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=None,  # type: ignore[arg-type]
        )

    assert client.pages == initial_pages
    assert client.revisions == initial_revisions
    assert not (tmp_path / "rollback").exists()


def test_deploy_propagates_user_guards_and_never_marks_edits_as_bot(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake(edit_account="InterfaceAdmin", is_bot=False)
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)

    def checked_read(method: Callable[..., Any]) -> Callable[..., Any]:
        def guarded(*args: Any, **kwargs: Any) -> Any:
            assert kwargs["assertion"] == "user"
            assert kwargs["assert_user"] == "InterfaceAdmin"
            return method(*args, **kwargs)

        return guarded

    def checked_write(method: Callable[..., Any]) -> Callable[..., Any]:
        guarded_read = checked_read(method)

        def guarded(*args: Any, **kwargs: Any) -> Any:
            assert kwargs["bot"] is False
            return guarded_read(*args, **kwargs)

        return guarded

    client.get_page_snapshots = checked_read(client.get_page_snapshots)
    client.get_current_user_rights = checked_read(client.get_current_user_rights)
    client.safe_edit_page = checked_write(client.safe_edit_page)
    client.safe_create_page = checked_write(client.safe_create_page)
    plan = plan_interface_pages(
        tmp_path,
        client,
        assert_user="InterfaceAdmin",
    )

    deploy_interface_pages(
        plan,
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )

    assert all(user == "InterfaceAdmin" for user in client.page_users.values())
    assert all(revision == 2 for revision in client.revisions.values())


def test_prepares_all_sidecars_and_checkpoints_before_first_mutation(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    initial_pages = client.pages.copy()
    initial_revisions = client.revisions.copy()
    plan = plan_interface_pages(tmp_path, client)
    checkpoints: list[InterfaceDeployManifest] = []

    def checkpoint(manifest: InterfaceDeployManifest) -> None:
        checkpoints.append(manifest)
        if len(checkpoints) == 1:
            assert client.pages == initial_pages
            assert client.revisions == initial_revisions
            assert len(list((tmp_path / "rollback").iterdir())) == 3

    deploy_interface_pages(
        plan,
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=checkpoint,
    )
    assert len(checkpoints) == 4  # prepared plus definition, CSS, JS


def test_a_new_gadget_is_registered_before_the_pages_that_load_it_change(tmp_path: Path) -> None:
    _repo(tmp_path)
    pages = _pages("* unrelated[ResourceLoader]|other.js\n")
    del pages["MediaWiki:Gadget-first.css"]
    client = MediaWikiFake()
    for title, text in pages.items():
        client.put_page(title, text)

    def checkpoint(manifest: InterfaceDeployManifest) -> None:
        completed = [entry.title for entry in manifest.entries if entry.mutation_state == "applied"]
        expected_order = [
            "MediaWiki:Gadget-first.css",
            "MediaWiki:Gadgets-definition",
            "MediaWiki:Gadget-second.js",
        ]
        assert completed == expected_order[: len(completed)]
        if len(completed) == 1:
            assert client.pages["MediaWiki:Gadget-first.css"] == "body { color: red; }"
            assert client.pages["MediaWiki:Gadgets-definition"] == pages["MediaWiki:Gadgets-definition"].rstrip()
            assert client.pages["MediaWiki:Gadget-second.js"] == "old js"
        elif len(completed) == 2:
            assert "* first[ResourceLoader]|first.css" in client.pages["MediaWiki:Gadgets-definition"]
            assert client.pages["MediaWiki:Gadget-second.js"] == "old js"

    deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=checkpoint,
    )

    assert client.pages["MediaWiki:Gadget-first.css"] == "body { color: red; }"
    assert client.pages["MediaWiki:Gadget-second.js"] == "console.log('x');"
    assert client.revisions["MediaWiki:Gadgets-definition"] == 2


def test_definition_reconciliation_owns_only_managed_lines_and_removes_duplicates(tmp_path: Path) -> None:
    _repo(tmp_path)
    definition = (
        "# keep\n* unrelated[ResourceLoader]|unrelated.js\n"
        "* first[ResourceLoader]|stale.css\n* first[ResourceLoader]|duplicate.css\n"
    )
    client = MediaWikiFake()
    for title, text in _pages(definition).items():
        client.put_page(title, text)
    deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    uploaded = client.pages["MediaWiki:Gadgets-definition"]
    assert "# keep\n" in uploaded
    assert uploaded.count("* first[") == 1
    assert "* second[ResourceLoader]|second.js" in uploaded.splitlines()


def test_partial_failure_leaves_last_checkpoint_as_safe_rollback_journal(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    safe_edit_page = client.safe_edit_page

    def fail_edit(title: str, *args: Any, **kwargs: Any) -> int:
        if title == "MediaWiki:Gadget-second.js":
            raise RuntimeError(f"failure at {title}")
        return safe_edit_page(title, *args, **kwargs)

    client.safe_edit_page = fail_edit
    plan = plan_interface_pages(tmp_path, client)
    checkpoints: list[InterfaceDeployManifest] = []

    with pytest.raises(InterfaceMutationError) as error:
        deploy_interface_pages(
            plan,
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=checkpoints.append,
        )
    journal = checkpoints[-1]
    assert error.value.manifest == journal
    assert journal.rollback_root == "rollback"
    entries = {entry.title: entry for entry in journal.entries}
    assert entries["MediaWiki:Gadgets-definition"].new_revision_id is not None
    assert entries["MediaWiki:Gadget-first.css"].new_revision_id is not None
    failed = entries["MediaWiki:Gadget-second.js"]
    assert failed.mutation_state == "ambiguous"
    assert failed.deploy_action == "edited"
    assert failed.rollback_text_sha256 == hashlib.sha256(b"old js").hexdigest()
    assert failed.deployed_text_sha256 == hashlib.sha256(b"console.log('x');").hexdigest()


def test_rollback_refuses_revision_conflict_and_reverse_restores(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    result = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    client.put_page("MediaWiki:Gadget-first.css", client.pages["MediaWiki:Gadget-first.css"])
    with pytest.raises(InterfaceRevisionConflictError):
        rollback_interface_pages(result.manifest, tmp_path, client, "rollback")

    # Force restores in reverse deployment order and uses each current revision.
    safe_edit_page = client.safe_edit_page

    def restore_edit(title: str, *args: Any, **kwargs: Any) -> int:
        if title == "MediaWiki:Gadget-first.css":
            assert client.pages["MediaWiki:Gadget-second.js"] == "old js"
        elif title == "MediaWiki:Gadgets-definition":
            assert client.pages["MediaWiki:Gadget-first.css"] == "old css"
            assert client.pages["MediaWiki:Gadget-second.js"] == "old js"
        return safe_edit_page(title, *args, **kwargs)

    client.safe_edit_page = restore_edit
    restored = rollback_interface_pages(result.manifest, tmp_path, client, "rollback", force=True)
    assert restored.restored_titles == (
        "MediaWiki:Gadget-second.js",
        "MediaWiki:Gadget-first.css",
        "MediaWiki:Gadgets-definition",
    )
    assert client.pages == {
        title: text.rstrip() for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items()
    }
    assert client.revisions["MediaWiki:Gadget-first.css"] == 4
    assert client.revisions["MediaWiki:Gadget-second.js"] == 3
    assert client.revisions["MediaWiki:Gadgets-definition"] == 3


def test_created_pages_are_left_in_place_and_reported(tmp_path: Path) -> None:
    _repo(tmp_path)
    pages = {"MediaWiki:Gadgets-definition": "* unrelated[ResourceLoader]|other.js\n"}
    client = MediaWikiFake()
    for title, text in pages.items():
        client.put_page(title, text)
    result = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    rollback = rollback_interface_pages(result.manifest, tmp_path, client, "rollback")
    assert rollback.created_titles == ("MediaWiki:Gadget-first.css", "MediaWiki:Gadget-second.js")
    assert "MediaWiki:Gadget-first.css" in client.pages
    assert "MediaWiki:Gadget-second.js" in client.pages


def test_source_hash_drift_is_rejected_before_sidecars(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    initial_pages = client.pages.copy()
    initial_revisions = client.revisions.copy()
    plan = plan_interface_pages(tmp_path, client)
    source = tmp_path / "wiki" / "gadgets" / "first.css"
    source.write_bytes(b"changed\n")
    with pytest.raises(ValueError, match="Source hash mismatch"):
        deploy_interface_pages(
            plan,
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=lambda _manifest: None,
        )
    assert client.pages == initial_pages
    assert client.revisions == initial_revisions
    assert not (tmp_path / "rollback").exists()


def test_definition_text_is_rederived_before_any_mutation(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("# preserve\n* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    initial_pages = client.pages.copy()
    initial_revisions = client.revisions.copy()

    def unexpected_rights_read(*args: Any, **kwargs: Any) -> frozenset[str]:
        raise AssertionError("must reject forged text before querying rights")

    client.get_current_user_rights = unexpected_rights_read
    plan = plan_interface_pages(tmp_path, client)
    definition = replace(
        plan.entries[-1],
        new_text="* first[ResourceLoader]|first.css\n",
    )
    forged_plan = replace(plan, entries=(*plan.entries[:-1], definition))

    with pytest.raises(ValueError, match="Planned upload text changed"):
        deploy_interface_pages(
            forged_plan,
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=lambda _manifest: None,
        )

    assert client.pages == initial_pages
    assert client.revisions == initial_revisions
    assert not (tmp_path / "rollback").exists()


def test_manifest_round_trips_prepared_and_completed_entries(tmp_path: Path) -> None:
    manifest = InterfaceDeployManifest(
        (
            InterfacePageManifestEntry(
                title="MediaWiki:Gadget-a.css",
                source_path="wiki/gadgets/a.css",
                source_sha256="a" * 64,
                content_model="css",
                old_revision_id=1,
                old_revision_timestamp="2026-07-13T00:00:00Z",
                rollback_text_source="rollback/MediaWiki%3AGadget-a.css.wiki",
            ),
            InterfacePageManifestEntry(
                title="MediaWiki:Gadget-b.js",
                source_path="wiki/gadgets/b.js",
                source_sha256="b" * 64,
                content_model="javascript",
                new_revision_id=3,
                deployed_text_sha256="d" * 64,
                deploy_action="created",
                mutation_state="applied",
            ),
            InterfacePageManifestEntry(
                title="MediaWiki:Gadgets-definition",
                source_path="wiki/gadgets/gadgets.toml",
                source_sha256="c" * 64,
                content_model="wikitext",
                deploy_action="unchanged",
                mutation_state="applied",
            ),
        ),
        rollback_root="rollback",
    )
    path = tmp_path / "manifest.json"

    write_interface_deploy_manifest(manifest, path)

    assert read_interface_deploy_manifest(path) == manifest


def test_manifest_rejects_completed_creation_without_revision(tmp_path: Path) -> None:
    entry = InterfacePageManifestEntry(
        title="MediaWiki:Gadget-a.css",
        source_path="wiki/gadgets/a.css",
        source_sha256="a" * 64,
        content_model="css",
        mutation_state="applied",
        deploy_action="created",
    )

    with pytest.raises(ValueError, match="lacks its deployed revision"):
        write_interface_deploy_manifest(
            InterfaceDeployManifest((entry,)),
            tmp_path / "manifest.json",
        )


def test_manifest_rejects_unrelated_interface_page(tmp_path: Path) -> None:
    entry = InterfacePageManifestEntry(
        title="MediaWiki:Common.js",
        source_path="wiki/gadgets/common.js",
        source_sha256="a" * 64,
        content_model="javascript",
    )

    with pytest.raises(ValueError, match="not a repo-owned gadget page"):
        write_interface_deploy_manifest(
            InterfaceDeployManifest((entry,)),
            tmp_path / "manifest.json",
        )


def test_manifest_rejects_sidecar_path_traversal(tmp_path: Path) -> None:
    entry = InterfacePageManifestEntry(
        title="MediaWiki:Gadget-a.css",
        source_path="wiki/gadgets/a.css",
        source_sha256="a" * 64,
        content_model="css",
        old_revision_id=1,
        old_revision_timestamp="2026-07-13T00:00:00Z",
        new_revision_id=2,
        mutation_state="applied",
        rollback_text_source="../outside.wiki",
        deploy_action="edited",
    )
    with pytest.raises(ValueError, match="traversal"):
        write_interface_deploy_manifest(InterfaceDeployManifest((entry,)), tmp_path / "manifest.json")


def test_sidecar_names_are_percent_encoded_and_injective(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    names = {path.name for path in (tmp_path / "rollback").iterdir()}
    assert "MediaWiki%3AGadget-first.css.wiki" in names
    assert "MediaWiki%3AGadgets-definition.wiki" in names
    assert all("/" not in name for name in names)
    assert all(hashlib.sha256(path.read_bytes()).digest() for path in (tmp_path / "rollback").iterdir())


def test_revalidation_rejects_post_plan_revision_change_even_when_content_is_unchanged(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    plan = plan_interface_pages(tmp_path, client)
    client.put_page("MediaWiki:Gadget-first.css", client.pages["MediaWiki:Gadget-first.css"])
    initial_pages = client.pages.copy()
    initial_revisions = client.revisions.copy()
    checkpoints: list[InterfaceDeployManifest] = []

    with pytest.raises(InterfaceRevisionConflictError, match="changed after planning"):
        deploy_interface_pages(
            plan,
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=checkpoints.append,
        )
    assert checkpoints == []
    assert client.pages == initial_pages
    assert client.revisions == initial_revisions
    assert not (tmp_path / "rollback").exists()


def test_response_failure_after_remote_write_is_reconciled_and_checkpointed(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    safe_edit_page = client.safe_edit_page

    def lose_edit_response(title: str, *args: Any, **kwargs: Any) -> int:
        revision = safe_edit_page(title, *args, **kwargs)
        if title == "MediaWiki:Gadget-first.css":
            raise RuntimeError(f"response failure at {title}")
        return revision

    client.safe_edit_page = lose_edit_response
    plan = plan_interface_pages(tmp_path, client)
    checkpoints: list[InterfaceDeployManifest] = []

    with pytest.raises(InterfaceDeployError, match="committed but response failed"):
        deploy_interface_pages(
            plan,
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=checkpoints.append,
        )
    recovered = checkpoints[-1].entries[0]
    assert recovered.mutation_state == "applied"
    assert recovered.deploy_action == "edited"
    assert recovered.new_revision_id is not None
    assert recovered.rollback_text_sha256 is not None


def test_rollback_retry_recognizes_already_restored_content(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    result = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    first = rollback_interface_pages(result.manifest, tmp_path, client, "rollback")
    pages_after_first = client.pages.copy()
    revisions_after_first = client.revisions.copy()
    second = rollback_interface_pages(result.manifest, tmp_path, client, "rollback")
    assert second.restored_titles == first.restored_titles
    assert client.pages == pages_after_first
    assert client.revisions == revisions_after_first


def test_rollback_rejects_sidecar_filename_digest_and_symlink_attacks(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    result = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    entry = result.manifest.entries[0]
    bad = replace(entry, rollback_text_source="rollback/other.wiki")
    forged = InterfaceDeployManifest(entries=(bad, *result.manifest.entries[1:]), rollback_root="rollback")
    with pytest.raises(InterfaceDeployError, match="filename"):
        rollback_interface_pages(forged, tmp_path, client, "rollback")

    sidecar = tmp_path / entry.rollback_text_source
    sidecar.write_text("tampered", encoding="utf-8")
    with pytest.raises(InterfaceDeployError, match="digest"):
        rollback_interface_pages(result.manifest, tmp_path, client, "rollback")

    sidecar.unlink()
    sidecar.symlink_to(tmp_path / "outside")
    with pytest.raises(InterfaceDeployError, match="regular"):
        rollback_interface_pages(result.manifest, tmp_path, client, "rollback")
