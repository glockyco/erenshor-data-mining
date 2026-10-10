"""Contract tests: the shared `MediaWikiFake` agrees with the real local wiki.

Each scenario below runs once against a fresh `MediaWikiFake` and once
against the real MediaWiki client in `wiki-dev/`, asserting the same
observable outcome from both. This is the boundary that keeps the fake
honest: a change to the fake that disagrees with what the real server does
fails here, not in a consumer test that happens to use the same method.

The real-wiki half reuses the harness fixtures in `tests/system/wiki/conftest.py`
and is skipped under the same conditions as the rest of that package: no
local MediaWiki harness, or no Docker to provision accounts and clean up
pages.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from PIL import Image
from tests.fakes.mediawiki import MediaWikiFake

from erenshor.infrastructure.wiki import MediaWikiClient, MediaWikiEditConflictError, MediaWikiFileVersion

if TYPE_CHECKING:
    from tests.system.wiki.conftest import _PageScope

_Client = MediaWikiFake | MediaWikiClient


def _png_bytes(color: tuple[int, int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (4, 4), color).save(buffer, "PNG")
    return buffer.getvalue()


# --- The five scenarios, each shared verbatim between the fake and the real wiki. ---


def _check_create_a_page(client: _Client, title: str) -> None:
    """Creating a missing page returns a revision and makes the page readable at that revision."""
    revision_id = client.safe_create_page(
        title, "Created by the contract suite.\n", client.get_edit_start_timestamp(assertion="bot"), assertion="bot"
    )

    snapshot = client.get_page_snapshots([title], assertion="bot")[title]
    assert snapshot.source_text == "Created by the contract suite."
    assert snapshot.revision is not None
    assert snapshot.revision.revision_id == revision_id

    with pytest.raises(MediaWikiEditConflictError):
        client.safe_create_page(
            title,
            "A second create races the first.\n",
            client.get_edit_start_timestamp(assertion="bot"),
            assertion="bot",
        )


def _check_edit_twice_and_read_revision_history(client: _Client, title: str) -> None:
    """Two successive safe edits each produce a new revision; a stale base revision is a conflict."""
    rev1 = client.safe_create_page(title, "v1\n", client.get_edit_start_timestamp(assertion="bot"), assertion="bot")
    base1 = client.get_page_revision_metadata(title, assertion="bot")
    assert base1 is not None
    assert base1.revision_id == rev1

    rev2 = client.safe_edit_page(title, "v2\n", base1, assertion="bot")
    base2 = client.get_page_revision_metadata(title, assertion="bot")
    assert base2 is not None
    assert base2.revision_id == rev2
    assert rev2 != rev1

    rev3 = client.safe_edit_page(title, "v3\n", base2, assertion="bot")
    final = client.get_page_snapshots([title], assertion="bot")[title]
    assert final.source_text == "v3"
    assert final.revision is not None
    assert final.revision.revision_id == rev3
    assert rev3 not in (rev1, rev2)

    with pytest.raises(MediaWikiEditConflictError):
        client.safe_edit_page(title, "stale\n", base1, assertion="bot")


def _check_upload_a_file(client: _Client, tmp_path: Path, title: str) -> None:
    """Uploading a file makes it listed, downloadable, and the sole entry in its version history."""
    path = tmp_path / "contract-upload.png"
    path.write_bytes(_png_bytes((200, 50, 50, 255)))
    filename = title.removeprefix("File:")

    result = client.upload_file(str(path), filename, "Contract upload", ignore_warnings=True)
    assert result["result"] == "Success"

    versions = client.get_file_versions(title)
    assert len(versions) == 1
    assert isinstance(versions[0], MediaWikiFileVersion)
    assert any(f.title == title for f in client.list_files())
    assert client.download(versions[0].url) == path.read_bytes()


def _check_move_a_file_over_a_redirect(administrator: _Client, tmp_path: Path, source: str, target: str) -> None:
    """Moving a file over a one-revision redirect back to it succeeds, as MediaWiki allows."""
    path = tmp_path / "contract-move.png"
    path.write_bytes(_png_bytes((50, 200, 50, 255)))
    administrator.upload_file(str(path), source.removeprefix("File:"), "Contract upload for move", ignore_warnings=True)
    administrator.safe_create_page(
        target, f"#REDIRECT [[{source}]]", administrator.get_edit_start_timestamp(assertion="user"), assertion="user"
    )

    administrator.move_page(source, target, "Contract move")

    titles = {f.title for f in administrator.list_files()}
    assert target in titles
    assert source not in titles


def _check_delete_then_undelete(administrator: _Client, title: str) -> None:
    """Deleting a page removes it; undeleting restores its exact text."""
    administrator.safe_create_page(
        title, "to be deleted\n", administrator.get_edit_start_timestamp(assertion="user"), assertion="user"
    )
    assert administrator.get_page(title) == "to be deleted"

    administrator.delete_page(title, "Contract delete")
    assert administrator.get_page(title) is None

    administrator.undelete_page(title, "Contract undelete")
    assert administrator.get_page(title) == "to be deleted"


# --- Against the fake. ---


def test_fake_create_a_page() -> None:
    _check_create_a_page(MediaWikiFake(), "ContractCreate")


def test_fake_edit_twice_and_read_revision_history() -> None:
    _check_edit_twice_and_read_revision_history(MediaWikiFake(), "ContractEditHistory")


def test_fake_upload_a_file(tmp_path: Path) -> None:
    _check_upload_a_file(MediaWikiFake(), tmp_path, "File:ContractUpload.png")


def test_fake_move_a_file_over_a_redirect(tmp_path: Path) -> None:
    _check_move_a_file_over_a_redirect(
        MediaWikiFake(), tmp_path, "File:ContractMoveSource.png", "File:ContractMoveTarget.png"
    )


def test_fake_delete_then_undelete() -> None:
    _check_delete_then_undelete(MediaWikiFake(), "ContractDelete")


# --- Against the real local wiki. ---


def test_real_create_a_page(wiki_client: MediaWikiClient, pages: _PageScope) -> None:
    _check_create_a_page(wiki_client, pages.claim("ContractRealCreate"))


def test_real_edit_twice_and_read_revision_history(wiki_client: MediaWikiClient, pages: _PageScope) -> None:
    _check_edit_twice_and_read_revision_history(wiki_client, pages.claim("ContractRealEditHistory"))


def test_real_upload_a_file(wiki_client: MediaWikiClient, pages: _PageScope, tmp_path: Path) -> None:
    _check_upload_a_file(wiki_client, tmp_path, pages.claim("File:ContractRealUpload.png"))


def test_real_move_a_file_over_a_redirect(
    wiki_administrator: MediaWikiClient, pages: _PageScope, tmp_path: Path
) -> None:
    source = pages.claim("File:ContractRealMoveSource.png")
    target = pages.claim("File:ContractRealMoveTarget.png")
    _check_move_a_file_over_a_redirect(wiki_administrator, tmp_path, source, target)


def test_real_delete_then_undelete(wiki_administrator: MediaWikiClient, pages: _PageScope) -> None:
    _check_delete_then_undelete(wiki_administrator, pages.claim("ContractRealDelete"))
