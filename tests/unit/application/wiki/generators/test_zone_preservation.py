"""Unit tests for ZonePageGenerator field preservation.

Verifies that hand-curated content in the on-disk output file (wiki/zones/)
survives regeneration, even when fetched wiki storage is empty. This is the
regression test for the bug where `wiki generate` clobbered curated zone pages
with bare template stubs because field preservation read from fetched storage
instead of the on-disk output file.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from erenshor.application.wiki.generators.context import GeneratorContext
from erenshor.application.wiki.generators.pages.zones import ZonePageGenerator
from erenshor.domain.entities.zone import Zone

# Curated zone page as it lives on disk: template with manual fields plus a
# hand-authored NPC/Enemy/Boss table and prose description that must survive.
CURATED_SOLUNA = """[[Category:Soluna's Landing]]
{{Zone
|title=Soluna's Landing
|image=[[File:Solunas Landing.png|thumb]]
|imagecaption=
|type=Zone
|level=25-33
|maplink={{MapLink|zone=Soluna}}
|connects=[[Loomingwood Forest]], [[Malaroth's Nesting Grounds]]
}}
Soluna's Landing is located in the Northen part of [[Erenshor]].

{| class="wikitable"
|+Soluna's Landing
!NPCs
!Enemies
|-
|[[Illian Asboth]]
|[[Celestial Matter]]
|}
"""


def _make_zone(scene_name: str, wiki_page_name: str) -> Zone:
    """Build a minimal Zone entity for testing."""
    return Zone(
        stable_key=f"zone:{scene_name}",
        scene_name=scene_name,
        zone_name=wiki_page_name,
        is_dungeon=0,
        raid_capable=False,
        use_zone_as_temp_bind="",
        display_name=wiki_page_name,
        wiki_page_name=wiki_page_name,
        image_name="",
        is_wiki_generated=1,
        is_map_visible=1,
        achievement="",
    )


@pytest.fixture
def mock_context(tmp_path: Path) -> Mock:
    """Generator context with an in-memory zone repo and empty fetched storage."""
    ctx = Mock(spec=GeneratorContext)
    # Mock(spec=...) does not auto-create nested attributes; set up storage and
    # zone_repo so their methods can be called by the generator.
    storage = Mock()
    storage.read_fetched_by_title.return_value = None
    ctx.storage = storage
    zone_repo = Mock()
    soluna = _make_zone("Soluna", "Soluna's Landing")
    zone_repo.get_all_zones.return_value = [soluna]
    zone_repo.get_zone_connections.return_value = ["Loomingwood Forest", "Malaroth's Nesting Grounds"]
    ctx.zone_repo = zone_repo
    zone_positions_path = tmp_path / "zone-positions.json"
    zone_positions_path.write_text('{"Soluna": {}}', encoding="utf-8")
    ctx.zone_positions_path = zone_positions_path
    return ctx


class TestZonePagePreservation:
    """Field preservation for on-disk zone pages."""

    def test_preserves_curated_fields_from_existing_output_file(self, mock_context: Mock, tmp_path: Path) -> None:
        """Curated |image=, |level=, prose, and tables survive regeneration."""
        output_dir = tmp_path / "zones"
        output_dir.mkdir()
        (output_dir / "Soluna's_Landing.txt").write_text(CURATED_SOLUNA, encoding="utf-8")

        gen = ZonePageGenerator(mock_context, output_dir=output_dir)
        pages = list(gen.generate_pages())

        assert len(pages) == 1
        content = pages[0].content

        # Manually-set fields preserved (not blanked to stub defaults).
        assert "|level=25-33" in content
        assert "[[File:Solunas Landing.png|thumb]]" in content
        # Manual prose and tables survive (merge_templates keeps non-template content).
        assert "Soluna's Landing is located in the Northen part" in content
        assert "|+Soluna's Landing" in content
        assert "[[Illian Asboth]]" in content
        # Category line preserved.
        assert "[[Category:Soluna's Landing]]" in content

    def test_writes_stub_when_no_existing_file(self, mock_context: Mock, tmp_path: Path) -> None:
        """First generation of a new zone (no on-disk file) produces a stub."""
        output_dir = tmp_path / "zones"
        output_dir.mkdir()
        # No file on disk, no fetched copy — stub is expected here.

        gen = ZonePageGenerator(mock_context, output_dir=output_dir)
        pages = list(gen.generate_pages())

        assert len(pages) == 1
        content = pages[0].content
        # Stub template present with generated maplink.
        assert "{{Zone" in content
        assert "{{MapLink|zone=Soluna}}" in content
        # No curated content (none existed).
        assert "Illian Asboth" not in content

    def test_falls_back_to_fetched_storage_when_no_output_file(self, mock_context: Mock, tmp_path: Path) -> None:
        """If the on-disk file is absent, fetched storage is still consulted."""
        output_dir = tmp_path / "zones"
        output_dir.mkdir()
        # No on-disk file, but fetched storage has curated content.
        mock_context.storage.read_fetched_by_title.return_value = CURATED_SOLUNA

        gen = ZonePageGenerator(mock_context, output_dir=output_dir)
        pages = list(gen.generate_pages())

        assert len(pages) == 1
        content = pages[0].content
        assert "|level=25-33" in content
        assert "[[Illian Asboth]]" in content

    def test_on_disk_file_takes_precedence_over_stale_fetched(self, mock_context: Mock, tmp_path: Path) -> None:
        """On-disk file wins over a stale fetched copy when both exist."""
        output_dir = tmp_path / "zones"
        output_dir.mkdir()
        # On-disk has the curated level; fetched has a stale, different level.
        on_disk = CURATED_SOLUNA.replace("25-33", "30-40")
        (output_dir / "Soluna's_Landing.txt").write_text(on_disk, encoding="utf-8")
        stale_fetched = CURATED_SOLUNA.replace("25-33", "1-5")
        mock_context.storage.read_fetched_by_title.return_value = stale_fetched

        gen = ZonePageGenerator(mock_context, output_dir=output_dir)
        pages = list(gen.generate_pages())

        content = pages[0].content
        assert "|level=30-40" in content
        assert "1-5" not in content
