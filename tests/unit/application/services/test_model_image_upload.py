from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from erenshor.application.services.model_image_upload import (
    Approval,
    ApprovedImage,
    approve,
    execute_uploads,
    plan_uploads,
)
from erenshor.infrastructure.wiki import MediaWikiFileUpload, MediaWikiUploadWarningError


def _png(directory: Path, name: str, content: bytes) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _approval(directory: Path, images: dict[str, bytes]) -> Approval:
    approved: list[ApprovedImage] = []
    for file, content in images.items():
        name = file.replace(":", "_")
        sha256 = _png(directory, name, content)
        approved.append(
            ApprovedImage(file, name, sha256, f"character:{file}", "character", (file.removesuffix(".png"),))
        )
    return Approval(game_build="24405256", preset="portrait-1", images=tuple(approved))


class FakeWiki:
    """Live files by title, files by SHA-1, and the writes that an upload run makes."""

    def __init__(self, uploads: dict[str, MediaWikiFileUpload] | None = None) -> None:
        self.uploads = dict(uploads or {})
        self.by_sha1: dict[str, tuple[str, ...]] = {}
        self.uploaded: list[str] = []
        self.created: list[tuple[str, str]] = []
        self.upload_warnings: dict[str, dict[str, Any]] = {}

    def get_file_uploads(self, titles: Sequence[str]) -> dict[str, MediaWikiFileUpload]:
        return {title: self.uploads[title] for title in titles if title in self.uploads}

    def find_files_by_sha1(self, sha1: str) -> tuple[str, ...]:
        return self.by_sha1.get(sha1, ())

    def upload_file(
        self,
        file_path: str,
        filename: str,
        comment: str,
        text: str = "",
        ignore_warnings: bool = False,
        bot: bool = True,
    ) -> dict[str, Any]:
        assert not ignore_warnings
        if filename in self.upload_warnings:
            raise MediaWikiUploadWarningError(self.upload_warnings[filename])
        self.uploaded.append(filename)
        return {"result": "Success"}

    def get_edit_start_timestamp(self) -> str:
        return "2026-10-06T12:00:00Z"

    def safe_create_page(self, title: str, content: str, start_timestamp: str, summary: str | None = None) -> int:
        self.created.append((title, content))
        return 1


def test_an_editor_image_is_skipped_and_its_uploader_named(tmp_path: Path) -> None:
    approval = _approval(tmp_path, {"Faith.png": b"faith"})
    wiki = FakeWiki({"File:Faith.png": MediaWikiFileUpload("File:Faith.png", "Biridian", "abc")})

    plan = plan_uploads(approval, tmp_path, wiki)

    assert [(item.action, item.reason) for item in plan] == [("skip", "exists as File:Faith.png, uploaded by Biridian")]
    assert execute_uploads(plan, wiki, tmp_path, approval, "summary")[0]["action"] == "skip"
    assert (wiki.uploaded, wiki.created) == ([], [])


def test_a_batch_plans_only_its_files_and_refuses_an_unapproved_one(tmp_path: Path) -> None:
    approval = _approval(tmp_path, {"Faith.png": b"faith", "Zenith.png": b"zenith"})

    plan = plan_uploads(approval.batch(["Zenith.png"]), tmp_path, FakeWiki())

    assert [(item.file, item.action) for item in plan] == [("Zenith.png", "upload")]
    with pytest.raises(ValueError, match=r"Not approved: Opus\.png"):
        approval.batch(["Zenith.png", "Opus.png"])


def test_a_title_with_a_colon_uploads_without_it_and_redirects(tmp_path: Path) -> None:
    approval = _approval(tmp_path, {"Summoned: Treant.png": b"treant"})
    wiki = FakeWiki()

    plan = plan_uploads(approval, tmp_path, wiki)
    execute_uploads(plan, wiki, tmp_path, approval, "summary")

    assert [(item.action, item.target) for item in plan] == [("upload", "File:Summoned Treant.png")]
    assert wiki.uploaded == ["Summoned Treant.png"]
    assert wiki.created == [("File:Summoned: Treant.png", "#REDIRECT [[File:Summoned Treant.png]]")]


