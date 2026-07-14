from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

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
from erenshor.infrastructure.wiki import MediaWikiPageRevision, MediaWikiPageSnapshot


@dataclass
class _Page:
    text: str
    revision_id: int
    timestamp: str = "2026-07-13T00:00:00Z"


class FakeInterfaceClient:
    """Stateful fake: snapshots and guarded writes exercise the real protocol."""

    def __init__(self, pages: dict[str, str], *, rights: bool = True) -> None:
        self.pages = {title: _Page(text, index + 1) for index, (title, text) in enumerate(pages.items())}
        self.rights = rights
        self.snapshot_requests: list[tuple[str, ...]] = []
        self.snapshot_guards: list[tuple[str, str | None]] = []
        self.rights_guards: list[tuple[str, str | None]] = []
        self.write_guards: list[tuple[str, bool, str, str | None]] = []
        self.writes: list[tuple[str, str]] = []
        self.fail_title: str | None = None
        self.raise_after_write_title: str | None = None
        self.next_revision = 100

    def get_current_user_rights(self, assertion: str = "user", assert_user: str | None = None) -> tuple[str, ...]:
        self.rights_guards.append((assertion, assert_user))
        return ("editinterface",) if self.rights else ()

    def get_page_snapshots(
        self, titles: list[str], assertion: str = "user", assert_user: str | None = None
    ) -> dict[str, MediaWikiPageSnapshot]:
        self.snapshot_requests.append(tuple(titles))
        self.snapshot_guards.append((assertion, assert_user))
        result: dict[str, MediaWikiPageSnapshot] = {}
        for title in titles:
            page = self.pages.get(title)
            if page is None:
                result[title] = MediaWikiPageSnapshot(title, None, None, "2026-07-13T00:00:00Z")
                continue
            revision = MediaWikiPageRevision(
                title=title,
                page_id=page.revision_id,
                revision_id=page.revision_id,
                timestamp=page.timestamp,
                start_timestamp="2026-07-13T00:00:00Z",
            )
            result[title] = MediaWikiPageSnapshot(title, page.text, revision, "2026-07-13T00:00:00Z")
        return result

    def safe_edit_page(
        self,
        title: str,
        content: str,
        base_revision: MediaWikiPageRevision,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = True,
        assertion: str = "user",
        assert_user: str | None = None,
        content_model: str | None = None,
    ) -> int:
        if title == self.fail_title:
            raise RuntimeError(f"failure at {title}")
        page = self.pages[title]
        if page.revision_id != base_revision.revision_id:
            raise RuntimeError("edit conflict")
        self.next_revision += 1
        page.text = content
        page.revision_id = self.next_revision
        self.write_guards.append((title, bot, assertion, assert_user))
        self.writes.append((title, content))
        if title == self.raise_after_write_title:
            raise RuntimeError(f"response failure at {title}")
        return page.revision_id

    def safe_create_page(
        self,
        title: str,
        content: str,
        start_timestamp: str,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = True,
        assertion: str = "user",
        assert_user: str | None = None,
        content_model: str | None = None,
    ) -> int:
        if title == self.fail_title:
            raise RuntimeError(f"failure at {title}")
        if title in self.pages:
            raise RuntimeError("create conflict")
        self.next_revision += 1
        self.pages[title] = _Page(content, self.next_revision)
        self.write_guards.append((title, bot, assertion, assert_user))
        self.writes.append((title, content))
        if title == self.raise_after_write_title:
            raise RuntimeError(f"response failure at {title}")
        return self.next_revision


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
    client = FakeInterfaceClient(_pages("* unrelated[ResourceLoader]|other.js\n"), rights=False)
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
    assert client.writes == []
    assert not (tmp_path / "rollback").exists()


