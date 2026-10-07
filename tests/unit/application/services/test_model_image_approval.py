from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from erenshor.application.services.model_image_approval import approve


def _png(directory: Path, name: str, content: bytes) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _review(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    staging = tmp_path / "staging"
    results = [
        {"subject": "Faith", "status": "accepted", "png": "Faith.png", "sha256": _png(staging, "Faith.png", b"faith")},
        {"subject": "Opus", "status": "rejected", "png": "Opus.png", "sha256": _png(staging, "Opus.png", b"opus")},
    ]
    for result in results:
        result.update(stable_key=f"character:{result['subject']}", kind="character")
    captures = {"game_build": "24405256", "preset": "portrait-1", "results": results}
    manifest = {
        "game_build": "24405256",
        "camera_preset": "portrait-1",
        "entries": [{"subject": "Faith", "pages": ["Faith"]}, {"subject": "Opus", "pages": ["Opus"]}],
    }
    return captures, manifest, staging


def test_approval_copies_an_accepted_capture_with_its_pages(tmp_path: Path) -> None:
    captures, manifest, staging = _review(tmp_path)

    approval = approve(captures, manifest, staging, tmp_path / "approved", ["Faith"])

    assert [(image.subject, image.pages) for image in approval.images] == [("Faith", ("Faith",))]
    assert (tmp_path / "approved" / "Faith.png").read_bytes() == b"faith"


def test_a_rejected_capture_cannot_be_approved(tmp_path: Path) -> None:
    captures, manifest, staging = _review(tmp_path)

    with pytest.raises(ValueError, match=r"Opus\ was rejected in the review"):
        approve(captures, manifest, staging, tmp_path / "approved", ["Opus"])
    assert not (tmp_path / "approved" / "Opus.png").exists()


def test_a_capture_that_changed_after_the_review_cannot_be_approved(tmp_path: Path) -> None:
    captures, manifest, staging = _review(tmp_path)
    (staging / "Faith.png").write_bytes(b"another image")

    with pytest.raises(ValueError, match=r"Faith\ changed after the review"):
        approve(captures, manifest, staging, tmp_path / "approved", ["Faith"])


def test_a_new_build_approves_a_capture_and_keeps_the_approvals_of_an_earlier_build(tmp_path: Path) -> None:
    captures, manifest, staging = _review(tmp_path)
    earlier = approve(captures, manifest, staging, tmp_path / "approved", ["Faith"])
    captures["game_build"] = manifest["game_build"] = "25000000"
    captures["results"][1]["status"] = "accepted"

    approval = approve(captures, manifest, staging, tmp_path / "approved", ["Opus"], earlier)

    assert [(image.subject, image.game_build) for image in approval.images] == [
        ("Faith", "24405256"),
        ("Opus", "25000000"),
    ]
