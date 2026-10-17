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
    InterfaceEditVerificationReceipt,
    InterfacePageManifestEntry,
    read_interface_deploy_manifest,
    write_interface_deploy_manifest,
)
from erenshor.infrastructure.wiki.client import MediaWikiEditVerificationError, MediaWikiNetworkError


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

    result = deploy_interface_pages(
        plan,
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )

    assert all(user == "InterfaceAdmin" for user in client.page_users.values())
    assert client.revisions == {entry.title: entry.new_revision_id for entry in result.manifest.entries}


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
    assert len(checkpoints) == 7  # prepared plus request and completion for each write


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

    result = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=checkpoint,
    )

    assert client.pages["MediaWiki:Gadget-first.css"] == "body { color: red; }"
    assert client.pages["MediaWiki:Gadget-second.js"] == "console.log('x');"
    assert client.revisions["MediaWiki:Gadgets-definition"] == next(
        entry.new_revision_id for entry in result.manifest.entries if entry.title == "MediaWiki:Gadgets-definition"
    )


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
    checkpoints: list[InterfaceDeployManifest] = []
    with pytest.raises(InterfaceRevisionConflictError):
        rollback_interface_pages(result.manifest, tmp_path, client, "rollback", checkpoint=checkpoints.append)

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
    restored = rollback_interface_pages(
        checkpoints[-1], tmp_path, client, "rollback", force=True, checkpoint=checkpoints.append
    )
    assert restored.restored_titles == (
        "MediaWiki:Gadget-second.js",
        "MediaWiki:Gadget-first.css",
        "MediaWiki:Gadgets-definition",
    )
    assert client.pages == {
        title: text.rstrip() for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items()
    }
    assert client.revisions == {entry.title: entry.new_revision_id for entry in restored.entries}


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
    checkpoints: list[InterfaceDeployManifest] = []
    rollback = rollback_interface_pages(result.manifest, tmp_path, client, "rollback", checkpoint=checkpoints.append)
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
    recovered = next(entry for entry in checkpoints[-1].entries if entry.title == "MediaWiki:Gadget-first.css")
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
    checkpoints: list[InterfaceDeployManifest] = []
    first = rollback_interface_pages(result.manifest, tmp_path, client, "rollback", checkpoint=checkpoints.append)
    pages_after_first = client.pages.copy()
    revisions_after_first = client.revisions.copy()
    second = rollback_interface_pages(checkpoints[-1], tmp_path, client, "rollback", checkpoint=checkpoints.append)
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
    entry = result.manifest.entries[-1]
    bad = replace(entry, rollback_text_source="rollback/other.wiki")
    forged = replace(
        result.manifest, entries=tuple(bad if item.title == entry.title else item for item in result.manifest.entries)
    )
    checkpoints: list[InterfaceDeployManifest] = []
    with pytest.raises(InterfaceDeployError, match="filename"):
        rollback_interface_pages(forged, tmp_path, client, "rollback", checkpoint=checkpoints.append)

    sidecar = tmp_path / entry.rollback_text_source
    sidecar.write_text("tampered", encoding="utf-8")
    with pytest.raises(InterfaceDeployError, match="digest"):
        rollback_interface_pages(result.manifest, tmp_path, client, "rollback", checkpoint=checkpoints.append)

    sidecar.unlink()
    sidecar.symlink_to(tmp_path / "outside")
    with pytest.raises(InterfaceDeployError, match="regular"):
        rollback_interface_pages(result.manifest, tmp_path, client, "rollback", checkpoint=checkpoints.append)


