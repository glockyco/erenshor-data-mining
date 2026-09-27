"""A failed perceptual-hash comparison never counts as an unchanged image."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from erenshor.application.services.image_registry import ImageComparisonError, ImageRegistry, ImageRegistryError
from erenshor.domain.entities.image import ImageInfo, ProcessingResult

SAME_PHASH = "8f373714acfcf4d0"
OTHER_PHASH = "70c8c8eb53030b2f"


def _register(registry: ImageRegistry, name: str, phash: str) -> None:
    registry.register_processed_image(
        stable_key=f"item:{name}",
        image_info=ImageInfo(
            stable_key=f"item:{name}",
            entity_type="item",
            entity_name=name,
            image_name=name,
            icon_name=name,
            source_path=None,
        ),
        processing_result=ProcessingResult(
            content_hash=f"content-{name}-{phash}",
            perceptual_hash=phash,
            processed_at="2026-09-27T00:00:00+00:00",
            file_size=100,
            dimensions=(64, 64),
            source_hash=f"source-{name}",
        ),
    )


def _classifications(registry: ImageRegistry) -> dict[str, str | None]:
    with sqlite3.connect(registry.db_path) as conn:
        return dict(conn.execute("SELECT stable_key, change_type FROM image_versions").fetchall())


def _registry_after_first_upload(tmp_path: Path) -> ImageRegistry:
    """Two images that were processed, compared, and uploaded once."""
    registry = ImageRegistry(tmp_path / "registry.db")
    _register(registry, "Sword", SAME_PHASH)
    _register(registry, "Shield", SAME_PHASH)
    registry.detect_changes()
    for name in ("Sword", "Shield"):
        registry.mark_uploaded(f"item:{name}", f"content-{name}-{SAME_PHASH}", f"{name}.png")
    return registry


def test_failed_comparison_is_reported_and_writes_no_classification(tmp_path: Path) -> None:
    registry = _registry_after_first_upload(tmp_path)
    _register(registry, "Sword", SAME_PHASH)
    _register(registry, "Shield", OTHER_PHASH)
    with sqlite3.connect(registry.db_path) as conn:
        conn.execute("UPDATE image_versions SET previous_phash = 'not-hex' WHERE stable_key = 'item:Shield'")

    with pytest.raises(ImageComparisonError, match="item:Shield") as error:
        registry.detect_changes()

    assert [stable_key for stable_key, _reason in error.value.failures] == ["item:Shield"]
    assert _classifications(registry) == {"item:Sword": None, "item:Shield": None}


def test_image_whose_comparison_failed_is_never_selected_as_needing_no_upload(tmp_path: Path) -> None:
    registry = _registry_after_first_upload(tmp_path)
    _register(registry, "Shield", OTHER_PHASH)
    with sqlite3.connect(registry.db_path) as conn:
        conn.execute("UPDATE image_versions SET previous_phash = 'not-hex' WHERE stable_key = 'item:Shield'")
    with pytest.raises(ImageComparisonError):
        registry.detect_changes()

    with pytest.raises(ImageRegistryError, match="item:Shield"):
        registry.get_deployment_list()


def test_completed_comparison_selects_only_the_modified_image(tmp_path: Path) -> None:
    registry = _registry_after_first_upload(tmp_path)
    _register(registry, "Sword", SAME_PHASH)
    _register(registry, "Shield", OTHER_PHASH)

    registry.detect_changes()

    assert _classifications(registry) == {"item:Sword": "unchanged", "item:Shield": "modified"}
    assert list(registry.get_deployment_list()) == ["Shield"]


def test_unreadable_previous_image_fails_instead_of_reusing_stored_hashes(tmp_path: Path) -> None:
    registry = _registry_after_first_upload(tmp_path)
    previous_dir = tmp_path / "previous"
    previous_dir.mkdir()
    (previous_dir / "item@Sword.png").write_bytes(b"not a png")

    with pytest.raises(ImageRegistryError, match=r"item@Sword\.png"):
        registry.register_processed_image(
            stable_key="item:Sword",
            image_info=ImageInfo(
                stable_key="item:Sword",
                entity_type="item",
                entity_name="Sword",
                image_name="Sword",
                icon_name="Sword",
                source_path=None,
            ),
            processing_result=ProcessingResult(
                content_hash="new",
                perceptual_hash=SAME_PHASH,
                processed_at="2026-09-27T00:00:00+00:00",
                file_size=100,
                dimensions=(64, 64),
                source_hash="source-Sword",
            ),
            previous_dir=previous_dir,
        )
