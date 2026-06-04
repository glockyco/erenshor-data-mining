"""Tests for deploying repo-owned wiki pages."""

from __future__ import annotations

from pathlib import Path

from erenshor.application.wiki_deploy.manifest import build_repo_page_manifest
from erenshor.application.wiki_deploy.pages import build_deployed_manifest, deploy_repo_pages
from erenshor.infrastructure.wiki import MediaWikiPageRevision


def write_page(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class RecordingWikiClient:
    def __init__(self, pages: dict[str, str | None]) -> None:
        self.pages = pages
        self.revision_requests: list[tuple[str, str, str | None]] = []
        self.timestamp_requests: list[tuple[str, str | None]] = []
        self.safe_edits: list[tuple[str, str, MediaWikiPageRevision, str, str, str | None]] = []
        self.safe_creates: list[tuple[str, str, str, str, str, str | None]] = []

    def get_pages(self, titles: list[str]) -> dict[str, str | None]:
        return {title: self.pages.get(title) for title in titles}

    def get_page_revision_metadata(
        self,
        title: str,
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> MediaWikiPageRevision | None:
        self.revision_requests.append((title, assertion or "", assert_user))
        return MediaWikiPageRevision(
            title=title,
            page_id=100,
            revision_id=200,
            timestamp="2026-06-04T12:00:00Z",
            start_timestamp="2026-06-04T12:01:00Z",
        )

    def get_edit_start_timestamp(
        self,
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> str:
        self.timestamp_requests.append((assertion or "", assert_user))
        return "2026-06-04T12:02:00Z"

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
    )

    [entry] = result.entries
    assert entry.title == "Module:Erenshor/Item"
    assert entry.status == "unchanged"
    assert entry.old_revision_id is None
    assert entry.new_revision_id is None
    assert client.revision_requests == []
    assert client.safe_edits == []


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
        rollback_root=tmp_path / "rollback",
    )

    [entry] = result.entries
    assert entry.title == "Module:Erenshor/Item"
    assert entry.status == "changed"
    assert entry.old_revision_id == 200
    assert entry.old_revision_timestamp == "2026-06-04T12:00:00Z"
    assert entry.new_revision_id == 201
    assert entry.rollback_text_source == "rollback/Module_Erenshor_Item.wiki"
    assert (tmp_path / entry.rollback_text_source).read_text(encoding="utf-8") == "old source\n"
    assert client.revision_requests == [("Module:Erenshor/Item", "bot", "ErenshorBot")]
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
    write_page(tmp_path, "variants/main/wiki/lua/Erenshor/Data/Items.lua", source)
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    client = RecordingWikiClient({"Module:Erenshor/Data/Items": None})

    result = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Deploy repo-owned wiki pages",
        assertion="bot",
        assert_user="ErenshorBot",
    )

    [entry] = result.entries
    assert entry.title == "Module:Erenshor/Data/Items"
    assert entry.status == "changed"
    assert entry.old_revision_id is None
    assert entry.old_revision_timestamp is None
    assert entry.new_revision_id == 301
    assert client.revision_requests == []
    assert client.timestamp_requests == [("bot", "ErenshorBot")]
    assert client.safe_edits == []
    assert client.safe_creates == [
        (
            "Module:Erenshor/Data/Items",
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
    assert deployed_entry.rollback_text_source == "rollback/Module_Erenshor_Item.wiki"
    # The base manifest is not mutated.
    assert base_entry.new_revision_id is None
