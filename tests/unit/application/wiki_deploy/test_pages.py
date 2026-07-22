"""Tests for deploying repo-owned wiki pages."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest, build_repo_page_manifest
from erenshor.application.wiki_deploy.pages import build_deployed_manifest, deploy_repo_pages
from erenshor.infrastructure.wiki import MediaWikiPageRevision
from erenshor.infrastructure.wiki.client import MediaWikiPageSnapshot


def write_page(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class RecordingWikiClient:
    def __init__(self, pages: dict[str, str | None]) -> None:
        self.pages = pages
        self.snapshot_requests: list[tuple[list[str], str | None, str | None]] = []
        self.safe_edits: list[tuple[str, str, MediaWikiPageRevision, str, str, str | None]] = []
        self.safe_creates: list[tuple[str, str, str, str, str, str | None]] = []

    def get_page_snapshots(
        self,
        titles: list[str],
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> dict[str, MediaWikiPageSnapshot]:
        self.snapshot_requests.append((titles, assertion, assert_user))
        snapshots: dict[str, MediaWikiPageSnapshot] = {}
        for title in titles:
            content = self.pages.get(title)
            if content is None:
                snapshots[title] = MediaWikiPageSnapshot(
                    title=title,
                    source_text=None,
                    revision=None,
                    start_timestamp="2026-06-04T12:02:00Z",
                )
            else:
                snapshots[title] = MediaWikiPageSnapshot(
                    title=title,
                    source_text=content,
                    revision=MediaWikiPageRevision(
                        title=title,
                        page_id=100,
                        revision_id=200,
                        timestamp="2026-06-04T12:00:00Z",
                        start_timestamp="2026-06-04T12:02:00Z",
                    ),
                    start_timestamp="2026-06-04T12:02:00Z",
                )
        return snapshots

    def safe_edit_page(
        self,
        title: str,
        content: str,
        base_revision: MediaWikiPageRevision,
        summary: str,
        assertion: str,
        assert_user: str | None,
    ) -> int:
        self.safe_edits.append((title, content, base_revision, summary, assertion, assert_user))
        return 201

    def safe_create_page(
        self,
        title: str,
        content: str,
        start_timestamp: str,
        summary: str,
        assertion: str,
        assert_user: str | None,
    ) -> int:
        self.safe_creates.append((title, content, start_timestamp, summary, assertion, assert_user))
        return 301


def test_deploy_repo_pages_rejects_templates_before_remote_reads(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/templates/Item.wiki", "{{Item}}\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main", include_templates=True)
    client = RecordingWikiClient({"Template:Item": "old source\n"})

    with pytest.raises(ValueError, match="Template pages require explicit deployment opt-in"):
        deploy_repo_pages(
            manifest=manifest,
            repo_root=tmp_path,
            client=client,
            summary="Deploy repo-owned wiki pages",
            assertion="bot",
        )

    assert client.snapshot_requests == []
    assert client.safe_edits == []
    assert client.safe_creates == []


def test_deploy_repo_pages_rejects_generated_data_without_opt_in(tmp_path: Path) -> None:
    write_page(tmp_path, "variants/main/wiki/lua/Erenshor/Data/Links.lua", "return {}\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main", include_generated_data=True)
    client = RecordingWikiClient({"Module:Erenshor/Data/Links": None})

    with pytest.raises(ValueError, match="Generated data pages require explicit deployment opt-in"):
        deploy_repo_pages(
            manifest=manifest,
            repo_root=tmp_path,
            client=client,
            summary="Deploy generated data",
            assertion="bot",
        )
    assert client.snapshot_requests == []


def test_deploy_repo_pages_accepts_content_opt_in(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/content/Category/Links.wiki", "__HIDDENCAT__\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main", include_content_pages=True)
    client = RecordingWikiClient({"Category:Links": None})

    result = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Deploy content page",
        assertion="bot",
        include_content_pages=True,
    )
    assert [entry.title for entry in result.entries] == ["Category:Links"]
    assert client.safe_creates[0][0] == "Category:Links"

    client = RecordingWikiClient({})

    result = deploy_repo_pages(
        manifest=RepoWikiPageManifest(entries=()),
        repo_root=tmp_path,
        client=client,
        summary="Deploy repo-owned wiki pages",
        assertion="bot",
    )

    assert result.entries == ()
    assert client.snapshot_requests == []


def test_repo_page_manifest_rejects_mediawiki_interface_titles(tmp_path: Path) -> None:
    """A content-bot manifest rejects every case and whitespace spelling of the interface namespace."""
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "return {}\n")
    normal_manifest = build_repo_page_manifest(tmp_path, variant="main")
    [normal_entry] = normal_manifest.entries

    for title in ("MediaWiki:Gadget-erenshor.css", "mediawiki:Example", "mEdIaWiKi:Example", "  MediaWiki:Example  "):
        with pytest.raises(ValueError, match="cannot contain MediaWiki interface pages"):
            RepoWikiPageManifest(entries=(replace(normal_entry, title=title),))


def test_repo_page_manifest_preserves_non_interface_mediawiki_titles(tmp_path: Path) -> None:
    """The guard only parses the namespace prefix, not later title text."""
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "return {}\n")
    normal_manifest = build_repo_page_manifest(tmp_path, variant="main")
    [normal_entry] = normal_manifest.entries

    for title in ("Module:MediaWiki:Example", "MediaWiki-inspired article", ":MediaWiki:Example"):
        manifest = RepoWikiPageManifest(entries=(replace(normal_entry, title=title),))
        assert manifest.entries[0].title == title


def test_deploy_repo_pages_skips_unchanged_pages(tmp_path: Path) -> None:
    """Exact content matches are recorded as unchanged and never edited."""
    source = "local p = {}\nreturn p\n"
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", source)
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    client = RecordingWikiClient({"Module:Erenshor/Item": source})

    result = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Deploy repo-owned wiki pages",
        assertion="bot",
        assert_user="ErenshorBot",
        known_live_titles={"Module:Erenshor/Data/Links"},
    )

    [entry] = result.entries
    assert entry.title == "Module:Erenshor/Item"
    assert entry.status == "unchanged"
    assert entry.old_revision_id is None
    assert entry.new_revision_id is None
    assert client.safe_edits == []


def test_deploy_repo_pages_treats_trailing_newline_difference_as_unchanged(tmp_path: Path) -> None:
    """A repo file whose only difference from the stored page is MediaWiki's save normalization is unchanged."""
    source = "local p = {}\nreturn p\n"
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", source)
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    # MediaWiki stores content with CRLF collapsed and trailing whitespace trimmed.
    client = RecordingWikiClient({"Module:Erenshor/Item": "local p = {}\r\nreturn p"})
    result = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Deploy repo-owned wiki pages",
        assertion="bot",
        assert_user="ErenshorBot",
        known_live_titles={"Module:Erenshor/Data/Links"},
    )
    [entry] = result.entries
    assert entry.status == "unchanged"
    assert client.safe_edits == []
    assert client.safe_creates == []