@pytest.mark.parametrize("parent_available", [False, True])
@pytest.mark.parametrize("written_available", [False, True])
def test_verification_mismatch_checkpoints_receipt_before_evidence_io_and_stops_downstream(
    tmp_path: Path, parent_available: bool, written_available: bool
) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    title = "MediaWiki:Gadget-first.css"
    downstream = "MediaWiki:Gadget-second.js"
    reviewed = client.get_page_snapshots([title])[title]
    downstream_revision = client.revisions[downstream]
    safe_edit_page = client.safe_edit_page
    get_page_snapshots = client.get_page_snapshots
    manifest_path = tmp_path / "manifest.json"
    receipts: list[MediaWikiEditVerificationError] = []

    def unavailable_evidence(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("evidence service unavailable")

    def mismatched_edit(title: str, *args: Any, **kwargs: Any) -> int:
        if title != "MediaWiki:Gadget-first.css":
            return safe_edit_page(title, *args, **kwargs)
        client.put_page(title, "intervening editor text", user="Editor", content_model="javascript")
        parent = get_page_snapshots([title])[title]
        # Matching requested text and account must not erase a native ancestry mismatch.
        client.put_page(title, kwargs["content"], content_model=kwargs["content_model"])
        written = get_page_snapshots([title])[title]
        receipt = MediaWikiEditVerificationError(
            "saved revision has an intervening parent",
            new_revision_id=client.revisions[title],
            written_snapshot=written if written_available else None,
            actual_parent_snapshot=parent if parent_available else None,
        )
        receipts.append(receipt)
        client.get_page_snapshots = unavailable_evidence
        raise receipt

    client.safe_edit_page = mismatched_edit
    with pytest.raises(InterfaceMutationError, match="Verification failed") as caught:
        deploy_interface_pages(
            plan_interface_pages(tmp_path, client),
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=lambda manifest: write_interface_deploy_manifest(manifest, manifest_path),
        )
    persisted = read_interface_deploy_manifest(manifest_path)
    assert caught.value.manifest == persisted
    entry = next(item for item in persisted.entries if item.title == title)
    receipt = receipts[0]
    assert entry.mutation_state == "ambiguous"
    assert entry.new_revision_id == receipt.new_revision_id
    assert entry.edit_verification_error is not None
    assert entry.edit_verification_error.written_snapshot == receipt.written_snapshot
    assert entry.edit_verification_error.actual_parent_snapshot == receipt.actual_parent_snapshot
    assert entry.old_revision_id == reviewed.revision.revision_id
    assert (tmp_path / entry.rollback_text_source).read_text() == reviewed.source_text
    assert client.revisions[downstream] == downstream_revision
    assert next(item for item in persisted.entries if item.title == downstream).mutation_state == "pending"

    client.get_page_snapshots = get_page_snapshots
    client.safe_edit_page = safe_edit_page
    if parent_available and written_available:
        result = rollback_interface_pages(
            persisted,
            tmp_path,
            client,
            "rollback",
            checkpoint=lambda manifest: write_interface_deploy_manifest(manifest, manifest_path),
        )
        assert client.pages[title] == "intervening editor text"
        assert client.content_models[title] == "javascript"
        restored = next(item for item in result.entries if item.title == title)
        assert restored.restored_revision_id == receipt.actual_parent_snapshot.revision.revision_id
        assert (tmp_path / entry.rollback_text_source).read_text() == reviewed.source_text
    else:
        revisions = client.revisions.copy()
        for force in (False, True):
            with pytest.raises(InterfaceRevisionConflictError, match="Actual parent evidence remains unresolved"):
                rollback_interface_pages(
                    persisted,
                    tmp_path,
                    client,
                    "rollback",
                    force=force,
                    checkpoint=lambda manifest: write_interface_deploy_manifest(manifest, manifest_path),
                )
            assert client.revisions == revisions


def test_verification_checkpoint_failure_keeps_acknowledged_receipt_in_error(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    title = "MediaWiki:Gadget-first.css"
    safe_edit_page = client.safe_edit_page
    receipts: list[MediaWikiEditVerificationError] = []

    def mismatched_edit(title: str, *args: Any, **kwargs: Any) -> int:
        revision_id = safe_edit_page(title, *args, **kwargs)
        if title == "MediaWiki:Gadget-first.css":
            receipt = MediaWikiEditVerificationError("historical evidence unavailable", new_revision_id=revision_id)
            receipts.append(receipt)
            raise receipt
        return revision_id

    def checkpoint(manifest: InterfaceDeployManifest) -> None:
        if any(entry.edit_verification_error is not None for entry in manifest.entries):
            raise OSError("manifest storage unavailable")

    client.safe_edit_page = mismatched_edit
    with pytest.raises(InterfaceMutationError, match="checkpoint failed") as caught:
        deploy_interface_pages(
            plan_interface_pages(tmp_path, client),
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=checkpoint,
        )
    entry = next(item for item in caught.value.manifest.entries if item.title == title)
    assert entry.new_revision_id == receipts[0].new_revision_id
    assert entry.edit_verification_error is not None
    assert entry.edit_verification_error.new_revision_id == receipts[0].new_revision_id
    assert entry.mutation_state == "ambiguous"


@pytest.mark.parametrize("parent_available", [False, True])
def test_rollback_verification_mismatch_is_checkpointed_not_adopted_or_retried(
    tmp_path: Path, parent_available: bool
) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    manifest_path = tmp_path / "manifest.json"

    def checkpoint(manifest: InterfaceDeployManifest) -> None:
        write_interface_deploy_manifest(manifest, manifest_path)

    result = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=checkpoint,
    )
    title = "MediaWiki:Gadget-second.js"
    downstream = "MediaWiki:Gadget-first.css"
    downstream_revision = client.revisions[downstream]
    safe_edit_page = client.safe_edit_page
    get_page_snapshots = client.get_page_snapshots
    receipts: list[MediaWikiEditVerificationError] = []

    def unavailable_evidence(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("evidence service unavailable")

    def mismatched_rollback(title: str, *args: Any, **kwargs: Any) -> int:
        if title != "MediaWiki:Gadget-second.js":
            return safe_edit_page(title, *args, **kwargs)
        client.put_page(title, "intervening editor during rollback", user="Editor", content_model="wikitext")
        parent = get_page_snapshots([title])[title]
        client.put_page(title, kwargs["content"], content_model=kwargs["content_model"])
        written = get_page_snapshots([title])[title]
        receipt = MediaWikiEditVerificationError(
            "rollback has an intervening parent",
            new_revision_id=client.revisions[title],
            written_snapshot=written,
            actual_parent_snapshot=parent if parent_available else None,
        )
        receipts.append(receipt)
        client.get_page_snapshots = unavailable_evidence
        raise receipt

    client.safe_edit_page = mismatched_rollback
    with pytest.raises(InterfaceMutationError, match="Rollback verification failed") as caught:
        rollback_interface_pages(result.manifest, tmp_path, client, "rollback", checkpoint=checkpoint)
    persisted = read_interface_deploy_manifest(manifest_path)
    assert caught.value.manifest == persisted
    original = next(item for item in result.manifest.entries if item.title == title)
    entry = next(item for item in persisted.entries if item.title == title)
    assert (
        replace(
            entry,
            rollback_verification_error=None,
            rollback_request_base=None,
            rollback_account=None,
            rollback_api_url=None,
            rollback_request_state=None,
            rollback_new_revision_id=None,
        )
        == original
    )
    receipt = receipts[0]
    assert entry.rollback_verification_error is not None
    assert entry.rollback_verification_error.new_revision_id == receipt.new_revision_id
    assert entry.rollback_verification_error.written_snapshot == receipt.written_snapshot
    assert entry.rollback_verification_error.actual_parent_snapshot == receipt.actual_parent_snapshot
    assert client.revisions[downstream] == downstream_revision
    revisions = client.revisions.copy()
    for force in (False, True):
        with pytest.raises(InterfaceMutationError, match="Rollback verification remains unresolved"):
            rollback_interface_pages(persisted, tmp_path, client, "rollback", force=force, checkpoint=checkpoint)
        assert client.revisions == revisions


def test_checkpoint_failure_after_verified_edit_preserves_known_ack_when_evidence_read_fails(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    receipts: list[int] = []
    safe_edit_page = client.safe_edit_page

    def unavailable_evidence(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("evidence service unavailable")

    def record_edit(title: str, *args: Any, **kwargs: Any) -> int:
        revision_id = safe_edit_page(title, *args, **kwargs)
        receipts.append(revision_id)
        client.get_page_snapshots = unavailable_evidence
        return revision_id

    def checkpoint(manifest: InterfaceDeployManifest) -> None:
        if any(entry.new_revision_id is not None for entry in manifest.entries):
            raise OSError("manifest storage unavailable")

    client.safe_edit_page = record_edit
    with pytest.raises(InterfaceMutationError, match="checkpoint failed") as caught:
        deploy_interface_pages(
            plan_interface_pages(tmp_path, client),
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=checkpoint,
        )
    assert caught.value.manifest.entries[0].new_revision_id == receipts[0]


@pytest.mark.parametrize("missing", ["parent_revision", "parent_model", "parent_text", "lineage", "written_id"])
@pytest.mark.parametrize("force", [False, True])
def test_incomplete_actual_parent_proof_blocks_restoration(tmp_path: Path, missing: str, force: bool) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    title = "MediaWiki:Gadget-second.js"
    parent = client.get_page_snapshots([title])[title]
    checkpoints: list[InterfaceDeployManifest] = []
    deployed = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=checkpoints.append,
    )
    written = client.get_page_snapshots([title])[title]
    assert parent.revision is not None and written.revision is not None
    if missing == "parent_revision":
        parent = replace(parent, revision=None)
    elif missing == "parent_model":
        parent = replace(parent, content_model=None)
    elif missing == "parent_text":
        parent = replace(parent, source_text=None)
    elif missing == "lineage":
        written = replace(written, revision=replace(written.revision, parent_revision_id=None))
    else:
        written = replace(written, revision=replace(written.revision, revision_id=parent.revision.revision_id))
    entries = tuple(
        replace(
            entry,
            mutation_state="ambiguous",
            edit_verification_error=InterfaceEditVerificationReceipt(
                new_revision_id=entry.new_revision_id,
                written_snapshot=written,
                actual_parent_snapshot=parent,
            ),
        )
        if entry.title == title
        else entry
        for entry in deployed.manifest.entries
    )
    unresolved = replace(deployed.manifest, entries=entries)
    revisions = client.revisions.copy()
    with pytest.raises(InterfaceRevisionConflictError, match="Actual parent evidence remains unresolved"):
        rollback_interface_pages(unresolved, tmp_path, client, "rollback", force=force, checkpoint=checkpoints.append)
    assert client.revisions == revisions


@pytest.mark.parametrize("force", [False, True])
def test_native_preflight_rejection_never_adopts_another_admins_matching_revision(tmp_path: Path, force: bool) -> None:
    _repo(tmp_path)
    client = MediaWikiFake(edit_account="InterfaceAdmin")
    definition = "* first[ResourceLoader]|first.css\n* second[ResourceLoader]|second.js\n"
    for title, text in _pages(definition).items():
        client.put_page(title, text)
    plan = plan_interface_pages(tmp_path, client)
    target = "MediaWiki:Gadget-first.css"
    planned = next(entry for entry in plan.entries if entry.title == target)
    safe_edit = client.safe_edit_page
    own_writes: list[int] = []
    checkpoints: list[InterfaceDeployManifest] = []

    def checkpoint(manifest: InterfaceDeployManifest) -> None:
        checkpoints.append(manifest)
        if len(checkpoints) == 1:
            client.put_page(target, planned.new_text, user="AnotherAdmin", content_model="css")

    def guarded_edit(*args: Any, **kwargs: Any) -> int:
        revision = safe_edit(*args, **kwargs)
        own_writes.append(revision)
        return revision

    client.safe_edit_page = guarded_edit
    with pytest.raises(InterfaceDeployError, match="Native mutation rejected"):
        deploy_interface_pages(
            plan,
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=checkpoint,
        )
    rejected = next(entry for entry in checkpoints[-1].entries if entry.title == target)
    assert rejected.new_revision_id is None
    assert rejected.deploy_action is None
    assert rejected.mutation_state == "pending"
    assert rejected.deploy_request_state == "rejected"
    external_revision = client.revisions[target]
    rollback_interface_pages(checkpoints[-1], tmp_path, client, "rollback", force=force, checkpoint=checkpoints.append)
    assert own_writes == []
    assert client.revisions[target] == external_revision
    assert client.page_users[target] == "AnotherAdmin"


@pytest.mark.parametrize(
    "defect",
    [
        "other_author",
        "missing_author",
        "wrong_parent",
        "missing_parent",
        "wrong_page",
        "wrong_title",
        "missing_model",
        "wrong_wiki",
    ],
)
@pytest.mark.parametrize("force", [False, True])
def test_unknown_deploy_outcome_requires_complete_native_attribution(tmp_path: Path, defect: str, force: bool) -> None:
    _repo(tmp_path)
    client = MediaWikiFake(edit_account="InterfaceAdmin")
    for title, text in _pages("* first[ResourceLoader]|first.css\n* second[ResourceLoader]|second.js\n").items():
        client.put_page(title, text)
    target = "MediaWiki:Gadget-first.css"
    plan = plan_interface_pages(tmp_path, client)
    get_snapshots = client.get_page_snapshots
    safe_edit = client.safe_edit_page

    def unknown_edit(title: str, *args: Any, **kwargs: Any) -> int:
        if title != target:
            return safe_edit(title, *args, **kwargs)
        client.put_page(title, kwargs["content"], user="InterfaceAdmin", content_model="css")
        snapshot = get_snapshots([title])[title]
        assert snapshot.revision is not None
        revision = snapshot.revision
        if defect == "other_author":
            revision = replace(revision, user="AnotherAdmin")
        elif defect == "missing_author":
            revision = replace(revision, user=None)
        elif defect == "wrong_parent":
            revision = replace(revision, parent_revision_id=99999)
        elif defect == "missing_parent":
            revision = replace(revision, parent_revision_id=None)
        elif defect == "wrong_page":
            revision = replace(revision, page_id=99999)
        elif defect == "wrong_title":
            revision = replace(revision, title="MediaWiki:Gadget-other.css")
        elif defect == "wrong_wiki":
            client.api_url = "https://other-wiki.invalid/api.php"
        snapshot = replace(snapshot, revision=revision, content_model=None if defect == "missing_model" else "css")

        def evidence(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {title: snapshot}

        client.get_page_snapshots = evidence
        raise RuntimeError("write outcome unavailable")

    client.safe_edit_page = unknown_edit
    checkpoints: list[InterfaceDeployManifest] = []
    with pytest.raises(InterfaceMutationError, match="ambiguous"):
        deploy_interface_pages(
            plan,
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=checkpoints.append,
        )
    entry = next(entry for entry in checkpoints[-1].entries if entry.title == target)
    assert entry.mutation_state == "ambiguous"
    assert entry.new_revision_id is None
    revisions = client.revisions.copy()
    with pytest.raises(InterfaceRevisionConflictError, match=r"no attributable revision|wiki identity"):
        rollback_interface_pages(
            checkpoints[-1], tmp_path, client, "rollback", force=force, checkpoint=checkpoints.append
        )
    assert client.revisions == revisions


@pytest.mark.parametrize("defect", ["other_author", "missing_author", "wrong_parent", "missing_parent", "wrong_wiki"])
@pytest.mark.parametrize("force", [False, True])
def test_rollback_unknown_outcome_cannot_adopt_unproven_restored_text(tmp_path: Path, force: bool, defect: str) -> None:
    _repo(tmp_path)
    client = MediaWikiFake(edit_account="InterfaceAdmin")
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
    target = "MediaWiki:Gadget-second.js"
    checkpoints: list[InterfaceDeployManifest] = []
    get_snapshots = client.get_page_snapshots

    def unknown_rollback(title: str, *args: Any, **kwargs: Any) -> int:
        assert title == target
        durable = next(entry for entry in checkpoints[-1].entries if entry.title == title)
        assert durable.rollback_request_base is not None
        assert durable.rollback_request_base.revision is not None
        assert durable.rollback_request_base.revision.revision_id == kwargs["base_revision"].revision_id
        assert durable.rollback_account == "InterfaceAdmin"
        assert durable.rollback_api_url == client.api_url
        user = "AnotherAdmin" if defect == "other_author" else "InterfaceAdmin"
        client.put_page(title, kwargs["content"], user=user, content_model=kwargs["content_model"])
        snapshot = get_snapshots([title])[title]
        assert snapshot.revision is not None
        revision = snapshot.revision
        if defect == "missing_author":
            revision = replace(revision, user=None)
        elif defect == "wrong_parent":
            revision = replace(revision, parent_revision_id=99999)
        elif defect == "missing_parent":
            revision = replace(revision, parent_revision_id=None)
        elif defect == "wrong_wiki":
            client.api_url = "https://other-wiki.invalid/api.php"

        def evidence(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {title: replace(snapshot, revision=revision)}

        client.get_page_snapshots = evidence
        raise RuntimeError("write outcome unavailable")

    client.safe_edit_page = unknown_rollback
    with pytest.raises(InterfaceMutationError, match="Rollback outcome is ambiguous") as caught:
        rollback_interface_pages(result.manifest, tmp_path, client, "rollback", checkpoint=checkpoints.append)
    assert caught.value.manifest == checkpoints[-1]
    entry = next(entry for entry in checkpoints[-1].entries if entry.title == target)
    assert entry.rollback_new_revision_id is None
    revisions = client.revisions.copy()
    with pytest.raises(InterfaceRevisionConflictError, match=r"no attributable rollback receipt|wiki identity"):
        rollback_interface_pages(
            checkpoints[-1], tmp_path, client, "rollback", force=force, checkpoint=checkpoints.append
        )
    assert client.revisions == revisions
    assert client.page_users[target] == ("AnotherAdmin" if defect == "other_author" else "InterfaceAdmin")


def test_rollback_checkpoint_failure_preserves_ack_without_further_reads(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    deployed = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    safe_edit = client.safe_edit_page
    acknowledgements: list[int] = []

    def unavailable(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("evidence unavailable")

    def edit(*args: Any, **kwargs: Any) -> int:
        revision = safe_edit(*args, **kwargs)
        acknowledgements.append(revision)
        client.get_page_snapshots = unavailable
        return revision

    def checkpoint(manifest: InterfaceDeployManifest) -> None:
        if any(entry.rollback_new_revision_id is not None for entry in manifest.entries):
            raise OSError("checkpoint unavailable")

    client.safe_edit_page = edit
    with pytest.raises(InterfaceMutationError, match="committed but checkpoint failed") as caught:
        rollback_interface_pages(deployed.manifest, tmp_path, client, "rollback", checkpoint=checkpoint)
    entry = next(entry for entry in caught.value.manifest.entries if entry.title == "MediaWiki:Gadget-second.js")
    assert entry.rollback_new_revision_id == acknowledgements[0]
    assert entry.rollback_request_base is not None


def test_generic_reconciliation_cannot_replace_a_known_ack_with_a_matching_sibling_revision(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* first[ResourceLoader]|first.css\n* second[ResourceLoader]|second.js\n").items():
        client.put_page(title, text)
    target = "MediaWiki:Gadget-first.css"
    safe_edit = client.safe_edit_page
    get_snapshots = client.get_page_snapshots
    acknowledgements: list[int] = []
    checkpoints: list[InterfaceDeployManifest] = []

    def edit(title: str, *args: Any, **kwargs: Any) -> int:
        revision_id = safe_edit(title, *args, **kwargs)
        acknowledgements.append(revision_id)
        snapshot = get_snapshots([title])[title]
        assert snapshot.revision is not None
        sibling = replace(snapshot, revision=replace(snapshot.revision, revision_id=revision_id + 1000))

        def evidence(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {title: sibling}

        client.get_page_snapshots = evidence
        return revision_id

    def checkpoint(manifest: InterfaceDeployManifest) -> None:
        entry = next(entry for entry in manifest.entries if entry.title == target)
        if entry.mutation_state == "applied":
            raise OSError("checkpoint unavailable")
        checkpoints.append(manifest)

    client.safe_edit_page = edit
    with pytest.raises(InterfaceMutationError, match="ambiguous") as caught:
        deploy_interface_pages(
            plan_interface_pages(tmp_path, client),
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=checkpoint,
        )
    entry = next(entry for entry in caught.value.manifest.entries if entry.title == target)
    assert entry.new_revision_id == acknowledgements[0]
    assert entry.mutation_state == "ambiguous"
    assert checkpoints[-1] == caught.value.manifest


def test_forced_rollback_unknown_outcome_uses_its_actual_checkpointed_request_parent(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = MediaWikiFake()
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    deployed = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    target = "MediaWiki:Gadget-second.js"
    client.put_page(target, "a later reviewed edit", user="AnotherAdmin")
    request_base = client.revisions[target]
    safe_edit = client.safe_edit_page
    checkpoints: list[InterfaceDeployManifest] = []

    def edit(title: str, *args: Any, **kwargs: Any) -> int:
        if title == target:
            durable = next(entry for entry in checkpoints[-1].entries if entry.title == title)
            assert durable.rollback_request_base is not None
            assert durable.rollback_request_base.revision is not None
            assert durable.rollback_request_base.revision.revision_id == request_base
            safe_edit(title, *args, **kwargs)
            raise RuntimeError("response lost")
        return safe_edit(title, *args, **kwargs)

    client.safe_edit_page = edit
    result = rollback_interface_pages(
        deployed.manifest, tmp_path, client, "rollback", force=True, checkpoint=checkpoints.append
    )
    entry = next(entry for entry in checkpoints[-1].entries if entry.title == target)
    assert entry.rollback_new_revision_id == client.revisions[target]
    assert client.page_parents[target] == request_base
    assert result.restored_titles[0] == target


@pytest.mark.parametrize("author", ["AnotherAdmin", "InterfaceAdmin"])
@pytest.mark.parametrize("force", [False, True])
def test_matching_preimage_without_a_recorded_rollback_request_is_not_an_own_restore(
    tmp_path: Path, author: str, force: bool
) -> None:
    _repo(tmp_path)
    client = MediaWikiFake(edit_account="InterfaceAdmin")
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    deployed = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    client.put_page("MediaWiki:Gadget-second.js", "old js\n", user=author)
    revisions = client.revisions.copy()
    with pytest.raises(InterfaceRevisionConflictError, match="no attributable rollback receipt"):
        rollback_interface_pages(
            deployed.manifest, tmp_path, client, "rollback", force=force, checkpoint=lambda _manifest: None
        )
    assert client.revisions == revisions


@pytest.mark.parametrize("created", [False, True])
def test_rollback_recovers_the_durable_pre_ack_crash_window_before_restoring_any_page(
    tmp_path: Path, created: bool
) -> None:
    _repo(tmp_path)
    client = MediaWikiFake(edit_account="InterfaceAdmin")
    target = "MediaWiki:Gadget-first.css"
    pages = _pages("* first[ResourceLoader]|first.css\n* second[ResourceLoader]|second.js\n")
    if created:
        del pages[target]
    for title, text in pages.items():
        client.put_page(title, text)
    manifest_path = tmp_path / "manifest.json"

    def crash_checkpoint(manifest: InterfaceDeployManifest) -> None:
        target_entry = next(entry for entry in manifest.entries if entry.title == target)
        if target_entry.new_revision_id is not None:
            raise OSError("process lost its completion checkpoint")
        write_interface_deploy_manifest(manifest, manifest_path)

    with pytest.raises(InterfaceMutationError, match="checkpoint failed"):
        deploy_interface_pages(
            plan_interface_pages(tmp_path, client),
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=crash_checkpoint,
        )
    persisted = read_interface_deploy_manifest(manifest_path)
    target_entry = next(entry for entry in persisted.entries if entry.title == target)
    assert target_entry.deploy_action is None
    assert target_entry.new_revision_id is None
    assert target_entry.deploy_request_state == "pending"
    assert target_entry.mutation_state == "pending"
    written_revision = client.revisions[target]
    revisions = client.revisions.copy()
    checkpoints: list[InterfaceDeployManifest] = []

    def recovery_checkpoint(manifest: InterfaceDeployManifest) -> None:
        if not checkpoints:
            assert client.revisions == revisions
            recovered = next(entry for entry in manifest.entries if entry.title == target)
            assert recovered.new_revision_id == written_revision
            assert recovered.mutation_state == "applied"
        checkpoints.append(manifest)
        write_interface_deploy_manifest(manifest, manifest_path)

    result = rollback_interface_pages(persisted, tmp_path, client, "rollback", checkpoint=recovery_checkpoint)
    assert checkpoints
    if created:
        assert result.created_titles == (target,)
        assert client.revisions[target] == written_revision
    else:
        assert result.restored_titles == (target,)
        assert client.pages[target] == "old css"
    assert client.pages["MediaWiki:Gadget-second.js"] == "old js"


@pytest.mark.parametrize("outcome", ["external", "unchanged", "missing", "missing_author", "missing_parent"])
@pytest.mark.parametrize("force", [False, True])
def test_unresolved_pending_crash_window_blocks_all_earlier_restores(tmp_path: Path, outcome: str, force: bool) -> None:
    _repo(tmp_path)
    client = MediaWikiFake(edit_account="InterfaceAdmin")
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    target = "MediaWiki:Gadget-first.css"
    manifest_path = tmp_path / "manifest.json"
    plan = plan_interface_pages(tmp_path, client)
    target_plan = next(entry for entry in plan.entries if entry.title == target)

    def stop_before_request(manifest: InterfaceDeployManifest) -> None:
        write_interface_deploy_manifest(manifest, manifest_path)
        entry = next(entry for entry in manifest.entries if entry.title == target)
        if entry.deploy_request_state == "pending":
            raise OSError("process exits before receiving any request outcome")

    with pytest.raises(OSError, match="process exits"):
        deploy_interface_pages(
            plan,
            repo_root=tmp_path,
            client=client,
            summary="deploy",
            rollback_root=tmp_path / "rollback",
            checkpoint=stop_before_request,
        )
    manifest = read_interface_deploy_manifest(manifest_path)
    get_snapshots = client.get_page_snapshots
    if outcome not in ("unchanged", "missing"):
        client.put_page(
            target,
            target_plan.new_text,
            user="AnotherAdmin" if outcome == "external" else "InterfaceAdmin",
            content_model="css",
        )
    evidence = get_snapshots([target])[target]
    if outcome == "missing":
        evidence = replace(evidence, revision=None, source_text=None)
    elif outcome in ("missing_author", "missing_parent"):
        assert evidence.revision is not None
        revision = replace(
            evidence.revision,
            user=None if outcome == "missing_author" else "InterfaceAdmin",
            parent_revision_id=None if outcome == "missing_parent" else evidence.revision.parent_revision_id,
        )
        evidence = replace(evidence, revision=revision)

    def pending_evidence(titles: Any, **kwargs: Any) -> dict[str, Any]:
        snapshots = dict(get_snapshots(titles, **kwargs))
        if target in titles:
            snapshots[target] = evidence
        return snapshots

    client.get_page_snapshots = pending_evidence
    pages_before = client.pages.copy()
    revisions_before = client.revisions.copy()
    checkpoints: list[InterfaceDeployManifest] = []
    with pytest.raises(InterfaceRevisionConflictError, match="Pending deploy has no attributable revision"):
        rollback_interface_pages(manifest, tmp_path, client, "rollback", force=force, checkpoint=checkpoints.append)
    assert client.pages == pages_before
    assert client.revisions == revisions_before
    assert checkpoints == []


@pytest.mark.parametrize("author", ["AnotherAdmin", "InterfaceAdmin"])
@pytest.mark.parametrize("force", [False, True])
def test_explicit_rollback_preflight_rejection_is_not_adopted_on_a_later_retry(
    tmp_path: Path, author: str, force: bool
) -> None:
    _repo(tmp_path)
    client = MediaWikiFake(edit_account="InterfaceAdmin")
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    deployed = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    target = "MediaWiki:Gadget-second.js"
    safe_edit = client.safe_edit_page
    checkpoints: list[InterfaceDeployManifest] = []

    def reject_rollback(title: str, *args: Any, **kwargs: Any) -> int:
        assert title == target
        client.put_page(title, kwargs["content"], user=author, content_model=kwargs["content_model"])
        return safe_edit(title, *args, **kwargs)

    client.safe_edit_page = reject_rollback
    with pytest.raises(InterfaceRevisionConflictError, match="Native rollback rejected"):
        rollback_interface_pages(deployed.manifest, tmp_path, client, "rollback", checkpoint=checkpoints.append)
    rejected = next(entry for entry in checkpoints[-1].entries if entry.title == target)
    assert rejected.rollback_request_state == "rejected"
    assert rejected.rollback_new_revision_id is None
    revisions = client.revisions.copy()
    with pytest.raises(InterfaceRevisionConflictError, match="no attributable rollback receipt"):
        rollback_interface_pages(
            checkpoints[-1], tmp_path, client, "rollback", force=force, checkpoint=checkpoints.append
        )
    assert client.revisions == revisions


@pytest.mark.parametrize("legacy_state", [False, True])
@pytest.mark.parametrize("force", [False, True])
def test_pending_rollback_timeout_is_not_replayed_and_late_commit_is_attributed(
    tmp_path: Path, legacy_state: bool, force: bool
) -> None:
    _repo(tmp_path)
    client = MediaWikiFake(edit_account="InterfaceAdmin")
    for title, text in _pages("* unrelated[ResourceLoader]|other.js\n").items():
        client.put_page(title, text)
    deployed = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    target = "MediaWiki:Gadget-second.js"
    original_edit = client.safe_edit_page
    requests: list[str] = []
    manifest_path = tmp_path / "manifest.json"

    def checkpoint(manifest: InterfaceDeployManifest) -> None:
        write_interface_deploy_manifest(manifest, manifest_path)

    def timeout(title: str, *args: Any, **kwargs: Any) -> int:
        requests.append(title)
        raise MediaWikiNetworkError("request timed out without an acknowledgement")

    client.safe_edit_page = timeout
    with pytest.raises(InterfaceMutationError, match="Rollback outcome is ambiguous"):
        rollback_interface_pages(deployed.manifest, tmp_path, client, "rollback", checkpoint=checkpoint)
    pending = read_interface_deploy_manifest(manifest_path)
    pending_entry = next(entry for entry in pending.entries if entry.title == target)
    assert pending_entry.rollback_request_base is not None
    assert pending_entry.rollback_request_state == "pending"
    assert pending_entry.rollback_new_revision_id is None
    if legacy_state:
        pending = replace(
            pending,
            entries=tuple(
                replace(entry, rollback_request_state=None) if entry.title == target else entry
                for entry in pending.entries
            ),
        )
        write_interface_deploy_manifest(pending, manifest_path)
    revisions_before = client.revisions.copy()
    bytes_before = manifest_path.read_bytes()
    with pytest.raises(InterfaceRevisionConflictError, match="Pending rollback has no attributable rollback receipt"):
        rollback_interface_pages(pending, tmp_path, client, "rollback", force=force, checkpoint=checkpoint)
    assert requests == [target]
    assert client.revisions == revisions_before
    assert manifest_path.read_bytes() == bytes_before
    assert client.pages["MediaWiki:Gadget-first.css"] == "body { color: red; }"
    assert "* first[ResourceLoader]|first.css" in client.pages["MediaWiki:Gadgets-definition"]

    # The outstanding request completes later with the exact recorded parent.
    client.put_page(target, "old js", user="InterfaceAdmin", content_model="javascript")
    late_revision = client.revisions[target]

    def checked_edit(title: str, *args: Any, **kwargs: Any) -> int:
        requests.append(title)
        assert title != target
        persisted_entry = next(
            entry for entry in read_interface_deploy_manifest(manifest_path).entries if entry.title == target
        )
        assert persisted_entry.rollback_new_revision_id == late_revision
        return original_edit(title, *args, **kwargs)

    client.safe_edit_page = checked_edit
    restored = rollback_interface_pages(
        read_interface_deploy_manifest(manifest_path), tmp_path, client, "rollback", force=force, checkpoint=checkpoint
    )
    assert restored.restored_titles == (
        target,
        "MediaWiki:Gadget-first.css",
        "MediaWiki:Gadgets-definition",
    )
    assert requests.count(target) == 1
    assert client.revisions[target] == late_revision
    assert client.pages["MediaWiki:Gadget-first.css"] == "old css"
