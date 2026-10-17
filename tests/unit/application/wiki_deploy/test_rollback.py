"""Tests for manifest-backed wiki rollback."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from tests.fakes.mediawiki import MediaWikiFake

from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest, RepoWikiPageManifestEntry
from erenshor.application.wiki_deploy.rollback import rollback_repo_pages
from erenshor.infrastructure.wiki import MediaWikiNetworkError
from erenshor.infrastructure.wiki.client import MediaWikiEditVerificationError
from erenshor.infrastructure.wiki.content import normalize_saved_text


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
                rollback_content_model="wikitext",
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
    client = MediaWikiFake()
    client.put_page("Module:Erenshor/Data/Items", "return {}")
    created_revision = client.revisions["Module:Erenshor/Data/Items"]
    client.put_page("Template:Item", "old template source")
    old_revision = client.revisions["Template:Item"]
    client.put_page("Template:Item", "deployed template source")
    deployed_revision = client.revisions["Template:Item"]
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
                new_revision_id=created_revision,
                deploy_action="created",
            ),
            RepoWikiPageManifestEntry(
                title="Template:Item",
                source_path="wiki/templates/Item.wiki",
                source_sha256="0" * 64,
                ownership_class="template",
                upload_stage="template",
                content_model="wikitext",
                old_revision_id=old_revision,
                old_revision_timestamp="2026-06-04T12:00:00Z",
                new_revision_id=deployed_revision,
                rollback_text_source="variants/main/wiki/rollback/Template_Item.wiki",
                deploy_action="edited",
            ),
        )
    )

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
    assert result.entries[0].new_revision_id == client.revisions["Template:Item"]
    assert client.pages == {
        "Module:Erenshor/Data/Items": "return {}",
        "Template:Item": "old template source",
    }
    assert client.revisions == {
        "Module:Erenshor/Data/Items": created_revision,
        "Template:Item": result.entries[0].new_revision_id,
    }
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


@pytest.mark.parametrize("separator", ["\r\n", "\r"])
def test_rollback_restores_preimage_newlines_byte_exactly(tmp_path: Path, separator: str) -> None:
    _write_rollback_text(tmp_path)
    old = separator.join(("editor text", "second line", "last line"))
    manifest = _edited_manifest()
    [entry] = manifest.entries
    assert entry.rollback_text_source is not None
    (tmp_path / entry.rollback_text_source).write_bytes(old.encode("utf-8"))
    wiki = MediaWikiFake()
    wiki.put_page(entry.title, old)
    wiki.put_page(entry.title, "deployed")
    edit = wiki.safe_edit_page
    sent = []

    def capture_preimage(*args, **kwargs):
        sent.append(kwargs["content"].encode("utf-8"))
        return edit(*args, **kwargs)

    wiki.safe_edit_page = capture_preimage

    rollback_repo_pages(manifest=manifest, repo_root=tmp_path, client=wiki, summary="Restore", assertion="bot")

    assert sent == [old.encode("utf-8")]
    assert wiki.pages[entry.title] == normalize_saved_text(old)


@pytest.mark.parametrize("force", [False, True])
def test_pending_unknown_outcome_blocks_rollback_before_any_mutation(tmp_path: Path, force: bool) -> None:
    _write_rollback_text(tmp_path)
    [entry] = _edited_manifest().entries
    manifest = RepoWikiPageManifest(entries=(replace(entry, pending_mutation=True),))
    wiki = MediaWikiFake()
    wiki.put_page(entry.title, "old template source")
    wiki.put_page(entry.title, "deployed")
    wiki.put_page(entry.title, "later human edit", user="HumanEditor")

    with pytest.raises(ValueError, match="Cannot reconcile pending remote mutation"):
        rollback_repo_pages(
            manifest=manifest, repo_root=tmp_path, client=wiki, summary="Restore", assertion="bot", force=force
        )

    assert wiki.pages[entry.title] == "later human edit"
    assert wiki.revisions[entry.title] == 3


def test_rollback_checkpoints_receipts_before_next_failure_and_resumes(tmp_path: Path) -> None:
    _write_rollback_text(tmp_path)
    [first] = _edited_manifest().entries
    second = replace(first, title="Template:Second")
    manifest = RepoWikiPageManifest(entries=(first, second), variant="reviewed", wiki_root=str(tmp_path.resolve()))
    wiki = MediaWikiFake()
    prepared_entries = []
    for entry in manifest.entries:
        wiki.put_page(entry.title, "old template source")
        old_revision = wiki.revisions[entry.title]
        wiki.put_page(entry.title, "deployed")
        prepared_entries.append(
            replace(entry, old_revision_id=old_revision, new_revision_id=wiki.revisions[entry.title])
        )
    manifest = replace(manifest, entries=tuple(prepared_entries))
    edit = wiki.safe_edit_page
    checkpoints: list[RepoWikiPageManifest] = []

    def lose_second_response(*args, **kwargs) -> int:
        title = kwargs["title"]
        assert checkpoints[-1].entries[0 if title == first.title else 1].pending_mutation
        revision_id = edit(*args, **kwargs)
        if title == second.title:
            raise MediaWikiNetworkError("rollback response lost")
        return revision_id

    wiki.safe_edit_page = lose_second_response
    with pytest.raises(MediaWikiNetworkError, match="rollback response lost"):
        rollback_repo_pages(
            manifest=manifest,
            repo_root=tmp_path,
            client=wiki,
            summary="Restore",
            assertion="bot",
            checkpoint=checkpoints.append,
        )
    saved = checkpoints[-1]
    assert saved.variant == "reviewed"
    assert saved.wiki_root == str(tmp_path.resolve())
    assert saved.entries[0].rollback_revision_id == wiki.revisions[first.title]
    assert not saved.entries[0].pending_mutation
    assert saved.entries[1].new_revision_id == manifest.entries[1].new_revision_id
    assert saved.entries[1].pending_mutation
    before_resume = dict(wiki.revisions)

    wiki.safe_edit_page = edit
    result = rollback_repo_pages(
        manifest=saved,
        repo_root=tmp_path,
        client=wiki,
        summary="Restore",
        assertion="bot",
        checkpoint=checkpoints.append,
    )
    assert result.entries == ()
    assert [entry.rollback_revision_id for entry in checkpoints[-1].entries] == [
        wiki.revisions[first.title],
        wiki.revisions[second.title],
    ]
    assert all(not entry.pending_mutation for entry in checkpoints[-1].entries)
    assert wiki.revisions == before_resume


def test_force_rollback_records_actual_request_base_for_lost_response_recovery(tmp_path: Path) -> None:
    _write_rollback_text(tmp_path)
    manifest = _edited_manifest()
    [entry] = manifest.entries
    wiki = MediaWikiFake()
    wiki.put_page(entry.title, "old template source")
    wiki.put_page(entry.title, "deployed")
    wiki.put_page(entry.title, "later editor text", user="Editor")
    edit = wiki.safe_edit_page
    checkpoints: list[RepoWikiPageManifest] = []

    def lose_response(*args, **kwargs) -> int:
        pending = checkpoints[-1].entries[0]
        assert pending.pending_mutation
        assert pending.pending_operation == "rollback"
        assert pending.pending_base_revision_id == 3
        edit(*args, **kwargs)
        raise MediaWikiNetworkError("lost force rollback response")

    wiki.safe_edit_page = lose_response
    with pytest.raises(MediaWikiNetworkError):
        rollback_repo_pages(
            manifest=manifest,
            repo_root=tmp_path,
            client=wiki,
            summary="Restore",
            assertion="bot",
            force=True,
            checkpoint=checkpoints.append,
        )
    saved = checkpoints[-1]
    assert saved.entries[0].new_revision_id == 2
    assert saved.entries[0].pending_base_revision_id == 3
    assert wiki.revisions[entry.title] == 4
    wiki.safe_edit_page = edit
    result = rollback_repo_pages(
        manifest=saved,
        repo_root=tmp_path,
        client=wiki,
        summary="Restore",
        assertion="bot",
        checkpoint=checkpoints.append,
    )
    assert result.entries == ()
    assert checkpoints[-1].entries[0].rollback_revision_id == 4
    assert not checkpoints[-1].entries[0].pending_mutation
    assert wiki.revisions[entry.title] == 4


def test_failed_rollback_verification_preserves_receipt_without_claiming_restoration(tmp_path: Path) -> None:
    _write_rollback_text(tmp_path)
    manifest = _edited_manifest()
    [entry] = manifest.entries
    wiki = MediaWikiFake()
    wiki.put_page(entry.title, "old template source")
    wiki.put_page(entry.title, "deployed")
    checkpoints: list[RepoWikiPageManifest] = []

    def merged_restore(*args, **kwargs) -> int:
        wiki.put_page(entry.title, "later editor change", user="Editor")
        parent = wiki.get_page_snapshots([entry.title])[entry.title]
        wiki.put_page(entry.title, "old template source\nlater editor change")
        written = wiki.get_page_snapshots([entry.title])[entry.title]
        raise MediaWikiEditVerificationError(
            "Restore did not match the captured request base",
            new_revision_id=4,
            written_snapshot=written,
            actual_parent_snapshot=parent,
        )

    wiki.safe_edit_page = merged_restore
    with pytest.raises(MediaWikiEditVerificationError):
        rollback_repo_pages(
            manifest=manifest,
            repo_root=tmp_path,
            client=wiki,
            summary="Restore",
            assertion="bot",
            checkpoint=checkpoints.append,
        )
    [saved] = checkpoints[-1].entries
    assert saved.new_revision_id == 2
    assert saved.rollback_revision_id is None
    assert saved.pending_acknowledged_revision_id == 4
    assert saved.pending_mutation
    assert saved.requires_rollback
    assert saved.pending_operation == "rollback"
    assert saved.pending_base_revision_id == 2
    with pytest.raises(ValueError, match="Cannot reconcile pending remote mutation"):
        rollback_repo_pages(
            manifest=checkpoints[-1], repo_root=tmp_path, client=wiki, summary="Restore", assertion="bot", force=True
        )
    assert wiki.revisions[entry.title] == 4
