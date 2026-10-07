"""Approval of reviewed model captures.

A reviewer approves captures by subject. Approval copies each accepted PNG
out of the staging directory, which the next capture run replaces, and binds
it to its subject, SHA-256, game build, and capture preset. The clean build
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
    subjects: Sequence[str],
    previous: Approval | None = None,
) -> Approval:
    """Approve the accepted captures of ``subjects`` and copy them to ``approved_dir``.

    Earlier approvals of other subjects stay, also of other builds, and a new
    approval of a subject replaces its earlier one. A capture that the review
    rejected, that failed, or whose bytes changed since the review cannot be
    approved.
    """
    if captures["preset"] != manifest["camera_preset"] or captures["game_build"] != manifest["game_build"]:
        raise ValueError("The captures and the manifest are of different builds or presets.")
    results = {result["subject"]: result for result in captures["results"]}
    pages = {entry["subject"]: tuple(entry["pages"]) for entry in manifest["entries"]}
    approved = {image.subject: image for image in (previous.images if previous else ())}
    approved_dir.mkdir(parents=True, exist_ok=True)
    for subject in subjects:
        result = results.get(subject)
        if result is None:
            raise ValueError(f"{subject} has no capture to approve.")
        if result["status"] != "accepted":
            raise ValueError(f"{subject} was {result['status']} in the review and cannot be approved.")
        staged = staging_png_dir / str(result["png"])
        if _sha256(staged) != result["sha256"]:
            raise ValueError(f"{subject} changed after the review.")
        shutil.copy2(staged, approved_dir / staged.name)
        approved[subject] = ApprovedImage(
            subject=subject,
            png=staged.name,
            sha256=str(result["sha256"]),
            stable_key=str(result["stable_key"]),
            kind=str(result["kind"]),
            pages=pages.get(subject, ()),
            game_build=str(captures["game_build"]),
            preset=str(captures["preset"]),
        )
    return Approval(images=tuple(sorted(approved.values(), key=lambda image: image.subject)))