def test_deploy_requires_checkpoint_before_sidecar_or_wiki_writes(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = FakeInterfaceClient(_pages("* unrelated[ResourceLoader]|other.js\n"))
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

    assert client.writes == []
    assert not (tmp_path / "rollback").exists()


def test_deploy_propagates_user_guards_and_never_marks_edits_as_bot(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = FakeInterfaceClient(_pages("* unrelated[ResourceLoader]|other.js\n"))
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

    assert client.snapshot_guards == [("user", "InterfaceAdmin"), ("user", "InterfaceAdmin")]
    assert client.rights_guards == [("user", "InterfaceAdmin")]
    assert client.write_guards
    assert all(
        bot is False and assertion == "user" and assert_user == "InterfaceAdmin"
        for _title, bot, assertion, assert_user in client.write_guards
    )


def test_prepares_all_sidecars_and_checkpoints_before_first_mutation(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = FakeInterfaceClient(_pages("* unrelated[ResourceLoader]|other.js\n"))
    plan = plan_interface_pages(tmp_path, client)
    checkpoints: list[InterfaceDeployManifest] = []

    def checkpoint(manifest: InterfaceDeployManifest) -> None:
        checkpoints.append(manifest)
        if len(checkpoints) == 1:
            assert client.writes == []
            assert len(list((tmp_path / "rollback").iterdir())) == 3

    deploy_interface_pages(
        plan,
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=checkpoint,
    )
    assert len(checkpoints) == 4  # prepared plus CSS, JS, definition
    assert [title for title, _ in client.writes] == [
        "MediaWiki:Gadget-first.css",
        "MediaWiki:Gadget-second.js",
        "MediaWiki:Gadgets-definition",
    ]


def test_definition_reconciliation_owns_only_managed_lines_and_removes_duplicates(tmp_path: Path) -> None:
    _repo(tmp_path)
    definition = (
        "# keep\n* unrelated[ResourceLoader]|unrelated.js\n"
        "* first[ResourceLoader]|stale.css\n* first[ResourceLoader]|duplicate.css\n"
    )
    client = FakeInterfaceClient(_pages(definition))
    result = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    uploaded = dict(client.writes)["MediaWiki:Gadgets-definition"]
    assert "# keep\n" in uploaded
    assert uploaded.count("* first[") == 1
    assert "* second[ResourceLoader]|second.js\n" in uploaded
    assert result.manifest.entries[-1].title == "MediaWiki:Gadgets-definition"


def test_partial_failure_leaves_last_checkpoint_as_safe_rollback_journal(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = FakeInterfaceClient(_pages("* unrelated[ResourceLoader]|other.js\n"))
    client.fail_title = "MediaWiki:Gadget-second.js"
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
    assert len(checkpoints) == 3
    journal = checkpoints[-1]
    assert error.value.manifest == journal
    assert journal.rollback_root == "rollback"
    assert journal.entries[0].new_revision_id is not None
    assert journal.entries[1].mutation_state == "ambiguous"
    assert journal.entries[1].deploy_action == "edited"
    assert journal.entries[1].rollback_text_sha256 == hashlib.sha256(b"old js\n").hexdigest()
    assert journal.entries[1].deployed_text_sha256 == hashlib.sha256(b"console.log('x');").hexdigest()
    assert journal.entries[2].new_revision_id is None


def test_rollback_refuses_revision_conflict_and_reverse_restores(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = FakeInterfaceClient(_pages("* unrelated[ResourceLoader]|other.js\n"))
    result = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    client.pages["MediaWiki:Gadget-first.css"].revision_id += 1
    with pytest.raises(InterfaceRevisionConflictError):
        rollback_interface_pages(result.manifest, tmp_path, client, "rollback")

    # Force restores in reverse deployment order and uses each current revision.
    restored = rollback_interface_pages(result.manifest, tmp_path, client, "rollback", force=True)
    assert restored.restored_titles == (
        "MediaWiki:Gadgets-definition",
        "MediaWiki:Gadget-second.js",
        "MediaWiki:Gadget-first.css",
    )
    assert [title for title, _ in client.writes[-3:]] == list(restored.restored_titles)


def test_created_pages_are_left_in_place_and_reported(tmp_path: Path) -> None:
    _repo(tmp_path)
    pages = {"MediaWiki:Gadgets-definition": "* unrelated[ResourceLoader]|other.js\n"}
    client = FakeInterfaceClient(pages)
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
    client = FakeInterfaceClient(_pages("* unrelated[ResourceLoader]|other.js\n"))
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
    assert client.writes == []
    assert not (tmp_path / "rollback").exists()


def test_definition_text_is_rederived_before_any_mutation(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = FakeInterfaceClient(_pages("# preserve\n* unrelated[ResourceLoader]|other.js\n"))
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

    assert client.rights_guards == []
    assert client.writes == []
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
    client = FakeInterfaceClient(_pages("* unrelated[ResourceLoader]|other.js\n"))
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
    client = FakeInterfaceClient(_pages("* unrelated[ResourceLoader]|other.js\n"))
    plan = plan_interface_pages(tmp_path, client)
    page = client.pages["MediaWiki:Gadget-first.css"]
    page.revision_id += 100
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
    assert client.writes == []
    assert not (tmp_path / "rollback").exists()


def test_response_failure_after_remote_write_is_reconciled_and_checkpointed(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = FakeInterfaceClient(_pages("* unrelated[ResourceLoader]|other.js\n"))
    client.raise_after_write_title = "MediaWiki:Gadget-first.css"
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
    client = FakeInterfaceClient(_pages("* unrelated[ResourceLoader]|other.js\n"))
    result = deploy_interface_pages(
        plan_interface_pages(tmp_path, client),
        repo_root=tmp_path,
        client=client,
        summary="deploy",
        rollback_root=tmp_path / "rollback",
        checkpoint=lambda _manifest: None,
    )
    first = rollback_interface_pages(result.manifest, tmp_path, client, "rollback")
    writes_after_first = len(client.writes)
    second = rollback_interface_pages(result.manifest, tmp_path, client, "rollback")
    assert second.restored_titles == first.restored_titles
    assert len(client.writes) == writes_after_first


def test_rollback_rejects_sidecar_filename_digest_and_symlink_attacks(tmp_path: Path) -> None:
    _repo(tmp_path)
    client = FakeInterfaceClient(_pages("* unrelated[ResourceLoader]|other.js\n"))
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