def test_an_image_that_the_wiki_or_the_batch_holds_becomes_a_redirect(tmp_path: Path) -> None:
    approval = _approval(
        tmp_path,
        {"Braxonian Chest.png": b"chest", "Solunarian Chest.png": b"chest", "Shadow of Brax.png": b"shadow"},
    )
    wiki = FakeWiki()
    wiki.by_sha1[hashlib.sha1(b"shadow", usedforsecurity=False).hexdigest()] = ("File:Skeleton.png",)

    plan = plan_uploads(approval, tmp_path, wiki)
    execute_uploads(plan, wiki, tmp_path, approval, "summary")

    assert [(item.file, item.action, item.target) for item in plan] == [
        ("Braxonian Chest.png", "upload", "File:Braxonian Chest.png"),
        ("Solunarian Chest.png", "redirect", "File:Braxonian Chest.png"),
        ("Shadow of Brax.png", "redirect", "File:Skeleton.png"),
    ]
    assert wiki.uploaded == ["Braxonian Chest.png"]
    assert wiki.created == [
        ("File:Solunarian Chest.png", "#REDIRECT [[File:Braxonian Chest.png]]"),
        ("File:Shadow of Brax.png", "#REDIRECT [[File:Skeleton.png]]"),
    ]


def test_an_image_that_appears_after_the_plan_is_not_replaced(tmp_path: Path) -> None:
    approval = _approval(tmp_path, {"Faith.png": b"faith", "Zenith.png": b"zenith"})
    wiki = FakeWiki()
    plan = plan_uploads(approval, tmp_path, wiki)
    # An editor uploads Faith between the plan and the write, and Zenith
    # arrives while the bot's upload is on its way.
    wiki.uploads["File:Faith.png"] = MediaWikiFileUpload("File:Faith.png", "Editor", "abc")
    wiki.upload_warnings["Zenith.png"] = {"exists": "Zenith.png"}

    results = execute_uploads(plan, wiki, tmp_path, approval, "summary")

    assert [(result["file"], result["action"], result["reason"]) for result in results] == [
        ("Faith.png", "skip", "exists since the plan, uploaded by Editor"),
        ("Zenith.png", "skip", "MediaWiki warned: exists"),
    ]
    assert wiki.uploaded == []


def test_an_approved_image_that_changed_cannot_upload(tmp_path: Path) -> None:
    approval = _approval(tmp_path, {"Faith.png": b"faith"})
    (tmp_path / "Faith.png").write_bytes(b"another image")

    with pytest.raises(ValueError, match="changed after its approval"):
        plan_uploads(approval, tmp_path, FakeWiki())


def _review(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    staging = tmp_path / "staging"
    results = [
        {"file": "Faith.png", "status": "accepted", "png": "Faith.png", "sha256": _png(staging, "Faith.png", b"faith")},
        {"file": "Opus.png", "status": "rejected", "png": "Opus.png", "sha256": _png(staging, "Opus.png", b"opus")},
    ]
    for result in results:
        result.update(stable_key=f"character:{result['file']}", kind="character")
    captures = {"game_build": "24405256", "preset": "portrait-1", "results": results}
    manifest = {
        "game_build": "24405256",
        "camera_preset": "portrait-1",
        "entries": [{"file": "Faith.png", "pages": ["Faith"]}, {"file": "Opus.png", "pages": ["Opus"]}],
    }
    return captures, manifest, staging


def test_approval_copies_an_accepted_capture_with_its_pages(tmp_path: Path) -> None:
    captures, manifest, staging = _review(tmp_path)

    approval = approve(captures, manifest, staging, tmp_path / "approved", ["Faith.png"])

    assert [(image.file, image.pages) for image in approval.images] == [("Faith.png", ("Faith",))]
    assert (tmp_path / "approved" / "Faith.png").read_bytes() == b"faith"


def test_a_rejected_capture_cannot_be_approved(tmp_path: Path) -> None:
    captures, manifest, staging = _review(tmp_path)

    with pytest.raises(ValueError, match=r"Opus\.png was rejected in the review"):
        approve(captures, manifest, staging, tmp_path / "approved", ["Opus.png"])
    assert not (tmp_path / "approved" / "Opus.png").exists()
