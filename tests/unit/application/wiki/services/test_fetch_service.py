"""Tests for wiki fetch freshness and page-title indexing."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from tests.unit.application.wiki_lua.fakes import (
    make_character,
    make_item,
    make_skill,
    make_spell,
    make_stance,
    make_zone,
)

from erenshor.application.wiki.services.fetch_service import WikiFetchService, build_fetch_page_index
from erenshor.application.wiki.services.storage import WikiMetadataError, WikiStorage
from erenshor.infrastructure.wiki.client import MediaWikiPageRevision, MediaWikiPageSnapshot


def _snapshot(title: str, revision_id: int, content: str) -> MediaWikiPageSnapshot:
    return MediaWikiPageSnapshot(
        title=title,
        source_text=content,
        revision=MediaWikiPageRevision(
            title=title,
            page_id=7,
            revision_id=revision_id,
            timestamp="2026-09-27T12:00:00Z",
            start_timestamp="2026-09-27T12:00:00Z",
            user="ErenshorBot",
        ),
        start_timestamp="2026-09-27T12:00:00Z",
    )


def _fetch_service(tmp_path: Path) -> tuple[WikiFetchService, WikiStorage, Mock]:
    storage = WikiStorage(tmp_path)
    client = Mock()
    service = WikiFetchService(client, Mock(storage=storage))
    service._build_page_title_index = Mock(return_value={"A Page": ["item:a_page"]})
    return service, storage, client


def test_page_edited_after_fetch_is_refetched(tmp_path: Path) -> None:
    service, storage, client = _fetch_service(tmp_path)
    client.get_page_revision_ids.return_value = {"A Page": 42}
    client.get_page_snapshots.return_value = {"A Page": _snapshot("A Page", 42, "Old text")}
    assert service._fetch_pages_bulk(["A Page"], dry_run=False).succeeded == 1

    client.get_page_revision_ids.return_value = {"A Page": 43}
    client.get_page_snapshots.return_value = {"A Page": _snapshot("A Page", 43, "Community edit")}
    result = service._fetch_pages_bulk(["A Page"], dry_run=False)

    assert (result.succeeded, result.skipped, result.failed) == (1, 0, 0)
    assert storage.read_fetched_by_title("A Page") == "Community edit"
    assert storage.get_metadata_by_title("A Page").fetched_revision_id == 43
    assert client.get_page_snapshots.call_count == 2


def test_unchanged_page_skips_content_download(tmp_path: Path) -> None:
    service, storage, client = _fetch_service(tmp_path)
    storage.save_fetched_by_title("A Page", ["item:a_page"], "Cached text", ["A Page"], 42)
    client.get_page_revision_ids.return_value = {"A Page": 42}

    result = service._fetch_pages_bulk(["A Page"], dry_run=False)

    assert (result.succeeded, result.skipped, result.failed) == (0, 1, 0)
    assert storage.read_fetched_by_title("A Page") == "Cached text"
    client.get_page_snapshots.assert_not_called()


def test_missing_local_copy_is_refetched_even_with_matching_revision(tmp_path: Path) -> None:
    service, storage, client = _fetch_service(tmp_path)
    storage.save_fetched_by_title("A Page", ["item:a_page"], "Old text", ["A Page"], 42)
    storage.clear_fetched()
    client.get_page_revision_ids.return_value = {"A Page": 42}
    client.get_page_snapshots.return_value = {"A Page": _snapshot("A Page", 42, "Current text")}

    result = service._fetch_pages_bulk(["A Page"], dry_run=False)

    assert result.succeeded == 1
    assert storage.read_fetched_by_title("A Page") == "Current text"


def test_legacy_cache_without_revision_is_refetched(tmp_path: Path) -> None:
    service, storage, client = _fetch_service(tmp_path)
    storage.save_fetched_by_title("A Page", ["item:a_page"], "Stale text", ["A Page"], 41)

    metadata_file = tmp_path / "metadata.json"
    data = json.loads(metadata_file.read_text(encoding="utf-8"))
    del data["A Page"]["fetched_revision_id"]
    metadata_file.write_text(json.dumps(data), encoding="utf-8")
    client.get_page_revision_ids.return_value = {"A Page": 42}
    client.get_page_snapshots.return_value = {"A Page": _snapshot("A Page", 42, "Current text")}

    result = service._fetch_pages_bulk(["A Page"], dry_run=False)

    assert result.succeeded == 1
    assert storage.read_fetched_by_title("A Page") == "Current text"


def test_deleted_page_discards_cached_text_before_generation(tmp_path: Path) -> None:
    service, storage, client = _fetch_service(tmp_path)
    storage.save_fetched_by_title("A Page", ["item:a_page"], "Removed text", ["A Page"], 42)
    client.get_page_revision_ids.return_value = {"A Page": None}

    result = service._fetch_pages_bulk(["A Page"], dry_run=False)

    assert (result.succeeded, result.skipped, result.failed) == (0, 1, 0)
    assert storage.read_fetched_by_title("A Page") is None
    assert storage.get_metadata_by_title("A Page").fetched_revision_id is None
    client.get_page_snapshots.assert_not_called()


def test_missing_page_never_downloads_content(tmp_path: Path) -> None:
    service, storage, client = _fetch_service(tmp_path)
    client.get_page_revision_ids.return_value = {"A Page": None}

    first = service._fetch_pages_bulk(["A Page"], dry_run=False)
    second = service._fetch_pages_bulk(["A Page"], dry_run=False)

    assert (first.skipped, second.skipped) == (1, 1)
    assert storage.read_fetched_by_title("A Page") is None
    client.get_page_snapshots.assert_not_called()


def test_deleted_page_is_refetched_if_recreated(tmp_path: Path) -> None:
    service, storage, client = _fetch_service(tmp_path)
    storage.save_fetched_by_title("A Page", ["item:a_page"], "Removed text", ["A Page"], 42)
    client.get_page_revision_ids.return_value = {"A Page": None}
    assert service._fetch_pages_bulk(["A Page"], dry_run=False).skipped == 1

    client.get_page_revision_ids.return_value = {"A Page": 43}
    client.get_page_snapshots.return_value = {"A Page": _snapshot("A Page", 43, "Restored text")}
    result = service._fetch_pages_bulk(["A Page"], dry_run=False)

    assert result.succeeded == 1
    assert storage.read_fetched_by_title("A Page") == "Restored text"


def test_corrupt_metadata_stops_fetch_and_names_input(tmp_path: Path) -> None:
    service, _, client = _fetch_service(tmp_path)
    (tmp_path / "metadata.json").write_text("{bad json", encoding="utf-8")

    with pytest.raises(WikiMetadataError, match=r"metadata\.json.*Expecting property name"):
        service._fetch_pages_bulk(["A Page"], dry_run=False)

    client.get_page_revision_ids.assert_not_called()


def test_force_refetch_downloads_unchanged_page(tmp_path: Path) -> None:
    service, storage, client = _fetch_service(tmp_path)
    storage.save_fetched_by_title("A Page", ["item:a_page"], "Old text", ["A Page"], 42)
    client.get_page_snapshots.return_value = {"A Page": _snapshot("A Page", 42, "Current text")}

    result = service._fetch_pages_bulk(["A Page"], dry_run=False, force_refetch=True)

    assert result.succeeded == 1
    assert storage.read_fetched_by_title("A Page") == "Current text"
    client.get_page_revision_ids.assert_not_called()


def test_failed_revision_lookup_does_not_reuse_cached_page(tmp_path: Path) -> None:
    from erenshor.infrastructure.wiki.client import MediaWikiAPIError

    service, storage, client = _fetch_service(tmp_path)
    storage.save_fetched_by_title("A Page", ["item:a_page"], "Old text", ["A Page"], 42)
    client.get_page_revision_ids.side_effect = MediaWikiAPIError("wiki unavailable")

    result = service._fetch_pages_bulk(["A Page"], dry_run=False)

    assert result.failed == 1
    assert "wiki unavailable" in result.errors[0]
    client.get_page_snapshots.assert_not_called()


def _context_with_one_of_each() -> Mock:
    context = Mock()
    context.item_repo.get_items_for_wiki_generation.return_value = [make_item()]
    context.character_repo.get_characters_for_wiki_generation.return_value = [make_character()]
    context.spell_repo.get_spells_for_wiki_generation.return_value = [make_spell()]
    context.skill_repo.get_skills_for_wiki_generation.return_value = [make_skill()]
    context.stance_repo.get_all.return_value = [make_stance()]
    context.zone_repo.get_all_zones.return_value = [make_zone()]
    return context


def test_build_fetch_page_index_includes_zone_pages() -> None:
    """Zone pages contribute stable keys to the fetch metadata index."""
    zone = make_zone()
    context = _context_with_one_of_each()
    context.zone_repo.get_all_zones.return_value = [zone]

    index = build_fetch_page_index(context)

    assert index[zone.wiki_page_name] == [zone.stable_key]


def test_build_fetch_page_index_groups_every_entity_kind() -> None:
    """Every wiki-generated entity kind is represented in the index."""
    context = _context_with_one_of_each()

    index = build_fetch_page_index(context)

    assert {
        "Sword of Flames",
        "A Grizzly Bear",
        "Minor Lightning",
        "Double Attack",
        "Aggressive Stance",
        "Port Azure",
    } <= set(index)
