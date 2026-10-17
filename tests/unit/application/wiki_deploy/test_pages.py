"""Tests for deploying repo-owned wiki pages."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from tests.fakes.mediawiki import MediaWikiFake

from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest, build_repo_page_manifest
from erenshor.application.wiki_deploy.pages import RepoPageDriftError, build_deployed_manifest, deploy_repo_pages


def write_page(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_deploy_repo_pages_rejects_templates_before_remote_reads(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/templates/Item.wiki", "{{Item}}\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main", include_templates=True)
    client = MediaWikiFake()
    client.put_page("Template:Item", "old source\n")

    with pytest.raises(ValueError, match="Template pages require explicit deployment opt-in"):
        deploy_repo_pages(
            manifest=manifest,
            repo_root=tmp_path,
            client=client,
            summary="Deploy repo-owned wiki pages",
            assertion="bot",
        )

    assert client.pages["Template:Item"] == "old source"
    assert client.revisions["Template:Item"] == 1


def test_deploy_repo_pages_rejects_generated_data_without_opt_in(tmp_path: Path) -> None:
    write_page(tmp_path, "variants/main/wiki/lua/Erenshor/Data/Links.lua", "return {}\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main", include_generated_data=True)
    client = MediaWikiFake()

    with pytest.raises(ValueError, match="Generated data pages require explicit deployment opt-in"):
        deploy_repo_pages(
            manifest=manifest,
            repo_root=tmp_path,
            client=client,
            summary="Deploy generated data",
            assertion="bot",
        )
    assert client.pages == {}


def test_deploy_repo_pages_accepts_content_opt_in(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/content/Category/Links.wiki", "__HIDDENCAT__\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main", include_content_pages=True)
    client = MediaWikiFake()

    result = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Deploy content page",
        assertion="bot",
        include_content_pages=True,
    )
    assert [entry.title for entry in result.entries] == ["Category:Links"]
    assert client.pages["Category:Links"] == "__HIDDENCAT__"

    client = MediaWikiFake()

    result = deploy_repo_pages(
        manifest=RepoWikiPageManifest(entries=()),
        repo_root=tmp_path,
        client=client,
        summary="Deploy repo-owned wiki pages",
        assertion="bot",
    )

    assert result.entries == ()
    assert client.pages == {}


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
    client = MediaWikiFake()
    client.put_page("Module:Erenshor/Item", source)

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
    assert client.revisions["Module:Erenshor/Item"] == 1


def test_deploy_repo_pages_treats_trailing_newline_difference_as_unchanged(tmp_path: Path) -> None:
    """A repo file whose only difference from the stored page is MediaWiki's save normalization is unchanged."""
    source = "local p = {}\nreturn p\n"
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", source)
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    # MediaWiki stores content with CRLF collapsed and trailing whitespace trimmed.
    client = MediaWikiFake()
    client.put_page("Module:Erenshor/Item", "local p = {}\r\nreturn p")
    result = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Deploy repo-owned wiki pages",
        assertion="bot",
        assert_user="ErenshorBot",
    )
    [entry] = result.entries
    assert entry.status == "unchanged"
    assert client.revisions["Module:Erenshor/Item"] == 1


def test_deploy_repo_pages_safe_edits_changed_pages(tmp_path: Path) -> None:
    """Changed pages are uploaded through revision-guarded safe edits."""
    source = "local p = {}\nfunction p.field() return 'new' end\nreturn p\n"
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", source)
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    client = MediaWikiFake()
    client.put_page("Module:Erenshor/Item", "old source\n")

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
    assert entry.status == "edited"
    assert entry.old_revision_id == 1
    assert entry.old_revision_timestamp == "2026-01-01T00:00:00Z"
    assert entry.new_revision_id == 2
    assert entry.rollback_text_source == "rollback/Module%3AErenshor%2FItem.wiki"
    assert (tmp_path / entry.rollback_text_source).read_text(encoding="utf-8") == "old source"
    assert client.pages["Module:Erenshor/Item"] == source.rstrip()
    assert client.revisions["Module:Erenshor/Item"] == 2


def test_deploy_repo_pages_safe_creates_missing_pages(tmp_path: Path) -> None:
    """Missing repo-owned pages are uploaded through timestamp-guarded create-only edits."""
    source = "return {}\n"
    write_page(tmp_path, "wiki/modules/Erenshor/NewModule.lua", source)
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    client = MediaWikiFake()

    result = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Deploy repo-owned wiki pages",
        assertion="bot",
        assert_user="ErenshorBot",
    )

    [entry] = result.entries
    assert entry.title == "Module:Erenshor/NewModule"
    assert entry.status == "created"
    assert entry.old_revision_id is None
    assert entry.old_revision_timestamp is None
    assert entry.new_revision_id == 1
    assert client.pages["Module:Erenshor/NewModule"] == source.rstrip()
    assert client.revisions["Module:Erenshor/NewModule"] == 1


