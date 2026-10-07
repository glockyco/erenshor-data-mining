"""Verified local access to HotRepl artifact references."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.parse import unquote, urlsplit

from erenshor.application.capture.wine import from_wine_path

ArtifactPathResolver = Callable[[dict[str, Any]], Path | None]


class ArtifactError(ValueError):
    """An artifact cannot be opened or its bytes do not match its reference."""


def resolve_wine_artifact_path(path: str, bottle: Path) -> Path:
    """Map Wine C: through the resolved Steam bottle; reuse the shared Z: mapping."""
    windows = PureWindowsPath(path)
    if windows.drive.lower() == "c:":
        if not windows.is_absolute() or ".." in windows.parts:
            raise ArtifactError(f"Invalid Wine artifact path: {path}")
        return bottle / "drive_c" / Path(*windows.parts[1:])
    if windows.drive and windows.drive.lower() != "z:":
        raise ArtifactError(f"Unsupported Wine artifact drive: {windows.drive}")
    return from_wine_path(path)


class Artifact:
    """Read bytes/text/JSON only after finalization, size and SHA-256 checks.

    Domain-specific JSON schema and record-count checks remain the consumer's
    responsibility; a verified hash alone does not establish those semantics.
    """

    def __init__(self, reference: dict[str, Any], resolver: ArtifactPathResolver | None = None) -> None:
        self.reference = reference
        self.resolver = resolver

    def path(self) -> Path:
        if self.resolver is not None:
            resolved = self.resolver(self.reference)
            if resolved is not None:
                return resolved
        path = self.reference.get("path")
        if path is None:
            uri = urlsplit(self.reference["uri"])
            if uri.scheme != "file" or uri.netloc not in {"", "localhost"}:
                raise ArtifactError(f"Cannot open non-local artifact URI: {self.reference['uri']}")
            path = unquote(uri.path)
        if PureWindowsPath(path).drive:
            if PureWindowsPath(path).drive.lower() != "z:":
                raise ArtifactError(f"Wine artifact needs a CrossOver bottle resolver: {path}")
            return from_wine_path(path)
        return Path(path)

    def _check_reference(self) -> None:
        if self.reference.get("finalized") is not True:
            raise ArtifactError("Artifact is not finalized")
        size = self.reference.get("byteSize")
        digest = self.reference.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ArtifactError("Artifact byteSize must be a non-negative integer")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
            raise ArtifactError("Artifact sha256 must be a SHA-256 hex digest")

    def _check_bytes(self, size: int, digest: str) -> None:
        if size != self.reference["byteSize"]:
            raise ArtifactError(f"Artifact size mismatch: expected {self.reference['byteSize']}, got {size}")
        if digest != self.reference["sha256"].lower():
            raise ArtifactError(f"Artifact hash mismatch: expected {self.reference['sha256']}, got {digest}")

    def verify(self) -> Path:
        """Verify without retaining potentially large artifacts in memory."""
        self._check_reference()
        path = self.path()
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    digest.update(chunk)
        except OSError as exc:
            raise ArtifactError(f"Cannot read artifact {path}: {exc}") from exc
        self._check_bytes(size, digest.hexdigest())
        return path

    def bytes(self) -> bytes:
        self._check_reference()
        try:
            data = self.path().read_bytes()
        except OSError as exc:
            raise ArtifactError(f"Cannot read artifact: {exc}") from exc
        self._check_bytes(len(data), hashlib.sha256(data).hexdigest())
        return data

    def text(self) -> str:
        return self.bytes().decode("utf-8")

    def json(self) -> Any:
        import json

        return json.loads(self.text())
