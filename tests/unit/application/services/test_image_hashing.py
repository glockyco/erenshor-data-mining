"""Focused contracts for shared image file hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from erenshor.application.hashing import SHA256_FILE_CHUNK_SIZE, sha256_file
from erenshor.application.services.image_processor import ImageProcessor
from erenshor.application.services.image_registry import ImageRegistry
from erenshor.domain.entities.image import ImageInfo


def test_sha256_file_returns_known_hex_digest(tmp_path: Path) -> None:
    """File hashing returns the expected hexadecimal SHA-256 digest."""
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(b"Erenshor image hashing")

    assert sha256_file(file_path) == hashlib.sha256(b"Erenshor image hashing").hexdigest()


def test_sha256_file_reads_only_fixed_size_chunks() -> None:
    """Hashing reads a file in the shared chunk size, including its final partial chunk."""

    payload = b"x" * (SHA256_FILE_CHUNK_SIZE * 2 + 3)
    read_sizes: list[int] = []
    returned_sizes: list[int] = []
    position = 0

    class RecordingStream:
        def __enter__(self) -> RecordingStream:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int) -> bytes:
            nonlocal position
            read_sizes.append(size)
            chunk = payload[position : position + size]
            position += len(chunk)
            returned_sizes.append(len(chunk))
            return chunk

    class RecordingPath:
        def open(self, mode: str) -> RecordingStream:
            assert mode == "rb"
            return RecordingStream()

    assert sha256_file(RecordingPath()) == hashlib.sha256(payload).hexdigest()  # type: ignore[arg-type]
    assert read_sizes == [SHA256_FILE_CHUNK_SIZE] * 4
    assert returned_sizes == [SHA256_FILE_CHUNK_SIZE, SHA256_FILE_CHUNK_SIZE, 3, 0]


def test_image_processor_hashes_source_and_output_with_shared_primitive(tmp_path: Path, monkeypatch) -> None:
    """Processor uses the shared primitive for both source and processed files."""
    source_path = tmp_path / "source.png"
    output_path = tmp_path / "output.png"
    Image.new("RGBA", (12, 8), (20, 30, 40, 255)).save(source_path)
    image_info = ImageInfo(
        entity_type="spell",
        stable_key="spell:test",
        entity_name="Test Spell",
        image_name="Test Spell",
        icon_name="source",
        source_path=source_path,
    )
    hashed_paths: list[Path] = []

    def fake_sha256_file(path: Path) -> str:
        hashed_paths.append(path)
        return "shared-digest"

    import erenshor.application.services.image_processor as image_processor_module

    monkeypatch.setattr(image_processor_module, "sha256_file", fake_sha256_file)

    result = ImageProcessor(tmp_path, tmp_path, tmp_path / "unused.sqlite").process_single_image(
        image_info, output_path
    )

    assert result.source_hash == "shared-digest"
    assert result.content_hash == "shared-digest"
    assert hashed_paths == [source_path, output_path]


def test_image_registry_hashes_processed_files_with_shared_primitive(tmp_path: Path, monkeypatch) -> None:
    """Registry content hashing delegates its file digest to the shared primitive."""
    image_path = tmp_path / "processed.png"
    Image.new("RGBA", (8, 8), (20, 30, 40, 255)).save(image_path)

    import erenshor.application.services.image_registry as image_registry_module

    monkeypatch.setattr(image_registry_module, "sha256_file", lambda path: "shared-digest")

    content_hash, perceptual_hash, file_size = ImageRegistry(tmp_path / "registry.db")._calculate_file_hashes(
        image_path
    )

    assert content_hash == "shared-digest"
    assert perceptual_hash
    assert file_size == image_path.stat().st_size