def test_build_deployed_manifest_merges_deploy_results_into_entries(tmp_path: Path) -> None:
    """The deployed manifest records revision IDs and rollback sources from the deploy result."""
    source = "local p = {}\nfunction p.field() return 'new' end\nreturn p\n"
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", source)
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    client = MediaWikiFake()
    client.put_page("Module:Erenshor/Item", "old source\n")
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
    assert deployed_entry.old_revision_id == 1
    assert deployed_entry.old_revision_timestamp == "2026-01-01T00:00:00Z"
    assert deployed_entry.new_revision_id == 2
    assert deployed_entry.rollback_text_source == "rollback/Module%3AErenshor%2FItem.wiki"
    assert deployed_entry.deploy_action == "edited"
    # The base manifest is not mutated.
    assert base_entry.new_revision_id is None


def test_deploy_repo_pages_aborts_on_stale_source_hash_before_writes(tmp_path: Path) -> None:
    """A source hash mismatch fails before any remote mutation is attempted."""
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "return {}\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "return {stale = true}\n")
    client = MediaWikiFake()
    client.put_page("Module:Erenshor/Item", "old source\n")

    try:
        deploy_repo_pages(
            manifest=manifest,
            repo_root=tmp_path,
            client=client,
            summary="Deploy repo-owned wiki pages",
            assertion="bot",
        )
    except ValueError as error:
        assert "Source hash mismatch" in str(error)
    else:
        raise AssertionError("stale source hash was accepted")

    assert client.pages["Module:Erenshor/Item"] == "old source"
    assert client.revisions["Module:Erenshor/Item"] == 1


def test_deploy_repo_pages_prepares_all_sidecars_before_first_write(tmp_path: Path) -> None:
    """The prepared checkpoint observes every changed existing sidecar before edits."""
    write_page(tmp_path, "wiki/modules/Erenshor/A.lua", "return 'a'\n")
    write_page(tmp_path, "wiki/modules/Erenshor/B.lua", "return 'b'\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    client = MediaWikiFake()
    client.put_page("Module:Erenshor/A", "old a\n")
    client.put_page("Module:Erenshor/B", "old b\n")
    checkpoints: list[RepoWikiPageManifest] = []

    def checkpoint(value: RepoWikiPageManifest) -> None:
        checkpoints.append(value)
        if len(checkpoints) == 1:
            assert (tmp_path / "rollback/Module%3AErenshor%2FA.wiki").read_text(encoding="utf-8") == "old a"
            assert (tmp_path / "rollback/Module%3AErenshor%2FB.wiki").read_text(encoding="utf-8") == "old b"

    deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Deploy repo-owned wiki pages",
        assertion="bot",
        rollback_root=tmp_path / "rollback",
        checkpoint=checkpoint,
    )

    assert len(checkpoints) == 5
    assert checkpoints[1].entries[0].pending_mutation
    assert checkpoints[3].entries[1].pending_mutation
    assert all(not entry.pending_mutation for entry in checkpoints[-1].entries)
    assert client.revisions["Module:Erenshor/A"] == checkpoints[-1].entries[0].new_revision_id
    assert client.revisions["Module:Erenshor/B"] == checkpoints[-1].entries[1].new_revision_id


def test_deploy_repo_pages_checkpoint_journals_partial_failure(tmp_path: Path) -> None:
    """A later write failure leaves the earlier successful write journaled."""
    write_page(tmp_path, "wiki/modules/Erenshor/A.lua", "return 'a'\n")
    write_page(tmp_path, "wiki/modules/Erenshor/B.lua", "return 'b'\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main")

    client = MediaWikiFake()
    client.put_page("Module:Erenshor/A", "old a\n")
    client.put_page("Module:Erenshor/B", "old b\n")
    edits = 0
    real_safe_edit_page = client.safe_edit_page

    def failing_safe_edit_page(*args: object, **kwargs: object):
        nonlocal edits
        if edits:
            raise RuntimeError("second write failed")
        edits += 1
        return real_safe_edit_page(*args, **kwargs)

    client.safe_edit_page = failing_safe_edit_page  # type: ignore[method-assign]
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

    assert len(checkpoints) == 4
    prepared, before_first, after_first, before_second = checkpoints
    assert before_first.entries[0].pending_mutation
    assert not after_first.entries[0].pending_mutation
    assert before_second.entries[0].new_revision_id == client.revisions["Module:Erenshor/A"]
    assert before_second.entries[1].pending_mutation
    assert all(entry.deploy_action is None for entry in prepared.entries)
    actions = {entry.title: entry.deploy_action for entry in after_first.entries}
    assert actions["Module:Erenshor/A"] == "edited"
    assert actions["Module:Erenshor/B"] is None


