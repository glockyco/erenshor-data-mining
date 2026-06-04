"""Tests for manifest-backed wiki rollback."""

from __future__ import annotations

from pathlib import Path

import pytest

from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest, RepoWikiPageManifestEntry
from erenshor.application.wiki_deploy.rollback import rollback_repo_pages
from erenshor.infrastructure.wiki import MediaWikiPageRevision


class RecordingRollbackClient:
    def __init__(self, current_revision_id: int = 500) -> None:
        self.current_revision_id = current_revision_id
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
            revision_id=self.current_revision_id,
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
        return self.current_revision_id + 1


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
                new_revision_id=500,
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


def _edited_manifest() -> RepoWikiPageManifest:
    return RepoWikiPageManifest(
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
                new_revision_id=500,
                rollback_text_source="variants/main/wiki/rollback/Template_Item.wiki",
            ),
        )
    )


def _write_rollback_text(tmp_path: Path) -> None:
    rollback_path = tmp_path / "variants/main/wiki/rollback/Template_Item.wiki"
    rollback_path.parent.mkdir(parents=True)
    rollback_path.write_text("old template source\n", encoding="utf-8")


def test_rollback_refuses_when_page_changed_since_deploy(tmp_path: Path) -> None:
    """A page edited after deploy is not silently overwritten by rollback."""
    _write_rollback_text(tmp_path)
    client = RecordingRollbackClient(current_revision_id=777)

    with pytest.raises(ValueError, match="changed since deploy"):
        rollback_repo_pages(
            manifest=_edited_manifest(),
            repo_root=tmp_path,
            client=client,
            summary="Rollback repo-owned wiki deploy",
            assertion="bot",
            assert_user="ErenshorBot",
        )

    assert client.safe_edits == []


def test_rollback_force_overrides_post_deploy_change(tmp_path: Path) -> None:
    """An explicit force restores even when the page changed after deploy."""
    _write_rollback_text(tmp_path)
    client = RecordingRollbackClient(current_revision_id=777)

    result = rollback_repo_pages(
        manifest=_edited_manifest(),
        repo_root=tmp_path,
        client=client,
        summary="Rollback repo-owned wiki deploy",
        assertion="bot",
        assert_user="ErenshorBot",
        force=True,
    )

    [entry] = result.entries
    assert entry.new_revision_id == 778
    assert len(client.safe_edits) == 1


def test_rollback_reports_created_pages_for_manual_deletion(tmp_path: Path) -> None:
    """Pages the deploy created cannot be restored by editing, so they are reported, not skipped."""
    _write_rollback_text(tmp_path)
    manifest = RepoWikiPageManifest(
        entries=(
            RepoWikiPageManifestEntry(
                title="Module:Erenshor/Data/Items",
                source_path="variants/main/wiki/lua/Erenshor/Data/Items.lua",
                source_sha256="0" * 64,
                ownership_class="generated_data",
                upload_stage="generated_data",
                content_model="Scribunto",
                declares_cargo_table=False,
                cargo_tables=(),
                old_revision_id=None,
                old_revision_timestamp=None,
                new_revision_id=301,
                deploy_action="created",
            ),
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
                new_revision_id=500,
                rollback_text_source="variants/main/wiki/rollback/Template_Item.wiki",
                deploy_action="edited",
            ),
        )
    )
    client = RecordingRollbackClient(current_revision_id=500)

    result = rollback_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Rollback repo-owned wiki deploy",
        assertion="bot",
        assert_user="ErenshorBot",
    )

    assert [entry.title for entry in result.entries] == ["Template:Item"]
    assert result.created_titles == ("Module:Erenshor/Data/Items",)
    # The created page is never edited back to anything.
    assert [edit[0] for edit in client.safe_edits] == ["Template:Item"]
