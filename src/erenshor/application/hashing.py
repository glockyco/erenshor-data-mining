"""Shared file hashing primitives for application services."""

from __future__ import annotations

import hashlib
from pathlib import Path

__all__ = ["SHA256_FILE_CHUNK_SIZE", "sha256_file"]


# Keep file hashing bounded and consistent across application services.
SHA256_FILE_CHUNK_SIZE = 8192


def sha256_file(file_path: Path) -> str:
    """Return the hexadecimal SHA-256 digest of a file without loading it all."""
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        while chunk := stream.read(SHA256_FILE_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()
