"""Historical proofs use the same immutable revisions as current fake reads."""

from __future__ import annotations

import pytest

from erenshor.infrastructure.wiki import MediaWikiAPIError
from tests.fakes.mediawiki import MediaWikiFake


def test_fake_history_has_global_ids_true_parents_and_immutable_sources() -> None:
    wiki = MediaWikiFake(api_url="https://fixture.invalid/api.php")
    wiki.put_page("Example", "Original\rsource", user="Editor")
    original = wiki.get_page_snapshots(["Example"])["Example"]
    assert original.revision is not None
    wiki.put_page("Module:Other", "return {}")
    other_id = wiki.revisions["Module:Other"]
    new_id = wiki.safe_edit_page("Example", "Reviewed source", original.revision)

    historical = wiki.get_revision_snapshots([original.revision.revision_id, other_id, new_id])
    assert len(historical) == 3
    assert len({original.revision.revision_id, other_id, new_id}) == 3
    assert historical[original.revision.revision_id] == original
    assert historical[original.revision.revision_id].source_text == "Original\nsource"
    assert historical[original.revision.revision_id].revision.user == "Editor"
    assert historical[new_id].revision.parent_revision_id == original.revision.revision_id
    assert historical[other_id].revision.parent_revision_id == 0
    assert historical[other_id].content_model == "Scribunto"
    assert historical[new_id].content_model == "wikitext"
    assert wiki.api_url == "https://fixture.invalid/api.php"


def test_fake_history_follows_page_identity_through_move_delete_and_restore() -> None:
    wiki = MediaWikiFake()
    wiki.put_page("Example", "Original")
    revision_id = wiki.revisions["Example"]
    page_id = wiki.page_ids["Example"]
    wiki.move_page("Example", "Moved", "Move fixture")
    moved = wiki.get_revision_snapshots([revision_id])[revision_id]
    assert moved.title == "Moved"
    assert moved.revision.title == "Moved"
    assert moved.revision.page_id == page_id
    wiki.delete_page("Moved", "Delete fixture")
    with pytest.raises(MediaWikiAPIError, match="unreadable"):
        wiki.get_revision_snapshots([revision_id])
    wiki.undelete_page("Moved", "Restore fixture")
    restored = wiki.get_revision_snapshots([revision_id])[revision_id]
    assert restored == moved
    assert wiki.revisions["Moved"] == revision_id


def test_fake_history_refuses_missing_revisions_and_invalid_ids() -> None:
    wiki = MediaWikiFake()
    wiki.put_page("Example", "Original")
    with pytest.raises(MediaWikiAPIError, match="unreadable"):
        wiki.get_revision_snapshots([999])
    with pytest.raises(ValueError, match="positive integers"):
        wiki.get_revision_snapshots([True])


@pytest.mark.parametrize(
    ("source", "saved"),
    [
        ("First\r\nSecond\rThird \t\n\r\x00\x0b", "First\nSecond\nThird"),
        ("Source\u00a0 \t\n", "Source\u00a0"),
        ("Source\u2003", "Source\u2003"),
        ("Source\x0c", "Source\x0c"),
    ],
)
def test_fake_writes_use_mediawiki_saved_text_normalization(source: str, saved: str) -> None:
    wiki = MediaWikiFake()
    wiki.put_page("Example", source)
    original_id = wiki.revisions["Example"]
    original = wiki.get_page_snapshots(["Example"])["Example"]
    assert original.source_text == saved
    assert original.revision is not None

    edit_id = wiki.safe_edit_page("Example", source, original.revision)
    create_id = wiki.safe_create_page("Other", source, "t")

    assert wiki.pages == {"Example": saved, "Other": saved}
    history = wiki.get_revision_snapshots([original_id, edit_id, create_id])
    assert all(snapshot.source_text == saved for snapshot in history.values())


def test_fake_records_supplied_summaries_per_immutable_revision() -> None:
    wiki = MediaWikiFake()
    wiki.put_page("Example", "Original source", summary="Initial summary")
    original = wiki.get_page_snapshots(["Example"])["Example"]
    assert original.revision is not None
    edited_id = wiki.safe_edit_page(
        "Example", "Reviewed source", original.revision, summary="Reviewed marker sha256:actual"
    )
    edited = wiki.get_page_snapshots(["Example"])["Example"]
    assert edited.revision is not None
    empty_id = wiki.safe_edit_page("Example", "Another source", edited.revision, summary="")
    created_id = wiki.safe_create_page("Created", "Created source", "t", summary="Create marker")
    history = wiki.get_revision_snapshots([original.revision.revision_id, edited_id, empty_id, created_id])
    assert history[original.revision.revision_id].revision.comment == "Initial summary"
    assert history[edited_id].revision.comment == "Reviewed marker sha256:actual"
    assert history[empty_id].revision.comment == ""
    assert history[created_id].revision.comment == "Create marker"
    wiki.put_page("Unknown", "Arranged source")
    unknown = wiki.get_page_snapshots(["Unknown"])["Unknown"]
    assert unknown.revision is not None and unknown.revision.comment is None
