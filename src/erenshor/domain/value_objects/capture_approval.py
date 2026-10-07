"""The record of reviewed model captures that may go to the wiki.

A reviewer approves captures by subject. Each approval binds the approved
PNG, a copy outside the staging set, to its subject and to the SHA-256 of its
bytes, and records the game build and camera preset of its capture. Approvals
of different builds coexist: a portrait stays approved until a review approves
another capture for its subject.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["APPROVAL_FILE", "Approval", "ApprovedImage"]

APPROVAL_FILE = "approved.json"


@dataclass(frozen=True, slots=True)
class ApprovedImage:
    """A reviewed capture that may go to the wiki for ``subject``.

    ``png`` names the approved copy in the approved directory, and ``sha256``
    is the hash of its bytes.
    """

    subject: str
    png: str
    sha256: str
    stable_key: str
    kind: str
    pages: tuple[str, ...]
    game_build: str
    preset: str

    def to_json(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "png": self.png,
            "sha256": self.sha256,
            "stable_key": self.stable_key,
            "kind": self.kind,
            "pages": list(self.pages),
            "game_build": self.game_build,
            "preset": self.preset,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> ApprovedImage:
        return cls(
            subject=str(data["subject"]),
            png=str(data["png"]),
            sha256=str(data["sha256"]),
            stable_key=str(data["stable_key"]),
            kind=str(data["kind"]),
            pages=tuple(str(page) for page in data["pages"]),
            game_build=str(data["game_build"]),
            preset=str(data["preset"]),
        )


@dataclass(frozen=True, slots=True)
class Approval:
    """Every approved capture, at most one per subject, in subject order."""

    images: tuple[ApprovedImage, ...]

    def to_json(self) -> dict[str, Any]:
        return {"images": [image.to_json() for image in self.images]}

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Approval:
        return cls(images=tuple(ApprovedImage.from_json(image) for image in data["images"]))
