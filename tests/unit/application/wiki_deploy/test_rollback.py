"""Tests for manifest-backed wiki rollback."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from tests.fakes.mediawiki import MediaWikiFake

from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest, RepoWikiPageManifestEntry
from erenshor.application.wiki_deploy.rollback import rollback_repo_pages


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
                ownership_class="template",
                upload_stage="template",
                content_model="wikitext",
                old_revision_id=1,
                old_revision_timestamp="2026-06-04T12:00:00Z",
                new_revision_id=2,
                rollback_text_source="variants/main/wiki/rollback/Template_Item.wiki",
            ),
        )
    )
    client = MediaWikiFake()
    client.put_page("Template:Item", "old template source")
    client.put_page("Template:Item", "deployed template source")

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
    assert entry.restored_revision_id == 1
    assert entry.new_revision_id == 3
    assert client.pages == {"Template:Item": "old template source"}
    assert client.revisions == {"Template:Item": entry.new_revision_id}
    assert client.page_users == {"Template:Item": "ErenshorBot"}


def _edited_manifest() -> RepoWikiPageManifest:
    return RepoWikiPageManifest(
        entries=(
            RepoWikiPageManifestEntry(
                title="Template:Item",
                source_path="wiki/templates/Item.wiki",
                source_sha256="0" * 64,
                ownership_class="template",
                upload_stage="template",
                content_model="wikitext",
                old_revision_id=1,
                old_revision_timestamp="2026-06-04T12:00:00Z",
                new_revision_id=2,
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
    client = MediaWikiFake()
    client.put_page("Template:Item", "old template source")
    client.put_page("Template:Item", "deployed template source")
    client.put_page("Template:Item", "post-deploy human edit", user="HumanEditor")

    with pytest.raises(ValueError, match="changed since deploy"):
        rollback_repo_pages(
            manifest=_edited_manifest(),
            repo_root=tmp_path,
            client=client,
            summary="Rollback repo-owned wiki deploy",
            assertion="bot",
            assert_user="ErenshorBot",
        )

    assert client.pages == {"Template:Item": "post-deploy human edit"}
    assert client.revisions == {"Template:Item": 3}
    assert client.page_users == {"Template:Item": "HumanEditor"}


def test_rollback_force_overrides_post_deploy_change(tmp_path: Path) -> None:
    """An explicit force restores even when the page changed after deploy."""
    _write_rollback_text(tmp_path)
    client = MediaWikiFake()
    client.put_page("Template:Item", "old template source")
    client.put_page("Template:Item", "deployed template source")
    client.put_page("Template:Item", "post-deploy human edit", user="HumanEditor")

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
    assert entry.title == "Template:Item"
    assert entry.restored_revision_id == 1
    assert entry.new_revision_id == 4
    assert client.pages == {"Template:Item": "old template source"}
    assert client.revisions == {"Template:Item": entry.new_revision_id}
    assert client.page_users == {"Template:Item": "ErenshorBot"}


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
                old_revision_id=None,
                old_revision_timestamp=None,
                new_revision_id=1,
                deploy_action="created",
            ),
            RepoWikiPageManifestEntry(
                title="Template:Item",
                source_path="wiki/templates/Item.wiki",
                source_sha256="0" * 64,
                ownership_class="template",
                upload_stage="template",
                content_model="wikitext",
                old_revision_id=1,
                old_revision_timestamp="2026-06-04T12:00:00Z",
                new_revision_id=2,
                rollback_text_source="variants/main/wiki/rollback/Template_Item.wiki",
                deploy_action="edited",
            ),
        )
    )
    client = MediaWikiFake()
    client.put_page("Module:Erenshor/Data/Items", "return {}")
    client.put_page("Template:Item", "old template source")
    client.put_page("Template:Item", "deployed template source")

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
    assert result.entries[0].new_revision_id == 3
    assert client.pages == {
        "Module:Erenshor/Data/Items": "return {}",
        "Template:Item": "old template source",
    }
    assert client.revisions == {"Module:Erenshor/Data/Items": 1, "Template:Item": 3}
    assert client.page_users == {
        "Module:Erenshor/Data/Items": "ErenshorBot",
        "Template:Item": "ErenshorBot",
    }


def test_rollback_skips_pages_that_a_stopped_deploy_never_wrote(tmp_path: Path) -> None:
    """A prepared entry without a new revision was never written, so rollback leaves its page alone."""
    _write_rollback_text(tmp_path)
    [entry] = _edited_manifest().entries
    manifest = RepoWikiPageManifest(entries=(replace(entry, new_revision_id=None),))
    client = MediaWikiFake()
    client.put_page("Template:Item", "old template source")
    client.put_page("Template:Item", "post-deploy human edit", user="HumanEditor")

    result = rollback_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Rollback repo-owned wiki deploy",
        assertion="bot",
    )

    assert result.entries == ()
    assert client.pages == {"Template:Item": "post-deploy human edit"}
    assert client.revisions == {"Template:Item": 2}
    assert client.page_users == {"Template:Item": "HumanEditor"}
