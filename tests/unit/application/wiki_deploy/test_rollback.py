"""Tests for manifest-backed wiki rollback."""

from __future__ import annotations

from pathlib import Path

from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest, RepoWikiPageManifestEntry
from erenshor.application.wiki_deploy.rollback import rollback_repo_pages
from erenshor.infrastructure.wiki import MediaWikiPageRevision


class RecordingRollbackClient:
    def __init__(self) -> None:
        self.revision_requests: list[tuple[str, str, str | None]] = []
        self.safe_edits: list[tuple[str, str, MediaWikiPageRevision, str, str, str | None]] = []

    def get_page_revision_metadata(
        self,
        title: str,
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> MediaWikiPageRevision | None:
        self.revision_requests.append((title, assertion or "", assert_user))
        return MediaWikiPageRevision(
            title=title,
            page_id=42,
            revision_id=500,
            timestamp="2026-06-04T13:00:00Z",
            start_timestamp="2026-06-04T13:01:00Z",
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
        return 501


def test_rollback_repo_pages_restores_manifest_rollback_text(tmp_path: Path) -> None:
    """Rollback reads stored old text and restores it through safe edits."""
    rollback_path = tmp_path / "variants/main/wiki/rollback/Template_Item.wiki"
    rollback_path.parent.mkdir(parents=True)
    rollback_path.write_text("old template source\n", encoding="utf-8")
    manifest = RepoWikiPageManifest(
        entries=(
            RepoWikiPageManifestEntry(
                title="Template:Item",
                source_path="wiki/templates/Item.wiki",
                source_sha256="0" * 64,
                ownership_class="cargo_declaration",
                upload_stage="cargo_declaration",
                content_model="wikitext",
                declares_cargo_table=True,
                cargo_tables=("Items",),
                old_revision_id=123,
                old_revision_timestamp="2026-06-04T12:00:00Z",
                new_revision_id=124,
                rollback_text_source="variants/main/wiki/rollback/Template_Item.wiki",
            ),
        )
    )
    client = RecordingRollbackClient()

    result = rollback_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Rollback repo-owned wiki deploy",
        assertion="bot",
        assert_user="ErenshorBot",
    )

    [entry] = result.entries
    assert entry.title == "Template:Item"
    assert entry.restored_revision_id == 123
    assert entry.new_revision_id == 501
    assert client.revision_requests == [("Template:Item", "bot", "ErenshorBot")]
    [(title, content, base_revision, summary, assertion, assert_user)] = client.safe_edits
    assert title == "Template:Item"
    assert content == "old template source\n"
    assert base_revision.revision_id == 500
    assert summary == "Rollback repo-owned wiki deploy"
    assert assertion == "bot"
    assert assert_user == "ErenshorBot"