def test_deploy_repo_pages_safe_edits_changed_pages(tmp_path: Path) -> None:
    """Changed pages are uploaded through revision-guarded safe edits."""
    source = "local p = {}\nfunction p.field() return 'new' end\nreturn p\n"
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", source)
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    client = RecordingWikiClient({"Module:Erenshor/Item": "old source\n"})

    result = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Deploy repo-owned wiki pages",
        assertion="bot",
        assert_user="ErenshorBot",
        known_live_titles={"Module:Erenshor/Data/Links"},
        rollback_root=tmp_path / "rollback",
    )

    [entry] = result.entries
    assert entry.title == "Module:Erenshor/Item"
    assert entry.status == "edited"
    assert entry.old_revision_id == 200
    assert entry.old_revision_timestamp == "2026-06-04T12:00:00Z"
    assert entry.new_revision_id == 201
    assert entry.rollback_text_source == "rollback/Module%3AErenshor%2FItem.wiki"
    assert (tmp_path / entry.rollback_text_source).read_text(encoding="utf-8") == "old source\n"
    assert client.snapshot_requests == [(["Module:Erenshor/Item"], "bot", "ErenshorBot")]
    [(title, content, base_revision, summary, assertion, assert_user)] = client.safe_edits
    assert title == "Module:Erenshor/Item"
    assert content == source
    assert base_revision.revision_id == 200
    assert summary == "Deploy repo-owned wiki pages"
    assert assertion == "bot"
    assert assert_user == "ErenshorBot"


def test_deploy_repo_pages_safe_creates_missing_pages(tmp_path: Path) -> None:
    """Missing repo-owned pages are uploaded through timestamp-guarded create-only edits."""
    source = "return {}\n"
    write_page(tmp_path, "wiki/modules/Erenshor/NewModule.lua", source)
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    client = RecordingWikiClient({"Module:Erenshor/NewModule": None})

    result = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Deploy repo-owned wiki pages",
        assertion="bot",
        assert_user="ErenshorBot",
        known_live_titles={"Module:Erenshor/Data/Links"},
    )

    [entry] = result.entries
    assert entry.title == "Module:Erenshor/NewModule"
    assert entry.status == "created"
    assert entry.old_revision_id is None
    assert entry.old_revision_timestamp is None
    assert entry.new_revision_id == 301
    assert client.snapshot_requests == [(["Module:Erenshor/NewModule"], "bot", "ErenshorBot")]
    assert client.safe_edits == []
    assert client.safe_creates == [
        (
            "Module:Erenshor/NewModule",
            source,
            "2026-06-04T12:02:00Z",
            "Deploy repo-owned wiki pages",
            "bot",
            "ErenshorBot",
        )
    ]


