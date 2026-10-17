"""The standalone vendor writer uses the native durable guarded publisher."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from tests.fakes.mediawiki import MediaWikiFake

from erenshor.application.wiki_deploy.manifest import read_repo_page_manifest
from erenshor.infrastructure.wiki import MediaWikiEditVerificationError
from erenshor.tools.vendor_inventory_tables import VendorInventory


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "update_vendor_inventory_tables", Path("src/tools/update_vendor_inventory_tables.py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _updates(script: ModuleType, wiki: MediaWikiFake):
    for title in ("Alpha", "Beta"):
        wiki.put_page(title, "Original " + title)
    snapshots = wiki.get_page_snapshots(["Alpha", "Beta"])
    return tuple(
        script.PendingUpdate(VendorInventory(title, ()), snapshots[title], "Reviewed " + title) for title in snapshots
    )


def test_vendor_native_manifest_records_confirmed_writes(tmp_path: Path) -> None:
    script = _script()
    wiki = MediaWikiFake()
    updates = _updates(script, wiki)
    result = script.update_live(
        wiki, updates, repo_root=tmp_path, run_dir=tmp_path / "run", wiki_root=tmp_path / "wiki"
    )
    manifest = read_repo_page_manifest(result.manifest_path)
    assert not result.failed
    assert result.edited == ("Alpha", "Beta")
    assert manifest.api_url == wiki.api_url
    assert manifest.variant == "main"
    assert manifest.wiki_root == str(tmp_path / "wiki")
    assert {entry.title: entry.new_revision_id for entry in manifest.entries} == wiki.revisions
    assert all(not entry.pending_mutation and not entry.requires_rollback for entry in manifest.entries)


@pytest.mark.parametrize("known_parent", [False, True])
def test_vendor_mismatch_retains_ack_parent_and_stops_later_pages(tmp_path: Path, known_parent: bool) -> None:
    script = _script()
    wiki = MediaWikiFake()
    updates = _updates(script, wiki)
    beta_revision = wiki.revisions["Beta"]
    edit = wiki.safe_edit_page

    def merged_write(title, content, **kwargs):
        assert title == "Alpha"
        wiki.put_page(title, "Original Alpha\nEditor paragraph", user="Editor")
        parent = wiki.get_page_snapshots([title])[title]
        new_revision = edit(title, content + "\nEditor paragraph", parent.revision)
        written = wiki.get_revision_snapshots([new_revision])[new_revision]
        raise MediaWikiEditVerificationError(
            "Saved revision differs from its reviewed parent",
            new_revision_id=new_revision,
            written_snapshot=written if known_parent else None,
            actual_parent_snapshot=parent if known_parent else None,
        )

    wiki.safe_edit_page = merged_write
    with pytest.raises(RuntimeError, match="Vendor publication stopped"):
        script.update_live(wiki, updates, repo_root=tmp_path, run_dir=tmp_path / "run", wiki_root=tmp_path / "wiki")
    manifest = read_repo_page_manifest(tmp_path / "run/manifest.json")
    first, second = manifest.entries
    assert first.new_revision_id == wiki.revisions["Alpha"]
    assert first.pending_acknowledged_revision_id == wiki.revisions["Alpha"]
    assert first.requires_rollback
    assert first.pending_mutation is not known_parent
    assert second.new_revision_id is None
    assert wiki.revisions["Beta"] == beta_revision
    assert wiki.pages["Beta"] == "Original Beta"
    if known_parent:
        assert (tmp_path / first.rollback_text_source).read_bytes() == b"Original Alpha\nEditor paragraph"
        assert first.rollback_content_model == "wikitext"
    assert any(path.read_bytes() == b"Original Alpha" for path in (tmp_path / "run/rollback").glob("*.wiki"))


def test_vendor_conflict_stops_before_the_next_page(tmp_path: Path) -> None:
    script = _script()
    wiki = MediaWikiFake()
    updates = _updates(script, wiki)
    wiki.put_page("Alpha", "Editor replacement", user="Editor")
    before = dict(wiki.revisions)
    with pytest.raises(RuntimeError, match="Vendor publication stopped"):
        script.update_live(wiki, updates, repo_root=tmp_path, run_dir=tmp_path / "run", wiki_root=tmp_path / "wiki")
    assert wiki.revisions == before
    manifest = read_repo_page_manifest(tmp_path / "run/manifest.json")
    assert all(entry.new_revision_id is None and not entry.pending_mutation for entry in manifest.entries)
