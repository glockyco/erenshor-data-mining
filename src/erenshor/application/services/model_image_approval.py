"""Approval of reviewed model captures.

A reviewer approves captures by file title. Approval copies each accepted PNG
out of the staging directory, which the next capture run replaces, and binds
it to its file title, SHA-256, game build, and capture preset. The clean build
catalogues the approved copies, and ``images publish`` uploads them.
"""

from __future__ import annotations

import hashlib
import shutil
from typing import TYPE_CHECKING, Any

from erenshor.domain.value_objects.capture_approval import Approval, ApprovedImage

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path


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

    Earlier approvals of other files stay, also of other builds, and a new
    approval of a file replaces its earlier one. A capture that the review
    rejected, that failed, or whose bytes changed since the review cannot be
    approved.
    """
    if captures["preset"] != manifest["camera_preset"] or captures["game_build"] != manifest["game_build"]:
        raise ValueError("The captures and the manifest are of different builds or presets.")
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
            game_build=str(captures["game_build"]),
            preset=str(captures["preset"]),
        )
    return Approval(images=tuple(sorted(approved.values(), key=lambda image: image.file)))
