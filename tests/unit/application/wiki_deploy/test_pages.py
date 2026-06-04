"""Tests for deploying repo-owned wiki pages."""

from __future__ import annotations

from pathlib import Path

from erenshor.application.wiki_deploy.manifest import build_repo_page_manifest
from erenshor.application.wiki_deploy.pages import deploy_repo_pages
from erenshor.infrastructure.wiki import MediaWikiPageRevision


def write_page(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class RecordingWikiClient:
    def __init__(self, pages: dict[str, str | None]) -> None:
        self.pages = pages
        self.revision_requests: list[tuple[str, str, str | None]] = []
        self.safe_edits: list[tuple[str, str, MediaWikiPageRevision, str, str, str | None]] = []

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
    )

    [entry] = result.entries
    assert entry.title == "Module:Erenshor/Item"
    assert entry.status == "changed"
    assert entry.old_revision_id == 200
    assert entry.old_revision_timestamp == "2026-06-04T12:00:00Z"
    assert entry.new_revision_id == 201
    assert client.revision_requests == [("Module:Erenshor/Item", "bot", "ErenshorBot")]
    [(title, content, base_revision, summary, assertion, assert_user)] = client.safe_edits
    assert title == "Module:Erenshor/Item"
    assert content == source
    assert base_revision.revision_id == 200
    assert summary == "Deploy repo-owned wiki pages"
    assert assertion == "bot"
    assert assert_user == "ErenshorBot"