def test_safe_title_filename_is_injective_for_distinct_titles() -> None:
    """Distinct titles map to distinct rollback sidecar filenames (no lossy collision)."""
    from erenshor.application.wiki_deploy.pages import rollback_filename

    # These collide under a "replace non-alnum with underscore" scheme.
    first = rollback_filename("Template:Item/Quality")
    second = rollback_filename("Template:Item:Quality")

    assert first != second
    # Filenames stay flat: title separators must not become path separators.
    assert "/" not in first
    assert "/" not in second


def _template_deploy(tmp_path: Path, client: MediaWikiFake, accept_drift: tuple[str, ...] = ()):
    checkpoints: list[RepoWikiPageManifest] = []
    result = deploy_repo_pages(
        manifest=build_repo_page_manifest(tmp_path, variant="main", include_templates=True),
        repo_root=tmp_path,
        client=client,
        summary="Deploy repo-owned wiki pages",
        assertion="bot",
        include_templates=True,
        rollback_root=tmp_path / "rollback",
        checkpoint=checkpoints.append,
        accept_drift=accept_drift,
    )
    return result, checkpoints


def test_a_template_that_another_account_reverted_stops_the_deploy_before_any_write(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/templates/Quest.wiki", "{{Quest|lua=1}}\n")
    write_page(tmp_path, "wiki/templates/Zone.wiki", "{{Zone|lua=1}}\n")
    client = MediaWikiFake()
    client.put_page("Template:Quest", "{{Quest}} reverted", user="Admin")
    client.put_page("Template:Zone", "{{Zone}} old")

    with pytest.raises(RepoPageDriftError, match=r"Template:Quest \(revision 1 by Admin\)") as raised:
        _template_deploy(tmp_path, client)

    assert [item.title for item in raised.value.drift] == ["Template:Quest"]
    assert client.revisions["Template:Quest"] == 1
    assert not (tmp_path / "rollback").exists()


def test_an_accepted_page_is_overwritten(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/templates/Quest.wiki", "{{Quest|lua=1}}\n")
    client = MediaWikiFake()
    client.put_page("Template:Quest", "{{Quest}} reverted", user="Admin")

    result, _ = _template_deploy(tmp_path, client, accept_drift=("Template:Quest",))

    assert [(entry.title, entry.status) for entry in result.entries] == [("Template:Quest", "edited")]


def test_a_page_that_another_account_left_equal_to_the_source_is_not_drift(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/templates/Quest.wiki", "{{Quest|lua=1}}\n")
    client = MediaWikiFake()
    client.put_page("Template:Quest", "{{Quest|lua=1}}", user="Admin")

    result, _ = _template_deploy(tmp_path, client)

    assert [(entry.title, entry.status) for entry in result.entries] == [("Template:Quest", "unchanged")]
    assert client.revisions["Template:Quest"] == 1


def test_prepared_snapshots_refuse_a_new_revision_before_creating_rollback(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/modules/Erenshor/Example.lua", "return { new = true }\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    title = "Module:Erenshor/Example"
    client = MediaWikiFake()
    client.put_page(title, "return {}")
    expected = client.get_page_snapshots([title])
    client.put_page(title, "return {}", user="Editor")

    with pytest.raises(ValueError, match="changed after the prepared review"):
        deploy_repo_pages(
            manifest=manifest,
            repo_root=tmp_path,
            client=client,
            summary="Publish reviewed data",
            assertion="bot",
            expected_snapshots=expected,
            rollback_root=tmp_path / "rollback",
            accept_drift=(title,),
        )

    assert client.revisions[title] == 2
    assert not (tmp_path / "rollback").exists()


def test_prepared_snapshot_revision_guards_remain_atomic(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/modules/Erenshor/Example.lua", "return { new = true }\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    title = "Module:Erenshor/Example"
    client = MediaWikiFake()
    client.put_page(title, "return {}")
    expected = client.get_page_snapshots([title])

    result = deploy_repo_pages(
        manifest=manifest,
        repo_root=tmp_path,
        client=client,
        summary="Publish reviewed data",
        assertion="bot",
        expected_snapshots=expected,
        rollback_root=tmp_path / "rollback",
    )

    assert result.entries[0].old_revision_id == expected[title].revision.revision_id
    assert result.entries[0].new_revision_id == client.revisions[title]