def test_build_deployed_manifest_merges_deploy_results_into_entries(tmp_path: Path) -> None:
    """The deployed manifest records revision IDs and rollback sources from the deploy result."""
    source = "local p = {}\nfunction p.field() return 'new' end\nreturn p\n"
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", source)
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    client = RecordingWikiClient({"Module:Erenshor/Item": "old source\n"})
    result = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Deploy repo-owned wiki pages",
        assertion="bot",
        known_live_titles={"Module:Erenshor/Data/Links"},
        rollback_root=tmp_path / "rollback",
    )
    deployed = build_deployed_manifest(manifest, result)
    [base_entry] = manifest.entries
    [deployed_entry] = deployed.entries
    # Source-of-truth metadata is carried over unchanged.
    assert deployed_entry.title == base_entry.title
    assert deployed_entry.source_sha256 == base_entry.source_sha256
    # Deploy outcome is merged in.
    assert deployed_entry.old_revision_id == 200
    assert deployed_entry.old_revision_timestamp == "2026-06-04T12:00:00Z"
    assert deployed_entry.new_revision_id == 201
    assert deployed_entry.rollback_text_source == "rollback/Module%3AErenshor%2FItem.wiki"
    assert deployed_entry.deploy_action == "edited"
    # The base manifest is not mutated.
    assert base_entry.new_revision_id is None


def test_deploy_repo_pages_aborts_on_stale_source_hash_before_writes(tmp_path: Path) -> None:
    """A source hash mismatch fails before any remote mutation is attempted."""
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "return {}\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "return {stale = true}\n")
    client = RecordingWikiClient({"Module:Erenshor/Item": "old source\n"})

    try:
        deploy_repo_pages(
            manifest=manifest,
            repo_root=tmp_path,
            client=client,
            summary="Deploy repo-owned wiki pages",
            assertion="bot",
            known_live_titles={"Module:Erenshor/Data/Links"},
        )
    except ValueError as error:
        assert "Source hash mismatch" in str(error)
    else:
        raise AssertionError("stale source hash was accepted")

    assert client.safe_edits == []
    assert client.safe_creates == []


def test_deploy_repo_pages_prepares_all_sidecars_before_first_write(tmp_path: Path) -> None:
    """The prepared checkpoint observes every changed existing sidecar before edits."""
    write_page(tmp_path, "wiki/modules/Erenshor/A.lua", "return 'a'\n")
    write_page(tmp_path, "wiki/modules/Erenshor/B.lua", "return 'b'\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    client = RecordingWikiClient({"Module:Erenshor/A": "old a\n", "Module:Erenshor/B": "old b\n"})
    checkpoints: list[RepoWikiPageManifest] = []

    def checkpoint(value: RepoWikiPageManifest) -> None:
        checkpoints.append(value)
        if len(checkpoints) == 1:
            assert (tmp_path / "rollback/Module%3AErenshor%2FA.wiki").read_text(encoding="utf-8") == "old a\n"
            assert (tmp_path / "rollback/Module%3AErenshor%2FB.wiki").read_text(encoding="utf-8") == "old b\n"

    deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Deploy repo-owned wiki pages",
        assertion="bot",
        rollback_root=tmp_path / "rollback",
        checkpoint=checkpoint,
    )

    assert len(checkpoints) == 3
    assert len(client.safe_edits) == 2


def test_deploy_repo_pages_checkpoint_journals_partial_failure(tmp_path: Path) -> None:
    """A later write failure leaves the earlier successful write journaled."""
    write_page(tmp_path, "wiki/modules/Erenshor/A.lua", "return 'a'\n")
    write_page(tmp_path, "wiki/modules/Erenshor/B.lua", "return 'b'\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main")

    class FailingClient(RecordingWikiClient):
        def safe_edit_page(
            self,
            title: str,
            content: str,
            base_revision: MediaWikiPageRevision,
            summary: str,
            assertion: str,
            assert_user: str | None,
        ) -> int:
            if self.safe_edits:
                raise RuntimeError("second write failed")
            return super().safe_edit_page(title, content, base_revision, summary, assertion, assert_user)

    client = FailingClient({"Module:Erenshor/A": "old a\n", "Module:Erenshor/B": "old b\n"})
    checkpoints: list[RepoWikiPageManifest] = []

    try:
        deploy_repo_pages(
            manifest=manifest,
            repo_root=tmp_path,
            client=client,
            summary="Deploy repo-owned wiki pages",
            assertion="bot",
            rollback_root=tmp_path / "rollback",
            checkpoint=checkpoints.append,
        )
    except RuntimeError as error:
        assert str(error) == "second write failed"
    else:
        raise AssertionError("expected the second write to fail")

    assert len(checkpoints) == 2
    [prepared, after_first] = checkpoints
    assert all(entry.deploy_action is None for entry in prepared.entries)
    actions = {entry.title: entry.deploy_action for entry in after_first.entries}
    assert actions["Module:Erenshor/A"] == "edited"
    assert actions["Module:Erenshor/B"] is None


def test_safe_title_filename_is_injective_for_distinct_titles() -> None:
    """Distinct titles map to distinct rollback sidecar filenames (no lossy collision)."""
    from erenshor.application.wiki_deploy.pages import _safe_title_filename

    # These collide under a "replace non-alnum with underscore" scheme.
    first = _safe_title_filename("Template:Item/CargoDeclare")
    second = _safe_title_filename("Template:Item:CargoDeclare")

    assert first != second
    # Filenames stay flat: title separators must not become path separators.
    assert "/" not in first
    assert "/" not in second
