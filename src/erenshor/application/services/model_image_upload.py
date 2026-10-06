"""Approval and upload of reviewed model captures.

A reviewer approves captures by file title. Approval copies each accepted PNG
out of the staging directory, which the next capture run replaces, and binds
it to its file title and SHA-256. The upload plan reads the live wiki for each
approved file: a file that has bytes, directly or through a redirect, is
skipped and its uploader named; a file whose bytes the wiki already holds under
another title, or that an earlier file of the batch uploads, becomes a redirect
to that file; every other file is uploaded. MediaWiki forbids colons in
uploaded file names, so a title with a colon is uploaded without it and
redirects to that upload. Each write checks the live title again just before
it happens, and uploads never ignore MediaWiki's warnings, so the bot never
replaces an image that someone uploaded in the meantime (design D4 of the
change restore-missing-wiki-images).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

from erenshor.domain.value_objects.wiki_filename import sanitize_wiki_filename
from erenshor.infrastructure.wiki import MediaWikiEditError, MediaWikiUploadWarningError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from erenshor.infrastructure.wiki import MediaWikiFileUpload

APPROVAL_FILE = "approved.json"


class LiveFiles(Protocol):
    """The reads of the live wiki that an upload plan needs."""

    def get_file_uploads(self, titles: Sequence[str]) -> dict[str, MediaWikiFileUpload]: ...

    def find_files_by_sha1(self, sha1: str) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class ApprovedImage:
    """A reviewed capture that may go to the wiki under ``file``."""

    file: str
    png: str
    sha256: str
    stable_key: str
    kind: str
    pages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Approval:
    game_build: str
    preset: str
    images: tuple[ApprovedImage, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "game_build": self.game_build,
            "preset": self.preset,
            "images": [
                {
                    "file": image.file,
                    "png": image.png,
                    "sha256": image.sha256,
                    "stable_key": image.stable_key,
                    "kind": image.kind,
                    "pages": list(image.pages),
                }
                for image in self.images
            ],
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Approval:
        return cls(
            game_build=str(data["game_build"]),
            preset=str(data["preset"]),
            images=tuple(
                ApprovedImage(
                    file=str(image["file"]),
                    png=str(image["png"]),
                    sha256=str(image["sha256"]),
                    stable_key=str(image["stable_key"]),
                    kind=str(image["kind"]),
                    pages=tuple(image["pages"]),
                )
                for image in data["images"]
            ),
        )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def approve(
    captures: Mapping[str, Any],
    manifest: Mapping[str, Any],
    staging_png_dir: Path,
    approved_dir: Path,
    files: Sequence[str],
    previous: Approval | None = None,
) -> Approval:
    """Approve the accepted captures of ``files`` and copy them to ``approved_dir``.

    Earlier approvals of other files stay, and a new approval of a file
    replaces its earlier one. A capture that the review rejected, that failed,
    or whose bytes changed since the review cannot be approved.
    """
    if captures["preset"] != manifest["camera_preset"] or captures["game_build"] != manifest["game_build"]:
        raise ValueError("The captures and the manifest are of different builds or presets.")
    if previous is not None and (previous.preset, previous.game_build) != (captures["preset"], captures["game_build"]):
        raise ValueError("The earlier approvals are of another build or preset.")
    results = {result["file"]: result for result in captures["results"]}
    pages = {entry["file"]: tuple(entry["pages"]) for entry in manifest["entries"]}
    approved = {image.file: image for image in (previous.images if previous else ())}
    approved_dir.mkdir(parents=True, exist_ok=True)
    for file in files:
        result = results.get(file)
        if result is None:
            raise ValueError(f"{file} has no capture to approve.")
        if result["status"] != "accepted":
            raise ValueError(f"{file} was {result['status']} in the review and cannot be approved.")
        staged = staging_png_dir / str(result["png"])
        if _sha256(staged) != result["sha256"]:
            raise ValueError(f"{file} changed after the review.")
        shutil.copy2(staged, approved_dir / staged.name)
        approved[file] = ApprovedImage(
            file=file,
            png=staged.name,
            sha256=str(result["sha256"]),
            stable_key=str(result["stable_key"]),
            kind=str(result["kind"]),
            pages=pages.get(file, ()),
        )
    return Approval(
        game_build=str(captures["game_build"]),
        preset=str(captures["preset"]),
        images=tuple(sorted(approved.values(), key=lambda image: image.file)),
    )


def upload_title(file: str) -> str:
    """The title that an upload of ``file`` takes: MediaWiki forbids colons and other characters in file names."""
    stem, dot, extension = file.rpartition(".")
    return f"{sanitize_wiki_filename(stem)}{dot}{extension}" if dot else sanitize_wiki_filename(file)


@dataclass(frozen=True, slots=True)
class PlannedWrite:
    """What the upload does for one approved file.

    ``upload`` stores the image as ``target`` and, when that differs from the
    file title, redirects the title to it. ``redirect`` points the title at
    ``target``, an image the wiki holds or the batch uploads. ``skip`` leaves
    the title alone for ``reason``.
    """

    file: str
    action: Literal["upload", "redirect", "skip"]
    target: str | None
    reason: str
    image: ApprovedImage


def plan_uploads(approval: Approval, approved_dir: Path, live: LiveFiles) -> list[PlannedWrite]:
    """The write of each approved file, from the live state of the wiki."""
    for image in approval.images:
        if _sha256(approved_dir / image.png) != image.sha256:
            raise ValueError(f"{image.file} changed after its approval.")
    titles = [f"File:{image.file}" for image in approval.images]
    titles += [f"File:{upload_title(image.file)}" for image in approval.images]
    uploads = live.get_file_uploads(titles)

    plan: list[PlannedWrite] = []
    batch_uploads: dict[str, str] = {}
    for image in approval.images:
        existing = uploads.get(f"File:{image.file}")
        if existing is not None:
            reason = f"exists as {existing.title}, uploaded by {existing.user}"
            plan.append(PlannedWrite(image.file, "skip", None, reason, image))
            continue
        target = upload_title(image.file)
        sanitized = uploads.get(f"File:{target}")
        if sanitized is not None:
            reason = f"the upload {target} exists, uploaded by {sanitized.user}"
            plan.append(PlannedWrite(image.file, "redirect", f"File:{target}", reason, image))
            continue
        sha1 = hashlib.sha1((approved_dir / image.png).read_bytes(), usedforsecurity=False).hexdigest()
        duplicates = live.find_files_by_sha1(sha1)
        if duplicates:
            plan.append(PlannedWrite(image.file, "redirect", duplicates[0], "the wiki has the same image", image))
            continue
        if image.sha256 in batch_uploads:
            plan.append(
                PlannedWrite(
                    image.file,
                    "redirect",
                    batch_uploads[image.sha256],
                    "the batch uploads the same image",
                    image,
                )
            )
            continue
        batch_uploads[image.sha256] = f"File:{target}"
        plan.append(PlannedWrite(image.file, "upload", f"File:{target}", "missing", image))
    return plan


def description(image: ApprovedImage, approval: Approval) -> str:
    """The file description page of an uploaded capture."""
    subject = f"[[{image.pages[0]}]]" if image.pages else "a character"
    return (
        f"Rendered from the in-game model of {subject} (game build {approval.game_build}, "
        f"capture preset {approval.preset}). An in-game screenshot may replace it."
    )


def write_record(path: Path, approval: Approval, results: Sequence[Mapping[str, Any]]) -> None:
    """Record what an upload run wrote, for its review and for a rollback."""
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"game_build": approval.game_build, "preset": approval.preset, "results": list(results)}
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class WikiWriter(Protocol):
    """The reads and writes of the live wiki that an upload run needs."""

    def get_file_uploads(self, titles: Sequence[str]) -> dict[str, MediaWikiFileUpload]: ...

    def upload_file(
        self,
        file_path: str,
        filename: str,
        comment: str,
        text: str = "",
        ignore_warnings: bool = False,
        bot: bool = True,
    ) -> dict[str, Any]: ...

    def get_edit_start_timestamp(self) -> str: ...

    def safe_create_page(self, title: str, content: str, start_timestamp: str, summary: str | None = None) -> int: ...


def execute_uploads(
    plan: Sequence[PlannedWrite], writer: WikiWriter, approved_dir: Path, approval: Approval, summary: str
) -> list[dict[str, Any]]:
    """Carry out the plan, checking each title again just before its write.

    A title that gained an image since the plan, an upload that MediaWiki
    answers with a warning, and a redirect whose page appeared meanwhile are
    skipped, so no write replaces anything.
    """
    results: list[dict[str, Any]] = []
    for item in plan:
        record: dict[str, Any] = {
            "file": item.file,
            "action": item.action,
            "target": item.target,
            "reason": item.reason,
        }
        results.append(record)
        if item.action == "skip":
            continue
        title = f"File:{item.file}"
        existing = writer.get_file_uploads([title]).get(title)
        if existing is not None:
            record.update(action="skip", reason=f"exists since the plan, uploaded by {existing.user}")
            continue
        target = item.target
        if target is None:
            raise ValueError(f"The {item.action} of {item.file} names no target.")
        if item.action == "upload":
            try:
                writer.upload_file(
                    str(approved_dir / item.image.png),
                    target.removeprefix("File:"),
                    summary,
                    text=description(item.image, approval),
                    ignore_warnings=False,
                )
            except MediaWikiUploadWarningError as warning:
                record.update(action="skip", reason=f"MediaWiki warned: {', '.join(sorted(warning.warnings))}")
                continue
            record["uploaded"] = target
            if target == title:
                continue
        try:
            record["redirect_revision"] = writer.safe_create_page(
                title, f"#REDIRECT [[{target}]]", writer.get_edit_start_timestamp(), summary=summary
            )
        except MediaWikiEditError as error:
            record.update(redirect_error=str(error))
    return results
