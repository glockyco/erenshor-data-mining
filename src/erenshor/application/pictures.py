"""The identity of a game picture, independent of how a file encodes it.

Two PNG files can hold the same picture with different bytes: another
compression level, another encoder, or extra metadata. A picture is therefore
identified by the SHA-256 of its width, height, and RGBA pixels. The image
catalog, the publishing plan, and the map's icons all compare pictures this
way.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["PictureIdentity", "identify", "identify_file"]


@dataclass(frozen=True, slots=True)
class PictureIdentity:
    """A picture's pixel hash and its size in pixels."""

    pixel_hash: str
    width: int
    height: int


def identify(data: bytes) -> PictureIdentity:
    """Decode an image and return the identity of its pixels."""
    with Image.open(io.BytesIO(data)) as image:
        rgba = image.convert("RGBA")
    digest = hashlib.sha256(f"{rgba.width}x{rgba.height}".encode() + b"\0" + rgba.tobytes())
    return PictureIdentity(pixel_hash=digest.hexdigest(), width=rgba.width, height=rgba.height)


def identify_file(path: Path) -> PictureIdentity:
    """Return the identity of the picture in an image file."""
    return identify(path.read_bytes())
